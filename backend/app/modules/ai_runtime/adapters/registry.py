"""REQ-061 versioned capability adapter registry (T031)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.modules.ai_runtime.adapters.contracts import (
    AcceptanceEnvelope,
    AdapterError,
    CapabilityActionSpec,
    MilestoneSpec,
    validate_acceptance_envelope,
)

_DEFAULT_POINTS = {
    "resume_derive:derive": 300,
    "resume_intelligence:analyze": 120,
    "resume_intelligence:suggest": 80,
    "interview:start": 200,
    "interview:conduct": 200,
    "general_coach:chat": 40,
    "error_coach:drill": 60,
    "ability_insight:diagnose": 100,
    "proactive_research:research": 250,
    "wechat_agent:run": 50,
}


def _fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "tests"
        / "fixtures"
        / "ai_capability_registry.json"
    )


def _split_points(total: int, codes: list[str]) -> list[tuple[int, int]]:
    """Return (weight_bps, max_points) per milestone summing to 10000 / total."""
    n = max(1, len(codes))
    base_w = 10000 // n
    weights = [base_w] * n
    weights[-1] += 10000 - sum(weights)
    base_p = total // n
    points = [base_p] * n
    points[-1] += total - sum(points)
    return list(zip(weights, points, strict=True))


@lru_cache(maxsize=1)
def load_registry() -> dict[tuple[str, str], CapabilityActionSpec]:
    path = _fixture_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], CapabilityActionSpec] = {}
    for entry in raw.get("entries", []):
        cap = entry["capability_code"]
        act = entry["action_code"]
        key = f"{cap}:{act}"
        total = _DEFAULT_POINTS.get(key, 100)
        codes: list[str] = list(entry.get("milestones") or ["delivery"])
        splits = _split_points(total, codes)
        milestones = tuple(
            MilestoneSpec(
                code=code,
                label=code.replace("_", " ").title(),
                weight_basis_points=w,
                max_points=p,
            )
            for code, (w, p) in zip(codes, splits, strict=True)
        )
        spec = CapabilityActionSpec(
            capability_code=cap,
            action_code=act,
            engine_kind=entry.get("engine_kind", "synchronous_adapter"),
            tiers=tuple(entry.get("tiers") or ["standard"]),
            milestones=milestones,
            rollout_status=entry.get("rollout_status", "shadow"),
            owners=tuple(entry.get("owners") or []),
            runbooks=entry.get("runbooks"),
        )
        out[(cap, act)] = spec
    return out


def get_capability_action(capability: str, action: str) -> CapabilityActionSpec:
    registry = load_registry()
    try:
        return registry[(capability, action)]
    except KeyError as exc:
        raise AdapterError(f"unknown capability/action: {capability}/{action}") from exc


def canonical_input_hash(ref: str, payload: dict[str, Any] | None = None) -> str:
    body = {"ref": ref, "payload": payload or {}}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_acceptance_envelope(
    *,
    capability: str,
    action: str,
    service_tier: str,
    input_snapshot_ref: str,
    allow_degrade: bool,
    input_payload: dict[str, Any] | None = None,
) -> AcceptanceEnvelope:
    spec = get_capability_action(capability, action)
    if service_tier not in spec.tiers:
        raise AdapterError(f"tier {service_tier} not permitted for {capability}/{action}")
    if spec.rollout_status == "disabled":
        raise AdapterError(f"{capability}/{action} is disabled")
    envelope = AcceptanceEnvelope(
        capability_code=capability,
        action_code=action,
        service_tier=service_tier,
        input_snapshot_ref=input_snapshot_ref,
        input_canonical_hash=canonical_input_hash(input_snapshot_ref, input_payload),
        allow_degrade=allow_degrade,
        milestones=spec.milestones,
        max_points=sum(m.max_points for m in spec.milestones),
        metadata={"engine_kind": spec.engine_kind, "rollout_status": spec.rollout_status},
    )
    validate_acceptance_envelope(envelope)
    return envelope


__all__ = [
    "build_acceptance_envelope",
    "canonical_input_hash",
    "get_capability_action",
    "load_registry",
]
