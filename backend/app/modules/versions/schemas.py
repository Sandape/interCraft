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


# ---- Version diff (spec 027 US7 FR-049/050) ----

class BlockLineDiff(BaseModel):
    """A single line-level diff entry inside a modified block.

    `kind` is one of 'unchanged' / 'added' / 'removed'. Caller renders
    them with green/red/grey coloring (FR-050).
    """

    kind: Literal["unchanged", "added", "removed"]
    text: str


class BlockDiff(BaseModel):
    """Per-block diff entry.

    `op` is one of 'unchanged' / 'added' / 'removed' / 'modified'.
    For `modified` blocks, `line_diff` is populated; for other ops it is null.
    """

    op: Literal["unchanged", "added", "removed", "modified"]
    # Stable identity: `(type, title)` keyed when present, else uses block id.
    key: str
    type: str
    title: str | None = None
    old_block: SnapshotBlock | None = None
    new_block: SnapshotBlock | None = None
    line_diff: list[BlockLineDiff] | None = None


class BranchDiff(BaseModel):
    """Branch-attribute diff (name/company/position/status)."""

    name: str | None = None
    company: str | None = None
    position: str | None = None
    status: str | None = None


class VersionDiff(BaseModel):
    """Top-level diff payload returned by GET /versions/:v1/diff/:v2."""

    branch_id: str
    old_version_no: int
    new_version_no: int
    branch_diff: BranchDiff
    blocks: list[BlockDiff]
    summary: dict[str, int]


class VersionDiffResponse(BaseModel):
    diff: VersionDiff


__all__ = [
    "BlockDiff",
    "BlockLineDiff",
    "BranchDiff",
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
    "VersionDiff",
    "VersionDiffResponse",
    "VersionsListResponse",
]
