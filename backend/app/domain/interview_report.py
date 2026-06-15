"""InterviewReport domain model + Pydantic schemas (T031)."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewReportCreate(BaseModel):
    """Schema for creating an interview report."""
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


__all__ = ["InterviewReportCreate", "InterviewReportListOut", "InterviewReportResponse"]
