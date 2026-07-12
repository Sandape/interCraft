"""REQ-061 US7 — tier→route selection with snapshot lock (T105)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from app.core.ids import new_uuid_v7
from app.modules.ai_runtime.provider_gateway.policy_repository import (
    ModelPolicyRecord,
    ModelPolicyRepository,
    get_default_policy_repository,
)

BehaviorMode = Literal["locked_snapshot", "current_stable"]


class PolicyRouterError(RuntimeError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or code
        super().__init__(message or code)


PolicyAdmissionError = PolicyRouterError


@dataclass(frozen=True)
class LockedPolicySnapshot:
    snapshot_id: str
    model_policy_version_id: UUID
    capability: str
    subscenario: str
    service_tier: str
    primary_route: str
    allowed_fallbacks: tuple[str, ...]
    quality_gate_ref: str
    cost_ceiling_rmb: Decimal
    locked_at: datetime
    latency_target_ms: int = 0


RouteSnapshot = LockedPolicySnapshot


@dataclass
class RouteDecision:
    model_policy_version_id: UUID
    route_internal_code: str
    snapshot: LockedPolicySnapshot
    used_fallback: bool = False
    safety_upgrade: bool = False
    surcharge_points: int = 0
    provider_internal_code: str = "default"
    service_tier: str = "standard"
    metadata: dict[str, Any] = field(default_factory=dict)


SelectedRoute = RouteDecision


def _split_route(full_route: str) -> tuple[str, str]:
    if ":" in full_route:
        provider, name = full_route.split(":", 1)
        return provider, name
    return "default", full_route


class PolicyRouter:
    def __init__(
        self,
        repo: ModelPolicyRepository | None = None,
        *,
        known_rate_routes: set[str] | None = None,
    ) -> None:
        self.repo = repo or get_default_policy_repository()
        self.known_rate_routes = known_rate_routes

    def effective_policy(
        self,
        *,
        capability: str,
        service_tier: str,
        subscenario: str = "default",
        at: datetime | None = None,
    ) -> ModelPolicyRecord | None:
        return self.repo.find_effective(
            capability_code=capability,
            subscenario=subscenario,
            service_tier=service_tier,
            at=at,
        )

    def _snapshot_from_policy(self, policy: ModelPolicyRecord) -> LockedPolicySnapshot:
        return LockedPolicySnapshot(
            snapshot_id=str(new_uuid_v7()),
            model_policy_version_id=policy.id,
            capability=policy.capability,
            subscenario=policy.subscenario,
            service_tier=policy.service_tier,
            primary_route=policy.primary_route,
            allowed_fallbacks=tuple(policy.allowed_fallbacks),
            quality_gate_ref=policy.quality_gate_ref,
            cost_ceiling_rmb=policy.cost_ceiling_rmb,
            locked_at=datetime.now(timezone.utc),
            latency_target_ms=policy.latency_target_ms or 0,
        )

    def select_route(
        self,
        *,
        capability_code: str,
        subscenario: str = "default",
        service_tier: str,
        trigger_kind: str = "initial",
        behavior_mode: BehaviorMode | None = None,
        locked_snapshot: LockedPolicySnapshot | None = None,
        primary_unavailable: bool = False,
        allow_degrade: bool = False,
        safety_upgrade_route: str | None = None,
        estimated_cost_rmb: Decimal | str | None = None,
        unknown_rate_ok: bool = False,
    ) -> RouteDecision:
        # Resume / in-flight retry must reuse the locked snapshot.
        use_locked = behavior_mode == "locked_snapshot" or trigger_kind in {
            "user_resume",
            "system_failure_retry",
        }
        if use_locked and locked_snapshot is not None:
            snapshot = locked_snapshot
        else:
            # Re-execution / initial → current stable.
            policy = self.effective_policy(
                capability=capability_code,
                service_tier=service_tier,
                subscenario=subscenario,
            )
            if policy is None:
                raise PolicyRouterError(
                    "NO_STABLE_POLICY",
                    f"no stable/gray policy for {capability_code}/{subscenario}/{service_tier}",
                )
            snapshot = self._snapshot_from_policy(policy)

        full_route = snapshot.primary_route
        used_fallback = False

        if primary_unavailable:
            if not snapshot.allowed_fallbacks:
                raise PolicyRouterError("NO_FALLBACK", "no permitted fallbacks")
            # Quality tier silent degrade is forbidden without authorization.
            if snapshot.service_tier == "quality" and not allow_degrade:
                raise PolicyRouterError(
                    "DEGRADE_NOT_AUTHORIZED",
                    "quality tier fallback requires allow_degrade",
                )
            if not allow_degrade and snapshot.service_tier != "standard":
                raise PolicyRouterError("DEGRADE_NOT_AUTHORIZED")
            # Standard→fallback still requires explicit degrade flag for safety.
            if not allow_degrade:
                raise PolicyRouterError(
                    "DEGRADE_NOT_AUTHORIZED",
                    "fallback requires allow_degrade authorization",
                )
            full_route = snapshot.allowed_fallbacks[0]
            used_fallback = True

        safety_upgrade = False
        if safety_upgrade_route:
            full_route = safety_upgrade_route
            safety_upgrade = True

        if (
            self.known_rate_routes is not None
            and full_route not in self.known_rate_routes
            and not unknown_rate_ok
        ):
            raise PolicyRouterError(
                "UNKNOWN_RATE", f"route {full_route} has no cost-rate mapping"
            )

        if estimated_cost_rmb is not None:
            estimated = Decimal(str(estimated_cost_rmb))
            if estimated > snapshot.cost_ceiling_rmb:
                raise PolicyRouterError(
                    "COST_CEILING_EXCEEDED",
                    f"estimated {estimated} exceeds ceiling {snapshot.cost_ceiling_rmb}",
                )

        provider, route_code = _split_route(full_route)
        return RouteDecision(
            model_policy_version_id=snapshot.model_policy_version_id,
            route_internal_code=route_code,
            snapshot=snapshot,
            used_fallback=used_fallback,
            safety_upgrade=safety_upgrade,
            surcharge_points=0,
            provider_internal_code=provider,
            service_tier=service_tier,
            metadata={
                "full_route": full_route,
                "trigger_kind": trigger_kind,
                "behavior_mode": behavior_mode or (
                    "locked_snapshot" if use_locked else "current_stable"
                ),
                "quality_gate_ref": snapshot.quality_gate_ref,
            },
        )

    def lock_snapshot(
        self,
        *,
        capability: str,
        service_tier: str,
        subscenario: str = "default",
        at: datetime | None = None,
    ) -> LockedPolicySnapshot:
        policy = self.effective_policy(
            capability=capability,
            service_tier=service_tier,
            subscenario=subscenario,
            at=at,
        )
        if policy is None:
            raise PolicyRouterError("NO_STABLE_POLICY")
        return self._snapshot_from_policy(policy)

    def public_quote_fields(self, snapshot: LockedPolicySnapshot) -> dict[str, Any]:
        return {
            "service_tier": snapshot.service_tier,
            "policy_version": str(snapshot.model_policy_version_id),
            "quality_gate_ref": snapshot.quality_gate_ref,
        }


ModelPolicyRouter = PolicyRouter


def create_policy_router(
    repo: ModelPolicyRepository | None = None,
    *,
    known_rate_routes: set[str] | None = None,
) -> PolicyRouter:
    return PolicyRouter(repo, known_rate_routes=known_rate_routes)


__all__ = [
    "BehaviorMode",
    "LockedPolicySnapshot",
    "ModelPolicyRouter",
    "PolicyAdmissionError",
    "PolicyRouter",
    "PolicyRouterError",
    "RouteDecision",
    "RouteSnapshot",
    "SelectedRoute",
    "create_policy_router",
]
