"""REQ-033 contract fixture builders (T023).

Plain factory functions that construct ORM instances for the eleven
033 telemetry / eval / badcase / redaction tables defined in
``backend/app/modules/telemetry_contracts/models.py`` (mirrors
``migrations/versions/0024_033_eval_pm_dashboard.py``).

Each factory accepts an ``**overrides`` keyword bag so test code can
override any column without re-typing the whole shape.  Defaults match
the most common happy-path values from ``specs/033-eval-pm-dashboard/
data-model.md``.

Why plain factory functions (not factory_boy):
    The project does not use factory_boy elsewhere; pulling it in for
    five factories is overkill.  These factories only set ORM fields
    they care about and rely on column defaults / mapped defaults for
    the rest.  No DB session is opened — call sites do
    ``async with get_session_context(user_id=...) as session:``
    and call ``session.add(row)`` themselves, mirroring
    ``tests/contract/test_agents_api.py`` fixtures.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.core.ids import new_uuid_v7
from app.modules.telemetry_contracts.events import (
    AIInvocationSummary,
    MetricSnapshot,
    ProductEvent,
)
from app.modules.telemetry_contracts.models import (
    AIInvocationRecord,
    Badcase,
    BadcaseReviewAction,
    EvalCaseResult,
    EvalRun,
    LangSmithExperimentRef,
    PMMetricSnapshot,
    ProductFunnelEvent,
    RedactionAudit,
    RedactionPolicy,
    TraceRunRef,
)

__all__ = [
    "ai_invocation_record",
    "badcase",
    "badcase_review_action",
    "eval_case_result",
    "eval_run",
    "langsmith_experiment_ref",
    "metric_snapshot",
    "product_funnel_event",
    "redaction_audit",
    "redaction_policy",
    "trace_run_ref",
]


# ---------------------------------------------------------------------------
# EvalRun
# ---------------------------------------------------------------------------


def eval_run(**overrides: Any) -> EvalRun:
    """Construct an unsaved :class:`EvalRun` ORM instance.

    Defaults to a STAGING env / STARTED status row with a 24h-ago
    ``started_at``.  Pass ``run_id`` to override; otherwise a UUIDv7 is
    generated.  Always requires ``user_id`` (FK target).
    """
    defaults: dict[str, Any] = {
        "run_id": new_uuid_v7(),
        "user_id": uuid4(),
        "source_revision": "abc1234",
        "branch": "main",
        "environment": "STAGING",
        "status": "STARTED",
        "started_at": datetime.now(UTC) - timedelta(hours=1),
        "completed_at": None,
        "aggregate_pass_rate": None,
        "known_regression_recall": None,
        "stale_case_count": None,
        "budget_tokens": None,
        "budget_cost": None,
        "version_context": {"app_version": "0.33.0"},
    }
    defaults.update(overrides)
    return EvalRun(**defaults)


# ---------------------------------------------------------------------------
# EvalCaseResult
# ---------------------------------------------------------------------------


def eval_case_result(run_id: UUID, **overrides: Any) -> EvalCaseResult:
    """Construct an unsaved :class:`EvalCaseResult`.

    Pass ``run_id`` (required FK); ``user_id`` defaults to a fresh UUID.
    """
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "run_id": run_id,
        "user_id": uuid4(),
        "case_id": "case.demo.001",
        "verdict": "PENDING",
        "failure_reason": None,
        "metrics": {},
        "trace_id": None,
        "artifact_ref": None,
    }
    defaults.update(overrides)
    return EvalCaseResult(**defaults)


# ---------------------------------------------------------------------------
# LangSmithExperimentRef
# ---------------------------------------------------------------------------


def langsmith_experiment_ref(run_id: UUID, **overrides: Any) -> LangSmithExperimentRef:
    """Construct an unsaved :class:`LangSmithExperimentRef`."""
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "run_id": run_id,
        "user_id": uuid4(),
        "project": "intercraft-staging",
        "dataset": "interview-graph@v1",
        "experiment_name": "main-abc1234-20260628",
        "external_id": None,
        "url": None,
        "sync_status": "PENDING",
        "sync_error": None,
        "synced_at": None,
    }
    defaults.update(overrides)
    return LangSmithExperimentRef(**defaults)


# ---------------------------------------------------------------------------
# TraceRunRef
# ---------------------------------------------------------------------------


def trace_run_ref(**overrides: Any) -> TraceRunRef:
    """Construct an unsaved :class:`TraceRunRef`.

    ``trace_id`` is unique — caller can override to force a specific id.
    """
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "trace_id": f"trace-{uuid4().hex[:12]}",
        "run_id": None,
        "user_id": uuid4(),
        "environment": "STAGING",
        "sampling_decision": "NOT_ENABLED",
        "privacy_class": "PUBLIC_METADATA",
        "redaction_status": "NOT_REQUIRED",
        "retention_expires_at": datetime.now(UTC) + timedelta(days=30),
    }
    defaults.update(overrides)
    return TraceRunRef(**defaults)


# ---------------------------------------------------------------------------
# ProductFunnelEvent
# ---------------------------------------------------------------------------


def product_funnel_event(**overrides: Any) -> ProductFunnelEvent:
    """Construct an unsaved :class:`ProductFunnelEvent`.

    The SQLAlchemy column for ``metadata`` is exposed as
    ``metadata_`` (Python identifier); callers override via
    ``metadata_={...}``.  ``version_context`` defaults to a doc that
    matches the spec §Event Schema Draft.
    """
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "event_name": "resume.diagnosis_completed",
        "occurred_at": datetime.now(UTC),
        "actor_hash": None,
        "user_hash": None,
        "session_hash": None,
        "thread_hash": None,
        "feature_area": "RESUME",
        "version_context": {
            "app_version": "0.33.0",
            "release_stage": "RELEASE_CANDIDATE",
            "environment": "STAGING",
            "prompt_fingerprint": "unknown",
            "rubric_version": "unknown",
            "model": "deepseek-v4-pro",
            "schema_version": "v1",
        },
        "privacy_class": "PUBLIC_METADATA",
        "redaction_status": "NOT_REQUIRED",
        "metadata_": {"template.id": "modern", "duration_ms": 1234},
        "user_id": uuid4(),
    }
    defaults.update(overrides)
    return ProductFunnelEvent(**defaults)


# ---------------------------------------------------------------------------
# AIInvocationRecord
# ---------------------------------------------------------------------------


def ai_invocation_record(**overrides: Any) -> AIInvocationRecord:
    """Construct an unsaved :class:`AIInvocationRecord`.

    ``invocation_id`` is unique — caller may override to dedupe between
    calls in the same test.
    """
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "invocation_id": uuid4(),
        "run_id": None,
        "trace_id": None,
        "graph": "interview",
        "node": "score_node",
        "model": "deepseek-v4-pro",
        "prompt_fingerprint": "sha256:" + uuid4().hex,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "estimated_cost": None,
        "latency_ms": 850,
        "retry_count": 0,
        "status": "SUCCESS",
        "error_category": None,
        "user_id": uuid4(),
    }
    defaults.update(overrides)
    return AIInvocationRecord(**defaults)


# ---------------------------------------------------------------------------
# PMMetricSnapshot
# ---------------------------------------------------------------------------


def metric_snapshot(**overrides: Any) -> PMMetricSnapshot:
    """Construct an unsaved :class:`PMMetricSnapshot`.

    Period defaults to a 1-day window ending now.  ``metric_id`` should
    match one of the registered ids in
    :mod:`app.modules.telemetry_contracts.metrics`.
    """
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "metric_id": "ai.success_rate",
        "period_start": now - timedelta(days=1),
        "period_end": now,
        "grain": "DAY",
        "dimensions": {"environment": "STAGING", "model": "deepseek-v4-pro"},
        "numerator": 98,
        "denominator": 100,
        "value": 0.98,
        "unit": "PERCENT",
        "source_of_truth": "ai_invocation_records",
        "freshness_at": now,
        "quality_flags": {},
        "user_id": uuid4(),
    }
    defaults.update(overrides)
    return PMMetricSnapshot(**defaults)


# ---------------------------------------------------------------------------
# Badcase
# ---------------------------------------------------------------------------


def badcase(**overrides: Any) -> Badcase:
    """Construct an unsaved :class:`Badcase`.

    ``badcase_id`` is the human-readable join key (string) and must be
    unique across rows.
    """
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "badcase_id": f"bc-{uuid4().hex[:12]}",
        "type": "AI_RELIABILITY",
        "severity": "MEDIUM",
        "status": "OPEN",
        "source": "eval_failure",
        "reviewer": None,
        "privacy_class": "PUBLIC_METADATA",
        "redaction_status": "NOT_REQUIRED",
        "run_id": None,
        "trace_id": None,
        "closure_reason": None,
        "closed_at": None,
        "user_id": uuid4(),
    }
    defaults.update(overrides)
    return Badcase(**defaults)


# ---------------------------------------------------------------------------
# BadcaseReviewAction
# ---------------------------------------------------------------------------


def badcase_review_action(
    badcase_id: str, **overrides: Any
) -> BadcaseReviewAction:
    """Construct an unsaved :class:`BadcaseReviewAction`.

    ``badcase_id`` is the FK target (string).  ``action_type`` defaults
    to CREATE.
    """
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "badcase_id": badcase_id,
        "action_type": "CREATE",
        "actor_role": "badcase_reviewer",
        "reason": None,
        "evidence_ref": None,
    }
    defaults.update(overrides)
    return BadcaseReviewAction(**defaults)


# ---------------------------------------------------------------------------
# RedactionPolicy (global — no user_id)
# ---------------------------------------------------------------------------


def redaction_policy(**overrides: Any) -> RedactionPolicy:
    """Construct an unsaved :class:`RedactionPolicy`.

    Defaults match the production policy (30-day retention + requires
    human review).  No ``user_id`` column.
    """
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "policy_version": "v1",
        "environment": "PRODUCTION",
        "allowed_classes": ["PUBLIC_METADATA", "INTERNAL_METADATA", "REDACTED_SUMMARY"],
        "forbidden_classes": ["SENSITIVE_USER_CONTENT", "SECRET"],
        "summary_rules": {"strip_pii": True, "max_summary_tokens": 256},
        "retention_days": 30,
        "requires_human_review": True,
    }
    defaults.update(overrides)
    return RedactionPolicy(**defaults)


# ---------------------------------------------------------------------------
# RedactionAudit (global — no user_id)
# ---------------------------------------------------------------------------


def redaction_audit(**overrides: Any) -> RedactionAudit:
    """Construct an unsaved :class:`RedactionAudit`."""
    defaults: dict[str, Any] = {
        "id": new_uuid_v7(),
        "audit_id": f"audit-{uuid4().hex[:12]}",
        "policy_version": "v1",
        "environment": "PRODUCTION",
        "sample_count": 100,
        "forbidden_content_failures": 0,
        "result": "PASSED",
        "reviewer": "qa-bot",
        "evidence_ref": "docs/evidence/033-eval-pm-dashboard/redaction/v1.json",
    }
    defaults.update(overrides)
    return RedactionAudit(**defaults)


# ---------------------------------------------------------------------------
# Dataclass helpers (re-export under fixture-style names for ergonomic use)
# ---------------------------------------------------------------------------


def product_event(**overrides: Any) -> ProductEvent:
    """Construct a :class:`ProductEvent` dataclass instance.

    Mirrors :func:`product_funnel_event` but returns the pure-Python
    dataclass from ``events.py`` (no ORM dependency).  Used by tests that
    exercise the JSON round-trip path rather than persistence.
    """
    defaults: dict[str, Any] = {
        "name": "resume.diagnosis_completed",
        "occurred_at": datetime.now(UTC),
        "properties": {},
        "event_id": uuid4(),
        "user_id": uuid4(),
        "environment": "STAGING",
        "release_stage": "RELEASE_CANDIDATE",
        "app_version": "0.33.0",
        "feature_area": "RESUME",
        "privacy_class": "PUBLIC_METADATA",
        "redaction_status": "NOT_REQUIRED",
    }
    defaults.update(overrides)
    return ProductEvent(**defaults)


def ai_invocation_summary(**overrides: Any) -> AIInvocationSummary:
    """Construct an :class:`AIInvocationSummary` dataclass instance."""
    defaults: dict[str, Any] = {
        "invocation_id": uuid4(),
        "graph_name": "interview",
        "run_id": None,
        "model": "deepseek-v4-pro",
        "tokens_in": 100,
        "tokens_out": 50,
        "latency_ms": 850,
        "cached": False,
        "error": None,
    }
    defaults.update(overrides)
    return AIInvocationSummary(**defaults)


def metric_snapshot_dataclass(**overrides: Any) -> MetricSnapshot:
    """Construct a :class:`MetricSnapshot` dataclass instance."""
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "metric_id": "ai.success_rate",
        "name": "AI Success Rate",
        "value": 0.98,
        "captured_at": now,
        "unit": "percent",
        "dimensions": {"environment": "STAGING"},
        "numerator": 98,
        "denominator": 100,
        "snapshot_id": uuid4(),
        "source_of_truth": "ai_invocation_records",
        "freshness_at": now,
    }
    defaults.update(overrides)
    return MetricSnapshot(**defaults)
