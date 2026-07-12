"""REQ-061 canonical AI task state machine and failure policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Sequence


class TaskStatus(StrEnum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    RETRY_WAIT = "retry_wait"
    CANCELLING = "cancelling"
    RESULT_CONFIRMING = "result_confirming"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset(
    {
        TaskStatus.SUCCEEDED,
        TaskStatus.PARTIALLY_SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.EXPIRED,
    }
)

_ALLOWED: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.ACCEPTED: frozenset(
        {TaskStatus.QUEUED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    ),
    TaskStatus.QUEUED: frozenset(
        {
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
            TaskStatus.FAILED,
            TaskStatus.EXPIRED,
        }
    ),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.WAITING_USER,
            TaskStatus.RETRY_WAIT,
            TaskStatus.CANCELLING,
            TaskStatus.RESULT_CONFIRMING,
            TaskStatus.SUCCEEDED,
            TaskStatus.PARTIALLY_SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.EXPIRED,
        }
    ),
    TaskStatus.WAITING_USER: frozenset(
        {
            TaskStatus.QUEUED,
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
            TaskStatus.CANCELLED,
            TaskStatus.EXPIRED,
        }
    ),
    TaskStatus.RETRY_WAIT: frozenset(
        {
            TaskStatus.QUEUED,
            TaskStatus.RUNNING,
            TaskStatus.CANCELLING,
            TaskStatus.FAILED,
        }
    ),
    TaskStatus.CANCELLING: frozenset(
        {
            TaskStatus.CANCELLED,
            TaskStatus.RESULT_CONFIRMING,
            TaskStatus.FAILED,
        }
    ),
    TaskStatus.RESULT_CONFIRMING: frozenset(
        {
            TaskStatus.SUCCEEDED,
            TaskStatus.PARTIALLY_SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.PARTIALLY_SUCCEEDED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
    TaskStatus.EXPIRED: frozenset(),
}


class InvalidTransition(ValueError):
    """Raised when a task status transition is not allowed."""


class FailurePolicy(StrEnum):
    TERMINAL = "terminal"
    RETRY = "retry"
    RECONCILE = "reconcile"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class FailureDecision:
    action: FailurePolicy
    reason: str = ""


def is_terminal(status: TaskStatus) -> bool:
    return status in TERMINAL_STATUSES


def validate_task_transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    if target is current:
        return target
    if target not in _ALLOWED.get(current, frozenset()):
        raise InvalidTransition(f"{current.value} -> {target.value}")
    return target


def available_actions_for(status: TaskStatus, *, terminal: bool) -> list[str]:
    actions: list[str] = []
    if terminal:
        if status is TaskStatus.SUCCEEDED or status is TaskStatus.PARTIALLY_SUCCEEDED:
            actions.extend(["open_result", "submit_feedback", "reexecute"])
        if status is TaskStatus.PARTIALLY_SUCCEEDED:
            actions.append("retry_failed_component")
        if status is TaskStatus.FAILED:
            actions.extend(["system_failure_retry", "reexecute", "submit_feedback", "dispute_points"])
        if status in {TaskStatus.CANCELLED, TaskStatus.EXPIRED}:
            actions.append("reexecute")
        return actions

    if status in {
        TaskStatus.ACCEPTED,
        TaskStatus.QUEUED,
        TaskStatus.RUNNING,
        TaskStatus.WAITING_USER,
        TaskStatus.RETRY_WAIT,
    }:
        actions.append("cancel")
    if status is TaskStatus.WAITING_USER:
        actions.extend(["provide_input", "confirm", "resume"])
    if status is TaskStatus.RETRY_WAIT:
        actions.append("resume")
    return actions


def progress_percent_from_milestones(
    weights: Sequence[tuple[str, int]],
    *,
    completed: Iterable[str],
) -> int:
    done = set(completed)
    total = sum(w for _, w in weights)
    if total != 10000:
        raise ValueError("milestone weights must total 10000 basis points")
    earned = sum(w for code, w in weights if code in done)
    return int(round(earned * 100 / 10000))


def validate_milestone_progress(
    *,
    previous_completed: Sequence[str],
    next_completed: Sequence[str],
) -> None:
    prev = set(previous_completed)
    nxt = set(next_completed)
    if not prev.issubset(nxt):
        raise ValueError("milestone progress must be monotonic")


def validate_execution_lineage(execution: dict) -> None:
    trigger = execution.get("trigger_kind")
    source = execution.get("source_execution_id")
    if trigger != "initial" and source is None:
        raise ValueError("non-initial execution requires source_execution_id")
    if trigger == "initial" and source is not None:
        raise ValueError("initial execution must not set source_execution_id")


def next_event_sequence(existing: Sequence[int]) -> int:
    if not existing:
        return 1
    return max(existing) + 1


def append_task_event(*, existing_sequences: Sequence[int], new_sequence: int) -> int:
    expected = next_event_sequence(existing_sequences)
    if new_sequence != expected:
        raise ValueError(f"event sequence must be contiguous; expected {expected}")
    return new_sequence


_TERMINAL_CATEGORIES = frozenset({"validation", "authz", "not_found", "conflict", "cancelled"})
_TRANSIENT = frozenset({"rate_limit", "timeout", "dependency"})


def decide_failure_policy(
    category: str,
    *,
    attempt: int,
    max_attempts: int,
    effect_started: bool = False,
) -> FailureDecision:
    if category in _TERMINAL_CATEGORIES:
        return FailureDecision(FailurePolicy.TERMINAL, reason=category)
    if category == "unknown_result":
        return FailureDecision(FailurePolicy.RECONCILE, reason="unknown_result")
    if effect_started and category in _TRANSIENT:
        return FailureDecision(FailurePolicy.RECONCILE, reason="effect_may_have_started")
    if attempt >= max_attempts:
        return FailureDecision(FailurePolicy.DEAD_LETTER, reason="attempts_exhausted")
    if category in _TRANSIENT or category == "internal":
        return FailureDecision(FailurePolicy.RETRY, reason=category)
    return FailureDecision(FailurePolicy.TERMINAL, reason=category)
