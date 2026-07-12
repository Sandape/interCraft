"""REQ-061 named AI admin capabilities (T024 precursor for T012 tests)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AIAdminCapability(StrEnum):
    SUPPORT_READ = "ai.support.read"
    OPERATIONS_READ = "ai.operations.read"
    QUALITY_BADCASE_MANAGE = "ai.quality.badcase.manage"
    COST_MANAGE = "ai.cost.manage"
    MODEL_POLICY_MANAGE = "ai.model_policy.manage"
    RESTRICTED_CONTENT_REVEAL = "ai.restricted_content.reveal"
    AUDIT_EXPORT = "ai.audit.export"


_ADMIN_ROLES = frozenset({"admin", "superadmin", "ops", "ai_ops"})

_PROVIDER_FIELDS = frozenset(
    {
        "provider_model_name",
        "provider_internal_code",
        "route_internal_code",
        "provider_request_id",
    }
)

_CAPABILITIES_SEEING_PROVIDER = frozenset(
    {
        AIAdminCapability.COST_MANAGE,
        AIAdminCapability.MODEL_POLICY_MANAGE,
        AIAdminCapability.OPERATIONS_READ,
        AIAdminCapability.AUDIT_EXPORT,
    }
)


@dataclass(frozen=True, slots=True)
class FieldAccessDecision:
    allowed: bool
    reason: str | None = None


def has_ai_admin_capability(*, roles: list[str], capability: str) -> bool:
    if capability not in {c.value for c in AIAdminCapability}:
        return False
    return any(role in _ADMIN_ROLES for role in roles)


def decide_field_access(
    *,
    capability: str,
    field: str,
    reveal_reason: str | None = None,
    ttl_seconds: int | None = None,
) -> FieldAccessDecision:
    try:
        cap = AIAdminCapability(capability)
    except ValueError:
        return FieldAccessDecision(allowed=False, reason="unknown_capability")

    if cap == AIAdminCapability.RESTRICTED_CONTENT_REVEAL:
        if field == "evidence_snapshot":
            if not reveal_reason or ttl_seconds is None or ttl_seconds <= 0:
                return FieldAccessDecision(
                    allowed=False, reason="reveal_requires_reason_and_ttl"
                )
            return FieldAccessDecision(allowed=True)
        return FieldAccessDecision(allowed=False, reason="field_not_revealable")

    if field in _PROVIDER_FIELDS:
        if cap in _CAPABILITIES_SEEING_PROVIDER:
            return FieldAccessDecision(allowed=True)
        return FieldAccessDecision(allowed=False, reason="provider_field_restricted")

    if cap == AIAdminCapability.SUPPORT_READ:
        return FieldAccessDecision(allowed=True)

    return FieldAccessDecision(allowed=True)


__all__ = [
    "AIAdminCapability",
    "FieldAccessDecision",
    "decide_field_access",
    "has_ai_admin_capability",
]
