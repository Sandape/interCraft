"""Job Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CreateJobInput(BaseModel):
    company: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=100)
    jd_url: str | None = Field(default=None, pattern=r'^https?://.*')
    branch_id: UUID | None = None
    notes_md: str | None = None


class PatchJobInput(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=100)
    position: str | None = Field(default=None, min_length=1, max_length=100)
    jd_url: str | None = Field(default=None, pattern=r'^https?://.*')
    branch_id: UUID | None = None
    notes_md: str | None = None


class UpdateJobStatusInput(BaseModel):
    to: str
    note: str = Field(default="", max_length=500)


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


__all__ = [
    "CreateJobInput", "JobListOut", "JobOut", "JobStatsOut",
    "JobTimelineOut", "PatchJobInput", "UpdateJobStatusInput",
]
