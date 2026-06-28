"""REQ-033 US10 — production 30-day retention integration tests (T026).

Covers the spec scenarios in §US10 around FR-035a (``production trace
metadata + redacted summaries retained for 30 days``) and the CLI /
runtime contract documented in
``specs/033-eval-pm-dashboard/contracts/eval-langsmith-cli.md``.

Each scenario here exercises the in-process retention library plus a
lightweight in-memory DB stub (a plain dict) that stands in for the
``trace_run_refs`` table — the integration test must NOT require a live
PostgreSQL because it is supposed to remain runnable in CI without
external services (and to run in the same suite as the redaction policy
tests).

Scenarios:

- AC-01 after 30 days, ``trace_run_refs.retention_expires_at`` is past
  → read returns 0 rows (records inaccessible).
- AC-02 retention ``check`` CLI exits 0 when all rows are current.
- AC-03 retention ``check`` reports a count of expired records + the
  earliest expiration timestamp.
- AC-04 staging uses 7-day archive (per env policy).
- AC-05 local / dev / ci is a no-op (no rows reported as expired).
- AC-06 production check CLI defaults to ``--dry-run`` and never
  deletes automatically (per FR-035a — only ``enforce_retention`` /
  explicit operator action does).
- AC-07 ``next_cleanup_at`` is the canonical cadence (24h) used by the
  CLI scheduler.
"""
from __future__ import annotations

from __future__ import annotations

import importlib.util as _ilu
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

from app.modules.telemetry_contracts.events import MetricSnapshot
from app.modules.telemetry_contracts.retention import (
    RetentionContext,
    dev_default_context,
    enforce_retention,
    next_cleanup_at,
    production_default_context,
    staging_default_context,
)

# ---------------------------------------------------------------------------
# In-memory DB stub for ``trace_run_refs`` rows. Mirrors the relevant
# columns of the SQLAlchemy ORM model in
# ``backend/app/modules/telemetry_contracts/models.py`` without spinning
# up a real Postgres session.
# ---------------------------------------------------------------------------


@dataclass
class TraceRunRefRow:
    """Subset of ``trace_run_refs`` columns that the retention logic needs."""

    trace_id: str
    environment: str
    privacy_class: str
    redaction_status: str
    retention_expires_at: datetime | None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionCheckResult:
    """Output of the ``retention check`` CLI / in-memory equivalent."""

    environment: str
    checked_rows: int
    expired_rows: list[TraceRunRefRow]
    earliest_expired_at: datetime | None
    earliest_trace_id: str | None
    dry_run: bool
    policy_version: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "checkedRows": self.checked_rows,
            "expiredCount": len(self.expired_rows),
            "earliestExpiredAt": (
                self.earliest_expired_at.isoformat()
                if self.earliest_expired_at
                else None
            ),
            "earliestTraceId": self.earliest_trace_id,
            "dryRun": self.dry_run,
            "policyVersion": self.policy_version,
            "error": self.error,
        }


class _InMemoryTraceStore:
    """Tiny test stand-in for the ``trace_run_refs`` table.

    The production implementation will hit ``app.modules.telemetry_contracts.
    repository`` / SQLAlchemy async session. These tests only need to
    exercise the *contract* (filter rows by ``retention_expires_at < now``
    per env policy), so an in-memory list + helpers is sufficient and
    keeps the integration tests fast and DB-free.
    """

    def __init__(self) -> None:
        self._rows: list[TraceRunRefRow] = []

    def add(self, row: TraceRunRefRow) -> None:
        self._rows.append(row)

    def all(self) -> list[TraceRunRefRow]:
        return list(self._rows)

    def active_rows(
        self,
        environment: str,
        *,
        now: datetime,
    ) -> list[TraceRunRefRow]:
        """Rows whose ``retention_expires_at`` is still in the future."""
        return [
            r
            for r in self._rows
            if r.environment == environment
            and r.retention_expires_at is not None
            and r.retention_expires_at >= now
        ]

    def expired_rows(
        self,
        environment: str,
        *,
        now: datetime,
    ) -> list[TraceRunRefRow]:
        return [
            r
            for r in self._rows
            if r.environment == environment
            and r.retention_expires_at is not None
            and r.retention_expires_at < now
        ]


def _retention_check(
    store: _InMemoryTraceStore,
    environment: str,
    *,
    now: datetime,
    dry_run: bool = True,
    policy_version: str = "v1",
) -> RetentionCheckResult:
    """In-process equivalent of ``python -m app.modules.telemetry_contracts.retention check``.

    Mirrors the CLI contract from
    ``specs/033-eval-pm-dashboard/contracts/eval-langsmith-cli.md``:
    production always defaults to dry-run per FR-035a.
    """
    norm_env = environment.strip().lower()
    if norm_env in ("production", "prod"):
        # FR-035a: production default is dry-run; never auto-delete.
        dry_run = True

    rows = [r for r in store.all() if r.environment == norm_env]
    expired = [r for r in rows if r.retention_expires_at is not None and r.retention_expires_at < now]
    earliest = min((r.retention_expires_at for r in expired), default=None) if expired else None
    earliest_tid = (
        next(
            (r.trace_id for r in expired if r.retention_expires_at == earliest),
            None,
        )
        if earliest
        else None
    )

    # dry_run semantics: in real backend we'd call ``enforce_retention``
    # on MetricSnapshots and only persist the deletion audit row when
    # not dry-run. For test purposes, we record the side-effect intent
    # without mutating state.
    if not dry_run and expired:
        store._rows = [r for r in store._rows if r not in expired]

    return RetentionCheckResult(
        environment=norm_env,
        checked_rows=len(rows),
        expired_rows=expired,
        earliest_expired_at=earliest,
        earliest_trace_id=earliest_tid,
        dry_run=dry_run,
        policy_version=policy_version,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> _InMemoryTraceStore:
    return _InMemoryTraceStore()


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# AC-01 — after 30 days, retention_expires_at is past → read = 0
# ---------------------------------------------------------------------------


def test_production_records_after_30_days_are_inaccessible(
    store: _InMemoryTraceStore, fixed_now: datetime
) -> None:
    """A production row with ``retention_expires_at`` in the past is not active."""
    # Inserted 31 days ago, expires 1 day ago.
    store.add(
        TraceRunRefRow(
            trace_id="trace-old-001",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=fixed_now - timedelta(days=1),
        )
    )
    active = store.active_rows("production", now=fixed_now)
    expired = store.expired_rows("production", now=fixed_now)
    assert active == []
    assert len(expired) == 1


def test_production_records_within_30_days_are_active(
    store: _InMemoryTraceStore, fixed_now: datetime
) -> None:
    """Production row with ``retention_expires_at`` 5 days in the future → still active."""
    store.add(
        TraceRunRefRow(
            trace_id="trace-fresh-001",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=fixed_now + timedelta(days=5),
        )
    )
    assert len(store.active_rows("production", now=fixed_now)) == 1
    assert store.expired_rows("production", now=fixed_now) == []


# ---------------------------------------------------------------------------
# AC-02 — retention check CLI exit 0 when all rows are current
# ---------------------------------------------------------------------------


def test_retention_check_reports_zero_expired(
    store: _InMemoryTraceStore, fixed_now: datetime
) -> None:
    """All-current store → expiredCount=0, exit 0."""
    store.add(
        TraceRunRefRow(
            trace_id="trace-a",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=fixed_now + timedelta(days=15),
        )
    )
    result = _retention_check(store, "production", now=fixed_now)
    assert result.expired_rows == []
    assert result.earliest_expired_at is None
    # Exit 0 mapping (no exception) — confirmed via shape only.
    assert result.environment == "production"
    assert result.dry_run is True  # FR-035a default


def test_retention_check_serializes_for_cli() -> None:
    """The check result shape is JSON-serializable (CLI --json output)."""
    res = RetentionCheckResult(
        environment="production",
        checked_rows=10,
        expired_rows=[],
        earliest_expired_at=None,
        earliest_trace_id=None,
        dry_run=True,
        policy_version="v1",
    )
    import json

    blob = json.dumps(res.to_dict())
    assert "checkedRows" in blob
    assert "expiredCount" in blob
    assert "dryRun" in blob


# ---------------------------------------------------------------------------
# AC-03 — check reports expired count + earliest expiration
# ---------------------------------------------------------------------------


def test_retention_check_reports_expired_count_and_earliest(
    store: _InMemoryTraceStore, fixed_now: datetime
) -> None:
    """Mixed store → check reports expired count + earliest expired_at."""
    # 3 expired rows, 1 still current.
    store.add(
        TraceRunRefRow(
            trace_id="trace-expired-1",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=fixed_now - timedelta(days=10),
        )
    )
    store.add(
        TraceRunRefRow(
            trace_id="trace-expired-2",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=fixed_now - timedelta(days=20),
        )
    )
    store.add(
        TraceRunRefRow(
            trace_id="trace-expired-3",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=fixed_now - timedelta(days=2),
        )
    )
    store.add(
        TraceRunRefRow(
            trace_id="trace-fresh",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=fixed_now + timedelta(days=5),
        )
    )
    result = _retention_check(store, "production", now=fixed_now)
    assert len(result.expired_rows) == 3
    assert result.earliest_expired_at == fixed_now - timedelta(days=20)
    # Earliest trace id is the one that expired longest ago.
    assert result.earliest_trace_id == "trace-expired-2"
    assert result.dry_run is True


# ---------------------------------------------------------------------------
# AC-04 — staging 7-day archive
# ---------------------------------------------------------------------------


def test_staging_default_context_is_7_day_archive() -> None:
    """Staging default: 7-day retention + archive action."""
    ctx = staging_default_context()
    assert ctx.env == "staging"
    assert ctx.max_age_days == 7
    assert ctx.action == "archive"


def test_staging_records_after_7_days_are_expired(
    store: _InMemoryTraceStore, fixed_now: datetime
) -> None:
    """Staging row with retention_expires_at 8 days in the past is expired."""
    store.add(
        TraceRunRefRow(
            trace_id="trace-staging-old",
            environment="staging",
            privacy_class="INTERNAL_METADATA",
            redaction_status="PASSED",
            retention_expires_at=fixed_now - timedelta(days=8),
        )
    )
    result = _retention_check(store, "staging", now=fixed_now, dry_run=False)
    assert len(result.expired_rows) == 1
    # dry_run=False is allowed for staging (action = archive, not delete).
    assert result.dry_run is False


# ---------------------------------------------------------------------------
# AC-05 — local / dev / ci is a no-op
# ---------------------------------------------------------------------------


def test_dev_default_context_is_no_op() -> None:
    ctx = dev_default_context()
    assert ctx.env == "dev"
    assert ctx.max_age_days == 0
    assert ctx.max_records == 0


def test_dev_store_never_reports_expired(
    store: _InMemoryTraceStore, fixed_now: datetime
) -> None:
    """dev / local / ci rows are never reported as expired by the CLI check.

    The dev / local / ci convention (per the retention library's
    :func:`dev_default_context` = no-op): dev rows MUST have
    ``retention_expires_at=None`` (no expiry). The CLI skips rows with
    ``None`` retention from the expired list because they have no
    expiry to enforce.
    """
    store.add(
        TraceRunRefRow(
            trace_id="trace-dev-1",
            environment="dev",
            privacy_class="PUBLIC_METADATA",
            redaction_status="NOT_REQUIRED",
            retention_expires_at=None,
        )
    )
    store.add(
        TraceRunRefRow(
            trace_id="trace-dev-2",
            environment="local",
            privacy_class="PUBLIC_METADATA",
            redaction_status="NOT_REQUIRED",
            retention_expires_at=None,
        )
    )
    result = _retention_check(store, "dev", now=fixed_now, dry_run=True)
    assert result.expired_rows == []
    assert result.earliest_expired_at is None


# ---------------------------------------------------------------------------
# AC-06 — production always dry-run (FR-035a)
# ---------------------------------------------------------------------------


def test_production_check_always_dry_run_even_if_requested_otherwise(
    store: _InMemoryTraceStore, fixed_now: datetime
) -> None:
    """``--dry-run=false`` for production is overridden to True (FR-035a).

    Per FR-035a the 30-day window is the policy; production never
    auto-deletes. The CLI confirms operator intent (``dry_run`` in the
    result) but never persists the deletion.
    """
    store.add(
        TraceRunRefRow(
            trace_id="trace-prod-expired",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=fixed_now - timedelta(days=2),
        )
    )
    before = len(store.all())
    result = _retention_check(store, "production", now=fixed_now, dry_run=False)
    after = len(store.all())
    assert result.dry_run is True  # FR-035a override
    # Even though caller asked dry_run=False, the production path
    # forced dry_run=True, so the store is NOT mutated.
    assert before == after


def test_production_30_day_default() -> None:
    """Production default: 30 days + delete (caller selects action, default dry-run)."""
    ctx = production_default_context()
    assert ctx.env == "production"
    assert ctx.max_age_days == 30
    assert ctx.action == "delete"


# ---------------------------------------------------------------------------
# AC-07 — next_cleanup_at cadence
# ---------------------------------------------------------------------------


def test_next_cleanup_at_default_is_24h() -> None:
    base = datetime(2026, 6, 26, 0, 0, 0, tzinfo=UTC)
    assert next_cleanup_at(base) == base + timedelta(hours=24)


def test_next_cleanup_at_custom_for_dry_run() -> None:
    base = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)
    # Operators can run the check more frequently than 24h without
    # forcing a delete.
    assert next_cleanup_at(base, interval_hours=6) == base + timedelta(hours=6)


# ---------------------------------------------------------------------------
# Auxiliary — enforce_retention on MetricSnapshot
# ---------------------------------------------------------------------------


def test_enforce_retention_production_drops_30d_old() -> None:
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    old = MetricSnapshot(
        metric_id="pm.uv",
        name="UV",
        value=100.0,
        captured_at=now - timedelta(days=40),
    )
    fresh = MetricSnapshot(
        metric_id="pm.uv",
        name="UV",
        value=200.0,
        captured_at=now - timedelta(days=5),
    )
    kept = enforce_retention([old, fresh], production_default_context(), now=now)
    assert fresh in kept
    assert old not in kept


def test_enforce_retention_staging_drops_8d_old() -> None:
    """Staging drops snapshots older than 7 days; the 7-day boundary is kept (>=)."""
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    snaps = [
        MetricSnapshot(
            metric_id=f"m{i}",
            name="X",
            value=1.0,
            captured_at=now - timedelta(days=i),
        )
        for i in range(10)
    ]
    kept = enforce_retention(snaps, staging_default_context(), now=now)
    # ``>= cutoff`` semantics means the 7-day boundary row (m7) survives
    # along with m0..m6; m8 and m9 are dropped.
    ids = {s.metric_id for s in kept}
    assert ids == {"m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7"}
    assert "m8" not in ids
    assert "m9" not in ids