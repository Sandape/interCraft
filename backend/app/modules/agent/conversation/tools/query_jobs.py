"""query_jobs tool — immediate read via JobService (REQ-054 US3)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import INTERVIEW_STATUSES, JOB_STATUS_CN
from app.modules.agent.conversation import metrics as m
from app.modules.agent.conversation.job_matcher import match_jobs
from app.modules.agent.conversation.reply_formatter import truncate
from app.modules.agent.conversation.tools import ToolResult, fail, ok
from app.modules.agent.conversation.time_parser import SHANGHAI, format_shanghai, now_shanghai


async def execute(
    session: AsyncSession,
    user_id: UUID,
    entities: dict[str, Any] | None = None,
) -> ToolResult:
    from app.modules.jobs.service import JobService

    entities = entities or {}
    try:
        jobs = await JobService(session).list(user_id)
    except Exception:
        m.tool_calls_total.labels(tool="query_jobs", phase="execute", outcome="error").inc()
        return fail(
            "抱歉，暂时无法获取求职数据（系统繁忙）。请稍后重试或前往 InterCraft 查看。",
            "internal_error",
        )

    if not jobs:
        m.tool_calls_total.labels(tool="query_jobs", phase="execute", outcome="ok").inc()
        return ok("你还没有追踪任何岗位。回复「帮我记一个XX的YY岗」来新增第一个吧！")

    filter_status = entities.get("filter_status")
    company = entities.get("company")
    horizon_days = int(entities.get("horizon_days") or 7)

    # Company detail
    if company and not filter_status:
        match = match_jobs(jobs, company=company, position=entities.get("position"))
        if match.unique:
            return ok(_format_job_detail(match.matched), {"job_id": str(match.matched.id)})
        if match.candidates:
            from app.modules.agent.conversation.reply_formatter import format_job_candidates

            return ok(format_job_candidates(match.candidates))

    # Upcoming interviews
    if entities.get("upcoming") or (
        not filter_status and not company and entities.get("query_kind") == "upcoming"
    ):
        return ok(_format_upcoming(jobs, horizon_days))

    # Filter by interview stage
    if filter_status in INTERVIEW_STATUSES or filter_status == "interviewing":
        subset = [
            j
            for j in jobs
            if j.status in INTERVIEW_STATUSES
            or (filter_status != "interviewing" and j.status == filter_status)
        ]
        if filter_status != "interviewing":
            subset = [j for j in jobs if j.status == filter_status]
        return ok(_format_list(subset, title="当前在面试阶段的岗位" if filter_status == "interviewing" or filter_status in INTERVIEW_STATUSES else f"状态为「{JOB_STATUS_CN.get(filter_status, filter_status)}」的岗位"))

    if filter_status:
        subset = [j for j in jobs if j.status == filter_status]
        return ok(_format_list(subset, title=f"「{JOB_STATUS_CN.get(filter_status, filter_status)}」岗位"))

    # Default overview
    reply = _format_overview(jobs)
    m.tool_calls_total.labels(tool="query_jobs", phase="execute", outcome="ok").inc()
    return ok(truncate(reply, 500), {"count": len(jobs)})


def _format_overview(jobs: list[Any]) -> str:
    counts = Counter(j.status for j in jobs)
    parts = [f"{JOB_STATUS_CN.get(s, s)} {n}" for s, n in counts.items() if n]
    hist = " | ".join(parts)
    recent = sorted(
        jobs,
        key=lambda j: getattr(j, "last_status_changed_at", None)
        or getattr(j, "updated_at", None)
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[0]
    recent_status = JOB_STATUS_CN.get(recent.status, recent.status)
    when = getattr(recent, "last_status_changed_at", None)
    when_s = ""
    if when is not None:
        try:
            when_s = f"（{format_shanghai(when)}）"
        except Exception:
            when_s = ""
    return (
        f"📊 求职概览：共追踪 {len(jobs)} 个岗位。{hist}。"
        f"最近更新：{recent.company} → {recent_status}{when_s}。"
    )


def _format_list(jobs: list[Any], *, title: str) -> str:
    if not jobs:
        return f"{title}：暂无。"
    lines = [f"{title}："]
    for i, j in enumerate(jobs[:8], 1):
        st = JOB_STATUS_CN.get(j.status, j.status)
        extra = ""
        if getattr(j, "interview_time", None):
            try:
                extra = f"，面试时间 {format_shanghai(j.interview_time)}"
            except Exception:
                extra = ""
        lines.append(f"{i}. {j.company} · {j.position} — {st}{extra}")
    lines.append(f"共 {len(jobs)} 个。")
    return truncate("\n".join(lines), 500)


def _format_job_detail(job: Any) -> str:
    st = JOB_STATUS_CN.get(job.status, job.status)
    lines = [
        f"📌 {job.company} · {job.position}",
        f"状态：{st}",
    ]
    if getattr(job, "interview_time", None):
        lines.append(f"面试时间：{format_shanghai(job.interview_time)}")
    if getattr(job, "base_location", None):
        lines.append(f"地点：{job.base_location}")
    if getattr(job, "jd_url", None):
        lines.append(f"JD：{job.jd_url}")
    hist = getattr(job, "status_history", None) or []
    if hist:
        last = hist[-1] if isinstance(hist, list) else None
        if isinstance(last, dict) and last.get("note"):
            lines.append(f"最近备注：{last['note']}")
    return truncate("\n".join(lines), 500)


def _format_upcoming(jobs: list[Any], horizon_days: int) -> str:
    now = now_shanghai()
    end = now + timedelta(days=horizon_days)
    upcoming = []
    for j in jobs:
        it = getattr(j, "interview_time", None)
        if it is None:
            continue
        if it.tzinfo is None:
            it = it.replace(tzinfo=SHANGHAI)
        else:
            it = it.astimezone(SHANGHAI)
        if now <= it <= end:
            upcoming.append((it, j))
    if not upcoming:
        return f"未来 {horizon_days} 天内暂无面试安排。继续保持投递哦 💪"
    upcoming.sort(key=lambda x: x[0])
    lines = [f"未来 {horizon_days} 天面试安排："]
    for it, j in upcoming[:8]:
        st = JOB_STATUS_CN.get(j.status, j.status)
        lines.append(f"· {j.company} · {j.position} — {st}，{format_shanghai(it)}")
    return truncate("\n".join(lines), 500)


__all__ = ["execute"]
