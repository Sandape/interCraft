"""Interview session schemas (Phase 2 + Phase 4)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewSessionCreate(BaseModel):
    """Request body for POST /interview-sessions."""
    position: str = Field(..., min_length=1, max_length=100)
    company: str = Field(..., min_length=1, max_length=100)
    branch_id: UUID | None = None
    mode: str = "text"
    # 019 — Job→Interview linking (optional)
    job_id: UUID | None = None


class InterviewSessionStartOut(BaseModel):
    id: UUID
    status: str
    started_at: datetime
    # 019 — expose for client-side routing
    job_id: UUID | None = None
    branch_id: UUID | None = None


class InterviewSessionOut(BaseModel):
    id: UUID
    branch_id: UUID | None
    # 019 — Job→Interview linking
    job_id: UUID | None = None
    position: str | None
    company: str | None
    mode: str | None
    status: str
    thread_id: str | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
    overall_score: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterviewSessionListOut(BaseModel):
    data: list[InterviewSessionOut]


class InterviewSessionCreateOut(BaseModel):
    data: InterviewSessionOut


class InterviewSessionResumeOut(BaseModel):
    data: dict


__all__ = [
    "InterviewSessionCreate",
    "InterviewSessionCreateOut",
    "InterviewSessionListOut",
    "InterviewSessionOut",
    "InterviewSessionResumeOut",
    "InterviewSessionStartOut",
]
