"""REQ-061 AI Runtime Pydantic schemas aligned to ai-runtime.openapi.yaml (T030)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai_runtime.state_machine import TaskStatus

ServiceTier = Literal["standard", "quality"]

AvailableAction = Literal[
    "open_result",
    "provide_input",
    "confirm",
    "cancel",
    "resume",
    "retry_failed_component",
    "system_failure_retry",
    "reexecute",
    "submit_feedback",
    "dispute_points",
]


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    code: str
    correlation_id: str
    detail: str | None = None
    current_task: TaskSummary | None = None


class Stage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    progress_percent: int | None = None


class MilestoneQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    weight_basis_points: int = Field(ge=0, le=10000)
    max_points: int = Field(ge=0)


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str
    action: str
    service_tier: ServiceTier
    input_snapshot_ref: str
    allow_degrade: bool


class PointQuoteOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote_id: UUID
    price_table_version: str
    service_tier: ServiceTier
    max_points: int
    milestones: list[MilestoneQuote]
    balance_before: int
    projected_available_after_reservation: int
    expires_at: datetime


class PointSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quoted_max: int
    reserved: int
    settled: int
    released: int
    settlement_status: Literal["unsettled", "zero", "partial", "full", "reversed"]


class TaskSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    capability: str
    action: str
    status: TaskStatus
    stage: Stage
    service_tier: ServiceTier
    accepted_at: datetime
    terminal: bool
    available_actions: list[AvailableAction]
    point_summary: PointSummary
    title: str | None = None
    terminal_at: datetime | None = None


class TaskPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskSummary]
    next_cursor: str | None


class MilestoneOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    status: Literal["pending", "running", "delivered", "failed", "cancelled", "invalidated"]
    settle_eligible: bool
    points_settled: int
    result_ref: str | None = None
    delivered_at: datetime | None = None


class ExecutionRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: UUID
    execution_no: int
    trigger_kind: Literal[
        "initial",
        "system_failure_retry",
        "user_resume",
        "user_reexecute",
        "operator_reexecute",
    ]
    status: TaskStatus
    started_at: datetime
    source_execution_id: UUID | None = None
    finished_at: datetime | None = None


class FailurePresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    what_happened: str
    what_was_saved: str
    point_effect: str
    system_next_step: str
    user_next_steps: list[str]
    support_ref: str


class TaskDetail(TaskSummary):
    task_version: int
    input_summary: dict[str, Any]
    executions: list[ExecutionRef]
    milestones: list[MilestoneOut]
    degraded: bool
    automatic_retry_count: int
    result_ref: str | None = None
    failure: FailurePresentation | None = None
    degradation_summary: str | None = None


class TaskEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    sequence: int
    event_type: str
    occurred_at: datetime
    recorded_at: datetime
    status: TaskStatus
    stage: Stage
    message: str


class TaskAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    execution_id: UUID
    status: TaskStatus
    stage: Stage
    task_version: int
    quote: PointQuoteOut
    reservation_id: UUID
    accepted_at: datetime
    status_url: str
    events_url: str
    available_actions: list[AvailableAction]
    terminal: bool
    next_poll_after_ms: int | None = 1000


class AcceptTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str
    action: str
    service_tier: ServiceTier = "standard"
    quote_id: UUID
    input_snapshot_ref: str
    allow_degrade: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)


class TaskActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_task_version: int = Field(ge=1)
    reason: str | None = None


class ResumeRequest(TaskActionRequest):
    user_input_ref: str | None = None


class ReexecutionRequest(TaskActionRequest):
    input_mode: Literal["original_snapshot", "latest_snapshot"]
    behavior_mode: Literal["original_locked", "current_stable"]
    quote_id: UUID


class DecimalMoney(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: str
    currency: str = "CNY"


class CapabilityCatalogItem(BaseModel):
    """User-facing capability entry — tiers/points only, never provider names."""

    model_config = ConfigDict(extra="ignore")

    capability: str
    action: str | None = None
    actions: list[str] | None = None
    tiers: list[ServiceTier] | None = None
    service_tiers: list[ServiceTier] | None = None
    max_points_by_tier: dict[str, int] | None = None
    milestones: list[dict[str, Any]] | None = None


class CapabilityCatalogOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CapabilityCatalogItem]


class ModelPolicyCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str
    subscenario: str
    service_tier: ServiceTier
    primary_route: str
    allowed_fallbacks: list[str]
    quality_gate_ref: str
    latency_target_ms: int = Field(ge=1)
    cost_ceiling_rmb: DecimalMoney
    rollback_target: str | None = None
    owner: str
    reason: str = Field(min_length=1)


class ModelPolicyReleaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_status: Literal["gray", "stable", "stopped", "retired"]
    traffic_percent: float = Field(ge=0, le=100)
    eval_evidence_ref: str
    rollback_target: str
    reason: str = Field(min_length=1)


# Resolve forward ref for Problem.current_task
Problem.model_rebuild()


__all__ = [
    "AcceptTaskRequest",
    "AvailableAction",
    "CapabilityCatalogItem",
    "CapabilityCatalogOut",
    "DecimalMoney",
    "ExecutionRef",
    "FailurePresentation",
    "MilestoneOut",
    "MilestoneQuote",
    "ModelPolicyCommand",
    "ModelPolicyReleaseCommand",
    "PointQuoteOut",
    "PointSummary",
    "Problem",
    "QuoteRequest",
    "ReexecutionRequest",
    "ResumeRequest",
    "ServiceTier",
    "Stage",
    "TaskAccepted",
    "TaskActionRequest",
    "TaskDetail",
    "TaskEventOut",
    "TaskPage",
    "TaskStatus",
    "TaskSummary",
]
