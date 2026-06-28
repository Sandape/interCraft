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

from app.modules.telemetry_contracts.events import (
    AIInvocationSummary,
    MetricSnapshot,
    ProductEvent,
    dict_to_event,
    event_to_dict,
)
from app.modules.telemetry_contracts.metrics import (
    Aggregation,
    MetricCatalog,
    MetricDefinition,
    build_default_catalog,
)
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
from app.modules.telemetry_contracts.retention import (
    RetentionAction,
    RetentionContext,
    enforce_retention,
    next_cleanup_at,
)

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
from app.modules.telemetry_contracts.retention import (
    dev_default_context as retention_dev_default_context,
)
from app.modules.telemetry_contracts.retention import (
    production_default_context as retention_production_default_context,
)
from app.modules.telemetry_contracts.retention import (
    staging_default_context as retention_staging_default_context,
)

__all__ = [
    "AI_INVOCATION_STATUSES",
    "AIInvocationSummary",
    "AIInvocationSummaryV2",
    "ENVIRONMENTS",
    "METADATA_FIELDS",
    "PII_FIELDS",
    "RELEASE_STAGES",
    "VALID_ENVIRONMENTS",
    "Aggregation",
    "MetricCatalog",
    "MetricDefinition",
    "MetricSnapshot",
    "ProductEvent",
    "RedactionAudit",
    "RedactionContext",
    "RedactionPolicy",
    "RetentionAction",
    "RetentionContext",
    "VersionContext",
    "apply_redaction",
    "audit_redaction",
    "build_default_catalog",
    "dict_to_event",
    "enforce_retention",
    "event_to_dict",
    "next_cleanup_at",
    "redaction_dev_default_context",
    "redaction_production_default_context",
    "redaction_staging_default_context",
    "retention_dev_default_context",
    "retention_production_default_context",
    "retention_staging_default_context",
    "validate_redaction",
]
