"""Question generation node — generates interview questions (T026).

REQ-048 (US2): when ``state.error_question_ids`` is non-empty the node
short-circuits and returns the next error question from the list (FR-030
+ FR-031) instead of asking the LLM to generate a new question. This
preserves the original question_text (one-character equality required by
AC-25 default behavior) and dimension.

REQ-048 (US3 T069): the node respects ``state.effective_max`` so the
「完整面试」 mode terminates at 7-15 questions (FR-023 + AC-13). When
``current_question`` has reached ``effective_max`` the node returns an
empty state delta so the routing edge takes the report path instead of
asking the LLM for one more question.

REQ-058: plan-driven selection via ``plan_questions`` helpers; sanitize
targets; gate on failed plan unless degraded.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.interview.effective_max import (
    HARD_MAX_QUESTIONS_FULL,
    HARD_MIN_QUESTIONS_FULL,
    compute_effective_max,
    compute_planner_recommended,
)
from app.agents.interview.noop import noop_state_delta
from app.agents.interview.placeholders import display_target_or_fallback
from app.agents.interview.plan_questions import (
    format_plan_prompt_block,
    select_next_question_spec,
)
from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client
from app.agents.interview.requirements_block import build_requirements_block
from app.agents.utils.node_error_handler import node_error_handler
from app.observability import traced_node
import structlog

logger = structlog.get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Dimension rotation: cycle through 5 dimensions (degraded / fallback only)
DIMENSIONS = [
    "tech_depth",
    "architecture",
    "engineering_practice",
    "communication",
    "algorithm",
]

DIMENSION_LABELS = {
    "tech_depth": "技术深度",
    "architecture": "系统架构",
    "engineering_practice": "工程实践",
    "communication": "沟通协作",
    "algorithm": "算法能力",
}


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def _parse_expected_points(reference_answer_md: str | None) -> list[str]:
    if not isinstance(reference_answer_md, str) or not reference_answer_md.strip():
        return []
    return [
        line.strip("- ").strip()
        for line in reference_answer_md.splitlines()
        if line.strip()
    ][:8]


async def _afetch_error_question_payload(
    source_question_id: str, user_id: str | None = None
) -> dict | None:
    """Load error_question text + dimension for quick_drill verbatim replay."""
    if not source_question_id:
        return None
    try:
        from uuid import UUID

        from sqlalchemy import text

        from app.core.db import get_session_context

        uid = None
        if user_id:
            try:
                uid = UUID(str(user_id))
            except (TypeError, ValueError):
                uid = None

        user_filter = "AND user_id = CAST(:uid AS uuid)" if uid else ""
        async with get_session_context(user_id=uid) as session:
            stmt = text(
                f"""
                SELECT dimension, question_text, reference_answer_md
                FROM error_questions
                WHERE deleted_at IS NULL
                  AND (
                    source_question_id::text = :sid
                    OR id::text = :sid
                  )
                  {user_filter}
                ORDER BY
                  CASE WHEN source_question_id::text = :sid THEN 0 ELSE 1 END,
                  updated_at DESC
                LIMIT 1
                """
            )
            params = {"sid": str(source_question_id)}
            if uid:
                params["uid"] = str(uid)
            result = await session.execute(stmt, params)
            row = result.mappings().first()
            if not row:
                return None
            return {
                "dimension": row.get("dimension") or "",
                "question": row.get("question_text") or "",
                "expected_points": _parse_expected_points(row.get("reference_answer_md")),
            }
    except Exception:
        logger.warning(
            "interview.question_gen.replay_fetch_failed",
            source_question_id=source_question_id,
            exc_info=True,
        )
        return None


def _resolve_effective_max(state: InterviewGraphState) -> int:
    precomputed = state.get("effective_max")
    if isinstance(precomputed, int) and HARD_MIN_QUESTIONS_FULL <= precomputed <= HARD_MAX_QUESTIONS_FULL:
        return precomputed
    user_choice = state.get("max_questions") or 10
    focus_count = state.get("planner_focus_area_count") or 3
    planner = compute_planner_recommended(int(focus_count))
    return compute_effective_max(int(user_choice), planner)


@node_error_handler(fallback_strategy="retry")
@traced_node("interview.question_gen")
async def question_gen_node(state: InterviewGraphState) -> dict:
    """Generate the next interview question based on state context."""
    current = state.get("current_question", 0)
    questions = state.get("questions", [])

    effective_max = _resolve_effective_max(state)
    mode = state.get("mode")
    if mode == "full" and current >= effective_max:
        logger.info(
            "interview.question_gen.terminate_at_effective_max",
            current=current,
            effective_max=effective_max,
            user_id=state.get("user_id"),
        )
        return noop_state_delta(state)

    # REQ-048 quick-drill replay path.
    error_question_ids = state.get("error_question_ids") or []
    if error_question_ids and current < len(error_question_ids):
        sid = str(error_question_ids[current])
        payload = await _afetch_error_question_payload(
            sid, user_id=str(state.get("user_id") or "") or None
        ) or {}
        new_question = {
            "question_no": current + 1,
            "dimension": payload.get("dimension", DIMENSIONS[current % len(DIMENSIONS)]),
            "question": payload.get("question", "") or f"[REPLAY] {sid}",
            "expected_points": payload.get("expected_points", []),
            "hints": [],
            "source_question_id": sid,
            "source": "replay",
        }
        return {
            "questions": [*questions, new_question],
            "current_question": current + 1,
        }

    plan = state.get("interview_plan") if isinstance(state.get("interview_plan"), dict) else None
    plan_status = state.get("plan_status")
    degraded = bool(state.get("degraded", False))
    if not plan_status and plan:
        plan_status = "ready"

    position = display_target_or_fallback(state.get("position"), kind="position", fallback="")
    company = display_target_or_fallback(state.get("company"), kind="company", fallback="")

    spec = select_next_question_spec(
        interview_plan=plan,
        plan_status=plan_status,
        degraded=degraded,
        questions=questions,
        max_questions=effective_max,
        position=state.get("position"),
        company=state.get("company"),
    )

    if spec.source == "blocked":
        logger.warning(
            "interview.question_gen.blocked",
            reason=spec.blocked_reason,
            plan_status=plan_status,
            degraded=degraded,
        )
        return {
            **noop_state_delta(state),
            "error": {
                "error_category": "plan_blocked",
                "node_name": "question_gen",
                "message": "面试计划未就绪，无法出题",
                "code": spec.blocked_reason or "plan_not_ready",
            },
        }

    dimension = spec.dimension or DIMENSIONS[current % len(DIMENSIONS)]

    # Suggested path — use plan stem directly (optional light LLM polish skipped in v1)
    if spec.source == "suggested" and spec.question:
        logger.info(
            "question.from_suggested",
            question_no=spec.question_no,
            focus=spec.focus,
            dimension=dimension,
        )
        new_question = {
            "question_no": spec.question_no,
            "dimension": dimension,
            "question": spec.question,
            "expected_points": spec.expected_points or [],
            "hints": [],
            "source": "suggested",
            "focus": spec.focus,
        }
        return {
            "questions": [*questions, new_question],
            "current_question": current + 1,
            "effective_max": effective_max,
            "planner_focus_area_count": state.get("planner_focus_area_count")
            or len((plan or {}).get("focus_areas") or []),
        }

    if spec.source == "template_degraded":
        label = DIMENSION_LABELS.get(dimension, "综合能力")
        logger.info(
            "question.from_template_degraded",
            question_no=spec.question_no,
            dimension=dimension,
        )
        new_question = {
            "question_no": spec.question_no,
            "dimension": dimension,
            "question": (
                f"请结合一个真实项目，分享你在{label}方面的实践："
                "当时的目标是什么，你负责了哪些关键设计，遇到的难点如何解决，"
                "最后如何验证效果。"
            ),
            "expected_points": [],
            "hints": [],
            "source": "template_degraded",
            "focus": spec.focus,
        }
        return {
            "questions": [*questions, new_question],
            "current_question": current + 1,
            "effective_max": effective_max,
            "planner_focus_area_count": state.get("planner_focus_area_count")
            or len((plan or {}).get("focus_areas") or []),
        }

    previous_questions = json.dumps(
        [q.get("question", "") for q in questions], ensure_ascii=False
    )

    raw_req = state.get("requirements_md")
    block, provided, truncated, original_chars = build_requirements_block(raw_req)
    if raw_req and provided and not state.get("requirements_provided"):
        state["requirements_provided"] = True
        state["requirements_truncated"] = truncated
        state["requirements_original_chars"] = original_chars

    plan_block = format_plan_prompt_block(plan) if spec.use_plan_block else ""
    template = _load_prompt("question_gen.md")
    prompt = template.format(
        position=position or state.get("position", "") or "目标岗位",
        company=company or state.get("company", "") or "目标公司",
        difficulty=state.get("difficulty", "medium"),
        current_question=current + 1,
        max_questions=effective_max,
        dimension=dimension,
        topics_to_probe=spec.focus or "根据岗位要求与面试计划选择",
        previous_questions=previous_questions if previous_questions else "无",
        requirements_md_block=block if block else "",
        plan_context_block=plan_block,
    )

    client = get_llm_client()
    source = spec.source
    try:
        result = await client.invoke(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一位技术面试官，负责生成面试题。所有 JSON 字段值必须使用中文（zh-CN），"
                        "仅 JSON 的 key 保持英文。`dimension` 字段值必须使用英文 key，其余字段"
                        "（question、expected_points、hints）必须为中文。只返回 JSON，不要包含任何解释或 markdown 标记。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=2500,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="question_gen",
        )
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            q_data = json.loads(json_match.group(0))
        else:
            q_data = {
                "question": content,
                "dimension": dimension,
                "difficulty": state.get("difficulty", "medium"),
            }
    except Exception:
        if source != "template_degraded" and plan_status == "ready":
            # Never silently template when plan is ready
            logger.error(
                "interview.question_gen.llm_failed_with_ready_plan",
                exc_info=True,
            )
            raise
        q_data = {
            "question": f"请分享你在{dimension}方面的经验和理解。",
            "dimension": dimension,
            "difficulty": state.get("difficulty", "medium"),
            "expected_points": [],
        }
        source = "template_degraded"

    if source == "generated":
        logger.info(
            "question.from_generated",
            question_no=spec.question_no,
            focus=spec.focus,
            dimension=dimension,
        )
    elif source == "template_degraded":
        logger.info(
            "question.from_template_degraded",
            question_no=spec.question_no,
            dimension=dimension,
        )

    stem = q_data.get("question", "") or ""
    # Scrub junk targets if they leaked into LLM output
    raw_company = state.get("company") or ""
    raw_position = state.get("position") or ""
    if raw_company and not company:
        stem = stem.replace(str(raw_company), "目标公司")
    if raw_position and not position:
        stem = stem.replace(str(raw_position), "目标岗位")

    new_question = {
        "question_no": current + 1,
        "dimension": q_data.get("dimension") or dimension,
        "question": stem,
        "expected_points": q_data.get("expected_points", []) or [],
        "hints": q_data.get("hints", []) or [],
        "source": source,
        "focus": spec.focus,
    }

    return {
        "questions": [*questions, new_question],
        "current_question": current + 1,
        "effective_max": effective_max,
        "planner_focus_area_count": state.get("planner_focus_area_count")
        or len((plan or {}).get("focus_areas") or []),
    }


__all__ = ["question_gen_node"]
