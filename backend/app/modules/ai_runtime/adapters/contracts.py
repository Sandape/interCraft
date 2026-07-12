"""REQ-061 capability adapter contracts (T031)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class MilestoneSpec:
    code: str
    label: str
    weight_basis_points: int
    max_points: int


@dataclass(frozen=True, slots=True)
class CapabilityActionSpec:
    capability_code: str
    action_code: str
    engine_kind: str
    tiers: tuple[str, ...]
    milestones: tuple[MilestoneSpec, ...]
    rollout_status: str
    owners: tuple[str, ...] = ()
    runbooks: str | None = None


@dataclass(frozen=True, slots=True)
class AcceptanceEnvelope:
    """Canonical acceptance payload every capability adapter must produce."""

    capability_code: str
    action_code: str
    service_tier: str
    input_snapshot_ref: str
    input_canonical_hash: str
    allow_degrade: bool
    milestones: tuple[MilestoneSpec, ...]
    max_points: int
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityAdapter(Protocol):
    spec: CapabilityActionSpec

    def build_acceptance_envelope(
        self,
        *,
        service_tier: str,
        input_snapshot_ref: str,
        allow_degrade: bool,
        input_payload: dict[str, Any] | None = None,
    ) -> AcceptanceEnvelope: ...


class AdapterError(ValueError):
    """Raised when an acceptance envelope is invalid or capability unknown."""


def validate_acceptance_envelope(envelope: AcceptanceEnvelope) -> None:
    if not envelope.capability_code or not envelope.action_code:
        raise AdapterError("capability and action required")
    if envelope.service_tier not in {"standard", "quality"}:
        raise AdapterError("invalid service_tier")
    if not envelope.input_canonical_hash:
        raise AdapterError("input_canonical_hash required")
    weights = sum(m.weight_basis_points for m in envelope.milestones)
    if envelope.milestones and weights != 10000:
        raise AdapterError(f"milestone weights must sum to 10000, got {weights}")
    if envelope.max_points < 0:
        raise AdapterError("max_points must be non-negative")
    points = sum(m.max_points for m in envelope.milestones)
    if points != envelope.max_points:
        raise AdapterError("max_points must equal sum of milestone max_points")


__all__ = [
    "AcceptanceEnvelope",
    "AdapterError",
    "CapabilityActionSpec",
    "CapabilityAdapter",
    "MilestoneSpec",
    "validate_acceptance_envelope",
]
