"""Async def monthly_quota_reset(ctx) — ARQ cron task.

DEC-P2-4: fires 00:00 UTC 1st of each month with 5-min tolerance window.
Sets monthly_token_used=0 and quota_reset_at=now() for all active users.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.core.db import get_session_factory
from app.core.logging import get_logger

log = get_logger("workers.monthly_quota_reset")


async def monthly_quota_reset(ctx: dict) -> dict:
    """Reset monthly_token_used to 0 for all active users.

    Called by ARQ cron at midnight UTC on the 1st of each month.
    """
    now = datetime.now(timezone.utc)
    log.info("monthly_quota_reset.start", ts=now.isoformat())

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                "UPDATE users SET monthly_token_used = 0, quota_reset_at = :now "
                "WHERE deleted_at IS NULL AND status = 'active'"
            ),
            {"now": now},
        )
        await session.commit()
        updated = result.rowcount

    log.info("monthly_quota_reset.done", rows_updated=updated)
    return {"status": "ok", "rows_updated": updated, "ts": now.isoformat()}


__all__ = ["monthly_quota_reset"]
