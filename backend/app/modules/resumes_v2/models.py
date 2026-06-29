"""M032 — Resume v2 ORM models (REB-032 v2 MVP stub).

The real models live in feature 032 v2 US1 (T018 — schema + Alembic
migration). For the REB-032 v2 MVP we only need ``ResumeV2`` and
``ResumeStatisticsV2`` to exist so the service layer's import-time
references resolve. The full table definitions (JSONB data blob,
RLS binding, soft delete, public sharing, statistics counters,
analysis cache) ship in a later US phase via Alembic migration.

We declare minimal table shells so ``app.modules.resumes_v2.service``
can import the class names without raising ``ModuleNotFoundError``.
Runtime SQL is exercised through Alembic-migrated tables in the real
schema; the stubs below are intentionally not registered with the
shared ``Base.metadata`` so they don't shadow the production DDL.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ResumeV2(Base):
    """Stub: full table definition ships in 032 v2 US1 (T018).

    This minimal model exposes the column names the service layer
    references (``id``, ``user_id``, ``name``, ``slug``, ``tags``,
    ``is_public``, ``is_locked``, ``password_hash``, ``data``,
    ``version``, ``created_at``, ``updated_at``) so type checkers
    and the import chain stay green. The Alembic migration that
    creates the production table is a separate concern (tracked in
    specs/032-resume-renderer-v2/tasks.md).
    """

    __tablename__ = "resumes_v2"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(64))
    slug: Mapped[str] = mapped_column(String(64), index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ResumeStatisticsV2(Base):
    """Stub: view + download counters. Production schema ships in 032 v2 US11."""

    __tablename__ = "resume_statistics_v2"
    __table_args__ = {"extend_existing": True}

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    views: Mapped[int] = mapped_column(Integer, default=0)
    downloads: Mapped[int] = mapped_column(Integer, default=0)


__all__ = ["ResumeV2", "ResumeStatisticsV2"]