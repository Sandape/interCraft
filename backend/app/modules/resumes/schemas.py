"""Pydantic schemas for resumes + blocks."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

BranchStatus = Literal["draft", "optimizing", "ready", "submitted", "archived"]
BlockType = Literal["heading", "summary", "experience", "project", "skill", "education", "custom"]

VALID_THEME_IDS = {"default", "blue", "orange", "pupple"}
VALID_AVATAR_POSITIONS = {"left", "right", "top", "center", "bottom"}
VALID_AVATAR_SHAPES = {"circle", "rounded", "square"}
AVATAR_SIZE_MIN = 50
AVATAR_SIZE_MAX = 200
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _uuid_to_str(v: Any) -> Any:
    return str(v) if isinstance(v, UUID) else v


class ResumeBranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    parent_id: str | None

    _coerce_ids = field_validator("id", "parent_id", mode="before")(_uuid_to_str)
    name: str
    company: str | None
    position: str | None
    status: BranchStatus
    match_score: float | None
    is_main: bool
    is_pinned: bool
    style_preference: str
    theme_id: str = "default"
    accent_color: str = "#39393a"
    avatar_url: str | None = None
    avatar_size: int | None = None
    avatar_position: str | None = None
    avatar_shape: str | None = None
    avatar_updated_at: datetime | None = None
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
    theme_id: str = Field(default="default", max_length=32)
    accent_color: str = Field(default="#39393a", max_length=7)

    @field_validator("theme_id")
    @classmethod
    def _validate_theme_id(cls, v: str) -> str:
        if v not in VALID_THEME_IDS:
            raise ValueError(f"theme_id must be one of {VALID_THEME_IDS}, got '{v}'")
        return v

    @field_validator("accent_color")
    @classmethod
    def _validate_accent_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            raise ValueError(f"accent_color must be a #RRGGBB hex string, got '{v}'")
        return v


class PatchBranchInput(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=128)
    position: str | None = Field(default=None, max_length=128)
    status: BranchStatus | None = None
    is_pinned: bool | None = None
    style_preference: str | None = None
    theme_id: str | None = Field(default=None, max_length=32)
    accent_color: str | None = Field(default=None, max_length=7)
    avatar_url: str | None = Field(default=None, max_length=512)
    avatar_size: int | None = Field(default=None, ge=AVATAR_SIZE_MIN, le=AVATAR_SIZE_MAX)
    avatar_position: str | None = Field(default=None, max_length=16)
    avatar_shape: str | None = Field(default=None, max_length=16)

    @field_validator("theme_id")
    @classmethod
    def _validate_theme_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in VALID_THEME_IDS:
            raise ValueError(f"theme_id must be one of {VALID_THEME_IDS}, got '{v}'")
        return v

    @field_validator("accent_color")
    @classmethod
    def _validate_accent_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_COLOR_RE.match(v):
            raise ValueError(f"accent_color must be a #RRGGBB hex string, got '{v}'")
        return v

    @field_validator("avatar_position")
    @classmethod
    def _validate_avatar_position(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in VALID_AVATAR_POSITIONS:
            raise ValueError(
                f"avatar_position must be one of {sorted(VALID_AVATAR_POSITIONS)}, got '{v}'"
            )
        return v

    @field_validator("avatar_shape")
    @classmethod
    def _validate_avatar_shape(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in VALID_AVATAR_SHAPES:
            raise ValueError(
                f"avatar_shape must be one of {sorted(VALID_AVATAR_SHAPES)}, got '{v}'"
            )
        return v


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
