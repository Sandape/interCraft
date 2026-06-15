"""ARQ cron: reset_monthly_quota — monthly 1st at 00:00 UTC.

Resets monthly_token_used to 0 for all users using the subscription service.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.core.db import get_session_factory
from app.core.logging import get_logger

log = get_logger("workers.reset_monthly_quota")


async def reset_monthly_quota_cron(ctx: dict) -> dict:
    now = datetime.now(timezone.utc)
    log.info("reset_monthly_quota.start", ts=now.isoformat())

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                "UPDATE users SET monthly_token_used = 0, quota_reset_at = :now "
                "WHERE deleted_at IS NULL"
            ),
            {"now": now},
        )
        await session.commit()
        reset_count = result.rowcount

    log.info("reset_monthly_quota.done", reset_count=reset_count)
    return {"reset_count": reset_count, "ts": now.isoformat()}


__all__ = ["reset_monthly_quota_cron"]
