"""update_fields tool — location / jd_url / notes_md only (REQ-054)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.conversation import metrics as m
from app.modules.agent.conversation.job_matcher import match_jobs
from app.modules.agent.conversation.reply_formatter import (
    WEB_GUIDE_DELETE,
    WEB_GUIDE_OFFER,
    format_job_candidates,
    format_update_fields_card,
)
from app.modules.agent.conversation.tools import ToolResult, clarify, fail, ok, pending

ALLOWED_FIELDS = frozenset({"base_location", "jd_url", "notes_md"})
REJECT_FIELDS = frozenset(
    {
        "salary",
        "salary_range_text",
        "hr_contact",
        "offer",
        "offer_salary",
        "delete",
        "archive",
    }
)


async def prepare(
    session: AsyncSession,
    user_id: UUID,
    entities: dict[str, Any],
) -> ToolResult:
    from app.modules.jobs.service import JobService

    # Reject out-of-scope field updates
    for key in entities:
        kl = key.lower()
        if kl in REJECT_FIELDS or "offer" in kl or "salary" in kl or "hr" in kl:
            if "delete" in kl or "archive" in kl:
                return fail(WEB_GUIDE_DELETE, "rejected_web_guide")
            return fail(WEB_GUIDE_OFFER, "rejected_web_guide")

    patch = {k: entities[k] for k in ALLOWED_FIELDS if entities.get(k) is not None}
    if not patch:
        m.tool_calls_total.labels(tool="update_fields", phase="prepare", outcome="clarify").inc()
        return clarify(
            "可以帮你改工作地点、JD 链接或备注。请说明要改哪一项，例如「地点改成杭州」。"
            "删除岗位或填写 Offer 请用 Web 端。"
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
            return clarify("未找到匹配的岗位，请补充公司名。")
        text = format_job_candidates(match.candidates)
        m.tool_calls_total.labels(tool="update_fields", phase="prepare", outcome="clarify").inc()
        return clarify(text)

    job = match.matched
    params = {
        "job_id": str(job.id),
        "company": job.company,
        "position": job.position,
        **patch,
    }
    card = format_update_fields_card(params)
    m.tool_calls_total.labels(tool="update_fields", phase="prepare", outcome="ok").inc()
    return pending(card, "update_job_fields", params)


async def execute(
    session: AsyncSession,
    user_id: UUID,
    params: dict[str, Any],
) -> ToolResult:
    from app.modules.jobs.service import JobService

    job_id = UUID(str(params["job_id"]))
    patch = {k: params[k] for k in ALLOWED_FIELDS if k in params}
    if not patch:
        return fail("没有可更新的字段。", "validation_error")

    try:
        job = await JobService(session).patch(job_id, user_id, patch)
        parts = []
        if "base_location" in patch:
            parts.append(f"地点={patch['base_location']}")
        if "jd_url" in patch:
            parts.append("JD已更新")
        if "notes_md" in patch:
            parts.append("备注已更新")
        reply = f"✅ 已更新 {job.company} · {job.position}：{'，'.join(parts)}"
        m.tool_calls_total.labels(tool="update_fields", phase="execute", outcome="ok").inc()
        return ok(reply, {"job_id": str(job.id)})
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        msg = f"❌ 更新失败：{detail}" if detail else "❌ 更新失败，请稍后重试。"
        m.tool_calls_total.labels(tool="update_fields", phase="execute", outcome="error").inc()
        return fail(msg, "internal_error")


__all__ = ["prepare", "execute", "ALLOWED_FIELDS"]
