"""Per-capability plan for fixture expansion.

Drive the matrix expansion. ``(target_count, distribution)`` is read by
``expand_all_capabilities`` to know how many synthetic cases each capability
needs and how many must hit each ``case_class``.

Rules (frozen for FR-112):

- ordinary capabilities (no WRITE_FACT_CHARGING): total == 30, every class
  represented.
- WRITE_FACT_CHARGING capabilities: total == 50, every class represented,
  with adversarial ≥ 6 (P0/P1 risk class requires adversarial coverage).
- hand-written seed cases (``specs/061.../eval-cases/...``) count
  toward these totals — they are folded in by
  :func:`tests.eval._gen.expansion.expand_all_capabilities`.

Sync note: this table is the only authoritative declaration of expansion
strategy. ``test_061_eval_dataset_coverage`` re-derives totals from the
expanded list so any drift surfaces as a test failure.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TierPlan:
    """Expansion plan for one capability."""

    capability_code: str
    target_count: int            # FR-112 = 30 ordinary, 50 writing-tier
    distribution: dict[str, int]  # case_class → target synthetic count


# WRITE / fact / charging capabilities (FR-112 ≥ 50).
# Pinned to capability_registry.WRITE_FACT_CHARGING_CAPABILITIES for cohesion.
WRITE_TIER_CAPABILITIES: tuple[str, ...] = (
    "resume_intelligence",
    "resume_derive",
    "interview",
    "wechat_agent",
    "proactive_research",
    "point_safety",
)

# Ordinary capabilities (FR-112 ≥ 30).
ORDINARY_TIER_CAPABILITIES: tuple[str, ...] = (
    "general_coach",
    "error_coach",
    "ability_insight",
    "failure_recovery",
    "privacy",
)

# Standard 5-class distribution. Production teams MUST keep this in sync with
# REQUIRED_CASE_CLASSES in capability_registry.py; the test asserts parity.
_BASE_DISTRIBUTION: dict[str, int] = {
    "normal": 12,
    "boundary": 6,
    "failure": 5,
    "privacy": 4,
    "adversarial": 3,
}

_WRITE_DISTRIBUTION: dict[str, int] = {
    "normal": 18,
    "boundary": 10,
    "failure": 10,
    "privacy": 6,
    "adversarial": 6,
}


def _plan_for(capability: str) -> TierPlan:
    if capability in WRITE_TIER_CAPABILITIES:
        return TierPlan(
            capability_code=capability,
            target_count=50,
            distribution=_WRITE_DISTRIBUTION,
        )
    return TierPlan(
        capability_code=capability,
        target_count=30,
        distribution=_BASE_DISTRIBUTION,
    )


TIER_PLAN: dict[str, TierPlan] = {
    cap: _plan_for(cap)
    for cap in WRITE_TIER_CAPABILITIES + ORDINARY_TIER_CAPABILITIES
}


__all__ = [
    "ORDINARY_TIER_CAPABILITIES",
    "TIER_PLAN",
    "TierPlan",
    "WRITE_TIER_CAPABILITIES",
]
