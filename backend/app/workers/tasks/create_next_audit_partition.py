"""ARQ cron: create_next_audit_partition — monthly on 1st at 00:00 UTC.

Creates the next month's partition for the audit_logs table.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.core.db import get_session_factory
from app.core.logging import get_logger

log = get_logger("workers.create_next_audit_partition")


async def create_next_audit_partition(ctx: dict) -> dict:
    now = datetime.now(timezone.utc)
    year = now.year
    month = now.month + 1
    if month > 12:
        month = 1
        year += 1

    partition_name = f"audit_logs_{year}{month:02d}"
    date_from = f"{year}-{month:02d}-01"
    if month == 12:
        date_to = f"{year + 1}-01-01"
    else:
        date_to = f"{year}-{month + 1:02d}-01"

    log.info("create_next_audit_partition.start", partition=partition_name)

    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {partition_name} "
                f"PARTITION OF audit_logs "
                f"FOR VALUES FROM ('{date_from}') TO ('{date_to}');"
            )
        )
        await session.commit()

    log.info("create_next_audit_partition.done", partition=partition_name)
    return {"partition": partition_name, "ts": now.isoformat()}


__all__ = ["create_next_audit_partition"]
