"""ARQ cron: cleanup_expired_exports — hourly.

Deletes expired export ZIP files and their database records.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.core.db import get_session_factory
from app.core.logging import get_logger

log = get_logger("workers.cleanup_expired_exports")


async def cleanup_expired_exports(ctx: dict) -> dict:
    now = datetime.now(timezone.utc)
    log.info("cleanup_expired_exports.start", ts=now.isoformat())

    factory = get_session_factory()
    deleted_count = 0

    async with factory() as session:
        result = await session.execute(
            select(text("id"), text("file_path")).select_from(text("export_tasks"))
            .where(text("expires_at <= :now AND status = 'completed'")),
            {"now": now},
        )
        rows = result.fetchall()

        for row in rows:
            task_id = row[0]
            file_path = row[1]
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            await session.execute(
                text("DELETE FROM export_tasks WHERE id = :id"),
                {"id": task_id},
            )
            deleted_count += 1

        await session.commit()

    log.info("cleanup_expired_exports.done", deleted_count=deleted_count)
    return {"deleted_count": deleted_count, "ts": now.isoformat()}


__all__ = ["cleanup_expired_exports"]
