"""REQ-061 ability-insight capability adapter (T094).

Separates deterministic profile score updates from the AI insight milestone.
Deterministic scores never depend on insight success and are never settled as
AI points when the trigger is an interview (included in interview fee).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

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
from app.modules.ai_runtime.state_machine import (
    TaskStatus,
    available_actions_for,
    is_terminal,
)

CAPABILITY_CODE = "ability_insight"
DEFAULT_ACTION = "diagnose"
SUPPORTED_ACTIONS = frozenset({"diagnose"})
MILESTONE_CODES = ("ai_insight",)
ADAPTER_VERSION = "ability_insight.adapter.v1"

# Interview-triggered insight is included in interview points (FR-064).
INCLUDED_IN_INTERVIEW_MAX_POINTS = 0

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
    "waiting_external": TaskStatus.RUNNING,
    "unknown_result": TaskStatus.RESULT_CONFIRMING,
    "result_confirming": TaskStatus.RESULT_CONFIRMING,
    "complete": TaskStatus.SUCCEEDED,
    "succeeded": TaskStatus.SUCCEEDED,
    "partial": TaskStatus.PARTIALLY_SUCCEEDED,
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


@dataclass(frozen=True, slots=True)
class ScoreInsightSeparation:
    """Projection proving deterministic score is independent of insight task."""

    score_status: str
    score_source: str
    score_available: bool
    insight_status: str
    insight_task_id: str | None
    insight_failed: bool
    score_rolled_back_on_insight_failure: bool = False


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
        raise ValueError(f"unknown ability_insight domain status: {domain_status!r}")
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
    user_id: str,
    session_id: str | None = None,
    interview_id: str | None = None,
    score_snapshot_ref: str | None = None,
    trigger: str = "interview",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Input snapshot for insight acceptance. Score refs are read-only evidence."""
    payload: dict[str, Any] = {
        "user_id": str(user_id),
        "session_id": str(session_id) if session_id else None,
        "interview_id": str(interview_id) if interview_id else None,
        "score_snapshot_ref": score_snapshot_ref,
        "trigger": trigger,
        "adapter_version": ADAPTER_VERSION,
        "milestones": list(MILESTONE_CODES),
        # Deterministic score is never an AI milestone.
        "deterministic_score_in_milestones": False,
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def separate_score_and_insight(
    *,
    score_source: str,
    score_verified: bool,
    insight_domain_status: str,
    insight_task_id: str | None = None,
) -> ScoreInsightSeparation:
    """Prove FR-040: insight failure must not roll back a verified score."""
    insight_status = map_domain_status(
        insight_domain_status,
        has_result_evidence=insight_domain_status
        in {"complete", "succeeded", "partial", "partial_success"},
        has_failure_evidence=insight_domain_status in {"failed", "dead_letter"},
    )
    insight_failed = insight_status is TaskStatus.FAILED
    return ScoreInsightSeparation(
        score_status="verified" if score_verified else "pending",
        score_source=score_source,
        score_available=bool(score_verified),
        insight_status=insight_status.value,
        insight_task_id=insight_task_id,
        insight_failed=insight_failed,
        score_rolled_back_on_insight_failure=False,
    )


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
            message="no insight delivery evidence",
            deliverable=False,
            chargeable=False,
        )
    body = result_payload.get("insight_text") or result_payload.get("insights")
    if not body:
        return QualityGateVerdict(
            passed=False,
            code="INSIGHT_INCOMPLETE",
            message="insight body missing",
            deliverable=False,
            chargeable=False,
        )
    return QualityGateVerdict(
        passed=True,
        code="INSIGHT_OK",
        message="insight evidence present",
        deliverable=True,
        # Interview-triggered: never charge; standalone may charge via quote.
        chargeable=result_payload.get("billing_mode") != "included_in_interview",
    )


def open_result_ref(
    *,
    user_id: str,
    insight_id: str | None = None,
    milestone_code: str | None = None,
) -> ResourceRef:
    if insight_id:
        url = f"/api/v1/ability-profile/insights/{insight_id}"
    else:
        url = f"/api/v1/ability-profile/dashboard?user={user_id}"
    return ResourceRef(
        kind="ability_insight_result",
        url=url,
        milestone_code=milestone_code or "ai_insight",
        owner_scoped=True,
    )


def decide_cancel(
    *,
    domain_status: str,
    cancel_acknowledged: bool = False,
) -> ControlDecision:
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
        reason="cancel accepted; score remains untouched",
        target_status=TaskStatus.CANCELLING,
        metadata={
            "safe_points": ("before_provider", "before_publish", "before_domain_write"),
            "preserves_deterministic_score": True,
        },
    )


def decide_retry(*, domain_status: str) -> ControlDecision:
    status = map_domain_status(domain_status)
    if status in {TaskStatus.FAILED, TaskStatus.RETRY_WAIT}:
        return ControlDecision(
            allowed=True,
            action="system_failure_retry",
            reason="retry insight only; deterministic score unchanged",
            target_status=TaskStatus.QUEUED,
            metadata={
                "new_execution_required": True,
                "preserves_deterministic_score": True,
            },
        )
    return ControlDecision(
        allowed=False,
        action="system_failure_retry",
        reason=f"retry not available in {status.value}",
    )


def projection_actions(domain_status: str) -> list[str]:
    status = map_domain_status(domain_status)
    return available_actions_for(status, terminal=is_terminal(status))


def build_runtime_envelope(
    *,
    user_id: str,
    session_id: str,
    service_tier: str = "standard",
    trigger: str = "interview",
) -> AcceptanceEnvelope:
    """Convenience for workers: build a validated acceptance envelope."""
    adapter = AbilityInsightAdapter()
    snap = build_input_snapshot(
        user_id=user_id,
        session_id=session_id,
        trigger=trigger,
    )
    return adapter.build_acceptance_envelope(
        service_tier=service_tier,
        input_snapshot_ref=f"ability-insight:{user_id}:{session_id}",
        allow_degrade=False,
        input_payload=snap,
        included_in_interview=trigger == "interview",
    )


class AbilityInsightAdapter:
    """CapabilityAdapter for ability_insight diagnose."""

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
        included_in_interview: bool = True,
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
        if codes != MILESTONE_CODES:
            if set(codes) != set(MILESTONE_CODES):
                raise ValueError(f"unexpected milestones {codes}, expected {MILESTONE_CODES}")
        metadata = dict(envelope.metadata)
        metadata["deterministic_score_independent"] = True
        if included_in_interview:
            # Zero user charge when insight is part of interview fee.
            zero_milestones = tuple(
                MilestoneSpec(
                    code=m.code,
                    label=m.label,
                    weight_basis_points=m.weight_basis_points,
                    max_points=INCLUDED_IN_INTERVIEW_MAX_POINTS,
                )
                for m in envelope.milestones
            )
            metadata["billing_mode"] = "included_in_interview"
            envelope = AcceptanceEnvelope(
                capability_code=envelope.capability_code,
                action_code=envelope.action_code,
                service_tier=envelope.service_tier,
                input_snapshot_ref=envelope.input_snapshot_ref,
                input_canonical_hash=envelope.input_canonical_hash,
                allow_degrade=envelope.allow_degrade,
                milestones=zero_milestones,
                max_points=INCLUDED_IN_INTERVIEW_MAX_POINTS,
                metadata=metadata,
            )
        else:
            metadata["billing_mode"] = "standalone"
            envelope = AcceptanceEnvelope(
                capability_code=envelope.capability_code,
                action_code=envelope.action_code,
                service_tier=envelope.service_tier,
                input_snapshot_ref=envelope.input_snapshot_ref,
                input_canonical_hash=envelope.input_canonical_hash,
                allow_degrade=envelope.allow_degrade,
                milestones=envelope.milestones,
                max_points=envelope.max_points,
                metadata=metadata,
            )
        validate_acceptance_envelope(envelope)
        return envelope


__all__ = [
    "ADAPTER_VERSION",
    "CAPABILITY_CODE",
    "ControlDecision",
    "DEFAULT_ACTION",
    "INCLUDED_IN_INTERVIEW_MAX_POINTS",
    "MILESTONE_CODES",
    "QualityGateVerdict",
    "ResourceRef",
    "ScoreInsightSeparation",
    "AbilityInsightAdapter",
    "SUPPORTED_ACTIONS",
    "build_input_snapshot",
    "build_runtime_envelope",
    "decide_cancel",
    "decide_retry",
    "evaluate_quality_gate",
    "map_domain_status",
    "milestone_catalog",
    "open_result_ref",
    "projection_actions",
    "separate_score_and_insight",
]
