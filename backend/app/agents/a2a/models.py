"""SQLAlchemy model for the ``a2a_messages`` table (REQ-031 US1, T006).

Mirrors the migration at ``backend/migrations/versions/0021_a2a_messages.py``.
The DB is the audit log; the wire format is
:class:`~app.agents.a2a.schemas.A2AMessage`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_uuid_v7


class A2AMessage(Base):
    """Standardized inter-agent message envelope (spec FR-016, FR-017)."""

    __tablename__ = "a2a_messages"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    trace_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    parent_agent: Mapped[str] = mapped_column(String(128), nullable=False)
    child_agent: Mapped[str] = mapped_column(String(128), nullable=False)
    task: Mapped[str] = mapped_column(String(512), nullable=False)
    context_jsonb: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    expected_output_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    result_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','success','failed','timeout')",
            name="ck_a2a_messages_status",
        ),
        CheckConstraint(
            "retry_count >= 0 AND retry_count <= 5",
            name="ck_a2a_messages_retry_range",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_a2a_messages_duration_nonneg",
        ),
    )


__all__ = ["A2AMessage"]