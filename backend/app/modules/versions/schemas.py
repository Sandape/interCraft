"""Pydantic schemas for M07 (versions)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _uuid_to_str(v: Any) -> Any:
    return str(v) if isinstance(v, UUID) else v


class SnapshotBlock(BaseModel):
    id: str
    type: str
    title: str | None = None
    content_md: str
    meta: dict[str, Any] | None = None
    order_index: str


class SnapshotBranch(BaseModel):
    id: str
    name: str
    company: str | None = None
    position: str | None = None
    status: str


class Snapshot(BaseModel):
    branch: SnapshotBranch
    blocks: list[SnapshotBlock]


class ResumeVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    branch_id: str
    version_no: int
    label: str | None = None
    is_full_snapshot: bool
    trigger: Literal["manual", "auto", "ai"]
    author_type: Literal["user", "ai"]
    actor_id: str | None = None
    created_at: datetime

    _coerce_ids = field_validator("id", "branch_id", "actor_id", mode="before")(_uuid_to_str)


class ResumeVersionDetail(ResumeVersionSummary):
    snapshot: Snapshot


class CreateVersionInput(BaseModel):
    label: str | None = Field(default=None, max_length=256)


class CreateVersionResponse(BaseModel):
    version: ResumeVersionSummary


class VersionsListResponse(BaseModel):
    data: list[ResumeVersionSummary]


class VersionDetailResponse(BaseModel):
    version: ResumeVersionDetail


class RollbackInput(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class RollbackResponse(BaseModel):
    new_branch_id: str


__all__ = [
    "CreateVersionInput",
    "CreateVersionResponse",
    "ResumeVersionDetail",
    "ResumeVersionSummary",
    "RollbackInput",
    "RollbackResponse",
    "Snapshot",
    "SnapshotBlock",
    "SnapshotBranch",
    "VersionDetailResponse",
    "VersionsListResponse",
]
