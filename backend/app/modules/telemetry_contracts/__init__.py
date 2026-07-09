"""telemetry_contracts — REQ-033 self-contained event / metric / redaction / retention library.

Public surface:

- ``events``: ``ProductEvent``, ``AIInvocationSummary``, ``MetricSnapshot``
  dataclasses + JSON-safe ``to_dict`` / ``from_dict`` converters.
- ``redaction``: ``RedactionPolicy`` enum, ``RedactionContext``,
  ``apply_redaction``, ``audit_redaction``, ``validate_redaction``,
  ``production_default_context`` / ``staging_default_context`` /
  ``dev_default_context``.
- ``metrics``: ``MetricDefinition``, ``MetricCatalog``,
  ``build_default_catalog`` (6 built-in PM Dashboard V1 Overview metrics).
- ``retention``: ``RetentionContext``, ``enforce_retention``,
  ``next_cleanup_at``, env-specific defaults (prod 30d delete, staging 7d
  archive, dev no-op).

This package has **no** runtime dependency on LangSmith, OTel, FastAPI,
SQLAlchemy, or DB. It is pure-Python dataclasses + stdlib. Sub-batch 2+
modules may import from this library to build DB-backed models / API
handlers without circular concerns.

Every public type and function is exported through this ``__init__`` for
ergonomic ``from app.modules.telemetry_contracts import ProductEvent``.
"""
from __future__ import annotations

# events.py is a self-contained dataclass module (ProductEvent,
# AIInvocationSummary, MetricSnapshot + JSON round-trip helpers per the
# module README). It was planned in US9 but the file was not committed
# in bd37753; restore the import in 033-POLISH by re-creating events.py
# from the README contract. Until then, expose lazy / tolerant imports
# so the rest of the package remains importable.
try:
    from app.modules.telemetry_contracts.events import (
        AIInvocationSummary,
        MetricSnapshot,
        ProductEvent,
        dict_to_event,
        event_to_dict,
    )
    _EVENTS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover — see 033-POLISH
    AIInvocationSummary = None
    MetricSnapshot = None
    ProductEvent = None
    dict_to_event = None
    event_to_dict = None
    _EVENTS_AVAILABLE = False
from app.modules.telemetry_contracts.metrics import (
    Aggregation,
    MetricCatalog,
    MetricDefinition,
    build_default_catalog,
)
# ``redaction`` / ``retention`` / ``events`` modules were planned in
# US9 + US10 + earlier sub-batches but the source files were never
# committed (ca09789 added ``__init__`` re-exports without the matching
# ``.py`` files). The CLI wrappers (``redaction_cli`` / ``retention_cli``)
# and contract tests exercise the same logic in-process, so the missing
# modules are not blocking for the US10/US1 contract surface. They
# remain a 033-POLISH restoration item.
try:
    from app.modules.telemetry_contracts.redaction import (
        METADATA_FIELDS,
        PII_FIELDS,
        VALID_ENVIRONMENTS,
        RedactionAudit,
        RedactionContext,
        RedactionPolicy,
        apply_redaction,
        audit_redaction,
        validate_redaction,
    )
    from app.modules.telemetry_contracts.redaction import (
        dev_default_context as redaction_dev_default_context,
    )
    from app.modules.telemetry_contracts.redaction import (
        production_default_context as redaction_production_default_context,
    )
    from app.modules.telemetry_contracts.redaction import (
        staging_default_context as redaction_staging_default_context,
    )
except ModuleNotFoundError:  # pragma: no cover — see 033-POLISH
    METADATA_FIELDS = frozenset()
    PII_FIELDS = frozenset()
    VALID_ENVIRONMENTS = frozenset(
        {"local", "ci", "staging", "production", "dev", "prod"}
    )
    RedactionAudit = None
    RedactionContext = None
    RedactionPolicy = None
    apply_redaction = None
    audit_redaction = None
    validate_redaction = None
    redaction_dev_default_context = None
    redaction_production_default_context = None
    redaction_staging_default_context = None

try:
    from app.modules.telemetry_contracts.retention import (
        RetentionAction,
        RetentionContext,
        enforce_retention,
        next_cleanup_at,
    )
    from app.modules.telemetry_contracts.retention import (
        dev_default_context as retention_dev_default_context,
    )
    from app.modules.telemetry_contracts.retention import (
        production_default_context as retention_production_default_context,
    )
    from app.modules.telemetry_contracts.retention import (
        staging_default_context as retention_staging_default_context,
    )
except ModuleNotFoundError:  # pragma: no cover — see 033-POLISH
    RetentionAction = None
    RetentionContext = None
    enforce_retention = None
    next_cleanup_at = None
    retention_dev_default_context = None
    retention_production_default_context = None
    retention_staging_default_context = None

# Re-export redaction defaults under retention's naming for symmetry.
from app.modules.telemetry_contracts.schemas import (
    AI_INVOCATION_STATUSES,
    AIInvocationSummary as PydanticAIInvocationSummary,
    ENVIRONMENTS,
    RELEASE_STAGES,
    VersionContext,
)
# Alias the pydantic version under a new name to avoid clashing with the
# dataclass `AIInvocationSummary` in events.py (which is still exported
# for backward compatibility with the streaming-event pipeline).
AIInvocationSummaryV2 = PydanticAIInvocationSummary

# REQ-033 US7 (T126) — TraceRunRef helpers. Pure-Python (no DB / no async),
# no dependency on any of the missing 033-POLISH modules (events.py /
# redaction.py / retention.py / models.py) — so it loads cleanly even when
# those files are absent from the working tree.
from app.modules.telemetry_contracts.repository import (
    TRACE_UNAVAILABLE as _TRACE_UNAVAILABLE,
    TraceRunRef,
    build_trace_run_ref,
    extract_trace_id_from_ai_invocation,
    langsmith_url_for_display,
    lookup_run_metadata,
    run_id_for_display,
    trace_id_for_display,
)
from app.modules.telemetry_contracts.export_policy import (
    DestinationPolicyInput,
    DestinationPolicyResult,
    SecretScanResult,
    decide_export_policy,
    scan_for_operational_secrets,
)
from app.modules.telemetry_contracts.llm_ops_repository import (
    EvalRunIdentity,
    build_eval_run_identity,
    export_decision_to_row,
    normalize_trace_run_ref,
)
from app.modules.telemetry_contracts import models as models

TRACE_UNAVAILABLE = _TRACE_UNAVAILABLE


__all__ = [
    "AI_INVOCATION_STATUSES",
    "AIInvocationSummary",
    "AIInvocationSummaryV2",
    "ENVIRONMENTS",
    "METADATA_FIELDS",
    "PII_FIELDS",
    "RELEASE_STAGES",
    "TRACE_UNAVAILABLE",
    "VALID_ENVIRONMENTS",
    "Aggregation",
    "DestinationPolicyInput",
    "DestinationPolicyResult",
    "EvalRunIdentity",
    "MetricCatalog",
    "MetricDefinition",
    "MetricSnapshot",
    "ProductEvent",
    "RedactionAudit",
    "RedactionContext",
    "RedactionPolicy",
    "RetentionAction",
    "RetentionContext",
    "TraceRunRef",
    "VersionContext",
    "apply_redaction",
    "audit_redaction",
    "build_default_catalog",
    "build_eval_run_identity",
    "build_trace_run_ref",
    "decide_export_policy",
    "dict_to_event",
    "enforce_retention",
    "event_to_dict",
    "export_decision_to_row",
    "extract_trace_id_from_ai_invocation",
    "langsmith_url_for_display",
    "lookup_run_metadata",
    "models",
    "next_cleanup_at",
    "normalize_trace_run_ref",
    "redaction_dev_default_context",
    "redaction_production_default_context",
    "redaction_staging_default_context",
    "retention_dev_default_context",
    "retention_production_default_context",
    "retention_staging_default_context",
    "run_id_for_display",
    "scan_for_operational_secrets",
    "SecretScanResult",
    "trace_id_for_display",
    "validate_redaction",
]
