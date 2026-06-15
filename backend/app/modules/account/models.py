"""Phase 6 — Account module ORM models: export_tasks."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.domain.mixins import TenantScopedMixin, TimestampedMixin, UUIDv7PrimaryKeyMixin


class ExportTask(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampedMixin,
    TenantScopedMixin,
):
    """M21 export_tasks table — tracks async data export jobs."""

    __tablename__ = "export_tasks"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_types: Mapped[dict | None] = mapped_column(JSONB, nullable=False, default=[])
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name="export_tasks_status_chk",
        ),
    )


__all__ = ["ExportTask"]
