"""InterviewSession SQLAlchemy model — per data-model-phase-2.md §8.

Phase 2: read-only skeleton. No create/update/delete API.
Phase 4 M15: Agent creates sessions.

REQ-048 (Interview Mode Split): adds ``max_questions``, ``error_question_ids``,
``drill_cache_key`` columns. ``mode`` column already existed; migration 0028
adds CHECK + NOT NULL DEFAULT 'full'.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_uuid_v7


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Historically this pointed at resume_branches.id. Resume v2 is now the
    # active resume surface, so this field is a compatibility context id that
    # may contain either a legacy branch id or a resumes_v2.id.
    branch_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    # 019 — Job→Interview linking
    job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    position: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    # REQ-048 — mode already existed (line 37 of legacy file); migration 0028 adds CHECK + NOT NULL.
    mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    # REQ-048 — 10/15 (full mode only; nullable for quick_drill/doubao). CHECK 7..15 in DB.
    max_questions: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # REQ-048 — quick_drill only: 5 source_question_id from hybrid retrieval.
    error_question_ids: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=True
    )
    # REQ-048 — Redis cache key mirror for audit / invalidation (FR-015 / AC-09c).
    drill_cache_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    thread_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint_ns: Mapped[str | None] = mapped_column(Text, nullable=True)
    interview_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    web_research: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["InterviewSession"]
