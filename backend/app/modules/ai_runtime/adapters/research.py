"""REQ-061 proactive-research capability adapter (T095).

Explicit opt-in, job/input snapshot, quote preview, source sufficiency gate,
cancellation, and sourced-report milestone. Points must not be reserved or
settled before opt-in/acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.modules.ai_runtime.adapters.contracts import (
    AcceptanceEnvelope,
    AdapterError,
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

CAPABILITY_CODE = "proactive_research"
DEFAULT_ACTION = "research"
SUPPORTED_ACTIONS = frozenset({"research"})
MILESTONE_CODES = ("sourced_report",)
ADAPTER_VERSION = "proactive_research.adapter.v1"

# FR-064 / US6: standard 100 / quality 250 after successful report delivery.
TIER_POINT_CAPS: dict[str, int] = {"standard": 100, "quality": 250}

# Minimum distinct sources required before a determinative research conclusion.
DEFAULT_MIN_SOURCES = 2

_DOMAIN_STATUS_MAP: dict[str, TaskStatus] = {
    "pending": TaskStatus.ACCEPTED,
    "accepted": TaskStatus.ACCEPTED,
    "queued": TaskStatus.QUEUED,
    "running": TaskStatus.RUNNING,
    "awaiting_confirmation": TaskStatus.WAITING_USER,
    "waiting_user": TaskStatus.WAITING_USER,
    "opt_in_required": TaskStatus.WAITING_USER,
    "retry_wait": TaskStatus.RETRY_WAIT,
    "cancelling": TaskStatus.CANCELLING,
    "canceling": TaskStatus.CANCELLING,
    "waiting_external": TaskStatus.RUNNING,
    "unknown_result": TaskStatus.RESULT_CONFIRMING,
    "result_confirming": TaskStatus.RESULT_CONFIRMING,
    "complete": TaskStatus.SUCCEEDED,
    "completed": TaskStatus.SUCCEEDED,
    "succeeded": TaskStatus.SUCCEEDED,
    "quality_failed": TaskStatus.FAILED,
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
class ResearchQuotePreview:
    job_id: str
    service_tier: str
    max_points: int
    opt_in: bool
    can_disable: bool
    consume_points_before_accept: bool
    milestones: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceSufficiencyVerdict:
    sufficient: bool
    source_count: int
    min_required: int
    code: str
    message: str


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
        raise ValueError(f"unknown proactive_research domain status: {domain_status!r}")
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
    job_id: str,
    user_id: str,
    interview_time: str | None = None,
    company: str | None = None,
    role_title: str | None = None,
    opt_in: bool = False,
    service_tier: str = "standard",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_id": str(job_id),
        "user_id": str(user_id),
        "interview_time": interview_time,
        "company": company,
        "role_title": role_title,
        "opt_in": bool(opt_in),
        "service_tier": service_tier,
        "adapter_version": ADAPTER_VERSION,
        "milestones": list(MILESTONE_CODES),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def preview_quote(
    *,
    job_id: str,
    service_tier: str,
    opt_in: bool,
) -> ResearchQuotePreview:
    if service_tier not in TIER_POINT_CAPS:
        raise AdapterError(f"invalid service_tier: {service_tier}")
    return ResearchQuotePreview(
        job_id=str(job_id),
        service_tier=service_tier,
        max_points=TIER_POINT_CAPS[service_tier],
        opt_in=bool(opt_in),
        can_disable=True,
        # FR-041: no reserve/consume before explicit opt-in + accept.
        consume_points_before_accept=False,
        milestones=MILESTONE_CODES,
    )


def require_opt_in(*, opt_in: bool, accepted: bool = False) -> ControlDecision:
    if not opt_in:
        return ControlDecision(
            allowed=False,
            action="accept",
            reason="proactive research requires explicit opt-in",
            target_status=TaskStatus.WAITING_USER,
            metadata={"opt_in_required": True, "may_reserve_points": False},
        )
    if not accepted:
        return ControlDecision(
            allowed=False,
            action="accept",
            reason="opt-in present but acceptance not yet recorded",
            target_status=TaskStatus.WAITING_USER,
            metadata={"opt_in_required": False, "may_reserve_points": False},
        )
    return ControlDecision(
        allowed=True,
        action="accept",
        reason="opt-in and acceptance present; reservation permitted",
        target_status=TaskStatus.ACCEPTED,
        metadata={"opt_in_required": False, "may_reserve_points": True},
    )


def evaluate_source_sufficiency(
    sources: Sequence[Mapping[str, Any]] | Sequence[str] | None,
    *,
    min_required: int = DEFAULT_MIN_SOURCES,
) -> SourceSufficiencyVerdict:
    items = list(sources or [])
    count = len(items)
    if count < min_required:
        return SourceSufficiencyVerdict(
            sufficient=False,
            source_count=count,
            min_required=min_required,
            code="INSUFFICIENT_SOURCES",
            message=(
                f"need at least {min_required} sources before determinative "
                f"research conclusions; got {count}"
            ),
        )
    return SourceSufficiencyVerdict(
        sufficient=True,
        source_count=count,
        min_required=min_required,
        code="SOURCES_OK",
        message="source sufficiency gate passed",
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
            message="no report delivery evidence",
            deliverable=False,
            chargeable=False,
        )

    sources = result_payload.get("sources") or result_payload.get("source_refs") or []
    sufficiency = evaluate_source_sufficiency(sources)
    if not sufficiency.sufficient:
        return QualityGateVerdict(
            passed=False,
            code=sufficiency.code,
            message=sufficiency.message,
            deliverable=False,
            chargeable=False,
            metadata={"source_count": sufficiency.source_count},
        )

    report = result_payload.get("report_text") or result_payload.get("report_id")
    if not report:
        return QualityGateVerdict(
            passed=False,
            code="REPORT_INCOMPLETE",
            message="sourced report body missing",
            deliverable=False,
            chargeable=False,
        )

    return QualityGateVerdict(
        passed=True,
        code="REPORT_OK",
        message="sourced report evidence present",
        deliverable=True,
        chargeable=True,
        metadata={"source_count": sufficiency.source_count},
    )


def open_result_ref(
    *,
    job_id: str,
    report_id: str | None = None,
    milestone_code: str | None = None,
) -> ResourceRef:
    if report_id:
        url = f"/api/v1/jobs/{job_id}/research-reports/{report_id}"
    else:
        url = f"/api/v1/jobs/{job_id}/research-reports"
    return ResourceRef(
        kind="proactive_research_result",
        url=url,
        milestone_code=milestone_code or "sourced_report",
        owner_scoped=True,
    )


def decide_cancel(
    *,
    domain_status: str,
    cancel_acknowledged: bool = False,
    report_delivered: bool = False,
) -> ControlDecision:
    status = map_domain_status(domain_status)
    if is_terminal(status):
        return ControlDecision(
            allowed=False,
            action="cancel",
            reason=f"terminal status {status.value} cannot cancel",
            metadata={"points_settled": report_delivered},
        )
    if status is TaskStatus.CANCELLING:
        return ControlDecision(
            allowed=True,
            action="cancel",
            reason="cancel already in progress (idempotent)",
            target_status=TaskStatus.CANCELLED if cancel_acknowledged else TaskStatus.CANCELLING,
            metadata={"idempotent": True, "settle_on_cancel": False},
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
        reason="cancel accepted before delivery; no point settlement",
        target_status=TaskStatus.CANCELLING,
        metadata={
            "safe_points": ("before_provider", "before_publish", "before_domain_write"),
            "settle_on_cancel": False,
        },
    )


def decide_retry(*, domain_status: str) -> ControlDecision:
    status = map_domain_status(domain_status)
    if status in {TaskStatus.FAILED, TaskStatus.RETRY_WAIT}:
        return ControlDecision(
            allowed=True,
            action="system_failure_retry",
            reason="retry research creates new execution lineage",
            target_status=TaskStatus.QUEUED,
            metadata={"new_execution_required": True, "requires_fresh_opt_in": False},
        )
    return ControlDecision(
        allowed=False,
        action="system_failure_retry",
        reason=f"retry not available in {status.value}",
    )


def projection_actions(domain_status: str) -> list[str]:
    status = map_domain_status(domain_status)
    return available_actions_for(status, terminal=is_terminal(status))


class ResearchAdapter:
    """CapabilityAdapter for proactive_research."""

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
        opt_in: bool | None = None,
    ) -> AcceptanceEnvelope:
        payload = dict(input_payload or {})
        opted = bool(opt_in if opt_in is not None else payload.get("opt_in"))
        if not opted:
            raise AdapterError(
                "proactive research acceptance requires explicit opt-in"
            )
        envelope = registry_build_envelope(
            capability=CAPABILITY_CODE,
            action=self.action,
            service_tier=service_tier,
            input_snapshot_ref=input_snapshot_ref,
            allow_degrade=allow_degrade,
            input_payload=payload,
        )
        # Align milestone max_points with FR-064 tier caps.
        cap = TIER_POINT_CAPS.get(service_tier, envelope.max_points)
        milestones = tuple(
            MilestoneSpec(
                code=m.code,
                label=m.label,
                weight_basis_points=m.weight_basis_points,
                max_points=cap if i == 0 else 0,
            )
            for i, m in enumerate(envelope.milestones)
        )
        # Single milestone: put full cap on it.
        if len(milestones) == 1:
            milestones = (
                MilestoneSpec(
                    code=milestones[0].code,
                    label=milestones[0].label,
                    weight_basis_points=10000,
                    max_points=cap,
                ),
            )
        metadata = dict(envelope.metadata)
        metadata["opt_in"] = True
        metadata["can_disable"] = True
        metadata["consume_points_before_accept"] = False
        result = AcceptanceEnvelope(
            capability_code=envelope.capability_code,
            action_code=envelope.action_code,
            service_tier=envelope.service_tier,
            input_snapshot_ref=envelope.input_snapshot_ref,
            input_canonical_hash=envelope.input_canonical_hash,
            allow_degrade=envelope.allow_degrade,
            milestones=milestones,
            max_points=cap,
            metadata=metadata,
        )
        validate_acceptance_envelope(result)
        return result


__all__ = [
    "ADAPTER_VERSION",
    "CAPABILITY_CODE",
    "ControlDecision",
    "DEFAULT_ACTION",
    "DEFAULT_MIN_SOURCES",
    "MILESTONE_CODES",
    "QualityGateVerdict",
    "ResearchAdapter",
    "ResearchQuotePreview",
    "ResourceRef",
    "SUPPORTED_ACTIONS",
    "SourceSufficiencyVerdict",
    "TIER_POINT_CAPS",
    "build_input_snapshot",
    "decide_cancel",
    "decide_retry",
    "evaluate_quality_gate",
    "evaluate_source_sufficiency",
    "map_domain_status",
    "milestone_catalog",
    "open_result_ref",
    "preview_quote",
    "projection_actions",
    "require_opt_in",
]
