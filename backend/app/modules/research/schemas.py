"""Pydantic schemas for the interview-research module (REQ-053)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ResearchTaskStatus = Literal[
    "pending", "running", "completed", "cancelled", "failed", "quality_failed"
]
ResearchDimension = Literal[
    "interview_experience", "company_product", "exam_points", "user_weakness"
]


class ResearchTaskCreate(BaseModel):
    job_id: UUID
    user_id: UUID
    interview_time: datetime


class ResearchTaskOut(BaseModel):
    id: UUID
    job_id: UUID
    user_id: UUID
    interview_time: datetime
    status: ResearchTaskStatus
    search_dimensions: dict[str, Any] = Field(default_factory=dict)
    report_id: UUID | None = None
    triggered_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ResearchTaskListOut(BaseModel):
    data: list[ResearchTaskOut]


class ResearchResultCreate(BaseModel):
    task_id: UUID
    dimension: ResearchDimension
    query: str
    company: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    result_count: int = 0
    error: str | None = None


class ResearchResultOut(BaseModel):
    id: UUID
    task_id: UUID
    dimension: ResearchDimension
    query: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    result_count: int
    company: str
    error: str | None = None
    searched_at: datetime


class ResearchStats(BaseModel):
    total_tasks: int
    by_status: dict[str, int]
    total_reports: int
    average_rating: float | None = None


class TriggerResearchRequest(BaseModel):
    job_id: UUID


class TriggerResearchResponse(BaseModel):
    task_id: UUID
    status: ResearchTaskStatus


__all__ = [
    "ResearchTaskCreate",
    "ResearchTaskOut",
    "ResearchTaskListOut",
    "ResearchResultCreate",
    "ResearchResultOut",
    "ResearchStats",
    "TriggerResearchRequest",
    "TriggerResearchResponse",
    "ResearchTaskStatus",
    "ResearchDimension",
]