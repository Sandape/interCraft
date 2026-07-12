"""REQ-061 US9 budget evaluation + abnormal-consumption guard worker (T119).

Evaluates site/capability/user budgets (80% warn / 100% stop optional) and
abnormal-consumption detectors. Never blocks query/cancel/appeal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.logging import get_logger
from app.modules.ai_metering.anomalies import (
    PROTECTED_OPERATIONS,
    evaluate_abnormal_consumption,
)
from app.modules.ai_metering.budgets import (
    BudgetDefinition,
    any_budget_blocks_optional,
    evaluate_budgets,
)

log = get_logger("workers.ai_cost_guard")


def _budget_from_dict(raw: dict[str, Any]) -> BudgetDefinition:
    return BudgetDefinition(
        scope_type=str(raw["scope_type"]),
        scope_ref=str(raw["scope_ref"]),
        period=str(raw.get("period", "day")),
        amount_rmb=Decimal(str(raw["amount_rmb"])),
        warning_percent=Decimal(str(raw.get("warning_percent", 80))),
        version=int(raw.get("version", 1)),
        budget_id=str(raw.get("budget_id") or raw.get("id") or "budget"),
    )


async def run_ai_cost_guard(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate budgets + anomaly signals from ctx payloads (or empty defaults)."""
    payload = ctx or {}
    now = datetime.now(timezone.utc)

    budgets_raw = list(payload.get("budgets") or [])
    consumption = {
        (str(k[0]), str(k[1])): Decimal(str(v))
        for k, v in (payload.get("consumption_by_key") or {}).items()
    }
    # Also accept flat list of {scope_type, scope_ref, consumed_rmb}
    for row in payload.get("consumption") or []:
        key = (str(row["scope_type"]), str(row["scope_ref"]))
        consumption[key] = Decimal(str(row["consumed_rmb"]))

    budgets = [_budget_from_dict(b) for b in budgets_raw]
    evaluations = evaluate_budgets(budgets, consumption_by_key=consumption) if budgets else []

    anomaly_input = payload.get("anomaly") or {}
    decision = evaluate_abnormal_consumption(
        task_cost_rmb=anomaly_input.get("task_cost_rmb"),
        capability_costs_7d=list(anomaly_input.get("capability_costs_7d") or []),
        hourly_points_consumed=int(anomaly_input.get("hourly_points_consumed") or 0),
        daily_grant_points=int(anomaly_input.get("daily_grant_points") or 0),
        failure_charge_count=int(anomaly_input.get("failure_charge_count") or 0),
    )

    alerts: list[dict[str, Any]] = []
    for ev in evaluations:
        if ev.warning_reached and not ev.hard_limit_reached:
            alerts.append(
                {
                    "type": "budget_warning",
                    "budget_id": ev.budget_id,
                    "utilization_percent": str(ev.utilization_percent),
                }
            )
        if ev.hard_limit_reached:
            alerts.append(
                {
                    "type": "budget_exhausted",
                    "budget_id": ev.budget_id,
                    "utilization_percent": str(ev.utilization_percent),
                    "stop_new_optional_tasks": True,
                }
            )
    if decision.triggered:
        alerts.append(
            {
                "type": "abnormal_consumption",
                "protection": decision.protection.value,
                "triggers": [
                    {
                        "kind": t.kind.value,
                        "observed": str(t.observed),
                        "threshold": str(t.threshold),
                    }
                    for t in decision.triggers
                ],
            }
        )

    summary = {
        "ts": now.isoformat(),
        "budget_count": len(evaluations),
        "stop_new_optional_tasks": any_budget_blocks_optional(evaluations)
        or decision.blocked_new_optional_tasks,
        "anomaly_triggered": decision.triggered,
        "protected_operations": sorted(PROTECTED_OPERATIONS),
        "alerts": alerts,
        # Explicit proof that protected paths stay open.
        "allows_query": True,
        "allows_cancel": True,
        "allows_appeal": True,
    }
    if alerts:
        log.warning("ai_cost_guard.alerts", alert_count=len(alerts), **{k: summary[k] for k in ("stop_new_optional_tasks", "anomaly_triggered")})
    else:
        log.info("ai_cost_guard.ok", **{k: summary[k] for k in ("budget_count", "anomaly_triggered")})
    return summary


async def ai_cost_guard(ctx: dict[str, Any]) -> dict[str, Any]:
    return await run_ai_cost_guard(ctx)


__all__ = ["ai_cost_guard", "run_ai_cost_guard"]
