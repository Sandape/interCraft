"""REQ-061 US9 production AI Operations helpers (T118 light-touch).

Additive schemas/builders for metrics, budgets, reconciliations, and
task-cost drilldown. Does not alter existing REQ-044 seed endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agent_observability.projections import (
    OperationalFacts,
    aggregate_operational_metrics,
)
from app.modules.ai_metering.budgets import BudgetDefinition, evaluate_budget
from app.modules.ai_metering.reconciliation.service import ReconciliationResult


class DecimalMoney(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: str
    currency: str = "CNY"


class DataQualityOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fresh_at: datetime
    coverage_percent: float
    unknown_count: int
    seed_or_mock_count: int = 0


class MetricsResponseOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stability: dict[str, Any]
    quality: dict[str, Any]
    latency: dict[str, Any]
    points: dict[str, Any]
    cost: dict[str, Any]
    revenue_rmb: DecimalMoney
    data_quality: DataQualityOut


class BudgetOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_id: str
    scope_type: str
    scope_ref: str
    period: str
    amount_rmb: DecimalMoney
    consumed_rmb: DecimalMoney
    utilization_percent: str
    level: str
    warning_reached: bool
    hard_limit_reached: bool
    stop_new_optional_tasks: bool


class ReconciliationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_type: str
    status: str
    expected_total: str | None = None
    actual_total: str | None = None
    difference: str | None = None
    difference_pct: str | None = None
    issue_count: int = 0
    issues: list[dict[str, Any]] = Field(default_factory=list)


class TaskCostDrilldownOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    point_settled: int
    cost_status: str
    current_cost_rmb: DecimalMoney
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    data_quality: DataQualityOut


def empty_metrics(*, as_of: datetime | None = None) -> MetricsResponseOut:
    moment = as_of or datetime.now(timezone.utc)
    raw = aggregate_operational_metrics(OperationalFacts(as_of=moment))
    dq = raw["data_quality"]
    return MetricsResponseOut(
        stability=raw["stability"],
        quality=raw["quality"],
        latency=raw["latency"],
        points=raw["points"],
        cost=raw["cost"],
        revenue_rmb=DecimalMoney(amount="0", currency="CNY"),
        data_quality=DataQualityOut(
            fresh_at=datetime.fromisoformat(dq["fresh_at"].replace("Z", "+00:00"))
            if isinstance(dq["fresh_at"], str)
            else moment,
            coverage_percent=dq["coverage_percent"],
            unknown_count=dq["unknown_count"],
            seed_or_mock_count=0,
        ),
    )


def budget_to_out(budget: BudgetDefinition, *, consumed_rmb: Decimal) -> BudgetOut:
    ev = evaluate_budget(budget, consumed_rmb=consumed_rmb)
    return BudgetOut(
        budget_id=ev.budget_id,
        scope_type=ev.scope_type,
        scope_ref=ev.scope_ref,
        period=ev.period,
        amount_rmb=DecimalMoney(amount=str(ev.limit_rmb), currency="CNY"),
        consumed_rmb=DecimalMoney(amount=str(ev.consumed_rmb), currency="CNY"),
        utilization_percent=str(ev.utilization_percent),
        level=ev.level.value,
        warning_reached=ev.warning_reached,
        hard_limit_reached=ev.hard_limit_reached,
        stop_new_optional_tasks=ev.stop_new_optional_tasks,
    )


def reconciliation_to_out(result: ReconciliationResult) -> ReconciliationOut:
    return ReconciliationOut(
        run_type=result.run_type,
        status=result.status,
        expected_total=str(result.expected_total) if result.expected_total is not None else None,
        actual_total=str(result.actual_total) if result.actual_total is not None else None,
        difference=str(result.difference) if result.difference is not None else None,
        difference_pct=str(result.difference_pct) if result.difference_pct is not None else None,
        issue_count=len(result.issues),
        issues=[
            {
                "issue_class": str(i.issue_class),
                "severity": i.severity,
                "affected_identities": i.affected_identities,
                "status": str(i.status),
            }
            for i in result.issues
        ],
    )


__all__ = [
    "BudgetOut",
    "DataQualityOut",
    "DecimalMoney",
    "MetricsResponseOut",
    "ReconciliationOut",
    "TaskCostDrilldownOut",
    "budget_to_out",
    "empty_metrics",
    "reconciliation_to_out",
]
