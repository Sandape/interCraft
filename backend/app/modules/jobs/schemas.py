"""Job Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

EmploymentType = Literal["internship", "campus", "experienced", "contract", "unspecified"]


class CreateJobInput(BaseModel):
    company: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=100)
    jd_url: str | None = Field(default=None, pattern=r'^https?://.*')
    branch_id: UUID | None = None
    notes_md: str | None = None
    # 019 — extended fields
    base_location: str | None = Field(default=None, max_length=50)
    requirements_md: str | None = Field(default=None, max_length=5000)
    employment_type: EmploymentType = "unspecified"
    salary_range_text: str | None = Field(default=None, max_length=100)
    headcount: int | None = Field(default=None, ge=1)


class PatchJobInput(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=100)
    position: str | None = Field(default=None, min_length=1, max_length=100)
    jd_url: str | None = Field(default=None, pattern=r'^https?://.*')
    branch_id: UUID | None = None
    notes_md: str | None = None
    # 019 — extended fields
    base_location: str | None = Field(default=None, max_length=50)
    requirements_md: str | None = Field(default=None, max_length=5000)
    employment_type: EmploymentType | None = None
    salary_range_text: str | None = Field(default=None, max_length=100)
    headcount: int | None = Field(default=None, ge=1)
    # REQ-053: Interview time for interview-round states. Must be ISO 8601 datetime.
    interview_time: datetime | None = Field(default=None)


class UpdateJobStatusInput(BaseModel):
    to: str
    note: str = Field(default="", max_length=500)
    # REQ-053: Required when `to` is test/interview_1/interview_2/interview_3; must be future time.
    interview_time: datetime | None = Field(default=None)


class StatusChange(BaseModel):
    from_: str | None
    to: str
    at: str
    note: str


class JobOut(BaseModel):
    id: UUID
    company: str
    position: str
    jd_url: str | None
    branch_id: UUID | None
    status: str
    status_history: list[dict]
    last_status_changed_at: datetime
    notes_md: str | None
    # 019 — extended fields
    base_location: str
    requirements_md: str | None
    employment_type: str
    salary_range_text: str | None
    headcount: int | None
    # REQ-053
    interview_time: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListOut(BaseModel):
    data: list[JobOut]
    next_cursor: str | None = None
    has_more: bool = False


class JobStatsOut(BaseModel):
    counts: dict[str, int]
    total: int


class JobTimelineOut(BaseModel):
    job_id: UUID
    status_history: list[dict]


class TransitionEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str

    model_config = {"populate_by_name": True}


class TransitionsOut(BaseModel):
    statuses: list[str]
    transitions: list[TransitionEdge]


__all__ = [
    "CreateJobInput", "JobListOut", "JobOut", "JobStatsOut",
    "JobTimelineOut", "PatchJobInput", "UpdateJobStatusInput",
    "TransitionEdge", "TransitionsOut", "EmploymentType",
]
