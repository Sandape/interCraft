"""Baseline/candidate comparison helpers for REQ-045 US4."""
from __future__ import annotations

from typing import Any


def _field(report: dict[str, Any], *names: str, default: Any = 0) -> Any:
    for name in names:
        if name in report:
            return report[name]
    return default


def _run_id(report: dict[str, Any], fallback: str) -> str:
    return str(_field(report, "runId", "run_id", default=fallback))


def _rounded(value: float) -> float:
    return round(value, 4)


def compare_experiments(
    *,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    min_quality_delta: float = 0.0,
) -> dict[str, Any]:
    baseline_quality = float(
        _field(baseline, "aggregatePassRate", "aggregate_pass_rate", default=0.0) or 0.0
    )
    candidate_quality = float(
        _field(candidate, "aggregatePassRate", "aggregate_pass_rate", default=0.0) or 0.0
    )
    baseline_cost = float(_field(baseline, "costUsd", "cost_usd", default=0.0) or 0.0)
    candidate_cost = float(_field(candidate, "costUsd", "cost_usd", default=0.0) or 0.0)
    baseline_latency = int(_field(baseline, "latencyMs", "latency_ms", default=0) or 0)
    candidate_latency = int(_field(candidate, "latencyMs", "latency_ms", default=0) or 0)

    quality_delta = candidate_quality - baseline_quality
    cost_delta = candidate_cost - baseline_cost
    latency_delta = candidate_latency - baseline_latency
    risk_flags: list[str] = []
    if quality_delta < 0:
        risk_flags.append("quality_regression")
    if cost_delta > 0 and quality_delta <= 0:
        risk_flags.append("cost_increase_without_quality_gain")
    if latency_delta > 0 and quality_delta <= 0:
        risk_flags.append("latency_increase_without_quality_gain")

    recommendation = (
        "candidate_wins"
        if quality_delta >= min_quality_delta and "quality_regression" not in risk_flags
        else "baseline_wins"
    )
    return {
        "comparisonId": f"cmp-{_run_id(baseline, 'baseline')}-{_run_id(candidate, 'candidate')}",
        "baselineRunId": _run_id(baseline, "baseline"),
        "candidateRunId": _run_id(candidate, "candidate"),
        "baselinePassRate": _rounded(baseline_quality),
        "candidatePassRate": _rounded(candidate_quality),
        "qualityDelta": _rounded(quality_delta),
        "costDeltaUsd": _rounded(cost_delta),
        "latencyDeltaMs": latency_delta,
        "recommendation": recommendation,
        "riskFlags": risk_flags,
    }


def link_prompt_proposal_to_comparison(
    proposal: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    return {
        **proposal,
        "comparisonRunId": comparison.get("comparisonId"),
        "comparisonRecommendation": comparison.get("recommendation"),
    }


__all__ = ["compare_experiments", "link_prompt_proposal_to_comparison"]
