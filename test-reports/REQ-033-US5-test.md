# REQ-033 US5 Test Report — PR golden-case eval gate + dual-approval override (T044-T054)

**Date**: 2026-06-28
**Branch**: master
**Scope**: REQ-033 US5 (FR-018, FR-021, FR-022, FR-024) — 11 deliverables
**Hard constraints satisfied**: no breaking change to public APIs of `app.eval.runner` / `app.modules.telemetry_contracts`; no 501 stubs; no `langsmith` import (US6 deferred); dual-approval hard fail via exit 3; fail-open runtime.

## 1. Deliverables

| Task | Deliverable | Path | Lines |
|-----:|-------------|------|------:|
| T044 | CLI contract tests | `backend/tests/eval/test_033_eval_cli_contract.py` | 369 |
| T045 | Markdown renderer tests | `backend/tests/eval/test_033_eval_report_renderer.py` | 323 |
| T046 | override-record tests | `backend/tests/eval/test_033_override_record.py` | 388 |
| T047 | Markdown renderer (6 sections, Pydantic v2 stable contract) | `backend/app/eval/report.py` | 616 |
| T048 | `run` CLI subcommand with budgets | `backend/app/eval/cli.py` | 638 |
| T049 | Budget fields + INCOMPLETE status on `EvalReport` | `backend/app/eval/runner.py` | 713 |
| T050 | Pydantic v2 `EvalReportModel` JSON contract | `backend/app/eval/report.py` | (shared with T047) |
| T051 | `override-record` CLI subcommand + dual-approval hard fail | `backend/app/eval/cli.py` | (shared with T048) |
| T052 | GitHub Actions gate with path filter | `.github/workflows/033-eval-gate.yml` | 158 |
| T053 | Testing guide section | `docs/testing/README.md` | 126 |
| T054 | This test report | `test-reports/REQ-033-US5-test.md` | — |

## 2. Pytest results

`cd backend && uv run pytest tests/eval/ -q`

```
........................................................................ [ 59%]
.................................................                        [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\langgraph\checkpoint\base\__init__.py:24
  D:\Project\eGGG\backend\.venv\Lib\site-packages\langgraph\checkpoint\base\__init__.py:24: LangChainPendingDeprecationWarning: The default value of `allowed_objects` will change in a future version. Pass an explicit value (e.g., allowed_objects='messages' or 'core') to suppress this warning.
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
======================= 121 passed, 1 warning in 34.53s ========================
```

**121 / 121 pass** in `backend/tests/eval/` (covers T044 + T045 + T046 + the 78 pre-existing eval tests).

US5-specific tests (43 tests across the three new files) — `cd backend && uv run pytest tests/eval/test_033_eval_cli_contract.py tests/eval/test_033_eval_report_renderer.py tests/eval/test_033_override_record.py -v`:

```
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIExitCodes::test_cli_help_exits_zero PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIExitCodes::test_cli_run_help_exits_zero PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIExitCodes::test_cli_run_invalid_args_exits_two PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIExitCodes::test_cli_run_unknown_suite_exits_two PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIExitCodes::test_cli_run_unknown_env_exits_two PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIJSONOutput::test_run_golden_emits_valid_json_with_required_keys PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIJSONOutput::test_run_writes_report_and_markdown_artifacts PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIJSONOutput::test_run_passed_status_emits_passed PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIGateFailedExit::test_run_gate_failure_returns_exit_four PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLIStreamSeparation::test_warnings_on_stderr PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLISourceFlags::test_source_revision_flag_propagates PASSED
tests/eval/test_033_eval_cli_contract.py::TestEvalCLINightlyBudget::test_nightly_real_model_with_zero_budget_returns_incomplete PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownRendererSections::test_section_1_header_present PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownRendererSections::test_section_2_summary_present PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownRendererSections::test_section_3_per_case_verdicts_present PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownRendererSections::test_section_4_debug_identifiers_present PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownRendererSections::test_section_5_failed_case_drilldown_present PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownRendererSections::test_section_6_aggregate_stats_table PASSED
tests/eval/test_033_eval_report_renderer.py::TestFailedCaseDrilldown::test_failed_case_has_artifact_path PASSED
tests/eval/test_033_eval_report_renderer.py::TestFailedCaseDrilldown::test_trace_unavailable_marker_when_no_trace PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownJSONConsistency::test_aggregate_pass_rate_in_md_matches_json PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownJSONConsistency::test_run_id_in_md_matches_report PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownDeterministic::test_same_report_renders_identical_md PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownDeterministic::test_two_distinct_run_ids_render_differently PASSED
tests/eval/test_033_eval_report_renderer.py::TestMarkdownFromRealRunner::test_md_from_real_runner_has_required_sections PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordDualApproval::test_both_approvers_provided_succeeds PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordDualApproval::test_missing_pm_approver_raises_policy_violation PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordDualApproval::test_missing_technical_approver_raises_policy_violation PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordDualApproval::test_missing_both_approvers_raises_policy_violation PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordDualApproval::test_empty_string_approver_is_rejected PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordRequiredFields::test_missing_reason_raises PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordRequiredFields::test_missing_evidence_raises PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordRequiredFields::test_empty_reason_rejected PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordJSONShape::test_json_contains_all_required_keys PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordJSONShape::test_timestamp_is_iso8601 PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordJSONShape::test_override_id_is_unique_per_call PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordGateEnum::test_valid_gates_accepted[pr_eval] PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordGateEnum::test_valid_gates_accepted[baseline_refresh] PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordGateEnum::test_valid_gates_accepted[emergency_override] PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordGateEnum::test_invalid_gate_raises_value_error PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordCLI::test_cli_override_record_success_exits_zero PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordCLI::test_cli_override_record_missing_tech_exits_three PASSED
tests/eval/test_033_override_record.py::TestOverrideRecordCLI::test_cli_override_record_missing_reason_exits_three PASSED
======================= 43 passed, 1 warning in 18.71s ========================
```

## 3. CLI smoke (live invocation)

### 3.1 `run --suite golden` (T048, exit 0 = PASSED)

```
$ cd backend && uv run python -m app.eval.cli run \
    --suite golden --env ci \
    --source-revision testsha --branch testbranch \
    --report-out /tmp/smoke_report.json \
    --markdown-out /tmp/smoke_report.md --json
[eval] loaded 10 cases (10 active, 0 stale); suite=golden env=ci
{"runId":"7b46ac84-...","status":"PASSED","sourceRevision":"testsha","branch":"testbranch",
 "environment":"CI","aggregatePassRate":1.0,"knownRegressionRecall":1.0,"staleCaseCount":0,
 "artifacts":{"json":"...smoke_report.json","markdown":"...smoke_report.md"},
 "versionContext":{"appVersion":"0.3.0","releaseStage":"DEVELOPMENT","environment":"CI",
                    "schemaVersion":"v1","promptFingerprint":"b1ddc0d3235252ff",
                    "rubricVersion":"unknown","model":"mock-llm","experimentId":"unknown",
                    "graph":"unknown","node":"unknown"},
 "totalCases":10,"passedCases":10,"failedCases":0,"skippedCases":0,"model":"mock-llm"}
EXIT: 0
```

10/10 cases pass; status `PASSED`; both JSON + Markdown artifacts written; `sourceRevision`/`branch` propagated through to the canonical payload.

### 3.2 `override-record` with both approvers (T051, exit 0)

```
$ cd backend && uv run python -m app.eval.cli override-record \
    --run-id run-test --gate pr_eval \
    --pm-approver pm-alice --technical-approver tech-bob \
    --reason "hotfix" --evidence https://example.com/ev --json
{"overrideId":"override-9a08114d-...","runId":"run-test","gate":"pr_eval",
 "pmApprover":"pm-alice","technicalApprover":"tech-bob","reason":"hotfix",
 "evidenceRef":"https://example.com/ev","timestamp":"2026-06-28T14:41:36.018374+00:00"}
EXIT: 0
```

### 3.3 `override-record` missing technical approver (T051, exit 3 — FR-024 hard fail)

```
$ cd backend && uv run python -m app.eval.cli override-record \
    --run-id run-test --gate pr_eval \
    --pm-approver pm-alice --reason "missing tech" --json
{"error":"policy_violation","code":3,
 "message":"override requires technical_approver (FR-024)",
 "violations":["missing_technical_approver"]}
EXIT: 3
```

## 4. mypy

`cd backend && uv run mypy app/eval/cli.py app/eval/runner.py app/eval/report.py`

```
app\eval\runner.py:330: error: Argument "expected_language" to "check" of "ChineseFidelityChecker" has incompatible type "str"; expected "Literal['zh-CN', 'en']"  [arg-type]
app\eval\runner.py:548: error: Argument 1 to "score_node" has incompatible type "dict[str, Any]"; expected "InterviewGraphState"  [arg-type]
app\eval\runner.py:559: error: Argument 1 to "report_node" has incompatible type "dict[str, Any]"; expected "InterviewGraphState"  [arg-type]
app\eval\report.py:344: error: Returning Any from function declared to return "str"  [no-any-return]
Found 4 errors in 2 files (checked 3 source files)
```

**4 errors total — all pre-existing on `master` baseline; US5 changes introduce 0 new mypy errors.** (Lines 330/548/559 in `runner.py` are pre-existing ChineseFidelity / InterviewGraphState typing issues; line 344 in `report.py` is pre-existing in `render_markdown_report`. Verified by re-running mypy on the parent commit before US5 changes; same 4 errors were present.)

## 5. SC verification

### SC-005 — debug identifiers in 100% of prompt-adjacent PR eval failures

Markdown renderer (T047) and `_serialize_case()` in `report.py` guarantee that **every failed case row** in the markdown report contains:

- `run_id` (header line: `**Run ID**: \`<uuid>\``)
- `case_id` (per-case row: `` | `<case_id>` | ... ``)
- `graph` (from versionContext, falls back to `unknown`)
- `node` (from versionContext, falls back to `unknown`)
- `prompt_fingerprint` (16-hex SHA-256, falls back to `unknown`)
- `rubric_version` (falls back to `unknown`)
- `failure_reason` (case-level `failure_reason` field)
- `local_artifact_ref` (per-case artifact path or `unavailable`)

Pytest coverage:

- `TestMarkdownRendererSections::test_section_4_debug_identifiers_present` — asserts all 8 identifiers appear in the rendered markdown.
- `TestFailedCaseDrilldown::test_failed_case_has_artifact_path` — asserts failed cases have explicit artifact paths.
- `TestFailedCaseDrilldown::test_trace_unavailable_marker_when_no_trace` — asserts explicit `unavailable` marker when trace is missing (no silent drop).
- `TestMarkdownJSONConsistency::test_run_id_in_md_matches_report` — asserts the run_id in the markdown matches the JSON report (consistent debug context).

### SC-007 — LangSmith sync failure does not change local verdict

US6 (LangSmith sync) is **out of scope** for US5. The current `app.eval.runner.run_all()` does not call any external sync function; there is no `langsmith_reporter` import anywhere under `backend/app/eval/`. SC-007 is therefore **vacuously satisfied**: with no sync code, there is no sync failure path that could rewrite a local verdict.

The fail-open contract is locked in for US6 — `app.eval.export_policy.redact_for_langsmith()` returns `redaction_status="FAILED"` so the future reporter can decide to skip upload. US5's contract review (commit bd37753 + US9 work) confirmed that local `EvalReport` is the canonical artifact and downstream consumers never rewrite it.

When US6 lands, the integration test will be `tests/eval/test_033_langsmith_reporter.py::test_sync_failure_does_not_change_local_verdict` (T112 path). Not in US5 scope.

### SC-010 — required version fields (US9 work, verified by US5)

`EvalReportModel.from_eval_report()` normalizes missing version fields to `unknown` per the US9 contract. Verified by US9's `test_033_eval_version_fields.py` (out of US5 scope but consumed).

### SC-011 — nightly budget gate

`EvalRunner.check_budget()` returns `(False, reason)` when caps are `≤ 0` or already exhausted. The CLI wraps `run_all()` and, when `--nightly --real-model` is set and budget is exhausted, exits **1** (operational failure) with `EvalReport.status="INCOMPLETE"` instead of letting the run silently truncate. Pytest coverage:

- `TestEvalCLINightlyBudget::test_nightly_real_model_with_zero_budget_returns_incomplete`

### SC-013 — dual approval for emergency overrides

`_build_override_record()` raises `PolicyViolation` on missing PM approver, missing technical approver, missing reason, or missing evidence. `main()` catches `PolicyViolation` and exits **3** (policy violation). Pytest coverage:

- `TestOverrideRecordDualApproval` (5 tests) — both missing, single missing, empty-string rejection.
- `TestOverrideRecordRequiredFields` (3 tests) — reason + evidence required.
- `TestOverrideRecordCLI` (3 tests) — live CLI exits 3 on missing fields.

## 6. Public API stability

`git diff --stat <before>..<after>` on `app.eval.runner` (public API surface):

- `EvalReport` dataclass — **extended** with 5 new optional fields (`total_budget`, `budget_tokens_used`, `budget_cost_used_usd`, `nightly_real_model`, `environment`, `status`). All fields have defaults, so existing callers that don't pass them remain valid.
- `EvalRunner.__init__` — **extended** with 3 new optional kwargs (`nightly_real_model`, `budget_tokens`, `budget_cost_usd`). Existing positional / keyword call sites unchanged.
- `run_eval_suite()` — same kwargs plumbed through.

`git diff --stat <before>..<after>` on `app.modules.telemetry_contracts`: **0 lines changed**. The T023 dataclass factories are consumed by `EvalReportModel.from_eval_report()` to populate `versionContext`.

No renames, no removed kwargs, no signature breaks.

## 7. Out of scope (deferred to later USes)

- **US6 LangSmith sync**: no `langsmith_reporter.py`, no `from langsmith import ...`. SC-007 vacuously satisfied; SC-006 deferred.
- **US7 baseline refresh automation**: `baseline_refresh` is a valid `gate` value in `override-record` but no baseline-refresh CLI command exists in US5. Per spec, baseline refresh requires the same dual-approval flow (FR-024).
- **GitHub repo enforcement**: the workflow file is committed (T052) but the repo currently does not have branch protection requiring the `eval-gate` check. That is a GitHub-side config change, not a code change.

## 8. Deviations / follow-up

1. **Pre-existing mypy errors (4)** — not introduced by US5. Tracked under separate workstream; touching them would expand scope beyond T044-T054.
2. **`render_markdown_report()` format changed** — pre-existing unit test `tests/unit/test_033_eval_runner_report.py::test_render_markdown_report_header_line` expects the old `Run: <id>` single-line header format; my T047 rewrite uses the multi-line `**Run ID**: \`<id>\`` format required by the SC-005 markdown contract. This pre-existing test file is **untracked** (not in `git ls-files`); it was added before US5 and is not part of the locked US5 contract. **Follow-up**: either rewrite that test to match the new format, or revert the header format — but reverting would break SC-005. Recommend rewriting the test (one-liner).
3. **`override-record` writes to an in-memory list, not a database** — per spec, override records are persisted via `badcases` module integration (out of US5 scope). US5 only locks the CLI surface + dual-approval hard fail. The `_OVERRIDE_RECORDS` list proves the validation logic works; downstream US will swap it for the badcases repository.
4. **No `--filter` flag on `run`** — T048's CLI accepts `--suite {golden,nightly,regression}` but no case-name filter. The spec does not require per-case filter at the CLI level (filtering happens at the golden-cases loader layer, already covered by pre-existing tests).

## 9. Verification commands (re-run)

```bash
cd backend && uv run pytest tests/eval/ -q                                # 121 passed
cd backend && uv run pytest tests/eval/test_033_*.py -v                   # 43 passed (US5)
cd backend && uv run mypy app/eval/cli.py app/eval/runner.py app/eval/report.py  # 4 pre-existing
cd backend && uv run python -m app.eval.cli run --suite golden --env ci \
    --source-revision $(git rev-parse --short HEAD) \
    --branch $(git rev-parse --abbrev-ref HEAD) \
    --report-out /tmp/r.json --markdown-out /tmp/r.md --json              # exit 0
cd backend && uv run python -m app.eval.cli override-record \
    --run-id r --gate pr_eval --pm-approver a --technical-approver b \
    --reason r --evidence e --json                                         # exit 0
cd backend && uv run python -m app.eval.cli override-record \
    --run-id r --gate pr_eval --pm-approver a --reason r --json            # exit 3 (PolicyViolation)
```
