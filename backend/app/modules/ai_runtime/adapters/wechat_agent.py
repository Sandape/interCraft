"""REQ-061 WeChat Agent capability adapter (T082).

Maps channel-specific AgentTask / tool / delivery state onto the canonical
runtime while retaining binding epoch, immutable authorization receipts,
execution fence, and effect-intent evidence. Adapters never mutate point
balances or canonical task rows directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping
from uuid import uuid4

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
from app.modules.ai_runtime.authorization.service import (
    AuthorizationError,
    AuthorizationReceipt,
    issue_authorization_receipt,
    validate_receipt_for_execution,
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

CAPABILITY_CODE = "wechat_agent"
DEFAULT_ACTION = "run"
SUPPORTED_ACTIONS = frozenset({"run"})
MILESTONE_CODES = ("answer", "committed_tool_result")
ADAPTER_VERSION = "wechat_agent.adapter.v1"

_BOUND_RECEIPT_FIELDS = (
    "actor_id",
    "tenant_id",
    "action",
    "target_id",
    "target_version",
    "argument_hash",
    "tool_policy_version",
    "budget_points",
    "expires_at",
    "idempotency_key",
    "approval_id",
)

# Domain AgentTask / tool-loop statuses → canonical. Terminals need evidence.
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
    "succeeded": TaskStatus.SUCCEEDED,
    "complete": TaskStatus.SUCCEEDED,
    "partial": TaskStatus.PARTIALLY_SUCCEEDED,
    "partial_success": TaskStatus.PARTIALLY_SUCCEEDED,
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
class ToolEffectEvidence:
    """Committed / unknown / not-started evidence for a tool side effect."""

    status: str  # committed | unknown | not_started | failed
    tool_name: str
    effect_intent_id: str | None = None
    authorization_receipt_id: str | None = None
    claim_generation_at_send: int | None = None
    claim_generation_at_adoption: int | None = None
    committed: bool = False
    deliverable: bool = False
    chargeable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EffectFence:
    """In-memory fence for send/adoption CAS (pure adapter helper)."""

    intent_id: str
    claim_generation: int
    binding_id: str
    binding_epoch: int
    authorization_receipt_id: str
    canonical_request_hash: str
    status: str = "prepared"  # prepared|sent|adopted|unknown|rejected_stale
    provider_idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalLineage:
    root_task_id: str
    task_id: str
    execution_id: str
    binding_id: str
    binding_epoch: int
    claim_generation: int
    attempt_id: str | None = None


def map_domain_status(
    domain_status: str,
    *,
    binding_epoch: int | None = None,
    expected_binding_epoch: int | None = None,
    has_result_evidence: bool = True,
    has_failure_evidence: bool = True,
    has_task_event: bool = True,
    has_settlement_trigger: bool = True,
) -> TaskStatus:
    """Binding-scoped domain → canonical mapping.

    Epoch mismatch forces ``result_confirming`` rather than a false terminal.
    """
    if (
        binding_epoch is not None
        and expected_binding_epoch is not None
        and int(binding_epoch) != int(expected_binding_epoch)
    ):
        return TaskStatus.RESULT_CONFIRMING

    key = str(domain_status or "").strip().lower()
    if key not in _DOMAIN_STATUS_MAP:
        raise ValueError(f"unknown wechat_agent domain status: {domain_status!r}")
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
    binding_id: str,
    binding_epoch: int,
    user_message_ref: str,
    tool_catalog_version: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "binding_id": str(binding_id),
        "binding_epoch": int(binding_epoch),
        "user_message_ref": str(user_message_ref),
        "tool_catalog_version": str(tool_catalog_version),
        "adapter_version": ADAPTER_VERSION,
        "milestones": list(MILESTONE_CODES),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def issue_tool_authorization(
    *,
    actor_id: str,
    tenant_id: str,
    action: str,
    target_id: str,
    target_version: int,
    argument_hash: str,
    tool_policy_version: str,
    budget_points: int,
    expires_at: str,
    idempotency_key: str,
    approval_id: str,
    claim_generation: int,
) -> AuthorizationReceipt:
    """Issue an immutable authorization receipt for a writable tool."""
    return issue_authorization_receipt(
        actor_id=actor_id,
        tenant_id=tenant_id,
        action=action,
        target_id=target_id,
        target_version=target_version,
        argument_hash=argument_hash,
        tool_policy_version=tool_policy_version,
        budget_points=budget_points,
        expires_at=expires_at,
        idempotency_key=idempotency_key,
        approval_id=approval_id,
        claim_generation=claim_generation,
    )


def consume_authorization_receipt(
    receipt: AuthorizationReceipt,
    *,
    execution_claim_generation: int,
    **bound_fields: Any,
) -> AuthorizationReceipt:
    """CAS-consume a receipt; any bound-field mismatch requires reauthorization."""
    return validate_receipt_for_execution(
        receipt,
        execution_claim_generation=execution_claim_generation,
        **bound_fields,
    )


def bound_receipt_field_names() -> tuple[str, ...]:
    return _BOUND_RECEIPT_FIELDS


def prepare_effect_fence(
    *,
    claim_generation: int,
    binding_id: str,
    binding_epoch: int,
    authorization_receipt_id: str,
    canonical_request_hash: str,
    provider_idempotency_key: str | None = None,
) -> EffectFence:
    return EffectFence(
        intent_id=str(uuid4()),
        claim_generation=int(claim_generation),
        binding_id=str(binding_id),
        binding_epoch=int(binding_epoch),
        authorization_receipt_id=str(authorization_receipt_id),
        canonical_request_hash=str(canonical_request_hash),
        status="prepared",
        provider_idempotency_key=provider_idempotency_key,
    )


def send_effect(fence: EffectFence) -> EffectFence:
    if fence.status not in {"prepared"}:
        raise AuthorizationError(f"cannot send effect in status {fence.status}")
    return replace(fence, status="sent")


def adopt_effect(
    fence: EffectFence,
    *,
    current_claim_generation: int,
    current_binding_epoch: int,
) -> EffectFence:
    """Only the current fence may adopt. Stale claim → rejected_stale / unknown."""
    if fence.status != "sent":
        raise AuthorizationError(f"cannot adopt effect in status {fence.status}")
    if int(current_claim_generation) != int(fence.claim_generation):
        return replace(fence, status="rejected_stale")
    if int(current_binding_epoch) != int(fence.binding_epoch):
        return replace(fence, status="unknown")
    return replace(fence, status="adopted")


def classify_tool_evidence(
    *,
    tool_name: str,
    fence: EffectFence | None,
    tool_committed: bool,
    tool_status: str,
) -> ToolEffectEvidence:
    """Map fence + tool outcome onto committed/unknown/not_started evidence."""
    if fence is None:
        return ToolEffectEvidence(
            status="not_started",
            tool_name=tool_name,
            committed=False,
            deliverable=False,
            chargeable=False,
        )
    if fence.status == "rejected_stale" or fence.status == "unknown":
        return ToolEffectEvidence(
            status="unknown",
            tool_name=tool_name,
            effect_intent_id=fence.intent_id,
            authorization_receipt_id=fence.authorization_receipt_id,
            claim_generation_at_send=fence.claim_generation,
            committed=False,
            deliverable=False,
            chargeable=False,
            metadata={"fence_status": fence.status},
        )
    if fence.status == "adopted" and tool_committed and tool_status == "succeeded":
        return ToolEffectEvidence(
            status="committed",
            tool_name=tool_name,
            effect_intent_id=fence.intent_id,
            authorization_receipt_id=fence.authorization_receipt_id,
            claim_generation_at_send=fence.claim_generation,
            claim_generation_at_adoption=fence.claim_generation,
            committed=True,
            deliverable=True,
            chargeable=True,
        )
    if tool_status in {"unknown_result", "unknown"}:
        return ToolEffectEvidence(
            status="unknown",
            tool_name=tool_name,
            effect_intent_id=fence.intent_id,
            authorization_receipt_id=fence.authorization_receipt_id,
            claim_generation_at_send=fence.claim_generation,
            committed=False,
            deliverable=False,
            chargeable=False,
        )
    return ToolEffectEvidence(
        status="failed",
        tool_name=tool_name,
        effect_intent_id=fence.intent_id,
        authorization_receipt_id=fence.authorization_receipt_id,
        claim_generation_at_send=fence.claim_generation,
        committed=False,
        deliverable=False,
        chargeable=False,
        metadata={"tool_status": tool_status},
    )


def delivery_independent_projection(
    *,
    tool_evidence: ToolEffectEvidence,
    channel_delivery_status: str,
) -> dict[str, Any]:
    """Channel delivery must not rewrite tool commitment / chargeability."""
    delivery = str(channel_delivery_status or "").strip().lower()
    return {
        "tool_evidence_status": tool_evidence.status,
        "tool_committed": tool_evidence.committed,
        "chargeable": tool_evidence.chargeable,
        "channel_delivery_status": delivery,
        "delivery_affects_commitment": False,
        # Even if WeChat delivery failed, committed tool facts remain committed.
        "settlement_basis": tool_evidence.status,
    }


def build_canonical_lineage(
    *,
    root_task_id: str,
    task_id: str,
    execution_id: str,
    binding_id: str,
    binding_epoch: int,
    claim_generation: int,
    attempt_id: str | None = None,
) -> CanonicalLineage:
    return CanonicalLineage(
        root_task_id=str(root_task_id),
        task_id=str(task_id),
        execution_id=str(execution_id),
        binding_id=str(binding_id),
        binding_epoch=int(binding_epoch),
        claim_generation=int(claim_generation),
        attempt_id=str(attempt_id) if attempt_id else None,
    )


def open_result_ref(
    *,
    task_id: str,
    milestone_code: str | None = None,
) -> ResourceRef:
    if milestone_code == "committed_tool_result":
        url = f"/api/v1/agent/tasks/{task_id}?milestone=committed_tool_result"
    elif milestone_code == "answer":
        url = f"/api/v1/agent/tasks/{task_id}?milestone=answer"
    else:
        url = f"/api/v1/agent/tasks/{task_id}"
    return ResourceRef(
        kind="wechat_agent_result",
        url=url,
        milestone_code=milestone_code,
        owner_scoped=True,
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
        reason="cancel accepted; durable before provider/tool work",
        target_status=TaskStatus.CANCELLING,
        metadata={"safe_points": ("before_provider", "before_tool", "before_delivery")},
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


def runtime_links_for_task(task_id: str) -> dict[str, str]:
    """Canonical acceptance/detail/control links without binding/provider internals."""
    tid = str(task_id)
    return {
        "status_url": f"/api/v1/ai-tasks/{tid}",
        "events_url": f"/api/v1/ai-tasks/{tid}/events",
        "detail_url": f"/api/v1/agent/tasks/{tid}",
        "cancel_url": f"/api/v1/agent/tasks/{tid}/cancel",
        "resume_url": f"/api/v1/agent/tasks/{tid}/resume",
    }


class WeChatAgentAdapter:
    """CapabilityAdapter for wechat_agent/run."""

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
    "AuthorizationError",
    "AuthorizationReceipt",
    "CAPABILITY_CODE",
    "CanonicalLineage",
    "ControlDecision",
    "DEFAULT_ACTION",
    "EffectFence",
    "MILESTONE_CODES",
    "ResourceRef",
    "SUPPORTED_ACTIONS",
    "ToolEffectEvidence",
    "WeChatAgentAdapter",
    "adopt_effect",
    "bound_receipt_field_names",
    "build_canonical_lineage",
    "build_input_snapshot",
    "classify_tool_evidence",
    "consume_authorization_receipt",
    "decide_cancel",
    "decode_live_artifact",
    "delivery_independent_projection",
    "issue_tool_authorization",
    "map_domain_status",
    "milestone_catalog",
    "open_result_ref",
    "prepare_effect_fence",
    "projection_actions",
    "runtime_links_for_task",
    "send_effect",
]
