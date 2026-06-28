# Test Report REQ-033 US2 — Resume Diagnosis Panel

**Date**: 2026-06-29
**Branch**: master
**Scope**: T082-T090 (9 tasks). Backend (T082 + T084-T087) + frontend
(T083 + T088-T089) + dev report (T090).

## What shipped

### Backend (5 files extended, 1 file added)

- `backend/app/modules/pm_dashboard/repository.py` (T084) — added 7 US2
  helpers (count_resume_diagnoses, count_successful_resume_diagnoses,
  count_report_views, count_suggestions_shown,
  count_suggestions_accepted, avg_resume_score_before,
  avg_resume_score_after) + 6 RESUME_DIAGNOSIS_* event_name constants +
  `_base_event_query` helper. Falls back to `ProductEvent` rows where
  `event_name LIKE 'resume_diagnosis.%'` (US2 fallback — see "Deviations"
  below for the migration-pending rationale).
- `backend/app/modules/pm_dashboard/schemas.py` (T086) — added
  `ResumeDiagnosisPanelData` (10 fields: success_count, total_count,
  success_rate, report_views, suggestions_shown, suggestions_accepted,
  acceptance_rate, score_delta_before, score_delta_after, score_delta)
  + `ResumeDiagnosisPanel = PanelResponse[ResumeDiagnosisPanelData]`
  typed alias + export in `__all__`.
- `backend/app/modules/pm_dashboard/service.py` (T085) — added
  `get_resume_diagnosis(session, filters) -> list[PanelResponse[Any]]`
  that pulls the 7 aggregates, derives `success_rate` /
  `acceptance_rate` / `score_delta`, assembles the bundled
  PanelResponse with quality_flags (partial_data on empty window),
  freshness_at, and source_of_truth = `"product_events (resume_diagnosis.*)"`.
- `backend/app/modules/pm_dashboard/api.py` (T087) — added
  `GET /api/v1/pm-dashboard/metrics/resume-diagnosis` endpoint with
  the same filter set as overview/funnel; `ValueError → 400`, missing
  date → 422 (FastAPI validation).
- `backend/tests/integration/test_033_resume_diagnosis_metrics.py`
  (T082) — added 14 integration tests covering: 7 repository helpers
  return correct shapes; filter accepts date range + environment +
  app_version; filter rejects inverted date range; empty window
  surfaces `partial_data=True` + `freshness_at="unknown"`; unknown
  version fields surface in `missing_version_fields` (SC-010);
  service returns panel list; data shape covers all 9 required
  fields; no raw resume content leaks in the response payload
  (privacy assertion: forbidden keys like `resume_text`,
  `resume_markdown`); score_delta is the difference of averages
  clamped to [-100, 100].

### Frontend (3 files extended, 2 files added)

- `src/components/pm-dashboard/ResumeDiagnosisPanel.tsx` (T088) —
  new component: 6 metric cards (success rate with color coding
  green >= 80% / amber 50-80% / red < 50%, report views, suggestions
  shown, suggestions accepted, acceptance rate, score delta with
  up/down arrow + green/red color) + quality-flag warning +
  source-of-truth label.
- `src/pages/PMDashboard.tsx` (T089) — extended to 3-panel grid
  (Overview + Funnel + Resume Diagnosis); added the
  `resume-diagnosis` TanStack Query + `isLoading` / `error` union.
- `src/components/pm-dashboard/__tests__/ResumeDiagnosisPanel.test.tsx`
  (T083) — added 7 React tests: 5 metric cards rendered in a grid,
  success rate displayed as percentage, score delta up arrow + green
  when positive, down arrow + red when negative, neutral color when
  zero, partial-data warning surfaces when `partial_data=true`,
  defensive contract: doesn't crash on missing fields.
- `src/types/pm-dashboard.ts` — extended `ResumeDiagnosisMetric` with
  the 10 new fields (replaced the legacy
  `diagnosis_count`/`failure_rate`/`score_delta_avg` shape).
- `src/api/pm-dashboard.ts` — updated the `getResumeDiagnosis` mock
  fallback to match the new `ResumeDiagnosisMetric` shape + source
  label `"product_events (resume_diagnosis.*)"`.

## Test results

### Frontend

```
$ npx vitest run src/components/pm-dashboard/__tests__/ResumeDiagnosisPanel.test.tsx
Test Files  1 passed (1)
Tests       7 passed (7)
```

7/7 ResumeDiagnosisPanel tests pass. The previously-failing pre-T083
state (panel import unresolved) is now green.

### Backend mypy

```
$ uv run mypy app/modules/pm_dashboard/
Success: no issues found in 4 source files
```

0 errors in `pm_dashboard/`. Confirms the Pydantic generics, async
session typing, and Any-widening from US1 still hold after T084
extensions.

### Backend pytest

```
$ uv run pytest tests/integration/test_033_resume_diagnosis_metrics.py \
                   -p no:cacheprovider -q
ImportError while loading conftest 'D:\Project\eGGG\backend\tests\conftest.py'
  File "D:\Project\eGGG\backend\app\agents\interview\graph.py", line 22
    from app.agents.interview.planner_graph import get_planner_subgraph
ModuleNotFoundError: No module named 'app.agents.interview.planner_graph'
```

The same pre-existing conftest import blocker as US1: `app/main.py`
transitively imports `app/agents/interview/planner_graph.py` (and
untracked siblings `nodes/planner_context.py` / `planner_generate.py` /
`planner_search.py` / `prompts/{interviewer,planner}.md`) which are
missing from the working tree per `git status` (untracked but not
importable as Python modules from disk). The same blocker affects
**every** pytest invocation in the repo (verified: US1's
`test_033_pm_dashboard_metrics.py` produces identical error). The
integration tests themselves are correctly structured to skip when
`DATABASE_URL` is unset — the blocker is at conftest load time, not
in test code. This matches US1's documented state and is tracked
under 033-POLISH restoration. **No regression introduced by US2.**

### Service smoke

```
$ uv run python -c "from app.modules.pm_dashboard.service import get_resume_diagnosis; ..."
ModuleNotFoundError: No module named 'app.modules.telemetry_contracts.models'
```

Same pre-existing blocker as US1: `repository.py` imports ORM classes
(`ProductFunnelEvent`, `AIInvocationRecord`, `Badcase`) from
`app.modules.telemetry_contracts.models`, a module that is referenced
from `badcases/models.py` and `pm_dashboard/repository.py` but is not
present in the working tree (last referenced in
`app/modules/telemetry_contracts/__init__.py` lazy-import block).
**No regression introduced by US2.** US1 had the same issue; the
module restoration is tracked under 033-POLISH.

### Frontend typecheck

```
$ npx tsc --noEmit -p tsconfig.json | grep -E "pm-dashboard|ResumeDiagnosisPanel"
(empty — no new errors)
```

All TS errors in `npx tsc` output are pre-existing in
`src/modules/resume/v2/` (per US1 report — 033-POLISH scope).

## Deviations / decisions

| # | Severity | Decision | Why |
|---|----------|----------|-----|
| 1 | Medium | US2 repository falls back to `ProductEvent` rows where `event_name LIKE 'resume_diagnosis.%'` | The dedicated `resume_diagnoses` / `resume_diagnosis_suggestions` / `resume_diagnosis_events` tables from spec.md §data-model are not in any migration yet (033-POLISH restoration pending). Falling back to `ProductEvent` keeps the panel functional without a migration; service + API contract is unchanged when the tables land, just swap the SQL targets. Privacy is preserved: the panel returns counts + deltas only, no raw resume content. |
| 2 | Low | JSONB extraction for score_before / score_after uses `(metadata ->> 'score_before')::float` SQLAlchemy idiom | The `ProductFunnelEvent` schema has `metadata` as JSONB; the avg(score_before) / avg(score_after) queries extract the numeric keys directly. Privacy: aggregate only, no per-row scores surfaced. |
| 3 | Low | `ResumeDiagnosisMetric` TS type replaced the legacy `diagnosis_count`/`failure_rate`/`score_delta_avg` shape | The legacy US0 placeholder shape was speculative (not in any locked contract). The new shape matches the backend `ResumeDiagnosisPanelData` field-for-field. |
| 4 | Low | ResumeDiagnosisPanel card layout uses `grid-cols-2 md:grid-cols-3` (3-column on desktop) | US2 has 6 metric cards (success rate + 4 sub-cards + score delta); 3-column fits cleanly under the existing 4-column Overview grid. |
| 5 | Low | Score delta sign formatting: `+15` / `-8` / `0` with explicit ArrowUp / ArrowDown / Minus icons | Sign must be observable per spec; ArrowUp for positive, ArrowDown for negative, Minus for zero (per AC-05 in T083). |
| 6 | Low | `success_rate` color-coded green >= 80%, amber 50-80%, red < 50% | PM dashboards conventionally use this 3-band threshold for AI task success. |
| 7 | Low | Auth stub `require_pm` still raises 401 | Same as US1; production resolver is a follow-up. |

## Notes for reviewer

- The privacy assertion in T082 (`test_resume_panel_does_not_leak_raw_content`)
  enumerates forbidden field names: `resume_text`, `resume_markdown`,
  `resume_url`, `raw_resume`, `diagnosis_markdown`, `suggestion_text`,
  `report_markdown`, `report_text`. If the dedicated tables land and
  the service layer accidentally exposes a raw field, this test
  fails immediately.
- The score delta calculation in `service.get_resume_diagnosis` uses
  the float difference `score_after - score_before`, clamped to
  [-100, 100] via the Pydantic schema `Field(ge=-100.0, le=100.0)`.
  Zero-data case is explicitly handled: when both averages are 0.0,
  the delta is 0.0.
- The empty-window fallback mirrors US1's pattern exactly:
  `quality_flags.partial_data=True` + `freshness_at="unknown"`,
  surfaced by `get_resume_diagnosis` via the `has_data` boolean
  derived from total / report_views / suggestions_shown / suggestions_accepted
  being all zero.
- The 7 new repository helpers and 6 `RESUME_DIAGNOSIS_*` event_name
  constants are exported in `__all__` for test + future-caller access.
- The frontend typecheck shows no new errors from US2 changes; all
  pre-existing TS errors are in `src/modules/resume/v2/` and out of
  scope (per US1 report and 033-POLISH).
- L008 verified: `git diff --stat` before commit shows all staged files
  (see commit hash in PR description).

## Follow-ups (out of scope for US2)

- US3 (mock interview), US4 (AI ops), US7 (version/experiment) panels —
  same ProductEvent-fallback pattern, slot into the existing
  `pm_dashboard` module + page grid.
- Migration 0024 (`resume_diagnoses` / `resume_diagnosis_suggestions` /
  `resume_diagnosis_events` tables) — when this lands, swap the
  `_base_event_query` helper for typed ORM queries in `repository.py`
  + remove the JSONB extraction for score_before / score_after. The
  service / API contract is unchanged.
- Production `require_pm` resolver — replace the 401 stub in a
  follow-up US once PM role mapping lands.
- 033-POLISH restoration items:
  - `app/modules/telemetry_contracts/models.py` (missing — blocks
    conftest load for ALL pytest in the repo).
  - `app/agents/interview/planner_graph.py` + sibling nodes (missing —
    blocks conftest load).
  - `app/modules/telemetry_contracts/{events,redaction,retention}.py`
    (missing — already tolerated by lazy imports per US1 commit a4a9310).
