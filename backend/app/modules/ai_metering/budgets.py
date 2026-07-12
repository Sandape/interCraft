"""REQ-061 US9 cost budgets (T117 / FR-088, FR-089).

Site / capability / model_policy / point_config / user budgets with:
- 80% warning
- 100% stop of new *optional* tasks

Protected operations (query, cancel, appeal, safety fix, reconciliation)
must never be blocked by budget exhaustion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4

from app.modules.ai_metering.anomalies import PROTECTED_OPERATIONS


class BudgetScopeType(StrEnum):
    SITE = "site"
    CAPABILITY = "capability"
    MODEL_POLICY = "model_policy"
    POINT_CONFIG = "point_config"
    USER = "user"


class BudgetPeriod(StrEnum):
    DAY = "day"
    MONTH = "month"


class BudgetLevel(StrEnum):
    OK = "ok"
    WARNING = "warning"
    EXHAUSTED = "exhausted"


WARNING_PERCENT = Decimal("80")
HARD_LIMIT_PERCENT = Decimal("100")


@dataclass(frozen=True, slots=True)
class BudgetDefinition:
    scope_type: BudgetScopeType | str
    scope_ref: str
    period: BudgetPeriod | str
    amount_rmb: Decimal
    warning_percent: Decimal = WARNING_PERCENT
    version: int = 1
    budget_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.amount_rmb < 0:
            raise ValueError("amount_rmb must be non-negative")
        if self.warning_percent != WARNING_PERCENT:
            # Contract locks warning_percent at 80.
            raise ValueError("warning_percent must be 80")


@dataclass(frozen=True, slots=True)
class BudgetEvaluation:
    budget_id: str
    scope_type: str
    scope_ref: str
    period: str
    limit_rmb: Decimal
    consumed_rmb: Decimal
    utilization_percent: Decimal
    level: BudgetLevel
    warning_reached: bool
    hard_limit_reached: bool
    stop_new_optional_tasks: bool

    def allows(self, operation: str) -> bool:
        op = operation.strip().lower()
        if op in PROTECTED_OPERATIONS:
            return True
        if self.stop_new_optional_tasks and op in {
            "submit_optional_task",
            "start_optional_task",
            "enqueue_optional",
            "new_optional_task",
        }:
            return False
        if self.hard_limit_reached and op in {
            "submit_task",
            "start_task",
            "enqueue_task",
            "new_task",
            "optional_quality_tier",
        }:
            # Optional / new work blocked; protected ops already returned True.
            return False
        return True


def utilization_percent(*, consumed_rmb: Decimal, limit_rmb: Decimal) -> Decimal:
    if limit_rmb < 0 or consumed_rmb < 0:
        raise ValueError("amounts must be non-negative")
    if limit_rmb == 0:
        return Decimal("100") if consumed_rmb > 0 else Decimal("0")
    return (consumed_rmb / limit_rmb * Decimal("100")).quantize(Decimal("0.0001"))


def evaluate_budget(
    budget: BudgetDefinition,
    *,
    consumed_rmb: Decimal | str | int | float,
) -> BudgetEvaluation:
    consumed = Decimal(str(consumed_rmb))
    util = utilization_percent(consumed_rmb=consumed, limit_rmb=budget.amount_rmb)
    warning = util >= budget.warning_percent
    hard = util >= HARD_LIMIT_PERCENT
    if hard:
        level = BudgetLevel.EXHAUSTED
    elif warning:
        level = BudgetLevel.WARNING
    else:
        level = BudgetLevel.OK
    return BudgetEvaluation(
        budget_id=budget.budget_id,
        scope_type=str(budget.scope_type),
        scope_ref=budget.scope_ref,
        period=str(budget.period),
        limit_rmb=budget.amount_rmb,
        consumed_rmb=consumed,
        utilization_percent=util,
        level=level,
        warning_reached=warning,
        hard_limit_reached=hard,
        stop_new_optional_tasks=hard,
    )


def evaluate_budgets(
    budgets: list[BudgetDefinition],
    *,
    consumption_by_key: dict[tuple[str, str], Decimal],
) -> list[BudgetEvaluation]:
    results: list[BudgetEvaluation] = []
    for budget in budgets:
        key = (str(budget.scope_type), budget.scope_ref)
        consumed = consumption_by_key.get(key, Decimal("0"))
        results.append(evaluate_budget(budget, consumed_rmb=consumed))
    return results


def any_budget_blocks_optional(evaluations: list[BudgetEvaluation]) -> bool:
    return any(e.stop_new_optional_tasks for e in evaluations)


def budget_command_from_payload(payload: dict[str, Any]) -> BudgetDefinition:
    """Build a BudgetDefinition from OpenAPI BudgetCommand shape."""
    amount = payload.get("amount_rmb")
    if isinstance(amount, dict):
        amount_value = Decimal(str(amount["amount"]))
    else:
        amount_value = Decimal(str(amount))
    warning = payload.get("warning_percent", 80)
    return BudgetDefinition(
        scope_type=str(payload["scope_type"]),
        scope_ref=str(payload["scope_ref"]),
        period=str(payload["period"]),
        amount_rmb=amount_value,
        warning_percent=Decimal(str(warning)),
    )


__all__ = [
    "BudgetDefinition",
    "BudgetEvaluation",
    "BudgetLevel",
    "BudgetPeriod",
    "BudgetScopeType",
    "HARD_LIMIT_PERCENT",
    "WARNING_PERCENT",
    "any_budget_blocks_optional",
    "budget_command_from_payload",
    "evaluate_budget",
    "evaluate_budgets",
    "utilization_percent",
]
