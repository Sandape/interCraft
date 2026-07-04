"""REQ-044 US7 — Review Snapshots in-memory repository.

Seed strategy (parity with US1/2/3/4/6):

- :func:`seed_demo_metric_definitions` — 4 metric definitions (one per
  workspace that has chart data: command-center / product-analytics /
  ai-operations / logs-and-traces). Each declares the full 10 FR-027
  fields. Used by AC-27.2 / AC-27.3.
- :func:`seed_demo_current_values` — current (live) metric values for
  each metric_id; includes one row that DELIBERATELY differs from the
  frozen seed value to drive EC-1 (late-arriving data) + AC-30.3
  delta path.
- :func:`seed_demo_frozen_values` — frozen metric values for each
  metric_id at snapshot time. Slight numerical skew vs current seed
  (one metric +12%, one +0%) so AC-30.3 has something to render.
- :func:`seed_demo_evidence_links` — privacy-safe evidence link list
  per workspace (no raw_* fields, per FR-032 + SC-010).
- :func:`seed_demo_cohort_versions` — ``{cohort_name: version_int}``
  map used by EC-2 cohort-definition-changed detection.
- :func:`seed_demo_snapshots` — 2 historical snapshots so the Reports
  page has data on first load (zero-state is allowed but empty list
  is unhelpful for tests).

In-memory buffers:
- :data:`_SNAPSHOTS` — ``{snapshot_id: snapshot_dict}`` (immutable once
  written; PUT/PATCH/DELETE 405 asserted by service).
- :data:`_COHORT_VERSIONS` — mutable map; bumped on demand for EC-2
  test (US7 contract test calls ``bump_cohort_version``).

Audit write goes through US6 :func:`governance.repository.append_audit_event`
+ :func:`governance.repository.next_audit_event_id` (no new audit
buffer; reuse US6 in-memory ring).

[CROSS-TEAM-DEBT] Real review_snapshot DB + real-time late-arriving
data recompute + cohort change detector land in Phase 2 batch 5.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.admin_console.governance.repository import (
    append_audit_event,
    next_audit_event_id,
)
from app.modules.admin_console.governance.schemas import (
    DataStatus,
    WorkspaceId,
)
from app.modules.admin_console.review_snapshots.schemas import (
    ComparisonDelta,
    CurrentValue,
    EvidenceLink,
    FrozenValue,
    MetricDefinition10Field,
    ReviewSnapshotResponse,
)

_lock = threading.Lock()

#: snapshot_id -> ReviewSnapshotResponse dict.
_SNAPSHOTS: dict[str, dict[str, Any]] = {}
#: Cohort version map for EC-2 detection.
_COHORT_VERSIONS: dict[str, int] = {}
#: Sequence counter for snapshot ids.
_NEXT_SNAPSHOT_SEQ = 0
#: Initialised flag.
_SEEDED = False


def _now_iso() -> str:
    return (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _earlier_iso(days: int = 0, hours: int = 0, minutes: int = 0) -> str:
    return (
        (datetime.now(UTC) - timedelta(days=days, hours=hours, minutes=minutes))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def reset_for_tests() -> None:
    """Clear all snapshot buffers. Test helper."""
    global _SEEDED, _NEXT_SNAPSHOT_SEQ
    with _lock:
        _SNAPSHOTS.clear()
        _COHORT_VERSIONS.clear()
        _NEXT_SNAPSHOT_SEQ = 0
        _SEEDED = False


# ---------------------------------------------------------------------------
# Metric definition catalog seed (FR-027 AC-27.2 / AC-27.3)
# ---------------------------------------------------------------------------


def seed_demo_metric_definitions() -> list[MetricDefinition10Field]:
    """Return 4 metric definitions, each with the full 10 FR-027 fields.

    One metric per workspace that has chart surfaces in REQ-044:

    - ``decision_queue_depth`` (command-center)
    - ``funnel_activation_dropoff`` (product-analytics)
    - ``ai_task_success_rate`` (ai-operations)
    - ``log_coverage_rate`` (logs-and-traces)
    """
    return [
        MetricDefinition10Field(
            metric_id="pm.command-center.decision_queue_depth",
            name="Command-Center Decision Queue Depth",
            definition="Count of decision signals in the queue at snapshot time.",
            owner="pm-team",
            source="telemetry:command-center.signals",
            numerator="signals where status='open'",
            denominator="1 (count)",
            unit="count",
            period="rolling 7d",
            freshness="updated every 15 minutes",
            completeness="100% (PM signals all instrumented)",
            quality_flags="valid_zero",
        ),
        MetricDefinition10Field(
            metric_id="pm.product-analytics.funnel_activation_dropoff",
            name="Activation Funnel Drop-off",
            definition="Fraction of users who started the activation funnel but did not complete step 3.",
            owner="growth-team",
            source="telemetry:resume.created_or_uploaded",
            numerator="users with step=started but no step=completed-3",
            denominator="users with step=started",
            unit="percent",
            period="rolling 7d",
            freshness="updated hourly",
            completeness="98% (legacy path excluded)",
            quality_flags="partial",
        ),
        MetricDefinition10Field(
            metric_id="pm.ai-operations.ai_task_success_rate",
            name="AI Task Success Rate",
            definition="Fraction of AI tasks with status=success in the snapshot window.",
            owner="ai-team",
            source="telemetry:ai.call_completed",
            numerator="ai tasks where status='success'",
            denominator="ai tasks (all statuses)",
            unit="percent",
            period="rolling 7d",
            freshness="updated every 30 minutes",
            completeness="99% (only ai-team scoped tasks)",
            quality_flags="valid_zero",
        ),
        MetricDefinition10Field(
            metric_id="pm.logs-and-traces.log_coverage_rate",
            name="Log Coverage Rate",
            definition="Fraction of agent runs with at least one structured log line.",
            owner="platform-team",
            source="telemetry:agent.run_completed",
            numerator="agent runs with log_count >= 1",
            denominator="agent runs",
            unit="percent",
            period="rolling 24h",
            freshness="updated every 5 minutes",
            completeness="95% (legacy path bypasses centralized logging)",
            quality_flags="partial",
        ),
    ]


# ---------------------------------------------------------------------------
# Current (live) value seed (FR-030 + EC-1)
# ---------------------------------------------------------------------------


def seed_demo_current_values() -> list[CurrentValue]:
    """Return the current (live) value for each metric — DELIBERATELY skewed
    vs frozen seed so EC-1 + AC-30.3 (DeltaIndicator) has data to render.
    """
    now = _now_iso()
    return [
        # +12% vs frozen (drives AC-30.3 delta path)
        CurrentValue(
            metric_id="pm.command-center.decision_queue_depth",
            value=56.0,
            unit="count",
            captured_at=now,
            data_status="valid_zero",
        ),
        # +3% vs frozen (small delta — late-arriving data)
        CurrentValue(
            metric_id="pm.product-analytics.funnel_activation_dropoff",
            value=0.41,
            unit="percent",
            captured_at=now,
            data_status="partial",
        ),
        # 0% delta (control)
        CurrentValue(
            metric_id="pm.ai-operations.ai_task_success_rate",
            value=0.93,
            unit="percent",
            captured_at=now,
            data_status="valid_zero",
        ),
        # 0% delta (control)
        CurrentValue(
            metric_id="pm.logs-and-traces.log_coverage_rate",
            value=0.93,
            unit="percent",
            captured_at=now,
            data_status="partial",
        ),
    ]


# ---------------------------------------------------------------------------
# Frozen value seed (FR-029 + AC-30.1)
# ---------------------------------------------------------------------------


def seed_demo_frozen_values() -> list[FrozenValue]:
    """Return the frozen metric values at snapshot time.

    Historical baseline: same metrics, slightly lower — late-arriving
    data bumped them up in current.
    """
    captured = _earlier_iso(days=2)
    return [
        FrozenValue(
            metric_id="pm.command-center.decision_queue_depth",
            value=50.0,
            unit="count",
            captured_at=captured,
            data_status="valid_zero",
        ),
        FrozenValue(
            metric_id="pm.product-analytics.funnel_activation_dropoff",
            value=0.40,
            unit="percent",
            captured_at=captured,
            data_status="partial",
        ),
        FrozenValue(
            metric_id="pm.ai-operations.ai_task_success_rate",
            value=0.93,
            unit="percent",
            captured_at=captured,
            data_status="valid_zero",
        ),
        FrozenValue(
            metric_id="pm.logs-and-traces.log_coverage_rate",
            value=0.93,
            unit="percent",
            captured_at=captured,
            data_status="partial",
        ),
    ]


# ---------------------------------------------------------------------------
# Evidence link seed (FR-029 + FR-032 + SC-010)
# ---------------------------------------------------------------------------


def seed_demo_evidence_links() -> list[EvidenceLink]:
    """Return privacy-safe evidence link list.

    Labels are human-readable summaries; no raw_* fields (FR-032 + SC-010).
    """
    return [
        EvidenceLink(
            label="INC-2026-001 activation regression (no raw payload)",
            kind="incident",
            target_id="INC-2026-001",
        ),
        EvidenceLink(
            label="Trace tr-7f3a activation funnel drop (no raw payload)",
            kind="trace",
            target_id="tr-7f3a-9b2c",
        ),
        EvidenceLink(
            label="Eval case EC-1412 rubric mismatch (no raw payload)",
            kind="badcase",
            target_id="EC-1412",
        ),
    ]


# ---------------------------------------------------------------------------
# Cohort version seed (EC-2)
# ---------------------------------------------------------------------------


def seed_demo_cohort_versions() -> dict[str, int]:
    """Return cohort -> version map.

    EC-2 detector compares the version at snapshot-generation time
    vs current; mismatch triggers ``cohort_definition_changed``.
    """
    return {
        "activation_funnel_2026_q3": 1,
        "ai_team_paid_cohort": 2,
    }


def get_cohort_versions() -> dict[str, int]:
    """Return a copy of the current cohort version map."""
    seed_once()
    with _lock:
        return dict(_COHORT_VERSIONS)


def bump_cohort_version(cohort_name: str) -> int:
    """Increment a cohort version. EC-2 test helper."""
    seed_once()
    with _lock:
        cur = _COHORT_VERSIONS.get(cohort_name, 0)
        _COHORT_VERSIONS[cohort_name] = cur + 1
        return _COHORT_VERSIONS[cohort_name]


# ---------------------------------------------------------------------------
# Snapshot buffer (FR-029 + AC-30.4 immutable)
# ---------------------------------------------------------------------------


def next_snapshot_id() -> str:
    """Return the next snapshot id (Phase 1; Phase 2 batch 5 swaps for UUID)."""
    global _NEXT_SNAPSHOT_SEQ
    with _lock:
        _NEXT_SNAPSHOT_SEQ += 1
        return f"snap-{_NEXT_SNAPSHOT_SEQ:06d}"


def append_snapshot(snapshot_dict: dict[str, Any]) -> None:
    """Append a snapshot to the in-memory buffer.

    AC-30.4: there is no update/delete helper — the API layer's
    PUT/PATCH/DELETE handlers must return 405.
    """
    with _lock:
        _SNAPSHOTS[snapshot_dict["snapshot_id"]] = snapshot_dict


def get_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    with _lock:
        return _SNAPSHOTS.get(snapshot_id)


def list_snapshots() -> list[dict[str, Any]]:
    with _lock:
        return list(_SNAPSHOTS.values())


def snapshot_count() -> int:
    """Test helper for AC-SC-12.1 + 405 guard verification."""
    with _lock:
        return len(_SNAPSHOTS)


# ---------------------------------------------------------------------------
# Audit re-export (so service can call once)
# ---------------------------------------------------------------------------


__audit_append = append_audit_event
__audit_next_id = next_audit_event_id


# ---------------------------------------------------------------------------
# Seed-once orchestrator
# ---------------------------------------------------------------------------


def seed_once() -> None:
    """Seed cohort versions once on first import. Idempotent.

    Frozen / current / evidence seed values are NOT cached here
    because they need per-snapshot ``captured_at`` timestamps; the
    service layer calls the seed helpers directly when generating.
    """
    global _SEEDED
    with _lock:
        if _SEEDED:
            return
        _COHORT_VERSIONS.update(seed_demo_cohort_versions())
        _SEEDED = True


def seed_demo_snapshots() -> int:
    """Seed 2 historical snapshots so the Reports page has data on first load.

    Returns the number of snapshots seeded (0 if already seeded).

    Tests call this from a fixture so the AC-SC-12.1 contract test
    has populated ``GET /review-snapshots`` data to assert against.
    """
    seed_once()
    # Build minimal envelope using service layer (avoid circular import).
    from app.modules.admin_console.review_snapshots import service

    count = 0
    seed_targets = [
        ("command-center", "vs prior week", "Weekly PM sync — command-center pulse"),
        ("ai-operations", "vs prior month", "Monthly AI ops review"),
    ]
    for workspace, period, annotations in seed_targets:
        snapshot = service.generate_snapshot(
            workspace=workspace,
            filters={"period": period},
            comparison_period=period,
            annotations=annotations,
            actor="@user:seed",
        )
        count += 1
    return count


__all__ = [
    "append_snapshot",
    "bump_cohort_version",
    "get_cohort_versions",
    "get_snapshot",
    "list_snapshots",
    "next_snapshot_id",
    "reset_for_tests",
    "seed_demo_cohort_versions",
    "seed_demo_current_values",
    "seed_demo_evidence_links",
    "seed_demo_frozen_values",
    "seed_demo_metric_definitions",
    "seed_demo_snapshots",
    "seed_once",
    "snapshot_count",
]