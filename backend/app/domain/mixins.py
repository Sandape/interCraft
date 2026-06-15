"""Reusable column mixins per data-model §0."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_uuid_v7


class UUIDv7PrimaryKeyMixin:
    """Primary key = uuid v7 (time-ordered, index-friendly)."""

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid_v7,
        server_default=text("gen_random_uuid()"),
    )


class TimestampedMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeletableMixin:
    """Soft-delete: rows where `deleted_at IS NULL` are alive."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class TenantScopedMixin:
    """RLS column. All business tables MUST include this (except `users`)."""

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


__all__ = [
    "SoftDeletableMixin",
    "TenantScopedMixin",
    "TimestampedMixin",
    "UUIDv7PrimaryKeyMixin",
]
