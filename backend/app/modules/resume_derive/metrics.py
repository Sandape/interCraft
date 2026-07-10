"""Prometheus metrics for resume derive (REQ-055 / REQ-056).

Alert defaults and drill notes:
  specs/056-derive-prod-hardening/contracts/alerts.md
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

derive_runs_total = Counter(
    "resume_derive_runs_total",
    "Resume derive runs by terminal status",
    ["status"],
)

derive_duration_seconds = Histogram(
    "resume_derive_duration_seconds",
    "Resume derive wall-clock duration",
    buckets=(1, 5, 15, 30, 60, 120, 300, 600),
)

calibrate_rounds = Histogram(
    "resume_derive_calibrate_rounds",
    "Page calibrate rounds before success or guidance",
    buckets=(0, 1, 2, 3, 4, 5),
)

export_page_mismatch_total = Counter(
    "resume_export_page_mismatch_total",
    "Export rejected due to PDF page count mismatch",
)

suggestion_apply_total = Counter(
    "resume_derive_suggestion_apply_total",
    "Suggestion apply outcomes",
    ["outcome"],
)
