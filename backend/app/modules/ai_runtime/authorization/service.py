"""REQ-061 immutable authorization receipts (T021).

Pure helpers satisfy unit/integration field-matrix tests. Callers issue semantic
receipts; execution-time validation CAS-consumes a matching receipt once.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class AuthorizationError(ValueError):
    """Raised when a receipt is missing, mismatched, expired, or already consumed."""


@dataclass(frozen=True, slots=True)
class AuthorizationReceipt:
    id: str
    actor_id: str
    tenant_id: str
    action: str
    target_id: str
    target_version: int
    argument_hash: str
    tool_policy_version: str
    budget_points: int
    expires_at: str
    idempotency_key: str
    approval_id: str
    claim_generation: int
    consumed: bool = False
    revoked: bool = False


_BOUND_COMPARE = (
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


def issue_authorization_receipt(
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
    **_: Any,
) -> AuthorizationReceipt:
    return AuthorizationReceipt(
        id=str(uuid4()),
        actor_id=actor_id,
        tenant_id=tenant_id,
        action=action,
        target_id=target_id,
        target_version=int(target_version),
        argument_hash=argument_hash,
        tool_policy_version=tool_policy_version,
        budget_points=int(budget_points),
        expires_at=expires_at,
        idempotency_key=idempotency_key,
        approval_id=approval_id,
        claim_generation=int(claim_generation),
        consumed=False,
        revoked=False,
    )


def validate_receipt_for_execution(
    receipt: AuthorizationReceipt,
    *,
    execution_claim_generation: int,
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
    **_: Any,
) -> AuthorizationReceipt:
    if receipt.revoked:
        raise AuthorizationError("receipt revoked")
    if receipt.consumed:
        raise AuthorizationError("receipt already consumed")
    if int(execution_claim_generation) != int(receipt.claim_generation):
        raise AuthorizationError("claim_generation mismatch — reauthorization required")

    expected = {
        "actor_id": receipt.actor_id,
        "tenant_id": receipt.tenant_id,
        "action": receipt.action,
        "target_id": receipt.target_id,
        "target_version": receipt.target_version,
        "argument_hash": receipt.argument_hash,
        "tool_policy_version": receipt.tool_policy_version,
        "budget_points": receipt.budget_points,
        "expires_at": receipt.expires_at,
        "idempotency_key": receipt.idempotency_key,
        "approval_id": receipt.approval_id,
    }
    actual = {
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "action": action,
        "target_id": target_id,
        "target_version": int(target_version),
        "argument_hash": argument_hash,
        "tool_policy_version": tool_policy_version,
        "budget_points": int(budget_points),
        "expires_at": expires_at,
        "idempotency_key": idempotency_key,
        "approval_id": approval_id,
    }
    for field in _BOUND_COMPARE:
        if expected[field] != actual[field]:
            raise AuthorizationError(f"{field} mismatch — reauthorization required")

    expires = datetime.fromisoformat(receipt.expires_at.replace("Z", "+00:00"))
    if expires <= datetime.now(timezone.utc):
        raise AuthorizationError("receipt expired")

    return replace(receipt, consumed=True)


class AuthorizationService:
    """Framework-neutral authorization helper used by ExecutionContext factories."""

    def issue(self, **kwargs: Any) -> AuthorizationReceipt:
        return issue_authorization_receipt(**kwargs)

    def validate_for_execution(
        self,
        receipt: AuthorizationReceipt,
        *,
        execution_claim_generation: int,
        **kwargs: Any,
    ) -> AuthorizationReceipt:
        return validate_receipt_for_execution(
            receipt,
            execution_claim_generation=execution_claim_generation,
            **kwargs,
        )


__all__ = [
    "AuthorizationError",
    "AuthorizationReceipt",
    "AuthorizationService",
    "issue_authorization_receipt",
    "validate_receipt_for_execution",
]
