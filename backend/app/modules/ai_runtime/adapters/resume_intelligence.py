"""REQ-061 resume intelligence capability adapter (T062).

Pure mapping/decision helpers — adapters never mutate point balances or
canonical task rows directly.
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
from app.modules.ai_runtime.compatibility import (
    CompatibilityDecision,
    decode_or_quarantine,
)
from app.modules.ai_runtime.state_machine import (
    TaskStatus,
    available_actions_for,
    is_terminal,
)

CAPABILITY_CODE = "resume_intelligence"
DEFAULT_ACTION = "analyze"
SUPPORTED_ACTIONS = frozenset({"analyze", "suggest"})
MILESTONE_CODES = ("analysis", "suggestions")
ADAPTER_VERSION = "resume_intelligence.adapter.v1"

# Domain → canonical. Terminal mappings require evidence (see map_domain_status).
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

_FABRICATION_BLOCK_MODES = frozenset(
    {"needs_supplement", "human_review", "forbid_write", "blocked"}
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
    """Map a resume-intelligence domain status onto the canonical 12-state enum."""
    key = str(domain_status or "").strip().lower()
    if key not in _DOMAIN_STATUS_MAP:
        raise ValueError(f"unknown resume_intelligence domain status: {domain_status!r}")
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
    resume_id: str,
    resume_version: int,
    job_id: str | None = None,
    jd_hash: str | None = None,
    mode: str = "job_fit",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic input/version snapshot fields for acceptance hashing."""
    payload: dict[str, Any] = {
        "resume_id": str(resume_id),
        "resume_version": int(resume_version),
        "job_id": str(job_id) if job_id else None,
        "jd_hash": jd_hash,
        "mode": mode,
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
    """Deterministic quality/safety gate before milestone delivery/charge."""
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

    if code == "analysis":
        score = result_payload.get("overall_score")
        gaps = result_payload.get("gaps")
        if score is None and not gaps:
            return QualityGateVerdict(
                passed=False,
                code="ANALYSIS_INCOMPLETE",
                message="analysis lacks score or gaps",
                deliverable=False,
                chargeable=False,
            )
        return QualityGateVerdict(
            passed=True,
            code="ANALYSIS_OK",
            message="analysis evidence present",
            deliverable=True,
            chargeable=True,
        )

    # suggestions milestone — anti-fabrication
    action_mode = str(result_payload.get("action_mode") or "").lower()
    if action_mode in _FABRICATION_BLOCK_MODES:
        return QualityGateVerdict(
            passed=True,
            code="FACT_GATE",
            message="suggestion requires supplement/human review; not directly writable",
            deliverable=True,
            chargeable=True,
            metadata={"direct_apply": False, "action_mode": action_mode},
        )
    if result_payload.get("fabricated") is True:
        return QualityGateVerdict(
            passed=False,
            code="FABRICATION_BLOCKED",
            message="fabricated suggestion must not be delivered or charged",
            deliverable=False,
            chargeable=False,
        )
    if not result_payload.get("source_refs"):
        return QualityGateVerdict(
            passed=False,
            code="MISSING_SOURCE_REFS",
            message="suggestions require source_refs",
            deliverable=False,
            chargeable=False,
        )
    return QualityGateVerdict(
        passed=True,
        code="SUGGESTION_OK",
        message="suggestion evidence present",
        deliverable=True,
        chargeable=True,
        metadata={"direct_apply": action_mode in {"", "direct", "apply"}},
    )


def open_result_ref(
    *,
    run_id: str,
    milestone_code: str | None = None,
    analysis_id: str | None = None,
) -> ResourceRef:
    """Owner-scoped result URL for a delivered milestone (or whole run)."""
    base_id = analysis_id or run_id
    if milestone_code == "suggestions":
        url = f"/api/v1/v2/resume-intelligence/runs/{run_id}/suggestions"
    elif milestone_code == "analysis":
        url = f"/api/v1/v2/resume-intelligence/analyses/{base_id}"
    else:
        url = f"/api/v1/v2/resume-intelligence/runs/{run_id}"
    return ResourceRef(
        kind="resume_intelligence_result",
        url=url,
        milestone_code=milestone_code,
        owner_scoped=True,
    )


def decide_cancel(
    *,
    domain_status: str,
    cancel_acknowledged: bool = False,
) -> ControlDecision:
    """Pure cancel hook — returns a decision envelope; does not mutate state."""
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
            target_status=None,
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
            target_status=None,
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
    failed_components: Mapping[str, str] | None = None,
) -> ControlDecision:
    """Pure retry/component-retry decision (new execution lineage expected)."""
    status = map_domain_status(domain_status)
    comps = dict(failed_components or {})
    target_component = component or "analysis"

    if status is TaskStatus.PARTIALLY_SUCCEEDED or (
        status is TaskStatus.FAILED and target_component in comps
    ):
        return ControlDecision(
            allowed=True,
            action="retry_failed_component",
            reason=f"retry component {target_component} creates new execution lineage",
            target_status=TaskStatus.QUEUED,
            metadata={
                "component": target_component,
                "new_execution_required": True,
                "settle_milestone_once": True,
            },
        )
    if status is TaskStatus.FAILED:
        return ControlDecision(
            allowed=True,
            action="system_failure_retry",
            reason="system failure retry creates new execution lineage",
            target_status=TaskStatus.QUEUED,
            metadata={"new_execution_required": True},
        )
    if status is TaskStatus.RETRY_WAIT:
        return ControlDecision(
            allowed=True,
            action="resume",
            reason="resume from retry_wait",
            target_status=TaskStatus.QUEUED,
        )
    return ControlDecision(
        allowed=False,
        action="retry_failed_component",
        reason=f"retry not available in {status.value}",
        target_status=None,
    )


def decode_live_artifact(
    *,
    kind: str,
    version: str,
    payload: Mapping[str, Any],
) -> CompatibilityDecision:
    """Decode current/prior live checkpoint or job fixture for this capability."""
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


class ResumeIntelligenceAdapter:
    """CapabilityAdapter for resume_intelligence analyze/suggest."""

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
        # Ensure analysis/suggestions milestone codes are present and ordered.
        codes = tuple(m.code for m in envelope.milestones)
        if codes != MILESTONE_CODES:
            # Registry is source of truth; assert shape for this adapter.
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
    "QualityGateVerdict",
    "ResourceRef",
    "ResumeIntelligenceAdapter",
    "SUPPORTED_ACTIONS",
    "build_input_snapshot",
    "decide_cancel",
    "decide_retry",
    "decode_live_artifact",
    "evaluate_quality_gate",
    "map_domain_status",
    "milestone_catalog",
    "open_result_ref",
    "projection_actions",
]
