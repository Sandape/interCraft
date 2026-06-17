"""Error question Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from typing import Literal

ALLOWED_DIMENSIONS = {
    "tech_depth", "architecture", "engineering_practice",
    "communication", "algorithm", "business",
}
ALLOWED_STATUSES = {"fresh", "practicing", "mastered", "archived"}


class CreateErrorQuestionInput(BaseModel):
    dimension: str | None = None
    question_text: str = Field(min_length=1, max_length=2000)
    answer_text: str | None = None
    reference_answer_md: str | None = None
    score: int | None = Field(default=None, ge=0, le=10)
    tags: list[str] | None = None
    # 019/020 (FIX-001, D-002) — traceable auto-deposit from interview.
    # Without these fields the Pydantic v2 default `ignore` behavior
    # silently drops them on POST, breaking 019 FR-016 end-to-end.
    source_session_id: UUID | None = None
    source_question_id: UUID | None = None

    @field_validator("dimension")
    @classmethod
    def valid_dimension(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_DIMENSIONS:
            raise ValueError(f"Invalid dimension: {v}")
        return v


class PatchErrorQuestionInput(BaseModel):
    dimension: str | None = None
    question_text: str | None = Field(default=None, min_length=1, max_length=2000)
    answer_text: str | None = None
    reference_answer_md: str | None = None
    score: int | None = Field(default=None, ge=0, le=10)
    status: str | None = None
    frequency: int | None = Field(default=None, ge=0, le=3)
    tags: list[str] | None = None

    @field_validator("dimension")
    @classmethod
    def valid_dimension(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_DIMENSIONS:
            raise ValueError(f"Invalid dimension: {v}")
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class ErrorQuestionOut(BaseModel):
    id: UUID
    source_session_id: UUID | None
    # 019 — Interview→ErrorBook auto link
    source_question_id: UUID | None = None
    dimension: str | None
    question_text: str
    answer_text: str | None
    reference_answer_md: str | None
    score: int | None
    status: str
    frequency: int
    tags: list[str] | None
    archived_at: datetime | None
    last_practiced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ErrorQuestionListOut(BaseModel):
    data: list[ErrorQuestionOut]
    next_cursor: str | None = None
    has_more: bool = False


# 019 — source filter accepted by GET /error-questions
ErrorQuestionSource = Literal["auto", "manual", "all"]


__all__ = [
    "CreateErrorQuestionInput",
    "ErrorQuestionListOut",
    "ErrorQuestionOut",
    "ErrorQuestionSource",
    "PatchErrorQuestionInput",
]
