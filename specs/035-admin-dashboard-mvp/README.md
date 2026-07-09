# 035-admin-dashboard-mvp

System management admin console and data dashboard MVP.

## Summary

REQ-035 is superseded by `specs/044-admin-console-redesign` as of 2026-07-03.
It is no longer an implementation source. Keep this directory only as
historical context for decisions that led to the redesigned management console.

## Current Status

| Area | Status | Notes |
|---|---|---|
| Spec | superseded | Replaced by `specs/044-admin-console-redesign/spec.md`. |
| Plan | superseded | Historical only; do not use for new implementation planning. |
| Tasks | superseded | Historical only; do not use as active task source. |
| Implementation | superseded | Existing code may be mined or removed during future planning, but this spec no longer defines target behavior. |
| Requirement status | superseded | See `requirements-status.md`. |
| Open questions | closed by replacement | New questions belong to REQ-044. |

## MVP Boundaries

- Admin console is exposed through a dedicated, unlinked `/admin-console`
  relative path or equivalent isolated service address, separate from the
  user-facing product route tree.
- Admin access is required before any dashboard data is shown.
- Dashboard MVP is read-only and covers overview, funnel, resume diagnosis,
  mock interview, AI operations, badcase, feedback, and version context metrics.
- Observability MVP supports user-level, business-run-level, agent-level,
  node-level, tool/retrieval-level, LLM-call-level, and eval-case-level
  drilldown.
- LLM call detail includes a redacted, reproducible cURL view. Real secrets such
  as API keys and Authorization headers are never stored or displayed as raw
  values.
- Metric definitions, freshness, empty states, stale states, and privacy-safe
  reporting output are part of MVP acceptance.
- LangSmith sync, full user management, role management, billing, and
  prompt/rubric mutation are out of scope.
- Unrestricted production raw payload browsing is out of scope; raw-like views
  must be governed by visibility mode, redaction, retention, and audit policy.

## Primary Sources

- `specs/035-admin-dashboard-mvp/spec.md`
- `specs/035-admin-dashboard-mvp/observability-plan.md`
- `specs/033-eval-pm-dashboard/requirements-status.md`
- `docs/decisions/ADR-002-langsmith-eval-workflow-plan.md`
- `docs/testing/README.md`
- `docs/architecture/source-map.md`

## Plan Artifacts

- `plan.md` - implementation plan and constitution checks.
- `research.md` - architecture decisions and alternatives.
- `data-model.md` - admin, trace, payload, LLM, eval, snapshot, audit, retention, and coverage entities.
- `contracts/` - admin console API, trace explorer API, eval center API, and CLI contracts.
- `quickstart.md` - validation guide for Strong Debug MVP.

## Next Step

REQ-035 MVP is complete. Non-blocking follow-ups are tracked in
`requirements-status.md`: resolve unrelated resume-v2 full frontend gate
blockers, replace MVP in-memory admin service paths with durable repository
storage where required for deployment, and run real database migration
validation in the deployment environment.
