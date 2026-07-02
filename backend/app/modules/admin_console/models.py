"""REQ-039 B1 — admin_console ORM models.

Tables declared here (see migration 0022 for DDL):

- :class:`TaskTag` — user-private annotation row; PK on
  (task_id, user_id, tag); RLS scoped to ``user_id`` (FR-016 / FR-031).
- :class:`AdminAuditLog` — append-only audit sink for Replay + Diff
  (FR-008 / FR-014 / FR-030, IC-7).

The :class:`Trace` projection is intentionally **read-only** here —
the source of truth is the ``traces`` table provisioned by migration
0022. We declare the ORM shell so service-layer queries can use
typed rows; runtime DDL is exercised through the migration, not via
``Base.metadata.create_all``.

All tables are registered with the shared :data:`app.core.db.Base`
metadata so future autogenerate migrations see them.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TaskTag(Base):
    """User-private annotation on a task (FR-016).

    Composite PK on (task_id, user_id, tag) means re-adding the same
    tag after a hard delete creates a new row with a new ``created_at``
    (IC-3). RLS scope: ``user_id`` (FR-031).
    """

    __tablename__ = "task_tags"

    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    tag: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_task_tags_task_user", "task_id", "user_id"),
        Index("idx_task_tags_user", "user_id"),
    )


class AdminAuditLog(Base):
    """Append-only audit row for admin actions (FR-008 / FR-014 / FR-030).

    No RLS — admin console actions are operator-scoped, not user-scoped.
    All write paths go through :func:`app.modules.admin_console.audit.write_audit`
    which prepends a server-generated UUID + timestamp.
    """

    __tablename__ = "admin_audit_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_admin_audit_user_action", "user_id", "action"),
        Index("idx_admin_audit_created_at", "created_at"),
    )


# ---------------------------------------------------------------------------
# Read-only Trace / TraceNode projections (migration 0022 owns DDL)
# ---------------------------------------------------------------------------


class Trace(Base):
    """Read-only projection over the ``traces`` table.

    Service-layer queries use this for replay + diff + payload slicing.
    The migration provisions a minimal schema; later REQs may extend it.
    """

    __tablename__ = "traces"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    task_type: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    model: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    input_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    replay_of: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("traces.id", ondelete="SET NULL"),
        nullable=True,
    )
    node_payloads: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["AdminAuditLog", "TaskTag", "Trace"]