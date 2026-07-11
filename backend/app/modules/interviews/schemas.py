"""Interview session schemas (Phase 2 + Phase 4 + REQ-048 + REQ-061)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
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
    # REQ-061 — optional quote/degrade flags for runtime acceptance binding
    allow_degrade: bool = False
    service_tier: Literal["standard", "quality"] = "standard"


PlanStatus = Literal["pending", "ready", "failed", "degraded"]


class InterviewRuntimeEvent(BaseModel):
    """Ordered server event for reconnect / WS sync (REQ-061 T074)."""

    type: str
    sequence: int
    session_id: str | None = None
    round_no: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class InterviewPointsSummary(BaseModel):
    reserved: int = 0
    settled: int = 0
    currency: str = "points"
    chargeable_milestones: list[str] = Field(default_factory=list)


class SafeFailureDetail(BaseModel):
    code: str
    message: str
    safe: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class InterviewRuntimeEnvelope(BaseModel):
    """Canonical runtime projection attached to interview HTTP responses."""

    task_id: UUID | None = None
    execution_id: UUID | None = None
    available_actions: list[str] = Field(default_factory=list)
    events: list[InterviewRuntimeEvent] = Field(default_factory=list)
    points_summary: InterviewPointsSummary | None = None
    failure: SafeFailureDetail | None = None
    pause_deadline: datetime | str | None = None
    saved_round_explanation: str | None = None


class InterviewSessionStartOut(BaseModel):
    id: UUID
    status: str
    started_at: datetime
    # 019 — expose for client-side routing
    job_id: UUID | None = None
    branch_id: UUID | None = None
    # REQ-058 — plan prewarm visibility
    plan_status: PlanStatus | str | None = None
    plan_error_code: str | None = None
    plan_error_message: str | None = None
    degraded: bool = False
    # REQ-061
    task_id: UUID | None = None
    execution_id: UUID | None = None
    available_actions: list[str] = Field(default_factory=list)
    points_summary: InterviewPointsSummary | None = None
    failure: SafeFailureDetail | None = None
    runtime: InterviewRuntimeEnvelope | None = None


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
    # REQ-058
    plan_status: PlanStatus | str | None = None
    plan_error_code: str | None = None
    plan_error_message: str | None = None
    degraded: bool = False
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
    overall_score: float | None
    created_at: datetime
    updated_at: datetime
    # REQ-061 runtime projection (optional; omitted for legacy rows)
    task_id: UUID | None = None
    execution_id: UUID | None = None
    available_actions: list[str] = Field(default_factory=list)
    points_summary: InterviewPointsSummary | None = None
    failure: SafeFailureDetail | None = None
    pause_deadline: datetime | str | None = None
    runtime: InterviewRuntimeEnvelope | None = None

    model_config = {"from_attributes": True}


class InterviewActiveEndIn(BaseModel):
    scored_rounds: int = Field(default=0, ge=0)
    generate_partial_report: bool | None = None


class InterviewRetryComponentIn(BaseModel):
    component: Literal["score_delivery", "next_question", "report", "plan_fallback"]
    round_no: int | None = None
    evidence: dict[str, Any] | None = None
    dry_run: bool = False
    consented: bool = False


class InterviewPlanDegradeIn(BaseModel):
    confirm: bool = True


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
    "InterviewActiveEndIn",
    "InterviewMode",
    "InterviewPlanDegradeIn",
    "InterviewPointsSummary",
    "InterviewRetryComponentIn",
    "InterviewRuntimeEnvelope",
    "InterviewRuntimeEvent",
    "InterviewSessionCreate",
    "InterviewSessionCreateOut",
    "InterviewSessionListOut",
    "InterviewSessionOut",
    "InterviewSessionResumeOut",
    "InterviewSessionStartOut",
    "PlanStatus",
    "SafeFailureDetail",
]
