"""Pydantic schemas for GET /me/dashboard-summary (REQ-057)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CtaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    href: str


class TodayInterviewItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    company: str
    position: str
    interview_time: datetime
    status: str
    relative_label: str
    href: str


class OnboardingStepOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal["resume", "job", "interview"]
    done: bool
    href: str


class OnboardingProgressOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show: bool
    steps: list[OnboardingStepOut]


class ResumableSessionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    company: str | None = None
    position: str | None = None
    status: str
    href: str


class CommandCenterL0Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    greeting_context: str
    next_interview: TodayInterviewItemOut | None = None
    today_interviews: list[TodayInterviewItemOut] = Field(default_factory=list)
    primary_cta: CtaOut
    onboarding: OnboardingProgressOut | None = None
    resumable_sessions: list[ResumableSessionOut] = Field(default_factory=list)


class ResumeSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    resume_kind: str
    job_id: UUID | None = None
    updated_at: datetime | None = None
    href: str


class ResumeCountsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: int = 0
    derived: int = 0
    standard: int = 0
    total: int = 0


class NextActionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title_zh: str
    body_zh: str
    cta: CtaOut
    tier: Literal[0, 1, 2]


class FunnelSegmentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["applying", "interviewing", "awaiting_feedback"]
    label_zh: str
    count: int
    filter_statuses: list[str] = Field(default_factory=list)
    href: str


class PrepPackOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    derived_resume_id: UUID | None = None
    actions: list[CtaOut] = Field(default_factory=list)


class CommandCenterL1Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume_summaries: list[ResumeSummaryOut] = Field(default_factory=list)
    resume_counts: ResumeCountsOut = Field(default_factory=ResumeCountsOut)
    next_action: NextActionOut | None = None
    job_funnel: list[FunnelSegmentOut] = Field(default_factory=list)
    prep_pack: PrepPackOut | None = None


class WeakDimensionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label_zh: str
    actual_score: float


class AbilitySnapshotOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_score: float
    weakest_dimensions: list[WeakDimensionOut] = Field(default_factory=list)
    href: str = "/ability-profile"


class ActivityViewOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    type: str
    title_zh: str
    detail_zh: str = ""
    occurred_at: datetime | None = None
    href: str | None = None


class InterviewTrendOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_count: int
    avg_score: float


class CommandCenterL2Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ability_snapshot: AbilitySnapshotOut | None = None
    recent_activities: list[ActivityViewOut] = Field(default_factory=list)
    interview_trend: InterviewTrendOut | None = None


class DashboardSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    cache_ttl_sec: int = 60
    tz: str
    local_date: date
    l0: CommandCenterL0Out
    l1: CommandCenterL1Out
    l2: CommandCenterL2Out


class DashboardSummaryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DashboardSummaryOut


__all__ = [
    "AbilitySnapshotOut",
    "ActivityViewOut",
    "CommandCenterL0Out",
    "CommandCenterL1Out",
    "CommandCenterL2Out",
    "CtaOut",
    "DashboardSummaryEnvelope",
    "DashboardSummaryOut",
    "FunnelSegmentOut",
    "InterviewTrendOut",
    "NextActionOut",
    "OnboardingProgressOut",
    "OnboardingStepOut",
    "PrepPackOut",
    "ResumableSessionOut",
    "ResumeCountsOut",
    "ResumeSummaryOut",
    "TodayInterviewItemOut",
    "WeakDimensionOut",
]
