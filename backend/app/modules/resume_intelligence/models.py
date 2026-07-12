"""Tenant-scoped persistence for REQ-059 resume intelligence."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes_v2.id", ondelete="CASCADE"), nullable=False
    )
    resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resume_hash: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    jd_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_derive_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_band: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    hard_blockers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    quality_flags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    scoring_version: Mapped[str] = mapped_column(Text, nullable=False, default="scoring.v1")
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False, default="resume-intelligence.v1")
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="analysis.v1")
    input_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail_safe: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResumeAISuggestion(Base):
    __tablename__ = "resume_ai_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_fit_analyses.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes_v2.id", ondelete="CASCADE"), nullable=False
    )
    base_resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    action_mode: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    anchor: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    requirement_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    proposed_patch: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    page_impact: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    applied_change_set_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ResumeAIChangeSet(Base):
    __tablename__ = "resume_ai_change_sets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes_v2.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_fit_analyses.id", ondelete="SET NULL"), nullable=True
    )
    base_resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_resume_version: Mapped[int] = mapped_column(Integer, nullable=False)
    suggestion_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    forward_patch: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    inverse_patch: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    before_hash: Mapped[str] = mapped_column(Text, nullable=False)
    after_hash: Mapped[str] = mapped_column(Text, nullable=False)
    preview_digest: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="applied")
    undo_of_change_set_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResumeAIFeedback(Base):
    __tablename__ = "resume_ai_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_fit_analyses.id", ondelete="CASCADE"), nullable=False
    )
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_ai_suggestions.id", ondelete="SET NULL"), nullable=True
    )
    change_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_ai_change_sets.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
