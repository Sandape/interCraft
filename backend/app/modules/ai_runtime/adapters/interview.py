"""REQ-061 interview capability adapter (T072).

Maps interview domain workflows onto canonical acceptance, round_score/report
milestones, pause checkpoints (7-day TTL), active-end choices, and degradation
authorization. Pure mapping/decision helpers — never mutates point balances or
canonical task rows directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
    append_task_event,
    available_actions_for,
    is_terminal,
    next_event_sequence,
)

CAPABILITY_CODE = "interview"
DEFAULT_ACTION = "start"
SUPPORTED_ACTIONS = frozenset({"start", "conduct"})
MILESTONE_CODES = ("round_score", "report")
ADAPTER_VERSION = "interview.adapter.v1"
PAUSE_TTL_DAYS = 7

_DOMAIN_STATUS_MAP: dict[str, TaskStatus] = {
    "pending": TaskStatus.ACCEPTED,
    "accepted": TaskStatus.ACCEPTED,
    "queued": TaskStatus.QUEUED,
    "in_progress": TaskStatus.RUNNING,
    "running": TaskStatus.RUNNING,
    "scoring": TaskStatus.RUNNING,
    "generating_question": TaskStatus.RUNNING,
    "awaiting_answer": TaskStatus.WAITING_USER,
    "paused": TaskStatus.WAITING_USER,
    "awaiting_confirmation": TaskStatus.WAITING_USER,
    "waiting_user": TaskStatus.WAITING_USER,
    "needs_guidance": TaskStatus.WAITING_USER,
    "retry_wait": TaskStatus.RETRY_WAIT,
    "cancelling": TaskStatus.CANCELLING,
    "canceling": TaskStatus.CANCELLING,
    "waiting_external": TaskStatus.RUNNING,
    "unknown_result": TaskStatus.RESULT_CONFIRMING,
    "result_confirming": TaskStatus.RESULT_CONFIRMING,
    "completed": TaskStatus.SUCCEEDED,
    "succeeded": TaskStatus.SUCCEEDED,
    "partial": TaskStatus.PARTIALLY_SUCCEEDED,
    "partial_report": TaskStatus.PARTIALLY_SUCCEEDED,
    "partial_success": TaskStatus.PARTIALLY_SUCCEEDED,
    "partially_succeeded": TaskStatus.PARTIALLY_SUCCEEDED,
    "failed": TaskStatus.FAILED,
    "dead_letter": TaskStatus.FAILED,
    "cancelled": TaskStatus.CANCELLED,
    "canceled": TaskStatus.CANCELLED,
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

_RETRYABLE_COMPONENTS = frozenset(
    {"score_delivery", "next_question", "report", "plan_fallback"}
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
class QualityGateVerdict:
    passed: bool
    code: str
    message: str
    deliverable: bool
    chargeable: bool
    metadata: dict[str, Any] = field(default_factory=dict)


def map_domain_status(
    domain_status: str,
    *,
    has_result_evidence: bool = True,
    has_failure_evidence: bool = True,
    has_task_event: bool = True,
    has_settlement_trigger: bool = True,
) -> TaskStatus:
    """Map an interview domain status onto the canonical 12-state enum."""
    key = str(domain_status or "").strip().lower()
    if key not in _DOMAIN_STATUS_MAP:
        raise ValueError(f"unknown interview domain status: {domain_status!r}")
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
    spec = get_capability_action(CAPABILITY_CODE, action)
    return spec.milestones


def build_input_snapshot(
    *,
    session_id: str,
    mode: str = "full",
    max_questions: int | None = 10,
    plan_status: str | None = None,
    service_tier: str = "standard",
    job_id: str | None = None,
    branch_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": str(session_id),
        "mode": mode,
        "max_questions": max_questions,
        "plan_status": plan_status,
        "service_tier": service_tier,
        "job_id": str(job_id) if job_id else None,
        "branch_id": str(branch_id) if branch_id else None,
        "adapter_version": ADAPTER_VERSION,
        "milestones": list(MILESTONE_CODES),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def build_policy_snapshot(
    *,
    allow_degrade: bool = False,
    pause_ttl_days: int = PAUSE_TTL_DAYS,
    score_before_next_question: bool = True,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "allow_degrade": bool(allow_degrade),
        "pause_ttl_days": int(pause_ttl_days),
        "score_before_next_question": bool(score_before_next_question),
        "adapter_version": ADAPTER_VERSION,
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def evaluate_quality_gate(
    *,
    milestone_code: str,
    result_payload: Mapping[str, Any] | None,
) -> QualityGateVerdict:
    code = str(milestone_code)
    if code not in MILESTONE_CODES:
        return QualityGateVerdict(
            passed=False,
            code="UNKNOWN_MILESTONE",
            message=f"unknown milestone {code}",
            deliverable=False,
            chargeable=False,
        )
    if not result_payload:
        return QualityGateVerdict(
            passed=False,
            code="MISSING_RESULT",
            message="no delivery evidence",
            deliverable=False,
            chargeable=False,
        )

    if code == "round_score":
        score = result_payload.get("score")
        if score is None:
            return QualityGateVerdict(
                passed=False,
                code="SCORE_INCOMPLETE",
                message="round_score requires numeric score",
                deliverable=False,
                chargeable=False,
            )
        return QualityGateVerdict(
            passed=True,
            code="ROUND_SCORE_OK",
            message="round score evidence present",
            deliverable=True,
            chargeable=True,
            metadata={
                "round_no": result_payload.get("round_no")
                or result_payload.get("question_no"),
            },
        )

    # report milestone
    overall = result_payload.get("overall_score")
    per_q = result_payload.get("per_question_score")
    if overall is None and not per_q:
        return QualityGateVerdict(
            passed=False,
            code="REPORT_INCOMPLETE",
            message="report lacks overall_score or per_question_score",
            deliverable=False,
            chargeable=False,
        )
    partial = bool(result_payload.get("partial"))
    return QualityGateVerdict(
        passed=True,
        code="REPORT_PARTIAL" if partial else "REPORT_OK",
        message="report evidence present",
        deliverable=True,
        chargeable=True,
        metadata={"partial": partial},
    )


def open_result_ref(
    *,
    session_id: str,
    milestone_code: str | None = None,
    round_no: int | None = None,
) -> ResourceRef:
    sid = str(session_id)
    if milestone_code == "round_score":
        rn = int(round_no or 0)
        url = f"/api/v1/interview-sessions/{sid}/rounds/{rn}/score"
    elif milestone_code == "report":
        url = f"/api/v1/interview-sessions/{sid}/report"
    else:
        url = f"/api/v1/interview-sessions/{sid}"
    return ResourceRef(
        kind="interview_result",
        url=url,
        milestone_code=milestone_code,
        owner_scoped=True,
    )


def build_score_first_event_sequence(
    *,
    session_id: str,
    round_no: int,
    score_payload: Mapping[str, Any],
    next_question_payload: Mapping[str, Any] | None = None,
    base_sequence: int = 0,
) -> list[dict[str, Any]]:
    """Ordered WS/domain events: score delivery then next question."""
    seq = int(base_sequence)
    events: list[dict[str, Any]] = []
    seq += 1
    events.append(
        {
            "type": "round.score",
            "session_id": str(session_id),
            "sequence": seq,
            "round_no": int(round_no),
            "payload": dict(score_payload),
        }
    )
    if next_question_payload is not None:
        seq += 1
        events.append(
            {
                "type": "round.next_question",
                "session_id": str(session_id),
                "sequence": seq,
                "round_no": int(round_no) + 1,
                "payload": dict(next_question_payload),
            }
        )
    return events


def next_reconnect_sequence(existing: Sequence[int]) -> int:
    return next_event_sequence(existing)


def append_reconnect_event(
    *,
    existing_sequences: Sequence[int],
    new_sequence: int,
) -> int:
    """Reject duplicates and gaps — reconnect must be contiguous."""
    if new_sequence in set(existing_sequences):
        raise ValueError(f"duplicate reconnect sequence {new_sequence}")
    return append_task_event(
        existing_sequences=existing_sequences,
        new_sequence=new_sequence,
    )


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def decide_pause(
    *,
    domain_status: str,
    now: datetime | None = None,
    pause_ttl_days: int = PAUSE_TTL_DAYS,
) -> ControlDecision:
    status = map_domain_status(domain_status)
    if is_terminal(status):
        return ControlDecision(
            allowed=False,
            action="pause",
            reason=f"terminal status {status.value} cannot pause",
        )
    if status not in {TaskStatus.RUNNING, TaskStatus.WAITING_USER}:
        return ControlDecision(
            allowed=False,
            action="pause",
            reason=f"pause not available in {status.value}",
        )
    ts = now or datetime.now(timezone.utc)
    deadline = ts + timedelta(days=int(pause_ttl_days))
    return ControlDecision(
        allowed=True,
        action="pause",
        reason="pause accepted; stop question generation and point spend",
        target_status=TaskStatus.WAITING_USER,
        metadata={
            "pause_deadline": _iso(deadline),
            "pause_ttl_days": int(pause_ttl_days),
            "domain_status": "paused",
        },
    )


def decide_resume(
    *,
    domain_status: str,
    pause_deadline: str | datetime | None,
    now: datetime | None = None,
) -> ControlDecision:
    status = map_domain_status(domain_status)
    if status is not TaskStatus.WAITING_USER and domain_status not in {
        "paused",
        "awaiting_answer",
        "waiting_user",
    }:
        return ControlDecision(
            allowed=False,
            action="resume",
            reason=f"resume not available in {status.value}",
            metadata={"reason_code": "NOT_PAUSED"},
        )
    ts = now or datetime.now(timezone.utc)
    if pause_deadline is None:
        return ControlDecision(
            allowed=False,
            action="resume",
            reason="pause deadline missing",
            metadata={"reason_code": "MISSING_DEADLINE"},
        )
    if isinstance(pause_deadline, str):
        deadline = datetime.fromisoformat(pause_deadline.replace("Z", "+00:00"))
    else:
        deadline = pause_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if ts > deadline:
        return ControlDecision(
            allowed=False,
            action="resume",
            reason="pause window expired",
            target_status=TaskStatus.EXPIRED,
            metadata={"reason_code": "PAUSE_EXPIRED", "pause_deadline": _iso(deadline)},
        )
    return ControlDecision(
        allowed=True,
        action="resume",
        reason="resume within pause window",
        target_status=TaskStatus.RUNNING,
        metadata={"pause_deadline": _iso(deadline)},
    )


def decide_degradation(
    *,
    plan_status: str,
    user_consented: bool,
    allow_degrade_on_quote: bool,
) -> ControlDecision:
    if str(plan_status).lower() != "failed":
        return ControlDecision(
            allowed=False,
            action="degrade",
            reason="degradation only applies after plan failure",
            metadata={"reason_code": "PLAN_NOT_FAILED"},
        )
    if not allow_degrade_on_quote:
        return ControlDecision(
            allowed=False,
            action="degrade",
            reason="quote did not authorize degradation",
            metadata={"reason_code": "DEGRADE_NOT_QUOTED"},
        )
    if not user_consented:
        return ControlDecision(
            allowed=False,
            action="degrade",
            reason="explicit user consent required",
            metadata={"reason_code": "CONSENT_REQUIRED"},
        )
    return ControlDecision(
        allowed=True,
        action="degrade",
        reason="user consented to degraded interview without ready plan",
        target_status=TaskStatus.RUNNING,
        metadata={
            "settlement_tier": "standard",
            "plan_status": "degraded",
            "limitation": "interview continues without personalized plan",
        },
    )


def decide_active_end(
    *,
    domain_status: str,
    scored_rounds: int,
    generate_partial_report: bool | None,
) -> ControlDecision:
    status = map_domain_status(domain_status)
    if is_terminal(status):
        return ControlDecision(
            allowed=False,
            action="active_end",
            reason=f"already terminal ({status.value})",
        )
    if int(scored_rounds) < 1:
        return ControlDecision(
            allowed=False,
            action="active_end",
            reason="no scored rounds to settle",
            metadata={"reason_code": "NO_SCORED_ROUNDS"},
        )
    if generate_partial_report is None:
        return ControlDecision(
            allowed=True,
            action="active_end",
            reason="awaiting partial-report choice",
            target_status=TaskStatus.WAITING_USER,
            metadata={
                "requires_partial_report_choice": True,
                "scored_rounds": int(scored_rounds),
            },
        )
    chargeable: list[str] = ["round_score"]
    if generate_partial_report:
        chargeable.append("report")
    return ControlDecision(
        allowed=True,
        action="active_end",
        reason="active end with milestone settlement",
        target_status=TaskStatus.PARTIALLY_SUCCEEDED,
        metadata={
            "requires_partial_report_choice": False,
            "generate_partial_report": bool(generate_partial_report),
            "scored_rounds": int(scored_rounds),
            "chargeable_milestones": tuple(chargeable),
        },
    )


def decide_cancel(
    *,
    domain_status: str,
    cancel_acknowledged: bool = False,
) -> ControlDecision:
    status = map_domain_status(
        domain_status,
        has_result_evidence=True,
        has_failure_evidence=True,
        has_task_event=True,
        has_settlement_trigger=True,
    )
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
        reason="cancel accepted; durable before provider work",
        target_status=TaskStatus.CANCELLING,
        metadata={"safe_points": ("before_provider", "before_publish", "before_domain_write")},
    )


def decide_retry(
    *,
    domain_status: str,
    component: str | None = None,
) -> ControlDecision:
    status = map_domain_status(domain_status)
    target = component or "score_delivery"
    if target not in _RETRYABLE_COMPONENTS:
        return ControlDecision(
            allowed=False,
            action="retry_failed_component",
            reason=f"unknown retryable component {target}",
        )
    if status in {
        TaskStatus.FAILED,
        TaskStatus.PARTIALLY_SUCCEEDED,
        TaskStatus.RETRY_WAIT,
        TaskStatus.RESULT_CONFIRMING,
    }:
        return ControlDecision(
            allowed=True,
            action="retry_failed_component",
            reason=f"retry component {target} creates new execution lineage",
            target_status=TaskStatus.QUEUED,
            metadata={
                "component": target,
                "new_execution_required": True,
                "settle_milestone_once": True,
                "evidence_gated": True,
            },
        )
    # Also allow component retry while running if prior attempt failed soft
    if status is TaskStatus.RUNNING and target in _RETRYABLE_COMPONENTS:
        return ControlDecision(
            allowed=True,
            action="retry_failed_component",
            reason=f"independent retry of {target}",
            target_status=TaskStatus.RUNNING,
            metadata={
                "component": target,
                "new_execution_required": True,
                "settle_milestone_once": True,
                "evidence_gated": True,
            },
        )
    return ControlDecision(
        allowed=False,
        action="retry_failed_component",
        reason=f"retry not available in {status.value}",
    )


def build_pause_checkpoint(
    *,
    session_id: str,
    round_no: int,
    scores: Sequence[Mapping[str, Any]],
    schema_version: str = "2",
    extra_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not str(session_id).strip():
        raise ValueError("session_id required for pause checkpoint")
    state: dict[str, Any] = {
        "round": int(round_no),
        "scores": [dict(s) for s in scores],
        "session_id": str(session_id),
    }
    if extra_state:
        state.update(dict(extra_state))
    return {
        "schema_version": str(schema_version),
        "kind": "pause",
        "node": "pause",
        "capability": CAPABILITY_CODE,
        "state": state,
    }


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
    actions = list(available_actions_for(status, terminal=is_terminal(status)))
    # Interview-specific controls surfaced alongside canonical actions.
    key = str(domain_status or "").strip().lower()
    if key in {"in_progress", "running", "awaiting_answer", "scoring"}:
        if "pause" not in actions:
            actions.append("pause")
        if "end" not in actions:
            actions.append("end")
    if key == "paused" and "resume" not in actions:
        actions.append("resume")
    return actions


class InterviewAdapter:
    """CapabilityAdapter for interview start/conduct."""

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
    "MILESTONE_CODES",
    "PAUSE_TTL_DAYS",
    "QualityGateVerdict",
    "ResourceRef",
    "InterviewAdapter",
    "SUPPORTED_ACTIONS",
    "append_reconnect_event",
    "build_input_snapshot",
    "build_pause_checkpoint",
    "build_policy_snapshot",
    "build_score_first_event_sequence",
    "decide_active_end",
    "decide_cancel",
    "decide_degradation",
    "decide_pause",
    "decide_resume",
    "decide_retry",
    "decode_live_artifact",
    "evaluate_quality_gate",
    "map_domain_status",
    "milestone_catalog",
    "next_reconnect_sequence",
    "open_result_ref",
    "projection_actions",
]
