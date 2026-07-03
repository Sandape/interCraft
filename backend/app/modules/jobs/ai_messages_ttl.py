"""REQ-043 US-1 FR-003 — ai_messages TTL cleanup job.

Spec contract (FR-003 + SC-003):
- Delete rows older than ``days`` (default 30) from the ``ai_messages``
  audit table.
- Run daily via a scheduler hook (registration in
  ``app.core.scheduler``; the hook itself is best-effort — see the
  scheduler module).
- Graceful no-op when the ``ai_messages`` table does not yet exist
  (the table is owned by an upstream feature / migration that may
  not be applied in all environments). Per spec edge case
  (line 69 — "已有的 ai_messages 数据保留不动, 新数据进 TTL pipeline")
  we treat this as a forward-only operation: once the table is
  present, all new data is subject to the TTL policy.

Design (per L041-001):
- The cleanup uses a raw ``DELETE FROM ai_messages WHERE created_at < :cutoff``
  rather than ORM mapping — we do not own the SQLAlchemy model for
  ``ai_messages`` (it lives in the audit module and is intentionally
  not coupled to this jobs package). When the table is missing the
  function catches the ``ProgrammingError`` and returns 0.
- Pure async function: no FastAPI/ARQ coupling. The scheduler
  registration wraps it in a cron schedule.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import text

logger = structlog.get_logger("jobs.ai_messages_ttl")


async def cleanup_old_ai_messages(days: int = 30) -> int:
    """Delete ``ai_messages`` rows older than ``days``.

    Returns the number of rows deleted. If the table is missing,
    returns ``0`` without raising (so the scheduler can run safely
    even before the audit migration lands).

    Args:
        days: Retention window in days. Default 30 per spec FR-003.
    """
    from app.core.db import _session_cm

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with _session_cm() as session:
            stmt = text(
                "DELETE FROM ai_messages WHERE created_at < :cutoff"
            )
            result = await session.execute(stmt, {"cutoff": cutoff})
            await session.commit()
            deleted = int(result.rowcount or 0)
            logger.info(
                "ai_messages.ttl_cleanup",
                days=days,
                cutoff=cutoff.isoformat(),
                deleted=deleted,
            )
            return deleted
    except Exception as exc:
        # Common case: relation 'ai_messages' does not exist (UndefinedTableError
        # subclasses ProgrammingError). The migration may not be applied yet.
        # Per spec line 69: we keep the existing data untouched and silently
        # skip the cleanup until the table lands.
        msg = str(exc).lower()
        if "does not exist" in msg or "undefined_table" in msg or "relation" in msg:
            logger.info(
                "ai_messages.ttl_cleanup_table_missing_skip",
                days=days,
                reason=str(exc),
            )
            return 0
        # Any other error is unexpected — re-raise so the scheduler can
        # alert. We deliberately do NOT swallow non-table errors.
        logger.warning(
            "ai_messages.ttl_cleanup_failed",
            days=days,
            exc_info=True,
        )
        raise


__all__ = ["cleanup_old_ai_messages"]