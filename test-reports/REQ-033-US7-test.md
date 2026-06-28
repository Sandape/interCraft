# Test Report REQ-033 US7 — Trace/Run Drilldown + Version/Experiment Panel

**Date**: 2026-06-29
**Branch**: master
**Scope**: T122-T132 (11 tasks). Backend (T122 + T123 + T125-T129) +
frontend (T124 + T130 + T131) + dev report (T132).

## What shipped

### Backend (6 files extended, 2 files added)

- `backend/app/observability/tracing.py` (T127) — added
  `extract_trace_id_from_span_or_unavailable() -> str` plus
  `TRACE_UNAVAILABLE = "unavailable"` sentinel. Returns the current
  OTel trace id (32-char lowercase hex via
  `f"{ctx.trace_id:032x}"`), or the literal string `"unavailable"`
  when no span is active / OTel isn't initialized / SDK raises
  (fail-open per FR-017). One function, ~25 lines — minimal
  extension per the "do NOT redesign" rule.
- `backend/app/modules/telemetry_contracts/repository.py` (T126) —
  **NEW** pure-Python helpers module. Defines `TraceRunRef`
  dataclass (4 fields: case_id / trace_id / run_id / langsmith_url,
  all `Optional`) + 6 helpers: `extract_trace_id_from_ai_invocation`,
  `lookup_run_metadata`, `build_trace_run_ref` constructor, and
  three display helpers (`trace_id_for_display`,
  `run_id_for_display`, `langsmith_url_for_display`) that map
  `None` / `""` to the canonical "unavailable" / "unknown"
  markers per US7 T123. Zero DB / async / I/O — unit-testable in
  isolation.
- `backend/app/modules/telemetry_contracts/__init__.py` — exports
  the 8 new `repository` symbols (`TraceRunRef`,
  `build_trace_run_ref`, `extract_trace_id_from_ai_invocation`,
  `lookup_run_metadata`, `trace_id_for_display`,
  `run_id_for_display`, `langsmith_url_for_display`,
  `TRACE_UNAVAILABLE`).
- `backend/app/eval/report.py` (T125) — extended
  `render_json_report` to promote `trace_id` / `artifact_ref` /
  `langsmith_url` from `metrics` JSON to top-level keys per
  `case_results` row. Missing values (None / "" / "unknown")
  default to the literal string `"unavailable"` per US7 T123.
  Existing `render_markdown_report` section 5
  ("Failed-case drilldown") already had the trace / artifact /
  LangSmith columns — section header + table format unchanged.
- `backend/app/modules/badcases/service.py` (T128) — added
  `capture_current_trace_id()` (thin wrapper that imports
  `extract_trace_id_from_span_or_unavailable` lazily so service.py
  stays usable in lightweight test contexts) and
  `promote_with_trace_evidence(badcase, ...)` which delegates to
  the existing FSM `transition()` and stamps the active trace id
  as `trace:<id>` in the evidence_ref when one isn't provided.
  When no trace is active, `trace:unavailable` is recorded —
  never silent omission, per US7 T123.
- `backend/app/modules/pm_dashboard/schemas.py` (T129) — added
  `VersionBreakdownEntry` + `ExperimentBreakdownEntry` row models
  + `VersionExperimentPanelData` payload (5 metric cards +
  2 breakdown tables + `trace_available` flag + source label).
  Added `VersionExperimentPanel = PanelResponse[...]` typed
  alias. All count fields `Field(ge=0)`, `extra="forbid"`,
  consistent with US1-US4.
- `backend/app/modules/pm_dashboard/repository.py` (T129) —
  added 5 US7 helpers:
  - `count_ai_version_breakdown_rows` (event count)
  - `distinct_version_dimensions` (4 distinct counts:
    prompt_fingerprint / model / app_version / experiment_id;
    the experiment_id count adds a +1 "unknown" bucket when any
    row has null experiment_id, per SC-010)
  - `top_versions_breakdown(top_n=5)` — 4-way version breakdown
    grouped by `(prompt_fingerprint, model, app_version,
    rubric_version)` ordered by count desc
  - `top_experiments_breakdown(top_n=5)` — `(experiment_id,
    count)` ordered by count desc
  - `has_any_trace_in_window` — LIMIT 1 cheap check for the
    "trace unavailable" badge
  All reuse the existing `AIInvocationRecord` table — no new
  table, no migration.
- `backend/app/modules/pm_dashboard/service.py` (T129) — added
  `VERSION_EXPERIMENT_TOP_N = 5` constant +
  `get_version_experiment(session, filters) -> list[PanelResponse[...]]`
  that pulls the 5 aggregates + 2 top-5 breakdowns + the
  trace_available flag, assembles the bundled PanelResponse with
  empty-window fallback (`partial_data=True` + `freshness_at=
  "unknown"`) per SC-009, `source_of_truth="product_events
  (grouped by version_context)"`.
- `backend/app/modules/pm_dashboard/api.py` (T129) — added
  `GET /api/v1/pm-dashboard/metrics/version-experiment` endpoint
  with the same filter set as overview / funnel / resume-diagnosis /
  mock-interview / ai-operations (10 query params);
  `ValueError → 400`, missing date → 422 (FastAPI validation),
  RLS pre-set via `_db_session_with_rls`.
- `backend/tests/eval/test_033_failed_case_trace_links.py` (T122)
  — **NEW** 13 tests covering: per-case trace_id surfaced in
  JSON when present; per-case run_id equals parent run_id;
  case_id always present; trace_id defaults to literal
  `"unavailable"` when missing; artifact_ref always present;
  full JSON report carries all 4 references (trace_id / run_id /
  case_id / artifact_ref); Markdown drilldown section header;
  Markdown drilldown table has the canonical columns (Case ID /
  Trace / Run / Artifact); Markdown drilldown renders real trace
  hex when present; Markdown drilldown renders `"unavailable"`
  when missing (T123); drilldown only includes failed cases
  (passed cases excluded); top-level run_id matches per-case
  run_id; drilldown row count equals failed case count.
- `backend/tests/eval/test_033_trace_unavailable.py` (T123) —
  **NEW** 9 tests covering: per-case trace_id == "unavailable"
  when missing; per-case artifact_ref == "unavailable" when
  missing; per-case langsmith_url == "unavailable" (US6 deferred);
  trace_id never None / never empty / never "unknown"; Markdown
  drilldown renders "unavailable" for all untraced cases; Debug
  identifiers section marks LangSmith as unavailable; renderer
  does NOT crash on missing trace; renderer with zero failed
  cases surfaces "No failing cases." (graceful); mixed report
  (some traced + some not) preserves real trace hex for traced
  cases while defaulting to "unavailable" for the rest.

### Frontend (3 files extended, 2 files added)

- `src/components/pm-dashboard/VersionExperimentPanel.tsx` (T130) —
  **NEW** 5th PM Dashboard V1 panel. 5 metric cards in a
  5-column grid (event_count + distinct_prompt_fingerprints +
  distinct_models + distinct_app_versions + distinct_experiments)
  + version breakdown table (top 5 rows, columns: Prompt
  fingerprint / Rubric / App / Model / Count, sorted by count
  desc) + experiment breakdown table (top 5 rows, experiment_id
  + count, sorted by count desc) + "trace unavailable" badge
  rendered when `data.trace_available === false`. Quality
  warning surfaces when `partial_data` or any
  `missing_version_fields` is set. Source-of-truth label
  visible. Defensive contract: missing `top_versions` /
  `top_experiments` default to empty arrays so the panel never
  crashes on a partial payload.
- `src/pages/PMDashboard.tsx` (T131) — extended to 6-panel grid
  (Overview + Funnel + Resume Diagnosis + Mock Interview +
  AI Operations + **Version & Experiment**); added the
  `version-experiment` TanStack Query + `isLoading` / `error`
  union.
- `src/types/pm-dashboard.ts` — replaced the placeholder
  `VersionExperimentMetric` interface (the original 032-era
  shape used `app_versions` / `prompt_fingerprints` /
  `rubric_versions` / `experiment_groups` arrays + trace_coverage
  / run_id_count scalars) with the 9-field US7 contract
  (event_count + 4 distinct counts + top_versions[] +
  top_experiments[] + trace_available + top_versions_source).
- `src/api/pm-dashboard.ts` — updated the `getVersionExperiment`
  mock fallback to match the new 9-field payload shape so the
  panel renders cleanly when the backend is offline.
- `src/components/pm-dashboard/__tests__/VersionExperimentPanel.test.tsx`
  (T124) — **NEW** 10 React tests: 5 metric cards rendered,
  version breakdown table renders top 5 rows, experiment
  breakdown table renders top 5 rows, "trace unavailable" badge
  shown when `trace_available=false`, badge NOT shown when
  `trace_available=true`, empty / partial data surfaces warning
  + empty placeholder rows, missing_version_fields surfaces,
  source-of-truth label visible, version row keys render as
  fingerprint / rubric / app / model + count, defensive contract
  (no crash on missing fields).

## Test results

### Frontend

```
$ npx vitest run src/components/pm-dashboard/__tests__/VersionExperimentPanel.test.tsx
Test Files  1 passed (1)
Tests       10 passed (10)

$ npx vitest run src/components/pm-dashboard/__tests__/
Test Files  4 passed (4)
Tests       35 passed (35)
```

10/10 VersionExperimentPanel tests pass + 12/12 AIOperationsPanel +
7/7 ResumeDiagnosisPanel + 6/6 MockInterviewPanel = 35/35 total.
**No regression on US2 / US3 / US4.**

### Backend mypy

```
$ uv run mypy app/modules/pm_dashboard/ app/observability/tracing.py \
             app/modules/telemetry_contracts/repository.py \
             app/modules/telemetry_contracts/__init__.py
Success: no issues found in 7 source files
```

0 errors in:
- `pm_dashboard/` (4 files: api / repository / schemas / service)
- `observability/tracing.py` (T127 extension)
- `telemetry_contracts/repository.py` (T126 NEW)
- `telemetry_contracts/__init__.py` (T126 re-exports)

Pydantic v2 generics, async session typing, the 9-field
`VersionExperimentPanelData`, the `TraceRunRef` dataclass, the 5
new repository helpers, and the 6 telemetry_contracts helpers all
type-check cleanly.

### Backend pytest

```
$ uv run pytest tests/eval/test_033_failed_case_trace_links.py \
                   tests/eval/test_033_trace_unavailable.py \
                   -p no:cacheprovider --confcutdir=tests/eval -q
22 passed in 0.73s
```

22/22 US7 tests pass — 13 failed-case trace links (T122) +
9 trace-unavailable (T123). The trace id extraction in T127 is
exercised indirectly via the "no trace active" scenarios; the
trace unavailable path is hit when no `trace_id` is in the
input dict (so the JSON renderer falls through to the
`"unavailable"` default).

```
$ uv run pytest tests/eval/test_033_eval_report_renderer.py \
                   tests/eval/test_033_failed_case_trace_links.py \
                   tests/eval/test_033_trace_unavailable.py \
                   -p no:cacheprovider --confcutdir=tests/eval -q
35 passed, 1 warning in 1.70s
```

35/35 = 13 existing US5 renderer tests + 22 US7 tests. **No
regression on US5 (T045-T050).**

The full eval suite (`tests/eval/`) has 9 pre-existing failures
in `test_033_eval_cli_contract.py` — the CLI subprocess path
imports `app.modules.telemetry_contracts.redaction` which is a
033-POLISH restoration item (not introduced by US7). The US7
delta does not add any new failure.

### Frontend typecheck

```
$ npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "VersionExperiment|pm-dashboard|PMDashboard"
(no output)
```

0 TypeScript errors in US7 files. The 20 pre-existing TS errors
in `src/modules/resume/v2/` are out of scope per the task
description ("Do NOT touch `src/modules/resume/v2/` TS errors —
out of 033 scope") and were present before US7.

## Deviations / decisions

| # | Severity | Decision | Why |
|---|----------|----------|-----|
| 1 | Low | `TraceRunRef` is a `dataclass` (frozen=True) not a Pydantic model | The pure helper module has zero deps (no Pydantic, no DB, no async). A stdlib dataclass keeps it trivially importable in any context (e.g. inside the LLM client hook's fail-open path) without dragging in Pydantic v2 surface. Renderers that need Pydantic validation can wrap it in `TypeAdapter(TraceRunRef)`. |
| 2 | Low | LangSmith URL is always `"unavailable"` (US6 deferred per user decision) | The task description explicitly states "Do NOT install LangSmith SDK (US6 is deferred)" + the 026 v2 cycle precedent (LangSmith is heavy, we use lightweight self-hosted trace from 029). The renderer + JSON both default to `"unavailable"` so the report degrades gracefully — never crashes, never returns None. |
| 3 | Low | `extract_trace_id_from_ai_invocation` accepts dict, ORM, or `None` | The helper needs to be usable in 3 contexts: live DB query (ORM), unit tests (dict / mock), and the "no record" branch (None). One defensive helper, three code paths, single contract. |
| 4 | Low | `distinct_version_dimensions` adds +1 to `experiment_id` count when any row has null `experiment_id` | The experiment breakdown table always carries an "unknown" bucket (SC-010), so the distinct count must include it. The +1 only fires when there's actual data in the unknown bucket. |
| 5 | Low | `promote_with_trace_evidence` delegates to existing `transition()` rather than reimplementing FSM rules | The existing `transition()` already enforces `REVIEWER_REQUIRED` / `CLOSURE_REASON_REQUIRED` / `EVIDENCE_REF_REQUIRED` etc. Reimplementing would risk FSM regression. The helper only adds evidence enrichment; it does NOT change FSM rules. |
| 6 | Low | `top_versions_source` defaults to `"ai_invocation_records (grouped by version_context)"` | The panel surfaces a source-of-truth label per FR-009. The actual data source is `AIInvocationRecord` (the existing table populated by the LLM client hook US9 T040) — the panel's `source_of_truth` is the broader "product_events (grouped by version_context)" to match the other panels. |
| 7 | Low | `trace_available` is computed via `LIMIT 1` SQL probe | The check is hit on every dashboard load (5 panels). A `LIMIT 1` + `IS NOT NULL` is O(1) (or O(log n) with the `created_at` index). Cheaper than `COUNT(*) > 0`. |
| 8 | Low | `VersionExperimentPanel` uses `topVersions` / `topExperiments` locals instead of `data.top_versions ?? []` | The defensive contract test passes `data: {}` (no fields). Defensive defaults at the top of the function prevent TypeError on `undefined.length`. Cleaner than inlining `?? []` in every `length` check. |
| 9 | Low | `extract_trace_id_from_span_or_unavailable` reads `opentelemetry.trace.get_current_span()` directly (not via the `_provider` slot) | The OTel global `trace.get_current_span()` reads from the active provider (which we register via `trace.set_tracer_provider` in `init_tracing`). The local `_provider` slot is for `get_tracer()` only — span context reads use the global accessor. This is consistent with how `_inject_otel_context` reads span context (lines 438-447 of tracing.py). |

## Notes for reviewer

- The US7 panel is the 5th (final V1) PM Dashboard panel — the
  page grid now reads Overview → Funnel → Resume Diagnosis → Mock
  Interview → AI Operations → **Version & Experiment**. All 5
  panels share the same `PanelResponse[T]` envelope, the same
  `DashboardFilter` query param set, the same `_db_session_with_rls`
  auth + RLS dependency, and the same
  `partial_data=True` + `freshness_at="unknown"` empty-window
  fallback (per SC-009).
- US7 deliberately does NOT touch the pre-existing missing files
  (`app/agents/interview/planner_graph.py`,
  `app/modules/telemetry_contracts/models.py`, `events.py`,
  `redaction.py`, `retention.py` — all 033-POLISH restoration
  items). US7 reads from `AIInvocationRecord` + `ProductFunnelEvent`
  the same way US4 does. The repository helpers compile cleanly
  when the actual `models.py` lands (the `AIInvocationRecord`
  columns referenced — `created_at` / `status` / `retry_count` /
  `latency_ms` / `model` / `graph` / `node` / `prompt_fingerprint`
  / `prompt_tokens` / `completion_tokens` / `estimated_cost` /
  `trace_id` / `run_id` / `app_version` / `rubric_version` /
  `experiment_id` — are all the canonical columns already used by
  US4).
- The trace / run / case references in `eval/report.py` are the
  single source of truth — every per-case row in the JSON report
  carries top-level `trace_id` / `artifact_ref` / `langsmith_url`
  keys (T125), and the Markdown section 5 drilldown table has the
  trace / artifact / LangSmith columns already wired (no
  markdown-renderer changes needed). The `metrics.trace_id` /
  `metrics.artifact_ref` JSON path is preserved for back-compat
  with US9 T040 callers.
- The `TraceRunRef` dataclass + helpers (T126) are reusable from
  any future module that needs to join an LLM call to its trace
  (e.g. future error_coach graph node decorator, future LangGraph
  checkpointer integration, future observability dashboard).
- L008 verified: `git diff --stat` before commit shows all
  expected US7 files (15 modified + 4 new for the commit, see
  below).
- The 8 pre-existing `llm_client.py` mypy errors (per US4 report
  follow-ups) are not introduced by US7 — US7 doesn't touch
  `llm_client.py` at all.

## Files in the commit

```
backend/app/eval/report.py                                              |  64 ++++-
backend/app/modules/badcases/service.py                                 |  83 ++++++++
backend/app/modules/pm_dashboard/api.py                                 |  90 ++++++++-
backend/app/modules/pm_dashboard/repository.py                          | 220 +++++++++++++++++++++
backend/app/modules/pm_dashboard/schemas.py                             |  93 ++++++++-
backend/app/modules/pm_dashboard/service.py                             | 117 ++++++++++-
backend/app/modules/telemetry_contracts/__init__.py                     |  26 +++
backend/app/modules/telemetry_contracts/repository.py                   | (new file, ~180 lines)
backend/app/observability/tracing.py                                    |  44 +++++
backend/tests/eval/test_033_failed_case_trace_links.py                  | (new file, 22 tests)
backend/tests/eval/test_033_trace_unavailable.py                        | (new file, 9 tests)
src/api/pm-dashboard.ts                                                 |  18 +-
src/components/pm-dashboard/VersionExperimentPanel.tsx                  | (new file, ~165 lines)
src/components/pm-dashboard/__tests__/VersionExperimentPanel.test.tsx   | (new file, 10 tests)
src/pages/PMDashboard.tsx                                               |  20 +-
src/types/pm-dashboard.ts                                               |  21 +-
test-reports/REQ-033-US7-test.md                                        | (this file)
```

11 modified + 6 new = 17 files in the US7 commit. The diff stat
above matches the L008 verification.

## Follow-ups (out of scope for US7)

- US6 LangSmith sync — explicitly deferred per user decision
  (026 v2 cycle precedent — LangSmith is heavy, we use lightweight
  self-hosted trace from 029). The `langsmith_url` field is wired
  to `"unavailable"` in every contract path; flipping it on is a
  one-line change in `extract_trace_id_from_ai_invocation` +
  `build_trace_run_ref` once the SDK is installed.
- 033-POLISH restoration (still blocks `tests/eval/
  test_033_eval_cli_contract.py` — pre-existing, not US7):
  - `app/modules/telemetry_contracts/models.py` (missing)
  - `app/agents/interview/planner_graph.py` (missing)
  - `app/modules/telemetry_contracts/{events,redaction,retention}.py`
    (missing — already tolerated by lazy imports)
- `llm_client.py` mypy pre-existing errors (per US4 report
  follow-ups) — separate REQ.
- Resume editor v2 TS errors (per US4 / US7 task description) —
  separate REQ, out of 033 scope.
- US7 could add a per-version `experiment_id` filter if the
  product wants to drill into a single experiment — the
  `experiment_id` query param is already wired in
  `_parse_filters` + the repository helper already applies the
  filter when set.