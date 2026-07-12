"""REQ-061 error coach capability adapter (T085).

Strict serialization, declared live-version decoder/upcaster, per-round
score/hint/correct-count milestones and resumable state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.modules.ai_runtime.adapters.contracts import (
    AcceptanceEnvelope,
    CapabilityActionSpec,
    MilestoneSpec,
    validate_acceptance_envelope,
)
from app.modules.ai_runtime.adapters.registry import (
    build_acceptance_envelope as registry_build_envelope,
    get_capability_action,
)
from app.modules.ai_runtime.compatibility import (
    CompatibilityDecision,
    decode_or_quarantine,
)
from app.modules.ai_runtime.state_machine import (
    TaskStatus,
    available_actions_for,
    is_terminal,
)

CAPABILITY_CODE = "error_coach"
DEFAULT_ACTION = "drill"
SUPPORTED_ACTIONS = frozenset({"drill"})
MILESTONE_CODES = ("scored_round",)
ADAPTER_VERSION = "error_coach.adapter.v1"
TARGET_CORRECT_COUNT = 3

_DOMAIN_STATUS_MAP: dict[str, TaskStatus] = {
    "pending": TaskStatus.ACCEPTED,
    "accepted": TaskStatus.ACCEPTED,
    "queued": TaskStatus.QUEUED,
    "running": TaskStatus.RUNNING,
    "awaiting_confirmation": TaskStatus.WAITING_USER,
    "waiting_user": TaskStatus.WAITING_USER,
    "retry_wait": TaskStatus.RETRY_WAIT,
    "cancelling": TaskStatus.CANCELLING,
    "canceling": TaskStatus.CANCELLING,
    "unknown_result": TaskStatus.RESULT_CONFIRMING,
    "result_confirming": TaskStatus.RESULT_CONFIRMING,
    "succeeded": TaskStatus.SUCCEEDED,
    "complete": TaskStatus.SUCCEEDED,
    "failed": TaskStatus.FAILED,
    "dead_letter": TaskStatus.FAILED,
    "cancelled": TaskStatus.CANCELLED,
    "canceled": TaskStatus.CANCELLED,
    "aborted": TaskStatus.CANCELLED,
    "expired": TaskStatus.EXPIRED,
}

_CANCELABLE = frozenset(
    {
        TaskStatus.ACCEPTED,
        TaskStatus.QUEUED,
        TaskStatus.RUNNING,
        TaskStatus.WAITING_USER,
        TaskStatus.RETRY_WAIT,
    }
)


@dataclass(frozen=True, slots=True)
class ControlDecision:
    allowed: bool
    action: str
    reason: str
    target_status: TaskStatus | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResourceRef:
    kind: str
    url: str
    milestone_code: str | None = None
    owner_scoped: bool = True


@dataclass(frozen=True, slots=True)
class ScoredRound:
    """One scored error-coach round (milestone delivery unit)."""

    round_index: int
    score: int
    hint_level: str | None
    hint_content: str | None
    correct_count: int
    feedback: str | None = None
    checkpoint_ref: str | None = None
    truthful_failure: str | None = None

    @property
    def passed(self) -> bool:
        return self.truthful_failure is None and self.score >= 8


def map_domain_status(
    domain_status: str,
    *,
    has_result_evidence: bool = True,
    has_failure_evidence: bool = True,
    has_task_event: bool = True,
    has_settlement_trigger: bool = True,
) -> TaskStatus:
    key = str(domain_status or "").strip().lower()
    if key not in _DOMAIN_STATUS_MAP:
        raise ValueError(f"unknown error_coach domain status: {domain_status!r}")
    mapped = _DOMAIN_STATUS_MAP[key]
    if not is_terminal(mapped):
        return mapped
    evidence_ok = has_task_event and has_settlement_trigger
    if mapped in {TaskStatus.SUCCEEDED, TaskStatus.PARTIALLY_SUCCEEDED}:
        evidence_ok = evidence_ok and has_result_evidence
    if mapped is TaskStatus.FAILED:
        evidence_ok = evidence_ok and has_failure_evidence
    if not evidence_ok:
        return TaskStatus.RESULT_CONFIRMING
    return mapped


def milestone_catalog(action: str = DEFAULT_ACTION) -> tuple[MilestoneSpec, ...]:
    return get_capability_action(CAPABILITY_CODE, action).milestones


def build_input_snapshot(
    *,
    thread_id: str,
    error_question_id: str,
    user_id: str,
    behavior_version: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "thread_id": str(thread_id),
        "error_question_id": str(error_question_id),
        "user_id": str(user_id),
        "behavior_version": behavior_version,
        "adapter_version": ADAPTER_VERSION,
        "milestones": list(MILESTONE_CODES),
        "target_correct_count": TARGET_CORRECT_COUNT,
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def serialize_scored_round(
    *,
    round_index: int,
    score: int | None,
    hint_level: str | None,
    hint_content: str | None,
    correct_count: int,
    feedback: str | None = None,
    checkpoint_ref: str | None = None,
    truthful_failure: str | None = None,
) -> ScoredRound:
    if truthful_failure:
        return ScoredRound(
            round_index=int(round_index),
            score=0,
            hint_level=hint_level,
            hint_content=hint_content,
            correct_count=int(correct_count),
            feedback=feedback,
            checkpoint_ref=checkpoint_ref,
            truthful_failure=str(truthful_failure),
        )
    if score is None:
        raise ValueError("score required for scored_round milestone unless truthful_failure")
    return ScoredRound(
        round_index=int(round_index),
        score=int(score),
        hint_level=hint_level,
        hint_content=hint_content,
        correct_count=int(correct_count),
        feedback=feedback,
        checkpoint_ref=checkpoint_ref,
        truthful_failure=None,
    )


def persist_scored_rounds(rounds: Sequence[ScoredRound]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rounds:
        item: dict[str, Any] = {
            "milestone": "scored_round",
            "round_index": row.round_index,
            "score": row.score,
            "hint_level": row.hint_level,
            "hint_content": row.hint_content,
            "correct_count": row.correct_count,
            "passed": row.passed,
        }
        if row.feedback is not None:
            item["feedback"] = row.feedback
        if row.checkpoint_ref:
            item["checkpoint_ref"] = row.checkpoint_ref
        if row.truthful_failure:
            item["truthful_failure"] = row.truthful_failure
            item["succeeded"] = False
        else:
            item["succeeded"] = True
        out.append(item)
    return out


def session_complete(*, correct_count: int, aborted: bool = False) -> bool:
    if aborted:
        return True
    return int(correct_count) >= TARGET_CORRECT_COUNT


def resumable_state(
    *,
    thread_id: str,
    correct_count: int,
    attempt_count: int,
    current_hint_level: str | None,
    rounds: Sequence[ScoredRound],
) -> dict[str, Any]:
    return {
        "thread_id": str(thread_id),
        "correct_count": int(correct_count),
        "attempt_count": int(attempt_count),
        "current_hint_level": current_hint_level,
        "rounds": persist_scored_rounds(rounds),
        "complete": session_complete(correct_count=correct_count),
        "adapter_version": ADAPTER_VERSION,
    }


def decide_cancel(*, domain_status: str, cancel_acknowledged: bool = False) -> ControlDecision:
    status = map_domain_status(domain_status)
    if is_terminal(status):
        return ControlDecision(
            allowed=False,
            action="cancel",
            reason=f"terminal status {status.value} cannot cancel",
        )
    if status is TaskStatus.CANCELLING:
        return ControlDecision(
            allowed=True,
            action="cancel",
            reason="cancel already in progress (idempotent)",
            target_status=TaskStatus.CANCELLED if cancel_acknowledged else TaskStatus.CANCELLING,
            metadata={"idempotent": True},
        )
    if status not in _CANCELABLE:
        return ControlDecision(
            allowed=False,
            action="cancel",
            reason=f"cancel not available in {status.value}",
        )
    return ControlDecision(
        allowed=True,
        action="cancel",
        reason="cancel/abort accepted before next evaluate",
        target_status=TaskStatus.CANCELLING,
    )


def decide_resume(
    *,
    domain_status: str,
    correct_count: int,
    has_checkpoint: bool,
) -> ControlDecision:
    status = map_domain_status(domain_status)
    if session_complete(correct_count=correct_count):
        return ControlDecision(
            allowed=False,
            action="resume",
            reason="session already complete",
            target_status=TaskStatus.SUCCEEDED,
        )
    if not has_checkpoint:
        return ControlDecision(
            allowed=False,
            action="resume",
            reason="missing resumable checkpoint",
            target_status=TaskStatus.RESULT_CONFIRMING,
        )
    if status in {TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.EXPIRED}:
        return ControlDecision(
            allowed=False,
            action="resume",
            reason=f"cannot resume from {status.value}",
        )
    return ControlDecision(
        allowed=True,
        action="resume",
        reason="resume scored round from checkpoint",
        target_status=TaskStatus.WAITING_USER,
        metadata={"correct_count": int(correct_count)},
    )


def open_result_ref(
    *,
    thread_id: str,
    milestone_code: str | None = None,
) -> ResourceRef:
    return ResourceRef(
        kind="error_coach_result",
        url=f"/api/v1/agents/error-coach/{thread_id}/state",
        milestone_code=milestone_code or "scored_round",
        owner_scoped=True,
    )


def checkpoint_ref_for(thread_id: str, *, round_index: int) -> str:
    return f"checkpoint:error_coach:{thread_id}:round:{int(round_index)}"


def decode_live_artifact(
    *,
    kind: str,
    version: str,
    payload: Mapping[str, Any],
) -> CompatibilityDecision:
    if kind not in {"checkpoint", "job", "interrupt"}:
        raise ValueError(f"unsupported artifact kind: {kind}")
    return decode_or_quarantine(
        kind,  # type: ignore[arg-type]
        payload,
        version=version,
        capability=CAPABILITY_CODE,
    )


def projection_actions(domain_status: str) -> list[str]:
    status = map_domain_status(domain_status)
    return available_actions_for(status, terminal=is_terminal(status))


def runtime_links_for_thread(thread_id: str) -> dict[str, str]:
    tid = str(thread_id)
    return {
        "status_url": f"/api/v1/agents/error-coach/{tid}/state",
        "detail_url": f"/api/v1/agents/error-coach/{tid}/state",
        "messages_url": f"/api/v1/agents/error-coach/{tid}/messages",
        "abort_url": f"/api/v1/agents/error-coach/{tid}/abort",
    }


class ErrorCoachAdapter:
    def __init__(self, action: str = DEFAULT_ACTION) -> None:
        if action not in SUPPORTED_ACTIONS:
            raise ValueError(f"unsupported action: {action}")
        self.action = action
        self.spec: CapabilityActionSpec = get_capability_action(CAPABILITY_CODE, action)

    def build_acceptance_envelope(
        self,
        *,
        service_tier: str,
        input_snapshot_ref: str,
        allow_degrade: bool,
        input_payload: dict[str, Any] | None = None,
    ) -> AcceptanceEnvelope:
        envelope = registry_build_envelope(
            capability=CAPABILITY_CODE,
            action=self.action,
            service_tier=service_tier,
            input_snapshot_ref=input_snapshot_ref,
            allow_degrade=allow_degrade,
            input_payload=input_payload,
        )
        codes = tuple(m.code for m in envelope.milestones)
        if set(codes) != set(MILESTONE_CODES):
            raise ValueError(f"unexpected milestones {codes}, expected {MILESTONE_CODES}")
        validate_acceptance_envelope(envelope)
        return envelope


__all__ = [
    "ADAPTER_VERSION",
    "CAPABILITY_CODE",
    "ControlDecision",
    "DEFAULT_ACTION",
    "ErrorCoachAdapter",
    "MILESTONE_CODES",
    "ResourceRef",
    "SUPPORTED_ACTIONS",
    "ScoredRound",
    "TARGET_CORRECT_COUNT",
    "build_input_snapshot",
    "checkpoint_ref_for",
    "decide_cancel",
    "decide_resume",
    "decode_live_artifact",
    "map_domain_status",
    "milestone_catalog",
    "open_result_ref",
    "persist_scored_rounds",
    "projection_actions",
    "resumable_state",
    "runtime_links_for_thread",
    "serialize_scored_round",
    "session_complete",
]
