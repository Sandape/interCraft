"""REQ-044 US7 — Review Snapshots + Metric Trust workspace.

Module surface:

- :mod:`schemas` — Pydantic v2 models for MetricDefinition (10 fields,
  FR-027), FrozenValue / CurrentValue (FR-030), ComparisonDelta,
  EvidenceLink (FR-029 privacy-safe), ReviewSnapshotRequest,
  ReviewSnapshotResponse, ReviewSnapshotListResponse.
- :mod:`repository` — in-memory buffer for snapshot records + frozen
  seed values + current seed values + MetricDefinition catalog +
  cohort version map (EC-2).
- :mod:`service` — orchestration: generate snapshot + audit (FR-029),
  get snapshot + delta (FR-030), immutable assertion (AC-30.4),
  EC-1 (late-arriving data warning) + EC-2 (cohort definition changed)
  + EC-3 (expired payloads blocked).
- :mod:`api` — FastAPI router mounted at
  ``/api/v1/admin-console/review-snapshots`` with 4 endpoints (POST,
  GET list, GET detail) + explicit PUT/PATCH/DELETE 405 guards.

Auth: capability check via :func:`app.modules.admin_console.auth.require_capability`
with the new US7 capability ``REVIEW_SNAPSHOT``.

Reuse baseline (heavy reuse from US6 + telemetry_contracts):

- US6 governance DataStatus Literal (5 states) — NOT redeclared.
- US6 AuditAction ``review_snapshot`` token — already in taxonomy.
- US6 governance EXPORT_FIELDS_REDACTED (4 raw_* names) — reuse.
- US6 audit log ``log_governance_change`` + ``append_audit_event`` — reuse.
- US6 ``next_audit_event_id`` for snapshot audit_event_id.
- telemetry_contracts MetricDefinition dataclass — extended via
  ``MetricDefinition10Field`` wrapper (10 fields),no mutation of source.

[CROSS-TEAM-DEBT] Real review_snapshot DB + real-time late-arriving
data recompute + real cohort definition change detector land in
Phase 2 batch 5. Until then all snapshot state is in-process + seed-driven.
"""
from app.modules.admin_console.review_snapshots import repository, service
from app.modules.admin_console.review_snapshots.api import review_snapshots_router

__all__ = [
    "repository",
    "review_snapshots_router",
    "service",
]