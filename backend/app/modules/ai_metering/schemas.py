"""REQ-061 AI Metering Pydantic schemas aligned to ai-metering.openapi.yaml (T051)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


PointEventType = Literal[
    "grant",
    "expire",
    "reserve",
    "settle",
    "release",
    "refund",
    "compensate",
    "reverse",
]

BucketType = Literal["daily_experience", "compensation"]

ExportStatus = Literal["queued", "running", "ready", "failed", "expired"]


def task_deep_link(task_id: UUID) -> str:
    """Owner-facing deep link into the AI task detail surface."""
    return f"/api/v1/ai-tasks/{task_id}"


class PointBucketOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket_id: UUID
    bucket_type: BucketType
    available: int = Field(ge=0)
    reserved: int = Field(ge=0)
    expires_at: datetime
    business_date: date | None = None
    grant_config_version: str | None = None


class PointAccountOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_label: Literal["Pro"] = "Pro"
    experience_badge: Literal["新用户体验"] = "新用户体验"
    is_paid: Literal[False] = False
    business_date: date
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    available: int = Field(ge=0)
    reserved: int = Field(ge=0)
    buckets: list[PointBucketOut]
    next_expiry: datetime | None = None
    daily_grant_amount: int = Field(ge=0, default=2000)
    grant_config_version: str
    parallel_ai_task_limit: Literal[2] = 2
    history_days: Literal[90] = 90


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_type: PointEventType
    occurred_at: datetime
    recorded_at: datetime
    available_delta: int
    reserved_delta: int
    available_after: int = Field(ge=0)
    reserved_after: int = Field(ge=0)
    reason: str
    task_id: UUID | None = None
    execution_id: UUID | None = None
    milestone_code: str | None = None
    capability: str | None = None
    service_tier: Literal["standard", "quality"] | None = None
    expires_at: datetime | None = None


class LedgerPageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LedgerEntryOut]
    next_cursor: str | None


class PointBudgetOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_limit: int = Field(ge=0)
    consumed_today: int = Field(ge=0)
    available: int = Field(ge=0)
    risk_limit: int = Field(ge=0)
    effective_limit: int = Field(ge=0)
    version: int = Field(ge=1)


class UpdateBudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_limit: int = Field(ge=0)
    expected_version: int = Field(ge=1)


class ExportLedgerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: datetime = Field(alias="from")
    to: datetime


class ExportJobOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: UUID
    status: ExportStatus
    created_at: datetime
    expires_at: datetime


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    code: str
    correlation_id: str
    detail: str | None = None


__all__ = [
    "BucketType",
    "ExportJobOut",
    "ExportLedgerRequest",
    "ExportStatus",
    "LedgerEntryOut",
    "LedgerPageOut",
    "PointAccountOut",
    "PointBudgetOut",
    "PointBucketOut",
    "PointEventType",
    "Problem",
    "UpdateBudgetRequest",
    "task_deep_link",
]
