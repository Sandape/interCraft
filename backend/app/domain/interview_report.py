"""InterviewReport domain model + Pydantic schemas (T031).

REQ-053 extends this table with `report_type` (mock_interview | pre_interview_research)
plus job_id, interview_time, research_task_id, rating, delivery_status fields.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ReportType = Literal["mock_interview", "pre_interview_research"]
DeliveryStatus = Literal["pending", "sent", "failed", "delayed", "cancelled"]


class InterviewReportCreate(BaseModel):
    """Schema for creating a mock-interview report (existing)."""
    overall_score: float = Field(..., ge=0, le=10)
    per_question_score: list[dict[str, Any]]
    dimension_scores: dict[str, float]
    strengths: list[dict[str, Any]]
    improvements: list[dict[str, Any]]
    summary_md: str
    session_id: UUID


class InterviewReportResponse(BaseModel):
    """API response schema for interview report."""
    id: UUID
    session_id: UUID
    overall_score: float
    per_question_score: list[dict[str, Any]]
    dimension_scores: dict[str, float]
    strengths: list[dict[str, Any]]
    improvements: list[dict[str, Any]]
    summary_md: str
    generated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewReportListOut(BaseModel):
    data: list[InterviewReportResponse]


# --- REQ-053: pre_interview_research report schemas ---


class ResearchReportCreate(BaseModel):
    """Schema for creating a pre-interview research report.

    All `interview_report` columns pertaining to mock_interview scoring
    (overall_score, per_question_score, dimension_scores, strengths,
    improvements, session_id) remain NULL for this report type.
    """
    job_id: UUID
    interview_time: datetime
    research_task_id: UUID | None = None
    summary_md: str = Field(..., min_length=1)
    report_type: ReportType = "pre_interview_research"


class ResearchReportOut(BaseModel):
    """Full read schema for a pre-interview research report."""
    id: UUID
    report_type: ReportType
    job_id: UUID | None
    interview_time: datetime | None
    research_task_id: UUID | None
    summary_md: str
    rating: int | None = None
    delivery_status: DeliveryStatus | None = None
    delivered_at: datetime | None = None
    quality_check_passed: bool | None = None
    generated_at: datetime
    created_at: datetime
    updated_at: datetime | None = None


class ResearchReportSummary(BaseModel):
    """Lightweight summary used for list views (per-job history)."""
    id: UUID
    report_type: ReportType
    job_id: UUID
    interview_time: datetime
    rating: int | None = None
    delivery_status: DeliveryStatus | None = None
    generated_at: datetime


class ResearchReportListOut(BaseModel):
    data: list[ResearchReportSummary]


__all__ = [
    "InterviewReportCreate",
    "InterviewReportListOut",
    "InterviewReportResponse",
    "ResearchReportCreate",
    "ResearchReportOut",
    "ResearchReportSummary",
    "ResearchReportListOut",
    "ReportType",
    "DeliveryStatus",
]
