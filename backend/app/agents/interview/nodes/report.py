"""Report node — generates final interview summary (T028)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.interview.state import InterviewGraphState
from app.agents.llm_client import get_llm_client
from app.agents.utils.node_error_handler import node_error_handler
from app.observability import traced_node

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


@node_error_handler(fallback_strategy="hard_fail")
@traced_node("interview.report")
async def report_node(state: InterviewGraphState) -> dict:
    """Aggregate scores by rule and generate a short LLM narrative summary.

    REQ-058: overall / per_question / dimension_scores are rule-aggregated from
    actual N scores (not a fixed five-round assumption). Improvements should
    reference plan focus_areas when available.
    """
    scores = state.get("scores", [])
    questions = state.get("questions", [])
    plan = state.get("interview_plan") if isinstance(state.get("interview_plan"), dict) else {}
    focus_areas = plan.get("focus_areas") or []

    # Rule aggregate first — authoritative numeric fields
    report_data = _fallback_report(scores, questions, focus_areas=focus_areas)

    local_scoring = any(
        isinstance(s, dict) and str(s.get("scoring_method", "")).startswith("local_")
        for s in scores
    )
    if state.get("degraded") or local_scoring:
        report_data = _normalize_report(report_data, scores, questions, focus_areas=focus_areas)
        report_data["report_source"] = "local_degraded" if state.get("degraded") else "local_rule"
        report_data["summary_md"] = (
            f"本报告基于规则评分汇总生成，共完成 {len(scores)} 轮问答。"
            f"综合评分 {report_data.get('overall_score', 0)}/10，数值来自每轮实际评分，"
            "未调用外部 LLM 生成总结。"
        )
        return {
            "overall_score": report_data.get("overall_score", 5.0),
            "interview_report": report_data,
        }

    template = _load_prompt("report.md")
    prompt = template.format(
        position=state.get("position", ""),
        company=state.get("company", ""),
        difficulty=state.get("difficulty", "medium"),
        question_count=len(scores),
        scores=json.dumps(scores, ensure_ascii=False),
        focus_areas=json.dumps(focus_areas, ensure_ascii=False),
        format_instructions="Return valid JSON only.",
    )

    client = get_llm_client()
    try:
        result = await client.invoke(
            messages=[
                {"role": "system", "content": "你是一位面试总结报告生成专家。所有 JSON 字段值必须使用中文（zh-CN），仅 JSON 的 key 保持英文。`dimension` 字段值必须使用英文 key，所有文本字段必须为中文。`summary_md` 必须是 3-5 句纯文字中文段落，不要使用 markdown 标记。只返回 JSON。"},
                {"role": "user", "content": prompt},
            ],
            estimated_tokens=3500,
            user_id=state.get("user_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            node_name="report",
        )
        content = result["content"]
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            llm_part = json.loads(json_match.group(0))
            if isinstance(llm_part, dict):
                for key in ("strengths", "improvements", "summary_md"):
                    if llm_part.get(key):
                        report_data[key] = llm_part[key]
    except Exception:
        pass

    report_data = _normalize_report(report_data, scores, questions, focus_areas=focus_areas)

    if state.get("requirements_provided") and state.get("requirements_md"):
        original = state.get("requirements_md", "")
        snippet = original[:500]
        suffix = "…" if len(original) > 500 else ""
        report_data["requirements_summary"] = (
            f"本次面试基于岗位招聘需求生成题目。原始需求 ({state.get('requirements_original_chars', len(original))} 字):\n\n"
            f"{snippet}{suffix}"
        )

    overall_score = report_data.get("overall_score", 5.0)

    return {
        "overall_score": overall_score,
        "interview_report": report_data,
    }


def _normalize_report(
    report_data: dict,
    scores: list,
    questions: list,
    *,
    focus_areas: list | None = None,
) -> dict:
    """Ensure the report contract is complete even when the LLM returns partial JSON."""
    fallback = _fallback_report(scores, questions, focus_areas=focus_areas)
    if not isinstance(report_data, dict) or not report_data:
        return fallback

    normalized = {**fallback, **report_data}

    # Always keep rule-based numeric aggregates
    normalized["per_question_score"] = fallback["per_question_score"]
    normalized["overall_score"] = fallback["overall_score"]
    normalized["dimension_scores"] = fallback["dimension_scores"]

    if not isinstance(normalized.get("strengths"), list):
        normalized["strengths"] = fallback["strengths"]
    if not isinstance(normalized.get("improvements"), list):
        normalized["improvements"] = fallback["improvements"]
    if not isinstance(normalized.get("summary_md"), str) or not normalized["summary_md"].strip():
        normalized["summary_md"] = fallback["summary_md"]

    # Scrub five-round assumptions from LLM copy
    summary = normalized.get("summary_md") or ""
    if isinstance(summary, str):
        for bad in ("五轮", "5 轮", "5轮", "五个问题"):
            summary = summary.replace(bad, f"{len(scores)} 轮")
        normalized["summary_md"] = summary

    return normalized


def _coerce_score(value: object, fallback: float | int) -> float | int:
    if isinstance(value, bool):
        return fallback
    try:
        score = float(value)
    except (TypeError, ValueError):
        return fallback
    if score < 0 or score > 10:
        return fallback
    return round(score, 2)


def _fallback_report(
    scores: list,
    questions: list,
    *,
    focus_areas: list | None = None,
) -> dict:
    """Generate a basic report without LLM (rule aggregate)."""
    n = len(scores)
    if n == 0:
        return {
            "overall_score": 0,
            "per_question_score": [],
            "dimension_scores": {},
            "strengths": [],
            "improvements": [],
            "summary_md": "No scores available.",
        }

    avg = sum(s.get("score", 5) for s in scores) / n
    per_q = []
    for i, s in enumerate(scores):
        q = questions[i] if i < len(questions) else {}
        per_q.append({
            "question_no": s.get("question_no", i + 1),
            "dimension": s.get("dimension", "unknown"),
            "score": s.get("score", 5),
            "feedback": s.get("feedback", ""),
            "question_text": q.get("question", ""),
            "user_answer": s.get("user_answer", ""),
        })

    dim_scores: dict = {}
    for s in scores:
        dim = s.get("dimension", "unknown")
        sc = s.get("score", 5)
        dim_scores.setdefault(dim, []).append(sc)
    dim_avgs = {d: round(sum(v) / len(v), 2) for d, v in dim_scores.items()}

    sorted_dims = sorted(dim_avgs.items(), key=lambda x: x[1])
    strengths = sorted_dims[-2:] if len(sorted_dims) >= 2 else sorted_dims
    improvements = sorted_dims[:2] if len(sorted_dims) >= 2 else sorted_dims

    focus_labels = [
        str(a.get("area"))
        for a in (focus_areas or [])
        if isinstance(a, dict) and a.get("area")
    ]
    improvement_items = []
    for d, s in improvements:
        suggestions = [f"加强{d}相关学习和实践"]
        if focus_labels:
            suggestions.append(f"结合计划重点「{focus_labels[0]}」做针对性复盘")
        improvement_items.append(
            {
                "dimension": d,
                "score": s,
                "detail": f"得分 {s}",
                "suggestions": suggestions,
            }
        )

    return {
        "overall_score": round(avg, 2),
        "per_question_score": per_q,
        "dimension_scores": dim_avgs,
        "strengths": [
            {"dimension": d, "score": s, "detail": f"得分 {s}"} for d, s in reversed(strengths)
        ],
        "improvements": improvement_items,
        "summary_md": f"面试完成, 综合评分 {avg:.2f}/10. 共完成 {n} 轮问答.",
    }


__all__ = ["report_node"]
