"""REQ-033 US10 — redaction audit / export-policy integration tests (T025).

Covers the cross-module behaviour that ties :mod:`app.eval.export_policy`
to the :mod:`app.modules.telemetry_contracts.redaction` library. Each
case here corresponds to a specific spec scenario in
``specs/033-eval-pm-dashboard/spec.md`` §US10 or a Success Criterion:

- AC-01 production forbidden content (resume / interview / JD / free-form
  / secret) → audit fails (exit 3 / status ``FAILED``).
- AC-02 staging synthetic + golden + approved staging payloads pass.
- AC-03 non-prod forbidden content is stripped (not silently allowed).
- AC-04 dual approval gate (FR-024) — single signer is hard-rejected.
- AC-05 fail-open runtime (FR-017) — unexpected exception during
  preparation must NOT raise to product code.

Tests use the ``tests/integration/fixtures/033_redaction_samples.py``
factories and do not require a DB / Redis / network. The integration
marker is applied so collection grouping stays consistent with the rest
of the US10 evidence bundle.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration

from app.eval.export_policy import (
    FORBIDDEN_PRODUCTION_KEYS,
    PolicyViolation,
    RedactionResult,
    assert_override_approved,
    context_for_environment,
    enforce_export_policy,
    find_forbidden_keys,
    is_override_approved,
    prepare_export_payload,
    safe_prepare_export_payload,
)
from app.modules.telemetry_contracts.redaction import (
    RedactionPolicy,
    audit_redaction,
    production_default_context,
    staging_default_context,
    validate_redaction,
)
from app.modules.telemetry_contracts.events import ProductEvent

# Lazy-load the fixture factories so this module can be imported even if
# the fixtures package is not on sys.path for some test runner setup.
_FIX = Path(__file__).parent / "fixtures" / "033_redaction_samples.py"
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("_redaction_samples", _FIX)
assert _spec and _spec.loader
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
forbidden_resume_sample = _mod.forbidden_resume_sample
forbidden_interview_answer_sample = _mod.forbidden_interview_answer_sample
forbidden_jd_sample = _mod.forbidden_jd_sample
forbidden_secret_sample = _mod.forbidden_secret_sample
forbidden_free_form_sample = _mod.forbidden_free_form_sample
approved_synthetic_sample = _mod.approved_synthetic_sample
golden_case_sample = _mod.golden_case_sample
override_record_dual_signed = _mod.override_record_dual_signed
override_record_single_signed = _mod.override_record_single_signed
contains_forbidden_keys = _mod.contains_forbidden_keys


# ---------------------------------------------------------------------------
# AC-01 — production forbidden content blocks audit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample_factory",
    [
        forbidden_resume_sample,
        forbidden_interview_answer_sample,
        forbidden_jd_sample,
        forbidden_free_form_sample,
        forbidden_secret_sample,
    ],
    ids=["resume_text", "interview_answer", "job_description", "free_form", "secret"],
)
def test_production_forbidden_content_blocks_export(sample_factory) -> None:
    """Any forbidden production content → ``payload=None`` and ``FAILED`` status."""
    payload = sample_factory()
    result = prepare_export_payload(payload, environment="production")

    assert isinstance(result, RedactionResult)
    assert result.payload is None
    assert result.redaction_status == "FAILED"
    assert result.violations, "violations list should enumerate the forbidden keys"


def test_production_audit_records_failure_metadata() -> None:
    """The audit (``audit_redaction``) records the policy + env used."""
    event = ProductEvent(
        name="eval.case_result",
        occurred_at=datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC),
        properties={"resume_text": "raw resume content", "score": 9.0},
    )
    ctx = production_default_context()
    redacted = event.__class__(
        name=event.name,
        occurred_at=event.occurred_at,
        properties={},  # METADATA_ONLY replaces with {}
        event_id=event.event_id,
        user_id=None,  # forced in production
        environment=event.environment,
        release_stage=event.release_stage,
        app_version=event.app_version,
        feature_area=event.feature_area,
        privacy_class=event.privacy_class,
        redaction_status="PASSED",
    )
    audit = audit_redaction(event, ctx, redacted)
    assert audit.policy_applied == RedactionPolicy.METADATA_ONLY
    assert audit.env == "production"
    # ``resume_text`` + ``score`` were both in properties before redaction;
    # METADATA_ONLY replaces properties -> both appear in fields_redacted.
    assert "resume_text" in audit.fields_redacted
    assert "score" in audit.fields_redacted


def test_production_validate_redaction_flags_properties() -> None:
    """``validate_redaction`` reports ``properties`` as a violation when non-empty under METADATA_ONLY."""
    event = ProductEvent(
        name="eval.case_result",
        occurred_at=datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC),
        properties={"resume_text": "raw"},
    )
    violations = validate_redaction(RedactionPolicy.METADATA_ONLY, event)
    assert "properties" in violations


def test_production_enforce_export_policy_raises() -> None:
    """``enforce_export_policy`` raises ``PolicyViolation`` for prod + forbidden content."""
    payload = forbidden_resume_sample()
    with pytest.raises(PolicyViolation) as exc_info:
        enforce_export_policy(payload, environment="production", sample_id="ac-01")
    assert "resume_text" in exc_info.value.violations
    assert exc_info.value.environment == "production"


# ---------------------------------------------------------------------------
# AC-02 — staging synthetic / golden / approved pass
# ---------------------------------------------------------------------------


def test_staging_synthetic_payload_passes() -> None:
    """Synthetic staging payload with no forbidden content → PASSED."""
    payload = approved_synthetic_sample()
    # Mutate to staging context for the test.
    payload["environment"] = "staging"
    result = prepare_export_payload(payload, environment="staging")
    assert result.payload is not None
    assert result.redaction_status == "PASSED"
    assert result.violations == []
    assert result.payload["environment"] == "staging"


def test_staging_golden_case_payload_passes() -> None:
    """Golden-case staging payload passes (FR-034 allows synthetic / golden / approved)."""
    payload = golden_case_sample()
    result = prepare_export_payload(payload, environment="staging")
    assert result.payload is not None
    assert result.redaction_status == "PASSED"
    assert result.violations == []


def test_staging_default_context_is_strip_pii() -> None:
    """Convenience constructor wires STRIP_PII for staging env."""
    ctx = staging_default_context()
    assert ctx.env == "staging"
    assert ctx.policy == RedactionPolicy.STRIP_PII


def test_production_default_context_is_metadata_only() -> None:
    """Production default context applies METADATA_ONLY (the strictest policy)."""
    ctx = production_default_context()
    assert ctx.env == "production"
    assert ctx.policy == RedactionPolicy.METADATA_ONLY


# ---------------------------------------------------------------------------
# AC-03 — raw user content in non-production is detected (and stripped)
# ---------------------------------------------------------------------------


def test_non_production_forbidden_content_is_detected_and_stripped() -> None:
    """Non-prod forbidden content is flagged and stripped from the payload."""
    payload = forbidden_resume_sample()
    payload["environment"] = "staging"
    result = prepare_export_payload(payload, environment="staging")

    assert result.violations, "violations should still be reported"
    assert result.redacted, "forbidden content must be stripped"
    assert result.payload is not None
    cleaned_props = result.payload.get("properties") or {}
    for k in cleaned_props:
        assert k.lower() not in FORBIDDEN_PRODUCTION_KEYS
    # Status remains FAILED so callers can choose to skip external upload.
    assert result.redaction_status == "FAILED"


def test_find_forbidden_keys_walks_properties_and_metadata() -> None:
    """``find_forbidden_keys`` walks both properties and metadata containers."""
    payload = {
        "properties": {"resume_text": "x", "ok": 1},
        "metadata": {"api_key": "y"},
    }
    found = find_forbidden_keys(payload)
    assert set(found) == {"resume_text", "api_key"}


def test_find_forbidden_keys_empty_when_safe() -> None:
    payload = {"properties": {"score": 9}, "metadata": {"graph": "interview"}}
    assert find_forbidden_keys(payload) == []


def test_contains_forbidden_keys_helper_matches_factory() -> None:
    """Fixture helper ``contains_forbidden_keys`` agrees with the policy module."""
    payload = forbidden_secret_sample()
    found_helper = contains_forbidden_keys(payload)
    found_module = find_forbidden_keys(payload)
    assert found_helper == found_module
    assert "api_key" in found_helper


# ---------------------------------------------------------------------------
# AC-04 — dual approval gate (FR-024)
# ---------------------------------------------------------------------------


def test_override_dual_signed_is_approved() -> None:
    """Both PM + technical owner signed → ``is_override_approved`` returns True."""
    rec = override_record_dual_signed()
    assert is_override_approved(rec) is True
    # assert_override_approved must NOT raise.
    assert_override_approved(rec)


def test_override_single_signed_is_hard_rejected() -> None:
    """Single-signer override must hard-fail dual approval."""
    rec = override_record_single_signed()
    assert is_override_approved(rec) is False
    with pytest.raises(PolicyViolation) as exc_info:
        assert_override_approved(rec)
    assert "missing_dual_approval" in exc_info.value.violations


def test_override_with_only_technical_owner_is_hard_rejected() -> None:
    """Only technical owner → still hard-rejected (need BOTH)."""
    rec = {
        "approvals": [
            {
                "actor_role": "TECHNICAL_OWNER",
                "actor": "tech.bob",
                "approved_at": datetime(2026, 6, 28, tzinfo=UTC).isoformat(),
            },
        ],
        "reason": "missing PM sign-off",
    }
    assert is_override_approved(rec) is False


def test_override_empty_record_is_hard_rejected() -> None:
    assert is_override_approved({}) is False
    assert is_override_approved({"approvals": []}) is False
    assert is_override_approved(None) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-05 — fail-open runtime (FR-017)
# ---------------------------------------------------------------------------


def test_fail_open_when_prepare_raises_unexpected() -> None:
    """Unexpected exception in prepare_export_payload must NOT propagate.

    FR-017: LangSmith integration MUST fail open for product runtime.
    """
    # Trigger an unexpected error by passing a non-mapping type.
    bogus = object()  # ``dict(bogus)`` would TypeError inside _find.
    result = safe_prepare_export_payload(bogus, environment="production")  # type: ignore[arg-type]
    assert isinstance(result, RedactionResult)
    assert result.redaction_status == "FAILED"
    assert result.payload is None
    # Sanity: production runtime continues, no exception raised.


def test_fail_open_returns_failed_status_not_raises() -> None:
    """``safe_prepare_export_payload`` returns a result; never raises."""
    payload = forbidden_resume_sample()
    result = safe_prepare_export_payload(payload, environment="production")
    assert isinstance(result, RedactionResult)
    assert result.payload is None
    assert result.redaction_status == "FAILED"


# ---------------------------------------------------------------------------
# Auxiliary — context_for_environment routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env,expected_policy",
    [
        ("production", RedactionPolicy.METADATA_ONLY),
        ("PRODUCTION", RedactionPolicy.METADATA_ONLY),
        ("prod", RedactionPolicy.METADATA_ONLY),
        ("staging", RedactionPolicy.STRIP_PII),
        ("Staging", RedactionPolicy.STRIP_PII),
        ("ci", RedactionPolicy.ALLOW_ALL),
        ("local", RedactionPolicy.ALLOW_ALL),
        ("dev", RedactionPolicy.ALLOW_ALL),
    ],
)
def test_context_for_environment_routing(env, expected_policy) -> None:
    """``context_for_environment`` maps env strings to the right policy."""
    ctx = context_for_environment(env)
    assert ctx.policy == expected_policy


# ---------------------------------------------------------------------------
# Audit report shape (SC-008 evidence path)
# ---------------------------------------------------------------------------


def test_audit_result_serializes_to_json() -> None:
    """The ``RedactionResult`` shape is JSON-serializable for CLI stdout."""
    payload = approved_synthetic_sample()
    payload["environment"] = "staging"
    result = prepare_export_payload(payload, environment="staging")
    assert result.payload is not None
    blob = json.dumps(result.payload, default=str)
    restored = json.loads(blob)
    assert restored["environment"] == "staging"
    assert restored["redaction_status"] == "PASSED"