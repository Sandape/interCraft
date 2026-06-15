"""ARQ cron: purge_expired_accounts — daily at 02:00 UTC.

Marks soft_deleted accounts past scheduled_purge_at as purged.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.core.db import get_session_factory
from app.core.logging import get_logger

log = get_logger("workers.purge_expired_accounts")


async def purge_expired_accounts(ctx: dict) -> dict:
    now = datetime.now(timezone.utc)
    log.info("purge_expired_accounts.start", ts=now.isoformat())

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                "UPDATE users SET status = 'purged', updated_at = :now "
                "WHERE status = 'soft_deleted' AND scheduled_purge_at <= :now"
            ),
            {"now": now},
        )
        await session.commit()
        purged_count = result.rowcount

    log.info("purge_expired_accounts.done", purged_count=purged_count)
    return {"purged_count": purged_count, "ts": now.isoformat()}


__all__ = ["purge_expired_accounts"]
