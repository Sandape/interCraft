"""create_job tool — prepare + execute via JobService (REQ-054 US1)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.conversation.reply_formatter import format_create_job_card
from app.modules.agent.conversation.tools import ToolResult, clarify, fail, ok, pending
from app.modules.agent.conversation import metrics as m


async def prepare(
    session: AsyncSession,
    user_id: UUID,
    entities: dict[str, Any],
) -> ToolResult:
    """Validate entities and build confirmation card / clarify prompt."""
    company = (entities.get("company") or "").strip()
    position = (entities.get("position") or "").strip()

    missing: list[str] = []
    if not company:
        missing.append("公司名")
    if not position:
        missing.append("职位名称")
    if missing:
        if len(missing) == 2:
            msg = "好的，请告诉我公司名和职位名称～"
        elif "公司名" in missing:
            msg = "好的，请问是哪家公司？"
        else:
            msg = "好的，请问这个岗位的具体职位名称是什么？"
        m.tool_calls_total.labels(tool="create_job", phase="prepare", outcome="clarify").inc()
        return clarify(msg, {"missing": missing})

    if len(company) > 100:
        return fail("公司名称过长（最多 100 字符）。请缩短后重试。", "validation_error")
    if len(position) > 100:
        return fail("职位名称过长（最多 100 字符）。请缩短后重试。", "validation_error")

    params = {
        "company": company,
        "position": position,
    }
    for key in (
        "base_location",
        "jd_url",
        "notes_md",
        "employment_type",
        "salary_range_text",
    ):
        if entities.get(key):
            params[key] = entities[key]

    card = format_create_job_card(params)
    m.tool_calls_total.labels(tool="create_job", phase="prepare", outcome="ok").inc()
    return pending(card, "create_job", params)


async def execute(
    session: AsyncSession,
    user_id: UUID,
    params: dict[str, Any],
) -> ToolResult:
    """Create job after user confirmation."""
    from app.modules.jobs.service import JobService

    try:
        job = await JobService(session).create(user_id, params)
        reply = (
            f"✅ 已创建：{job.company} · {job.position}（已投递）。"
            "你可以在 InterCraft 中查看详情或继续通过微信管理。"
        )
        m.tool_calls_total.labels(tool="create_job", phase="execute", outcome="ok").inc()
        return ok(reply, {"job_id": str(job.id)})
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        msg = "创建失败，请稍后重试。"
        if isinstance(detail, str):
            msg = f"❌ 创建失败：{detail}"
        elif "100" in str(exc):
            msg = "❌ 创建失败：公司名称过长（最多 100 字符）。请缩短后重试。"
        m.tool_calls_total.labels(tool="create_job", phase="execute", outcome="error").inc()
        return fail(msg, "validation_error")


__all__ = ["prepare", "execute"]
