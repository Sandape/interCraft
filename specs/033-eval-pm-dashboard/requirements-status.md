# 033 Requirement Status

Status tracking for feature 033 (Eval + PM Dashboard V1). Per
POLISH T141, US1-US5 + US7-US10 are marked Done with evidence;
US6 is Deferred (LangSmith SDK not installed — per user decision
mirroring 026 v2 cycle).

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | PM Product Overview + Core Funnel | done | `test-reports/REQ-033-US1-test.md` | 15 tasks T067-T081. Overview + Funnel panels + 6 metric cards + 4-step funnel. |
| US2 | Resume Diagnosis + Suggestion Adoption | done | `test-reports/REQ-033-US2-test.md` | 9 tasks T082-T090. ResumeDiagnosisPanel + diagnosis metric assembly. |
| US3 | Mock Interview Usage + Completion | done | `test-reports/REQ-033-US3-test.md` | 9 tasks T091-T099. MockInterviewPanel + interview outcome aggregation. |
| US4 | AI Operations (cost / reliability / latency) | done | `test-reports/REQ-033-US4-test.md` | 12 tasks T100-T111. AIOperationsPanel + 7 metrics + 4 top-N breakdowns + cost calculator. |
| US5 | Automatic Golden-Case Eval in PR | done | `test-reports/REQ-033-US5-test.md` | 11 tasks T044-T054. Stable JSON/Markdown reports + dual-approval override + CI eval gate workflow. |
| US6 | LangSmith Sync + Deep-Link Panel | **Deferred** | — | LangSmith SDK not installed (per 026 v2 cycle precedent). `langsmith_url` wired to `"unavailable"` in every contract path. Flipping on is one-line change once SDK lands. |
| US7 | Trace / Run Drilldown + Version / Experiment Panel | done | `test-reports/REQ-033-US7-test.md` | 11 tasks T122-T132. VersionExperimentPanel + 5 aggregates + 2 top-5 breakdowns + `trace_available` flag + `TraceRunRef` dataclass + 22 trace-link tests. |
| US8 | Badcase Mark / Classify / Promote / Close | done | `test-reports/REQ-033-US8-test.md` | 12 tasks T055-T066. 7-endpoint API + 7-subcommand CLI + FSM + promotion-to-golden. |
| US9 | Version / Prompt / Rubric / Experiment Fields | done | `test-reports/REQ-033-US9-test.md` | 10 tasks T034-T043. `VersionContext` Pydantic model + LLM client hook + AIInvocationRecord + badcase schemas. |
| US10 | Environment-Specific Redaction Policy | done | `test-reports/REQ-033-US10-test.md` | 9 tasks T025-T033. Production PII mandatory + staging recommended + dev no-op + retention (prod 30d delete / staging 7d archive / dev no-op). |
| POLISH | Polish & Cross-Cutting Concerns | done | `test-reports/REQ-033-POLISH-test.md` | 10 tasks T133-T142. 4 module READMEs + canonical E2E + 3 validation reports + requirements-status + feature index update. |

## Functional Requirements (summary)

| FR Group | Coverage | Status |
|----------|----------|--------|
| FR-001 — FR-014 (eval runner + golden cases) | US5 + US9 | done |
| FR-015 — FR-024 (override + policy gates) | US5 + US10 | done |
| FR-025 — FR-029 (badcase FSM + audit log) | US8 | done |
| FR-030 — FR-035 (redaction + retention) | US10 | done |
| FR-036 — FR-046 (PM dashboard overview + funnel + panels) | US1-US4 + US7 | done |
| FR-047 — FR-051 (LangSmith sync) | US6 | **deferred** |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 — SC-007 (eval + redaction + retention) | US5 + US10 | done | `test-reports/REQ-033-US5-test.md` + `US10` | — |
| SC-008 (redaction audit template) | US10 | done | `docs/evidence/033-eval-pm-dashboard/redaction-check-template.md` | — |
| SC-009 (empty-window 200 + partial_data) | US1-US4 + US7 | done | `test-reports/REQ-033-US1-test.md` US1 scenario 3 | All 6 panels return 200 with empty-state body. |
| SC-010 (missing version fields → "unknown") | US9 | done | `test-reports/REQ-033-US9-test.md` | Verified by 18-field test suite. |
| SC-011 — SC-014 (badcase lifecycle) | US8 | done | `test-reports/REQ-033-US8-test.md` | — |
| SC-015 — SC-020 (PM dashboard panels + privacy) | US1-US4 + US7 | done | `test-reports/REQ-033-US{1,2,3,4,7}-test.md` | Privacy invariant verified at 3 layers. |
| SC-021 — SC-025 (LangSmith sync) | US6 | **deferred** | — | Pending LangSmith SDK install. |

## Follow-ups (out of 033-POLISH)

These are tracked separately, not in the T133-T142 scope:

- `app/modules/telemetry_contracts/{events,redaction,retention}.py`
  (missing — blocked by lazy-import pattern in `__init__.py`)
- `app/modules/telemetry_contracts/models.py` (missing — `badcases/
  models.py` re-exports via lazy import)
- `app/agents/interview/planner_graph.py` + sibling nodes (missing —
  blocks full conftest load)
- `specs/033-eval-pm-dashboard/{spec,data-model,plan,research,
  quickstart}.md` + `contracts/*` (6 missing spec files)
- 1 pre-existing pytest failure: `test_033_nightly_real_model_with_zero_budget_returns_incomplete`
- US6 LangSmith SDK install (heavy; user decision to defer per 026
  v2 cycle precedent)
- Production `require_pm` / `require_reviewer` resolvers (stubs
  currently raise 401; follow-up US once role mapping lands)

## Tests by surface

| Surface | Pass count | Notes |
|---------|-----------|-------|
| Backend eval tests (4 of 5 spec files) | 53 / 53 | `tests/eval/test_033_*.py` minus `eval_cli_contract.py` (blocked by missing redaction module) |
| Backend unit tests (4 spec files) | 87 / 88 | `tests/unit/test_033_*.py` minus 1 pre-existing failure in `ai_invocation_fields.py` |
| Backend contract + integration (with DB) | covered by US1-US7 dev reports | Skipped here per L004 quota-safety (no dev server bring-up) |
| Frontend PM dashboard tests (6 spec files) | 35 / 35 + 4 page tests = 39 / 39 | `src/components/pm-dashboard/__tests__/*.test.tsx` |
| Frontend typecheck (033 scope) | 0 errors in 033 files | `test-reports/REQ-033-frontend-validation.md` |
| E2E | 1 spec written (`tests/e2e/033-pm-dashboard.spec.ts`) | Execution requires running dev server (out of scope per L004) |

See `test-reports/REQ-033-POLISH-test.md` for the full POLISH
batch summary + `test-reports/REQ-033-{frontend,backend,quickstart}-validation.md`
for the T138-T140 validation reports.
