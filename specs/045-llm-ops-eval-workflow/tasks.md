# Tasks: REQ-045 LLM Ops Eval Workflow

**Input**: Design documents from `specs/045-llm-ops-eval-workflow/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required. InterCraft Constitution principle III is Test-First, and REQ-045 changes production observability, eval gates, external export, and AI quality decisions.

**Organization**: Tasks are grouped by independently testable user story. Setup and Foundational phases must complete first; each user story phase can then be implemented and validated as an increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks.
- **[Story]**: Required only for user story phases.
- Every task includes an exact file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare direct dependencies, docs entry points, and evidence locations for REQ-045.

- [X] T001 Add direct `langsmith` and required OpenTelemetry instrumentation dependencies in `backend/pyproject.toml`
- [X] T002 [P] Add REQ-045 command and module overview to `backend/app/eval/README.md`
- [X] T003 [P] Add REQ-045 trace/export contract notes to `backend/app/observability/README.md`
- [X] T004 [P] Add destination policy and full-content LangSmith notes to `backend/app/modules/telemetry_contracts/README.md`
- [X] T005 [P] Add REQ-045 fixture README for sample reports and export samples in `specs/045-llm-ops-eval-workflow/fixtures/README.md`
- [X] T006 [P] Add evidence directory marker in `docs/evidence/045-llm-ops-eval-workflow/.gitkeep`
- [X] T007 [P] Export planned eval modules from `backend/app/eval/__init__.py`
- [X] T008 [P] Add REQ-045 implementation note to `specs/045-llm-ops-eval-workflow/requirements-status.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schemas, persistence, settings, and bounded metrics that all user stories depend on.

**Critical**: No user story implementation should begin until this phase is complete.

### Tests First

- [X] T009 [P] Add shared enum and schema unit tests in `backend/tests/unit/test_045_llm_ops_schemas.py`
- [X] T010 [P] Add migration/schema contract tests for REQ-045 records in `backend/tests/contract/test_045_llm_ops_migrations.py`
- [X] T011 [P] Add shared CLI exit-code contract tests in `backend/tests/contract/test_045_llm_ops_cli_contract.py`
- [X] T012 [P] Add bounded metric registration tests in `backend/tests/unit/test_045_llm_ops_metrics.py`

### Implementation

- [X] T013 Create shared eval/run/reference Pydantic models in `backend/app/eval/schemas.py`
- [X] T014 Add destination export policy value objects in `backend/app/modules/telemetry_contracts/export_policy.py`
- [X] T015 Add LLM Ops repository helpers for eval runs, trace refs, export decisions, and prompt proposals in `backend/app/modules/telemetry_contracts/llm_ops_repository.py`
- [X] T016 Add SQLAlchemy models or model imports for REQ-045 records in `backend/app/modules/telemetry_contracts/models.py`
- [X] T017 Add Alembic migration for eval runs, case results, trace refs, LangSmith refs, judge verdicts, export decisions, badcase candidates, and prompt proposals in `backend/migrations/versions/0045_llm_ops_eval_workflow.py`
- [X] T018 Add OTel, LangSmith, sync mode, and destination policy settings in `backend/app/core/config.py`
- [X] T019 Add bounded REQ-045 counters/histograms for eval runs, export status, judge calibration, and trace coverage in `backend/app/core/metrics.py`
- [X] T020 Add shared CLI response helpers for JSON/error output in `backend/app/eval/cli_contracts.py`
- [X] T021 Add reusable artifact path helpers for eval evidence in `backend/app/eval/artifacts.py`
- [X] T022 Update telemetry contract package exports in `backend/app/modules/telemetry_contracts/__init__.py`
- [X] T023 Update backend package imports after new modules in `backend/app/eval/__init__.py`
- [X] T024 Document foundational schema decisions in `specs/045-llm-ops-eval-workflow/data-model.md`

**Checkpoint**: Shared schemas, migrations, config, metrics, and CLI helpers exist and foundational tests fail for missing implementation before story work begins.

---

## Phase 3: User Story 1 - Run Trace-Linked Eval Gate (Priority: P1) MVP

**Goal**: Engineers can run an eval gate that produces complete local artifacts and optional LangSmith links without making LangSmith the local verdict source.

**Independent Test**: Run the eval suite with LangSmith disabled and enabled, then verify stable local JSON/Markdown reports, explicit unavailable links when disabled, and matching LangSmith references when enabled.

### Tests First

- [X] T025 [P] [US1] Add eval report schema contract tests in `backend/tests/contract/test_045_eval_report_schema.py`
- [X] T026 [P] [US1] Add eval run CLI contract tests for `--sync-langsmith` modes in `backend/tests/contract/test_045_eval_run_cli.py`
- [X] T027 [P] [US1] Add mocked LangSmith sync tests for disabled, synced, failed, and require modes in `backend/tests/eval/test_045_langsmith_sync.py`
- [X] T028 [P] [US1] Add local artifact rendering tests for JSON/Markdown parity in `backend/tests/eval/test_045_eval_artifacts.py`
- [X] T029 [P] [US1] Add regression-gate behavior tests for exit code 4 in `backend/tests/eval/test_045_eval_gate_regressions.py`

### Implementation

- [X] T030 [US1] Implement REQ-045 report schema normalization in `backend/app/eval/report.py`
- [X] T031 [US1] Add stable case/run/trace/artifact/LangSmith fields to eval run output in `backend/app/eval/runner.py`
- [X] T032 [US1] Implement optional LangSmith dataset/experiment sync adapter in `backend/app/eval/langsmith_sync.py`
- [X] T033 [US1] Extend eval CLI `run` with `--sync-langsmith` and add `langsmith-sync` subcommand in `backend/app/eval/cli.py`
- [X] T034 [US1] Add LangSmith export status and deep-link propagation to local reports in `backend/app/eval/report.py`
- [X] T035 [US1] Extend golden loader lifecycle and dataset version handling in `backend/app/eval/golden_loader.py`
- [X] T036 [US1] Add REQ-045 sample eval report fixture in `specs/045-llm-ops-eval-workflow/fixtures/eval-report-sample.json`
- [X] T037 [US1] Add CI workflow entry or extend existing eval gate path filters in `.github/workflows/045-llm-ops-eval-gate.yml`
- [X] T038 [US1] Update eval README with disabled/enabled LangSmith examples in `backend/app/eval/README.md`
- [X] T039 [US1] Record US1 validation commands and expected artifacts in `docs/evidence/045-llm-ops-eval-workflow/us1-eval-gate.md`
- [X] T040 [US1] Mark US1 requirement rows in `specs/045-llm-ops-eval-workflow/requirements-status.md`

**Checkpoint**: US1 is independently usable as the MVP eval gate. LangSmith disabled mode works locally; enabled mode has mocked contract coverage and optional credentialed smoke support.

---

## Phase 4: User Story 2 - Correlate AI Tasks End To End (Priority: P1)

**Goal**: Covered AI workflows share one canonical run/trace identity across API request, websocket, ARQ job, graph node, tool, LLM call, logs, metrics, invocation records, and eval artifacts.

**Independent Test**: Execute a covered workflow and assert that the same run/trace identifiers appear in logs, spans, AI invocation records, graph span sequence, and eval artifacts.

### Tests First

- [X] T041 [P] [US2] Add runtime tracing config and sampler tests in `backend/tests/unit/test_045_tracing_config.py`
- [X] T042 [P] [US2] Add HTTP-to-graph trace correlation integration tests in `backend/tests/integration/test_045_trace_correlation_http.py`
- [X] T043 [P] [US2] Add websocket trace propagation integration tests in `backend/tests/integration/test_045_trace_correlation_ws.py`
- [X] T044 [P] [US2] Add ARQ enqueue/worker trace propagation integration tests in `backend/tests/integration/test_045_trace_correlation_arq.py`
- [X] T045 [P] [US2] Add LLM invocation trace/run persistence tests in `backend/app/agents/tests/test_045_llm_invocation_trace_ids.py`

### Implementation

- [X] T046 [US2] Complete tracing runtime init, shutdown, W3C propagation, and sampling support in `backend/app/observability/tracing.py`
- [X] T047 [US2] Wire tracing init and shutdown into FastAPI lifespan in `backend/app/main.py`
- [X] T048 [US2] Inject OTel trace id, span id, and run id into structured logs in `backend/app/core/logging.py`
- [X] T049 [US2] Bridge existing `X-Trace-Id` compatibility with canonical OTel context in `backend/app/middleware/trace_id.py`
- [X] T050 [US2] Propagate trace/run context through ARQ enqueue metadata in `backend/app/core/redis.py`
- [X] T051 [US2] Extract and bind trace/run context in ARQ worker startup and job hooks in `backend/app/workers/main.py`
- [X] T052 [US2] Propagate trace/run context through interview websocket messages in `backend/app/api/v1/ws/interview.py`
- [X] T053 [US2] Create LLM child spans and persist trace/run ids in `backend/app/agents/llm_client.py`
- [X] T054 [US2] Ensure mock LLM calls emit testable spans without network calls in `backend/app/agents/llm_client_mock.py`
- [X] T055 [US2] Add trace coverage query helpers for PM/admin consumers in `backend/app/modules/agent_observability/repository.py`
- [X] T056 [US2] Add trace coverage service summary for covered flows in `backend/app/modules/agent_observability/service.py`
- [X] T057 [US2] Update observability README with HTTP/WS/ARQ/LLM propagation guarantees in `backend/app/observability/README.md`
- [X] T058 [US2] Record US2 trace-correlation validation evidence in `docs/evidence/045-llm-ops-eval-workflow/us2-trace-correlation.md`
- [X] T059 [US2] Mark US2 requirement rows in `specs/045-llm-ops-eval-workflow/requirements-status.md`

**Checkpoint**: US2 can be verified without LangSmith by inspecting local spans, logs, AI invocation records, and eval artifacts.

---

## Phase 5: User Story 3 - Enforce Governed External Export (Priority: P1)

**Goal**: External trace/eval export is destination-aware, policy-audited, and supports production full-content LangSmith export while forbidding operational secrets everywhere.

**Independent Test**: Run seeded export audits that allow production full-content LangSmith AI payloads, reject secrets, and redact/block raw AI payloads for non-approved destinations.

### Tests First

- [X] T060 [P] [US3] Add destination policy unit tests in `backend/tests/unit/test_045_export_policy.py`
- [X] T061 [P] [US3] Add export-audit CLI contract tests in `backend/tests/contract/test_045_export_audit_cli.py`
- [X] T062 [P] [US3] Add production full-content LangSmith policy integration tests in `backend/tests/integration/test_045_langsmith_full_content_policy.py`
- [X] T063 [P] [US3] Add operational secret rejection tests in `backend/tests/unit/test_045_export_secret_guard.py`
- [X] T064 [P] [US3] Add generic OTLP redacted/metadata-only export tests in `backend/tests/integration/test_045_otlp_export_policy.py`

### Implementation

- [X] T065 [US3] Implement destination policy decision engine in `backend/app/modules/telemetry_contracts/export_policy.py`
- [X] T066 [US3] Extend redaction helpers to support destination representation levels in `backend/app/modules/telemetry_contracts/redaction.py`
- [X] T067 [US3] Extend retention helpers with destination retention and access metadata in `backend/app/modules/telemetry_contracts/retention.py`
- [X] T068 [US3] Add `export-audit` CLI command and JSON output in `backend/app/eval/cli.py`
- [X] T069 [US3] Require export policy decisions before LangSmith sync in `backend/app/eval/langsmith_sync.py`
- [X] T070 [US3] Add full-content policy enforcement to LangSmith adapter in `backend/app/observability/langsmith.py`
- [X] T071 [US3] Add OTLP generic export representation checks in `backend/app/observability/tracing.py`
- [X] T072 [US3] Add seeded export audit sample with AI payloads and secrets in `specs/045-llm-ops-eval-workflow/fixtures/export-policy-sample.json`
- [X] T073 [US3] Update telemetry contract README with full-content LangSmith policy examples in `backend/app/modules/telemetry_contracts/README.md`
- [X] T074 [US3] Record US3 export-audit validation evidence in `docs/evidence/045-llm-ops-eval-workflow/us3-export-policy.md`
- [X] T075 [US3] Mark US3 requirement rows in `specs/045-llm-ops-eval-workflow/requirements-status.md`

**Checkpoint**: US3 proves the production LangSmith full-content path and the non-approved destination redaction/blocking path independently.

---

## Phase 6: User Story 4 - Compare Experiments With Judge Feedback (Priority: P2)

**Goal**: PMs and AI engineers can compare baseline/candidate variants using deterministic metrics, calibrated judge feedback, cost, latency, and confidence warnings.

**Independent Test**: Run baseline and candidate eval reports through the comparison workflow and verify judge calibration gates, report-only behavior, and comparison output.

### Tests First

- [X] T076 [P] [US4] Add judge rubric schema and calibration unit tests in `backend/tests/unit/test_045_judge_rubrics.py`
- [X] T077 [P] [US4] Add judge-run and judge-calibrate CLI contract tests in `backend/tests/contract/test_045_judge_cli.py`
- [X] T078 [P] [US4] Add experiment-compare CLI contract tests in `backend/tests/contract/test_045_experiment_compare_cli.py`
- [X] T079 [P] [US4] Add baseline/candidate comparison unit tests in `backend/tests/eval/test_045_experiment_compare.py`
- [X] T080 [P] [US4] Add AI Ops compare API contract tests in `backend/tests/contract/test_045_ai_ops_compare_api.py`

### Implementation

- [X] T081 [US4] Implement judge rubric and verdict models in `backend/app/eval/judge.py`
- [X] T082 [US4] Implement judge calibration thresholds and waiver handling in `backend/app/eval/judge.py`
- [X] T083 [US4] Add `judge-run` and `judge-calibrate` CLI commands in `backend/app/eval/cli.py`
- [X] T084 [US4] Add judge verdict rendering to eval report output in `backend/app/eval/report.py`
- [X] T085 [US4] Implement baseline/candidate comparison service in `backend/app/eval/experiment_compare.py`
- [X] T086 [US4] Add `experiment-compare` CLI command in `backend/app/eval/cli.py`
- [X] T087 [US4] Add experiment assignment persistence helpers in `backend/app/modules/telemetry_contracts/llm_ops_repository.py`
- [X] T088 [US4] Expose compare endpoint in `backend/app/modules/admin_console/ai_operations/api.py`
- [X] T089 [US4] Add compare response schemas in `backend/app/modules/admin_console/ai_operations/schemas.py`
- [X] T090 [US4] Add PM dashboard experiment evidence adapters in `backend/app/modules/pm_dashboard/service.py`
- [X] T091 [US4] Add calibration labels README in `specs/045-llm-ops-eval-workflow/calibration/README.md`
- [X] T092 [US4] Record US4 experiment/judge validation evidence in `docs/evidence/045-llm-ops-eval-workflow/us4-experiment-judge.md`
- [X] T093 [US4] Mark US4 requirement rows in `specs/045-llm-ops-eval-workflow/requirements-status.md`

**Checkpoint**: US4 can run comparison locally from two reports and expose the same evidence through AI Ops APIs.

---

## Phase 7: User Story 5 - Promote Production Badcases Into Eval Datasets (Priority: P2)

**Goal**: Governed production/staging badcases can become candidate or report-only eval cases with trace context and human approval before becoming golden.

**Independent Test**: Promote a seeded badcase and verify candidate lifecycle, source trace linkage, policy decision, reviewer metadata, and non-blocking behavior.

### Tests First

- [X] T094 [P] [US5] Add badcase promotion lifecycle unit tests in `backend/tests/unit/test_045_badcase_promotion_lifecycle.py`
- [X] T095 [P] [US5] Add badcase promote CLI contract tests in `backend/tests/contract/test_045_badcase_promotion_cli.py`
- [X] T096 [P] [US5] Add AI Ops badcase promotion API contract tests in `backend/tests/contract/test_045_badcase_promotion_api.py`
- [X] T097 [P] [US5] Add candidate dataset loader tests in `backend/tests/eval/test_045_candidate_dataset_loader.py`

### Implementation

- [X] T098 [US5] Extend badcase promotion schemas with export policy and eval lifecycle fields in `backend/app/modules/badcases/schemas.py`
- [X] T099 [US5] Extend badcase promotion persistence in `backend/app/modules/badcases/repository.py`
- [X] T100 [US5] Implement candidate/report-only promotion rules in `backend/app/modules/badcases/promotion.py`
- [X] T101 [US5] Add badcase promotion CLI flags and JSON output in `backend/app/modules/badcases/cli.py`
- [X] T102 [US5] Expose badcase promotion endpoint in `backend/app/modules/admin_console/ai_operations/api.py`
- [X] T103 [US5] Add candidate/report-only dataset loading in `backend/app/eval/golden_loader.py`
- [X] T104 [US5] Add seeded badcase candidate fixture in `specs/045-llm-ops-eval-workflow/fixtures/badcase-candidate.json`
- [X] T105 [US5] Record US5 badcase promotion validation evidence in `docs/evidence/045-llm-ops-eval-workflow/us5-badcase-promotion.md`
- [X] T106 [US5] Mark US5 requirement rows in `specs/045-llm-ops-eval-workflow/requirements-status.md`

**Checkpoint**: US5 can promote real or seeded badcases without letting candidates block merges before approval.

---

## Phase 8: User Story 6 - Propose Human-Approved Prompt Improvements (Priority: P3)

**Goal**: Failed eval clusters and judge feedback can create prompt/rubric proposals that require comparison evidence and human approval before application.

**Independent Test**: Create, compare, approve, and reject prompt proposals while verifying no command auto-deploys a prompt or auto-refreshes a golden baseline.

### Tests First

- [X] T107 [P] [US6] Add prompt proposal state machine unit tests in `backend/tests/unit/test_045_prompt_proposal_state.py`
- [X] T108 [P] [US6] Add prompt proposal CLI contract tests in `backend/tests/contract/test_045_prompt_proposal_cli.py`
- [X] T109 [P] [US6] Add prompt proposal API contract tests in `backend/tests/contract/test_045_prompt_proposal_api.py`
- [X] T110 [P] [US6] Add no-auto-deploy guardrail tests in `backend/tests/eval/test_045_prompt_proposal_guardrails.py`

### Implementation

- [X] T111 [US6] Implement prompt proposal models and state transitions in `backend/app/eval/prompt_proposals.py`
- [X] T112 [US6] Add prompt proposal persistence helpers in `backend/app/modules/telemetry_contracts/llm_ops_repository.py`
- [X] T113 [US6] Add `prompt-proposal create/compare/approve/reject` CLI commands in `backend/app/eval/cli.py`
- [X] T114 [US6] Add prompt proposal API endpoints in `backend/app/modules/admin_console/ai_operations/api.py`
- [X] T115 [US6] Add prompt proposal schemas in `backend/app/modules/admin_console/ai_operations/schemas.py`
- [X] T116 [US6] Link prompt proposals to experiment comparison reports in `backend/app/eval/experiment_compare.py`
- [X] T117 [US6] Add prompt proposal fixture in `specs/045-llm-ops-eval-workflow/fixtures/prompt-proposal.json`
- [X] T118 [US6] Record US6 prompt proposal validation evidence in `docs/evidence/045-llm-ops-eval-workflow/us6-prompt-proposals.md`
- [X] T119 [US6] Mark US6 requirement rows in `specs/045-llm-ops-eval-workflow/requirements-status.md`

**Checkpoint**: US6 provides a human-approved improvement loop without automatic deployment or baseline refresh.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Validate full REQ-045 behavior, update evidence, and prepare for implementation review.

- [X] T120 [P] Add or update OpenAPI generation notes for AI Ops endpoints in `docs/evidence/045-llm-ops-eval-workflow/openapi-validation.md`
- [X] T121 [P] Add quickstart validation transcript for disabled LangSmith mode in `docs/evidence/045-llm-ops-eval-workflow/quickstart-langsmith-disabled.md`
- [X] T122 [P] Add quickstart validation transcript for full-content LangSmith policy audit in `docs/evidence/045-llm-ops-eval-workflow/quickstart-full-content-policy.md`
- [X] T123 [P] Add trace coverage summary for five covered AI surfaces in `docs/evidence/045-llm-ops-eval-workflow/trace-coverage-summary.md`
- [X] T124 Update REQ-045 status table after validation in `specs/045-llm-ops-eval-workflow/requirements-status.md`
- [X] T125 Update specs index status after validation in `specs/README.md`
- [X] T126 Run backend focused tests and record results in `docs/evidence/045-llm-ops-eval-workflow/backend-focused-tests.md`
- [X] T127 Run full backend test suite and record results in `docs/evidence/045-llm-ops-eval-workflow/backend-full-tests.md`
- [X] T128 Run frontend typecheck/unit tests if AI Ops UI changed and record results in `docs/evidence/045-llm-ops-eval-workflow/frontend-validation.md`
- [X] T129 Run E2E only if admin/PM visible flows changed and record results in `docs/evidence/045-llm-ops-eval-workflow/e2e-validation.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 Trace-Linked Eval Gate (Phase 3)**: Depends on Foundational. This is the MVP.
- **US2 Trace Correlation (Phase 4)**: Depends on Foundational; can run after or alongside US1 once shared schemas exist.
- **US3 Governed Export (Phase 5)**: Depends on Foundational; LangSmith full-content sync in US1 becomes production-ready after US3.
- **US4 Experiment + Judge (Phase 6)**: Depends on US1 and Foundational; benefits from US2/US3 for full trace/export evidence.
- **US5 Badcase Promotion (Phase 7)**: Depends on US1 and US3; can run before US4 if judge feedback is not required.
- **US6 Prompt Proposals (Phase 8)**: Depends on US4 and usually US5.
- **Polish (Phase 9)**: Depends on all desired user stories for the release slice.

### User Story Dependencies

- **US1**: Independent after Foundational; MVP scope.
- **US2**: Independent after Foundational; strengthens all later story evidence.
- **US3**: Independent after Foundational; required for production full-content LangSmith export.
- **US4**: Requires US1 reports; can use US2/US3 evidence when available.
- **US5**: Requires US1 datasets and US3 export decisions.
- **US6**: Requires US4 comparison evidence and human approval state.

### Within Each User Story

- Write tests first and confirm they fail for the expected missing capability.
- Add or extend schemas before services.
- Add services before CLI/API endpoints.
- Add integration evidence before marking requirement rows `done`.

## Parallel Opportunities

- Setup documentation and fixture tasks T002-T008 can run in parallel.
- Foundational tests T009-T012 can run in parallel.
- US1 tests T025-T029 can run in parallel before US1 implementation.
- US2 tests T041-T045 can run in parallel before US2 implementation.
- US3 tests T060-T064 can run in parallel before US3 implementation.
- US4 tests T076-T080 can run in parallel before US4 implementation.
- US5 tests T094-T097 can run in parallel before US5 implementation.
- US6 tests T107-T110 can run in parallel before US6 implementation.
- Polish evidence tasks T120-T123 can run in parallel after the relevant validations exist.

## Parallel Examples

### US1

```bash
Task: "T025 Add eval report schema contract tests in backend/tests/contract/test_045_eval_report_schema.py"
Task: "T026 Add eval run CLI contract tests for --sync-langsmith modes in backend/tests/contract/test_045_eval_run_cli.py"
Task: "T027 Add mocked LangSmith sync tests for disabled, synced, failed, and require modes in backend/tests/eval/test_045_langsmith_sync.py"
```

### US2

```bash
Task: "T042 Add HTTP-to-graph trace correlation integration tests in backend/tests/integration/test_045_trace_correlation_http.py"
Task: "T043 Add websocket trace propagation integration tests in backend/tests/integration/test_045_trace_correlation_ws.py"
Task: "T044 Add ARQ enqueue/worker trace propagation integration tests in backend/tests/integration/test_045_trace_correlation_arq.py"
```

### US3

```bash
Task: "T060 Add destination policy unit tests in backend/tests/unit/test_045_export_policy.py"
Task: "T062 Add production full-content LangSmith policy integration tests in backend/tests/integration/test_045_langsmith_full_content_policy.py"
Task: "T064 Add generic OTLP redacted/metadata-only export tests in backend/tests/integration/test_045_otlp_export_policy.py"
```

### US4

```bash
Task: "T076 Add judge rubric schema and calibration unit tests in backend/tests/unit/test_045_judge_rubrics.py"
Task: "T078 Add experiment-compare CLI contract tests in backend/tests/contract/test_045_experiment_compare_cli.py"
Task: "T080 Add AI Ops compare API contract tests in backend/tests/contract/test_045_ai_ops_compare_api.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundational tasks.
3. Complete Phase 3 US1 Trace-Linked Eval Gate.
4. Validate local LangSmith-disabled eval and mocked LangSmith-enabled sync.

### Production-Ready P1

1. Add Phase 4 US2 to make trace/run correlation trustworthy.
2. Add Phase 5 US3 to make production full-content LangSmith export governed.
3. Re-run quickstart scenarios 1 through 4.

### Full REQ-045 Loop

1. Add Phase 6 US4 experiment comparison and judge calibration.
2. Add Phase 7 US5 badcase promotion.
3. Add Phase 8 US6 prompt/rubric proposals.
4. Complete Phase 9 evidence and status updates.

## Notes

- Keep local eval artifacts canonical even when LangSmith sync succeeds.
- Keep operational secrets out of every export path, including production full-content LangSmith export.
- Do not mark requirement rows `done` until implementation and verification evidence are both linked.
- Do not implement automatic prompt deployment or automatic golden baseline refresh in REQ-045.
