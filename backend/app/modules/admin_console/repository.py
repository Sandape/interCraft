"""REQ-039 B1 — admin_console repository (RLS-aware async DB helpers).

Thin wrappers over :class:`AsyncSession` for the 3 tables this module
owns / projects over:

- :class:`TaskTag` — ``task_tags`` table; CRUD helpers respect RLS via
  ``app.user_id`` GUC (set by callers before invoking these).
- :class:`AdminAuditLog` — append-only audit sink; no RLS.
- :class:`Trace` — read-only projection over ``traces`` for replay +
  diff + payload slicing.

Hard-delete semantics for tags (FR-016 / IC-3):

- ``delete_tag`` issues a real DELETE; re-adding after delete creates a
  new row with a new ``created_at`` (handled by the composite PK).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin_console.models import AdminAuditLog, TaskTag, Trace

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Task tags
# ---------------------------------------------------------------------------


async def list_tags(
    session: AsyncSession, task_id: UUID
) -> Sequence[TaskTag]:
    """Return all tags for ``task_id`` visible to the current RLS user."""
    result = await session.execute(
        select(TaskTag)
        .where(TaskTag.task_id == task_id)
        .order_by(TaskTag.created_at.asc(), TaskTag.tag.asc())
    )
    return list(result.scalars().all())


async def add_tag(
    session: AsyncSession,
    task_id: UUID,
    user_id: UUID,
    tag: str,
) -> TaskTag:
    """Insert a new tag row. Re-adding after delete is a fresh row."""
    row = TaskTag(task_id=task_id, user_id=user_id, tag=tag)
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateTagError(tag) from exc
    return row


async def delete_tag(
    session: AsyncSession,
    task_id: UUID,
    user_id: UUID,
    tag: str,
) -> bool:
    """Hard-delete a tag row. Returns True if a row was deleted."""
    result = await session.execute(
        delete(TaskTag).where(
            TaskTag.task_id == task_id,
            TaskTag.user_id == user_id,
            TaskTag.tag == tag,
        )
    )
    rowcount = getattr(result, "rowcount", 0) or 0
    return bool(rowcount > 0)


async def get_tag(
    session: AsyncSession,
    task_id: UUID,
    user_id: UUID,
    tag: str,
) -> TaskTag | None:
    """Read a single tag row. Returns None when missing (RLS scoped)."""
    result = await session.execute(
        select(TaskTag).where(
            TaskTag.task_id == task_id,
            TaskTag.user_id == user_id,
            TaskTag.tag == tag,
        )
    )
    return result.scalar_one_or_none()


class DuplicateTagError(Exception):
    """Raised when inserting a tag that already exists (HTTP 409)."""

    def __init__(self, tag: str) -> None:
        super().__init__(f"tag already exists: {tag!r}")
        self.tag = tag


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


async def write_audit(
    session: AsyncSession,
    user_id: UUID,
    action: str,
    target_kind: str,
    target_id: UUID | None,
    details: dict[str, Any] | None = None,
) -> AdminAuditLog:
    """Append a row to the audit log.

    Valid actions: ``replay_triggered`` | ``diff_computed`` |
    ``tag_added`` | ``tag_removed``. See DB CHECK constraint in
    migration 0022.
    """
    row = AdminAuditLog(
        id=uuid4(),
        user_id=user_id,
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        details=details or {},
    )
    session.add(row)
    await session.flush()
    return row


async def list_audit_entries(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 100,
) -> Sequence[AdminAuditLog]:
    """Read recent audit entries for ``user_id`` (newest first)."""
    result = await session.execute(
        select(AdminAuditLog)
        .where(AdminAuditLog.user_id == user_id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Trace (read-only projection)
# ---------------------------------------------------------------------------


async def get_trace(
    session: AsyncSession, trace_id: UUID
) -> Trace | None:
    """Read a single trace by id."""
    result = await session.execute(select(Trace).where(Trace.id == trace_id))
    return result.scalar_one_or_none()


async def get_traces_by_ids(
    session: AsyncSession, trace_ids: Sequence[UUID]
) -> list[Trace]:
    """Read multiple traces in one round-trip."""
    if not trace_ids:
        return []
    result = await session.execute(
        select(Trace).where(Trace.id.in_(trace_ids))
    )
    return list(result.scalars().all())


async def insert_trace(
    session: AsyncSession,
    *,
    task_id: UUID | None,
    user_id: UUID | None,
    task_type: str,
    prompt_version: str,
    model: str,
    input_payload: dict[str, Any],
    status: str = "pending",
    replay_of: UUID | None = None,
    node_payloads: dict[str, Any] | None = None,
    error_message: str | None = None,
    trace_id: UUID | None = None,
) -> Trace:
    """Insert a new trace row.

    Used by the replay service to create the new trace with
    ``replay_of=<orig>``.
    """
    row = Trace(
        id=trace_id or uuid4(),
        task_id=task_id,
        user_id=user_id,
        task_type=task_type,
        prompt_version=prompt_version,
        model=model,
        input_payload=input_payload,
        status=status,
        replay_of=replay_of,
        node_payloads=node_payloads or {},
        error_message=error_message,
    )
    session.add(row)
    await session.flush()
    return row


async def list_node_payload(
    session: AsyncSession,
    trace_id: UUID,
    node_id: str,
) -> tuple[str, int] | None:
    """Return ``(payload_str, total_size)`` for one node, or None if missing."""
    trace = await get_trace(session, trace_id)
    if trace is None:
        return None
    payloads = trace.node_payloads or {}
    node = payloads.get(node_id)
    if node is None:
        return None
    if isinstance(node, (bytes, bytearray)):
        raw = node.decode("utf-8", errors="replace")
    elif isinstance(node, str):
        raw = node
    else:
        # Structured payload (dict / list) — serialize for byte slicing.
        import json as _json

        raw = _json.dumps(node, ensure_ascii=False, default=str)
    return raw, len(raw.encode("utf-8"))


__all__ = [
    "AdminAuditLog",
    "DuplicateTagError",
    "TaskTag",
    "Trace",
    "add_tag",
    "delete_tag",
    "get_tag",
    "get_trace",
    "get_traces_by_ids",
    "insert_trace",
    "list_audit_entries",
    "list_node_payload",
    "list_tags",
    "write_audit",
]