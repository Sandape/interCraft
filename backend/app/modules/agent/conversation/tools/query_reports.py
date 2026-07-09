"""query_reports tool — recent interview report summaries (REQ-054 US5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.conversation import metrics as m
from app.modules.agent.conversation.reply_formatter import truncate
from app.modules.agent.conversation.tools import ToolResult, fail, ok


async def execute(
    session: AsyncSession,
    user_id: UUID,
    entities: dict[str, Any] | None = None,
) -> ToolResult:
    from app.modules.interviews.service import InterviewSessionService

    entities = entities or {}
    limit = min(int(entities.get("limit") or 5), 5)
    company = (entities.get("company") or "").strip().lower()

    try:
        svc = InterviewSessionService(session)
        sessions = await svc.list(user_id, status="completed", limit=20)
    except Exception:
        m.tool_calls_total.labels(tool="query_reports", phase="execute", outcome="error").inc()
        return fail(
            "抱歉，暂时无法获取面试报告。请稍后重试或前往 InterCraft 查看。",
            "internal_error",
        )

    completed = [s for s in sessions if getattr(s, "status", None) == "completed"]
    if company:
        completed = [
            s
            for s in completed
            if company in (getattr(s, "company", "") or "").lower()
        ]

    if not completed:
        m.tool_calls_total.labels(tool="query_reports", phase="execute", outcome="ok").inc()
        return ok(
            "你还没有完成过模拟面试。回复「开始模拟面试」来试试你的第一场 AI 面试！"
        )

    # Latest detailed summary
    latest = completed[0]
    report = None
    try:
        report = await InterviewSessionService(session).get_report(latest.id, user_id)
    except Exception:
        report = None

    if len(completed) == 1 or entities.get("latest_only"):
        reply = _format_one(latest, report)
    else:
        lines = ["📋 最近面试报告："]
        for i, s in enumerate(completed[:limit], 1):
            score = getattr(s, "overall_score", None)
            score_s = f"{float(score):.1f}" if score is not None else "-"
            date_s = ""
            ended = getattr(s, "ended_at", None) or getattr(s, "updated_at", None)
            if ended is not None:
                try:
                    date_s = ended.strftime("%m/%d")
                except Exception:
                    date_s = ""
            lines.append(
                f"{i}. {date_s} {s.company} · {s.position} — 总分 {score_s}"
            )
        if len(completed) > limit:
            lines.append("更多历史请前往 InterCraft Web 端查看。")
        lines.append("📎 完整报告：InterCraft → 面试记录。")
        # Also prepend latest detail briefly
        reply = _format_one(latest, report) + "\n\n" + "\n".join(lines)

    m.tool_calls_total.labels(tool="query_reports", phase="execute", outcome="ok").inc()
    return ok(truncate(reply, 800), {"count": len(completed)})


def _format_one(session: Any, report: dict | None) -> str:
    score = getattr(session, "overall_score", None)
    if report and report.get("overall_score") is not None:
        score = report["overall_score"]
    score_s = f"{float(score):.1f}" if score is not None else "-"
    date_s = ""
    ended = getattr(session, "ended_at", None)
    if ended is not None:
        try:
            date_s = ended.strftime("%-m/%-d") if False else ended.strftime("%m/%d")
        except Exception:
            date_s = ""

    lines = [
        f"📝 最近面试：{session.company} · {session.position}"
        + (f"（{date_s}）" if date_s else ""),
        f"总分 {score_s}/10。",
    ]

    dim = (report or {}).get("dimension_scores") or {}
    if dim:
        ranked = sorted(dim.items(), key=lambda x: float(x[1] or 0), reverse=True)
        if ranked:
            top = ranked[:2]
            weak = list(reversed(ranked))[:2]
            lines.append(
                "最强："
                + "、".join(f"{k}({float(v):.1f})" for k, v in top)
                + "。"
            )
            lines.append(
                "最弱："
                + "、".join(f"{k}({float(v):.1f})" for k, v in weak)
                + "。"
            )

    improvements = (report or {}).get("improvements") or []
    if improvements:
        tip = improvements[0] if isinstance(improvements[0], str) else str(improvements[0])
        lines.append(f"💡 建议：{tip}")

    lines.append("📎 完整报告：InterCraft → 面试记录。")
    return "\n".join(lines)


__all__ = ["execute"]
