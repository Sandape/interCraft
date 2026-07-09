"""[REQ-048 US4 AC-24 / T092] Markdown generator for the doubao card copy CTA.

Produces a Markdown string from an InterviewPlan that the user can
copy to clipboard and paste into Doubao / Notion / WeChat. Format is
locked per AC-24:

    # 面试大纲
    ## 公司: <target_company>
    ## 岗位: <target_position>
    ## 难度: <difficulty>
    ## 时长: <minutes> 分钟
    ## 关注重点: 1. <area>  2. <area> …
    ## 面试提示: 1. <tip>  2. <tip> …
    ## 大纲: 1. <question>  2. <question> …

The frontend lib (``src/lib/cardMarkdown.ts``) mirrors this Python
implementation; both are kept in lock-step so the test surface is
identical. The Python version is the canonical one because the
``test_card_markdown.py`` unit test exercises it.
"""
from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _focus_area_text(area: Any) -> str:
    if isinstance(area, dict):
        name = _safe_str(area.get("area") or area.get("name"))
        reason = _safe_str(area.get("reason"))
        if reason:
            return f"{name}（{reason}）" if name else reason
        return name
    return _safe_str(area)


def build_card_markdown(plan: dict[str, Any]) -> str:
    """Render InterviewPlan → Markdown string for the copy CTA.

    Tolerant of missing fields — empty strings render as blanks
    (never raises).
    """
    company = _safe_str(plan.get("target_company") or plan.get("company"))
    position = _safe_str(plan.get("target_position") or plan.get("position"))
    difficulty = _safe_str(plan.get("interview_difficulty"))
    duration = _safe_str(plan.get("estimated_duration_minutes"))

    focus_areas = [
        _focus_area_text(a) for a in _as_list(plan.get("focus_areas"))
    ]
    focus_areas = [a for a in focus_areas if a]

    suggested_questions = [
        _safe_str(q) for q in _as_list(plan.get("suggested_questions"))
    ]
    suggested_questions = [q for q in suggested_questions if q]

    tips = [_safe_str(t) for t in _as_list(plan.get("tips"))]
    tips = [t for t in tips if t]

    lines: list[str] = ["# 面试大纲"]
    lines.append(f"## 公司: {company}")
    lines.append(f"## 岗位: {position}")
    if difficulty:
        lines.append(f"## 难度: {difficulty}")
    if duration:
        lines.append(f"## 时长: {duration} 分钟")

    if focus_areas:
        lines.append("## 关注重点:")
        for i, area in enumerate(focus_areas[:8], start=1):
            lines.append(f"{i}. {area}")

    if tips:
        lines.append("## 面试提示:")
        for i, tip in enumerate(tips[:8], start=1):
            lines.append(f"{i}. {tip}")

    if suggested_questions:
        lines.append("## 大纲:")
        for i, q in enumerate(suggested_questions[:8], start=1):
            lines.append(f"{i}. {q}")
    else:
        # AC-24: even when no outlines the section header is emitted
        # so users always see the contract.
        lines.append("## 大纲: (无)")

    lines.append("")
    lines.append("— 来自 InterCraft 豆包面试卡")

    return "\n".join(lines)


__all__ = ["build_card_markdown"]