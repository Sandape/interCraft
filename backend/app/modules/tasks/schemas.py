"""Task Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateTaskInput(BaseModel):
    type: str = Field(default="manual")
    title: str = Field(min_length=1, max_length=200)
    description_md: str | None = None
    related_entity_type: str | None = None
    related_entity_id: UUID | None = None
    due_at: datetime | None = None
    auto_generated: bool = False


class PatchTaskInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description_md: str | None = None
    status: str | None = None
    due_at: datetime | None = None


class TaskOut(BaseModel):
    id: UUID
    type: str
    title: str
    description_md: str | None
    related_entity_type: str | None
    related_entity_id: UUID | None
    status: str
    due_at: datetime | None
    completed_at: datetime | None
    auto_generated: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListOut(BaseModel):
    data: list[TaskOut]


class FindOrCreateInput(BaseModel):
    user_id: UUID
    type: str
    title: str
    related_entity_type: str | None = None
    related_entity_id: UUID | None = None


__all__ = [
    "CreateTaskInput", "FindOrCreateInput", "PatchTaskInput", "TaskListOut", "TaskOut",
]
