# Tasks: 派生简历满页校准与真实页数一致 (REQ-063)

**Input**: Design documents from `/specs/063-derive-page-fill/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included per Constitution Principle VI (Test-First), plan Testing section, and FR/SC gates. Write failing tests before implementation where marked.

**Organization**: Tasks grouped by user story. Suggested delivery: **US1 (MVP) → US2 → US3 → US4**.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US4 maps to spec.md user stories
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/`, `backend/tests/`
- **Frontend**: `src/`
- **E2E**: `tests/e2e/`
- **Evidence**: `docs/evidence/063-derive-page-fill/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Evidence folder, thresholds module stubs, branch hygiene — no product rewrite yet

- [ ] T001 Create evidence tree `docs/evidence/063-derive-page-fill/{measure,calibrate,list-sync,export,bad-cases}/` with `README.md` mapping SC-001…SC-007 to folders
- [ ] T002 [P] Add threshold constants module skeleton `backend/app/modules/resume_derive/page_thresholds.py` (`SPARSE=1/3`, `COMFORT=2/3`, env override hooks documented)
- [ ] T003 [P] Add frontend threshold mirror `src/modules/resume/pagination/page-thresholds.ts` matching backend defaults
- [ ] T004 [P] Link REQ-063 quickstart from `specs/063-derive-page-fill/README.md` Next section (confirm `/speckit-implement` path)

**Checkpoint**: Evidence dirs + thresholds stubs exist

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared measure/decision types, Bad Case schema migration, page_report shape — MUST complete before story code

**⚠️ CRITICAL**: No user story implementation until this phase is complete

### Tests for Foundation

- [ ] T005 [P] Write failing unit tests for `decide_calibrate_action` table cases in `backend/tests/unit/resume_derive/test_calibrate_decision.py` per `contracts/calibrate-decision.md`
- [ ] T006 [P] Write failing unit tests asserting `PageMeasureResult` / fill-ratio invariants in `backend/tests/unit/resume_derive/test_page_measure_contract.py` per `contracts/page-measure.md`
- [ ] T007 [P] Write failing Vitest for `lastPageFillRatio` on `paginateMarkdownHtml` in `src/modules/resume/pagination/__tests__/fill-ratio.test.ts`

### Implementation for Foundation

- [ ] T008 Extend `PaginatedResumePreview` / page types with `lastPageFillRatio` (and optional per-page fill) in `src/modules/resume/pagination/types.ts`
- [ ] T009 Implement fill-ratio computation in `src/modules/resume/pagination/markdown-pages.ts` so T007 can go green
- [ ] T010 [P] Add `PageMeasureResult` / `PageReport` Pydantic schemas in `backend/app/modules/resume_derive/schemas.py` per `data-model.md`
- [ ] T011 Implement pure `decide_calibrate_action` in `backend/app/modules/resume_derive/calibrate_decision.py` so T005 goes green (no LLM)
- [ ] T012 Create Alembic migration for `resume_page_bad_cases` in `backend/migrations/versions/` per `data-model.md` (expand-only)
- [ ] T013 [P] Add ORM model `ResumePageBadCase` in `backend/app/modules/resume_derive/models.py` (or dedicated `bad_cases.py` models) wired to Base
- [ ] T014 [P] Add repository helpers `create_page_bad_case` / query-by-run in `backend/app/modules/resume_derive/bad_cases.py`
- [ ] T015 [P] Extend metrics stubs (`derive_calibrate_decision_total`, `page_measure_seconds`) in `backend/app/modules/resume_derive/metrics.py`
- [ ] T016 Document that char heuristic `_estimate_pages` MUST NOT be used as success truth in `backend/app/agents/nodes/resume_derive/calibrate_pages.py` module docstring (implementation rewrite in US1)

**Checkpoint**: Decision tests green; fill-ratio Vitest green; migration applies; stories unblocked

---

## Phase 3: User Story 1 — 目标 N 页得到充实的 N 页派生稿 (Priority: P1) 🎯 MVP

**Goal**: Derive calibrate uses real measure + decision table so success means pages=N and last-page fill ≥ COMFORT
**Independent Test**: Fixture draft → measure → decide → (spacing/prune/expand) → `page_report` + status; never succeed with char-estimated fake pages
**Quickstart**: Scenarios A–C

### Tests for User Story 1

- [ ] T017 [P] [US1] Capture RED/equivalent evidence: current `calibrate_pages` character estimate vs preview mismatch note in `docs/evidence/063-derive-page-fill/measure/baseline-char-estimate.md`
- [ ] T018 [P] [US1] Write failing integration test: calibrate with mocked measure fill≤1/3 overflow prefers `tighten_line_height` first in `backend/tests/integration/resume_derive/test_calibrate_spacing_first.py`
- [ ] T019 [P] [US1] Write failing integration test: measured==target & fill&lt;SPARSE → `agent_expand` + bad case row in `backend/tests/integration/resume_derive/test_calibrate_sparse_expand.py`
- [ ] T020 [P] [US1] Write failing unit/integration test: success requires fill≥COMFORT else `needs_guidance` in `backend/tests/unit/resume_derive/test_calibrate_comfort_gate.py`
- [ ] T021 [P] [US1] Write failing anti-fabrication assert on expand/prune path reuses source validator in `backend/tests/unit/agents/resume_derive/test_calibrate_no_fabrication.py`

### Implementation for User Story 1

- [ ] T022 [US1] Implement Playwright-backed `measure_resume_pages` in `backend/app/modules/resume_derive/page_measure.py` per `contracts/page-measure.md` (reuse browser context where practical)
- [ ] T023 [P] [US1] Add optional measure bundle entry `src/modules/resume/pagination/measure-bundle.ts` (or documented inject path) consumed by T022 for algorithm parity
- [ ] T024 [US1] Rewrite `calibrate_pages` in `backend/app/agents/nodes/resume_derive/calibrate_pages.py` to call measure + `decide_calibrate_action`, apply line-height strategies, invoke prune/expand only when decided, max rounds ≤5
- [ ] T025 [US1] Wire prune/expand helpers (reuse unused materials / existing draft tools) under calibrate node without fabricating claims; fail closed to `needs_guidance`
- [ ] T026 [US1] Persist enriched `page_report` on run artifacts + derived `derive_meta` in `backend/app/workers/tasks/resume_derive.py` and ensure `actual_page_count=measured` (never forge target on guidance)
- [ ] T027 [US1] Enforce exportable/success gate: `measured==target` AND `fill>=COMFORT` in `backend/app/modules/resume_derive/service.py` (page control / blockers)
- [ ] T028 [US1] Make T018–T021 green; record sample `page_report` JSON under `docs/evidence/063-derive-page-fill/calibrate/`
- [ ] T029 [US1] Add structured logs (`run_id`, `decision`, `last_page_fill_ratio`, `calibrate_round`) in calibrate/measure paths

**Checkpoint**: US1 independently verifiable — real measure drives success; spacing-first and sparse-expand behaviors proven

---

## Phase 4: User Story 2 — 列表实际页数与打开后一致 (Priority: P1)

**Goal**: List「实际页数」matches editor preview; save syncs `preview_page_count` → `actual_page_count`; open alone does not dirty-write
**Independent Test**: Save derived with new pageCount → GET list shows same actual; GET open without save does not bump version solely for page sync
**Quickstart**: Scenario D

### Tests for User Story 2

- [ ] T030 [P] [US2] Write failing contract/API test: PATCH/PUT derived with `preview_page_count` updates `actual_page_count` in `backend/tests/contract/resumes_v2/test_save_preview_page_count.py`
- [ ] T031 [P] [US2] Write failing Vitest: save payload includes `preview_page_count` from store `pageCount` in `src/modules/resume/v2/api/__tests__/save-preview-page-count.test.ts`
- [ ] T032 [P] [US2] Write failing Vitest/component test: DerivedResumeList displays server actual pages in `src/modules/resume/derive/__tests__/DerivedResumeList.pages.test.tsx`

### Implementation for User Story 2

- [ ] T033 [US2] Accept `preview_page_count` on resume update schemas/handlers in `backend/app/modules/resumes_v2/schemas.py` and `backend/app/modules/resumes_v2/api.py`; for `resume_kind=derived` set `actual_page_count` on successful owner save
- [ ] T034 [US2] Pass `pageCount` as `preview_page_count` on save from `src/modules/resume/v2/api/index.ts` and editor save path (`src/modules/resume/v2/store/index.ts` / BuilderShell save wiring)
- [ ] T035 [US2] Ensure open/load path does NOT auto-PATCH page count in editor entry (`src/modules/resume/v2/editor/` / page loader); only save/debounce-persist paths write
- [ ] T036 [US2] Confirm ResumeList / JobsDetailPanel still bind `actual_page_count` from API in `src/pages/ResumeList.tsx` and `src/components/jobs/JobsDetailPanel.tsx` (fix gaps if any)
- [ ] T037 [US2] Make T030–T032 green; add evidence note `docs/evidence/063-derive-page-fill/list-sync/README.md`

**Checkpoint**: US2 independently verifiable — list ↔ preview consistency after save

---

## Phase 5: User Story 3 — 导出以真实 PDF 页数为终裁 (Priority: P1)

**Goal**: PDF `/Count` remains authoritative; mismatch rejects export and rewrites `actual_page_count`
**Independent Test**: Matching export OK; forced mismatch → 422 `PAGE_COUNT_MISMATCH` + DB actual updated
**Quickstart**: Scenario E

### Tests for User Story 3

- [ ] T038 [P] [US3] Extend/confirm failing-or-RED contract for export mismatch + actual rewrite in `backend/tests/contract/resume_derive/test_export_gate_pages.py` (or `backend/tests/integration/resume_derive/test_export_page_gate.py`)
- [ ] T039 [P] [US3] Write E2E assertion PDF page count equals target for a succeeded derived in `tests/e2e/063-derive-page-fill.spec.ts` (may reuse helpers from `tests/e2e/derive-qa-page-count-pdf.spec.ts`)

### Implementation for User Story 3

- [ ] T040 [US3] Verify/harden PDF gate + `actual_page_count` rewrite on mismatch in `backend/app/modules/resumes_v2/api.py` export path (keep `count_pdf_pages`)
- [ ] T041 [US3] Ensure frontend export passes `expected_page_count` from target for derived in `src/modules/resume/v2/editor/controls/ExportMenu.tsx` (and related export-html path)
- [ ] T042 [US3] Make T038–T039 green; store one allow + one deny evidence under `docs/evidence/063-derive-page-fill/export/`

**Checkpoint**: US3 independently verifiable — PDF hard gate intact and documented

---

## Phase 6: User Story 4 — 校准决策可解释且可复盘 (Priority: P2)

**Goal**: `page_report` exposes decision trail; sparse-full drafts create queryable Bad Cases
**Independent Test**: After sparse fixture run, Bad Case row exists; page control / run payload shows fill + strategies
**Quickstart**: Scenario C (bad case portion)

### Tests for User Story 4

- [ ] T043 [P] [US4] Write failing integration test asserting Bad Case persistence fields in `backend/tests/integration/resume_derive/test_page_bad_cases.py`
- [ ] T044 [P] [US4] Write failing Vitest that PageControlPanel can render fill/decision when provided in `src/modules/resume/derive/__tests__/PageControlPanel.report.test.tsx`

### Implementation for User Story 4

- [ ] T045 [US4] On `record_bad_case` decisions, write `resume_page_bad_cases` via `backend/app/modules/resume_derive/bad_cases.py` and set `page_report.bad_case_ref` from calibrate/worker
- [ ] T046 [US4] Surface `page_report` (target/measured/fill/strategies/decision) on derive run GET already mapped in `backend/app/modules/resume_derive/api.py` / frontend `src/modules/resume/derive/api.ts`
- [ ] T047 [US4] Extend `PageControlPanel` in `src/modules/resume/derive/PageControlPanel.tsx` to show fill ratio / decision summary when available (keep compact)
- [ ] T048 [US4] Make T043–T044 green; dump sample Bad Case rows under `docs/evidence/063-derive-page-fill/bad-cases/`

**Checkpoint**: US4 independently verifiable — decisions + Bad Cases observable

---

## Phase 7: Aggregate Validation & Release Readiness

**Purpose**: Cross-story gates, deprecate char budget as authority, quickstart pass

- [ ] T049 [P] Deprecate/replace char `3200` as authoritative budget in `src/modules/resume/derive/target-pages.ts` (keep only as soft hint if needed; document non-authority)
- [ ] T050 [P] Remove or quarantine `_estimate_pages` success path from `backend/app/agents/nodes/resume_derive/calibrate_pages.py` (measure-only truth)
- [ ] T051 Add Playwright E2E covering list actual == preview after derive success in `tests/e2e/063-derive-page-fill.spec.ts`
- [ ] T052 [P] Update `specs/063-derive-page-fill/requirements-status.md` (create) with FR/SC status rows
- [ ] T053 Run `specs/063-derive-page-fill/quickstart.md` scenarios A–E; attach results under `docs/evidence/063-derive-page-fill/`
- [ ] T054 Verify metrics/log fields present in a sample worker log snippet saved to evidence
- [ ] T055 Update `specs/README.md` / feature README status to `in_progress` or `done` only when evidence backs SC-001…SC-007

**Checkpoint**: Ready for `/speckit-implement` completion review / ship

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: start immediately
- **Phase 2 Foundational**: after Setup — **blocks all stories**
- **Phase 3 US1**: after Foundational — **MVP**
- **Phase 4 US2**: after Foundational; ideally after US1 so list reflects real measure (can stub save sync earlier)
- **Phase 5 US3**: after Foundational; can parallel with US2 once export fixtures ready; benefits from US1 success samples
- **Phase 6 US4**: after US1 (needs calibrate writing page_report/bad cases)
- **Phase 7 Polish**: after selected stories complete

### User Story Dependencies

| Story | Depends on | Independently testable? |
|---|---|---|
| US1 | Phase 2 | Yes — calibrate + measure fixtures |
| US2 | Phase 2 (+ US1 for end-to-end list after derive) | Yes — save/list with fixture actual |
| US3 | Phase 2 | Yes — export gate with fixture PDF |
| US4 | US1 measure/decision path | Yes — bad case + report panel |

### Parallel Opportunities

- T002/T003/T004 parallel in Setup
- T005/T006/T007 parallel foundation tests
- T010/T013/T014/T015 parallel after schemas sketched
- US2 and US3 can proceed in parallel after US1 MVP checkpoint
- T049/T050/T052 parallel in polish

---

## Parallel Example: User Story 1

```text
# Tests in parallel:
T018 backend/tests/integration/resume_derive/test_calibrate_spacing_first.py
T019 backend/tests/integration/resume_derive/test_calibrate_sparse_expand.py
T020 backend/tests/unit/resume_derive/test_calibrate_comfort_gate.py
T021 backend/tests/unit/agents/resume_derive/test_calibrate_no_fabrication.py

# Then implementation sequence:
T022 page_measure.py → T024 calibrate_pages.py → T026 worker persist → T027 service gate
```

---

## Parallel Example: User Story 2

```text
T030 backend/tests/contract/resumes_v2/test_save_preview_page_count.py
T031 src/modules/resume/v2/api/__tests__/save-preview-page-count.test.ts
T032 src/modules/resume/derive/__tests__/DerivedResumeList.pages.test.tsx
# Then T033 → T034 → T035
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup
2. Phase 2 Foundational
3. Phase 3 US1
4. **STOP**: validate quickstart A–C
5. Demo: derive target 1/2 with full pages + honest guidance

### Incremental Delivery

1. US1 → real full-page derive
2. US2 → list/save trust
3. US3 → PDF终裁 hardening evidence
4. US4 → Bad Case + explainability
5. Phase 7 → mark done with evidence

### Suggested commit cadence

- After Phase 2 green
- After US1 green
- After US2+US3 green
- After US4 + quickstart evidence

---

## Notes

- Do **not** restore character-estimate success as a long-term fallback
- Agent prune/expand remains R2: source validation mandatory
- Open-without-save must not spam writes (US2)
- All tasks use checklist format with IDs and file paths for `/speckit-implement`
