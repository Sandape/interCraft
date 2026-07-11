"""update_status tool — prepare + execute via JobService (REQ-054 US2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import INTERVIEW_STATUSES, JOB_STATUS_CN, JOB_TRANSITIONS
from app.modules.agent.conversation import metrics as m
from app.modules.agent.conversation.job_matcher import match_jobs
from app.modules.agent.conversation.reply_formatter import (
    format_job_candidates,
    format_update_status_card,
)
from app.modules.agent.conversation.time_parser import format_shanghai, parse_relative_time
from app.modules.agent.conversation.tools import ToolResult, clarify, fail, ok, pending

_STATUS_ALIASES = {
    "applied": "applied",
    "已投递": "applied",
    "test": "test",
    "笔试": "test",
    "笔试中": "test",
    "进笔试": "test",
    "interview_1": "interview_1",
    "一面": "interview_1",
    "一面中": "interview_1",
    "进一面": "interview_1",
    "interview_2": "interview_2",
    "二面": "interview_2",
    "二面中": "interview_2",
    "进二面": "interview_2",
    "interview_3": "interview_3",
    "三面": "interview_3",
    "三面中": "interview_3",
    "进三面": "interview_3",
    "failed": "failed",
    "挂了": "failed",
    "没过": "failed",
    "已失败": "failed",
    "passed": "passed",
    "过了": "passed",
    "已通过": "passed",
    "拿了": "passed",
}


def normalize_status(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    if s in JOB_TRANSITIONS or s in ("applied", "test", "interview_1", "interview_2", "interview_3", "failed", "passed"):
        return s
    return _STATUS_ALIASES.get(s) or _STATUS_ALIASES.get(s.lower())


async def prepare(
    session: AsyncSession,
    user_id: UUID,
    entities: dict[str, Any],
) -> ToolResult:
    from app.modules.jobs.service import JobService

    target = normalize_status(entities.get("target_status"))
    if not target:
        m.tool_calls_total.labels(tool="update_status", phase="prepare", outcome="clarify").inc()
        return clarify(
            "好的，请问具体是什么消息？可选：进笔试了 / 进一面了 / 进二面了 / "
            "进三面了 / 挂了 / 过了。回复对应描述即可。"
        )

    jobs = await JobService(session).list(user_id)
    match = match_jobs(
        jobs,
        company=entities.get("company"),
        position=entities.get("position"),
        job_id=entities.get("job_id"),
    )
    if match.need_clarify:
        if not match.candidates:
            return clarify("未找到匹配的岗位。你可以先「查询求职进展」或补充公司名。")
        prompt = (
            "你目前追踪的岗位有："
            if not entities.get("company")
            else "找到多个可能的岗位，请问是哪一个？"
        )
        # Build numbered list matching format_job_candidates style
        text = format_job_candidates(match.candidates, prompt=prompt + " 回复序号或公司名即可。")
        if match.too_many:
            text += "\n候选较多，请补充公司名或职位缩小范围。"
        m.tool_calls_total.labels(tool="update_status", phase="prepare", outcome="clarify").inc()
        return clarify(text, {"candidates": [str(getattr(j, "id", "")) for j in match.candidates]})

    job = match.matched
    old_status = job.status
    allowed = JOB_TRANSITIONS.get(old_status, set())
    if target not in allowed:
        old_cn = JOB_STATUS_CN.get(old_status, old_status)
        to_cn = JOB_STATUS_CN.get(target, target)
        m.tool_calls_total.labels(
            tool="update_status", phase="prepare", outcome="invalid_transition"
        ).inc()
        return fail(
            f"❌ 无法从「{old_cn}」到「{to_cn}」。如需修改，请在 InterCraft Web 端操作。",
            "invalid_status_transition",
            {"from": old_status, "to": target},
        )

    interview_time: datetime | None = None
    interview_time_display: str | None = None
    if target in INTERVIEW_STATUSES:
        raw_time = entities.get("interview_time_raw") or entities.get("interview_time")
        if isinstance(raw_time, datetime):
            interview_time = raw_time
        elif raw_time:
            interview_time = parse_relative_time(str(raw_time))
        if interview_time is None:
            m.tool_calls_total.labels(tool="update_status", phase="prepare", outcome="clarify").inc()
            return clarify(
                f"推进到「{JOB_STATUS_CN.get(target, target)}」需要面试时间。"
                "请告诉我具体时间，例如「下周一 14:00」或「7月10日下午2点」。"
            )
        interview_time_display = format_shanghai(interview_time)

    params: dict[str, Any] = {
        "job_id": str(job.id),
        "company": job.company,
        "position": job.position,
        "target_status": target,
        "from_status": old_status,
        "failure_note": entities.get("failure_note") or "",
    }
    if interview_time is not None:
        params["interview_time"] = interview_time.isoformat()
        params["interview_time_display"] = interview_time_display

    card = format_update_status_card(params)
    if target == "failed" and not params["failure_note"]:
        card += "\n建议填写失败原因（如：技术面没过），方便后续复盘。可直接确认或先补充备注。"
    if target == "passed":
        card += "\n🎉 确认后将标记为已通过。记得稍后在 InterCraft 填写 Offer 信息。"

    m.tool_calls_total.labels(tool="update_status", phase="prepare", outcome="ok").inc()
    return pending(card, "update_job_status", params)


async def execute(
    session: AsyncSession,
    user_id: UUID,
    params: dict[str, Any],
) -> ToolResult:
    from fastapi import HTTPException

    from app.modules.jobs.service import JobService

    job_id = UUID(str(params["job_id"]))
    to = params["target_status"]
    note = params.get("failure_note") or ""
    interview_time = None
    if params.get("interview_time"):
        interview_time = datetime.fromisoformat(params["interview_time"])

    try:
        job = await JobService(session).update_status(
            job_id,
            user_id,
            to,
            note=note,
            interview_time=interview_time,
        )
        to_cn = JOB_STATUS_CN.get(to, to)
        reply = f"✅ 已更新：{job.company} · {job.position} → {to_cn}"
        if params.get("interview_time_display"):
            reply += f"，面试时间 {params['interview_time_display']}"
        if to == "passed":
            reply += "。记得在 InterCraft 中填写 Offer 信息（薪资、HR 联系方式等）。"
        m.tool_calls_total.labels(tool="update_status", phase="execute", outcome="ok").inc()
        return ok(reply, {"job_id": str(job.id), "status": job.status})
    except HTTPException as exc:
        code = "invalid_status_transition"
        detail = exc.detail
        if isinstance(detail, dict):
            err = detail.get("error") or {}
            code = err.get("code") or code
            msg = err.get("message") or str(detail)
        else:
            msg = str(detail)
        m.tool_calls_total.labels(tool="update_status", phase="execute", outcome="error").inc()
        return fail(f"❌ {msg}", code)
    except Exception:
        m.tool_calls_total.labels(tool="update_status", phase="execute", outcome="error").inc()
        return fail("❌ 更新失败，请稍后重试。", "internal_error")


__all__ = ["prepare", "execute", "normalize_status"]
