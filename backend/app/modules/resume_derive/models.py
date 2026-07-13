"""ORM: resume_derive_runs (REQ-055)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ResumeDeriveRun(Base):
    __tablename__ = "resume_derive_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_resume_derive_runs_user_id_id"),
        CheckConstraint(
            "status IN ('pending','queued','running','succeeded','partial_success',"
            "'needs_guidance','canceling','cancelled','failed','canceled')",
            name="ck_resume_derive_runs_status",
        ),
        CheckConstraint(
            "target_page_count IN (1, 2, 3)",
            name="ck_resume_derive_runs_pages",
        ),
        ForeignKeyConstraint(
            ["user_id", "job_id"],
            ["jobs.user_id", "jobs.id"],
            name="fk_resume_derive_runs_job_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "root_resume_id"],
            ["resumes_v2.user_id", "resumes_v2.id"],
            name="fk_resume_derive_runs_root_resume_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "derived_resume_id"],
            ["resumes_v2.user_id", "resumes_v2.id"],
            name="fk_resume_derive_runs_derived_resume_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "analysis_id"],
            ["resume_fit_analyses.user_id", "resume_fit_analyses.id"],
            name="fk_resume_derive_runs_analysis_tenant",
        ),
        Index("idx_resume_derive_runs_user_status", "user_id", "status"),
        Index("idx_resume_derive_runs_job_id", "job_id"),
        Index(
            "uq_resume_derive_runs_user_idempotency",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "idx_resume_derive_runs_input_fingerprint",
            "user_id",
            "input_fingerprint",
        ),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="resume_derive_runs_user_id_fkey", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", name="resume_derive_runs_job_id_fkey", ondelete="SET NULL"),
        nullable=True,
    )
    root_resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resumes_v2.id",
            name="resume_derive_runs_root_resume_id_fkey",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    root_version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_page_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    template_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="pikachu",
        server_default=text("'pikachu'::text"),
    )
    derived_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resumes_v2.id",
            name="resume_derive_runs_derived_resume_id_fkey",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default=text("'pending'::text")
    )
    phase: Mapped[str] = mapped_column(
        Text, nullable=False, default="parse_jd", server_default=text("'parse_jd'::text")
    )
    calibrate_round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    progress_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifacts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    root_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    job_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    component_status: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_fit_analyses.id",
            name="fk_resume_derive_runs_analysis_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=text("now()"),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
