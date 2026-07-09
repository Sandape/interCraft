# Tasks: REQ-035 Admin Dashboard Strong Debug MVP

**Input**: Design documents from `specs/035-admin-dashboard-mvp/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required. The specification marks user scenarios as mandatory and the project constitution requires test-first delivery.

**Organization**: Tasks are grouped by user story so each story can be implemented and verified independently after the shared foundation is ready.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches a different file or can be validated independently.
- **[Story]**: User story label for story phases only.
- Every task includes an exact target file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the admin-console feature surface, local admin entry point, evidence folder, and module ownership markers.

- [X] T001 Create REQ-035 evidence directory guide in `docs/evidence/035-admin-dashboard-mvp/README.md`
- [X] T002 [P] Create admin console module ownership notes in `backend/app/modules/admin_console/README.md`
- [X] T003 [P] Create agent observability module ownership notes in `backend/app/modules/agent_observability/README.md`
- [X] T004 [P] Create admin frontend ownership notes in `src/admin/README.md`
- [X] T005 Add the separate admin HTML entry in `index.admin.html`
- [X] T006 Add the admin React bootstrap entry in `src/admin/main.tsx`
- [X] T007 Add the admin root component skeleton in `src/admin/AdminApp.tsx`
- [X] T008 Add the admin route table skeleton in `src/admin/routes.tsx`
- [X] T009 Add `dev:admin`, `build:admin`, and `preview:admin` scripts in `package.json`
- [X] T010 Add admin entry input and port-aware Vite configuration in `vite.config.ts`
- [X] T011 Add REQ-035 admin, retention, freshness, and visibility settings in `backend/app/core/config.py`
- [X] T012 Create shared admin HTTP client scaffolding in `src/admin/api/client.ts`

**Checkpoint**: Admin/frontend/backend owners and entry-point scaffolding exist, but no protected data is exposed yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the database, policy, capture, router, CLI, and seed-data foundation required by every user story.

**Critical**: No user story implementation should begin until this phase is complete.

### Tests for Foundational Behavior

- [X] T013 [P] Create model and migration tests for admin/observability records in `backend/tests/unit/test_035_admin_observability_models.py`
- [X] T014 [P] Create payload visibility policy tests in `backend/tests/unit/test_035_payload_visibility.py`
- [X] T015 [P] Create cURL secret redaction tests in `backend/tests/unit/test_035_curl_redaction.py`
- [X] T016 [P] Create retention policy tests for 180/60/14-day windows in `backend/tests/unit/test_035_retention_policy.py`
- [X] T017 [P] Create coverage-report policy tests in `backend/tests/unit/test_035_coverage_report.py`
- [X] T018 [P] Create deterministic Strong Debug demo fixtures in `backend/tests/fixtures/req035_admin_demo.py`

### Implementation for Foundational Behavior

- [X] T019 Create REQ-035 Alembic migration for grants, audit events, traces, spans, payloads, LLM calls, tool operations, eval links, dashboard snapshots, and coverage gaps in `backend/migrations/versions/0025_035_admin_observability.py`
- [X] T020 Create admin console package exports in `backend/app/modules/admin_console/__init__.py`
- [X] T021 Define `AdminAccessGrant`, `AdminAuditEvent`, and `DashboardSnapshot` ORM models in `backend/app/modules/admin_console/models.py`
- [X] T022 Define shared admin console Pydantic schemas and enums in `backend/app/modules/admin_console/schemas.py`
- [X] T023 Implement admin grant, audit, and snapshot repository primitives in `backend/app/modules/admin_console/repository.py`
- [X] T024 Create agent observability package exports in `backend/app/modules/agent_observability/__init__.py`
- [X] T025 Define `ObservabilityTrace`, `ObservabilitySpan`, `ObservabilityPayload`, `LLMCallRecord`, `ToolOperationRecord`, `EvalRun`, `EvalCaseResult`, and `ObservabilityCoverageGap` ORM models in `backend/app/modules/agent_observability/models.py`
- [X] T026 Define trace, span, payload, LLM, tool, eval, and coverage Pydantic schemas in `backend/app/modules/agent_observability/schemas.py`
- [X] T027 Implement trace/span/payload/LLM/tool/eval repository primitives in `backend/app/modules/agent_observability/repository.py`
- [X] T028 Implement visibility modes, masking, shape extraction, and reveal eligibility in `backend/app/modules/agent_observability/payloads.py`
- [X] T029 Implement safe reconstructed cURL generation in `backend/app/modules/agent_observability/curl.py`
- [X] T030 Extend redaction helpers for masked raw payload validation in `backend/app/modules/telemetry_contracts/redaction.py`
- [X] T031 Extend retention helpers for REQ-035 180/60/14-day policy contexts in `backend/app/modules/telemetry_contracts/retention.py`
- [X] T032 Implement fail-open trace/span/payload capture service in `backend/app/modules/agent_observability/capture.py`
- [X] T033 Bridge OpenTelemetry span context to REQ-035 capture records in `backend/app/observability/tracing.py`
- [X] T034 Capture LLM request/response metadata, usage, retries, provider ids, and streaming timing in `backend/app/agents/llm_client.py`
- [X] T035 Create agent observability CLI command skeletons in `backend/app/modules/agent_observability/cli.py`
- [X] T036 Create admin console CLI command skeletons in `backend/app/modules/admin_console/cli.py`
- [X] T037 Implement `seed-strong-debug-demo` deterministic seed command in `backend/app/modules/agent_observability/cli.py`
- [X] T038 Create admin console API router with liveness placeholder in `backend/app/modules/admin_console/api.py`
- [X] T039 Create agent observability API router with liveness placeholder in `backend/app/modules/agent_observability/api.py`
- [X] T040 Register admin console and observability routers under `/api/v1/admin-console` in `backend/app/main.py`

**Checkpoint**: Shared persistence, redaction, retention, capture, CLI skeletons, and router imports are ready. User stories may now proceed.

---

## Phase 3: User Story 1 - Open Admin Console Safely (Priority: P1)

**Goal**: Authorized internal users can open the separate admin console entry point, while unauthenticated and unauthorized users see no protected data.

**Independent Test**: Open the admin entry point as admin, PM, developer/reviewer, non-admin, and unauthenticated visitor; verify shell access, denial behavior, and session-expired behavior without loading dashboard data for denied users.

### Tests for User Story 1

- [X] T041 [P] [US1] Create admin console contract tests for `/health` and `/me` in `backend/tests/contract/test_035_admin_console_contract.py`
- [X] T042 [P] [US1] Create admin access integration tests for 401, 403, capability grants, and session expiry in `backend/tests/integration/test_035_admin_access.py`
- [X] T043 [P] [US1] Create admin shell and route-guard component tests in `src/admin/AdminApp.test.tsx`
- [X] T044 [P] [US1] Create Playwright access-boundary scenarios in `tests/e2e/035-admin-dashboard-mvp.spec.ts`

### Implementation for User Story 1

- [X] T045 [US1] Implement admin capability resolution and FastAPI dependencies in `backend/app/modules/admin_console/auth.py`
- [X] T046 [US1] Implement admin session, capability, and access audit service methods in `backend/app/modules/admin_console/service.py`
- [X] T047 [US1] Implement `/health` and `/me` admin endpoints with 401/403 behavior in `backend/app/modules/admin_console/api.py`
- [X] T048 [US1] Add admin identity and capability API functions in `src/admin/api/admin-console.ts`
- [X] T049 [US1] Add admin identity types and capability constants in `src/admin/types/admin-console.ts`
- [X] T050 [US1] Implement protected admin route guard and session-expired state in `src/admin/routes.tsx`
- [X] T051 [US1] Implement admin shell layout, navigation, active page state, and default dashboard landing in `src/admin/components/AdminShell.tsx`
- [X] T052 [US1] Implement access denied and unauthenticated states in `src/admin/pages/AdminAccessBoundary.tsx`
- [X] T053 [US1] Persist audit events for admin login, denied access, and protected data route attempts in `backend/app/modules/admin_console/service.py`

**Checkpoint**: Admin shell is reachable on the admin entry point and protected before any dashboard, trace, eval, payload, or snapshot data loads.

---

## Phase 4: User Story 2 - View Data Dashboard MVP (Priority: P1)

**Goal**: PMs and owners can answer product-health questions from one privacy-safe dashboard covering usage, funnel, resume diagnosis, mock interview, AI operations, badcases, feedback, and version context.

**Independent Test**: With seeded metric data, open the dashboard, change the date range, and verify all MVP sections show expected values, rates, deltas, definitions, freshness, and privacy-safe content.

### Tests for User Story 2

- [X] T054 [P] [US2] Create dashboard summary contract tests in `backend/tests/contract/test_035_admin_console_contract.py`
- [X] T055 [P] [US2] Create metric definition catalog tests in `backend/tests/unit/test_035_metric_definitions.py`
- [X] T056 [P] [US2] Create dashboard aggregation integration tests in `backend/tests/integration/test_035_dashboard_summary.py`
- [X] T057 [P] [US2] Create admin dashboard frontend tests in `src/admin/pages/ProductDashboard.test.tsx`
- [X] T058 [P] [US2] Extend Playwright PM dashboard questions in `tests/e2e/035-admin-dashboard-mvp.spec.ts`

### Implementation for User Story 2

- [X] T059 [US2] Add admin dashboard summary, panel, freshness, and filter schemas in `backend/app/modules/admin_console/schemas.py`
- [X] T060 [US2] Add metric definition catalog and dashboard summary assembly in `backend/app/modules/pm_dashboard/service.py`
- [X] T061 [US2] Add 180-day metric snapshot query support in `backend/app/modules/pm_dashboard/repository.py`
- [X] T062 [US2] Implement `/dashboard/summary` with PM dashboard capability checks in `backend/app/modules/admin_console/api.py`
- [X] T063 [US2] Add dashboard view audit recording in `backend/app/modules/admin_console/service.py`
- [X] T064 [US2] Add dashboard summary API functions in `src/admin/api/admin-console.ts`
- [X] T065 [US2] Add dashboard data types for filters, panels, freshness, and quality states in `src/admin/types/dashboard.ts`
- [X] T066 [US2] Implement dashboard page container, query state, and date-range filter in `src/admin/pages/ProductDashboard.tsx`
- [X] T067 [US2] Implement overview KPI tiles with definitions and selected period in `src/admin/components/dashboard/OverviewMetrics.tsx`
- [X] T068 [US2] Implement core funnel table and largest-dropoff indicator in `src/admin/components/dashboard/FunnelPanel.tsx`
- [X] T069 [US2] Implement resume diagnosis and suggestion-adoption panels in `src/admin/components/dashboard/ResumeDiagnosisPanel.tsx`
- [X] T070 [US2] Implement mock interview metrics and dropout panels in `src/admin/components/dashboard/MockInterviewPanel.tsx`
- [X] T071 [US2] Implement AI operations token, cost, model, latency, and failure panels in `src/admin/components/dashboard/AIOperationsPanel.tsx`
- [X] T072 [US2] Implement badcase, feedback, version, and experiment context panels in `src/admin/components/dashboard/BadcaseVersionPanel.tsx`
- [X] T073 [US2] Implement dashboard loading, empty, stale, partial, and error presentation states in `src/admin/components/dashboard/DashboardStates.tsx`
- [X] T074 [US2] Seed deterministic dashboard metric snapshots for complete, empty, partial, and stale periods in `backend/app/modules/agent_observability/cli.py`

**Checkpoint**: PM dashboard MVP is read-only, privacy-safe, filterable by date range, and usable without manual database queries.

---

## Phase 5: User Story 3 - Drill Down Into User, Business, Agent, Node, Tool, LLM, And Eval Logs (Priority: P1)

**Goal**: Developer-agent maintainers and owners can search from a user or business event into the exact trace, agent run, node, tool/retrieval/memory operation, LLM call, eval result, and badcase link.

**Independent Test**: With a seeded failed business run, search by user/business/trace/agent/node/model/badcase and drill through the complete correlation chain from trace to eval case and badcase.

### Tests for User Story 3

- [X] T075 [P] [US3] Create Trace Explorer contract tests in `backend/tests/contract/test_035_trace_explorer_contract.py`
- [X] T076 [P] [US3] Create Eval Center contract tests in `backend/tests/contract/test_035_eval_center_contract.py`
- [X] T077 [P] [US3] Create end-to-end trace capture chain integration tests in `backend/tests/integration/test_035_trace_capture_chain.py`
- [X] T078 [P] [US3] Create trace explorer frontend tests in `src/admin/pages/TraceExplorer.test.tsx`
- [X] T079 [P] [US3] Create eval center frontend tests in `src/admin/pages/EvalCenter.test.tsx`
- [X] T080 [P] [US3] Extend Playwright trace drilldown scenarios in `tests/e2e/035-admin-dashboard-mvp.spec.ts`

### Implementation for User Story 3

- [X] T081 [US3] Implement trace search filters, pagination, and aggregate row schemas in `backend/app/modules/agent_observability/schemas.py`
- [X] T082 [US3] Implement trace search and hierarchy query methods in `backend/app/modules/agent_observability/repository.py`
- [X] T083 [US3] Implement trace hierarchy, correlation links, and comparison service methods in `backend/app/modules/agent_observability/service.py`
- [X] T084 [US3] Implement `/observability/traces` and `/observability/traces/{trace_id}` endpoints in `backend/app/modules/agent_observability/api.py`
- [X] T085 [US3] Implement `/observability/agent-runs/{agent_run_id}` endpoint in `backend/app/modules/agent_observability/api.py`
- [X] T086 [US3] Implement tool, retrieval, and memory operation detail query support in `backend/app/modules/agent_observability/service.py`
- [X] T087 [US3] Link eval runner outputs to trace, LLM, and badcase identifiers in `backend/app/eval/runner.py`
- [X] T088 [US3] Add eval report fields for score dimensions, regression delta, cost, tokens, latency, and trace links in `backend/app/eval/report.py`
- [X] T089 [US3] Implement Eval Center read-model adapter in `backend/app/modules/agent_observability/service.py`
- [X] T090 [US3] Implement `/eval-center/runs`, `/eval-center/runs/{eval_run_id}`, `/eval-center/cases/{case_result_id}`, and `/eval-center/gate/latest` endpoints in `backend/app/modules/agent_observability/api.py`
- [X] T091 [US3] Add Trace Explorer API functions in `src/admin/api/trace-explorer.ts`
- [X] T092 [US3] Add Eval Center API functions in `src/admin/api/eval-center.ts`
- [X] T093 [US3] Add trace, span, tool operation, LLM, eval, and badcase link types in `src/admin/types/trace-explorer.ts`
- [X] T094 [US3] Implement trace search page, filters, result table, and pagination in `src/admin/pages/TraceExplorer.tsx`
- [X] T095 [US3] Implement trace hierarchy timeline and parent-child span view in `src/admin/components/trace/TraceHierarchy.tsx`
- [X] T096 [US3] Implement trace comparison summary for status, latency, token, cost, node path, and eval outcome differences in `src/admin/components/trace/TraceComparison.tsx`
- [X] T097 [US3] Implement agent run detail page with graph identity, version context, node timeline, final output summary, and linked operations in `src/admin/pages/AgentRunDetail.tsx`
- [X] T098 [US3] Implement Eval Center run list, case detail, gate status, and trace/badcase links in `src/admin/pages/EvalCenter.tsx`
- [X] T099 [US3] Seed one successful trace and one failed trace linked to node, LLM call, eval failure, and badcase in `backend/app/modules/agent_observability/cli.py`
- [X] T100 [US3] Add observable coverage gap API response mapping in `backend/app/modules/agent_observability/api.py`

**Checkpoint**: A seeded failed experience can be followed from business run to agent, node, tool/LLM, eval case, and badcase without reading raw logs.

---

## Phase 6: User Story 4 - Inspect Node I/O And LLM Requests (Priority: P1)

**Goal**: Developer-agent maintainers can inspect node input/output/state diffs and reconstruct safe LLM cURL commands without exposing secrets or unrestricted raw business text.

**Independent Test**: With a seeded successful node, failed/retried node, and LLM call, verify node I/O, state diff, retry detail, LLM request/response metadata, safe cURL, masked raw reveal policy, audit event, and expired-payload behavior.

### Tests for User Story 4

- [X] T101 [P] [US4] Create masked raw access integration tests in `backend/tests/integration/test_035_masked_raw_access.py`
- [X] T102 [P] [US4] Create node detail and LLM detail contract tests in `backend/tests/contract/test_035_trace_explorer_contract.py`
- [X] T103 [P] [US4] Create node I/O frontend tests in `src/admin/pages/AgentRunDetail.test.tsx`
- [X] T104 [P] [US4] Create LLM call detail and cURL viewer frontend tests in `src/admin/pages/LLMCallDetail.test.tsx`
- [X] T105 [P] [US4] Extend Playwright masked raw and cURL redaction scenarios in `tests/e2e/035-admin-dashboard-mvp.spec.ts`

### Implementation for User Story 4

- [X] T106 [US4] Implement node detail query, state diff shaping, and linked operation assembly in `backend/app/modules/agent_observability/service.py`
- [X] T107 [US4] Implement `/observability/nodes/{span_id}` endpoint in `backend/app/modules/agent_observability/api.py`
- [X] T108 [US4] Implement LLM call detail query, usage, retry, provider id, and streaming timing assembly in `backend/app/modules/agent_observability/service.py`
- [X] T109 [US4] Implement `/observability/llm-calls/{llm_call_id}` endpoint in `backend/app/modules/agent_observability/api.py`
- [X] T110 [US4] Implement masked raw reveal reason validation, role-only authorization, expiry check, and audit creation in `backend/app/modules/agent_observability/payloads.py`
- [X] T111 [US4] Implement `/observability/payloads/{payload_id}/reveal` endpoint in `backend/app/modules/agent_observability/api.py`
- [X] T112 [US4] Implement cURL view service with reason audit and optional masked body mode in `backend/app/modules/agent_observability/service.py`
- [X] T113 [US4] Implement `/observability/llm-calls/{llm_call_id}/curl` endpoint in `backend/app/modules/agent_observability/api.py`
- [X] T114 [US4] Record payload reveal and cURL view audit events in `backend/app/modules/admin_console/service.py`
- [X] T115 [US4] Add capture hooks for agent graph invocation context in `backend/app/agents/base.py`
- [X] T116 [US4] Add capture hooks for checkpointer-resumed graph invocation context in `backend/app/agents/checkpointer.py`
- [X] T117 [US4] Add trace-safe node capture wrappers for centralized node execution helpers in `backend/app/agents/nodes/__init__.py`
- [X] T118 [US4] Add LLM detail and cURL API functions in `src/admin/api/trace-explorer.ts`
- [X] T119 [US4] Add payload visibility, masked raw reveal, and cURL response types in `src/admin/types/trace-explorer.ts`
- [X] T120 [US4] Implement reusable redacted/masked payload viewer in `src/admin/components/trace/PayloadViewer.tsx`
- [X] T121 [US4] Implement masked raw reason dialog with denied, expired, and success states in `src/admin/components/trace/MaskedRawDialog.tsx`
- [X] T122 [US4] Implement node detail panel with input, output, state diff, emitted events, next-step decision, errors, and retries in `src/admin/components/trace/NodeDetailPanel.tsx`
- [X] T123 [US4] Implement LLM call detail page with metadata, parameters, messages summary, response summary, usage, timing, retries, and errors in `src/admin/pages/LLMCallDetail.tsx`
- [X] T124 [US4] Implement safe cURL viewer with secret placeholders and trace context labels in `src/admin/components/trace/CurlViewer.tsx`

**Checkpoint**: Node and LLM debugging works with redacted defaults, approved masked raw reveal, reason capture, audit, and no secret-bearing cURL output.

---

## Phase 7: User Story 5 - Trust Metric Freshness And Definitions (Priority: P2)

**Goal**: Owners can tell whether a number is fresh, stale, partial, empty, or failed, and can inspect the plain-language definition behind every KPI, rate, and trend.

**Independent Test**: Load complete, partial, empty, stale, and error snapshots; verify every dashboard metric shows definition, selected period, source status, and last refresh time.

### Tests for User Story 5

- [X] T125 [P] [US5] Create dashboard freshness integration tests in `backend/tests/integration/test_035_dashboard_freshness.py`
- [X] T126 [P] [US5] Create metric source completeness unit tests in `backend/tests/unit/test_035_metric_definitions.py`
- [X] T127 [P] [US5] Create frontend freshness and definition state tests in `src/admin/components/dashboard/DashboardStates.test.tsx`
- [X] T128 [P] [US5] Extend Playwright stale, partial, empty, and valid-zero dashboard scenarios in `tests/e2e/035-admin-dashboard-mvp.spec.ts`

### Implementation for User Story 5

- [X] T129 [US5] Add per-metric numerator, denominator, comparison rule, source, owner, and version metadata in `backend/app/modules/pm_dashboard/schemas.py`
- [X] T130 [US5] Implement source completeness and quality-state calculation in `backend/app/modules/pm_dashboard/service.py`
- [X] T131 [US5] Persist dashboard metric snapshot freshness and quality state in `backend/app/modules/pm_dashboard/repository.py`
- [X] T132 [US5] Add dashboard freshness target and stale-warning policy in `backend/app/modules/admin_console/service.py`
- [X] T133 [US5] Add metric definition and freshness fields to `/dashboard/summary` responses in `backend/app/modules/admin_console/api.py`
- [X] T134 [US5] Implement metric definition popover/tooltip UI in `src/admin/components/dashboard/MetricDefinition.tsx`
- [X] T135 [US5] Implement freshness, source completeness, stale, partial, empty, valid-zero, and error badges in `src/admin/components/dashboard/FreshnessBadge.tsx`
- [X] T136 [US5] Ensure all dashboard panel components render definition and freshness metadata in `src/admin/pages/ProductDashboard.tsx`
- [X] T137 [US5] Add dashboard refresh timestamp and stale-warning seed cases in `backend/app/modules/agent_observability/cli.py`
- [X] T138 [US5] Implement `coverage-report` CLI command with high-severity gap exit behavior in `backend/app/modules/agent_observability/cli.py`
- [X] T139 [US5] Implement `/observability/coverage` endpoint with covered flows and gaps in `backend/app/modules/agent_observability/api.py`

**Checkpoint**: Dashboard numbers are explainable and freshness-aware, and centralized Agent/LLM coverage gaps are visible rather than silently missing.

---

## Phase 8: User Story 6 - Share MVP Report Snapshot (Priority: P3)

**Goal**: PMs and owners can generate a privacy-safe dashboard snapshot for stakeholder review without copying values across screens.

**Independent Test**: Select a period, generate a snapshot, and verify the artifact includes filters, generated time, visible metrics, definitions or definition references, freshness warnings, and no raw sensitive content.

### Tests for User Story 6

- [X] T140 [P] [US6] Create dashboard snapshot contract tests in `backend/tests/contract/test_035_admin_console_contract.py`
- [X] T141 [P] [US6] Create snapshot privacy integration tests in `backend/tests/integration/test_035_dashboard_snapshot.py`
- [X] T142 [P] [US6] Create dashboard snapshot frontend tests in `src/admin/components/dashboard/SnapshotDialog.test.tsx`
- [X] T143 [P] [US6] Extend Playwright snapshot generation and privacy scenarios in `tests/e2e/035-admin-dashboard-mvp.spec.ts`

### Implementation for User Story 6

- [X] T144 [US6] Implement privacy-safe dashboard snapshot creation and retrieval service methods in `backend/app/modules/admin_console/service.py`
- [X] T145 [US6] Implement snapshot persistence and lookup methods in `backend/app/modules/admin_console/repository.py`
- [X] T146 [US6] Implement `POST /dashboard/snapshots` and `GET /dashboard/snapshots/{dashboard_snapshot_id}` endpoints in `backend/app/modules/admin_console/api.py`
- [X] T147 [US6] Implement `dashboard-snapshot` CLI command and privacy-status exit behavior in `backend/app/modules/admin_console/cli.py`
- [X] T148 [US6] Add dashboard snapshot API functions in `src/admin/api/admin-console.ts`
- [X] T149 [US6] Implement dashboard snapshot dialog and generation flow in `src/admin/components/dashboard/SnapshotDialog.tsx`
- [X] T150 [US6] Implement snapshot detail/download page in `src/admin/pages/DashboardSnapshot.tsx`
- [X] T151 [US6] Add snapshot creation audit events in `backend/app/modules/admin_console/service.py`
- [X] T152 [US6] Generate example privacy-safe snapshot evidence in `docs/evidence/035-admin-dashboard-mvp/dashboard-snapshot.md`

**Checkpoint**: PM/owner snapshot reporting works and carries the same filters, warnings, definitions, and privacy guarantees as the visible dashboard.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Complete validation, docs, evidence, status updates, and operational hardening across the Strong Debug MVP.

- [X] T153 [P] Run backend unit tests and record results in `docs/evidence/035-admin-dashboard-mvp/test-summary.md`
- [X] T154 [P] Run backend contract tests and record results in `docs/evidence/035-admin-dashboard-mvp/test-summary.md`
- [X] T155 [P] Run backend integration tests and record results in `docs/evidence/035-admin-dashboard-mvp/test-summary.md`
- [X] T156 [P] Run admin frontend unit tests and record results in `docs/evidence/035-admin-dashboard-mvp/test-summary.md`
- [X] T157 [P] Run frontend typecheck/build gates and record results in `docs/evidence/035-admin-dashboard-mvp/test-summary.md`
- [X] T158 [P] Run Playwright E2E tests for REQ-035 and store screenshot evidence in `docs/evidence/035-admin-dashboard-mvp/e2e-admin-dashboard.png`
- [X] T159 Generate privacy audit evidence with the CLI in `docs/evidence/035-admin-dashboard-mvp/privacy-audit.json`
- [X] T160 Generate observability coverage evidence with the CLI in `docs/evidence/035-admin-dashboard-mvp/coverage-report.json`
- [X] T161 Validate retention purge dry-run output and append findings in `docs/evidence/035-admin-dashboard-mvp/test-summary.md`
- [X] T162 Update REQ-035 quickstart with final commands, port, and known limitations in `specs/035-admin-dashboard-mvp/quickstart.md`
- [X] T163 Update requirement-level statuses and evidence links in `specs/035-admin-dashboard-mvp/requirements-status.md`
- [X] T164 Update feature README status and next-step notes in `specs/035-admin-dashboard-mvp/README.md`
- [X] T165 Update feature-level status row in `specs/README.md`
- [X] T166 Perform pre-merge code review notes for privacy, retention, fail-open capture, and admin access boundaries in `docs/evidence/035-admin-dashboard-mvp/review-notes.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Stories (Phases 3-8)**: Depend on Foundational completion.
- **Polish (Phase 9)**: Depends on the desired user-story scope being implemented.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundation. Required before any admin page can safely expose data.
- **US2 (P1)**: Starts after Foundation and can run alongside US1 implementation, but full UI validation depends on US1 route guard.
- **US3 (P1)**: Starts after Foundation and can run alongside US2 once trace storage exists.
- **US4 (P1)**: Starts after US3 trace and LLM records are queryable; backend payload/cURL policy can begin earlier after Foundation.
- **US5 (P2)**: Depends on US2 dashboard data structures and adds trust/freshness/coverage detail.
- **US6 (P3)**: Depends on US2 dashboard summary and US5 freshness/definition metadata for complete snapshot output.

### Strong Debug MVP Acceptance Boundary

The first accepted MVP is not US1 alone. For REQ-035, complete and validate:

1. Phase 1 Setup.
2. Phase 2 Foundation.
3. US1 Admin access boundary.
4. US2 PM dashboard.
5. US3 Trace Explorer and Eval Center.
6. US4 Node I/O, LLM detail, redacted cURL, masked raw policy.

US5 and US6 are lower priority, but they are included in the implementation plan because metric trust and reporting are explicit business requirements.

---

## Parallel Examples

### Foundation

```text
Task: T013 model and migration tests in backend/tests/unit/test_035_admin_observability_models.py
Task: T014 payload visibility tests in backend/tests/unit/test_035_payload_visibility.py
Task: T015 cURL redaction tests in backend/tests/unit/test_035_curl_redaction.py
Task: T016 retention policy tests in backend/tests/unit/test_035_retention_policy.py
Task: T017 coverage report tests in backend/tests/unit/test_035_coverage_report.py
```

### User Story 1

```text
Task: T041 admin console contract tests in backend/tests/contract/test_035_admin_console_contract.py
Task: T042 admin access integration tests in backend/tests/integration/test_035_admin_access.py
Task: T043 admin shell frontend tests in src/admin/AdminApp.test.tsx
Task: T044 Playwright access scenarios in tests/e2e/035-admin-dashboard-mvp.spec.ts
```

### User Story 2

```text
Task: T056 dashboard aggregation integration tests in backend/tests/integration/test_035_dashboard_summary.py
Task: T057 dashboard frontend tests in src/admin/pages/ProductDashboard.test.tsx
Task: T067 overview component in src/admin/components/dashboard/OverviewMetrics.tsx
Task: T068 funnel component in src/admin/components/dashboard/FunnelPanel.tsx
```

### User Story 3

```text
Task: T075 Trace Explorer contract tests in backend/tests/contract/test_035_trace_explorer_contract.py
Task: T076 Eval Center contract tests in backend/tests/contract/test_035_eval_center_contract.py
Task: T094 Trace Explorer page in src/admin/pages/TraceExplorer.tsx
Task: T098 Eval Center page in src/admin/pages/EvalCenter.tsx
```

### User Story 4

```text
Task: T101 masked raw integration tests in backend/tests/integration/test_035_masked_raw_access.py
Task: T104 LLM call detail frontend tests in src/admin/pages/LLMCallDetail.test.tsx
Task: T120 payload viewer in src/admin/components/trace/PayloadViewer.tsx
Task: T124 cURL viewer in src/admin/components/trace/CurlViewer.tsx
```

---

## Implementation Strategy

### MVP First For This Feature

1. Complete Phase 1 and Phase 2.
2. Complete US1 through US4 as the Strong Debug MVP.
3. Validate admin access, dashboard, trace drilldown, node I/O, LLM cURL redaction, masked raw audit, and Eval Center together.
4. Only then expose the admin entry point beyond trusted local/staging reviewers.

### Incremental Delivery

1. Land the protected admin shell with no sensitive data.
2. Add the PM dashboard summary and date filters.
3. Add trace search, hierarchy, and Eval Center.
4. Add node/LLM payload and cURL inspection with strict privacy controls.
5. Add freshness/definition trust layer.
6. Add snapshot reporting.

### Team Parallelization

After Phase 2:

- Backend API owner: US1/US2 admin APIs and PM dashboard summary.
- Observability owner: US3/US4 trace, payload, LLM, eval, retention, and coverage.
- Frontend owner: admin shell, dashboard, trace explorer, Eval Center, and payload viewers.
- QA/evidence owner: tests, Playwright, privacy audit, retention, coverage, and documentation evidence.

---

## Notes

- Keep dashboard and snapshots aggregate/redacted only.
- Never persist or render literal API keys, bearer tokens, cookies, refresh tokens, private keys, or service credentials in cURL output.
- Production masked raw reveal requires developer/reviewer role, non-empty reason, audit event, and unexpired masked payload.
- Capture must fail open and must not block user-facing product flows.
- Update `specs/035-admin-dashboard-mvp/requirements-status.md` only when implementation and verification evidence both exist.
