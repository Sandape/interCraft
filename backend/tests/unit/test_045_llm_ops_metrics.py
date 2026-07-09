from __future__ import annotations

from prometheus_client.metrics import Counter, Histogram

from app.core import metrics

_FORBIDDEN_LABELS = {"user_id", "run_id", "trace_id", "case_id", "prompt", "input", "output"}


def _labelnames(metric: Counter | Histogram) -> set[str]:
    return set(getattr(metric, "_labelnames", ()))


def test_req045_metric_names_are_registered() -> None:
    assert metrics.llm_ops_eval_runs_total._name == "llm_ops_eval_runs"
    assert metrics.llm_ops_export_decisions_total._name == "llm_ops_export_decisions"
    assert metrics.llm_ops_judge_calibration_total._name == "llm_ops_judge_calibration"
    assert metrics.llm_ops_trace_coverage_ratio._name == "llm_ops_trace_coverage_ratio"


def test_req045_metrics_use_bounded_labels_only() -> None:
    for metric in (
        metrics.llm_ops_eval_runs_total,
        metrics.llm_ops_export_decisions_total,
        metrics.llm_ops_judge_calibration_total,
        metrics.llm_ops_trace_coverage_ratio,
        metrics.llm_ops_langsmith_sync_latency_seconds,
    ):
        assert _FORBIDDEN_LABELS.isdisjoint(_labelnames(metric))


def test_req045_metric_labels_match_contract() -> None:
    assert _labelnames(metrics.llm_ops_eval_runs_total) == {"suite", "environment", "status"}
    assert _labelnames(metrics.llm_ops_export_decisions_total) == {
        "destination",
        "environment",
        "representation_level",
        "decision",
    }
    assert _labelnames(metrics.llm_ops_judge_calibration_total) == {"rubric", "status"}
    assert _labelnames(metrics.llm_ops_trace_coverage_ratio) == {"surface", "environment"}
    assert _labelnames(metrics.llm_ops_langsmith_sync_latency_seconds) == {"mode", "status"}
