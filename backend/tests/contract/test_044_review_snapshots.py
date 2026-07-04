"""REQ-044 US7 — Review Snapshots + Metric Trust OpenAPI contract test.

Locks the 7-endpoint surface (POST + GET list + GET detail + 3×405
immutable guards + health) + payload shapes documented in
``.claude/teams/req044/ac-matrix/REQ-044-US7.md``:

- ``POST   /api/v1/admin-console/review-snapshots``
- ``GET    /api/v1/admin-console/review-snapshots``
- ``GET    /api/v1/admin-console/review-snapshots/{id}``
- ``PUT    /api/v1/admin-console/review-snapshots/{id}`` — 405 immutable
- ``PATCH  /api/v1/admin-console/review-snapshots/{id}`` — 405 immutable
- ``DELETE /api/v1/admin-console/review-snapshots/{id}`` — 405 immutable
- ``GET    /api/v1/admin-console/review-snapshots/health``

Coverage of AC matrix:

- AC-27.2 / AC-27.4 — MetricDefinition10Field schema has the 10 FR-027
  fields and missing fields default to "(not provided)".
- AC-28.2 / AC-28.3 — DataStatus Literal 5 values + every snapshot
  frozen_value carries a data_status.
- AC-29.1 / SC-12.1 — POST response has all 8 SC-012 fields populated.
- AC-29.2 — generation writes an audit event with action=
  review_snapshot + target_kind=snapshot.
- AC-29.3 — payload whitelist + raw_* redacted.
- AC-29.4 — download_url points at US6 export route.
- AC-30.1 — GET returns both frozen_values + current_values.
- AC-30.3 — delta computed when current differs from frozen.
- AC-30.4 — PUT/PATCH/DELETE return 405.
- EC-1 — late-arriving data warning emitted.
- EC-2 — cohort_definition_changed boolean flag.
- EC-3 — expired payloads → 422 with expired_record_ids.

Skipped if ``DATABASE_URL`` is not configured for parity with the rest
of the 033/039/044 suites.
"""
from __future__ import annotations

import os

import pytest


def _app():
    from app.main import create_app

    return create_app()


# ---------------------------------------------------------------------------
# Module import surface sanity (import time assertions)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_review_snapshots_module_imports() -> None:
    """The review_snapshots subpackage must import without error."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    from app.modules.admin_console.review_snapshots import (  # noqa: F401
        repository,
        service,
    )
    from app.modules.admin_console.review_snapshots.api import (  # noqa: F401
        review_snapshots_router,
    )
    from app.modules.admin_console.review_snapshots.schemas import (  # noqa: F401
        MetricDefinition10Field,
        ReviewSnapshotRequest,
        ReviewSnapshotResponse,
        FrozenValue,
        CurrentValue,
        EvidenceLink,
        NOT_PROVIDED,
    )
    from app.modules.admin_console.audit import log_snapshot_generated  # noqa: F401


# ---------------------------------------------------------------------------
# Route presence (OpenAPI surface)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_review_snapshots_routes_in_openapi() -> None:
    """All 7 routes must appear in the OpenAPI surface."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    expected = {
        "/api/v1/admin-console/review-snapshots",
        "/api/v1/admin-console/review-snapshots/{snapshot_id}",
        "/api/v1/admin-console/review-snapshots/health",
    }
    actual = {
        r.path
        for r in app.routes
        if hasattr(r, "path") and "/admin-console/review-snapshots" in r.path
    }
    missing = expected - actual
    assert not missing, f"missing review-snapshots routes: {missing}"


@pytest.mark.contract
def test_review_snapshots_post_declares_201_403_422() -> None:
    """POST must declare 201 + 403 + 422 (FR-029 + EC-3)."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    schema = app.openapi()
    path = schema["paths"]["/api/v1/admin-console/review-snapshots"]
    post = path["post"]
    assert "201" in post["responses"]
    assert "403" in post["responses"]
    assert "422" in post["responses"]


# ---------------------------------------------------------------------------
# FR-027 / AC-27.2 — MetricDefinition10Field schema 10 fields
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_metric_definition_schema_has_ten_fields() -> None:
    """AC-27.2: MetricDefinition10Field exposes the 10 FR-027 fields."""
    from app.modules.admin_console.review_snapshots.schemas import (
        MetricDefinition10Field,
    )

    fields = set(MetricDefinition10Field.model_fields.keys())
    expected = {
        "definition",
        "owner",
        "source",
        "numerator",
        "denominator",
        "unit",
        "period",
        "freshness",
        "completeness",
        "quality_flags",
    }
    missing = expected - fields
    assert not missing, f"MetricDefinition10Field missing FR-027 fields: {missing}"


@pytest.mark.contract
def test_metric_definition_missing_fields_render_as_not_provided() -> None:
    """AC-27.4: missing fields render as literal "(not provided)"."""
    from app.modules.admin_console.review_snapshots.schemas import (
        NOT_PROVIDED,
        MetricDefinition10Field,
    )

    m = MetricDefinition10Field(metric_id="m1", name="test")
    assert m.definition == NOT_PROVIDED
    assert m.owner == NOT_PROVIDED
    assert m.source == NOT_PROVIDED
    assert m.numerator == NOT_PROVIDED
    assert m.denominator == NOT_PROVIDED
    assert m.unit == NOT_PROVIDED
    assert m.period == NOT_PROVIDED
    assert m.freshness == NOT_PROVIDED
    assert m.completeness == NOT_PROVIDED


# ---------------------------------------------------------------------------
# FR-028 / AC-28.2 — DataStatus Literal 5 values
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_data_status_enum_five_values() -> None:
    """AC-28.2: DataStatus reuses US6 5-state Literal (no new values)."""
    from app.modules.admin_console.governance.schemas import DataStatus

    # Literal size lock via get_args
    import typing

    args = typing.get_args(DataStatus)
    assert set(args) == {
        "valid_zero",
        "missing",
        "partial",
        "stale",
        "failed",
    }, f"DataStatus values drifted from US6 baseline: {args}"


# ---------------------------------------------------------------------------
# FR-029 / AC-29.1 / SC-12.1 — POST response has all 8 fields populated
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_snapshot_post_response_eight_fields_all_populated() -> None:
    """SC-12.1: 8 SC-012 fields all populated on POST response."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
    )

    reset_for_tests()
    snap = generate_snapshot(
        workspace="command-center",
        filters={"period": "rolling_7d"},
        comparison_period="vs prior week",
        annotations="Weekly PM sync",
        actor="@user:test",
    )

    # The 8 SC-012 fields
    assert snap.filters  # non-empty
    assert len(snap.frozen_values) >= 1
    assert len(snap.comparison_deltas) >= 1
    assert len(snap.metric_definitions) >= 1
    assert isinstance(snap.freshness_warnings, list)  # may be empty
    assert snap.quality_flags  # non-empty
    assert snap.annotations == "Weekly PM sync"
    assert len(snap.evidence_links) >= 1


@pytest.mark.contract
def test_snapshot_response_has_eight_fields() -> None:
    """AC-29.1: response envelope covers all 8 SC-012 field names."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
    )

    reset_for_tests()
    snap = generate_snapshot(
        workspace="product-analytics",
        filters={"period": "rolling_7d"},
        comparison_period="vs prior month",
        annotations="",
        actor="@user:test",
    )
    for field in (
        "frozen_values",
        "comparison_deltas",
        "metric_definitions",
        "freshness_warnings",
        "quality_flags",
        "evidence_links",
        "filters",
        "annotations",
    ):
        assert hasattr(snap, field), f"ReviewSnapshotResponse missing SC-012 field: {field}"


# ---------------------------------------------------------------------------
# FR-034 / AC-29.2 — generation writes an audit event
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_snapshot_generation_writes_audit_event() -> None:
    """AC-29.2: snapshot generation writes review_snapshot audit event."""
    from app.modules.admin_console.governance.repository import (
        list_audit_events,
        reset_for_tests as gov_reset,
    )
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
    )

    gov_reset()
    reset_for_tests()
    snap = generate_snapshot(
        workspace="ai-operations",
        filters={"period": "rolling_7d"},
        comparison_period="vs prior week",
        annotations="audit test",
        actor="@user:audit-test",
    )
    events = list_audit_events(action="review_snapshot")
    matching = [
        e for e in events
        if e.target_kind == "snapshot" and e.target_id == snap.snapshot_id
    ]
    assert matching, (
        f"snapshot generation must emit review_snapshot audit event; "
        f"snapshot_id={snap.snapshot_id}; events={events}"
    )


# ---------------------------------------------------------------------------
# FR-032 / AC-29.3 — payload whitelist + raw_* not embedded
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_snapshot_strips_raw_fields() -> None:
    """AC-29.3: snapshot payload must NOT contain raw_* fields."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        EXPORT_FIELDS_REDACTED,
        generate_snapshot,
    )

    # First: the EXPORT_FIELDS_REDACTED list itself must include the 4 raw_*.
    expected_raw = {
        "raw_resume",
        "raw_interview_answer",
        "raw_prompt",
        "raw_model_output",
    }
    assert expected_raw.issubset(set(EXPORT_FIELDS_REDACTED)), (
        f"EXPORT_FIELDS_REDACTED missing raw_* enforcement: {EXPORT_FIELDS_REDACTED}"
    )

    # Second: a generated snapshot's evidence_links must not contain raw_*.
    reset_for_tests()
    snap = generate_snapshot(
        workspace="logs-and-traces",
        filters={"period": "rolling_24h"},
        comparison_period="vs prior day",
        annotations="",
        actor="@user:raw-test",
    )
    payload = snap.model_dump(mode="json")
    raw_found = set()
    for key, val in payload.items():
        if "raw_" in key:
            raw_found.add(key)
        if isinstance(val, str) and any(r in val for r in expected_raw):
            raw_found.add(f"{key}:<value-contains-raw>")
    for link in payload["evidence_links"]:
        label = link.get("label", "")
        for raw in expected_raw:
            if raw in label:
                raw_found.add(f"evidence_links.label:<contains-{raw}>")
    assert not raw_found, f"snapshot payload leaked raw_* fields: {raw_found}"


# ---------------------------------------------------------------------------
# FR-029 / AC-29.4 — download_url points at US6 export route
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_snapshot_download_url_is_export_route() -> None:
    """AC-29.4: snapshot.download_url must point at US6 export route."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
    )

    reset_for_tests()
    snap = generate_snapshot(
        workspace="command-center",
        filters={"period": "rolling_7d"},
        comparison_period="vs prior week",
        annotations="",
        actor="@user:url-test",
    )
    assert snap.download_url.startswith(
        "/api/v1/admin-console/governance/exports/"
    ), f"snapshot.download_url={snap.download_url}"


# ---------------------------------------------------------------------------
# FR-030 / AC-30.1 — GET returns frozen + current
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_snapshot_get_returns_frozen_and_current() -> None:
    """AC-30.1: GET returns frozen_values AND current_values."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
        get_snapshot_with_delta,
    )

    reset_for_tests()
    snap = generate_snapshot(
        workspace="command-center",
        filters={"period": "rolling_7d"},
        comparison_period="vs prior week",
        annotations="",
        actor="@user:get-test",
    )
    fetched = get_snapshot_with_delta(snap.snapshot_id)
    assert len(fetched.frozen_values) >= 1
    assert len(fetched.current_values) >= 1
    # current_values re-pulled; ensure timestamps differ (or at least both present)
    assert all(cv.captured_at for cv in fetched.current_values)


# ---------------------------------------------------------------------------
# FR-030 / AC-30.3 — delta computed when current differs from frozen
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_delta_computed_when_current_differs() -> None:
    """AC-30.3: delta_pct computed (non-zero) when current != frozen."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
        get_snapshot_with_delta,
    )

    reset_for_tests()
    snap = generate_snapshot(
        workspace="command-center",
        filters={"period": "rolling_7d"},
        comparison_period="vs prior week",
        annotations="",
        actor="@user:delta-test",
    )
    fetched = get_snapshot_with_delta(snap.snapshot_id)
    non_zero = [d for d in fetched.comparison_deltas if d.delta_pct != 0]
    # Seed: command-center.current (56) vs frozen (50) → +12%
    assert any(d.metric_id.endswith("decision_queue_depth") for d in fetched.comparison_deltas)
    assert any(
        d.metric_id == "pm.command-center.decision_queue_depth"
        and abs(d.delta_pct - 12.0) < 0.5
        for d in fetched.comparison_deltas
    ), f"expected ~12% delta on decision_queue_depth; got {[d.model_dump() for d in fetched.comparison_deltas]}"


# ---------------------------------------------------------------------------
# AC-30.4 — Snapshot immutable (PUT/PATCH/DELETE 405)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_snapshot_immutable_rejects_mutation_with_405() -> None:
    """AC-30.4: PUT/PATCH/DELETE handlers must return 405."""
    app = _app()
    schema = app.openapi()
    path = "/api/v1/admin-console/review-snapshots/{snapshot_id}"
    path_obj = schema["paths"][path]
    for method in ("put", "patch", "delete"):
        assert method in path_obj, (
            f"snapshot route {path} missing {method} 405 handler"
        )
        responses = path_obj[method]["responses"]
        assert "405" in responses, (
            f"snapshot route {path} {method} must declare 405"
        )


@pytest.mark.contract
def test_snapshot_immutable_service_guard_raises() -> None:
    """AC-30.4: assert_snapshot_immutable raises SnapshotImmutableError."""
    from app.modules.admin_console.review_snapshots.service import (
        SnapshotImmutableError,
        assert_snapshot_immutable,
    )

    with pytest.raises(SnapshotImmutableError):
        assert_snapshot_immutable("snap-999999")


# ---------------------------------------------------------------------------
# EC-1 — late-arriving data warning emitted
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_late_arriving_data_warning_emitted() -> None:
    """EC-1: late_arriving_warnings populated when current != frozen."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
        get_snapshot_with_delta,
    )

    reset_for_tests()
    snap = generate_snapshot(
        workspace="command-center",
        filters={"period": "rolling_7d"},
        comparison_period="vs prior week",
        annotations="",
        actor="@user:ec1-test",
    )
    fetched = get_snapshot_with_delta(snap.snapshot_id)
    assert any(
        "decision_queue_depth" in w for w in fetched.late_arriving_warnings
    ), f"expected late_arriving warning for decision_queue_depth; got {fetched.late_arriving_warnings}"


# ---------------------------------------------------------------------------
# EC-2 — cohort definition changed warning
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_cohort_definition_changed_warning() -> None:
    """EC-2: cohort_definition_changed=True when filters.cohort_changed=True."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
    )

    reset_for_tests()
    snap = generate_snapshot(
        workspace="command-center",
        filters={"period": "rolling_7d", "cohort_changed": True},
        comparison_period="vs prior week",
        annotations="",
        actor="@user:ec2-test",
    )
    assert snap.cohort_definition_changed is True
    assert snap.cohort_change_warning is not None
    assert "cohort definition changed" in snap.cohort_change_warning.lower()


# ---------------------------------------------------------------------------
# EC-3 — expired payloads → snapshot blocked
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_snapshot_rejects_expired_payloads() -> None:
    """EC-3: filters.expired_record_ids → SnapshotBlockedError."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        SnapshotBlockedError,
        generate_snapshot,
    )

    reset_for_tests()
    with pytest.raises(SnapshotBlockedError) as exc_info:
        generate_snapshot(
            workspace="command-center",
            filters={"expired_record_ids": ["rec-1", "rec-2"]},
            comparison_period="vs prior week",
            annotations="",
            actor="@user:ec3-test",
        )
    assert exc_info.value.expired_record_ids == ["rec-1", "rec-2"]


# ---------------------------------------------------------------------------
# Snapshot list endpoint sanity
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_snapshot_list_returns_seeded_snapshots() -> None:
    """Generate + list round-trip."""
    from app.modules.admin_console.review_snapshots.repository import (
        reset_for_tests,
    )
    from app.modules.admin_console.review_snapshots.service import (
        generate_snapshot,
        list_snapshots,
    )

    reset_for_tests()
    for ws in ["command-center", "ai-operations"]:
        generate_snapshot(
            workspace=ws,
            filters={"period": "rolling_7d"},
            comparison_period="vs prior week",
            annotations="",
            actor="@user:list-test",
        )
    out = list_snapshots()
    assert out.total >= 2
    assert all(s.snapshot_id.startswith("snap-") for s in out.snapshots)