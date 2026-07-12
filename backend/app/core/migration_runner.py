"""Pre-deploy migration runner with advisory-lock exclusion (REQ-061 T016).

API/worker lifespan must never run Alembic. Only a pre-deploy job acquires
the advisory lock, records a migration-ledger row, and upgrades.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

# Fixed 64-bit key space for REQ-061 schema migrations.
_ADVISORY_LOCK_KEY = 0x061A1517  # 102,179,095


@dataclass(frozen=True, slots=True)
class MigrationLedgerEntry:
    id: UUID
    revision: str
    checksum: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    detail: str | None = None


def migration_advisory_lock_key() -> int:
    return _ADVISORY_LOCK_KEY


async def acquire_migration_advisory_lock(
    conn: AsyncConnection,
    *,
    key: int | None = None,
) -> bool:
    """Try to acquire a session-level PostgreSQL advisory lock.

    Returns True if this session owns the lock; False if another migrator holds it.
    """
    lock_key = key if key is not None else _ADVISORY_LOCK_KEY
    result = await conn.execute(
        text("SELECT pg_try_advisory_lock(:key)"),
        {"key": lock_key},
    )
    return bool(result.scalar())


async def release_migration_advisory_lock(
    conn: AsyncConnection,
    *,
    key: int | None = None,
) -> bool:
    lock_key = key if key is not None else _ADVISORY_LOCK_KEY
    result = await conn.execute(
        text("SELECT pg_advisory_unlock(:key)"),
        {"key": lock_key},
    )
    return bool(result.scalar())


@asynccontextmanager
async def migration_ledger_exclude_concurrent(
    engine: AsyncEngine,
    *,
    revision: str,
    script_bytes: bytes,
) -> AsyncIterator[MigrationLedgerEntry]:
    """Exclude concurrent migrators via advisory lock + ledger row.

    Yields a started ledger entry after the lock is held. Callers must complete
    the migration inside the context; on exit the ledger is marked succeeded or
    failed and the lock is released.
    """
    checksum = hashlib.sha256(script_bytes).hexdigest()
    entry = MigrationLedgerEntry(
        id=uuid4(),
        revision=revision,
        checksum=checksum,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    async with engine.connect() as conn:
        locked = await acquire_migration_advisory_lock(conn)
        if not locked:
            raise RuntimeError(
                "another migration holds the advisory lock; join/observe or fail safely"
            )
        try:
            await conn.execute(
                text(
                    """
                    INSERT INTO ai_migration_ledger
                        (id, revision, checksum, status, started_at)
                    VALUES
                        (:id, :revision, :checksum, :status, :started_at)
                    """
                ),
                {
                    "id": entry.id,
                    "revision": entry.revision,
                    "checksum": entry.checksum,
                    "status": entry.status,
                    "started_at": entry.started_at,
                },
            )
            await conn.commit()
            try:
                yield entry
            except Exception as exc:  # noqa: BLE001 — record failure then re-raise
                await conn.execute(
                    text(
                        """
                        UPDATE ai_migration_ledger
                        SET status = 'failed',
                            finished_at = :finished_at,
                            detail = :detail
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": entry.id,
                        "finished_at": datetime.now(timezone.utc),
                        "detail": str(exc)[:2000],
                    },
                )
                await conn.commit()
                raise
            else:
                await conn.execute(
                    text(
                        """
                        UPDATE ai_migration_ledger
                        SET status = 'succeeded',
                            finished_at = :finished_at
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": entry.id,
                        "finished_at": datetime.now(timezone.utc),
                    },
                )
                await conn.commit()
        finally:
            await release_migration_advisory_lock(conn)


async def record_backfill_checkpoint(
    conn: AsyncConnection,
    *,
    job_name: str,
    cursor: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Idempotent upsert of a resumable backfill checkpoint."""
    await conn.execute(
        text(
            """
            INSERT INTO ai_migration_backfill_checkpoints
                (job_name, cursor_token, payload, updated_at)
            VALUES
                (:job_name, :cursor, CAST(:payload AS jsonb), now())
            ON CONFLICT (job_name) DO UPDATE SET
                cursor_token = EXCLUDED.cursor_token,
                payload = EXCLUDED.payload,
                updated_at = now()
            """
        ),
        {
            "job_name": job_name,
            "cursor": cursor,
            "payload": json.dumps(payload or {}),
        },
    )


async def load_backfill_checkpoint(
    conn: AsyncConnection,
    *,
    job_name: str,
) -> dict[str, Any] | None:
    result = await conn.execute(
        text(
            """
            SELECT cursor_token, payload
            FROM ai_migration_backfill_checkpoints
            WHERE job_name = :job_name
            """
        ),
        {"job_name": job_name},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return {"cursor": row["cursor_token"], "payload": row["payload"]}


def list_required_061_revisions() -> Sequence[str]:
    return (
        "0058_061_ai_runtime_foundation",
        "0059_061_ai_metering_foundation",
    )


__all__ = [
    "MigrationLedgerEntry",
    "acquire_migration_advisory_lock",
    "release_migration_advisory_lock",
    "migration_ledger_exclude_concurrent",
    "migration_advisory_lock_key",
    "record_backfill_checkpoint",
    "load_backfill_checkpoint",
    "list_required_061_revisions",
]
