"""Prometheus metrics for the research module (REQ-053 FR-023).

Exposes:
- interview_research_tasks_total (Counter by status)
- interview_research_duration_seconds (Histogram)
- interview_report_generation_tokens (Counter)
- web_search_api_calls_total (Counter by dimension)

Follows the same pattern as `app.core.metrics`.
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram


research_tasks_total = Counter(
    "interview_research_tasks_total",
    "Total number of interview research tasks by terminal status",
    labelnames=("status",),
)

research_duration_seconds = Histogram(
    "interview_research_duration_seconds",
    "End-to-end duration of research task execution (task enqueue -> report complete)",
    buckets=(5, 15, 30, 60, 90, 120, 180, 240, 300),
)

report_generation_tokens = Counter(
    "interview_report_generation_tokens",
    "LLM tokens consumed by research report generation",
    labelnames=("phase",),  # keyword_extract | report_gen
)

web_search_api_calls_total = Counter(
    "web_search_api_calls_total",
    "Tavily search API calls by dimension and outcome",
    labelnames=("dimension", "outcome"),  # outcome: success | failed | cached
)


__all__ = [
    "research_tasks_total",
    "research_duration_seconds",
    "report_generation_tokens",
    "web_search_api_calls_total",
]