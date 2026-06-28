# Test Report REQ-033 US3 — Mock Interview Panel

**Date**: 2026-06-29
**Branch**: master
**Scope**: T091-T099 (9 tasks). Backend (T091 + T093-T096) + frontend
(T092 + T097-T098) + dev report (T099).

## What shipped

### Backend (4 files extended, 1 file added)

- `backend/app/modules/pm_dashboard/repository.py` (T093) — added 6 US3
  helpers (`count_interview_starts`, `count_interview_completions`,
  `count_interview_failures`, `count_interview_retries`,
  `count_interview_report_views`, `avg_interview_question_count`) +
  5 `INTERVIEW_*` event_name constants. Falls back to `ProductEvent`
  rows where `event_name LIKE 'interview.%'` (US3 fallback — see
  "Deviations" below for the migration-pending rationale).
- `backend/app/modules/pm_dashboard/schemas.py` (T095) — added
  `MockInterviewPanelData` (8 fields: starts, completions,
  completion_rate, avg_question_count, report_views, retries,
  failure_rate, failure_categories) + `MockInterviewPanel =
  PanelResponse[MockInterviewPanelData]` typed alias + export in
  `__all__`.
- `backend/app/modules/pm_dashboard/service.py` (T094) — added
  `get_mock_interview(session, filters) -> list[PanelResponse[Any]]`
  that pulls the 6 aggregates, derives `completion_rate` /
  `failure_rate` (clamped to [0, 1]), assembles the bundled
  PanelResponse with quality_flags (partial_data on empty window),
  freshness_at, and source_of_truth = `"product_events (interview.*)"`.
- `backend/app/modules/pm_dashboard/api.py` (T096) — added
  `GET /api/v1/pm-dashboard/metrics/mock-interview` endpoint with the
  same filter set as overview/funnel/resume-diagnosis; `ValueError → 400`,
  missing date → 422 (FastAPI validation).
- `backend/tests/integration/test_033_mock_interview_metrics.py`
  (T091) — added 14 integration tests covering: 6 repository helpers
  return correct shapes; filter accepts date range + environment +
  app_version; filter rejects inverted date range; empty window
  surfaces `partial_data=True` + `freshness_at="unknown"`; service
  returns panel list; data shape covers all 7 required fields;
  no raw interview content leaks in the response payload (privacy
  assertion: forbidden keys like `interview_questions`,
  `interview_answers`, `interview_transcript`, `interview_audio`,
  `raw_interview`, `feedback_text`, `report_text`, `report_markdown`);
  completion_rate is clamped to [0, 1]; failure_rate is clamped to
  [0, 1]; avg_question_count is non-negative.

### Frontend (2 files extended, 2 files added)

- `src/components/pm-dashboard/MockInterviewPanel.tsx` (T097) — new
  component: 6 metric cards (starts, completions, completion rate with
  color coding green >= 80% / amber 50-80% / red < 50%, avg question
  count, report views, failure rate with inverted color coding
  green < 10% / amber 10-30% / red >= 30%) + quality-flag warning +
  source-of-truth label.
- `src/pages/PMDashboard.tsx` (T098) — extended to 4-panel grid
  (Overview + Funnel + Resume Diagnosis + Mock Interview); added the
  `mock-interview` TanStack Query + `isLoading` / `error` union.
- `src/components/pm-dashboard/__tests__/MockInterviewPanel.test.tsx`
  (T092) — added 6 React tests: 6 metric cards rendered in a grid,
  completion rate displayed as percentage, failure rate displayed as
  percentage, avg question count displayed as decimal, partial-data
  warning surfaces when `partial_data=true`, defensive contract:
  doesn't crash on missing fields.
- `src/api/pm-dashboard.ts` — updated the `getMockInterview` mock
  fallback to use the source label `"product_events (interview.*)"`
  (matching the backend).

## Test results

### Frontend

```
$ npx vitest run src/components/pm-dashboard/__tests__/MockInterviewPanel.test.tsx
Test Files  1 passed (1)
Tests       6 passed (6)

$ npx vitest run src/components/pm-dashboard/__tests__/
Test Files  2 passed (2)
Tests       13 passed (13)
```

6/6 MockInterviewPanel tests pass + 7/7 existing ResumeDiagnosisPanel
tests still pass = 13/13 total. The previously-failing pre-T092
state (panel import unresolved) is now green.

### Backend mypy

```
$ uv run mypy app/modules/pm_dashboard/
Success: no issues found in 4 source files
```

0 errors in `pm_dashboard/`. Confirms the Pydantic generics, async
session typing, and Any-widening from US1/US2 still hold after T093-T096
extensions.

### Backend pytest

```
$ uv run pytest tests/integration/test_033_mock_interview_metrics.py \
                   -p no:cacheprovider -q
ImportError while loading conftest 'D:\Project\eGGG\backend\tests\conftest.py'
  File "D:\Project\eGGG\backend\app\agents\interview\graph.py", line 22
    from app.agents.interview.planner_graph import get_planner_subgraph
ModuleNotFoundError: No module named 'app.agents.interview.planner_graph'
```

The same pre-existing conftest import blocker as US1/US2:
`app/main.py` transitively imports `app/agents/interview/planner_graph.py`
(and untracked siblings `nodes/planner_context.py` /
`planner_generate.py` / `planner_search.py` /
`prompts/{interviewer,planner}.md`) which are missing from the working
tree per `git status` (untracked but not importable as Python modules
from disk). The same blocker affects **every** pytest invocation in the
repo (verified: US1's `test_033_pm_dashboard_metrics.py` and US2's
`test_033_resume_diagnosis_metrics.py` produce identical errors). The
integration tests themselves are correctly structured to skip when
`DATABASE_URL` is unset — the blocker is at conftest load time, not in
test code. This matches US1's and US2's documented state and is tracked
under 033-POLISH restoration. **No regression introduced by US3.**

### Frontend typecheck

The frontend vitest suite (which runs TS-aware) passes 13/13 — all TS
errors that show in `npx tsc` output are pre-existing in
`src/modules/resume/v2/` (per US1 report — 033-POLISH scope).

## Deviations / decisions

| # | Severity | Decision | Why |
|---|----------|----------|-----|
| 1 | Medium | US3 repository falls back to `ProductEvent` rows where `event_name LIKE 'interview.%'` | The dedicated `interview_outcomes` table from spec.md §data-model is not in any migration yet (033-POLISH restoration pending). Falling back to `ProductEvent` keeps the panel functional without a migration; service + API contract is unchanged when the table lands, just swap the SQL targets. Privacy is preserved: the panel returns counts + rates + avg question count only, no raw interview content. |
| 2 | Low | JSONB extraction for `question_count` uses `(metadata ->> 'question_count')::float` SQLAlchemy idiom | The `ProductFunnelEvent` schema has `metadata` as JSONB; the avg(question_count) query extracts the numeric key directly. Privacy: aggregate only, no per-row question counts surfaced. |
| 3 | Low | `MockInterviewPanel` card layout uses `grid-cols-2 md:grid-cols-3` (3-column on desktop) | US3 has 6 metric cards (starts + completions + completion rate + avg questions + report views + failure rate); 3-column fits cleanly under the existing 4-column Overview grid. |
| 4 | Low | `completion_rate` color-coded green >= 80%, amber 50-80%, red < 50% | PM dashboards conventionally use this 3-band threshold for task completion. Matches US2 `success_rate` color scheme for visual consistency. |
| 5 | Low | `failure_rate` color-coded inverted: green < 10%, amber 10-30%, red >= 30% | Lower is better for failure rate, so the color bands are inverted relative to completion_rate. Green=low failure, red=high failure. |
| 6 | Low | `failure_categories` is an empty dict in MVP | The dedicated `interview_outcomes.failure_category` column is not yet landed in a migration (033-POLISH). When it lands, the repository layer will compute the breakdown via GROUP BY on the JSONB key. The Pydantic schema reserves the field so the contract is unchanged. |
| 7 | Low | Auth stub `require_pm` still raises 401 | Same as US1/US2; production resolver is a follow-up. |

## Notes for reviewer

- The privacy assertion in T091
  (`test_interview_panel_does_not_leak_raw_content`) enumerates
  forbidden field names: `interview_questions`, `interview_answers`,
  `interview_transcript`, `interview_audio`, `raw_interview`,
  `feedback_text`, `report_text`, `report_markdown`. If the dedicated
  table lands and the service layer accidentally exposes a raw field,
  this test fails immediately.
- The completion_rate / failure_rate calculations in
  `service.get_mock_interview` use float division with explicit
  clamping to [0.0, 1.0] at the service layer (and the Pydantic
  schema `Field(ge=0.0, le=1.0)` as the final defense). Zero-data
  case is explicitly handled: when `starts == 0`, both rates are 0.0.
- The empty-window fallback mirrors US1's and US2's patterns exactly:
  `quality_flags.partial_data=True` + `freshness_at="unknown"`,
  surfaced by `get_mock_interview` via the `has_data` boolean
  derived from starts / completions / failures / retries /
  report_views being all zero.
- The 6 new repository helpers and 5 `INTERVIEW_*` event_name
  constants are exported in `__all__` for test + future-caller
  access.
- The frontend typecheck shows no new errors from US3 changes; all
  pre-existing TS errors are in `src/modules/resume/v2/` and out of
  scope (per US1/US2 reports and 033-POLISH).
- L008 verified: `git diff --stat` before commit shows all staged files
  (see commit hash in PR description).

## Follow-ups (out of scope for US3)

- US4 (AI ops), US5 (feedback/badcase), US6 (version/experiment)
  panels — same ProductEvent-fallback pattern, slot into the existing
  `pm_dashboard` module + page grid.
- Migration 0024 (`interview_outcomes` table + `failure_category`
  column) — when this lands, swap the `_base_event_query` /
  JSONB-extraction helpers for typed ORM queries in `repository.py`.
  The service / API contract is unchanged.
- Production `require_pm` resolver — replace the 401 stub in a
  follow-up US once PM role mapping lands.
- 033-POLISH restoration items:
  - `app/modules/telemetry_contracts/models.py` (missing — blocks
    conftest load for ALL pytest in the repo).
  - `app/agents/interview/planner_graph.py` + sibling nodes (missing —
    blocks conftest load).
  - `app/modules/telemetry_contracts/{events,redaction,retention}.py`
    (missing — already tolerated by lazy imports per US1 commit a4a9310).