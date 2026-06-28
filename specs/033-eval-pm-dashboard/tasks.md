# Tasks: REQ-033 Automated Eval & PM Dashboard MVP

**Input**: Design documents from `specs/033-eval-pm-dashboard/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required. InterCraft Constitution Principle III is Test-First, so every non-trivial slice starts with failing contract/unit/integration tests before implementation.

**Organization**: Tasks are grouped by independently testable user story. Foundation tasks must finish before user-story tasks begin.

## Format: `[ID] [P?] [Story] Description`

- `[P]`: Can run in parallel because it touches different files and does not depend on incomplete tasks.
- `[Story]`: User-story label for story phases only.
- Every task includes a concrete file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the module/documentation skeleton and configuration surfaces used by later stories.

- [ ] T001 Create `backend/app/modules/telemetry_contracts/README.md` documenting event, metric, redaction, and retention module boundaries.
- [ ] T002 [P] Create `backend/app/modules/pm_dashboard/README.md` documenting PM Dashboard V1 sources, panels, and CLI/API ownership.
- [ ] T003 [P] Create `backend/app/modules/badcases/README.md` documenting badcase lifecycle, CLI-first promotion, and human review rules.
- [ ] T004 [P] Create `docs/evidence/033-eval-pm-dashboard/README.md` with expected eval, redaction, dashboard, and badcase evidence artifact names.
- [ ] T005 Add LangSmith and dashboard environment settings to `backend/app/core/config.py` without storing secrets in code.
- [ ] T006 Add direct LangSmith dependency if needed in `backend/pyproject.toml` and refresh `backend/uv.lock`.
- [ ] T007 Create frontend PM dashboard type barrel in `src/types/pm-dashboard.ts`.
- [ ] T008 Create frontend PM dashboard API client placeholder in `src/api/pm-dashboard.ts`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared contracts for events, metrics, privacy, retention, and storage. No user story should begin until this phase is complete.

- [ ] T009 [P] Write failing event/metric schema contract tests in `backend/tests/contract/test_033_event_metric_schema.py`.
- [ ] T010 [P] Write failing redaction policy unit tests in `backend/tests/unit/test_033_redaction.py`.
- [ ] T011 [P] Write failing metric definition unit tests in `backend/tests/unit/test_033_metric_definitions.py`.
- [ ] T012 [P] Write failing production retention unit tests in `backend/tests/unit/test_033_retention.py`.
- [ ] T013 [P] Write failing eval report schema tests in `backend/tests/eval/test_033_eval_report_schema.py`.
- [ ] T014 Implement shared Pydantic value objects in `backend/app/modules/telemetry_contracts/schemas.py`.
- [ ] T015 Implement event catalog and validation helpers in `backend/app/modules/telemetry_contracts/events.py`.
- [ ] T016 Implement metric definition catalog in `backend/app/modules/telemetry_contracts/metrics.py`.
- [ ] T017 Implement environment redaction policy evaluator in `backend/app/modules/telemetry_contracts/redaction.py`.
- [ ] T018 Implement production retention helpers in `backend/app/modules/telemetry_contracts/retention.py`.
- [ ] T019 Create persistence migration for eval metadata, PM metric snapshots, badcases, redaction audit, and retention fields in `backend/migrations/versions/0024_033_eval_pm_dashboard.py`.
- [ ] T020 Create shared SQLAlchemy models for telemetry contracts in `backend/app/modules/telemetry_contracts/models.py`.
- [ ] T021 Create shared telemetry repository helpers in `backend/app/modules/telemetry_contracts/repository.py`.
- [ ] T022 Add router registration placeholders for PM dashboard and badcases in `backend/app/main.py`.
- [ ] T023 Add backend contract fixture builders for 033 entities in `backend/tests/contract/fixtures/test_033_fixtures.py`.
- [ ] T024 Run and document foundational test status in `test-reports/REQ-033-foundation-test.md`.

**Checkpoint**: Event/metric/redaction/retention contracts exist, failing tests are in place, and user-story implementation can begin.

---

## Phase 3: User Story 10 - Environment-Specific Redaction Policy (Priority: P1)

**Goal**: Enforce local/CI/staging/production export policy, including production metadata + redacted summaries only and 30-day production trace retention.

**Independent Test**: Run redaction policy tests and a redaction audit sample to confirm forbidden production payloads are blocked while runtime remains fail-open.

### Tests for User Story 10

- [ ] T025 [P] [US10] Write failing redaction audit integration tests in `backend/tests/integration/test_033_redaction_policy.py`.
- [ ] T026 [P] [US10] Write failing retention integration tests in `backend/tests/integration/test_033_production_retention.py`.
- [ ] T027 [P] [US10] Write failing CLI contract tests for redaction audit in `backend/tests/contract/test_033_redaction_cli_contract.py`.

### Implementation for User Story 10

- [ ] T028 [US10] Implement redaction audit CLI entrypoint in `backend/app/modules/telemetry_contracts/redaction_cli.py`.
- [ ] T029 [US10] Implement retention CLI entrypoint in `backend/app/modules/telemetry_contracts/retention_cli.py`.
- [ ] T030 [US10] Add export-policy guard around eval and LangSmith payload preparation in `backend/app/eval/export_policy.py`.
- [ ] T031 [US10] Add production forbidden-content sample fixtures in `backend/tests/integration/fixtures/033_redaction_samples.py`.
- [ ] T032 [US10] Document redaction evidence format in `docs/evidence/033-eval-pm-dashboard/redaction-check-template.md`.
- [ ] T033 [US10] Record US10 verification evidence in `test-reports/REQ-033-US10-test.md`.

**Checkpoint**: US10 can be validated independently with no PM dashboard UI or LangSmith sync enabled.

---

## Phase 4: User Story 9 - Version, Prompt, Rubric, And Experiment Fields (Priority: P1)

**Goal**: Ensure eval runs, AI summaries, PM metrics, and badcases carry consistent version and join fields or explicit `unknown` values.

**Independent Test**: Inspect seeded records and generated metrics to confirm required version fields are present or explicitly unknown.

### Tests for User Story 9

- [ ] T034 [P] [US9] Write failing VersionContext schema tests in `backend/tests/unit/test_033_version_context.py`.
- [ ] T035 [P] [US9] Write failing eval runner metadata tests in `backend/tests/eval/test_033_eval_version_fields.py`.
- [ ] T036 [P] [US9] Write failing AI invocation version-field tests in `backend/tests/unit/test_033_ai_invocation_fields.py`.

### Implementation for User Story 9

- [ ] T037 [US9] Extend VersionContext helpers in `backend/app/modules/telemetry_contracts/schemas.py`.
- [ ] T038 [US9] Extend eval run metadata generation in `backend/app/eval/runner.py`.
- [ ] T039 [US9] Add stable prompt fingerprint helpers in `backend/app/eval/prompt_fingerprint.py`.
- [ ] T040 [US9] Extend AI invocation summary extraction in `backend/app/agents/llm_client.py`.
- [ ] T041 [US9] Add version-aware metric dimensions in `backend/app/modules/telemetry_contracts/metrics.py`.
- [ ] T042 [US9] Add version fields to badcase schemas in `backend/app/modules/badcases/schemas.py`.
- [ ] T043 [US9] Record US9 verification evidence in `test-reports/REQ-033-US9-test.md`.

**Checkpoint**: US9 can be validated independently through schema/unit tests and generated sample rows.

---

## Phase 5: User Story 5 - Automatic Golden-Case Eval In PR (Priority: P1)

**Goal**: Make prompt-adjacent PRs run deterministic golden-case eval, publish local artifacts, and block deterministic failures unless a dual-approved override is recorded.

**Independent Test**: Trigger a PR-like eval run with one failing case and confirm the report includes debug identifiers and exits with gate failure.

### Tests for User Story 5

- [ ] T044 [P] [US5] Write failing eval CLI contract tests in `backend/tests/eval/test_033_eval_cli_contract.py`.
- [ ] T045 [P] [US5] Write failing eval report renderer tests in `backend/tests/eval/test_033_eval_report_renderer.py`.
- [ ] T046 [P] [US5] Write failing override record tests in `backend/tests/eval/test_033_override_record.py`.

### Implementation for User Story 5

- [ ] T047 [US5] Implement stable eval report models in `backend/app/eval/report.py`.
- [ ] T048 [US5] Extend eval CLI `run` command flags in `backend/app/eval/cli.py`.
- [ ] T049 [US5] Extend eval runner aggregate fields in `backend/app/eval/runner.py`.
- [ ] T050 [US5] Implement Markdown report rendering in `backend/app/eval/report.py`.
- [ ] T051 [US5] Implement dual-approval override record command in `backend/app/eval/cli.py`.
- [ ] T052 [US5] Add prompt-adjacent CI eval workflow in `.github/workflows/033-eval-gate.yml`.
- [ ] T053 [US5] Add CI path filter documentation in `docs/testing/README.md`.
- [ ] T054 [US5] Record US5 verification evidence in `test-reports/REQ-033-US5-test.md`.

**Checkpoint**: US5 delivers the first developer-facing Safe MVP slice without requiring LangSmith.

---

## Phase 6: User Story 8 - Badcase Mark, Classify, Promote, And Close (Priority: P1)

**Goal**: Support reviewed badcase lifecycle, closure, and first-month CLI/documented golden-case promotion.

**Independent Test**: Create a badcase, classify it, attach evidence, promote a candidate, and close it with required reviewer fields.

### Tests for User Story 8

- [x] T055 [P] [US8] Write failing badcase API contract tests in `backend/tests/contract/test_033_badcase_contract.py`.
- [x] T056 [P] [US8] Write failing badcase service unit tests in `backend/tests/unit/test_033_badcase_service.py`.
- [x] T057 [P] [US8] Write failing badcase promotion CLI integration tests in `backend/tests/integration/test_033_badcase_promotion_cli.py`.

### Implementation for User Story 8

- [x] T058 [US8] Implement badcase SQLAlchemy models in `backend/app/modules/badcases/models.py`.
- [x] T059 [US8] Implement badcase Pydantic schemas in `backend/app/modules/badcases/schemas.py`.
- [x] T060 [US8] Implement badcase repository in `backend/app/modules/badcases/repository.py`.
- [x] T061 [US8] Implement badcase service lifecycle rules in `backend/app/modules/badcases/service.py`.
- [x] T062 [US8] Implement badcase API routes in `backend/app/modules/badcases/api.py`.
- [x] T063 [US8] Implement badcase CLI create/promote/close commands in `backend/app/modules/badcases/cli.py`.
- [x] T064 [US8] Implement golden-case candidate writer in `backend/app/modules/badcases/promotion.py`.
- [x] T065 [US8] Register badcase router in `backend/app/main.py`.
- [x] T066 [US8] Record US8 verification evidence in `test-reports/REQ-033-US8-test.md`.

**Checkpoint**: US8 is independently usable from CLI and API before PM dashboard integration.

---

## Phase 7: User Story 1 - PM Product Overview And Core Funnel (Priority: P1)

**Goal**: Provide PM Dashboard V1 overview and core funnel panels with freshness, quality flags, and filter semantics.

**Independent Test**: Seed product/funnel metrics and confirm PM can view overview and funnel counts/conversion/drop-off states.

### Tests for User Story 1

- [ ] T067 [P] [US1] Write failing PM dashboard overview/funnel contract tests in `backend/tests/contract/test_033_pm_dashboard_contract.py`.
- [ ] T068 [P] [US1] Write failing PM dashboard metric integration tests in `backend/tests/integration/test_033_pm_dashboard_metrics.py`.
- [ ] T069 [P] [US1] Write failing frontend PM dashboard shell tests in `src/pages/__tests__/PMDashboard.test.tsx`.

### Implementation for User Story 1

- [ ] T070 [US1] Implement PM dashboard filter and envelope schemas in `backend/app/modules/pm_dashboard/schemas.py`.
- [ ] T071 [US1] Implement overview/funnel metric repository queries in `backend/app/modules/pm_dashboard/repository.py`.
- [ ] T072 [US1] Implement overview/funnel metric service in `backend/app/modules/pm_dashboard/service.py`.
- [ ] T073 [US1] Implement overview/funnel API routes in `backend/app/modules/pm_dashboard/api.py`.
- [ ] T074 [US1] Register PM dashboard router in `backend/app/main.py`.
- [ ] T075 [US1] Implement frontend PM dashboard API client methods in `src/api/pm-dashboard.ts`.
- [ ] T076 [US1] Implement frontend PM dashboard types in `src/types/pm-dashboard.ts`.
- [ ] T077 [US1] Implement PM dashboard page shell in `src/pages/PMDashboard.tsx`.
- [ ] T078 [P] [US1] Implement overview panel in `src/components/pm-dashboard/OverviewPanel.tsx`.
- [ ] T079 [P] [US1] Implement funnel panel in `src/components/pm-dashboard/FunnelPanel.tsx`.
- [ ] T080 [US1] Add PM dashboard route in `src/App.tsx`.
- [ ] T081 [US1] Record US1 verification evidence in `test-reports/REQ-033-US1-test.md`.

**Checkpoint**: PM overview and core funnel are independently demoable with seeded metrics.

---

## Phase 8: User Story 2 - Resume Diagnosis And Suggestion Adoption (Priority: P1)

**Goal**: Show resume diagnosis success, report views, suggestions shown/accepted, acceptance rate, and score delta.

**Independent Test**: Seed resume diagnosis outcomes and confirm the resume panel aggregates and filters correctly without raw resume content.

### Tests for User Story 2

- [ ] T082 [P] [US2] Write failing resume diagnosis dashboard backend tests in `backend/tests/integration/test_033_resume_diagnosis_metrics.py`.
- [ ] T083 [P] [US2] Write failing resume diagnosis panel frontend tests in `src/components/pm-dashboard/__tests__/ResumeDiagnosisPanel.test.tsx`.

### Implementation for User Story 2

- [ ] T084 [US2] Add ResumeDiagnosisOutcome persistence mapping in `backend/app/modules/pm_dashboard/repository.py`.
- [ ] T085 [US2] Implement resume diagnosis metric assembly in `backend/app/modules/pm_dashboard/service.py`.
- [ ] T086 [US2] Add resume diagnosis API response schema in `backend/app/modules/pm_dashboard/schemas.py`.
- [ ] T087 [US2] Add resume diagnosis route in `backend/app/modules/pm_dashboard/api.py`.
- [ ] T088 [US2] Implement resume diagnosis panel in `src/components/pm-dashboard/ResumeDiagnosisPanel.tsx`.
- [ ] T089 [US2] Wire resume diagnosis panel into `src/pages/PMDashboard.tsx`.
- [ ] T090 [US2] Record US2 verification evidence in `test-reports/REQ-033-US2-test.md`.

**Checkpoint**: Resume diagnosis metrics are independently visible and privacy-safe.

---

## Phase 9: User Story 3 - Mock Interview Usage And Completion (Priority: P1)

**Goal**: Show mock interview starts, completions, completion rate, average question count, report views, retries, and failure rate.

**Independent Test**: Seed interview outcomes and confirm the interview panel aggregates starts/completions/retries/failures correctly.

### Tests for User Story 3

- [x] T091 [P] [US3] Write failing mock interview dashboard backend tests in `backend/tests/integration/test_033_mock_interview_metrics.py`.
- [x] T092 [P] [US3] Write failing mock interview panel frontend tests in `src/components/pm-dashboard/__tests__/MockInterviewPanel.test.tsx`.

### Implementation for User Story 3

- [x] T093 [US3] Add InterviewOutcome persistence mapping in `backend/app/modules/pm_dashboard/repository.py`.
- [x] T094 [US3] Implement mock interview metric assembly in `backend/app/modules/pm_dashboard/service.py`.
- [x] T095 [US3] Add mock interview API response schema in `backend/app/modules/pm_dashboard/schemas.py`.
- [x] T096 [US3] Add mock interview route in `backend/app/modules/pm_dashboard/api.py`.
- [x] T097 [US3] Implement mock interview panel in `src/components/pm-dashboard/MockInterviewPanel.tsx`.
- [x] T098 [US3] Wire mock interview panel into `src/pages/PMDashboard.tsx`.
- [x] T099 [US3] Record US3 verification evidence in `test-reports/REQ-033-US3-test.md`.

**Checkpoint**: Mock interview usage/completion metrics are independently visible.

---

## Phase 10: User Story 4 - AI Cost, Latency, And Reliability (Priority: P1)

**Goal**: Show AI call count, success/failure, retries, latency, estimated cost, token usage, model, graph, node, and prompt fingerprint.

**Independent Test**: Seed AI invocation summaries and confirm AI operations metrics match definitions and cost is labeled as estimate.

### Tests for User Story 4

- [ ] T100 [P] [US4] Write failing AI operations backend tests in `backend/tests/integration/test_033_ai_operations_metrics.py`.
- [ ] T101 [P] [US4] Write failing AI operations panel frontend tests in `src/components/pm-dashboard/__tests__/AIOperationsPanel.test.tsx`.
- [ ] T102 [P] [US4] Write failing AI cost-estimate unit tests in `backend/tests/unit/test_033_ai_cost_estimates.py`.

### Implementation for User Story 4

- [ ] T103 [US4] Add AIInvocationRecord persistence mapping in `backend/app/modules/pm_dashboard/repository.py`.
- [ ] T104 [US4] Implement AI operations metric assembly in `backend/app/modules/pm_dashboard/service.py`.
- [ ] T105 [US4] Add AI operations API response schema in `backend/app/modules/pm_dashboard/schemas.py`.
- [ ] T106 [US4] Add AI operations route in `backend/app/modules/pm_dashboard/api.py`.
- [ ] T107 [US4] Implement estimated cost calculator in `backend/app/modules/telemetry_contracts/costs.py`.
- [ ] T108 [US4] Connect AI invocation summaries to existing LLM metrics in `backend/app/agents/llm_client.py`.
- [ ] T109 [US4] Implement AI operations panel in `src/components/pm-dashboard/AIOperationsPanel.tsx`.
- [ ] T110 [US4] Wire AI operations panel into `src/pages/PMDashboard.tsx`.
- [ ] T111 [US4] Record US4 verification evidence in `test-reports/REQ-033-US4-test.md`.

**Checkpoint**: AI operations metrics are independently visible with cost estimates clearly labeled.

---

## Phase 11: User Story 6 - LangSmith Experiment Sync (Priority: P2)

**Goal**: Sync uploadable eval runs to LangSmith experiments when enabled while keeping local reports canonical.

**Independent Test**: Run eval with LangSmith disabled and enabled; verify disabled is safe, enabled uses the same run id, and sync failure does not rewrite local verdicts.

### Tests for User Story 6

- [ ] T112 [P] [US6] Write failing LangSmith reporter disabled-path tests in `backend/tests/eval/test_033_langsmith_reporter.py`.
- [ ] T113 [P] [US6] Write failing LangSmith upload privacy tests in `backend/tests/eval/test_033_langsmith_upload_policy.py`.
- [ ] T114 [P] [US6] Write failing LangSmith sync CLI contract tests in `backend/tests/eval/test_033_langsmith_cli.py`.

### Implementation for User Story 6

- [ ] T115 [US6] Implement optional LangSmith reporter in `backend/app/eval/langsmith_reporter.py`.
- [ ] T116 [US6] Add LangSmith dataset and experiment naming helpers in `backend/app/eval/langsmith_reporter.py`.
- [ ] T117 [US6] Add LangSmith sync command to `backend/app/eval/cli.py`.
- [ ] T118 [US6] Add LangSmith sync references to eval report output in `backend/app/eval/report.py`.
- [ ] T119 [US6] Add LangSmith configuration validation in `backend/app/core/config.py`.
- [ ] T120 [US6] Add LangSmith-enabled quickstart evidence template in `docs/evidence/033-eval-pm-dashboard/langsmith-sync-template.md`.
- [ ] T121 [US6] Record US6 verification evidence in `test-reports/REQ-033-US6-test.md`.

**Checkpoint**: LangSmith integration is optional, fail-open, and joinable by run id.

---

## Phase 12: User Story 7 - Locate Failed Case By Trace Or Run ID (Priority: P2)

**Goal**: Let developers jump from eval report to local artifacts, trace id, case id, and LangSmith experiment when available.

**Independent Test**: Create one failing eval case and confirm report links identify trace/run/case or explicitly state trace unavailable.

### Tests for User Story 7

- [ ] T122 [P] [US7] Write failing failed-case trace-link tests in `backend/tests/eval/test_033_failed_case_trace_links.py`.
- [ ] T123 [P] [US7] Write failing trace-unavailable report tests in `backend/tests/eval/test_033_trace_unavailable.py`.
- [ ] T124 [P] [US7] Write failing version experiment panel frontend tests in `src/components/pm-dashboard/__tests__/VersionExperimentPanel.test.tsx`.

### Implementation for User Story 7

- [ ] T125 [US7] Add trace/run/case link fields to eval report rendering in `backend/app/eval/report.py`.
- [ ] T126 [US7] Add TraceRunRef helpers in `backend/app/modules/telemetry_contracts/repository.py`.
- [ ] T127 [US7] Add trace id extraction adapter in `backend/app/observability/tracing.py`.
- [ ] T128 [US7] Add badcase evidence trace linking in `backend/app/modules/badcases/service.py`.
- [ ] T129 [US7] Add version/experiment dashboard route in `backend/app/modules/pm_dashboard/api.py`.
- [ ] T130 [US7] Implement version and experiment panel in `src/components/pm-dashboard/VersionExperimentPanel.tsx`.
- [ ] T131 [US7] Wire version and experiment panel into `src/pages/PMDashboard.tsx`.
- [ ] T132 [US7] Record US7 verification evidence in `test-reports/REQ-033-US7-test.md`.

**Checkpoint**: Failed eval cases can be located without guessing, and missing traces are explicit.

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and release-readiness checks across all selected stories.

- [ ] T133 [P] Add module README usage examples for eval reporting in `backend/app/eval/README.md`.
- [ ] T134 [P] Add PM dashboard implementation notes in `backend/app/modules/pm_dashboard/README.md`.
- [ ] T135 [P] Add badcase review workflow examples in `backend/app/modules/badcases/README.md`.
- [ ] T136 [P] Add telemetry contracts usage examples in `backend/app/modules/telemetry_contracts/README.md`.
- [ ] T137 Add canonical E2E coverage for PM dashboard happy path in `tests/e2e/033-pm-dashboard.spec.ts`.
- [ ] T138 Run frontend typecheck/build validation and record output in `test-reports/REQ-033-frontend-validation.md`.
- [ ] T139 Run backend eval/contract/full test validation and record output in `test-reports/REQ-033-backend-validation.md`.
- [ ] T140 Run quickstart scenarios and record completion notes in `test-reports/REQ-033-quickstart-validation.md`.
- [ ] T141 Update requirement statuses with evidence links in `specs/033-eval-pm-dashboard/requirements-status.md`.
- [ ] T142 Update feature index status and notes in `specs/README.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies.
- Foundational (Phase 2): depends on Setup and blocks all user stories.
- US10 and US9 should be completed before any external export, LangSmith sync, or PM dashboard release.
- US5 can ship after US10 and US9 as the first developer Safe MVP.
- US8 can ship after US10 and US9 to support reviewed badcase lifecycle.
- US1 can ship after Foundational, US9, and enough event/metric fixture data for overview/funnel.
- US2, US3, and US4 extend PM Dashboard V1 panels after US1.
- US6 depends on US5 and US10.
- US7 depends on US5, US6 where LangSmith links are needed, and existing trace fields from feature 029.
- Polish depends on all desired story phases.

### User Story Dependencies

- US10: depends only on Foundational; should be first because privacy gates external export.
- US9: depends on Foundational; should be early because every later record needs version context.
- US5: depends on US10 and US9 for privacy/version-safe eval reports.
- US8: depends on US10 and US9 for redacted, versioned badcase evidence.
- US1: depends on Foundational and US9; can use seeded metric snapshots before all panels exist.
- US2: depends on US1 PM dashboard shell.
- US3: depends on US1 PM dashboard shell.
- US4: depends on US1 PM dashboard shell and US9 version fields.
- US6: depends on US5 and US10.
- US7: depends on US5 and trace/run fields; LangSmith link behavior depends on US6.

### Within Each User Story

- Tests must be written first and fail for the expected reason.
- Data/schema contracts before repositories.
- Repositories before services.
- Services before API/CLI routes.
- Backend contracts before frontend consumers.
- Evidence is recorded after validation passes.

## Parallel Opportunities

- T002, T003, T004, T007, and T008 can run in parallel after T001.
- T009 through T013 can run in parallel as failing tests.
- T015 through T018 can run in parallel after T014.
- After Phase 2, US10 and US9 can proceed in parallel if the shared schema file changes are coordinated.
- US2 and US3 can proceed in parallel after US1 shell/API contracts exist.
- US6 and US7 can proceed in parallel after US5, with US7 treating LangSmith links as optional until US6 is done.
- Frontend panel tasks for US1, US2, US3, US4, and US7 can run in parallel with backend service implementation once API contracts are frozen.

## Parallel Example: US1 Product Overview And Core Funnel

```text
Task: T067 Write failing PM dashboard overview/funnel contract tests in backend/tests/contract/test_033_pm_dashboard_contract.py
Task: T068 Write failing PM dashboard metric integration tests in backend/tests/integration/test_033_pm_dashboard_metrics.py
Task: T069 Write failing frontend PM dashboard shell tests in src/pages/__tests__/PMDashboard.test.tsx
Task: T078 Implement overview panel in src/components/pm-dashboard/OverviewPanel.tsx
Task: T079 Implement funnel panel in src/components/pm-dashboard/FunnelPanel.tsx
```

## Parallel Example: US2 And US3 Dashboard Panels

```text
Task: T082 Write failing resume diagnosis dashboard backend tests in backend/tests/integration/test_033_resume_diagnosis_metrics.py
Task: T091 Write failing mock interview dashboard backend tests in backend/tests/integration/test_033_mock_interview_metrics.py
Task: T088 Implement resume diagnosis panel in src/components/pm-dashboard/ResumeDiagnosisPanel.tsx
Task: T097 Implement mock interview panel in src/components/pm-dashboard/MockInterviewPanel.tsx
```

## Implementation Strategy

### Safe MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US10 to make export privacy enforceable.
3. Complete US9 so eval, dashboard, and badcase records have version context.
4. Complete US5 to ship deterministic PR golden-case eval with local artifacts.
5. Stop and validate with `backend/tests/eval`, redaction tests, and generated evidence.

### PM Dashboard MVP

1. Complete US1 for product overview and core funnel.
2. Add US2 and US3 for resume and interview product loops.
3. Add US4 for AI operations/cost/reliability.
4. Validate dashboard contracts and frontend behavior before adding LangSmith links.

### LangSmith And Debug Expansion

1. Complete US6 after Safe MVP local eval is stable.
2. Complete US7 to make failed-case drilldown reliable.
3. Keep LangSmith optional and fail-open throughout.

## Task Count Summary

| Area | Count |
|---|---:|
| Setup | 8 |
| Foundational | 16 |
| US10 | 9 |
| US9 | 10 |
| US5 | 11 |
| US8 | 12 |
| US1 | 15 |
| US2 | 9 |
| US3 | 9 |
| US4 | 12 |
| US6 | 10 |
| US7 | 11 |
| Polish | 10 |
| Total | 142 |
