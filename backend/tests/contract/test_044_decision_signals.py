"""REQ-044 US1 — Command Center decision-signals OpenAPI contract test.

Locks the 3-endpoint surface + payload shapes documented in
``.claude/teams/req044/ac-matrix/REQ-044-US1.md``:

- ``GET /api/v1/admin-console/command-center/health``
- ``GET /api/v1/admin-console/command-center/signals``
- ``GET /api/v1/admin-console/command-center/overview``

The contract test does NOT need a real DB — it only introspects the
FastAPI OpenAPI schema, parses the seed payload, and validates the
locked field set per FR-008.

Skipped if ``DATABASE_URL`` is not configured for parity with the rest
of the 033/039 suites (these tests run via ``pytest -q`` from a CI
machine that may not have the full env).
"""
from __future__ import annotations

import os

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _app():
    from app.main import create_app

    return create_app()


# ---------------------------------------------------------------------------
# Route presence
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_command_center_routes_in_openapi() -> None:
    """All 3 routes + the canonical paths must appear in OpenAPI."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    expected = {
        "/api/v1/admin-console/command-center/signals",
        "/api/v1/admin-console/command-center/overview",
        "/api/v1/admin-console/command-center/health",
    }
    actual = {
        r.path
        for r in app.routes
        if hasattr(r, "path") and "/admin-console/command-center" in r.path
    }
    missing = expected - actual
    assert not missing, f"missing command_center routes: {missing}"


@pytest.mark.contract
def test_signals_endpoint_declares_200_and_403() -> None:
    """GET /signals must declare 200 + 403 (FR-031 least-privilege)."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    schema = app.openapi()
    path = schema["paths"]["/api/v1/admin-console/command-center/signals"]
    get = path["get"]
    assert "200" in get["responses"]
    assert "403" in get["responses"]


@pytest.mark.contract
def test_overview_endpoint_declares_200_and_403() -> None:
    """GET /overview must declare 200 + 403."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    schema = app.openapi()
    path = schema["paths"]["/api/v1/admin-console/command-center/overview"]
    get = path["get"]
    assert "200" in get["responses"]
    assert "403" in get["responses"]


# ---------------------------------------------------------------------------
# FR-008 / SC-002 schema field locks
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_decision_signal_schema_has_required_fields() -> None:
    """DecisionSignal must declare ALL 10 FR-008 fields.

    Locked from ``specs/044-admin-console-redesign/spec.md`` line 361-363:

    - what_changed
    - affected_segment
    - comparison_baseline
    - severity
    - confidence
    - owner
    - freshness_at
    - next_review_link

    Plus id and category (the schema baseline). Plus evidence_links and
    quality_flags (FR-018 + FR-028). Total: 10 distinct field names.
    """
    from app.modules.admin_console.decision_signals.schemas import DecisionSignal

    field_names = set(DecisionSignal.model_fields.keys())
    required = {
        "id",
        "category",
        "what_changed",
        "affected_segment",
        "comparison_baseline",
        "severity",
        "confidence",
        "owner",
        "freshness_at",
        "next_review_link",
    }
    missing = required - field_names
    assert not missing, f"DecisionSignal missing required fields: {missing}"


@pytest.mark.contract
def test_decision_signal_confidence_enum_has_4_tiers() -> None:
    """confidence ∈ {confirmed, sampled, inferred, candidate} per FR-009."""
    from app.modules.admin_console.decision_signals.schemas import DecisionSignal

    # Pydantic stores Literal as ``Literal[<items>]`` in the field annotation.
    confidence_field = DecisionSignal.model_fields["confidence"]
    annotation_repr = str(confidence_field.annotation)
    for tier in ("confirmed", "sampled", "inferred", "candidate"):
        assert tier in annotation_repr, (
            f"confidence tier '{tier}' missing from {annotation_repr}"
        )


@pytest.mark.contract
def test_decision_signal_category_enum_has_6_categories() -> None:
    """category ∈ {product, ai-quality, ai-cost, system-health, incident, data-quality} per FR-007."""
    from app.modules.admin_console.decision_signals.schemas import DecisionSignal

    category_field = DecisionSignal.model_fields["category"]
    annotation_repr = str(category_field.annotation)
    for cat in (
        "product",
        "ai-quality",
        "ai-cost",
        "system-health",
        "incident",
        "data-quality",
    ):
        assert cat in annotation_repr, (
            f"category '{cat}' missing from {annotation_repr}"
        )


@pytest.mark.contract
def test_signals_fields_non_empty() -> None:
    """SC-002: 100% of signals have non-empty required fields.

    Iterates the seed list directly via the service so we can validate
    without a live DB; the service is pure data (no async I/O).
    """
    from app.modules.admin_console.decision_signals.service import (
        list_decision_signals,
    )

    result = list_decision_signals()
    assert result.signals, "seed must produce at least one signal"
    for sig in result.signals:
        assert sig.id, f"empty id in {sig}"
        assert sig.category, f"empty category in {sig.id}"
        assert sig.what_changed, f"empty what_changed in {sig.id}"
        assert sig.affected_segment, f"empty affected_segment in {sig.id}"
        assert sig.comparison_baseline, f"empty comparison_baseline in {sig.id}"
        assert sig.severity, f"empty severity in {sig.id}"
        assert sig.confidence, f"empty confidence in {sig.id}"
        assert sig.owner, f"empty owner in {sig.id}"
        assert sig.freshness_at, f"empty freshness_at in {sig.id}"
        assert sig.next_review_link, f"empty next_review_link in {sig.id}"


# ---------------------------------------------------------------------------
# Sort order + FR-010 quiet state
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_signals_sorted_by_priority_then_freshness() -> None:
    """FR-007: signals sorted by priority desc, freshness_at desc."""
    from app.modules.admin_console.decision_signals.service import (
        list_decision_signals,
    )

    result = list_decision_signals()
    keys = [(s.priority, s.freshness_at) for s in result.signals]
    assert keys == sorted(keys, reverse=True), (
        f"signals not sorted by (priority desc, freshness_at desc): {keys}"
    )


@pytest.mark.contract
def test_seed_covers_all_four_confidence_tiers() -> None:
    """FR-009: seed must include at least one signal in each tier so
    the visual distinction is verifiable."""
    from app.modules.admin_console.decision_signals.service import (
        list_decision_signals,
    )

    result = list_decision_signals()
    tiers = {s.confidence for s in result.signals}
    required = {"confirmed", "sampled", "inferred", "candidate"}
    missing = required - tiers
    assert not missing, f"confidence tiers missing from seed: {missing}"


@pytest.mark.contract
def test_seed_covers_all_six_categories() -> None:
    """FR-007: seed must include at least one signal in each category."""
    from app.modules.admin_console.decision_signals.service import (
        list_decision_signals,
    )

    result = list_decision_signals()
    cats = {s.category for s in result.signals}
    required = {
        "product",
        "ai-quality",
        "ai-cost",
        "system-health",
        "incident",
        "data-quality",
    }
    missing = required - cats
    assert not missing, f"categories missing from seed: {missing}"


@pytest.mark.contract
def test_seed_has_high_severity_signals() -> None:
    """SC-001: PM must find top 3 product/AI-quality/cost/system-health
    issues in 5 minutes — seed must surface at least 3 high/critical
    signals at the top of the queue."""
    from app.modules.admin_console.decision_signals.service import (
        list_decision_signals,
    )

    result = list_decision_signals()
    top = result.signals[:3]
    high_top = [s for s in top if s.severity in {"critical", "high"}]
    assert len(high_top) >= 3, (
        f"top 3 must include high/critical signals; got {[s.severity for s in top]}"
    )


@pytest.mark.contract
def test_quiet_steady_state_flag_consistent_with_severity_count() -> None:
    """FR-010: quiet_steady_state iff high_severity_count == 0."""
    from app.modules.admin_console.decision_signals.service import (
        list_decision_signals,
    )

    result = list_decision_signals()
    if result.high_severity_count == 0:
        assert result.quiet_steady_state is True
    else:
        assert result.quiet_steady_state is False


# ---------------------------------------------------------------------------
# COMMAND_CENTER_VIEW capability token
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_command_center_view_capability_in_role_map() -> None:
    """FR-031: COMMAND_CENTER_VIEW must be granted to pm/owner/admin
    so the PM demo flow can hit /signals without manual seeding."""
    from app.modules.admin_console.auth import (
        COMMAND_CENTER_VIEW,
        _ROLE_GRANTS,
    )

    assert COMMAND_CENTER_VIEW in _ROLE_GRANTS["admin"]
    assert COMMAND_CENTER_VIEW in _ROLE_GRANTS["owner"]
    assert COMMAND_CENTER_VIEW in _ROLE_GRANTS["pm"]


# ---------------------------------------------------------------------------
# Edge-case locks (EC-1, EC-2, EC-3)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_edge_case_partial_baseline_signal_present() -> None:
    """EC-3: a signal with partial_baseline flag must exist so the
    Edge Case is visible in the seed."""
    from app.modules.admin_console.decision_signals.service import (
        list_decision_signals,
    )

    result = list_decision_signals()
    assert any(
        s.quality_flags.partial_baseline for s in result.signals
    ), "seed must include a signal with partial_baseline=True (EC-3)"


@pytest.mark.contract
def test_edge_case_stale_signal_present() -> None:
    """EC-2: a signal with stale=True must exist so the freshness
    staleness is visible."""
    from app.modules.admin_console.decision_signals.service import (
        list_decision_signals,
    )

    result = list_decision_signals()
    assert any(
        s.quality_flags.stale for s in result.signals
    ), "seed must include a signal with stale=True (EC-2)"


@pytest.mark.contract
def test_overview_response_schema_has_four_kpi_tiles() -> None:
    """The overview response must expose all 4 KPI tiles."""
    from app.modules.admin_console.decision_signals.schemas import (
        CommandCenterOverview,
    )

    fields = set(CommandCenterOverview.model_fields.keys())
    required = {
        "product_health",
        "ai_quality",
        "ai_cost",
        "system_health",
    }
    missing = required - fields
    assert not missing, f"overview missing KPI tiles: {missing}"