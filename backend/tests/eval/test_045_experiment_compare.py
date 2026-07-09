from __future__ import annotations

from app.eval.experiment_compare import compare_experiments


def test_compare_experiments_reports_quality_cost_latency_deltas() -> None:
    result = compare_experiments(
        baseline={
            "runId": "baseline",
            "aggregatePassRate": 0.72,
            "costUsd": 2.00,
            "latencyMs": 1000,
        },
        candidate={
            "runId": "candidate",
            "aggregatePassRate": 0.82,
            "costUsd": 2.40,
            "latencyMs": 900,
        },
    )

    assert result["baselineRunId"] == "baseline"
    assert result["candidateRunId"] == "candidate"
    assert result["qualityDelta"] == 0.10
    assert result["costDeltaUsd"] == 0.40
    assert result["latencyDeltaMs"] == -100
    assert result["recommendation"] == "candidate_wins"


def test_compare_experiments_flags_candidate_regression() -> None:
    result = compare_experiments(
        baseline={"runId": "baseline", "aggregatePassRate": 0.90},
        candidate={"runId": "candidate", "aggregatePassRate": 0.70},
    )

    assert result["recommendation"] == "baseline_wins"
    assert "quality_regression" in result["riskFlags"]
