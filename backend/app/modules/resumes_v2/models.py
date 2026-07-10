"""M032 — Resume v2 ORM models (REQ-032 v2, US11 + US14).

Tables created by Alembic migration 0022:
- ``resumes_v2``               — authoring + content (RLS-bound on app.user_id)
- ``resume_statistics_v2``     — public-access counters (FK CASCADE)
- ``resume_analysis_v2``       — LLM analysis snapshot (FK CASCADE, UPSERT)

Column notes
------------
- ``resumes_v2.tags`` is ``text[]`` (Postgres array), stored as Python
  ``list[str]``. The ORM mapping uses ``ARRAY(Text)`` so reads /
  writes round-trip the array form without JSON serialization
  surprises.
- ``resumes_v2.version`` is the optimistic-concurrency counter
  authored in service.py via ``repo.update_with_version``. DB default
  is 0; new rows inserted by ``repo.create`` set ``version=0`` to
  match the migration.
- ``resumes_v2.password_hash`` only valid when ``is_public=True`` —
  enforced by the CHECK constraint
  ``ck_resumes_v2_password_only_when_public``.
- ``resumes_v2.data`` is a JSONB blob mirroring the
  ``ResumeDataV2`` shape (see
  ``specs/032-resume-renderer-v2/contracts/02-resume-data-schema.md``).

The ``__table_args__ = {"extend_existing": True}`` is needed because
the v2 test fixtures (T016) instantiate models with the same
tablename registered against ``Base.metadata``; without it, two
declarations of the same table name would raise
``InvalidRequestError`` on import. The real DDL lives in the migration
not the ORM, so the model columns below are kept in sync with that
DDL by hand (verified against ``information_schema`` in Batch 5).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ResumeV2(Base):
    """The v2 resume authoring + content row.

    RLS is bound via ``app.user_id`` GUC by the API dependency
    ``db_session_user_dep``; the repository does not need to set it.

    REQ-055 adds ``resume_kind`` (root|derived|standard) and derive
    binding columns. See ``specs/055-resume-root-derive/data-model.md``.
    """

    __tablename__ = "resumes_v2"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # DB default is 0; new rows from repo.create() pin version=0 so
    # the audit log + E2E assertions both see the same baseline.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # REQ-055 — root / derived / standard
    resume_kind: Mapped[str] = mapped_column(Text, nullable=False, default="standard")
    root_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    root_version_at_derive: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_page_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    actual_page_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    derive_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class ResumeStatisticsV2(Base):
    """Public-access counters (US11, T141).

    Rows are inserted lazily by the service's
    ``ensure_statistics_row`` so private resumes never materialize a
    row. Children of ``resumes_v2.id`` with ON DELETE CASCADE, so a
    parent soft-delete cleans the counters too.

    No RLS: the parent row's RLS already gates access — see migration
    0022's note on the design choice.
    """

    __tablename__ = "resume_statistics_v2"
    __table_args__ = {"extend_existing": True}

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ResumeAnalysisV2(Base):
    """AI-analysis snapshot (US14, T151).

    One row per resume, UPSERT'd by ``repo.upsert_analysis`` so the
    latest attempt always wins. ``status`` is either ``"success"``
    or ``"failed"`` per the CHECK constraint
    ``ck_resume_analysis_v2_status``.
    """

    __tablename__ = "resume_analysis_v2"
    __table_args__ = {"extend_existing": True}

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    analysis: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )


__all__ = ["ResumeV2", "ResumeStatisticsV2", "ResumeAnalysisV2"]
