"""REQ-061 US12 — admin AI inspection schemas (T161)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProblemDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int
    code: str
    correlation_id: str | None = None
    detail: str | None = None


class DataQualityBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    freshness_at: datetime | None = None
    coverage: dict[str, bool] = Field(default_factory=dict)
    unknown_count: int = 0
    stale: bool = False
    complete: bool = False
    projection_available: bool = True


class OperationalTaskSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    user_id: UUID
    root_task_id: UUID
    status: str
    capability_code: str
    action_code: str
    user_summary: str | None = None
    failure_category: str | None = None
    available_actions: list[str] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)
    data_quality: DataQualityBlock = Field(default_factory=DataQualityBlock)


class OperationalTaskPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OperationalTaskSummary]
    next_cursor: str | None = None
    data_quality: DataQualityBlock = Field(default_factory=DataQualityBlock)


class OperationalTaskDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    user_id: UUID
    root_task_id: UUID
    status: str
    capability_code: str
    action_code: str
    task_version: int | None = None
    user_summary: str | None = None
    failure_category: str | None = None
    available_actions: list[str] = Field(default_factory=list)
    denormalized: dict[str, Any] = Field(default_factory=dict)
    related: dict[str, list[str]] = Field(default_factory=dict)
    links: dict[str, str] = Field(default_factory=dict)
    data_quality: DataQualityBlock = Field(default_factory=DataQualityBlock)


class TimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    sequence: int | None = None
    event_type: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    safe_message: str | None = None
    occurred_at: datetime | None = None
    ref_id: str | None = None


class TimelinePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    items: list[TimelineItem]
    next_cursor: str | None = None
    data_quality: DataQualityBlock = Field(default_factory=DataQualityBlock)


class AttemptSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    attempt_kind: str | None = None
    status: str
    provider_redacted: bool = True
    created_at: datetime | None = None


class AttemptPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    items: list[AttemptSummary]
    next_cursor: str | None = None
    data_quality: DataQualityBlock = Field(default_factory=DataQualityBlock)


class EvidenceReplayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    complete: bool
    missing_sequences: list[int] = Field(default_factory=list)
    event_count: int = 0
    provider_calls_created: int = 0
    tool_calls_created: int = 0
    ledger_events_created: int = 0
    reconstructed: bool = True
    read_only: bool = True


__all__ = [
    "AttemptPage",
    "AttemptSummary",
    "DataQualityBlock",
    "EvidenceReplayResponse",
    "OperationalTaskDetail",
    "OperationalTaskPage",
    "OperationalTaskSummary",
    "ProblemDetail",
    "TimelineItem",
    "TimelinePage",
]
