"""Interview session schemas (Phase 2 + Phase 4 + REQ-048)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# REQ-048 — Mode Literal (FR-001..FR-005).
# Mirrors the migration 0028 CHECK constraint ``mode IN ('quick_drill', 'full', 'doubao')``.
InterviewMode = Literal["quick_drill", "full", "doubao"]


class InterviewSessionCreate(BaseModel):
    """Request body for POST /interview-sessions (REQ-048 — extended)."""
    position: str | None = Field(default=None, min_length=1, max_length=100)
    company: str | None = Field(default=None, min_length=1, max_length=100)
    branch_id: UUID | None = None
    # REQ-048 — mode Literal enforced. Default 'full' keeps existing callers stable.
    mode: InterviewMode = "full"
    # REQ-048 — only when mode='full'; ignored for quick_drill/doubao.
    max_questions: int | None = None
    # REQ-048 — only when mode='quick_drill'; 5 source_question_ids from hybrid retrieval.
    error_question_ids: list[UUID] | None = None
    use_variants: bool = False
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
    # REQ-048 — mode now typed Literal.
    mode: InterviewMode | None = None
    # REQ-048 — max_questions + error_question_ids surfaced for client.
    max_questions: int | None = None
    error_question_ids: list[UUID] | None = None
    drill_cache_key: str | None = None
    status: str
    thread_id: str | None
    interview_plan: dict | None = None
    web_research: dict | None = None
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
    overall_score: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterviewSessionListOut(BaseModel):
    data: list[InterviewSessionOut]


# 020 (FIX-007, D-006) — narrow create-response schema. The contract
# (Round-2 MOCK-01) specifies exactly 6 fields under `data`:
#   id, status, thread_id, checkpoint_ns, job_id, branch_id
# ORM-only fields (position, company, mode, started_at, …) MUST NOT leak.
class InterviewSessionCreateData(BaseModel):
    id: UUID
    status: str
    thread_id: str | None
    checkpoint_ns: str | None
    job_id: UUID | None
    branch_id: UUID | None

    model_config = {"from_attributes": True}


class InterviewSessionCreateOut(BaseModel):
    data: InterviewSessionCreateData


class InterviewSessionResumeOut(BaseModel):
    data: dict


__all__ = [
    "InterviewMode",
    "InterviewSessionCreate",
    "InterviewSessionCreateOut",
    "InterviewSessionListOut",
    "InterviewSessionOut",
    "InterviewSessionResumeOut",
    "InterviewSessionStartOut",
]
