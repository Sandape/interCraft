"""REQ-056: metrics counters are importable and incrementable."""
from __future__ import annotations

from app.modules.resume_derive.metrics import (
    derive_runs_total,
    export_page_mismatch_total,
    suggestion_apply_total,
)


def test_metrics_increment_without_error():
    derive_runs_total.labels(status="succeeded").inc()
    export_page_mismatch_total.inc()
    suggestion_apply_total.labels(outcome="applied").inc()
