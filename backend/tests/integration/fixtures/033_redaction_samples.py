"""REQ-033 US10 — redaction sample fixtures (T031).

Pytest factory functions that build export-payload-shaped dicts for the
forbidden-content checks performed by US10 (FR-031..FR-036) and the
``audit_redaction`` / ``enforce_export_policy`` integration paths.

Each fixture returns a plain ``dict`` (not a dataclass) so it round-trips
through JSON loaders without ORM / DB context. The dict shape mirrors
what an eval / LangSmith / external report consumer would receive when
exporting an evaluation result, a trace, a badcase, or a raw AI call.

Forbidden-content rules under FR-032 / SC-008:

- production export MUST NOT contain raw resume text, interview answers,
  JD text, free-form chat, access/refresh tokens, API keys, passwords.
- staging export is permitted to send masked prompt / output for
  synthetic / golden / approved staging test data; otherwise metadata +
  redacted summaries only.

Forbidden-content detection (the production redaction audit looks for
the keys ``resume_text``, ``interview_answer``, ``job_description``,
``free_form_text``, ``api_key``, ``access_token``, ``refresh_token``,
``password``, ``secret`` in the payload properties/metadata bag).

Override approval fixture (FR-024 / dual approval):

- ``override_record_dual_signed`` — both PM business owner and technical
  owner signed; override is APPROVED.
- ``override_record_single_signed`` — only one approver signed; override
  is NOT approved (hard fail per FR-024).

Each override record carries the structured shape documented in
``specs/033-eval-pm-dashboard/data-model.md`` §BadcaseReviewAction
``actionType == OVERRIDE`` plus reason / evidence / timestamp.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

__all__ = [
    "forbidden_resume_sample",
    "forbidden_interview_answer_sample",
    "forbidden_jd_sample",
    "forbidden_secret_sample",
    "forbidden_free_form_sample",
    "approved_synthetic_sample",
    "golden_case_sample",
    "override_record_dual_signed",
    "override_record_single_signed",
    "contains_forbidden_keys",
]


# Keys that MUST NOT appear in a production export payload per FR-032.
# Lower-case — comparison is case-insensitive.
FORBIDDEN_PRODUCTION_KEYS: frozenset[str] = frozenset(
    {
        "resume_text",
        "interview_answer",
        "job_description",
        "free_form_text",
        "api_key",
        "access_token",
        "refresh_token",
        "password",
        "secret",
    }
)


def _envelope(
    *,
    environment: str,
    properties: dict[str, Any],
    name: str = "eval.case_result",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical export-payload envelope."""
    body: dict[str, Any] = {
        "event_id": str(uuid4()),
        "name": name,
        "occurred_at": datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC).isoformat(),
        "environment": environment,
        "release_stage": "RELEASE_CANDIDATE",
        "app_version": "0.33.0",
        "feature_area": "EVAL",
        "privacy_class": "PUBLIC_METADATA",
        "redaction_status": "PENDING",
        "properties": dict(properties),
    }
    if extra:
        body.update(extra)
    return body


# ---------------------------------------------------------------------------
# Forbidden-content samples (production must REJECT)
# ---------------------------------------------------------------------------


def forbidden_resume_sample() -> dict[str, Any]:
    """Export payload that contains raw resume text — production MUST reject."""
    return _envelope(
        environment="production",
        properties={
            "case_id": "case.demo.001",
            "graph": "resume_optimize",
            "node": "suggest_blocks",
            "run_id": str(uuid4()),
            "resume_text": (
                "John Doe · 5y backend · Built payment pipeline at Acme · "
                "Skills: Python, Go, Postgres"
            ),
            "duration_ms": 1234,
        },
    )


def forbidden_interview_answer_sample() -> dict[str, Any]:
    """Export payload containing a raw interview answer."""
    return _envelope(
        environment="production",
        properties={
            "case_id": "case.interview.001",
            "graph": "interview",
            "node": "score_node",
            "interview_answer": (
                "In my previous role I led a team of four engineers to "
                "ship a fraud-detection service."
            ),
            "rubric_version": "v1",
        },
    )


def forbidden_jd_sample() -> dict[str, Any]:
    """Export payload containing raw JD text."""
    return _envelope(
        environment="production",
        properties={
            "case_id": "case.jd.001",
            "job_description": (
                "We are looking for a senior backend engineer with 5+ "
                "years of experience in distributed systems."
            ),
        },
    )


def forbidden_secret_sample() -> dict[str, Any]:
    """Export payload containing a secret / API key."""
    return _envelope(
        environment="production",
        properties={
            "case_id": "case.secret.001",
            "api_key": "sk-live-abcdef0123456789",
        },
    )


def forbidden_free_form_sample() -> dict[str, Any]:
    """Export payload containing raw free-form user chat text."""
    return _envelope(
        environment="production",
        properties={
            "case_id": "case.chat.001",
            "free_form_text": (
                "User typed: I'm looking for a new role because my manager "
                "is unreasonable."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Approved samples (CI / staging / production-redacted-summary)
# ---------------------------------------------------------------------------


def approved_synthetic_sample() -> dict[str, Any]:
    """Synthetic eval data — no forbidden content; permitted in dev/CI."""
    return _envelope(
        environment="ci",
        properties={
            "case_id": "case.synthetic.001",
            "graph": "resume_optimize",
            "node": "suggest_blocks",
            "score": 9.0,
            "duration_ms": 1234,
            "template_id": "modern",
        },
    )


def golden_case_sample() -> dict[str, Any]:
    """Version-controlled golden case — permitted in CI/staging per FR-034."""
    return _envelope(
        environment="staging",
        properties={
            "case_id": "case.golden.001",
            "source": "MANUAL",
            "schema_version": "v1",
            "rubric_version": "v1",
            "expected_score_range": [7, 10],
            "upload_policy": "LANGSMITH_ALLOWED",
        },
    )


# ---------------------------------------------------------------------------
# Override (dual approval) records
# ---------------------------------------------------------------------------


def override_record_dual_signed(
    *,
    pm_approver: str = "pm.alice",
    technical_approver: str = "tech.bob",
    reason: str = "Known broken eval case (case.demo.001) — to be fixed next sprint",
    evidence: str = "docs/evidence/033-eval-pm-dashboard/eval-report-sample-2026-06-28.json",
) -> dict[str, Any]:
    """Override record with BOTH PM + technical owner approvals (FR-024)."""
    return {
        "override_id": str(uuid4()),
        "action_type": "OVERRIDE",
        "run_id": str(uuid4()),
        "gate": "pr_eval",
        "approvals": [
            {
                "actor_role": "PM_BUSINESS_OWNER",
                "actor": pm_approver,
                "approved_at": datetime(2026, 6, 28, 9, 0, 0, tzinfo=UTC).isoformat(),
            },
            {
                "actor_role": "TECHNICAL_OWNER",
                "actor": technical_approver,
                "approved_at": datetime(2026, 6, 28, 9, 30, 0, tzinfo=UTC).isoformat(),
            },
        ],
        "reason": reason,
        "evidence_ref": evidence,
        "created_at": datetime(2026, 6, 28, 9, 30, 0, tzinfo=UTC).isoformat(),
    }


def override_record_single_signed(
    *,
    pm_approver: str = "pm.alice",
) -> dict[str, Any]:
    """Override record with ONLY PM approval — must fail dual-approval gate."""
    return {
        "override_id": str(uuid4()),
        "action_type": "OVERRIDE",
        "run_id": str(uuid4()),
        "gate": "pr_eval",
        "approvals": [
            {
                "actor_role": "PM_BUSINESS_OWNER",
                "actor": pm_approver,
                "approved_at": datetime(2026, 6, 28, 9, 0, 0, tzinfo=UTC).isoformat(),
            },
        ],
        "reason": "single-signer attempt",
        "evidence_ref": "docs/evidence/033-eval-pm-dashboard/eval-report-sample.json",
        "created_at": datetime(2026, 6, 28, 9, 0, 0, tzinfo=UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def contains_forbidden_keys(payload: dict[str, Any]) -> list[str]:
    """Return the list of forbidden keys present in ``payload``.

    Walks ``payload["properties"]`` (and ``payload["metadata"]`` if
    present). Comparison is case-insensitive against
    :data:`FORBIDDEN_PRODUCTION_KEYS`. Empty list means the payload is
    safe to export under FR-032.
    """
    found: list[str] = []
    candidates: dict[str, Any] = {}
    for k in ("properties", "metadata"):
        v = payload.get(k)
        if isinstance(v, dict):
            candidates.update(v)
    for k in candidates:
        if k.lower() in FORBIDDEN_PRODUCTION_KEYS:
            found.append(k)
    return found


# ---------------------------------------------------------------------------
# Pytest fixture bindings
# ---------------------------------------------------------------------------


@pytest.fixture
def forbidden_resume() -> dict[str, Any]:
    """Pytest wrapper around :func:`forbidden_resume_sample`."""
    return forbidden_resume_sample()


@pytest.fixture
def forbidden_interview_answer() -> dict[str, Any]:
    """Pytest wrapper around :func:`forbidden_interview_answer_sample`."""
    return forbidden_interview_answer_sample()


@pytest.fixture
def forbidden_jd() -> dict[str, Any]:
    """Pytest wrapper around :func:`forbidden_jd_sample`."""
    return forbidden_jd_sample()


@pytest.fixture
def forbidden_secret() -> dict[str, Any]:
    """Pytest wrapper around :func:`forbidden_secret_sample`."""
    return forbidden_secret_sample()


@pytest.fixture
def forbidden_free_form() -> dict[str, Any]:
    """Pytest wrapper around :func:`forbidden_free_form_sample`."""
    return forbidden_free_form_sample()


@pytest.fixture
def approved_synthetic() -> dict[str, Any]:
    """Pytest wrapper around :func:`approved_synthetic_sample`."""
    return approved_synthetic_sample()


@pytest.fixture
def golden_case() -> dict[str, Any]:
    """Pytest wrapper around :func:`golden_case_sample`."""
    return golden_case_sample()


@pytest.fixture
def override_dual_signed() -> dict[str, Any]:
    """Pytest wrapper around :func:`override_record_dual_signed`."""
    return override_record_dual_signed()


@pytest.fixture
def override_single_signed() -> dict[str, Any]:
    """Pytest wrapper around :func:`override_record_single_signed`."""
    return override_record_single_signed()