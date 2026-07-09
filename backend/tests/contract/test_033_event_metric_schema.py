"""REQ-033 Sub-batch 1 — event / metric JSON round-trip contract tests.

Locks the contract between the Python dataclasses in
``app.modules.telemetry_contracts.events`` and the JSON envelope shape
documented in
``specs/033-eval-pm-dashboard/contracts/event-metric-schema.md``.

Contract surface (Sub-batch 1):

- ``ProductEvent.to_dict`` round-trips through ``dict_to_event`` without
  loss of any field. ``UUID`` and ``datetime`` fields are
  string-converted in JSON.
- ``AIInvocationSummary.to_dict`` round-trips through ``from_dict``
  preserving all fields including the optional ``error`` and
  ``cached`` flag.
- ``MetricSnapshot.to_dict`` round-trips through ``from_dict``
  preserving the ``dimensions`` dict, ``numerator`` / ``denominator``,
  and ``freshness_at``.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.telemetry_contracts.events import (
    AIInvocationSummary,
    MetricSnapshot,
    ProductEvent,
    dict_to_event,
    event_to_dict,
)


# ---------------------------------------------------------------------------
# ProductEvent
# ---------------------------------------------------------------------------


def test_event_round_trip_json() -> None:
    """``ProductEvent`` survives ``to_dict`` → ``dict_to_event`` without loss."""
    event_id = uuid4()
    user_id = uuid4()
    event = ProductEvent(
        name="resume.diagnosis_completed",
        occurred_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
        properties={"template.id": "modern", "duration_ms": 1234},
        event_id=event_id,
        user_id=user_id,
        environment="STAGING",
        release_stage="RELEASE_CANDIDATE",
        app_version="0.33.0",
        feature_area="RESUME",
        privacy_class="PUBLIC_METADATA",
        redaction_status="NOT_REQUIRED",
    )

    as_dict = event_to_dict(event)
    # JSON-safe types.
    json.dumps(as_dict)  # raises if not JSON-safe
    assert isinstance(as_dict["event_id"], str)
    assert isinstance(as_dict["user_id"], str)
    assert isinstance(as_dict["occurred_at"], str)

    restored = dict_to_event(as_dict)
    assert restored.name == event.name
    assert restored.event_id == event_id
    assert restored.user_id == user_id
    assert restored.occurred_at == event.occurred_at
    assert restored.properties == event.properties
    assert restored.environment == event.environment
    assert restored.app_version == event.app_version
    assert restored.feature_area == event.feature_area
    assert restored.release_stage == event.release_stage


def test_event_round_trip_anonymous_user() -> None:
    """Anonymous event (``user_id=None``) round-trips cleanly."""
    event = ProductEvent(
        name="product.visit",
        occurred_at=datetime(2026, 6, 26, 0, 0, 0, tzinfo=UTC),
    )
    as_dict = event_to_dict(event)
    assert as_dict["user_id"] is None
    restored = dict_to_event(as_dict)
    assert restored.user_id is None


# ---------------------------------------------------------------------------
# AIInvocationSummary
# ---------------------------------------------------------------------------


def test_ai_invocation_summary_serializes() -> None:
    """``AIInvocationSummary`` round-trips all fields."""
    inv = AIInvocationSummary(
        invocation_id=uuid4(),
        graph_name="interview",
        run_id=uuid4(),
        model="deepseek-v4-pro",
        tokens_in=1234,
        tokens_out=567,
        latency_ms=890,
        cached=False,
        error=None,
    )
    as_dict = inv.to_dict()
    json.dumps(as_dict)
    assert isinstance(as_dict["invocation_id"], str)
    assert isinstance(as_dict["run_id"], str)

    restored = AIInvocationSummary.from_dict(as_dict)
    assert restored.invocation_id == inv.invocation_id
    assert restored.run_id == inv.run_id
    assert restored.graph_name == inv.graph_name
    assert restored.model == inv.model
    assert restored.tokens_in == inv.tokens_in
    assert restored.tokens_out == inv.tokens_out
    assert restored.latency_ms == inv.latency_ms
    assert restored.cached == inv.cached
    assert restored.error == inv.error


def test_ai_invocation_summary_with_error_and_no_run_id() -> None:
    """``AIInvocationSummary`` round-trips with ``error`` set + ``run_id=None``."""
    inv = AIInvocationSummary(
        invocation_id=uuid4(),
        graph_name="interview",
        run_id=None,
        model="deepseek-v4-pro",
        tokens_in=0,
        tokens_out=0,
        latency_ms=12000,
        cached=True,
        error="timeout",
    )
    as_dict = inv.to_dict()
    assert as_dict["run_id"] is None
    assert as_dict["error"] == "timeout"
    restored = AIInvocationSummary.from_dict(as_dict)
    assert restored.error == "timeout"
    assert restored.cached is True
    assert restored.run_id is None


# ---------------------------------------------------------------------------
# MetricSnapshot
# ---------------------------------------------------------------------------


def test_metric_snapshot_serialize() -> None:
    """``MetricSnapshot`` round-trips with dimensions + numerator + denominator."""
    snap = MetricSnapshot(
        metric_id="ai.success_rate",
        name="AI Success Rate",
        value=0.98,
        captured_at=datetime(2026, 6, 26, 0, 0, 0, tzinfo=UTC),
        unit="percent",
        dimensions={
            "environment": "STAGING",
            "model": "deepseek-v4-pro",
            "graph": "interview",
        },
        numerator=98,
        denominator=100,
        source_of_truth="ai_invocation_records",
        freshness_at=datetime(2026, 6, 26, 0, 5, 0, tzinfo=UTC),
    )
    as_dict = snap.to_dict()
    json.dumps(as_dict)
    assert isinstance(as_dict["snapshot_id"], str)
    assert isinstance(as_dict["captured_at"], str)
    assert isinstance(as_dict["freshness_at"], str)

    restored = MetricSnapshot.from_dict(as_dict)
    assert restored.metric_id == snap.metric_id
    assert restored.name == snap.name
    assert restored.value == snap.value
    assert restored.unit == snap.unit
    assert restored.dimensions == snap.dimensions
    assert restored.numerator == snap.numerator
    assert restored.denominator == snap.denominator
    assert restored.source_of_truth == snap.source_of_truth
    assert restored.freshness_at == snap.freshness_at


def test_metric_snapshot_serialize_without_freshness() -> None:
    """``MetricSnapshot`` round-trips with ``freshness_at=None``."""
    snap = MetricSnapshot(
        metric_id="pm.resume.created",
        name="Resumes Created",
        value=42.0,
        captured_at=datetime(2026, 6, 26, 0, 0, 0, tzinfo=UTC),
    )
    as_dict = snap.to_dict()
    assert as_dict["freshness_at"] is None
    restored = MetricSnapshot.from_dict(as_dict)
    assert restored.freshness_at is None
    assert restored.dimensions == {}


# ---------------------------------------------------------------------------
# JSON envelope shape sanity (cross-check against contract doc)
# ---------------------------------------------------------------------------


def test_product_event_envelope_required_fields() -> None:
    """Top-level event envelope contains all spec-required fields.

    Spec: ``contracts/event-metric-schema.md`` lists required fields.
    """
    event = ProductEvent(
        name="resume.created_or_uploaded",
        occurred_at=datetime(2026, 6, 26, 0, 0, 0, tzinfo=UTC),
    )
    as_dict = event_to_dict(event)
    for required in (
        "name",
        "occurred_at",
        "environment",
        "release_stage",
        "app_version",
        "feature_area",
        "privacy_class",
        "redaction_status",
        "properties",
        "event_id",
    ):
        assert required in as_dict, f"missing required field {required}"
