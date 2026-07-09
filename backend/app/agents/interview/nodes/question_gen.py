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
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import UUID

from app.agents.interview.effective_max import (
    HARD_MAX_QUESTIONS_FULL,
    HARD_MIN_QUESTIONS_FULL,
    compute_effective_max,
    compute_planner_recommended,
)
from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client
from app.agents.interview.requirements_block import build_requirements_block
from app.agents.utils.node_error_handler import node_error_handler
from app.observability import traced_node
import structlog

logger = structlog.get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Dimension rotation: cycle through 5 dimensions
DIMENSIONS = [
    "tech_depth",
    "architecture",
    "engineering_practice",
    "communication",
    "algorithm",
]


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def _fetch_error_question_payload(source_question_id: str) -> dict | None:
    """Fetch the source error_question row (text + dimension) for replay.

    Phase 4 / US2 implementation hits ``error_questions`` directly via
    SQLAlchemy. Phase 1+2 skeleton returns None so the LLM fallback path
    remains in effect.
    """
    return None


def _resolve_effective_max(state: InterviewGraphState) -> int:
    """Resolve effective_max from state for the current session.

    Reads ``state.max_questions`` (user choice) and
    ``state.planner_recommended`` (set by planner graph via
    ``state.effective_max`` if present). Falls back to computing
    from ``state.max_questions`` + a derived planner value.
    """
    # Prefer the precomputed effective_max when the planner wrote it.
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
    """Generate the next interview question based on state context.

    Quick-drill mode (REQ-048 US2 FR-030 + FR-031): when
    ``state.error_question_ids`` is non-empty the next source question is
    replayed verbatim (no LLM call); otherwise the LLM path runs.

    US3 termination (REQ-048 US3 T069 + AC-13): when
    ``current_question >= effective_max`` the node returns an empty
    delta so the routing edge takes the report path. The
    ``effective_max`` is resolved from state via
    :func:`_resolve_effective_max`.

    Rotates through dimensions: tech_depth → architecture →
    engineering_practice → communication → algorithm.
    """
    current = state.get("current_question", 0)
    questions = state.get("questions", [])

    # REQ-048 US3 T069 — terminate at effective_max. The state is
    # expected to carry effective_max (written by planner or by
    # InterviewSessionCreate before the graph starts). When current has
    # reached the cap, return early with no new question so the
    # downstream edge routes to ``report`` instead of generating another
    # question (AC-13 + AC-15 + AC-16a).
    effective_max = _resolve_effective_max(state)
    mode = state.get("mode")
    if mode == "full" and current >= effective_max:
        logger.info(
            "interview.question_gen.terminate_at_effective_max",
            current=current,
            effective_max=effective_max,
            user_id=state.get("user_id"),
        )
        return {}

    # REQ-048 quick-drill replay path.
    error_question_ids = state.get("error_question_ids") or []
    if error_question_ids and current < len(error_question_ids):
        sid = str(error_question_ids[current])
        payload = _fetch_error_question_payload(sid) or {}
        new_question = {
            "question_no": current + 1,
            "dimension": payload.get("dimension", DIMENSIONS[current % len(DIMENSIONS)]),
            "question": payload.get("question", "") or f"[REPLAY] {sid}",
            "expected_points": payload.get("expected_points", []),
            "hints": [],
            "source_question_id": sid,
        }
        return {
            "questions": [*questions, new_question],
            "current_question": current + 1,
        }

    dimension = DIMENSIONS[current % len(DIMENSIONS)]
    previous_questions = json.dumps(
        [q.get("question", "") for q in questions], ensure_ascii=False
    )

    # 019 — inject requirements_md block (capped at MAX_REQUIREMENTS_TOKENS)
    raw_req = state.get("requirements_md")
    block, provided, truncated, original_chars = build_requirements_block(raw_req)
    if raw_req and provided and not state.get("requirements_provided"):
        # The state was missing the booleans (e.g. resumed session without
        # them). Re-stamp them so the report node still gets correct values.
        state["requirements_provided"] = True
        state["requirements_truncated"] = truncated
        state["requirements_original_chars"] = original_chars

    template = _load_prompt("question_gen.md")
    prompt = template.format(
        position=state.get("position", ""),
        company=state.get("company", ""),
        difficulty=state.get("difficulty", "medium"),
        current_question=current + 1,
        dimension=dimension,
        topics_to_probe="根据岗位要求自动选择",
        previous_questions=previous_questions if previous_questions else "无",
        requirements_md_block=block if block else "",
    )

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位技术面试官，负责生成面试题。所有 JSON 字段值必须使用中文（zh-CN），仅 JSON 的 key 保持英文。`dimension` 字段值必须使用英文 key，其余字段（question、expected_points、hints）必须为中文。只返回 JSON，不要包含任何解释或 markdown 标记。"},
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
            q_data = {"question": content, "dimension": dimension, "difficulty": state.get("difficulty", "medium")}
    except Exception:
        q_data = {
            "question": f"请分享你在{dimension}方面的经验和理解。",
            "dimension": dimension,
            "difficulty": state.get("difficulty", "medium"),
        }

    new_question = {
        "question_no": current + 1,
        "dimension": dimension,
        "question": q_data.get("question", ""),
        "expected_points": q_data.get("expected_points", []),
        "hints": q_data.get("hints", []),
    }

    return {
        "questions": [*questions, new_question],
        "current_question": current + 1,
        "effective_max": effective_max,
    }


__all__ = ["question_gen_node"]
