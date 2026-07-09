"""REQ-033 Sub-batch 1 — retention policy unit tests (US10, FR-035a).

Covers:

- ``enforce_retention`` drops snapshots older than ``max_age_days``.
- Production context defaults to 30 days + delete action.
- Staging context defaults to 7 days + archive action.
- Dev context is a no-op (no caps).
- ``next_cleanup_at`` returns ``last_cleanup + interval_hours`` and
  preserves tzinfo.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.telemetry_contracts.events import MetricSnapshot
from app.modules.telemetry_contracts.retention import (
    RetentionContext,
    dev_default_context,
    enforce_retention,
    next_cleanup_at,
    production_default_context,
    staging_default_context,
)


def _snap(captured_at: datetime, metric_id: str = "pm.x") -> MetricSnapshot:
    return MetricSnapshot(
        metric_id=metric_id,
        name="X",
        value=1.0,
        captured_at=captured_at,
    )


# ---------------------------------------------------------------------------
# Age filter
# ---------------------------------------------------------------------------


def test_enforce_retention_drops_expired() -> None:
    """Snapshots older than ``max_age_days`` are dropped."""
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    old = _snap(now - timedelta(days=40))
    fresh = _snap(now - timedelta(days=5))
    ctx = RetentionContext(
        env="production", max_age_days=30, max_records=0, action="delete"
    )
    kept = enforce_retention([old, fresh], ctx, now=now)
    assert fresh in kept
    assert old not in kept


def test_enforce_retention_keeps_when_within_window() -> None:
    """Snapshots at exactly the cutoff boundary are kept (>= comparison)."""
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    edge = _snap(now - timedelta(days=30))
    ctx = RetentionContext(
        env="production", max_age_days=30, max_records=0, action="delete"
    )
    kept = enforce_retention([edge], ctx, now=now)
    assert edge in kept


def test_enforce_retention_record_cap_drops_oldest_first() -> None:
    """Record-count cap keeps only the newest ``max_records`` rows."""
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    snaps = [
        _snap(now - timedelta(days=i), metric_id=f"m{i}") for i in range(5)
    ]
    ctx = RetentionContext(
        env="staging", max_age_days=0, max_records=2, action="archive"
    )
    kept = enforce_retention(snaps, ctx, now=now)
    # Newest two = days=0 (today) and days=1 (yesterday).
    assert {s.metric_id for s in kept} == {"m0", "m1"}


# ---------------------------------------------------------------------------
# Default contexts
# ---------------------------------------------------------------------------


def test_production_30_day_default() -> None:
    """Production default is 30 days + delete action."""
    ctx = production_default_context()
    assert ctx.env == "production"
    assert ctx.max_age_days == 30
    assert ctx.action == "delete"


def test_staging_7_day_default() -> None:
    """Staging default is 7 days + archive action."""
    ctx = staging_default_context()
    assert ctx.env == "staging"
    assert ctx.max_age_days == 7
    assert ctx.action == "archive"


def test_dev_default_is_no_op() -> None:
    """Dev default has no age / record cap; enforce_retention passes through."""
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    snaps = [_snap(now - timedelta(days=400))]
    kept = enforce_retention(snaps, dev_default_context(), now=now)
    assert len(kept) == 1


def test_invalid_max_age_raises() -> None:
    """Negative ``max_age_days`` is rejected at construction time."""
    with pytest.raises(ValueError, match="max_age_days"):
        RetentionContext(
            env="dev", max_age_days=-1, max_records=0, action="delete"
        )


def test_invalid_env_raises() -> None:
    """Unknown env string is rejected."""
    with pytest.raises(ValueError, match="invalid env"):
        RetentionContext(
            env="moon", max_age_days=1, max_records=0, action="delete"
        )


# ---------------------------------------------------------------------------
# next_cleanup_at
# ---------------------------------------------------------------------------


def test_next_cleanup_at_24h() -> None:
    """Default cadence is 24h after ``last_cleanup``."""
    base = datetime(2026, 6, 26, 0, 0, 0, tzinfo=UTC)
    assert next_cleanup_at(base) == base + timedelta(hours=24)


def test_next_cleanup_at_custom_interval() -> None:
    """Caller can override the interval (used in tests)."""
    base = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)
    assert next_cleanup_at(base, interval_hours=6) == base + timedelta(hours=6)


def test_next_cleanup_at_naive_input_assumes_utc() -> None:
    """Naive datetime input is treated as UTC (legacy callers)."""
    base = datetime(2026, 6, 26, 0, 0, 0)
    result = next_cleanup_at(base, interval_hours=1)
    assert result == datetime(2026, 6, 26, 1, 0, 0, tzinfo=UTC)


def test_next_cleanup_at_zero_interval_raises() -> None:
    """Zero / negative interval is rejected."""
    with pytest.raises(ValueError, match="interval_hours"):
        next_cleanup_at(datetime.now(UTC), interval_hours=0)
