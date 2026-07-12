"""Strict runtime envelopes and authoritative state transitions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    RECEIVED = "received"
    UNDERSTANDING = "understanding"
    AWAITING_INPUT = "awaiting_input"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    RETRY_WAIT = "retry_wait"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN_RESULT = "unknown_result"
    DEAD_LETTER = "dead_letter"


class ConfirmationStatus(StrEnum):
    PENDING = "pending"
    CONSUMED = "consumed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class ToolExecutionStatus(StrEnum):
    PROPOSED = "proposed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY_WAIT = "retry_wait"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN_RESULT = "unknown_result"
    DEAD_LETTER = "dead_letter"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SENDING = "sending"
    DELIVERED = "delivered"
    RETRY_WAIT = "retry_wait"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN_DELIVERY = "unknown_delivery"
    DEAD_LETTER = "dead_letter"


class InvalidTransition(ValueError):
    """Raised before persistence when a state transition is not allowed."""


_T = TypeVar("_T", bound=StrEnum)


def _validate_transition(current: _T, target: _T, graph: dict[_T, frozenset[_T]]) -> _T:
    if target not in graph.get(current, frozenset()):
        raise InvalidTransition(f"invalid transition: {current.value} -> {target.value}")
    return target


TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.RECEIVED: frozenset({TaskStatus.UNDERSTANDING, TaskStatus.QUEUED, TaskStatus.CANCELLED}),
    TaskStatus.UNDERSTANDING: frozenset({TaskStatus.AWAITING_INPUT, TaskStatus.AWAITING_CONFIRMATION, TaskStatus.QUEUED, TaskStatus.FAILED, TaskStatus.CANCELLED}),
    TaskStatus.AWAITING_INPUT: frozenset({TaskStatus.UNDERSTANDING, TaskStatus.CANCELLED}),
    TaskStatus.AWAITING_CONFIRMATION: frozenset({TaskStatus.QUEUED, TaskStatus.CANCELLED, TaskStatus.FAILED}),
    TaskStatus.QUEUED: frozenset({TaskStatus.RUNNING, TaskStatus.CANCEL_REQUESTED, TaskStatus.CANCELLED, TaskStatus.FAILED}),
    TaskStatus.RUNNING: frozenset({TaskStatus.AWAITING_INPUT, TaskStatus.AWAITING_CONFIRMATION, TaskStatus.WAITING_EXTERNAL, TaskStatus.RETRY_WAIT, TaskStatus.CANCEL_REQUESTED, TaskStatus.CANCELLED, TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.UNKNOWN_RESULT, TaskStatus.DEAD_LETTER}),
    TaskStatus.WAITING_EXTERNAL: frozenset({TaskStatus.RUNNING, TaskStatus.CANCEL_REQUESTED, TaskStatus.CANCELLED, TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.UNKNOWN_RESULT}),
    TaskStatus.RETRY_WAIT: frozenset({TaskStatus.QUEUED, TaskStatus.CANCELLED, TaskStatus.DEAD_LETTER}),
    TaskStatus.CANCEL_REQUESTED: frozenset({TaskStatus.CANCELLED, TaskStatus.SUCCEEDED, TaskStatus.UNKNOWN_RESULT}),
    TaskStatus.FAILED: frozenset({TaskStatus.QUEUED, TaskStatus.DEAD_LETTER}),
    TaskStatus.UNKNOWN_RESULT: frozenset({TaskStatus.QUEUED, TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.DEAD_LETTER}),
}

CONFIRMATION_TRANSITIONS: dict[ConfirmationStatus, frozenset[ConfirmationStatus]] = {
    ConfirmationStatus.PENDING: frozenset({ConfirmationStatus.CONSUMED, ConfirmationStatus.REJECTED, ConfirmationStatus.CANCELLED, ConfirmationStatus.EXPIRED, ConfirmationStatus.SUPERSEDED})
}

TOOL_TRANSITIONS: dict[ToolExecutionStatus, frozenset[ToolExecutionStatus]] = {
    ToolExecutionStatus.PROPOSED: frozenset({ToolExecutionStatus.AWAITING_CONFIRMATION, ToolExecutionStatus.CLAIMED, ToolExecutionStatus.CANCELLED, ToolExecutionStatus.FAILED}),
    ToolExecutionStatus.AWAITING_CONFIRMATION: frozenset({ToolExecutionStatus.CLAIMED, ToolExecutionStatus.CANCELLED, ToolExecutionStatus.FAILED}),
    ToolExecutionStatus.CLAIMED: frozenset({ToolExecutionStatus.RUNNING, ToolExecutionStatus.RETRY_WAIT, ToolExecutionStatus.CANCELLED}),
    ToolExecutionStatus.RUNNING: frozenset({ToolExecutionStatus.SUCCEEDED, ToolExecutionStatus.RETRY_WAIT, ToolExecutionStatus.FAILED, ToolExecutionStatus.CANCELLED, ToolExecutionStatus.UNKNOWN_RESULT, ToolExecutionStatus.DEAD_LETTER}),
    ToolExecutionStatus.RETRY_WAIT: frozenset({ToolExecutionStatus.CLAIMED, ToolExecutionStatus.CANCELLED, ToolExecutionStatus.DEAD_LETTER}),
    ToolExecutionStatus.UNKNOWN_RESULT: frozenset({ToolExecutionStatus.SUCCEEDED, ToolExecutionStatus.FAILED, ToolExecutionStatus.DEAD_LETTER}),
}

DELIVERY_TRANSITIONS: dict[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.PENDING: frozenset({DeliveryStatus.CLAIMED, DeliveryStatus.CANCELLED}),
    DeliveryStatus.CLAIMED: frozenset({DeliveryStatus.SENDING, DeliveryStatus.RETRY_WAIT, DeliveryStatus.CANCELLED}),
    DeliveryStatus.SENDING: frozenset({DeliveryStatus.DELIVERED, DeliveryStatus.RETRY_WAIT, DeliveryStatus.FAILED, DeliveryStatus.UNKNOWN_DELIVERY}),
    DeliveryStatus.RETRY_WAIT: frozenset({DeliveryStatus.CLAIMED, DeliveryStatus.CANCELLED, DeliveryStatus.DEAD_LETTER}),
    DeliveryStatus.UNKNOWN_DELIVERY: frozenset({DeliveryStatus.DELIVERED, DeliveryStatus.FAILED, DeliveryStatus.DEAD_LETTER}),
}


def validate_task_transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    return _validate_transition(current, target, TASK_TRANSITIONS)


def validate_confirmation_transition(current: ConfirmationStatus, target: ConfirmationStatus) -> ConfirmationStatus:
    return _validate_transition(current, target, CONFIRMATION_TRANSITIONS)


def validate_tool_transition(current: ToolExecutionStatus, target: ToolExecutionStatus) -> ToolExecutionStatus:
    return _validate_transition(current, target, TOOL_TRANSITIONS)


def validate_delivery_transition(current: DeliveryStatus, target: DeliveryStatus) -> DeliveryStatus:
    return _validate_transition(current, target, DELIVERY_TRANSITIONS)


class RuntimeEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentTaskState(RuntimeEnvelope):
    id: UUID
    user_id: UUID
    status: TaskStatus
    stage: str = Field(min_length=1, max_length=64)
    summary: str = Field(max_length=500)
    binding_epoch: int = Field(ge=1)
    claim_generation: int = Field(ge=0)
    version: int = Field(default=1, ge=1)


class TaskProgress(RuntimeEnvelope):
    task_id: UUID
    status: TaskStatus
    stage: str = Field(min_length=1, max_length=64)
    percent: int | None = Field(default=None, ge=0, le=100)
    message: str = Field(min_length=1, max_length=500)
    sequence: int = Field(ge=1)
    occurred_at: datetime | None = None


class ToolCallProposal(RuntimeEnvelope):
    tool_call_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    arguments: dict[str, Any]


__all__ = [
    "AgentTaskState",
    "ConfirmationStatus",
    "DeliveryStatus",
    "InvalidTransition",
    "TaskProgress",
    "TaskStatus",
    "ToolCallProposal",
    "ToolExecutionStatus",
    "validate_confirmation_transition",
    "validate_delivery_transition",
    "validate_task_transition",
    "validate_tool_transition",
]
