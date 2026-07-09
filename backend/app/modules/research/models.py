"""SQLAlchemy models for the interview-research module (REQ-053).

Defines two new tables:
- InterviewResearchTask  — one row per scheduled research job (one per job+interview_time)
- InterviewResearchResult — one row per search dimension executed

A note on access patterns:
- These models expose the table shape only; data access is performed via raw SQL
  in `app/modules/research/repository.py` (consistent with the existing
  InterviewReportRepo pattern), so most methods do not depend on ORM
  relationships. The ORM classes are still useful for type checking and for
  the test suite.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


RESEARCH_TASK_STATUSES = (
    "pending",
    "running",
    "completed",
    "cancelled",
    "failed",
    "quality_failed",
)

RESEARCH_DIMENSIONS = (
    "interview_experience",
    "company_product",
    "exam_points",
    "user_weakness",
)


class InterviewResearchTask(Base):
    __tablename__ = "interview_research_tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    interview_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(length=20), nullable=False, server_default="pending"
    )
    search_dimensions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    report_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN {RESEARCH_TASK_STATUSES!r}",
            name="ck_research_tasks_status",
        ),
        UniqueConstraint("job_id", "interview_time", name="uq_research_tasks_job_interview"),
    )


class InterviewResearchResult(Base):
    __tablename__ = "interview_research_results"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_research_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension: Mapped[str] = mapped_column(String(length=30), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    company: Mapped[str] = mapped_column(String(length=200), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"dimension IN {RESEARCH_DIMENSIONS!r}",
            name="ck_research_results_dimension",
        ),
    )


__all__ = [
    "InterviewResearchTask",
    "InterviewResearchResult",
    "RESEARCH_TASK_STATUSES",
    "RESEARCH_DIMENSIONS",
]