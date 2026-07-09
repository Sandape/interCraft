from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.telemetry_contracts.retention import (
    req035_default_context,
    req035_is_expired,
)


def test_req035_production_retention_windows_are_debug_heavy() -> None:
    ctx = req035_default_context("production")

    assert ctx.pm_metrics_days == 180
    assert ctx.redacted_trace_days == 60
    assert ctx.masked_raw_days == 14
    assert ctx.dashboard_freshness_minutes == 15


def test_req035_expiry_uses_record_kind_window() -> None:
    now = datetime(2026, 6, 29, tzinfo=UTC)
    ctx = req035_default_context("production")

    assert req035_is_expired(
        "masked_raw_payload",
        captured_at=now - timedelta(days=15),
        now=now,
        ctx=ctx,
    )
    assert not req035_is_expired(
        "redacted_trace",
        captured_at=now - timedelta(days=59),
        now=now,
        ctx=ctx,
    )
    assert not req035_is_expired(
        "pm_metric",
        captured_at=now - timedelta(days=179),
        now=now,
        ctx=ctx,
    )
