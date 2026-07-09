# REQ-035 Requirement Status

**Status (2026-07-03)**: Superseded by
`specs/044-admin-console-redesign`. REQ-035 is no longer an active requirement
or implementation source. Existing evidence remains historical only.

System management admin console and data dashboard MVP.

Status date: 2026-06-29

## User Stories

| ID | Requirement | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | Open Admin Console Safely | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Admin entry, shell, route guard, access denial, `/me`, capability checks, expired-session handling, audit events, and Playwright access-boundary coverage are implemented and verified. |
| US2 | View Data Dashboard MVP | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Dashboard summary, metric catalog, PM assembly adapter, aggregation integration, KPI/panel UI, filters, valid-zero display, definitions, and Playwright dashboard coverage are implemented and verified. |
| US3 | Drill Down Into User, Business, Agent, Node, Tool, LLM, And Eval Logs | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Trace search/detail schemas, repository query helpers, hierarchy/correlation service, node/tool/retrieval/memory operations, Eval Center links, trace capture-chain integration, and Playwright drilldown coverage are implemented and verified. |
| US4 | Inspect Node I/O And Reconstruct Redacted LLM cURL Requests | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Node I/O, LLM metadata, streaming capture, safe cURL, masked raw reveal policy, role/reason/expiry/audit checks, graph/checkpointer/node capture hooks, and Playwright redaction coverage are implemented and verified. |
| US5 | Trust Metric Freshness And Definitions | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Metric definitions, source completeness, snapshot freshness/quality persistence, stale-warning policy, API fields, panel trust metadata, seed cases, integration tests, and Playwright state coverage are implemented and verified. |
| US6 | Share MVP Report Snapshot | done | `docs/evidence/035-admin-dashboard-mvp/dashboard-snapshot.md` | Snapshot service/API/repository primitives, CLI, privacy-safe markdown, create/get contract, privacy integration, audit event, detail UI, and Playwright snapshot coverage are implemented and verified. |

## Functional Requirements

| ID | Requirement | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | Dedicated admin console entry point on `/admin-console`, separate admin port, or equivalent isolated service address | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | `/admin-console` Vite rewrite, admin Router basename, admin-only sign-in path, `npm run dev:admin`, and admin-only Vite bundle validation pass. |
| FR-002 | Restrict console to authorized admin/internal reviewer users | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Capability dependencies, role-derived grants, denied access, and session expiry are covered. |
| FR-003 | Prevent unauthorized direct-link data exposure | done | `tests/e2e/035-admin-dashboard-mvp.spec.ts` | Route guard and E2E access denial prevent protected data from loading. |
| FR-004 | Dashboard is admin console MVP landing view | done | `src/admin/pages/ProductDashboard.tsx` | Admin shell redirects to dashboard and dashboard E2E verifies landing content. |
| FR-005 | Minimal admin shell states | done | `src/admin/AdminApp.test.tsx` | Loading, authorized, denied, and navigation states are covered. |
| FR-006 | Read-only MVP, no admin mutation workflows | done | `src/admin/README.md` | Admin UI remains read-only except privacy-safe snapshot generation and audited reveal/cURL actions. |
| FR-007 | Date range filtering | done | `src/admin/pages/ProductDashboard.test.tsx` | Date/environment query state and backend summary filters are verified. |
| FR-008 | Overview metrics | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | KPI cards render values, definitions, units, source completeness, and freshness. |
| FR-009 | Core product funnel | done | `src/admin/components/dashboard/FunnelPanel.tsx` | Funnel panel renders with source, freshness, and quality state metadata. |
| FR-010 | Resume diagnosis metrics | done | `src/admin/components/dashboard/ResumeDiagnosisPanel.tsx` | Resume diagnosis panel renders with trust metadata and tested dashboard coverage. |
| FR-011 | Mock interview metrics | done | `src/admin/components/dashboard/MockInterviewPanel.tsx` | Mock interview panel renders empty/quality states and tested dashboard coverage. |
| FR-012 | AI operations metrics | done | `src/admin/components/dashboard/AIOperationsPanel.tsx` | AI operations summary, LLM usage/cost fields, and streaming capture coverage are verified. |
| FR-013 | Feedback and badcase metrics | done | `src/admin/components/dashboard/BadcaseVersionPanel.tsx` | Badcase, feedback, version, and experiment panels render source/freshness metadata. |
| FR-014 | Version and experiment context | done | `backend/app/modules/pm_dashboard/service.py` | Version/experiment metric catalog entry and panel metadata are verified. |
| FR-015 | Metric definitions | done | `backend/tests/unit/test_035_metric_definitions.py` | Numerator, denominator, comparison rule, source, owner, version, privacy class, and UI popovers are covered. |
| FR-016 | Freshness and source completeness | done | `backend/tests/integration/test_035_dashboard_freshness.py` | Freshness target, stale warnings, source completeness, and panel metadata are covered. |
| FR-017 | Zero/missing/stale/error distinction | done | `tests/e2e/035-admin-dashboard-mvp.spec.ts` | Complete, partial, empty, stale, and valid-zero states are covered in frontend and E2E tests. |
| FR-018 | No raw sensitive content | done | `backend/tests/unit/test_035_payload_visibility.py` | Redacted defaults, safe snapshots, masked raw reveal, and cURL redaction are verified. |
| FR-019 | Shareable dashboard snapshot | done | `docs/evidence/035-admin-dashboard-mvp/dashboard-snapshot.md` | Snapshot content includes filters, generated time, metrics, definitions, freshness warnings, and privacy line. |
| FR-020 | Audit trail for admin access and snapshot generation | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Admin login, denial, dashboard view, reveal, cURL view, and snapshot creation audit paths are covered. |
| FR-021 | Verification evidence | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Backend target slice, frontend tests, Playwright, typecheck filter, admin build, CLI evidence, and screenshot evidence are recorded. |
| FR-022 | Multi-level trace explorer | done | `backend/tests/contract/test_035_trace_explorer_contract.py` | Search filters, pagination, aggregate rows, hierarchy, links, and comparison data are covered. |
| FR-023 | Agent node timeline and I/O inspection | done | `src/admin/pages/AgentRunDetail.test.tsx` | Node input/output/state diff, events, next step, errors, retries, and linked operations are covered. |
| FR-024 | LLM call detail and redacted cURL reconstruction | done | `src/admin/pages/LLMCallDetail.test.tsx` | Provider IDs, usage, timing, retry/stream capture, safe cURL, and audit paths are covered. |
| FR-025 | Eval center linked to traces and badcases | done | `backend/tests/contract/test_035_eval_center_contract.py` | Eval run/case/gate APIs and trace/LLM/badcase/report fields are covered. |
| FR-026 | Visibility modes for aggregate, redacted, masked raw, and approved raw | done | `backend/tests/integration/test_035_masked_raw_access.py` | Visibility modes, role-only reveal, reason capture, expiry, and audit are verified. |
| FR-027 | Strong Debug MVP first-release boundary | done | `specs/035-admin-dashboard-mvp/tasks.md` | All SpecKit tasks are completed and checked. |
| FR-028 | Production redacted-by-default payload policy | done | `backend/tests/unit/test_035_payload_visibility.py` | Payload defaults and safe reveal policy are covered. |
| FR-029 | Debug-heavy retention and freshness | done | `backend/tests/unit/test_035_retention_policy.py` | Retention policy and freshness evidence are recorded. |
| FR-030 | Role-only masked raw authorization | done | `backend/tests/integration/test_035_masked_raw_access.py` | Reviewer allow, PM deny, owner-without-debug-role deny, and expired-payload denial are covered. |
| FR-031 | Centralized Agent/LLM flow coverage | done | `docs/evidence/035-admin-dashboard-mvp/coverage-report.json` | Coverage CLI/API reports covered centralized flows and zero high-severity gaps. |
| FR-032 | Admin console and observability contracts | done | `docs/evidence/035-admin-dashboard-mvp/test-summary.md` | Admin, dashboard, trace, node/LLM, Eval Center, snapshot, masked raw, and Playwright contracts are covered. |

## Non-Blocking Follow-Ups

- Resolve unrelated resume-v2 TypeScript/build blockers so full frontend gates can pass.
- Replace MVP in-memory admin audit/snapshot service paths with the existing repository primitives where production deployment requires durable storage.
- Run real database migration validation in the deployment environment.
