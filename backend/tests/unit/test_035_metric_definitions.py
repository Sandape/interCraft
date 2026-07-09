from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.pm_dashboard import service


def test_metric_definition_catalog_covers_req035_dashboard_cards() -> None:
    catalog = service.get_metric_definition_catalog()
    by_id = {definition.metric_id: definition for definition in catalog}

    assert {
        "pm.active_users",
        "pm.ai_success_rate",
        "pm.estimated_cost",
        "badcases.open",
        "pm.funnel",
        "pm.resume_diagnosis",
        "pm.mock_interview",
        "pm.ai_operations",
    }.issubset(by_id)

    active_users = by_id["pm.active_users"]
    assert active_users.owner == "product"
    assert active_users.source == "product_events"
    assert active_users.freshness_target_minutes == 15
    assert active_users.definition
    assert active_users.version == "req035.v1"

    estimated_cost = by_id["pm.estimated_cost"]
    assert estimated_cost.unit == "currency"
    assert estimated_cost.comparison_rule == "sum_estimate"
    assert "raw" not in estimated_cost.model_dump_json().lower()


def test_metric_definition_catalog_has_unique_ids_and_metadata() -> None:
    catalog = service.get_metric_definition_catalog()
    ids = [definition.metric_id for definition in catalog]

    assert len(ids) == len(set(ids))
    for definition in catalog:
      assert definition.display_name
      assert definition.numerator
      assert definition.source
      assert definition.owner
      assert definition.privacy_class == "aggregate"


def test_metric_source_completeness_quality_states() -> None:
    now = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)

    complete = service.calculate_metric_source_completeness(
        expected_sources=["product_events", "ai_invocation_records"],
        available_sources=["product_events", "ai_invocation_records"],
        row_count=12,
        freshness_at=now - timedelta(minutes=5),
        now=now,
        freshness_target_minutes=15,
    )
    assert complete.quality_state == "complete"
    assert complete.missing_sources == []

    partial = service.calculate_metric_source_completeness(
        expected_sources=["product_events", "ai_invocation_records"],
        available_sources=["product_events"],
        row_count=12,
        freshness_at=now - timedelta(minutes=5),
        now=now,
        freshness_target_minutes=15,
    )
    assert partial.quality_state == "partial"
    assert partial.missing_sources == ["ai_invocation_records"]

    empty = service.calculate_metric_source_completeness(
        expected_sources=["product_events"],
        available_sources=["product_events"],
        row_count=0,
        freshness_at=now - timedelta(minutes=5),
        now=now,
        freshness_target_minutes=15,
    )
    assert empty.quality_state == "empty"

    stale = service.calculate_metric_source_completeness(
        expected_sources=["product_events"],
        available_sources=["product_events"],
        row_count=3,
        freshness_at=now - timedelta(minutes=30),
        now=now,
        freshness_target_minutes=15,
    )
    assert stale.quality_state == "stale"

    error = service.calculate_metric_source_completeness(
        expected_sources=["product_events"],
        available_sources=["product_events"],
        row_count=3,
        freshness_at=now,
        now=now,
        freshness_target_minutes=15,
        error=True,
    )
    assert error.quality_state == "error"


def test_req035_dashboard_summary_assembly_uses_metric_catalog() -> None:
    now = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)

    summary = service.assemble_req035_dashboard_summary(
        metric_values={"pm.ai_success_rate": 0.0},
        freshness_at=now - timedelta(minutes=5),
        now=now,
    )

    cards = {card["metric_id"]: card for card in summary["summary_cards"]}
    assert cards["pm.ai_success_rate"]["value"] == 0.0
    assert cards["pm.ai_success_rate"]["definition"].denominator
    assert cards["pm.ai_success_rate"]["source_completeness"].quality_state == "complete"

    panels = {panel["panel_id"]: panel for panel in summary["panels"]}
    assert panels["version_context"]["definition"].metric_id == "pm.version_experiment"
    assert panels["version_context"]["quality_state"] == "complete"
