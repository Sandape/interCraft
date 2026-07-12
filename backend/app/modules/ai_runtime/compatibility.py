"""REQ-061 live-version registry, decoder/upcaster stubs, and quarantine (T023).

Versions outside the published matrix never silently decode — callers receive an
explicit quarantine decision (or ``VersionQuarantine``).
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping

ArtifactKind = Literal["checkpoint", "interrupt", "job"]
DecisionAction = Literal["accept", "upcast", "quarantine"]


@dataclass(frozen=True, slots=True)
class LiveVersionEntry:
    """Allowed versions for one capability (or ``*`` for shared defaults)."""

    capability: str
    behavior_versions: frozenset[str]
    payload_schema_versions: frozenset[str]
    checkpoint_versions: frozenset[str]
    interrupt_versions: frozenset[str]
    job_payload_versions: frozenset[str]


@dataclass(frozen=True, slots=True)
class CompatibilityDecision:
    action: DecisionAction
    reason: str
    kind: ArtifactKind
    from_version: str | None = None
    to_version: str | None = None
    capability: str | None = None
    payload: dict[str, Any] | None = None


class VersionQuarantine(ValueError):
    """Raised when a persisted artifact version is outside the live matrix."""

    def __init__(self, decision: CompatibilityDecision) -> None:
        self.decision = decision
        super().__init__(decision.reason)


def _fixture_path() -> Path:
    # backend/tests/fixtures/ai_live_version_matrix.json
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "ai_live_version_matrix.json"
    )


@lru_cache(maxsize=1)
def load_live_version_matrix() -> dict[str, Any]:
    path = _fixture_path()
    if not path.is_file():
        return {
            "schema_version": "1.0.0",
            "checkpoint_versions": [],
            "interrupt_versions": [],
            "job_payload_versions": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _versions_from_rows(rows: list[dict[str, Any]], *, key: str = "version") -> frozenset[str]:
    return frozenset(str(row[key]) for row in rows if key in row)


def build_live_version_registry(
    matrix: Mapping[str, Any] | None = None,
) -> dict[str, LiveVersionEntry]:
    """Map capability → allowed behavior / payload / checkpoint versions."""
    data = dict(matrix) if matrix is not None else load_live_version_matrix()
    checkpoint_rows = list(data.get("checkpoint_versions") or [])
    interrupt_rows = list(data.get("interrupt_versions") or [])
    job_rows = list(data.get("job_payload_versions") or [])

    by_capability: dict[str, dict[str, set[str]]] = {}

    def _bucket(cap: str) -> dict[str, set[str]]:
        if cap not in by_capability:
            by_capability[cap] = {
                "behavior": set(),
                "payload": set(),
                "checkpoint": set(),
                "interrupt": set(),
                "job": set(),
            }
        return by_capability[cap]

    for row in checkpoint_rows:
        cap = str(row.get("capability") or "*")
        bucket = _bucket(cap)
        version = str(row["version"])
        bucket["checkpoint"].add(version)
        bucket["behavior"].add(version)
        payload = row.get("payload") or {}
        if isinstance(payload, dict) and payload.get("schema_version") is not None:
            bucket["payload"].add(str(payload["schema_version"]))
        else:
            bucket["payload"].add(version)

    for row in interrupt_rows:
        cap = str(row.get("capability") or "*")
        bucket = _bucket(cap)
        version = str(row["version"])
        bucket["interrupt"].add(version)
        bucket["behavior"].add(version)
        payload = row.get("payload") or {}
        if isinstance(payload, dict) and payload.get("schema_version") is not None:
            bucket["payload"].add(str(payload["schema_version"]))

    for row in job_rows:
        # Job payloads are shared across capabilities unless annotated.
        cap = str(row.get("capability") or "*")
        bucket = _bucket(cap)
        version = str(row["version"])
        bucket["job"].add(version)
        bucket["behavior"].add(version)
        payload = row.get("payload") or {}
        if isinstance(payload, dict) and payload.get("schema_version") is not None:
            bucket["payload"].add(str(payload["schema_version"]))

    # Ensure a shared default row covering every matrix version.
    shared = _bucket("*")
    shared["checkpoint"] |= set(_versions_from_rows(checkpoint_rows))
    shared["interrupt"] |= set(_versions_from_rows(interrupt_rows))
    shared["job"] |= set(_versions_from_rows(job_rows))
    shared["behavior"] |= shared["checkpoint"] | shared["interrupt"] | shared["job"]
    shared["payload"] |= shared["behavior"]

    registry: dict[str, LiveVersionEntry] = {}
    for cap, buckets in by_capability.items():
        registry[cap] = LiveVersionEntry(
            capability=cap,
            behavior_versions=frozenset(buckets["behavior"]),
            payload_schema_versions=frozenset(buckets["payload"]),
            checkpoint_versions=frozenset(buckets["checkpoint"]),
            interrupt_versions=frozenset(buckets["interrupt"]),
            job_payload_versions=frozenset(buckets["job"]),
        )
    return registry


@lru_cache(maxsize=1)
def get_live_version_registry() -> dict[str, LiveVersionEntry]:
    return build_live_version_registry()


def resolve_live_versions(capability: str) -> LiveVersionEntry:
    registry = get_live_version_registry()
    if capability in registry:
        return registry[capability]
    return registry.get("*") or LiveVersionEntry(
        capability=capability,
        behavior_versions=frozenset(),
        payload_schema_versions=frozenset(),
        checkpoint_versions=frozenset(),
        interrupt_versions=frozenset(),
        job_payload_versions=frozenset(),
    )


def _allowed_for(kind: ArtifactKind, entry: LiveVersionEntry) -> frozenset[str]:
    if kind == "checkpoint":
        return entry.checkpoint_versions
    if kind == "interrupt":
        return entry.interrupt_versions
    return entry.job_payload_versions


def current_target_version(kind: ArtifactKind, capability: str | None = None) -> str | None:
    entry = resolve_live_versions(capability or "*")
    allowed = sorted(_allowed_for(kind, entry), key=lambda v: (len(v), v))
    return allowed[-1] if allowed else None


def evaluate_artifact_version(
    kind: ArtifactKind,
    version: str,
    *,
    capability: str | None = None,
) -> CompatibilityDecision:
    """Return accept / upcast / quarantine for one persisted artifact version."""
    entry = resolve_live_versions(capability or "*")
    allowed = _allowed_for(kind, entry)
    # Also consult shared ``*`` when capability-specific set is empty/partial.
    if capability and capability != "*":
        allowed = allowed | _allowed_for(kind, resolve_live_versions("*"))

    target = current_target_version(kind, capability)
    if version not in allowed:
        return CompatibilityDecision(
            action="quarantine",
            reason=f"{kind} version {version!r} outside live matrix",
            kind=kind,
            from_version=version,
            to_version=target,
            capability=capability,
        )
    if target is not None and version != target:
        return CompatibilityDecision(
            action="upcast",
            reason=f"{kind} version {version} requires N-1 upcast to {target}",
            kind=kind,
            from_version=version,
            to_version=target,
            capability=capability,
        )
    return CompatibilityDecision(
        action="accept",
        reason=f"{kind} version {version} is live",
        kind=kind,
        from_version=version,
        to_version=version,
        capability=capability,
    )


def quarantine_version(
    kind: ArtifactKind,
    version: str,
    *,
    capability: str | None = None,
    reason: str | None = None,
) -> CompatibilityDecision:
    """Explicit quarantine decision — never a silent decode path."""
    base = evaluate_artifact_version(kind, version, capability=capability)
    if base.action == "quarantine":
        if reason:
            return CompatibilityDecision(
                action="quarantine",
                reason=reason,
                kind=kind,
                from_version=version,
                to_version=base.to_version,
                capability=capability,
            )
        return base
    return CompatibilityDecision(
        action="quarantine",
        reason=reason or f"forced quarantine for {kind} version {version}",
        kind=kind,
        from_version=version,
        to_version=base.to_version,
        capability=capability,
    )


def _require_live(
    kind: ArtifactKind,
    version: str,
    *,
    capability: str | None,
) -> CompatibilityDecision:
    decision = evaluate_artifact_version(kind, version, capability=capability)
    if decision.action == "quarantine":
        raise VersionQuarantine(decision)
    return decision


def decode_checkpoint(
    payload: Mapping[str, Any] | dict[str, Any],
    *,
    version: str,
    capability: str | None = None,
) -> dict[str, Any]:
    """Decode a checkpoint payload; quarantine versions outside the matrix."""
    _require_live("checkpoint", version, capability=capability)
    if not isinstance(payload, Mapping):
        raise TypeError("checkpoint payload must be a mapping")
    decoded = deepcopy(dict(payload))
    decoded.setdefault("schema_version", str(version))
    return decoded


def decode_interrupt(
    payload: Mapping[str, Any] | dict[str, Any],
    *,
    version: str,
    capability: str | None = None,
) -> dict[str, Any]:
    _require_live("interrupt", version, capability=capability)
    if not isinstance(payload, Mapping):
        raise TypeError("interrupt payload must be a mapping")
    decoded = deepcopy(dict(payload))
    decoded.setdefault("schema_version", str(version))
    return decoded


def decode_job_payload(
    payload: Mapping[str, Any] | dict[str, Any],
    *,
    version: str,
    capability: str | None = None,
) -> dict[str, Any]:
    _require_live("job", version, capability=capability)
    if not isinstance(payload, Mapping):
        raise TypeError("job payload must be a mapping")
    decoded = deepcopy(dict(payload))
    decoded.setdefault("schema_version", str(version))
    return decoded


def upcast_payload(
    decoded: Mapping[str, Any] | dict[str, Any],
    *,
    from_version: str,
    kind: ArtifactKind = "checkpoint",
    capability: str | None = None,
) -> dict[str, Any]:
    """N-1 upcaster stub — stamps the current target schema_version."""
    decision = evaluate_artifact_version(kind, from_version, capability=capability)
    if decision.action == "quarantine":
        raise VersionQuarantine(decision)
    target = decision.to_version or from_version
    out = deepcopy(dict(decoded))
    out["schema_version"] = str(target)
    out["_upcast_from"] = str(from_version)
    if kind == "checkpoint" and str(from_version) == "1" and str(target) == "2":
        state = out.get("state")
        if isinstance(state, dict) and "scores" not in state:
            state = dict(state)
            state["scores"] = []
            out["state"] = state
    return out


def decode_or_quarantine(
    kind: ArtifactKind,
    payload: Mapping[str, Any] | dict[str, Any],
    *,
    version: str,
    capability: str | None = None,
) -> CompatibilityDecision:
    """Decode when live; otherwise return an explicit quarantine decision."""
    decision = evaluate_artifact_version(kind, version, capability=capability)
    if decision.action == "quarantine":
        return decision
    if kind == "checkpoint":
        decoded = decode_checkpoint(payload, version=version, capability=capability)
    elif kind == "interrupt":
        decoded = decode_interrupt(payload, version=version, capability=capability)
    else:
        decoded = decode_job_payload(payload, version=version, capability=capability)
    if decision.action == "upcast":
        decoded = upcast_payload(
            decoded, from_version=version, kind=kind, capability=capability
        )
    return CompatibilityDecision(
        action=decision.action,
        reason=decision.reason,
        kind=kind,
        from_version=version,
        to_version=decision.to_version,
        capability=capability,
        payload=decoded,
    )


__all__ = [
    "ArtifactKind",
    "CompatibilityDecision",
    "DecisionAction",
    "LiveVersionEntry",
    "VersionQuarantine",
    "build_live_version_registry",
    "current_target_version",
    "decode_checkpoint",
    "decode_interrupt",
    "decode_job_payload",
    "decode_or_quarantine",
    "evaluate_artifact_version",
    "get_live_version_registry",
    "load_live_version_matrix",
    "quarantine_version",
    "resolve_live_versions",
    "upcast_payload",
]
