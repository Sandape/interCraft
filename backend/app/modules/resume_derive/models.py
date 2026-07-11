"""ORM: resume_derive_runs (REQ-055)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ResumeDeriveRun(Base):
    __tablename__ = "resume_derive_runs"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    root_resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    root_version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_page_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    template_id: Mapped[str] = mapped_column(Text, nullable=False, default="muji-default-autumn")
    derived_resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    phase: Mapped[str] = mapped_column(Text, nullable=False, default="parse_jd")
    calibrate_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    root_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    job_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    component_status: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
