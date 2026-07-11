"""Job funnel aggregation for dashboard summary (REQ-057)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

APPLYING = "applying"
INTERVIEWING = "interviewing"
AWAITING_FEEDBACK = "awaiting_feedback"

APPLYING_STATUSES = frozenset({"applied"})
INTERVIEWING_STATUSES = frozenset({"test", "interview_1", "interview_2", "interview_3"})
TERMINAL_STATUSES = frozenset({"failed", "passed"})


def aggregate_funnel(
    jobs: Iterable[Any],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return three funnel segments with counts.

    awaiting_feedback: interview-related non-terminal status with
    interview_time in the past.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    applying = 0
    interviewing = 0
    awaiting = 0

    for job in jobs:
        status = getattr(job, "status", None) or ""
        if status in APPLYING_STATUSES:
            applying += 1
        if status in INTERVIEWING_STATUSES:
            interviewing += 1
            it = getattr(job, "interview_time", None)
            if it is not None:
                if it.tzinfo is None:
                    it = it.replace(tzinfo=timezone.utc)
                if it < now and status not in TERMINAL_STATUSES:
                    awaiting += 1

    return [
        {
            "key": APPLYING,
            "label_zh": "投递中",
            "count": applying,
            "filter_statuses": sorted(APPLYING_STATUSES),
            "href": "/jobs?status=applied",
        },
        {
            "key": INTERVIEWING,
            "label_zh": "面试中",
            "count": interviewing,
            "filter_statuses": sorted(INTERVIEWING_STATUSES),
            "href": "/jobs?view=interviewing",
        },
        {
            "key": AWAITING_FEEDBACK,
            "label_zh": "待反馈",
            "count": awaiting,
            "filter_statuses": [],
            "href": "/jobs?view=awaiting_feedback",
        },
    ]


__all__ = [
    "APPLYING",
    "APPLYING_STATUSES",
    "AWAITING_FEEDBACK",
    "INTERVIEWING",
    "INTERVIEWING_STATUSES",
    "TERMINAL_STATUSES",
    "aggregate_funnel",
]
