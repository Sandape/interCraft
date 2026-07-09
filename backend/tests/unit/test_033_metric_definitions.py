"""REQ-033 Sub-batch 1 — metric catalog unit tests (US1, FR-039).

Covers:

- ``MetricCatalog.register`` adds; duplicate id raises.
- ``MetricCatalog.get`` returns the registered definition; ``try_get``
  returns ``None`` for unknown ids.
- ``list_by_source_event`` returns only definitions whose ``source_event``
  matches.
- The six built-in Overview metrics are registered by default, each
  carries a non-empty ``aggregation``.
- ``MetricDefinition`` rejects empty ``metric_id`` / ``source_event`` at
  construction time.
"""
from __future__ import annotations

import pytest

from app.modules.telemetry_contracts.metrics import (
    MetricCatalog,
    MetricDefinition,
    build_default_catalog,
)


def test_catalog_register_and_get() -> None:
    """Register + get round-trips a definition by id."""
    cat = MetricCatalog()
    d = MetricDefinition(
        metric_id="pm.test.foo",
        name="Foo",
        description="foo metric",
        unit="count",
        aggregation="sum",
        source_event="foo.bar",
    )
    cat.register(d)
    assert cat.get("pm.test.foo") is d
    assert cat.try_get("missing") is None


def test_catalog_duplicate_registration_raises() -> None:
    """Re-registering the same metric_id raises ValueError."""
    cat = MetricCatalog()
    d = MetricDefinition(
        metric_id="dup",
        name="Dup",
        description="x",
        unit="count",
        aggregation="sum",
        source_event="dup",
    )
    cat.register(d)
    with pytest.raises(ValueError, match="already registered"):
        cat.register(d)


def test_list_by_source_event() -> None:
    """``list_by_source_event`` returns only the matching definitions."""
    cat = build_default_catalog()
    matches = cat.list_by_source("ai.call_completed")
    # Two built-in metrics source from ai.call_completed:
    # pm.ai.token_consumed + pm.ai.cache_hit_rate
    ids = sorted(d.metric_id for d in matches)
    assert ids == ["pm.ai.cache_hit_rate", "pm.ai.token_consumed"]


def test_builtin_six_metrics_have_aggregation() -> None:
    """All six built-in Overview metrics are registered + non-empty agg."""
    cat = build_default_catalog()
    all_defs = cat.list_all()
    assert len(all_defs) == 6
    for d in all_defs:
        assert d.metric_id, f"empty metric_id in {d!r}"
        assert d.aggregation in {"sum", "avg", "p50", "p95", "p99"}, d
        assert d.source_event, d


def test_builtin_overview_metric_ids() -> None:
    """Pin the six built-in metric ids so dashboard panels can rely on them."""
    cat = build_default_catalog()
    ids = {d.metric_id for d in cat.list_all()}
    assert ids == {
        "pm.resume.created",
        "pm.resume.exported",
        "pm.interview.completed",
        "pm.interview.avg_score",
        "pm.ai.token_consumed",
        "pm.ai.cache_hit_rate",
    }


def test_metric_definition_rejects_empty_metric_id() -> None:
    """Empty ``metric_id`` is rejected at construction time."""
    with pytest.raises(ValueError, match="metric_id"):
        MetricDefinition(
            metric_id="",
            name="x",
            description="x",
            unit="count",
            aggregation="sum",
            source_event="x",
        )


def test_metric_definition_rejects_empty_source_event() -> None:
    """Empty ``source_event`` is rejected at construction time."""
    with pytest.raises(ValueError, match="source_event"):
        MetricDefinition(
            metric_id="m",
            name="m",
            description="m",
            unit="count",
            aggregation="sum",
            source_event="",
        )


def test_metric_value_type_validation() -> None:
    """``MetricDefinition.value`` is a typed string contract, not float.

    The catalog stores *definitions* (not values). Values live on
    ``MetricSnapshot.value``. This test pins the unit / aggregation
    contract used by callers (e.g. snapshot serialization).
    """
    d = MetricDefinition(
        metric_id="pm.test.score",
        name="Score",
        description="x",
        unit="score",
        aggregation="avg",
        source_event="x",
    )
    assert d.unit == "score"
    assert d.aggregation == "avg"
    # Definition is frozen — mutations raise.
    with pytest.raises(Exception):
        d.metric_id = "other"  # type: ignore[misc]


def test_list_all_sorted_by_metric_id() -> None:
    """``list_all`` is sorted by ``metric_id`` for stable test assertions."""
    cat = MetricCatalog()
    for mid in ("zzz", "aaa", "mmm"):
        cat.register(
            MetricDefinition(
                metric_id=mid,
                name=mid,
                description="x",
                unit="count",
                aggregation="sum",
                source_event="x",
            )
        )
    ids = [d.metric_id for d in cat.list_all()]
    assert ids == ["aaa", "mmm", "zzz"]
