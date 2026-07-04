---
name: req-044-us7-metric-trust
description: REQ-044 US7 Review Snapshots — 10-field MetricDefinition wrapper + 5-state DataStatus reuse + 405 immutable guard pattern + SC-012 8-field envelope
metadata:
  type: project
---

# REQ-044 US7 — Review Snapshots + Metric Trust (2026-07-04)

US7 ships the PM-facing Reports workspace (`/admin-console/reports`)
plus the FR-027 10-field MetricDefinition wrapper, the frozen-vs-live
snapshot viewer, and explicit PUT/PATCH/DELETE 405 guards for snapshot
immutability (AC-30.4).

## Why: PM-grade reporting requires 8 SC-012 fields per snapshot
(visible filters + frozen values + comparison deltas + metric
definitions + freshness warnings + quality flags + annotations +
privacy-safe evidence links), and the FR-027 metric trust contract
demands every metric expose the same 10 fields. Reuse US6 governance
surface (DataStatus Literal + AuditAction + raw_* redaction) so
the contract stays consistent across the 5 reporting-related
features.

## How to apply:

- **10-field MetricDefinition wrapper**: do NOT mutate the
  `telemetry_contracts.metrics.MetricDefinition` dataclass — wrap
  it in a new `MetricDefinition10Field` Pydantic model. The 9
  string fields default to the `NOT_PROVIDED = "(not provided)"`
  literal sentinel so AC-27.4 ("no silent omission") is enforced
  by schema defaults + contract test.
- **DataStatus 5-state**: reuse US6 governance DataStatus Literal
  verbatim. NEVER redeclare. The 5-state visual badge
  (QualityFlagsBadge) is also US6 — US7 imports and renders it
  inline rather than rebuilding.
- **AC-30.4 immutable guard**: explicit `@router.put("/{id}", ...)`
  + `@router.patch(...)` + `@router.delete(...)` handlers returning
  405 with `SNAPSHOT_IMMUTABLE` error code. FastAPI default 405
  lacks the audit-friendly error body, so we wire the explicit
  handlers + `assert_snapshot_immutable` service guard.
- **SC-012 8-field envelope**: POST/GET response surfaces all 8
  fields (`filters`, `frozen_values`, `comparison_deltas`,
  `metric_definitions`, `freshness_warnings`, `quality_flags`,
  `annotations`, `evidence_links`) — contract test asserts each
  is populated.
- **EC-1 late-arriving data**: the GET endpoint re-fetches current
  values and recomputes delta_pct vs frozen. When `|delta_pct| >
  tolerance_pct`, append a `late_arriving_warnings` string so the
  UI can render the warning banner. delta_pct uses
  `(current - frozen) / frozen * 100` (rounded to 2 dp).
- **EC-3 expired payloads**: filter on `filters.expired_record_ids`
  triggers `SnapshotBlockedError` (mirror of US6 ExportBlockedError).
  Audit event written with action=review_snapshot + result=denied
  BEFORE raising — same invariant as US6 AC-33.5.
- **Capability token**: US7 adds `REVIEW_SNAPSHOT` token. Grants:
  pm / owner / admin / operations / maintainer. reviewer + viewer
  denied (FR-031 least-privilege).
- **Frontend type reuse**: WorkspaceId, DataStatus, VisibilityMode
  are imported from `@/types/admin-governance` — do NOT redeclare
  in admin-review-snapshots.ts. WorkspaceId was the only field I
  tried to re-export; tsc flagged it (TS2459); fix = import from
  governance types instead.
- **API client pattern**: `apiClient.request<T>({method, path, body, signal})`
  is the canonical signature. There is NO `.get()` / `.post()`
  shortcut — those will fail TS2339.

## Files shipped (US7 batch):

- Backend 5 files (schemas/repository/service/api/__init__) +
  1 contract test (19 tests, 16 pass + 3 skip on no-DB)
- Backend 3 edits (`audit.py` + `auth.py` + `main.py`)
- Frontend 1 types + 1 api + 1 hooks + 8 components + 1 page +
  1 css block + 1 test (30 tests)
- AC matrix + evidence log + Playwright e2e (12 tests)
- Total: ~21 files (16 new + 5 modified)

## Test counts:
- pytest 16/16 pass (US7) + 100 regression (US1-US6) = 116 + 7 skip
- vitest 30/30 pass (US7) + 98 regression (US1-US6 admin suite)
- typecheck: 0 new errors in admin/; 6 pre-existing in
  src/modules/resume/v2/ (out of scope, master issue)
- Playwright: 12 tests, INFRA-BLOCKED acceptable for Phase 1

Related: [[req-044-us3-seed-pattern]] (capability role map sync),
[[req-044-us6-data-status-5-state]] (governance 5-state + audit
taxonomy lock).