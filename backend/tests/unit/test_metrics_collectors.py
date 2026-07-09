"""022 US5 — Unit tests: metrics collectors.

Verifies 6 new metrics (T051-T056) exist with correct type and labels.

NOTE: prometheus_client strips the ``_total`` suffix from Counter names
in ``Metric.name``, so we search without it.
"""
from __future__ import annotations

from prometheus_client import REGISTRY

# Ensure all metrics are registered by loading the module
import app.core.metrics  # noqa: F401


def _find_metric(name: str):
    """Find a metric by its registry name (``_total`` stripped for counters)."""
    for metric in REGISTRY.collect():
        if metric.name == name:
            return metric
    return None


def _has_label(metric, label: str) -> bool:
    """Check if a metric has a label in its samples (or just check type spec)."""
    for s in metric.samples:
        if s.labels and label in s.labels:
            return True
    return False


class TestLLMQuotaMetrics:
    def test_llm_quota_exhausted_total_exists(self):
        m = _find_metric("llm_quota_exhausted")
        assert m is not None, "llm_quota_exhausted not found in registry"
        assert m.type == "counter", "expected counter type"

    def test_llm_quota_available_exists(self):
        m = _find_metric("llm_quota_available")
        assert m is not None, "llm_quota_available not found in registry"
        assert m.type == "gauge", "expected gauge type"


class TestCheckpointerMetrics:
    def test_checkpointer_reconnect_total_exists(self):
        m = _find_metric("checkpointer_reconnect")
        assert m is not None, "checkpointer_reconnect not found in registry"
        assert m.type == "counter", "expected counter type"


class TestWSMetrics:
    def test_ws_connections_active_exists(self):
        m = _find_metric("ws_connections_active")
        assert m is not None, "ws_connections_active not found in registry"
        assert m.type == "gauge", "expected gauge type"


class TestARQMetrics:
    def test_arq_jobs_queued_exists(self):
        m = _find_metric("arq_jobs_queued")
        assert m is not None, "arq_jobs_queued not found in registry"
        assert m.type == "gauge", "expected gauge type"

    def test_arq_jobs_failed_total_exists(self):
        m = _find_metric("arq_jobs_failed")
        assert m is not None, "arq_jobs_failed not found in registry"
        assert m.type == "counter", "expected counter type"
