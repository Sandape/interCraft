"""Pydantic schemas for resume derive (REQ-055)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


ResumeKind = Literal["root", "derived", "standard"]
TargetPages = Literal[1, 2, 3]
SyncTarget = Literal["derived_only", "root", "discard"]
GuidanceAction = Literal[
    "switch_template", "hide_modules", "reduce_projects", "change_target_pages", "retry"
]


class DeriveStartIn(_Base):
    job_id: UUID
    target_page_count: TargetPages
    template_id: str = "pikachu"
    root_resume_id: UUID | None = None


class DeriveRunAcceptedOut(_Base):
    run_id: UUID
    status: str


class DeriveRunOut(_Base):
    id: UUID
    user_id: UUID
    job_id: UUID
    root_resume_id: UUID
    root_version: int
    target_page_count: int
    template_id: str
    derived_resume_id: UUID | None
    status: str
    phase: str
    calibrate_round: int
    progress_pct: int
    error_code: str | None
    error_message: str | None
    artifacts: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


class ResumeGuidanceIn(_Base):
    action: GuidanceAction
    template_id: str | None = None
    target_page_count: TargetPages | None = None
    hide_module_ids: list[str] = Field(default_factory=list)


class ExportGateOut(_Base):
    exportable: bool
    actual_page_count: int | None
    target_page_count: int | None
    blockers: list[str] = Field(default_factory=list)


class SupplementAnswer(_Base):
    question_id: str
    text: str


class SupplementIn(_Base):
    answers: list[SupplementAnswer]
    sync_target: SyncTarget


class DerivedResumeSummaryOut(_Base):
    id: UUID
    name: str
    job_id: UUID | None
    target_page_count: int | None
    actual_page_count: int | None
    root_version_at_derive: int | None
    created_at: datetime | None
    updated_at: datetime | None
    has_pending_suggestions: bool = False
    is_from_latest_root: bool = True


class SuggestionPreviewIn(_Base):
    suggestion_id: str
    client_version: int | None = None


class SuggestionApplyIn(_Base):
    suggestion_id: str
    client_version: int | None = None
    preview_token: str | None = None
