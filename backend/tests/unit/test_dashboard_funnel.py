"""Unit tests for dashboard funnel aggregation (REQ-057)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.modules.dashboard.funnel import aggregate_funnel


def test_funnel_three_segments():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    jobs = [
        SimpleNamespace(status="applied", interview_time=None),
        SimpleNamespace(status="applied", interview_time=None),
        SimpleNamespace(
            status="interview_1",
            interview_time=now + timedelta(hours=2),
        ),
        SimpleNamespace(
            status="interview_2",
            interview_time=now - timedelta(hours=1),
        ),
    ]
    segs = {s["key"]: s for s in aggregate_funnel(jobs, now=now)}
    assert segs["applying"]["count"] == 2
    assert segs["interviewing"]["count"] == 2
    assert segs["awaiting_feedback"]["count"] == 1


def test_funnel_empty():
    segs = aggregate_funnel([], now=datetime.now(timezone.utc))
    assert len(segs) == 3
    assert all(s["count"] == 0 for s in segs)
