"""Pydantic schemas for resumes + blocks."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

BranchStatus = Literal["draft", "optimizing", "ready", "submitted", "archived"]
BlockType = Literal["heading", "summary", "experience", "project", "skill", "education", "custom"]


def _uuid_to_str(v: Any) -> Any:
    return str(v) if isinstance(v, UUID) else v


class ResumeBranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    parent_id: str | None
    name: str
    company: str | None
    position: str | None
    status: BranchStatus
    match_score: float | None
    is_main: bool
    is_pinned: bool
    style_preference: str
    last_edited_at: datetime
    created_at: datetime
    updated_at: datetime
    version_count: int = 0
    block_count: int = 0


class CreateBranchInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=128)
    position: str | None = Field(default=None, max_length=128)
    parent_id: str | None = None
    is_main: bool = False


class PatchBranchInput(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=128)
    position: str | None = Field(default=None, max_length=128)
    status: BranchStatus | None = None
    is_pinned: bool | None = None
    style_preference: str | None = None


class RefreshFromParentResponse(BaseModel):
    branch: ResumeBranchOut
    cloned_blocks: int


class CreateBranchResponse(BaseModel):
    branch: ResumeBranchOut


class ResumeBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    branch_id: str
    type: BlockType
    title: str | None
    content_md: str
    content_html: str | None
    meta: dict[str, Any] | None
    order_index: str
    collapsed: bool
    created_at: datetime
    updated_at: datetime

    _coerce_ids = field_validator("id", "branch_id", mode="before")(_uuid_to_str)


class CreateBlockInput(BaseModel):
    type: BlockType
    title: str | None = Field(default=None, max_length=200)
    content_md: str = ""
    meta: dict[str, Any] | None = None


class PatchBlockInput(BaseModel):
    type: BlockType | None = None
    title: str | None = Field(default=None, max_length=200)
    content_md: str | None = None
    meta: dict[str, Any] | None = None
    collapsed: bool | None = None


class ReorderBlocksInput(BaseModel):
    block_id: str
    prev_id: str | None = None
    next_id: str | None = None


class CreateBlockResponse(BaseModel):
    block: ResumeBlockOut


class ResumeBranchListResponse(BaseModel):
    data: list[ResumeBranchOut]


class ResumeBlockListResponse(BaseModel):
    data: list[ResumeBlockOut]


__all__ = [
    "BlockType",
    "BranchStatus",
    "CreateBlockInput",
    "CreateBlockResponse",
    "CreateBranchInput",
    "CreateBranchResponse",
    "PatchBlockInput",
    "PatchBranchInput",
    "RefreshFromParentResponse",
    "ReorderBlocksInput",
    "ResumeBlockListResponse",
    "ResumeBlockOut",
    "ResumeBranchListResponse",
    "ResumeBranchOut",
]
