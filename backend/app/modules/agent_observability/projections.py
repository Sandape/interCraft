"""REQ-061 US9 fact-driven operational aggregations (T115 light-touch).

Builds stability / quality / latency / point / cost metric envelopes with
explicit freshness, coverage, and unknown counts. Unknown values stay
``None`` / explicit counters — never coerced to zero revenue fiction.
Beta revenue is always Decimal("0").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class DataQuality:
    fresh_at: datetime
    coverage_percent: float
    unknown_count: int
    seed_or_mock_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "fresh_at": self.fresh_at.isoformat(),
            "coverage_percent": self.coverage_percent,
            "unknown_count": self.unknown_count,
            "seed_or_mock_count": self.seed_or_mock_count,
        }


@dataclass
class OperationalFacts:
    """Minimal fact bag consumed by aggregations (additive; no DB required)."""

    tasks: list[dict[str, Any]] = field(default_factory=list)
    point_events: list[dict[str, Any]] = field(default_factory=list)
    cost_events: list[dict[str, Any]] = field(default_factory=list)
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _group_key(row: dict[str, Any], dimensions: Iterable[str]) -> tuple[Any, ...]:
    return tuple(row.get(d) for d in dimensions)


def aggregate_operational_metrics(
    facts: OperationalFacts,
    *,
    dimensions: tuple[str, ...] = (
        "capability",
        "service_tier",
        "policy_version",
        "release_batch",
        "grant_config_version",
        "business_date",
    ),
) -> dict[str, Any]:
    tasks = facts.tasks
    total = len(tasks)
    successes = sum(1 for t in tasks if t.get("status") == "succeeded")
    failures = sum(1 for t in tasks if t.get("status") == "failed")
    cancels = sum(1 for t in tasks if t.get("status") == "cancelled")
    unknowns = sum(
        1
        for t in tasks
        if t.get("status") in {None, "unknown"}
        or t.get("cost_status") == "unknown"
        or t.get("latency_ms") is None
    )

    latencies = [int(t["latency_ms"]) for t in tasks if t.get("latency_ms") is not None]
    latencies.sort()

    def _pct(p: float) -> int | None:
        if not latencies:
            return None
        rank = max(1, min(len(latencies), int(-(-len(latencies) * p // 100))))
        return latencies[rank - 1]

    points_granted = sum(int(e.get("points") or 0) for e in facts.point_events if e.get("command") == "grant")
    points_settled = sum(int(e.get("points") or 0) for e in facts.point_events if e.get("command") == "settle")

    cost_rmb = Decimal("0")
    unknown_cost = 0
    for event in facts.cost_events:
        if event.get("cost_status") == "unknown" or event.get("rmb_amount") is None:
            unknown_cost += 1
            continue
        cost_rmb += Decimal(str(event["rmb_amount"]))

    by_dim: dict[str, Any] = {}
    for task in tasks:
        key = ",".join(str(x) for x in _group_key(task, dimensions))
        bucket = by_dim.setdefault(key, {"count": 0, "succeeded": 0})
        bucket["count"] += 1
        if task.get("status") == "succeeded":
            bucket["succeeded"] += 1

    coverage = 100.0 if total == 0 else round(100.0 * (total - unknowns) / total, 4)
    quality = DataQuality(
        fresh_at=facts.as_of,
        coverage_percent=coverage,
        unknown_count=unknowns + unknown_cost,
        seed_or_mock_count=0,
    )

    return {
        "stability": {
            "accepted": total,
            "succeeded": successes,
            "failed": failures,
            "cancelled": cancels,
            "success_rate": None if total == 0 else successes / total,
        },
        "quality": {
            "negative_feedback_rate": None,  # unknown until feedback facts join
            "by_dimension": by_dim,
        },
        "latency": {
            "p50_ms": _pct(50),
            "p95_ms": _pct(95),
            "p99_ms": _pct(99),
            "sample_size": len(latencies),
        },
        "points": {
            "granted": points_granted,
            "settled": points_settled,
        },
        "cost": {
            "rmb_total": str(cost_rmb),
            "unknown_cost_events": unknown_cost,
        },
        "revenue_rmb": {"amount": "0", "currency": "CNY"},
        "data_quality": quality.as_dict(),
    }


__all__ = [
    "DataQuality",
    "OperationalFacts",
    "aggregate_operational_metrics",
]
