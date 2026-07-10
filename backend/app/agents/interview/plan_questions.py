"""Plan-driven question selection helpers (REQ-058).

Normative algorithm: ``specs/058-interview-agent-optimize/contracts/question-selection.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.agents.interview.placeholders import display_target_or_fallback

SourceKind = Literal["suggested", "generated", "template_degraded", "blocked"]

FALLBACK_DIMENSIONS = [
    "tech_depth",
    "architecture",
    "engineering_practice",
    "communication",
    "algorithm",
]


@dataclass(frozen=True)
class QuestionSpec:
    """Pure selection result before LLM polish / persistence."""

    question_no: int
    source: SourceKind
    focus: str
    question: str | None
    dimension: str
    expected_points: list[str]
    use_plan_block: bool
    blocked_reason: str | None = None


def build_focus_schedule(
    focus_areas: list[dict[str, Any]] | None,
    n: int,
) -> list[str]:
    """Allocate ``n`` focus labels from weighted ``focus_areas`` (largest remainder).

    Each area contributes ``floor(weight * n)`` slots; remaining seats go to
    the largest fractional parts. High-weight areas appear at least
    ``floor(w * n)`` times.
    """
    if n <= 0:
        return []
    areas = [a for a in (focus_areas or []) if isinstance(a, dict) and a.get("area")]
    if not areas:
        return ["general"] * n

    weights: list[float] = []
    labels: list[str] = []
    for area in areas:
        labels.append(str(area.get("area") or "general"))
        try:
            w = float(area.get("weight", 0) or 0)
        except (TypeError, ValueError):
            w = 0.0
        weights.append(max(0.0, w))

    total = sum(weights)
    if total <= 0:
        # Equal share
        base = n // len(labels)
        rem = n % len(labels)
        schedule: list[str] = []
        for i, label in enumerate(labels):
            schedule.extend([label] * (base + (1 if i < rem else 0)))
        return schedule[:n]

    raw = [w / total * n for w in weights]
    floors = [int(x) for x in raw]
    assigned = sum(floors)
    remainders = sorted(
        ((raw[i] - floors[i], i) for i in range(len(labels))),
        key=lambda t: (-t[0], t[1]),
    )
    for k in range(n - assigned):
        floors[remainders[k % len(remainders)][1]] += 1

    # Interleave by repeating each label its count (stable order by area list)
    schedule = []
    for label, count in zip(labels, floors, strict=False):
        schedule.extend([label] * count)
    # If rounding overflowed, trim; if short, pad with first label
    if len(schedule) > n:
        schedule = schedule[:n]
    while len(schedule) < n:
        schedule.append(labels[0])
    return schedule


def _used_suggested_texts(questions: list[dict[str, Any]]) -> set[str]:
    used: set[str] = set()
    for q in questions or []:
        if not isinstance(q, dict):
            continue
        if q.get("source") == "suggested":
            text = (q.get("question") or "").strip()
            if text:
                used.add(text)
    return used


def _map_focus_to_dimension(focus: str) -> str:
    """Best-effort map Chinese/English focus labels to scoring dimension keys."""
    f = (focus or "").casefold()
    mapping = (
        (("架构", "architecture", "系统设计", "system"), "architecture"),
        (("算法", "algorithm", "leetcode", "数据结构"), "algorithm"),
        (("工程", "ci", "测试", "工程实践", "engineering"), "engineering_practice"),
        (("沟通", "协作", "communication", "文档"), "communication"),
        (("业务", "business"), "business_understanding"),
        (("技术", "tech", "深度", "后端", "前端", "java", "python", "go"), "tech_depth"),
    )
    for keys, dim in mapping:
        if any(k in f for k in keys):
            return dim
    return "tech_depth"


def is_plan_content_ready(plan: dict[str, Any] | None) -> bool:
    """True when plan has usable focus areas or suggested questions."""
    if not isinstance(plan, dict):
        return False
    suggestions = plan.get("suggested_questions") or []
    focuses = plan.get("focus_areas") or []
    has_suggestions = any(isinstance(s, str) and s.strip() for s in suggestions)
    has_focus = any(isinstance(a, dict) and a.get("area") for a in focuses)
    return has_suggestions or has_focus


def select_next_question_spec(
    *,
    interview_plan: dict[str, Any] | None,
    plan_status: str | None,
    degraded: bool,
    questions: list[dict[str, Any]] | None,
    max_questions: int,
    position: str | None = None,
    company: str | None = None,
) -> QuestionSpec:
    """Select the next question source per question-selection contract."""
    asked = list(questions or [])
    question_no = len(asked) + 1
    n = max(1, int(max_questions or 10))
    status = (plan_status or "").strip().lower() or (
        "ready" if is_plan_content_ready(interview_plan) else "pending"
    )

    schedule = build_focus_schedule(
        (interview_plan or {}).get("focus_areas") if interview_plan else None,
        n,
    )
    focus = schedule[min(question_no - 1, len(schedule) - 1)] if schedule else "general"
    dimension = _map_focus_to_dimension(focus)
    if status == "degraded" or degraded:
        dimension = FALLBACK_DIMENSIONS[(question_no - 1) % len(FALLBACK_DIMENSIONS)]

    if status == "failed" and not degraded:
        return QuestionSpec(
            question_no=question_no,
            source="blocked",
            focus=focus,
            question=None,
            dimension=dimension,
            expected_points=[],
            use_plan_block=False,
            blocked_reason="plan_status_failed",
        )

    plan_ready = status == "ready" and is_plan_content_ready(interview_plan)
    if plan_ready and interview_plan:
        suggestions = [
            s.strip()
            for s in (interview_plan.get("suggested_questions") or [])
            if isinstance(s, str) and s.strip()
        ]
        used = _used_suggested_texts(asked)
        # Also treat exact prior stems as used even without source tag
        for q in asked:
            if isinstance(q, dict):
                t = (q.get("question") or "").strip()
                if t:
                    used.add(t)
        for suggestion in suggestions:
            if suggestion not in used:
                # Light sanitize: strip junk company/position substrings if present
                company_disp = display_target_or_fallback(company, kind="company")
                position_disp = display_target_or_fallback(position, kind="position")
                text = suggestion
                if company and not company_disp:
                    text = text.replace(str(company), "目标公司")
                if position and not position_disp:
                    text = text.replace(str(position), "目标岗位")
                return QuestionSpec(
                    question_no=question_no,
                    source="suggested",
                    focus=focus,
                    question=text,
                    dimension=dimension,
                    expected_points=[],
                    use_plan_block=True,
                )

        return QuestionSpec(
            question_no=question_no,
            source="generated",
            focus=focus,
            question=None,
            dimension=dimension,
            expected_points=[],
            use_plan_block=True,
        )

    if degraded or status == "degraded":
        return QuestionSpec(
            question_no=question_no,
            source="template_degraded",
            focus=focus,
            question=None,
            dimension=dimension,
            expected_points=[],
            use_plan_block=False,
        )

    # No plan yet — fail closed for formal questions (caller may still allow intro)
    return QuestionSpec(
        question_no=question_no,
        source="blocked",
        focus=focus,
        question=None,
        dimension=dimension,
        expected_points=[],
        use_plan_block=False,
        blocked_reason="plan_not_ready",
    )


def format_plan_prompt_block(plan: dict[str, Any] | None) -> str:
    """Render plan context for question_gen LLM prompts."""
    if not isinstance(plan, dict):
        return ""
    lines: list[str] = ["### 面试计划上下文"]
    focuses = plan.get("focus_areas") or []
    if focuses:
        lines.append("重点考察领域:")
        for fa in focuses:
            if not isinstance(fa, dict):
                continue
            area = fa.get("area", "")
            weight = fa.get("weight", "")
            reason = fa.get("reason", "")
            lines.append(f"- {area} (weight={weight}): {reason}")
    tips = plan.get("tips") or []
    if tips:
        lines.append("面试官提示:")
        for tip in tips:
            if isinstance(tip, str) and tip.strip():
                lines.append(f"- {tip.strip()}")
    stack = plan.get("tech_stack") or []
    if stack:
        lines.append("技术栈: " + ", ".join(str(x) for x in stack if x))
    summary = plan.get("web_research_summary")
    if isinstance(summary, str) and summary.strip():
        lines.append("调研摘要: " + summary.strip()[:800])
    req = plan.get("job_requirements")
    if isinstance(req, str) and req.strip():
        lines.append("岗位要求摘要: " + req.strip()[:800])
    return "\n".join(lines)


__all__ = [
    "QuestionSpec",
    "build_focus_schedule",
    "format_plan_prompt_block",
    "is_plan_content_ready",
    "select_next_question_spec",
]
