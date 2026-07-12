"""REQ-061 US7 — model policy service facade (T104)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.ai_runtime.adapters.registry import load_registry
from app.modules.ai_runtime.provider_gateway.policy_repository import (
    ModelPolicyRecord,
    ModelPolicyRepository,
    PolicyRepositoryError,
    get_default_policy_repository,
)


class PolicyServiceError(ValueError):
    def __init__(self, message: str, status: int = 400, code: str = "POLICY_ERROR") -> None:
        self.message = message
        self.status = status
        self.code = code
        super().__init__(message)


def user_capability_catalog() -> list[dict[str, Any]]:
    """User-visible catalog — tiers/points only, never provider/model names."""
    registry = load_registry()
    # Group by capability for a compact catalog while keeping per-action detail.
    by_cap: dict[str, dict[str, Any]] = {}
    for (cap, act), spec in sorted(registry.items()):
        if spec.rollout_status == "disabled":
            continue
        entry = by_cap.setdefault(
            cap,
            {
                "capability": cap,
                "actions": [],
                "tiers": [],
                "service_tiers": [],
                "max_points_by_tier": {},
                "milestones": [],
            },
        )
        if act not in entry["actions"]:
            entry["actions"].append(act)
        for tier in spec.tiers:
            if tier not in entry["tiers"]:
                entry["tiers"].append(tier)
                entry["service_tiers"].append(tier)
            points = sum(m.max_points for m in spec.milestones)
            entry["max_points_by_tier"][tier] = max(
                entry["max_points_by_tier"].get(tier, 0), points
            )
        for m in spec.milestones:
            codes = {x["code"] for x in entry["milestones"]}
            if m.code not in codes:
                entry["milestones"].append(
                    {"code": m.code, "label": m.label, "max_points": m.max_points}
                )
    # Flatten to one row per capability/action for schema Compatibility.
    flat: list[dict[str, Any]] = []
    for (cap, act), spec in sorted(registry.items()):
        if spec.rollout_status == "disabled":
            continue
        flat.append(
            {
                "capability": cap,
                "action": act,
                "actions": [act],
                "tiers": list(spec.tiers),
                "service_tiers": list(spec.tiers),
                "max_points_by_tier": {
                    tier: sum(m.max_points for m in spec.milestones) for tier in spec.tiers
                },
                "milestones": [
                    {"code": m.code, "label": m.label, "max_points": m.max_points}
                    for m in spec.milestones
                ],
            }
        )
    return flat


def _money(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "amount": str(Decimal(str(value["amount"]))),
            "currency": str(value.get("currency") or "CNY"),
        }
    return {"amount": str(Decimal(str(value))), "currency": "CNY"}


def record_to_admin_dict(record: ModelPolicyRecord) -> dict[str, Any]:
    return {
        "policy_version": str(record.id),
        "id": str(record.id),
        "capability": record.capability,
        "subscenario": record.subscenario,
        "service_tier": record.service_tier,
        "primary_route": record.primary_route,
        "allowed_fallbacks": list(record.allowed_fallbacks),
        "quality_gate_ref": record.quality_gate_ref,
        "latency_target_ms": record.latency_target_ms,
        "cost_ceiling_rmb": _money(record.cost_ceiling_rmb),
        "rollback_target": record.rollback_target,
        "owner": record.owner,
        "reason": record.reason,
        "status": record.status,
        "effective_from": record.effective_from.isoformat() if record.effective_from else None,
        "effective_to": record.effective_to.isoformat() if record.effective_to else None,
        "evaluation_ref": record.evaluation_ref,
        "evaluation_evidence_ref": record.evaluation_ref,
        "traffic_percent": record.traffic_percent,
    }


class ModelPolicyService:
    def __init__(self, repo: ModelPolicyRepository | None = None) -> None:
        self.repo = repo or get_default_policy_repository()

    def create_policy(
        self,
        *,
        capability: str,
        subscenario: str,
        service_tier: str,
        primary_route: str,
        allowed_fallbacks: list[str] | None = None,
        quality_gate_ref: str,
        latency_target_ms: int,
        cost_ceiling_rmb: Any,
        rollback_target: str | None,
        owner: str,
        reason: str,
        **extra: Any,
    ) -> dict[str, Any]:
        try:
            status = "candidate" if rollback_target else "draft"
            record = self.repo.create(
                {
                    "capability": capability,
                    "subscenario": subscenario,
                    "service_tier": service_tier,
                    "primary_route": primary_route,
                    "allowed_fallbacks": allowed_fallbacks or [],
                    "quality_gate_ref": quality_gate_ref,
                    "latency_target_ms": latency_target_ms,
                    "cost_ceiling_rmb": cost_ceiling_rmb,
                    "rollback_target": rollback_target,
                    "owner": owner,
                    "reason": reason,
                    "status": status,
                    **extra,
                }
            )
        except PolicyRepositoryError as exc:
            raise PolicyServiceError(str(exc), status=422, code="POLICY_CREATE_FAILED") from exc
        return record_to_admin_dict(record)

    def list_policies(
        self,
        *,
        capability: str | None = None,
        service_tier: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            record_to_admin_dict(p)
            for p in self.repo.list(
                capability_code=capability,
                service_tier=service_tier,
                status=status,
            )
        ]

    def get_policy(self, policy_version: str) -> dict[str, Any]:
        record = self.repo.get(policy_version)
        if record is None:
            raise PolicyServiceError(
                f"unknown policy_version: {policy_version}", status=404
            )
        return record_to_admin_dict(record)

    def release_policy(
        self,
        policy_version: str,
        *,
        target_status: str,
        traffic_percent: int | float = 100,
        eval_evidence_ref: str,
        rollback_target: str | None = None,
        reason: str = "release",
        actor: str | None = None,
    ) -> dict[str, Any]:
        try:
            record = self.repo.transition(
                UUID(str(policy_version)),
                target_status=target_status,
                traffic_percent=traffic_percent,
                eval_evidence_ref=eval_evidence_ref,
                rollback_target=rollback_target,
                reason=reason,
                actor=actor,
            )
        except (PolicyRepositoryError, ValueError) as exc:
            status = 409 if "transition" in str(exc) or "overlap" in str(exc) else 422
            raise PolicyServiceError(str(exc), status=status, code="POLICY_RELEASE_FAILED") from exc
        return {
            "accepted": True,
            "status": record.status,
            "policy_version": str(record.id),
            "traffic_percent": record.traffic_percent,
            "reason": reason,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_effective(
        self,
        *,
        capability: str,
        subscenario: str,
        service_tier: str,
        at: datetime | None = None,
    ) -> ModelPolicyRecord | None:
        return self.repo.find_effective(
            capability_code=capability,
            subscenario=subscenario,
            service_tier=service_tier,
            at=at,
        )


__all__ = [
    "ModelPolicyService",
    "PolicyServiceError",
    "record_to_admin_dict",
    "user_capability_catalog",
]
