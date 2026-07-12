"""REQ-061 beta experience entitlement projection (T052).

Computed read-model only — not proof of purchase. Commercial subscription
truth remains outside REQ-061 (see data-model §7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ServiceTier = Literal["standard", "quality"]

PLAN_LABEL = "Pro"
EXPERIENCE_BADGE = "新用户体验"
PARALLEL_AI_TASK_LIMIT = 2
HISTORY_DAYS = 90
SERVICE_TIERS: tuple[ServiceTier, ...] = ("standard", "quality")


@dataclass(frozen=True, slots=True)
class BetaEntitlement:
    """Pro + 新用户体验 projection for authenticated ordinary users."""

    plan_label: str = PLAN_LABEL
    experience_badge: str = EXPERIENCE_BADGE
    is_paid: bool = False
    parallel_ai_task_limit: int = PARALLEL_AI_TASK_LIMIT
    history_days: int = HISTORY_DAYS
    service_tiers: tuple[ServiceTier, ...] = SERVICE_TIERS

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_label": self.plan_label,
            "experience_badge": self.experience_badge,
            "is_paid": self.is_paid,
            "parallel_ai_task_limit": self.parallel_ai_task_limit,
            "history_days": self.history_days,
            "service_tiers": list(self.service_tiers),
        }


def get_beta_entitlement(*, is_admin: bool = False) -> BetaEntitlement:
    """Return the beta display entitlement.

    Admins keep their permission roles elsewhere; beta display does not grant
    or revoke admin privileges. Ordinary and admin users share the same Pro
    experience badge for metering UI consistency.
    """
    _ = is_admin
    return BetaEntitlement()


__all__ = [
    "EXPERIENCE_BADGE",
    "HISTORY_DAYS",
    "PARALLEL_AI_TASK_LIMIT",
    "PLAN_LABEL",
    "SERVICE_TIERS",
    "BetaEntitlement",
    "ServiceTier",
    "get_beta_entitlement",
]
