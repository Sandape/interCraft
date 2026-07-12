"""REQ-061 Asia/Shanghai daily experience point grant worker (T050).

Idempotent per ``(user, Shanghai business date)``. New authenticated users
receive the full daily entitlement immediately (not prorated).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_factory
from app.core.ids import new_uuid_v7
from app.core.logging import get_logger
from app.modules.ai_metering.models import DailyGrantConfigVersion
from app.modules.ai_metering.points.configuration import (
    DEFAULT_TIMEZONE,
    plan_daily_grant,
    resolve_effective_grant_config,
    shanghai_business_date,
)
from app.modules.ai_metering.points.service import PointMeteringService
from app.modules.auth.models import User

log = get_logger("workers.ai_daily_point_grant")


async def ensure_grant_config_row(
    session: AsyncSession,
    *,
    at: datetime | None = None,
) -> DailyGrantConfigVersion:
    """Persist (or reuse) the effective in-memory/default grant config version."""
    moment = at or datetime.now(timezone.utc)
    cfg = resolve_effective_grant_config(at=moment)
    result = await session.execute(
        select(DailyGrantConfigVersion).where(
            DailyGrantConfigVersion.version == cfg.version
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row

    row = DailyGrantConfigVersion(
        id=new_uuid_v7(),
        version=cfg.version,
        points_amount=cfg.points_amount,
        timezone=cfg.timezone or DEFAULT_TIMEZONE,
        effective_at=cfg.effective_at,
        status="active",
        reason=cfg.reason or "daily grant bootstrap",
    )
    session.add(row)
    await session.flush()
    return row


async def grant_user_for_business_date(
    session: AsyncSession,
    *,
    user_id: UUID,
    business_date=None,
    is_new_user: bool = False,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Grant (or no-op via idempotency) one daily experience bucket for a user."""
    moment = at or datetime.now(timezone.utc)
    biz = business_date or shanghai_business_date(moment)
    plan = plan_daily_grant(
        user_id=user_id,
        business_date=biz,
        at=moment,
        is_new_user=is_new_user,
    )
    config_row = await ensure_grant_config_row(session, at=moment)
    svc = PointMeteringService(session)
    result = await svc.grant(
        user_id=user_id,
        points=plan.points,
        idempotency_key=plan.idempotency_key,
        expires_at=plan.expires_at,
        business_date=plan.business_date,
        grant_config_version_id=config_row.id,
        reason="new_user_immediate_grant" if is_new_user else "shanghai_midnight_grant",
    )
    return {
        "user_id": str(user_id),
        "business_date": plan.business_date.isoformat(),
        "points": plan.points,
        "reused": result.reused,
        "immediate": plan.immediate,
        "event_id": str(result.event.id),
        "grant_config_version": config_row.version,
    }


async def grant_new_user_immediate(
    session: AsyncSession,
    *,
    user_id: UUID,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Immediate full-day grant when a user first becomes authenticated."""
    return await grant_user_for_business_date(
        session,
        user_id=user_id,
        is_new_user=True,
        at=at,
    )


async def run_daily_point_grant(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cron entry: grant today's Shanghai entitlement to all active users."""
    _ = ctx
    now = datetime.now(timezone.utc)
    biz = shanghai_business_date(now)
    log.info("ai_daily_point_grant.start", business_date=biz.isoformat(), ts=now.isoformat())

    factory = get_session_factory()
    granted = 0
    reused = 0
    errors = 0

    async with factory() as session:
        users = (
            await session.execute(
                select(User.id).where(
                    User.deleted_at.is_(None),
                    User.status == "active",
                )
            )
        ).scalars().all()

        for user_id in users:
            try:
                outcome = await grant_user_for_business_date(
                    session,
                    user_id=user_id,
                    business_date=biz,
                    at=now,
                )
                if outcome["reused"]:
                    reused += 1
                else:
                    granted += 1
            except Exception as exc:  # noqa: BLE001 — continue other users
                errors += 1
                log.warning(
                    "ai_daily_point_grant.user_failed",
                    user_id=str(user_id),
                    error=str(exc),
                )
        await session.commit()

    summary = {
        "business_date": biz.isoformat(),
        "granted": granted,
        "reused": reused,
        "errors": errors,
        "ts": now.isoformat(),
    }
    log.info("ai_daily_point_grant.done", **summary)
    return summary


# ARQ-compatible alias
async def ai_daily_point_grant(ctx: dict[str, Any]) -> dict[str, Any]:
    return await run_daily_point_grant(ctx)


__all__ = [
    "ai_daily_point_grant",
    "ensure_grant_config_row",
    "grant_new_user_immediate",
    "grant_user_for_business_date",
    "run_daily_point_grant",
]
