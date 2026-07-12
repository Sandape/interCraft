"""REQ-061 US7 — effective-dated model policy repository (T104)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.ids import new_uuid_v7

POLICY_STATUSES = frozenset(
    {"draft", "candidate", "gray", "stable", "stopped", "retired", "rolled_back"}
)

_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"candidate", "retired"}),
    "candidate": frozenset({"gray", "retired", "draft"}),
    "gray": frozenset({"stable", "stopped", "retired"}),
    "stable": frozenset({"stopped", "retired", "rolled_back"}),
    "stopped": frozenset({"retired", "candidate"}),
    "retired": frozenset(),
    "rolled_back": frozenset({"retired"}),
}


class PolicyRepositoryError(ValueError):
    """Illegal policy transition or conflict."""


@dataclass
class ModelPolicyRecord:
    id: UUID
    capability: str
    subscenario: str
    service_tier: str
    primary_route: str
    allowed_fallbacks: list[str]
    quality_gate_ref: str
    latency_target_ms: int
    cost_ceiling_rmb: Decimal
    rollback_target: str | None
    owner: str
    reason: str
    status: str = "draft"
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    evaluation_ref: str | None = None
    traffic_percent: int | float = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def policy_version(self) -> str:
        return str(self.id)

    # Aliases used by older call sites
    @property
    def capability_code(self) -> str:
        return self.capability

    @property
    def permitted_fallbacks(self) -> list[str]:
        return self.allowed_fallbacks

    @property
    def rollback_target_id(self) -> str | None:
        return self.rollback_target


class ModelPolicyRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, ModelPolicyRecord] = {}

    def clear(self) -> None:
        self._items.clear()

    def list_all(self) -> list[ModelPolicyRecord]:
        return sorted(self._items.values(), key=lambda p: p.created_at, reverse=True)

    def list(
        self,
        *,
        capability_code: str | None = None,
        service_tier: str | None = None,
        status: str | None = None,
    ) -> list[ModelPolicyRecord]:
        items = self.list_all()
        if capability_code:
            items = [p for p in items if p.capability == capability_code]
        if service_tier:
            items = [p for p in items if p.service_tier == service_tier]
        if status:
            items = [p for p in items if p.status == status]
        return items

    def get(self, policy_id: UUID | str) -> ModelPolicyRecord | None:
        key = policy_id if isinstance(policy_id, UUID) else UUID(str(policy_id))
        return self._items.get(key)

    def create(self, command: dict[str, Any] | None = None, **kwargs: Any) -> ModelPolicyRecord:
        data = dict(command or {})
        data.update(kwargs)
        ceiling = data["cost_ceiling_rmb"]
        if isinstance(ceiling, dict):
            ceiling = Decimal(str(ceiling["amount"]))
        else:
            ceiling = Decimal(str(ceiling))
        if ceiling < 0:
            raise PolicyRepositoryError("cost_ceiling_rmb must be non-negative")
        status = str(data.get("status") or "draft")
        if status not in POLICY_STATUSES:
            raise PolicyRepositoryError(f"unknown status: {status}")
        item = ModelPolicyRecord(
            id=new_uuid_v7(),
            capability=str(data.get("capability") or data.get("capability_code")),
            subscenario=str(data.get("subscenario") or "default"),
            service_tier=str(data["service_tier"]),
            primary_route=str(data["primary_route"]),
            allowed_fallbacks=list(
                data.get("allowed_fallbacks") or data.get("permitted_fallbacks") or []
            ),
            quality_gate_ref=str(data["quality_gate_ref"]),
            latency_target_ms=int(data["latency_target_ms"]),
            cost_ceiling_rmb=ceiling,
            rollback_target=(
                str(data["rollback_target"])
                if data.get("rollback_target") is not None
                else None
            ),
            owner=str(data["owner"]),
            reason=str(data["reason"]),
            status=status,
            evaluation_ref=data.get("evaluation_ref") or data.get("eval_evidence_ref"),
            metadata=dict(data.get("metadata") or {}),
        )
        self._items[item.id] = item
        return item

    def transition(
        self,
        policy_id: UUID | str,
        *,
        target_status: str,
        reason: str | None = None,
        rollback_target: str | None = None,
        eval_evidence_ref: str | None = None,
        traffic_percent: int | float | None = None,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        actor: str | None = None,
    ) -> ModelPolicyRecord:
        item = self.get(policy_id)
        if item is None:
            raise PolicyRepositoryError(f"unknown policy: {policy_id}")
        if target_status not in POLICY_STATUSES:
            raise PolicyRepositoryError(f"unknown status: {target_status}")
        allowed = _TRANSITIONS.get(item.status, frozenset())
        if target_status not in allowed and target_status != item.status:
            raise PolicyRepositoryError(
                f"cannot transition {item.status} -> {target_status}"
            )

        if target_status in {"gray", "stable"}:
            evidence = eval_evidence_ref or item.evaluation_ref
            if not evidence:
                raise PolicyRepositoryError("eval_evidence_ref required")
            item.evaluation_ref = evidence
            rb = rollback_target if rollback_target is not None else item.rollback_target
            if not rb:
                raise PolicyRepositoryError("rollback_target required")
            item.rollback_target = str(rb)

        if rollback_target is not None:
            item.rollback_target = str(rollback_target)
        if eval_evidence_ref is not None:
            item.evaluation_ref = eval_evidence_ref
        if reason is not None:
            item.reason = reason
        if traffic_percent is not None:
            item.traffic_percent = traffic_percent
        if actor:
            item.metadata["last_actor"] = actor

        if target_status == "stable":
            now = effective_from or datetime.now(timezone.utc)
            for other in list(self._items.values()):
                if other.id == item.id:
                    continue
                if other.status != "stable":
                    continue
                if other.capability != item.capability:
                    continue
                if other.subscenario != item.subscenario:
                    continue
                if other.service_tier != item.service_tier:
                    continue
                other.status = "stopped"
                other.effective_to = now
                self._items[other.id] = other
            item.effective_from = now
            item.effective_to = effective_to
            if item.traffic_percent == 0:
                item.traffic_percent = 100
        elif target_status == "gray":
            item.effective_from = effective_from or datetime.now(timezone.utc)

        item.status = target_status
        self._items[item.id] = item
        return item

    def find_effective(
        self,
        *,
        capability_code: str,
        subscenario: str,
        service_tier: str,
        at: datetime | None = None,
    ) -> ModelPolicyRecord | None:
        moment = at or datetime.now(timezone.utc)
        candidates = [
            p
            for p in self._items.values()
            if p.status in {"stable", "gray"}
            and p.capability == capability_code
            and p.service_tier == service_tier
            and p.subscenario == subscenario
            and (p.effective_from is None or p.effective_from <= moment)
            and (p.effective_to is None or p.effective_to > moment)
        ]
        if not candidates:
            return None
        preferred = [p for p in candidates if p.status == "stable"] or candidates
        return sorted(
            preferred, key=lambda p: p.effective_from or p.created_at, reverse=True
        )[0]


_DEFAULT_REPO: ModelPolicyRepository | None = None


def get_default_policy_repository() -> ModelPolicyRepository:
    global _DEFAULT_REPO
    if _DEFAULT_REPO is None:
        _DEFAULT_REPO = ModelPolicyRepository()
    return _DEFAULT_REPO


def reset_default_policy_repository() -> ModelPolicyRepository:
    global _DEFAULT_REPO
    _DEFAULT_REPO = ModelPolicyRepository()
    return _DEFAULT_REPO


ModelPolicyVersion = ModelPolicyRecord
ModelPolicyConflictError = PolicyRepositoryError

__all__ = [
    "POLICY_STATUSES",
    "ModelPolicyConflictError",
    "ModelPolicyRecord",
    "ModelPolicyRepository",
    "ModelPolicyVersion",
    "PolicyRepositoryError",
    "get_default_policy_repository",
    "reset_default_policy_repository",
]
