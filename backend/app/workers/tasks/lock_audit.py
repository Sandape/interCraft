"""Fire-and-forget async lock audit log writer.

Write to `lock_audit_logs` via a background asyncio task. Failures are
logged at error level and metered via Prometheus — they never block the
lock acquire/release hot path.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import text

from app.core.db import get_engine
from app.core.ids import new_uuid_v7
from app.core.metrics import lock_audit_write_failures_total

logger = structlog.get_logger("lock_audit")


async def write_lock_audit(
    ctx: dict[str, Any], record: dict[str, Any]
) -> None:
    """Enqueue a background task to write the audit record.

    `ctx` is reserved for future worker integration (e.g. ARQ context).
    `record` must include: resource_type, resource_id, user_id, device_id,
    session_id, action, metadata_json.
    """
    asyncio.create_task(_write(record))


async def _write(record: dict[str, Any]) -> None:
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """INSERT INTO lock_audit_logs
                       (id, resource_type, resource_id, user_id, device_id,
                        session_id, action, metadata_json, occurred_at)
                       VALUES
                       (:id, :rt, :rid, :uid, :did,
                        :sid, :action, :meta, :ts)
                       ON CONFLICT DO NOTHING"""
                ),
                {
                    "id": record.get("id") or new_uuid_v7(),
                    "rt": record["resource_type"],
                    "rid": record["resource_id"],
                    "uid": record["user_id"],
                    "did": record.get("device_id", "unknown"),
                    "sid": record.get(
                        "session_id",
                        "00000000-0000-0000-0000-000000000000",
                    ),
                    "action": record["action"],
                    "meta": record.get("metadata_json", {}),
                    "ts": record.get("occurred_at", datetime.now(timezone.utc)),
                },
            )
    except Exception:
        logger.error(
            "lock_audit_log.write_failed",
            user_id=record.get("user_id"),
            resource_type=record.get("resource_type"),
            resource_id=record.get("resource_id"),
            action=record.get("action"),
        )
        lock_audit_write_failures_total.inc()
