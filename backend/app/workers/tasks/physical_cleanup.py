"""ARQ cron: physical_cleanup — weekly on Sunday at 03:00 UTC.

Physically deletes purged users older than 7 days, in batches of 100.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.db import get_session_factory
from app.core.logging import get_logger

log = get_logger("workers.physical_cleanup")

BATCH_SIZE = 100


async def physical_cleanup(ctx: dict) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    log.info("physical_cleanup.start", ts=now.isoformat(), cutoff=cutoff.isoformat())

    factory = get_session_factory()
    deleted_count = 0

    async with factory() as session:
        while True:
            result = await session.execute(
                text(
                    "DELETE FROM users WHERE id IN ("
                    "  SELECT id FROM users WHERE status = 'purged' AND updated_at <= :cutoff"
                    f"  LIMIT {BATCH_SIZE}"
                    ")"
                ),
                {"cutoff": cutoff},
            )
            await session.commit()
            if result.rowcount == 0:
                break
            deleted_count += result.rowcount

    log.info("physical_cleanup.done", deleted_count=deleted_count)
    return {"deleted_count": deleted_count, "ts": now.isoformat()}


__all__ = ["physical_cleanup"]
