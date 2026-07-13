"""Tenant-scoped persistence for REQ-059 resume intelligence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Worker processes do not import the HTTP router graph, so register every
# referenced table explicitly before SQLAlchemy sorts FK dependencies during
# flush. These are metadata imports only; domain access remains repository-led.
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.avatars import models as _avatar_models  # noqa: F401
from app.modules.jobs import models as _job_models  # noqa: F401
from app.modules.resume_derive import models as _derive_models  # noqa: F401
from app.modules.resumes_v2 import models as _resume_models  # noqa: F401


def _now() -> datetime:
    return datetime.now(UTC)


class ResumeFitAnalysis(Base):
    __tablename__ = "resume_fit_analyses"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_resume_fit_analyses_user_id_id"),
        CheckConstraint(
            "mode IN ('general','job_fit')",
            name="ck_resume_fit_analyses_mode",
        ),
        CheckConstraint(
            "status IN ('queued','running','complete','partial','failed','cancelled')",
            name="ck_resume_fit_analyses_status",
        ),
        CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)",
            name="ck_resume_fit_analyses_score",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_resume_fit_analyses_confidence",
        ),
        ForeignKeyConstraint(
            ["user_id", "resume_id"],
            ["resumes_v2.user_id", "resumes_v2.id"],
            name="fk_resume_fit_analyses_resume_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "job_id"],
            ["jobs.user_id", "jobs.id"],
            name="fk_resume_fit_analyses_job_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "run_id"],
            ["resume_derive_runs.user_id", "resume_derive_runs.id"],
            name="fk_resume_fit_analyses_run_tenant",
        ),
        Index(
            "idx_resume_fit_analyses_resume_history",
            "user_id",
            "resume_id",
            "created_at",
        ),
        Index("idx_resume_fit_analyses_run", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="resume_fit_analyses_user_id_fkey", ondelete="CASCADE"),
        nullable=False,
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resumes_v2.id",
            name="resume_fit_analyses_resume_id_fkey",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resume_hash: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", name="resume_fit_analyses_job_id_fkey", ondelete="SET NULL"),
        nullable=True,
    )
    jd_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_derive_runs.id",
            name="resume_fit_analyses_run_id_fkey",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="queued", server_default=text("'queued'::text")
    )
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_band: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimensions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    hard_blockers: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source_manifest: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    quality_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    scoring_version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="scoring.v1",
        server_default=text("'scoring.v1'::text"),
    )
    prompt_version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="resume-intelligence.v1",
        server_default=text("'resume-intelligence.v1'::text"),
    )
    schema_version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="analysis.v1",
        server_default=text("'analysis.v1'::text"),
    )
    input_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail_safe: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResumeAISuggestion(Base):
    __tablename__ = "resume_ai_suggestions"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_resume_ai_suggestions_user_id_id"),
        CheckConstraint(
            "status IN ('open','previewed','applied','ignored','deferred','stale',"
            "'conflict','withdrawn','undone')",
            name="ck_resume_ai_suggestions_status",
        ),
        ForeignKeyConstraint(
            ["user_id", "analysis_id"],
            ["resume_fit_analyses.user_id", "resume_fit_analyses.id"],
            name="fk_resume_ai_suggestions_analysis_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "resume_id"],
            ["resumes_v2.user_id", "resumes_v2.id"],
            name="fk_resume_ai_suggestions_resume_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "applied_change_set_id"],
            ["resume_ai_change_sets.user_id", "resume_ai_change_sets.id"],
            name="fk_resume_ai_suggestions_change_set_tenant",
        ),
        Index("idx_resume_ai_suggestions_analysis_status", "analysis_id", "status"),
        Index("idx_resume_ai_suggestions_resume", "user_id", "resume_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="resume_ai_suggestions_user_id_fkey", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_fit_analyses.id",
            name="resume_ai_suggestions_analysis_id_fkey",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resumes_v2.id",
            name="resume_ai_suggestions_resume_id_fkey",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    base_resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    action_mode: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    anchor: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    requirement_refs: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    proposed_patch: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    page_impact: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="open", server_default=text("'open'::text")
    )
    applied_change_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_ai_change_sets.id",
            name="fk_resume_ai_suggestions_change_set",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, server_default=text("now()")
    )


class ResumeAIChangeSet(Base):
    __tablename__ = "resume_ai_change_sets"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_resume_ai_change_sets_user_id_id"),
        UniqueConstraint(
            "resume_id",
            "result_resume_version",
            name="uq_resume_ai_change_sets_result_version",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_resume_ai_change_sets_idempotency",
        ),
        CheckConstraint(
            "status IN ('applied','undone','superseded')",
            name="ck_resume_ai_change_sets_status",
        ),
        ForeignKeyConstraint(
            ["user_id", "resume_id"],
            ["resumes_v2.user_id", "resumes_v2.id"],
            name="fk_resume_ai_change_sets_resume_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "analysis_id"],
            ["resume_fit_analyses.user_id", "resume_fit_analyses.id"],
            name="fk_resume_ai_change_sets_analysis_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "undo_of_change_set_id"],
            ["resume_ai_change_sets.user_id", "resume_ai_change_sets.id"],
            name="fk_resume_ai_change_sets_undo_of_tenant",
        ),
        Index("idx_resume_ai_change_sets_history", "user_id", "resume_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="resume_ai_change_sets_user_id_fkey", ondelete="CASCADE"),
        nullable=False,
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resumes_v2.id",
            name="resume_ai_change_sets_resume_id_fkey",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_fit_analyses.id",
            name="resume_ai_change_sets_analysis_id_fkey",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    base_resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    suggestion_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    forward_patch: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    inverse_patch: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    before_hash: Mapped[str] = mapped_column(Text, nullable=False)
    after_hash: Mapped[str] = mapped_column(Text, nullable=False)
    preview_digest: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="applied", server_default=text("'applied'::text")
    )
    undo_of_change_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_ai_change_sets.id",
            name="fk_resume_ai_change_sets_undo_of",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, server_default=text("now()")
    )
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResumeAIFeedback(Base):
    __tablename__ = "resume_ai_feedback"
    __table_args__ = (
        CheckConstraint(
            "category IN ('helpful','not_applicable','repeated','poor_wording',"
            "'fact_error','other')",
            name="ck_resume_ai_feedback_category",
        ),
        CheckConstraint(
            "comment IS NULL OR length(comment) <= 1000",
            name="ck_resume_ai_feedback_comment_length",
        ),
        ForeignKeyConstraint(
            ["user_id", "analysis_id"],
            ["resume_fit_analyses.user_id", "resume_fit_analyses.id"],
            name="fk_resume_ai_feedback_analysis_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "suggestion_id"],
            ["resume_ai_suggestions.user_id", "resume_ai_suggestions.id"],
            name="fk_resume_ai_feedback_suggestion_tenant",
        ),
        ForeignKeyConstraint(
            ["user_id", "change_set_id"],
            ["resume_ai_change_sets.user_id", "resume_ai_change_sets.id"],
            name="fk_resume_ai_feedback_change_set_tenant",
        ),
        Index("idx_resume_ai_feedback_analysis", "user_id", "analysis_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="resume_ai_feedback_user_id_fkey", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_fit_analyses.id",
            name="resume_ai_feedback_analysis_id_fkey",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_ai_suggestions.id",
            name="resume_ai_feedback_suggestion_id_fkey",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    change_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_ai_change_sets.id",
            name="resume_ai_feedback_change_set_id_fkey",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, server_default=text("now()")
    )
