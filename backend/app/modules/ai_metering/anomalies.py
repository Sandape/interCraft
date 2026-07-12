"""REQ-061 US9 abnormal-consumption decisions (T117 / FR-084, FR-085).

Pure decision helpers for:

- single-task cost > capability trailing 7-day P95 × 2
- user hourly point consumption > 20% of the day's grant
- repeated failure consumption > 3 attempts

Protection may pause new work or force standard tier, but MUST preserve
query, cancel, and appeal paths (FR-085 / FR-089).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Iterable, Sequence


class AnomalyKind(StrEnum):
    TASK_COST_P95 = "task_cost_p95_x2"
    HOURLY_GRANT_SHARE = "hourly_grant_share"
    REPEATED_FAILURE = "repeated_failure"


class ProtectionAction(StrEnum):
    NONE = "none"
    WARN = "warn"
    FORCE_STANDARD_TIER = "force_standard_tier"
    PAUSE_NEW_TASKS = "pause_new_tasks"
    REQUIRE_STEP_UP = "require_step_up"


# Operations that must remain available under abnormal protection / budget stop.
PROTECTED_OPERATIONS = frozenset(
    {
        "query",
        "status",
        "cancel",
        "appeal",
        "ledger_read",
        "account_read",
        "task_read",
        "safety_fix",
        "reconciliation",
    }
)

TASK_COST_MULTIPLIER = Decimal("2")
HOURLY_GRANT_THRESHOLD = Decimal("0.20")
REPEATED_FAILURE_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class AnomalyTrigger:
    kind: AnomalyKind
    observed: Decimal | int
    threshold: Decimal | int
    detail: str


@dataclass(frozen=True, slots=True)
class AnomalyDecision:
    triggered: bool
    triggers: tuple[AnomalyTrigger, ...] = ()
    protection: ProtectionAction = ProtectionAction.NONE
    allowed_operations: frozenset[str] = field(default_factory=lambda: frozenset(PROTECTED_OPERATIONS))
    blocked_new_optional_tasks: bool = False

    def allows(self, operation: str) -> bool:
        op = operation.strip().lower()
        if op in PROTECTED_OPERATIONS:
            return True
        if not self.triggered:
            return True
        if self.protection in {
            ProtectionAction.PAUSE_NEW_TASKS,
            ProtectionAction.REQUIRE_STEP_UP,
        }:
            return op in PROTECTED_OPERATIONS
        return True


def percentile(values: Sequence[Decimal | int | float | str], p: float) -> Decimal | None:
    """Nearest-rank percentile; returns None when the sample is empty."""
    if not values:
        return None
    if not 0 < p <= 100:
        raise ValueError("percentile must be in (0, 100]")
    ordered = sorted(Decimal(str(v)) for v in values)
    # Nearest-rank: ceil(p/100 * n), clamped to [1, n]
    rank = max(1, min(len(ordered), int(-(-len(ordered) * p // 100))))
    return ordered[rank - 1]


def evaluate_task_cost_vs_p95(
    *,
    task_cost_rmb: Decimal | str | int | float,
    capability_costs_7d: Sequence[Decimal | int | float | str],
    multiplier: Decimal = TASK_COST_MULTIPLIER,
) -> AnomalyTrigger | None:
    """FR-084: task actual cost > capability near-7-day P95 × 2."""
    p95 = percentile(capability_costs_7d, 95)
    if p95 is None:
        return None
    threshold = (p95 * multiplier).quantize(Decimal("0.0000000001"))
    observed = Decimal(str(task_cost_rmb))
    if observed > threshold:
        return AnomalyTrigger(
            kind=AnomalyKind.TASK_COST_P95,
            observed=observed,
            threshold=threshold,
            detail=f"task_cost {observed} > p95 {p95} × {multiplier}",
        )
    return None


def evaluate_hourly_consumption(
    *,
    hourly_points_consumed: int,
    daily_grant_points: int,
    threshold_ratio: Decimal = HOURLY_GRANT_THRESHOLD,
) -> AnomalyTrigger | None:
    """FR-084: hourly consumption > 20% of the day's granted points."""
    if daily_grant_points < 0 or hourly_points_consumed < 0:
        raise ValueError("points must be non-negative")
    if daily_grant_points == 0:
        if hourly_points_consumed > 0:
            return AnomalyTrigger(
                kind=AnomalyKind.HOURLY_GRANT_SHARE,
                observed=hourly_points_consumed,
                threshold=0,
                detail="hourly consumption with zero daily grant",
            )
        return None
    threshold = (Decimal(daily_grant_points) * threshold_ratio).quantize(Decimal("0.01"))
    observed = Decimal(hourly_points_consumed)
    if observed > threshold:
        return AnomalyTrigger(
            kind=AnomalyKind.HOURLY_GRANT_SHARE,
            observed=observed,
            threshold=threshold,
            detail=f"hourly {observed} > {threshold_ratio} of grant {daily_grant_points}",
        )
    return None


def evaluate_repeated_failure_consumption(
    *,
    failure_charge_count: int,
    threshold: int = REPEATED_FAILURE_THRESHOLD,
) -> AnomalyTrigger | None:
    """FR-084: repeated failure consumption exceeds 3 attempts."""
    if failure_charge_count < 0:
        raise ValueError("failure_charge_count must be non-negative")
    if failure_charge_count > threshold:
        return AnomalyTrigger(
            kind=AnomalyKind.REPEATED_FAILURE,
            observed=failure_charge_count,
            threshold=threshold,
            detail=f"failure charges {failure_charge_count} > {threshold}",
        )
    return None


def decide_abnormal_protection(
    triggers: Iterable[AnomalyTrigger | None],
) -> AnomalyDecision:
    """Collapse triggers into a protection decision that preserves query/cancel/appeal."""
    active = tuple(t for t in triggers if t is not None)
    if not active:
        return AnomalyDecision(triggered=False)

    kinds = {t.kind for t in active}
    if AnomalyKind.TASK_COST_P95 in kinds or AnomalyKind.REPEATED_FAILURE in kinds:
        protection = ProtectionAction.PAUSE_NEW_TASKS
    elif AnomalyKind.HOURLY_GRANT_SHARE in kinds:
        protection = ProtectionAction.FORCE_STANDARD_TIER
    else:
        protection = ProtectionAction.WARN

    return AnomalyDecision(
        triggered=True,
        triggers=active,
        protection=protection,
        allowed_operations=frozenset(PROTECTED_OPERATIONS),
        blocked_new_optional_tasks=protection
        in {ProtectionAction.PAUSE_NEW_TASKS, ProtectionAction.REQUIRE_STEP_UP},
    )


def evaluate_abnormal_consumption(
    *,
    task_cost_rmb: Decimal | str | int | float | None = None,
    capability_costs_7d: Sequence[Decimal | int | float | str] = (),
    hourly_points_consumed: int = 0,
    daily_grant_points: int = 0,
    failure_charge_count: int = 0,
) -> AnomalyDecision:
    """Convenience evaluator composing the three FR-084 detectors."""
    triggers: list[AnomalyTrigger | None] = []
    if task_cost_rmb is not None:
        triggers.append(
            evaluate_task_cost_vs_p95(
                task_cost_rmb=task_cost_rmb,
                capability_costs_7d=capability_costs_7d,
            )
        )
    triggers.append(
        evaluate_hourly_consumption(
            hourly_points_consumed=hourly_points_consumed,
            daily_grant_points=daily_grant_points,
        )
    )
    triggers.append(
        evaluate_repeated_failure_consumption(
            failure_charge_count=failure_charge_count,
        )
    )
    return decide_abnormal_protection(triggers)


__all__ = [
    "AnomalyDecision",
    "AnomalyKind",
    "AnomalyTrigger",
    "HOURLY_GRANT_THRESHOLD",
    "PROTECTED_OPERATIONS",
    "ProtectionAction",
    "REPEATED_FAILURE_THRESHOLD",
    "TASK_COST_MULTIPLIER",
    "decide_abnormal_protection",
    "evaluate_abnormal_consumption",
    "evaluate_hourly_consumption",
    "evaluate_repeated_failure_consumption",
    "evaluate_task_cost_vs_p95",
    "percentile",
]
