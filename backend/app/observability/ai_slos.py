"""REQ-061 aggregate AI SLOs / alert definitions (T176)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SLODefinition:
    name: str
    objective: str
    window: str
    burn_alert: str


AI_RUNTIME_SLOS: tuple[SLODefinition, ...] = (
    SLODefinition(
        name="ai_task_availability",
        objective=">= 99.5% accept→terminal without control-plane failure",
        window="30d",
        burn_alert="page on 2% burn / 1h",
    ),
    SLODefinition(
        name="dispatch_queue_saturation",
        objective="pending intents < admission ceiling for 95% of minutes",
        window="7d",
        burn_alert="ticket when >80% for 15m",
    ),
    SLODefinition(
        name="retry_amplification",
        objective="attempts/task P95 <= 3",
        window="7d",
        burn_alert="ticket when P95 > 5",
    ),
    SLODefinition(
        name="provider_breaker_open_ratio",
        objective="< 1% of route-minutes open",
        window="24h",
        burn_alert="page when open >5m",
    ),
    SLODefinition(
        name="evidence_gap_rate",
        objective="< 0.5% tasks missing attempt/milestone evidence",
        window="7d",
        burn_alert="ticket daily",
    ),
    SLODefinition(
        name="projection_backlog_age",
        objective="P95 catch-up < 5m; never re-execute AI work",
        window="24h",
        burn_alert="page when age >30m",
    ),
    SLODefinition(
        name="point_ledger_imbalance",
        objective="0 unresolved conservation issues / day",
        window="1d",
        burn_alert="page on any imbalance",
    ),
    SLODefinition(
        name="unknown_rate",
        objective="< 5% provider outcomes classified unknown",
        window="7d",
        burn_alert="ticket when >5%",
    ),
    SLODefinition(
        name="reconciliation_sla",
        objective="daily preliminary reconcile complete by T+4h",
        window="1d",
        burn_alert="ticket when late",
    ),
)


def list_ai_slos() -> list[dict[str, str]]:
    return [
        {
            "name": s.name,
            "objective": s.objective,
            "window": s.window,
            "burn_alert": s.burn_alert,
        }
        for s in AI_RUNTIME_SLOS
    ]
