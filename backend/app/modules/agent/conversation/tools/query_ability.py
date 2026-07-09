"""query_ability tool — ability profile dashboard summary (REQ-054 US5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.conversation import metrics as m
from app.modules.agent.conversation.reply_formatter import truncate
from app.modules.agent.conversation.tools import ToolResult, fail, ok

_TREND_ARROW = {"up": "↑", "down": "↓", "stable": "→"}


async def execute(
    session: AsyncSession,
    user_id: UUID,
    entities: dict[str, Any] | None = None,
) -> ToolResult:
    from app.modules.ability_profile.repository import AbilityProfileRepository
    from app.modules.ability_profile.service import AbilityProfileService

    _ = entities
    try:
        svc = AbilityProfileService(AbilityProfileRepository(session), session=session)
        dashboard = await svc.get_dashboard(user_id)
    except Exception:
        m.tool_calls_total.labels(tool="query_ability", phase="execute", outcome="error").inc()
        return fail(
            "抱歉，暂时无法获取能力画像。请稍后重试或前往 InterCraft 查看。",
            "internal_error",
        )

    dims = dashboard.get("dimensions") or []
    if not dims:
        m.tool_calls_total.labels(tool="query_ability", phase="execute", outcome="ok").inc()
        return ok(
            "你还没有能力画像数据。回复「开始模拟面试」完成第一场面试后即可生成！"
        )

    parts: list[str] = []
    ups: list[str] = []
    downs: list[str] = []
    for d in dims:
        label = d.get("label_zh") or d.get("key") or ""
        score = float(d.get("actual_score") or 0)
        trend = d.get("trend") or "stable"
        arrow = _TREND_ARROW.get(trend, "→")
        parts.append(f"{label} {score:.1f}{arrow if trend != 'stable' else ''}")
        if trend == "up":
            ups.append(label)
        elif trend == "down":
            downs.append(label)

    trend_note = ""
    if ups or downs:
        bits = []
        if ups:
            bits.append(f"{'、'.join(ups)}持续提升")
        if downs:
            bits.append(f"{'、'.join(downs)}略有下降")
        trend_note = "趋势：" + "，".join(bits) + "。"

    reply = (
        "🎯 能力画像："
        + " | ".join(parts)
        + "。"
        + (trend_note + " " if trend_note else "")
        + "📎 完整雷达图：InterCraft → 能力画像。"
    )
    m.tool_calls_total.labels(tool="query_ability", phase="execute", outcome="ok").inc()
    return ok(truncate(reply, 500), {"dimensions": len(dims)})


__all__ = ["execute"]
