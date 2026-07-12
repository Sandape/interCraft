"""REQ-061 general coach capability adapter (T084).

Strict serialization, declared live-version decoder/upcaster, persisted
assistant bodies, conversation end, feedback and checkpoint references.
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

CAPABILITY_CODE = "general_coach"
DEFAULT_ACTION = "chat"
SUPPORTED_ACTIONS = frozenset({"chat"})
MILESTONE_CODES = ("assistant_answer",)
ADAPTER_VERSION = "general_coach.adapter.v1"

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
    "closed": TaskStatus.SUCCEEDED,
    "ended": TaskStatus.SUCCEEDED,
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
class PersistedAssistantTurn:
    """Strictly serialized assistant body for recovery / UI."""

    role: str
    body: str
    turn_index: int
    checkpoint_ref: str | None = None
    feedback: str | None = None
    truthful_failure: str | None = None


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
        raise ValueError(f"unknown general_coach domain status: {domain_status!r}")
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
    conversation_id: str,
    user_id: str,
    initial_question: str | None = None,
    behavior_version: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "conversation_id": str(conversation_id),
        "user_id": str(user_id),
        "initial_question": initial_question or "",
        "behavior_version": behavior_version,
        "adapter_version": ADAPTER_VERSION,
        "milestones": list(MILESTONE_CODES),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def serialize_assistant_body(
    *,
    body: str,
    turn_index: int,
    checkpoint_ref: str | None = None,
    feedback: str | None = None,
    truthful_failure: str | None = None,
) -> PersistedAssistantTurn:
    text = str(body or "")
    if not text and not truthful_failure:
        raise ValueError("assistant body required unless truthful_failure is set")
    return PersistedAssistantTurn(
        role="assistant",
        body=text,
        turn_index=int(turn_index),
        checkpoint_ref=checkpoint_ref,
        feedback=feedback,
        truthful_failure=truthful_failure,
    )


def persist_conversation_turns(
    turns: Sequence[PersistedAssistantTurn],
) -> list[dict[str, Any]]:
    """Strict JSON-serializable projection for recovery."""
    out: list[dict[str, Any]] = []
    for turn in turns:
        if turn.role != "assistant":
            raise ValueError("only assistant turns are persisted by this adapter")
        row: dict[str, Any] = {
            "role": turn.role,
            "body": turn.body,
            "turn_index": turn.turn_index,
        }
        if turn.checkpoint_ref:
            row["checkpoint_ref"] = turn.checkpoint_ref
        if turn.feedback is not None:
            row["feedback"] = turn.feedback
        if turn.truthful_failure:
            row["truthful_failure"] = turn.truthful_failure
            row["succeeded"] = False
        else:
            row["succeeded"] = bool(turn.body)
        out.append(row)
    return out


def attach_feedback(
    turn: PersistedAssistantTurn,
    *,
    feedback: str,
) -> PersistedAssistantTurn:
    return PersistedAssistantTurn(
        role=turn.role,
        body=turn.body,
        turn_index=turn.turn_index,
        checkpoint_ref=turn.checkpoint_ref,
        feedback=str(feedback),
        truthful_failure=turn.truthful_failure,
    )


def decide_end(*, domain_status: str) -> ControlDecision:
    status = map_domain_status(domain_status)
    if is_terminal(status):
        return ControlDecision(
            allowed=True,
            action="end",
            reason="already terminal (idempotent end)",
            target_status=status,
            metadata={"idempotent": True},
        )
    return ControlDecision(
        allowed=True,
        action="end",
        reason="conversation end accepted",
        target_status=TaskStatus.SUCCEEDED,
        metadata={"requires_persisted_assistant_body": True},
    )


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
        reason="cancel accepted before next model call",
        target_status=TaskStatus.CANCELLING,
    )


def decide_recover(*, domain_status: str, has_persisted_turns: bool) -> ControlDecision:
    raw = str(domain_status or "").strip().lower()
    status = map_domain_status(domain_status, has_result_evidence=has_persisted_turns)
    if not has_persisted_turns and raw in {"succeeded", "complete", "closed", "ended"}:
        return ControlDecision(
            allowed=False,
            action="recover",
            reason="cannot recover succeeded conversation without persisted assistant body",
            target_status=TaskStatus.RESULT_CONFIRMING,
        )
    if status in {TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.EXPIRED}:
        return ControlDecision(
            allowed=False,
            action="recover",
            reason=f"cannot recover from {status.value}",
        )
    return ControlDecision(
        allowed=True,
        action="recover",
        reason="resume from persisted checkpoint / assistant turns",
        target_status=TaskStatus.RUNNING if status is not TaskStatus.WAITING_USER else status,
        metadata={"uses_checkpoint_ref": True},
    )


def truthful_failure_turn(*, turn_index: int, reason: str) -> PersistedAssistantTurn:
    """Never fabricate a successful assistant reply on failure."""
    return serialize_assistant_body(
        body="",
        turn_index=turn_index,
        truthful_failure=str(reason),
    )


def open_result_ref(
    *,
    thread_id: str,
    milestone_code: str | None = None,
) -> ResourceRef:
    url = f"/api/v1/agents/general-coach/{thread_id}/state"
    return ResourceRef(
        kind="general_coach_result",
        url=url,
        milestone_code=milestone_code or "assistant_answer",
        owner_scoped=True,
    )


def checkpoint_ref_for(thread_id: str, *, turn_index: int) -> str:
    return f"checkpoint:general_coach:{thread_id}:turn:{int(turn_index)}"


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
        "status_url": f"/api/v1/agents/general-coach/{tid}/state",
        "detail_url": f"/api/v1/agents/general-coach/{tid}/state",
        "messages_url": f"/api/v1/agents/general-coach/{tid}/messages",
        "close_url": f"/api/v1/agents/general-coach/{tid}/close",
    }


class GeneralCoachAdapter:
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
    "GeneralCoachAdapter",
    "MILESTONE_CODES",
    "PersistedAssistantTurn",
    "ResourceRef",
    "SUPPORTED_ACTIONS",
    "attach_feedback",
    "build_input_snapshot",
    "checkpoint_ref_for",
    "decide_cancel",
    "decide_end",
    "decide_recover",
    "decode_live_artifact",
    "map_domain_status",
    "milestone_catalog",
    "open_result_ref",
    "persist_conversation_turns",
    "projection_actions",
    "runtime_links_for_thread",
    "serialize_assistant_body",
    "truthful_failure_turn",
]
