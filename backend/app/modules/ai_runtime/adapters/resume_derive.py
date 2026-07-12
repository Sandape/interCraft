"""REQ-061 resume derive capability adapter (T063).

Maps derive domain runs onto canonical milestones (draft / job_analysis /
suggestions), cancel/retry decisions, and partial settlement evidence.
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
    progress_percent_from_milestones,
)

CAPABILITY_CODE = "resume_derive"
DEFAULT_ACTION = "derive"
SUPPORTED_ACTIONS = frozenset({"derive"})
MILESTONE_CODES = ("draft", "job_analysis", "suggestions")
ADAPTER_VERSION = "resume_derive.adapter.v1"

# Domain component_status keys → canonical milestone codes.
COMPONENT_TO_MILESTONE: dict[str, str] = {
    "derived_resume": "draft",
    "draft": "draft",
    "analysis": "job_analysis",
    "job_analysis": "job_analysis",
    "suggestions": "suggestions",
}

_DOMAIN_STATUS_MAP: dict[str, TaskStatus] = {
    "pending": TaskStatus.ACCEPTED,
    "accepted": TaskStatus.ACCEPTED,
    "queued": TaskStatus.QUEUED,
    "running": TaskStatus.RUNNING,
    "awaiting_confirmation": TaskStatus.WAITING_USER,
    "waiting_user": TaskStatus.WAITING_USER,
    "needs_guidance": TaskStatus.WAITING_USER,
    "retry_wait": TaskStatus.RETRY_WAIT,
    "cancelling": TaskStatus.CANCELLING,
    "canceling": TaskStatus.CANCELLING,
    "waiting_external": TaskStatus.RUNNING,
    "unknown_result": TaskStatus.RESULT_CONFIRMING,
    "result_confirming": TaskStatus.RESULT_CONFIRMING,
    "succeeded": TaskStatus.SUCCEEDED,
    "complete": TaskStatus.SUCCEEDED,
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

_DELIVERED_COMPONENT = frozenset({"succeeded", "complete", "delivered", "done"})
_FAILED_COMPONENT = frozenset({"failed", "error", "skipped"})


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
class PartialSettlementEvidence:
    delivered_milestones: tuple[str, ...]
    failed_milestones: tuple[str, ...]
    pending_milestones: tuple[str, ...]
    chargeable_milestone_codes: tuple[str, ...]
    canonical_status: TaskStatus
    progress_percent: int


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
        raise ValueError(f"unknown resume_derive domain status: {domain_status!r}")
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


def normalize_component_status(
    component_status: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Map domain component keys onto canonical milestone codes."""
    out: dict[str, str] = {code: "pending" for code in MILESTONE_CODES}
    for raw_key, raw_val in dict(component_status or {}).items():
        milestone = COMPONENT_TO_MILESTONE.get(str(raw_key))
        if milestone is None:
            continue
        out[milestone] = str(raw_val or "pending").lower()
    return out


def delivered_milestones(component_status: Mapping[str, Any] | None) -> tuple[str, ...]:
    normalized = normalize_component_status(component_status)
    return tuple(
        code for code in MILESTONE_CODES if normalized.get(code) in _DELIVERED_COMPONENT
    )


def failed_milestones(component_status: Mapping[str, Any] | None) -> tuple[str, ...]:
    normalized = normalize_component_status(component_status)
    return tuple(
        code for code in MILESTONE_CODES if normalized.get(code) in _FAILED_COMPONENT
    )


def build_partial_settlement_evidence(
    *,
    domain_status: str,
    component_status: Mapping[str, Any] | None,
    milestone_weights: Sequence[tuple[str, int]] | None = None,
) -> PartialSettlementEvidence:
    """Evidence for partial settlement — only delivered milestones are chargeable."""
    delivered = delivered_milestones(component_status)
    failed = failed_milestones(component_status)
    pending = tuple(
        code
        for code in MILESTONE_CODES
        if code not in delivered and code not in failed
    )
    status = map_domain_status(domain_status)
    if delivered and (failed or pending) and status is TaskStatus.SUCCEEDED:
        status = TaskStatus.PARTIALLY_SUCCEEDED
    if delivered and failed and domain_status in {"partial", "partial_success", "failed"}:
        status = TaskStatus.PARTIALLY_SUCCEEDED if delivered else status

    weights = milestone_weights
    if weights is None:
        weights = tuple((m.code, m.weight_basis_points) for m in milestone_catalog())
    progress = progress_percent_from_milestones(weights, completed=delivered)
    return PartialSettlementEvidence(
        delivered_milestones=delivered,
        failed_milestones=failed,
        pending_milestones=pending,
        chargeable_milestone_codes=delivered,
        canonical_status=status,
        progress_percent=progress,
    )


def build_input_snapshot(
    *,
    root_resume_id: str,
    root_version: int,
    job_id: str,
    target_page_count: int,
    template_id: str,
    root_hash: str | None = None,
    jd_hash: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "root_resume_id": str(root_resume_id),
        "root_version": int(root_version),
        "job_id": str(job_id),
        "target_page_count": int(target_page_count),
        "template_id": template_id,
        "root_hash": root_hash,
        "jd_hash": jd_hash,
        "adapter_version": ADAPTER_VERSION,
        "milestones": list(MILESTONE_CODES),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def open_result_ref(
    *,
    run_id: str,
    milestone_code: str | None = None,
    derived_resume_id: str | None = None,
) -> ResourceRef:
    if milestone_code == "draft" and derived_resume_id:
        url = f"/api/v1/resumes/{derived_resume_id}"
    elif milestone_code == "job_analysis":
        url = f"/api/v1/resumes/derive-runs/{run_id}/analysis"
    elif milestone_code == "suggestions":
        url = f"/api/v1/resumes/derive-runs/{run_id}/suggestions"
    else:
        url = f"/api/v1/resumes/derive-runs/{run_id}"
    return ResourceRef(
        kind="resume_derive_result",
        url=url,
        milestone_code=milestone_code,
        owner_scoped=True,
    )


def decide_cancel(
    *,
    domain_status: str,
    cancel_acknowledged: bool = False,
    cancel_requested: bool = False,
) -> ControlDecision:
    status = map_domain_status(domain_status)
    if is_terminal(status):
        return ControlDecision(
            allowed=False,
            action="cancel",
            reason=f"terminal status {status.value} cannot cancel",
            target_status=None,
        )
    if status is TaskStatus.CANCELLING or cancel_requested:
        return ControlDecision(
            allowed=True,
            action="cancel",
            reason="cancel already durable (idempotent)",
            target_status=TaskStatus.CANCELLED if cancel_acknowledged else TaskStatus.CANCELLING,
            metadata={"idempotent": True},
        )
    if status not in _CANCELABLE:
        return ControlDecision(
            allowed=False,
            action="cancel",
            reason=f"cancel not available in {status.value}",
            target_status=None,
        )
    return ControlDecision(
        allowed=True,
        action="cancel",
        reason="cancel accepted before next provider/domain write",
        target_status=TaskStatus.CANCELLING,
        metadata={
            "safe_points": ("before_provider", "before_publish", "before_domain_write"),
            "preserve_delivered_milestones": True,
        },
    )


def decide_retry(
    *,
    domain_status: str,
    component: str | None = None,
    component_status: Mapping[str, Any] | None = None,
) -> ControlDecision:
    """Component retry — new execution lineage; never double-settle a milestone."""
    status = map_domain_status(domain_status)
    evidence = build_partial_settlement_evidence(
        domain_status=domain_status,
        component_status=component_status,
    )
    raw_component = component or (evidence.failed_milestones[0] if evidence.failed_milestones else None)
    if raw_component is None:
        return ControlDecision(
            allowed=False,
            action="retry_failed_component",
            reason="no failed component to retry",
            target_status=None,
        )
    milestone = COMPONENT_TO_MILESTONE.get(raw_component, raw_component)
    if milestone not in MILESTONE_CODES:
        return ControlDecision(
            allowed=False,
            action="retry_failed_component",
            reason=f"unknown component {raw_component}",
            target_status=None,
        )
    if milestone in evidence.delivered_milestones:
        return ControlDecision(
            allowed=False,
            action="retry_failed_component",
            reason=f"milestone {milestone} already delivered; cannot settle twice",
            target_status=None,
            metadata={"settle_milestone_once": True},
        )
    if status not in {
        TaskStatus.PARTIALLY_SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.RETRY_WAIT,
    }:
        return ControlDecision(
            allowed=False,
            action="retry_failed_component",
            reason=f"component retry not available in {status.value}",
            target_status=None,
        )
    return ControlDecision(
        allowed=True,
        action="retry_failed_component",
        reason=f"retry {milestone} creates new execution lineage",
        target_status=TaskStatus.QUEUED,
        metadata={
            "component": milestone,
            "new_execution_required": True,
            "settle_milestone_once": True,
            "already_chargeable": list(evidence.chargeable_milestone_codes),
        },
    )


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


class ResumeDeriveAdapter:
    """CapabilityAdapter for resume_derive:derive."""

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
        if len(codes) != 3:
            raise ValueError("derive requires exactly three milestones")
        validate_acceptance_envelope(envelope)
        return envelope


__all__ = [
    "ADAPTER_VERSION",
    "CAPABILITY_CODE",
    "COMPONENT_TO_MILESTONE",
    "ControlDecision",
    "DEFAULT_ACTION",
    "MILESTONE_CODES",
    "PartialSettlementEvidence",
    "ResourceRef",
    "ResumeDeriveAdapter",
    "SUPPORTED_ACTIONS",
    "build_input_snapshot",
    "build_partial_settlement_evidence",
    "decide_cancel",
    "decide_retry",
    "decode_live_artifact",
    "delivered_milestones",
    "failed_milestones",
    "map_domain_status",
    "milestone_catalog",
    "normalize_component_status",
    "open_result_ref",
    "projection_actions",
]
