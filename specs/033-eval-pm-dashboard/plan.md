# Implementation Plan: REQ-033 Automated Eval & PM Dashboard MVP

**Branch**: `[033-eval-pm-dashboard]` | **Date**: 2026-06-26 | **Spec**: [./spec.md](./spec.md)

**Input**: Feature specification from `specs/033-eval-pm-dashboard/spec.md`

## Summary

Deliver a Safe MVP that connects existing InterCraft eval, tracing, audit, and
product telemetry into two user-facing outcomes:

1. Developers get deterministic golden-case PR evals, optional LangSmith Cloud
   experiment sync, stable run/trace identifiers, and a documented path from
   failures to reviewed badcases.
2. PM gets Dashboard V1 for product overview, core funnel, resume diagnosis,
   mock interview, AI operations, feedback/badcases, and version/experiment
   attribution.

The plan keeps InterCraft-controlled artifacts as canonical. LangSmith Cloud is
an optional workbench for eval/trace/experiment inspection, never the product
analytics, quota, billing, or compliance source of truth. Production export is
metadata plus redacted summaries only, retained for 30 days after production
trace export is approved.

## Technical Context

- **Language/Version**: Python 3.11 backend; TypeScript strict mode frontend.
- **Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Alembic,
  Redis/ARQ, OpenTelemetry SDK/OTLP, structlog, Prometheus metrics, React 18,
  Vite, TanStack Query, Zustand. Add direct LangSmith client dependency only in
  the backend eval integration if not already direct.
- **Storage**: PostgreSQL for canonical records, with redaction policy,
  eval/badcase/metric records stored locally. Filesystem/CI artifacts remain the
  canonical eval report backup under `docs/evidence/` or CI artifacts.
- **Testing**: `cd backend && uv run pytest tests/eval -q`, backend unit /
  integration / contract tests, frontend unit tests, typecheck, build, and
  canonical E2E as needed.
- **Target Platform**: Linux backend deployment and Windows developer workflow;
  local/CI/staging first, production trace export deferred.
- **Project Type**: Full-stack web app plus backend library/CLI/reporting
  workflow.
- **Performance Goals**:
  - PR deterministic eval should complete in under 10 minutes for prompt-adjacent
    changes.
  - PM dashboard panels should load from precomputed or efficiently aggregated
    metric snapshots within 2 seconds for a normal 30-day internal range.
  - LangSmith sync failure must not delay or change local eval verdicts.
- **Constraints**:
  - Production external export: metadata plus redacted summaries only.
  - Staging masked prompt/output only for synthetic, golden, or approved staging
    test data.
  - Nightly real-model eval: about 5M tokens or $50 per night, $1000 monthly cap.
  - Baseline refresh and emergency override: PM business owner + technical owner
    dual approval.
  - Badcase promotion first month: CLI/documented review flow; admin UI deferred.
  - Production trace metadata/redacted summaries: 30-day retention.
- **Scale/Scope**:
  - MVP covers PM Dashboard V1 and developer eval workflow, not executive
    reporting, billing, payment analytics, or automated prompt deployment.
  - The first implementation should integrate existing feature 026 eval and
    feature 029 tracing primitives before adding broader product telemetry.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | Pass | Plan introduces self-contained eval reporting, LangSmith sync, redaction, PM metrics, and badcase review boundaries. Each module must expose a narrow public contract and README before implementation is considered done. |
| II. CLI Interface | Pass | Eval run, LangSmith sync, redaction audit, metric snapshot generation, and first-month badcase promotion are planned with CLI contracts for local/CI use. |
| III. Test-First | Pass | Each slice has contract/unit/integration tests before implementation: redaction, eval report schema, LangSmith sync disabled/enabled paths, badcase lifecycle, and dashboard metric contracts. |
| IV. Integration & Synchronization Testing | Pass | Cross-boundary contracts cover CI artifacts, LangSmith experiment sync, dashboard APIs, and trace/run joins. Staging and production export require integration tests and redaction audit evidence. |
| V. Observability | Pass | The design extends existing trace/log/metric fields with run_id, trace_id, prompt fingerprint, rubric version, privacy class, and redaction status. Export failure is fail-open and observable. |
| Security & Privacy | Pass | Secrets remain in environment/CI secret stores; production raw career content is forbidden from external export; retention and redaction audit are explicit gates. |
| Documentation | Pass | This plan creates research, data model, contracts, and quickstart artifacts before tasks/implementation. |

No unjustified constitution violations are introduced.

## Project Structure

### Documentation (this feature)

```text
specs/033-eval-pm-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── pm-dashboard-api.md
│   ├── eval-langsmith-cli.md
│   └── event-metric-schema.md
├── requirements-status.md
└── tasks.md                 # Created later by /speckit-tasks
```

### Source Code (planned implementation surface)

```text
backend/app/eval/
├── cli.py                   # extend existing eval CLI/report flow
├── runner.py                # extend existing run_id/report fields
├── report.py                # planned: stable JSON/Markdown report rendering
└── langsmith_reporter.py    # planned: optional LangSmith dataset/experiment sync

backend/app/modules/pm_dashboard/
├── README.md
├── api.py                   # planned PM Dashboard V1 endpoints
├── schemas.py               # typed request/response contracts
├── service.py               # metric assembly from canonical internal sources
└── repository.py            # metric snapshot/event queries

backend/app/modules/badcases/
├── README.md
├── cli.py                   # first-month review/promotion flow
├── api.py                   # list/create/update/close for review records
├── models.py
├── schemas.py
├── repository.py
└── service.py

backend/app/modules/telemetry_contracts/
├── README.md
├── events.py                # event and metric schema definitions
├── redaction.py             # environment policy + validation
├── metrics.py               # metric definition catalog
└── retention.py             # production trace retention checks

backend/tests/
├── contract/
│   ├── test_033_pm_dashboard_contract.py
│   ├── test_033_badcase_contract.py
│   └── test_033_event_metric_schema.py
├── eval/
│   └── test_033_langsmith_reporter.py
├── integration/
│   ├── test_033_redaction_policy.py
│   ├── test_033_pm_dashboard_metrics.py
│   └── test_033_badcase_promotion_cli.py
└── unit/
    ├── test_033_redaction.py
    ├── test_033_metric_definitions.py
    └── test_033_retention.py

src/
├── pages/PMDashboard.tsx
├── api/pm-dashboard.ts
├── types/pm-dashboard.ts
└── components/pm-dashboard/
    ├── OverviewPanel.tsx
    ├── FunnelPanel.tsx
    ├── ResumeDiagnosisPanel.tsx
    ├── MockInterviewPanel.tsx
    ├── AIOperationsPanel.tsx
    ├── FeedbackBadcasePanel.tsx
    └── VersionExperimentPanel.tsx

tests/e2e/
└── 033-pm-dashboard.spec.ts
```

**Structure Decision**: Use additive, self-contained backend modules for PM
dashboard, badcase review, and telemetry/redaction contracts. Extend the
existing `backend/app/eval/` feature 026 surface instead of creating a second
eval runner. Extend existing feature 029 observability fields for trace joins
instead of making LangSmith the tracing source of truth. Frontend work is a new
internal dashboard page under the current `src/` root.

## Phase Plan

### Phase 0: Research Decisions

- Resolve external workbench boundary: LangSmith optional reporter, local
  reports canonical.
- Resolve telemetry source of truth: internal event/metric records and snapshots
  for PM dashboard.
- Resolve privacy model: environment-specific export policy, staging policy,
  production redacted-only export, 30-day production retention.
- Resolve first-month badcase workflow: CLI/documented promotion, admin UI
  deferred.

Output: [research.md](./research.md)

### Phase 1: Design & Contracts

- Define data model for eval runs, experiments, PM metrics, product events,
  AI invocation summaries, badcases, redaction policy, and redaction audits.
- Define PM Dashboard API contracts with consistent filters and response shapes.
- Define eval/LangSmith CLI contracts and event/metric schema contracts.
- Define quickstart validation scenarios for local eval, LangSmith disabled and
  enabled flows, redaction audit, dashboard contract, and badcase promotion.

Outputs: [data-model.md](./data-model.md), [contracts/](./contracts/),
[quickstart.md](./quickstart.md)

### Phase 2: Task Generation (Later)

Use `/speckit-tasks` after this plan to split work by independently testable
user story. Tasks should keep TDD ordering: contract/unit tests first, then
minimal implementation, then integration/E2E evidence.

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | Pass | Data model and contracts divide eval reporting, dashboard metrics, badcases, and redaction into separable modules. |
| II. CLI Interface | Pass | CLI contracts cover eval runs, LangSmith sync, redaction audit, metric snapshot generation, and first-month badcase promotion. |
| III. Test-First | Pass | Quickstart and contracts identify the tests that must precede implementation. |
| IV. Integration & Synchronization Testing | Pass | Planned contract/integration tests cover dashboard APIs, LangSmith sync, redaction policy, and run/trace joins. |
| V. Observability | Pass | All contracts carry run_id/trace_id/version/privacy fields and explicit sync/export failure states. |
| Security & Privacy | Pass | Data model separates sensitive content from metadata/redacted summaries and records retention/redaction evidence. |
| Documentation | Pass | Required plan artifacts are present and cross-linked. |

## Complexity Tracking

No constitution violations requiring justification.
