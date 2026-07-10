"""Planner generate node — LLM call to produce structured InterviewPlan (T014, REQ-05).

Takes ``planner_context`` (resume + JD) and ``web_research`` from graph state,
calls LLM with the planner prompt, and returns a validated ``InterviewPlan``.

Gracefully falls back to a minimal plan when the LLM call fails or returns
unparseable JSON.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog

from app.agents.interview.schemas import InterviewPlan
from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client

logger = structlog.get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """Read a prompt template from the prompts directory."""
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# User-message formatter
# ---------------------------------------------------------------------------

_DIMENSION_LABELS: list[tuple[str, str]] = [
    ("interview_experience", "面经"),
    ("company_tech_stack", "技术栈"),
    ("common_questions", "常见问题"),
]


def _format_resume_section(resume: dict[str, Any]) -> str:
    """Build a formatted resume block from planner_context data."""
    if not resume.get("has_resume"):
        return "（无简历数据）"

    lines: list[str] = []

    skills = resume.get("skills", [])
    if skills:
        lines.append("### 技能标签")
        lines.append(json.dumps(skills, ensure_ascii=False))

    experiences = resume.get("experiences", [])
    if experiences:
        lines.append("### 工作经历")
        for exp in experiences:
            title = exp.get("title", "")
            content = exp.get("content_md", "")
            lines.append(f"- {title}: {content[:500] if content else ''}")

    projects = resume.get("projects", [])
    if projects:
        lines.append("### 项目经验")
        for proj in projects:
            title = proj.get("title", "")
            content = proj.get("content_md", "")
            lines.append(f"- {title}: {content[:500] if content else ''}")

    education = resume.get("education", [])
    if education:
        lines.append("### 教育背景")
        for edu in education:
            title = edu.get("title", "")
            content = edu.get("content_md", "")
            lines.append(f"- {title}: {content[:500] if content else ''}")

    return "\n".join(lines)


def _format_job_section(job: dict[str, Any]) -> str:
    """Build a formatted job/JD block from planner_context data."""
    if not job.get("has_job"):
        return "（无岗位信息）"

    lines: list[str] = []
    lines.append(f"- 岗位名称: {job.get('position', '')}")
    lines.append(f"- 公司名称: {job.get('company', '')}")
    lines.append(f"- 岗位要求:\n{job.get('requirements_md', '未提供')}")
    lines.append(f"- 工作地点: {job.get('base_location', '未提供')}")
    lines.append(f"- 岗位类别: {job.get('employment_type', '未提供')}")
    if job.get("salary_range_text"):
        lines.append(f"- 薪资范围: {job['salary_range_text']}")
    return "\n".join(lines)


def _format_web_research_section(web_research: dict[str, Any] | None) -> str:
    """Build a formatted web-research block from state."""
    if not web_research:
        return "（无搜索结果）"

    lines: list[str] = []
    for dim, label in _DIMENSION_LABELS:
        items = web_research.get(dim, [])
        if not items:
            continue
        lines.append(f"\n### {label}")
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            lines.append(f"- {title}: {content[:300]}")
            if url:
                lines.append(f"  来源: {url}")
    return "\n".join(lines) if len(lines) > 1 else "（无搜索结果）"


def _format_memory_section(memories: list[dict[str, Any]] | None) -> str:
    """Build a 长期记忆 (long-term memory) block from planner_context.memories.

    REQ-028 US1: renders semantic memories retrieved by planner_context_node
    so the planner LLM can leverage cross-session user facts (target position,
    identified weaknesses, stated preferences). Empty memories → empty string
    (no section, no log spam for new users — FR-013 edge case).
    """
    if not memories:
        return ""

    lines: list[str] = []
    for mem in memories:
        if not isinstance(mem, dict):
            continue
        fact_key = mem.get("fact_key", "")
        fact_value = mem.get("fact_value", "")
        confidence = mem.get("confidence", 0.5)
        try:
            conf_str = f"{float(confidence):.2f}"
        except (TypeError, ValueError):
            conf_str = "0.50"
        source = mem.get("source", "unknown")
        lines.append(f"- {fact_key}: {fact_value} (置信度 {conf_str}, 来源 {source})")

    if not lines:
        return ""
    return "### 跨 session 记忆\n" + "\n".join(lines)


def _format_user_content(
    planner_context: dict[str, Any],
    web_research: dict[str, Any] | None,
) -> str:
    """Compose the user message from planner_context and web_research.

    The output is structured with clear section headers that align with the
    planner system prompt's expected input format.
    """
    resume = planner_context.get("resume", {})
    job = planner_context.get("job", {})
    memories = planner_context.get("memories")

    parts = [
        "## 简历数据",
        _format_resume_section(resume),
        "",
        "## 目标岗位信息",
        _format_job_section(job),
        "",
        "## 网络搜索结果",
        _format_web_research_section(web_research),
    ]
    memory_section = _format_memory_section(memories)
    if memory_section:
        parts.extend(["", "## 长期记忆", memory_section])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Plan validation / fallback
# ---------------------------------------------------------------------------


def _validate_plan(data: dict, state: InterviewGraphState) -> dict:
    """Convert the raw LLM JSON response into a validated ``InterviewPlan`` dict.

    Tolerant of minor LLM deviations (``name`` for ``area``, ``difficulty``
    for ``interview_difficulty``) but assumes the prompt's field layout.
    """
    try:
        raw_areas = data.get("focus_areas", [])
        if not isinstance(raw_areas, list):
            raw_areas = []
        focus_areas = [
            {
                "area": fa.get("area") or fa.get("name", ""),
                "weight": _normalise_weight(fa.get("weight")),
                "reason": fa.get("reason", ""),
            }
            for fa in raw_areas
            if isinstance(fa, dict)
        ]

        raw_qs = data.get("suggested_questions", [])
        suggested_questions = (
            [q.strip() for q in raw_qs if isinstance(q, str) and q.strip()]
            if isinstance(raw_qs, list) else []
        )

        tips = data.get("tips")
        if not isinstance(tips, list):
            tips = []

        # `or` fallback so empty-string LLM output doesn't shadow the
        # session-level context we explicitly seeded into graph state.
        plan = InterviewPlan(
            target_company=data.get("target_company") or state.get("company", ""),
            target_position=data.get("target_position") or state.get("position", ""),
            job_requirements=data.get("job_requirements"),
            tech_stack=data.get("tech_stack", []),
            interview_difficulty=_validate_difficulty(
                data.get("interview_difficulty") or data.get("difficulty")
            ),
            focus_areas=focus_areas,
            suggested_questions=suggested_questions,
            web_research_summary=data.get("web_research_summary"),
            tips=tips,
        )
        return plan.model_dump()

    except Exception as exc:
        logger.warning("planner_generate.validation_failed", error=str(exc))
        return _empty_plan(state)


def _normalise_weight(weight: Any | None) -> float:
    """Clamp an LLM-produced weight into [0.0, 1.0], defaulting to 0.5."""
    if weight is None:
        return 0.5
    try:
        w = float(weight)
        if 0.0 <= w <= 1.0:
            return round(w, 2)
    except (ValueError, TypeError):
        pass
    return 0.5


def _validate_difficulty(raw: Any) -> str:
    """Normalise difficulty to exactly one of ``easy``, ``medium``, ``hard``."""
    if isinstance(raw, str) and raw.strip().lower() in ("easy", "medium", "hard"):
        return raw.strip().lower()
    return "medium"


def _empty_plan(state: InterviewGraphState) -> dict:
    """Return a minimal InterviewPlan when generation fails entirely."""
    return InterviewPlan(
        target_company=state.get("company", ""),
        target_position=state.get("position", ""),
        interview_difficulty="medium",
        focus_areas=[],
        suggested_questions=[],
        tips=[],
    ).model_dump()


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


async def planner_generate_node(state: InterviewGraphState) -> dict[str, Any]:
    """Generate an ``InterviewPlan`` via LLM and return it as a state update.

    Reads ``planner_context`` (set by ``planner_context_node``) and
    ``web_research`` (set by ``planner_search_node``) from graph state,
    formats them into a prompt, invokes the LLM, and validates the response
    into a ``InterviewPlan`` model.

    REQ-058: skip regenerate when a usable ``interview_plan`` is already
    present; on failure return ``plan_error`` instead of silent empty success.
    """
    from app.agents.interview.plan_questions import is_plan_content_ready

    existing = state.get("interview_plan")
    if is_plan_content_ready(existing if isinstance(existing, dict) else None):
        focuses = (existing or {}).get("focus_areas") or []
        logger.info(
            "plan.reuse",
            reason="planner_generate_skip",
            focus_areas_count=len(focuses),
        )
        difficulty = (existing or {}).get("interview_difficulty") or state.get("difficulty")
        return {
            "interview_plan": existing,
            "difficulty": difficulty or "medium",
            "planner_focus_area_count": len(
                [a for a in focuses if isinstance(a, dict) and a.get("area")]
            ),
        }

    planner_context = state.get("planner_context") or {}
    web_research = state.get("web_research")

    if not planner_context:
        logger.warning("planner_generate.skip", reason="no_planner_context")
        return {
            "interview_plan": None,
            "plan_error": {
                "code": "PLAN_GENERATE_FAILED",
                "message": "缺少规划上下文，无法生成面试计划",
            },
            "plan_status": "failed",
        }

    user_content = _format_user_content(planner_context, web_research)
    system_prompt = _load_prompt("planner.md")

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            estimated_tokens=4000,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="planner_generate",
        )
        content = result["content"]

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            plan = _validate_plan(data, state)
        else:
            logger.warning(
                "planner_generate.no_json",
                content_preview=content[:300],
            )
            return {
                "interview_plan": None,
                "plan_error": {
                    "code": "PLAN_GENERATE_FAILED",
                    "message": "面试计划生成失败：模型未返回有效 JSON",
                },
                "plan_status": "failed",
            }

    except Exception as exc:
        from app.agents.llm_client import QuotaExceededError

        if isinstance(exc, QuotaExceededError):
            raise
        logger.warning("planner_generate.failed", error=str(exc), exc_info=True)
        return {
            "interview_plan": None,
            "plan_error": {
                "code": "PLAN_GENERATE_FAILED",
                "message": "面试计划生成失败，请稍后重试",
            },
            "plan_status": "failed",
        }

    if not is_plan_content_ready(plan):
        logger.warning("planner_generate.empty_plan")
        return {
            "interview_plan": None,
            "plan_error": {
                "code": "PLAN_GENERATE_FAILED",
                "message": "面试计划内容不完整",
            },
            "plan_status": "failed",
        }

    focus_areas_count = len(plan.get("focus_areas", []))
    suggested_questions_count = len(plan.get("suggested_questions", []))
    logger.info(
        "planner_generate.complete",
        target_company=plan.get("target_company", ""),
        target_position=plan.get("target_position", ""),
        focus_areas_count=focus_areas_count,
        suggested_questions_count=suggested_questions_count,
    )

    return {
        "interview_plan": plan,
        "difficulty": plan.get("interview_difficulty") or "medium",
        "planner_focus_area_count": focus_areas_count,
        "plan_status": "ready",
    }


__all__ = ["planner_generate_node"]
