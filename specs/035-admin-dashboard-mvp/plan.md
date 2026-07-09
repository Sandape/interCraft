# Implementation Plan: REQ-035 Admin Dashboard Strong Debug MVP

**Branch**: `[035-admin-dashboard-mvp]` | **Date**: 2026-06-29 | **Spec**: [./spec.md](./spec.md)

**Input**: Feature specification from `specs/035-admin-dashboard-mvp/spec.md`

## Summary

Deliver a dedicated internal management console on an unlinked admin entry
point, with the first release fixed as **Strong Debug MVP**:

1. PM and owner users get a privacy-safe product data dashboard, metric
   definitions, freshness indicators, stale/partial/zero states, and report
   snapshots.
2. Developer/reviewer users get a trace-first AI observability workbench:
   Trace Explorer, agent run detail, node input/output, tool/retrieval/memory
   operations, LLM call detail, redacted cURL reconstruction, read-only Eval
   Center, and explicit observability coverage gaps.
3. Production defaults to metadata, redacted summaries, and structured payload
   shape. Approved developer/reviewer roles may reveal masked raw payloads only
   after entering a reason; every reveal is audited and masked raw payloads are
   retained for 14 days.

The plan reuses REQ-033 PM dashboard and telemetry contracts, REQ-029
OpenTelemetry tracing primitives, and the existing eval/badcase modules. It
adds an internal admin console boundary and a canonical internal trace/span/
payload data model before any LangSmith synchronization.

## Technical Context

- **Language/Version**: Python 3.11+ backend; TypeScript strict mode frontend.
- **Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Alembic, Redis/ARQ,
  OpenTelemetry API/SDK/OTLP, structlog, prometheus-client, httpx/OpenAI SDK,
  LangGraph, React 18, Vite, TanStack Query, Zustand, Recharts, Playwright.
- **Storage**: PostgreSQL for canonical admin, trace/span, payload metadata,
  metric snapshots, eval links, retention/audit records. JSONB is acceptable for
  structured payload shape and masked payload bodies in the MVP, with explicit
  retention purge. External object storage is deferred.
- **Testing**: Backend unit, contract, and integration tests with pytest;
  frontend component tests with Vitest/Testing Library; canonical E2E tests
  under `tests/e2e/`; typecheck/build gates; feature evidence under
  `docs/evidence/035-admin-dashboard-mvp/`.
- **Target Platform**: Windows developer workflow; Linux backend deployment;
  local/CI/staging validation before any production admin exposure.
- **Project Type**: Full-stack web app plus backend libraries, admin APIs,
  CLI validation utilities, and scheduled metric/retention jobs.
- **Performance Goals**:
  - Admin console shell and dashboard landing view load within 3 seconds with
    seeded MVP data.
  - Trace Explorer search returns the first page within 3 seconds for normal
    internal 60-day trace windows.
  - A seeded business run can be drilled down from user/business id to agent
    node, LLM call, eval result, and badcase link in under 2 minutes.
  - Dashboard metric snapshots refresh within 15 minutes of source data
    availability, or affected sections show stale state.
  - Trace capture and payload persistence fail open and do not block user
    business flows.
- **Constraints**:
  - Admin console must be separate from the user-facing product route tree and
    reachable through an unlinked admin path such as `/admin-console`, its own
    local admin port, or an equivalent isolated service address.
  - Strong Debug MVP is the first acceptance boundary: admin shell, PM
    dashboard, trace explorer, node I/O, LLM detail/cURL, read-only Eval Center,
    privacy/audit controls, and coverage reporting ship together.
  - Production payload policy: redacted by default plus approved masked raw;
    full raw production payload display is out of scope.
  - Production retention: PM metrics 180 days, redacted traces 60 days, masked
    raw payloads 14 days.
  - Masked raw reveal: approved developer/reviewer role, user-entered reason,
    audit event on every reveal.
  - Literal secret-bearing cURL storage/display is forbidden. Authorization
    headers, API keys, cookies, and service credentials must be placeholders.
  - LangSmith synchronization, production trace export, full role-management UI,
    billing dashboards, and mutation-heavy admin workflows are out of scope.
- **Scale/Scope**:
  - Cover all production flows that pass through centralized Agent/LLM
    invocation entry points. Legacy/bypass paths are acceptable only when
    listed in an observable coverage-gap report.
  - Reuse existing 033 dashboard metric taxonomy and 029 tracing primitives;
    avoid a second eval runner or a second observability framework.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | Pass | Plan adds self-contained `admin_console` and `agent_observability` backend modules, extends existing `pm_dashboard`, `telemetry_contracts`, `observability`, and `eval` modules through explicit contracts, and keeps the admin frontend under a separate entry surface. |
| II. CLI Interface | Pass | Admin snapshot generation, coverage report, retention purge, privacy audit, and seeded validation are planned with CLI contracts for local/CI use. |
| III. Test-First | Pass | Each slice has contract/unit/integration tests before implementation: admin access boundary, dashboard freshness, trace capture, payload reveal, cURL redaction, eval links, retention, and coverage gaps. |
| IV. Integration & Synchronization Testing | Pass | Integration tests cover request to agent/node/LLM/eval correlation, admin UI to backend APIs, metric snapshot generation, and retention/audit behavior with realistic seeded data. |
| V. Observability | Pass | The feature is an observability workbench and extends trace/log/metric correlation with user, business run, agent, node, LLM, eval, version, token, cost, latency, and privacy fields. |
| Security & Privacy | Pass | Production defaults to redacted views; masked raw requires approved role, reason, audit, and 14-day retention; secrets are never stored or displayed in cURL. |
| Documentation | Pass | Plan creates research, data model, contracts, and quickstart before task generation. |

No unjustified constitution violations are introduced.

## Project Structure

### Documentation (this feature)

```text
specs/035-admin-dashboard-mvp/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- observability-plan.md
|-- contracts/
|   |-- admin-console-api.md
|   |-- trace-explorer-api.md
|   |-- eval-center-api.md
|   `-- admin-observability-cli.md
|-- requirements-status.md
`-- tasks.md                 # Created later by /speckit-tasks
```

### Source Code (planned implementation surface)

```text
backend/app/modules/admin_console/
|-- README.md
|-- api.py                   # admin home, session, snapshot, audit endpoints
|-- auth.py                  # PM/developer/reviewer/owner access dependencies
|-- cli.py                   # snapshot, audit, and seeded validation commands
|-- models.py                # grants, sessions, audit events, snapshots
|-- repository.py
|-- schemas.py
`-- service.py

backend/app/modules/agent_observability/
|-- README.md
|-- api.py                   # trace explorer, agent/node/LLM detail endpoints
|-- capture.py               # record trace/span/payload records fail-open
|-- cli.py                   # coverage report, retention purge, privacy audit
|-- curl.py                  # redacted cURL reconstruction
|-- models.py                # traces, spans, payloads, LLM/tool/eval links
|-- payloads.py              # visibility modes and masking
|-- repository.py
|-- schemas.py
`-- service.py

backend/app/modules/pm_dashboard/
|-- api.py                   # extend/reuse existing metrics endpoints
|-- repository.py            # add 180-day metric snapshot queries
`-- service.py               # freshness and snapshot assembly

backend/app/modules/telemetry_contracts/
|-- events.py                # extend ProductEvent/AIInvocationSummary shape
|-- redaction.py             # add masked raw policy helpers
`-- retention.py             # add 180/60/14-day policy contexts

backend/app/eval/
|-- runner.py                # link eval runs to trace/span/case records
|-- report.py
`-- cli.py                   # expose eval center validation artifacts

backend/app/observability/
`-- tracing.py               # preserve OTel spans and add capture bridge

backend/app/agents/
|-- llm_client.py            # centralized LLM call metadata/cURL capture
`-- */nodes/*.py             # node wrapper coverage through centralized hooks

backend/tests/
|-- contract/
|   |-- test_035_admin_console_contract.py
|   |-- test_035_trace_explorer_contract.py
|   `-- test_035_eval_center_contract.py
|-- integration/
|   |-- test_035_admin_access.py
|   |-- test_035_trace_capture_chain.py
|   |-- test_035_masked_raw_access.py
|   |-- test_035_dashboard_freshness.py
|   `-- test_035_retention.py
`-- unit/
    |-- test_035_curl_redaction.py
    |-- test_035_payload_visibility.py
    |-- test_035_coverage_report.py
    `-- test_035_metric_definitions.py

src/admin/
|-- main.tsx                 # separate admin frontend entry
|-- AdminApp.tsx
|-- routes.tsx
|-- api/
|   |-- admin-console.ts
|   |-- trace-explorer.ts
|   `-- eval-center.ts
|-- pages/
|   |-- AdminHome.tsx
|   |-- ProductDashboard.tsx
|   |-- TraceExplorer.tsx
|   |-- AgentRunDetail.tsx
|   |-- LLMCallDetail.tsx
|   |-- EvalCenter.tsx
|   `-- PrivacyAudit.tsx
|-- components/
`-- types/

tests/e2e/
`-- 035-admin-dashboard-mvp.spec.ts
```

**Structure Decision**: Use additive backend modules for admin-console
ownership and agent-observability ownership. Reuse existing `pm_dashboard`,
`telemetry_contracts`, `observability`, and `eval` surfaces instead of
duplicating them. Use a separate admin frontend entry inside the existing Vite
project, mounted under `/admin-console` for local development, without creating
a second repository or abandoning shared UI/test tooling.

## Phase Plan

### Phase 0: Research Decisions

- Choose admin entry boundary and local path/port strategy.
- Choose trace/span/payload storage and OTel relationship.
- Choose production payload visibility, cURL reconstruction, and audit policy.
- Choose retention/freshness implementation for 180/60/14 days and 15-minute
  dashboard freshness.
- Choose role/capability model for PM, owner, developer, and reviewer access.
- Choose coverage-gap reporting for centralized Agent/LLM flows.
- Choose eval center integration with existing eval/badcase records.

Output: [research.md](./research.md)

### Phase 1: Design & Contracts

- Define admin, trace, payload, LLM, eval, snapshot, audit, retention, and
  coverage entities in [data-model.md](./data-model.md).
- Define admin console APIs, trace explorer APIs, eval center APIs, and CLI
  contracts in [contracts/](./contracts/).
- Define quickstart validation for admin path access, dashboard freshness,
  trace drilldown, masked raw reveal, cURL redaction, eval links, retention, and
  coverage gaps in [quickstart.md](./quickstart.md).

Outputs: [data-model.md](./data-model.md), [contracts/](./contracts/),
[quickstart.md](./quickstart.md)

### Phase 2: Task Generation (Later)

Use `/speckit-tasks` after this plan. Tasks should be sliced by independently
testable user story and keep TDD ordering: failing contract/unit tests,
implementation, integration/E2E evidence, requirement-status updates.

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | Pass | Data model and contracts divide admin console, trace capture, payload visibility, cURL reconstruction, eval center, and dashboard snapshots into separable modules with narrow interfaces. |
| II. CLI Interface | Pass | CLI contracts cover coverage report, retention purge, privacy audit, dashboard snapshot, and seeded validation. |
| III. Test-First | Pass | Quickstart and contracts identify required tests before implementation. |
| IV. Integration & Synchronization Testing | Pass | Planned tests prove full request-to-node-to-LLM-to-eval correlation and admin UI/API behavior, not only isolated functions. |
| V. Observability | Pass | All planned records carry stable correlation identifiers and version/privacy context. |
| Security & Privacy | Pass | Visibility modes, reason capture, audit, retention, and secret redaction are first-class acceptance gates. |
| Documentation | Pass | Required design artifacts are generated and cross-linked. |

## Complexity Tracking

No constitution violations requiring justification.
