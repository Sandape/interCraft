"""REQ-033 Sub-batch 1 — redaction policy unit tests (US10, FR-031..FR-036).

Covers:

- STRIP_PII removes only PII keys from ``properties``; preserves everything
  else (event envelope, non-PII properties).
- METADATA_ONLY keeps only ``name`` / ``occurred_at`` / ``event_id`` /
  (allowed) ``user_id``; ``properties`` -> ``{}``.
- Production context forces ``user_id`` to ``None`` even under STRIP_PII
  unless ``allow_user_ids`` contains it.
- ``validate_redaction`` returns a list of violation names; empty when ok.
- ``audit_redaction`` records an audit row whose ``fields_redacted`` list
  enumerates the keys actually removed.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.telemetry_contracts.redaction import (
    PII_FIELDS,
    RedactionContext,
    RedactionPolicy,
    apply_redaction,
    audit_redaction,
    dev_default_context,
    production_default_context,
    staging_default_context,
    validate_redaction,
)
from app.modules.telemetry_contracts.events import ProductEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_event(
    *,
    name: str = "resume.diagnosis_completed",
    user_id: UUID | None = None,
    properties: dict | None = None,
    app_version: str = "0.33.0",
    feature_area: str = "RESUME",
    environment: str = "STAGING",
) -> ProductEvent:
    return ProductEvent(
        name=name,
        occurred_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
        properties=properties or {"template.id": "modern", "duration_ms": 1234},
        event_id=uuid4(),
        user_id=user_id,
        environment=environment,
        release_stage="RELEASE_CANDIDATE",
        app_version=app_version,
        feature_area=feature_area,
        privacy_class="PUBLIC_METADATA",
        redaction_status="NOT_REQUIRED",
    )


# ---------------------------------------------------------------------------
# STRIP_PII
# ---------------------------------------------------------------------------


def test_apply_redaction_strip_pii() -> None:
    """STRIP_PII removes PII keys; everything else preserved."""
    event = _make_event(
        properties={"email": "a@b.com", "phone": "555", "score": 9},
    )
    ctx = RedactionContext(env="staging", policy=RedactionPolicy.STRIP_PII)
    redacted = apply_redaction(event, ctx)

    assert "email" not in redacted.properties
    assert "phone" not in redacted.properties
    assert redacted.properties == {"score": 9}
    # Envelope fields preserved.
    assert redacted.name == event.name
    assert redacted.event_id == event.event_id
    assert redacted.app_version == event.app_version
    assert redacted.feature_area == event.feature_area


def test_apply_redaction_strip_pii_case_insensitive() -> None:
    """PII detection is case-insensitive (Email, PHONE, Address)."""
    event = _make_event(
        properties={"Email": "x@y", "PHONE": "1", "Address": "1 Main St"},
    )
    ctx = RedactionContext(env="staging", policy=RedactionPolicy.STRIP_PII)
    redacted = apply_redaction(event, ctx)
    assert redacted.properties == {}


# ---------------------------------------------------------------------------
# METADATA_ONLY
# ---------------------------------------------------------------------------


def test_apply_redaction_metadata_only() -> None:
    """METADATA_ONLY replaces ``properties`` with ``{}``; keeps envelope."""
    event = _make_event(
        properties={"email": "a@b.com", "phone": "1", "score": 9},
        app_version="0.33.0",
        feature_area="RESUME",
    )
    ctx = RedactionContext(env="production", policy=RedactionPolicy.METADATA_ONLY)
    redacted = apply_redaction(event, ctx)
    assert redacted.properties == {}
    # Envelope metadata preserved.
    assert redacted.name == event.name
    assert redacted.app_version == "0.33.0"
    assert redacted.feature_area == "RESUME"
    assert redacted.event_id == event.event_id


def test_apply_redaction_metadata_only_keeps_user_id_outside_prod() -> None:
    """Non-production env under METADATA_ONLY keeps ``user_id`` if non-prod."""
    user_id = uuid4()
    event = _make_event(user_id=user_id)
    ctx = RedactionContext(env="staging", policy=RedactionPolicy.METADATA_ONLY)
    redacted = apply_redaction(event, ctx)
    assert redacted.user_id == user_id


# ---------------------------------------------------------------------------
# Production default + user-id forcing
# ---------------------------------------------------------------------------


def test_apply_redaction_production_default() -> None:
    """Production default ctx applies METADATA_ONLY + strips user_id."""
    user_id = uuid4()
    event = _make_event(user_id=user_id, properties={"email": "a@b.com"})
    ctx = production_default_context()
    redacted = apply_redaction(event, ctx)

    assert ctx.env == "production"
    assert ctx.policy == RedactionPolicy.METADATA_ONLY
    assert redacted.user_id is None  # forced to None in prod
    assert redacted.properties == {}


def test_apply_redaction_production_allows_opted_in_user() -> None:
    """Production user-id forcing respects ``allow_user_ids`` escape hatch."""
    user_id = uuid4()
    event = _make_event(user_id=user_id)
    ctx = production_default_context(allow_user_ids={user_id})
    redacted = apply_redaction(event, ctx)
    assert redacted.user_id == user_id


def test_apply_redaction_production_user_id_forced_under_strip_pii_too() -> None:
    """``user_id`` is forced to None in prod even when policy is STRIP_PII."""
    user_id = uuid4()
    event = _make_event(user_id=user_id)
    ctx = RedactionContext(env="production", policy=RedactionPolicy.STRIP_PII)
    redacted = apply_redaction(event, ctx)
    assert redacted.user_id is None


# ---------------------------------------------------------------------------
# validate_redaction
# ---------------------------------------------------------------------------


def test_validate_redaction_returns_violations() -> None:
    """``validate_redaction`` returns names of PII keys in ``properties``."""
    event = _make_event(properties={"email": "x", "phone": "1", "ok": "y"})
    violations = validate_redaction(RedactionPolicy.STRIP_PII, event)
    assert set(violations) == {"properties.email", "properties.phone"}


def test_validate_redaction_allow_all_returns_empty() -> None:
    """``ALLOW_ALL`` never reports violations (no policy in effect)."""
    event = _make_event(properties={"email": "x"})
    assert validate_redaction(RedactionPolicy.ALLOW_ALL, event) == []


def test_validate_redaction_metadata_only_violates_when_properties_nonempty() -> None:
    """``METADATA_ONLY`` flags non-empty ``properties`` as a violation."""
    event = _make_event(properties={"x": 1})
    violations = validate_redaction(RedactionPolicy.METADATA_ONLY, event)
    assert "properties" in violations


# ---------------------------------------------------------------------------
# audit_redaction
# ---------------------------------------------------------------------------


def test_audit_records_redacted_fields() -> None:
    """``audit_redaction`` records which fields were actually redacted."""
    event = _make_event(
        user_id=uuid4(),
        properties={"email": "x", "score": 9},
    )
    ctx = production_default_context()
    redacted = apply_redaction(event, ctx)
    audit = audit_redaction(event, ctx, redacted)

    assert audit.policy_applied == RedactionPolicy.METADATA_ONLY
    assert audit.env == "production"
    assert audit.event_id == event.event_id
    # user_id was forced to None in prod. Properties keys (`email`,
    # `score`) were dropped by METADATA_ONLY which replaces the dict.
    assert "user_id" in audit.fields_redacted
    assert "email" in audit.fields_redacted
    assert "score" in audit.fields_redacted


def test_audit_no_op_when_no_field_changed() -> None:
    """``ALLOW_ALL`` audit lists no fields redacted."""
    event = _make_event()
    ctx = dev_default_context()
    redacted = apply_redaction(event, ctx)
    audit = audit_redaction(event, ctx, redacted)
    assert audit.fields_redacted == []


def test_staging_default_context_uses_strip_pii() -> None:
    """Convenience constructor wires STRIP_PII for staging env."""
    ctx = staging_default_context()
    assert ctx.env == "staging"
    assert ctx.policy == RedactionPolicy.STRIP_PII
    assert ctx.redaction_fields == set(PII_FIELDS)


def test_invalid_env_raises() -> None:
    """Unknown env string is rejected at construction time."""
    with pytest.raises(ValueError, match="invalid env"):
        RedactionContext(env="moon", policy=RedactionPolicy.ALLOW_ALL)
