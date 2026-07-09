# Tasks: Markdown Editor Cutover and Pagination (REQ-049)

**Input**: Design documents from `specs/049-markdown-editor-cutover/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Context**: Generated for `REQ-049`. `.specify/scripts/bash/setup-tasks.sh --json` could not run because `bash` is unavailable in this Windows environment. Equivalent setup result: `FEATURE_DIR=specs/049-markdown-editor-cutover`, `TASKS_TEMPLATE=.specify/templates/tasks-template.md`, `AVAILABLE_DOCS=["research.md","data-model.md","contracts/","quickstart.md"]`.

**Tests**: Required. The feature spec marks user scenario testing mandatory and the project constitution requires test-first implementation for non-trivial changes.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another incomplete task.
- **[Story]**: User story label for story-phase tasks only.
- Every task includes a concrete file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create shared fixtures and evidence locations used by all acceptance work.

- [X] T001 Create REQ-049 E2E fixture directory in `tests/e2e/fixtures/049-markdown-editor-cutover/README.md`
- [X] T002 [P] Add contact format lab Markdown fixture in `tests/e2e/fixtures/049-markdown-editor-cutover/contact-format-lab.md`
- [X] T003 [P] Add long three-page Markdown fixture in `tests/e2e/fixtures/049-markdown-editor-cutover/long-three-page.md`
- [X] T004 [P] Add structured-only legacy resume fixture in `tests/e2e/fixtures/049-markdown-editor-cutover/legacy-structured-resume.json`
- [X] T005 [P] Add Playwright route/mock helpers for REQ-049 in `tests/e2e/fixtures/049-markdown-editor-cutover/fixture.ts`
- [X] T006 [P] Create REQ-049 evidence directory guide in `docs/evidence/049-markdown-editor-cutover/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared state and schema work that all user stories rely on.

**Critical**: No user story work should begin until this phase is complete.

- [X] T007 Extend Markdown settings/status types for pagination and legacy conversion in `src/modules/resume/renderer/types.ts`
- [X] T008 [P] Extend frontend resume data validation for pagination and conversion fields in `src/modules/resume/v2/schema/data.ts`
- [X] T009 [P] Add default pagination and legacy conversion values in `src/modules/resume/v2/schema/defaults.ts`
- [X] T010 Add Zustand store actions for pagination state, page count, and legacy conversion status in `src/modules/resume/v2/store/index.ts`
- [X] T011 [P] Add store tests for pagination and legacy conversion metadata in `src/modules/resume/v2/store/__tests__/markdown-cutover-status.test.ts`
- [X] T012 [P] Update resume module documentation for Markdown-only boundaries in `src/modules/resume/README.md`

**Checkpoint**: Shared Markdown document state is typed, defaulted, validated, and test-covered.

---

## Phase 3: User Story 1 - Markdown-Only Resume Editing (Priority: P1) MVP

**Goal**: Every resume creation/editing path lands on the Markdown editor, and old structured editor controls are not exposed as active editing options.

**Independent Test**: Open create, existing Markdown, duplicate/open, direct route, and stale-link paths. Each path shows `markdown-source-editor`, preview, theme, line spacing, smart one-page, and export controls, with no active legacy structured editor controls.

### Tests for User Story 1

- [X] T013 [P] [US1] Add route/component test for Markdown editor hydration and restored settings in `src/pages/__tests__/ResumeEditorV2.markdown-cutover.test.tsx`
- [X] T014 [P] [US1] Add BuilderShell regression test proving legacy panels and dock controls are absent in `src/modules/resume/v2/editor/__tests__/BuilderShell.markdown-cutover.test.tsx`
- [X] T015 [P] [US1] Add Playwright entrypoint cutover coverage in `tests/e2e/049-markdown-editor-cutover.spec.ts`

### Implementation for User Story 1

- [X] T016 [US1] Update `ResumeEditorV2` to always hydrate the Markdown editor route and remove the legacy `open in v1 editor` dead-end in `src/pages/ResumeEditorV2.tsx`
- [X] T017 [US1] Replace active structured layout rendering with a Markdown-only editor shell in `src/modules/resume/v2/editor/BuilderShell.tsx`
- [X] T018 [US1] Remove active template gallery, sidebar toggle, legacy PDF branch, and structured-editor-only controls from the active header in `src/modules/resume/v2/editor/Header.tsx`
- [X] T019 [US1] Fix duplicate navigation so copied resumes reopen through `/resume/:id` Markdown routing in `src/modules/resume/v2/editor/BuilderShell.tsx`
- [X] T020 [US1] Verify and update resume list create/open links to target the Markdown editor route in `src/pages/ResumeList.tsx`
- [X] T021 [US1] Update existing BuilderShell tests to assert the Markdown-only contract instead of legacy panel behavior in `src/modules/resume/v2/editor/__tests__/BuilderShell.test.tsx`
- [X] T022 [US1] Update REQ-047 E2E compatibility expectations after the Markdown-only cutover in `tests/e2e/047-resume-editor-v3.spec.ts`

**Checkpoint**: User Story 1 is independently complete when all tested entry points open the Markdown editor and no active legacy editing controls are visible.

---

## Phase 4: User Story 2 - Polished `left/right` Contact Rendering (Priority: P1)

**Goal**: Muji-compatible `::: left` and `::: right` contact blocks render as aligned contact regions across all three themes and PDF export.

**Independent Test**: Render the contact format lab fixture with plain icon rows, icon-prefixed links, email/phone/location icons, unknown icons, and wrapping text. Verify alignment in all three themes and exported PDF.

### Tests for User Story 2

- [X] T023 [P] [US2] Add renderer unit tests for semantic contact row markup in `src/modules/resume/renderer/__tests__/contact-container-rendering.test.ts`
- [X] T024 [P] [US2] Add theme/component tests for wrapped contact rows across all three themes in `src/modules/resume/v2/editor/__tests__/MarkdownResumeContactLayout.test.tsx`
- [X] T025 [P] [US2] Add Playwright contact visual and PDF request assertions in `tests/e2e/049-markdown-editor-cutover.spec.ts`

### Implementation for User Story 2

- [X] T026 [US2] Implement contact row normalization for icon rows, icon-prefixed links, unknown icons, and plain text rows in `src/modules/resume/renderer/markdown-it-plugins/contact-rows.ts`
- [X] T027 [US2] Update container rendering to emit semantic left/right side wrappers and row groups in `src/modules/resume/renderer/markdown-it-plugins/containers.ts`
- [X] T028 [US2] Register the contact row plugin in the Markdown parser pipeline in `src/modules/resume/renderer/parser.ts`
- [X] T029 [US2] Export contact row warning types and fallback diagnostics in `src/modules/resume/renderer/types.ts`
- [X] T030 [US2] Add stable contact layout CSS for icon slots, text slots, wrapping, and right alignment in `src/modules/resume/v2/editor/markdown-resume.css`
- [X] T031 [US2] Ensure unknown icon names reserve the icon slot without breaking alignment in `src/modules/resume/renderer/icons/svg-map.ts`
- [X] T032 [US2] Ensure exported preview HTML includes semantic contact markup for PDF parity in `src/modules/resume/v2/editor/Header.tsx`

**Checkpoint**: User Story 2 is independently complete when contact rows align within the acceptance tolerance in preview and export evidence.

---

## Phase 5: User Story 3 - Multi-Page Markdown Resume Rendering (Priority: P1)

**Goal**: Long Markdown resumes render as ordered preview pages with visible boundaries, no clipped content, smart one-page fallback, and PDF page-order parity.

**Independent Test**: Paste the long 3-page fixture and verify page containers, page boundaries, no hidden content, smart one-page infeasible feedback, and PDF export with the same page count/order.

### Tests for User Story 3

- [X] T033 [P] [US3] Add pagination unit tests for page state transitions and page break decisions in `src/modules/resume/pagination/__tests__/markdown-pagination.test.ts`
- [X] T034 [P] [US3] Add Markdown editor component tests for multi-page preview containers in `src/modules/resume/v2/editor/__tests__/MarkdownResumePagination.test.tsx`
- [X] T035 [P] [US3] Add export tests for paginated preview HTML and measuring-state handling in `src/modules/resume/v2/editor/__tests__/ExportMenu.test.tsx`
- [X] T036 [P] [US3] Add API export payload tests for paginated HTML parity in `src/modules/resume/v2/api/__tests__/export-v3.test.ts`
- [X] T037 [P] [US3] Add Playwright long-resume pagination, smart one-page fallback, and export parity coverage in `tests/e2e/049-markdown-editor-cutover.spec.ts`

### Implementation for User Story 3

- [X] T038 [US3] Add paginated preview and page-break model types in `src/modules/resume/pagination/types.ts`
- [X] T039 [US3] Implement DOM-measured Markdown pagination helpers in `src/modules/resume/pagination/markdown-pages.ts`
- [X] T040 [US3] Re-export pagination helpers and preserve existing pagination API compatibility in `src/modules/resume/pagination/index.ts`
- [X] T041 [US3] Update `MarkdownResumeEditor` to measure rendered content, debounce pagination, and render ordered page containers in `src/modules/resume/v2/editor/MarkdownResumeEditor.tsx`
- [X] T042 [US3] Add multi-page A4 preview, page boundary, overflow warning, and print/export styles in `src/modules/resume/v2/editor/markdown-resume.css`
- [X] T043 [US3] Replace text-length smart one-page estimation with measured page counts in `src/modules/resume/v2/editor/MarkdownResumeEditor.tsx`
- [X] T044 [US3] Prevent smart one-page from clipping infeasible content and surface visible infeasible feedback in `src/modules/resume/pagination/smart-one-page.ts`
- [X] T045 [US3] Update export controls to wait for completed pagination and serialize all preview pages in `src/modules/resume/v2/editor/controls/ExportMenu.tsx`
- [X] T046 [US3] Update frontend export API types if paginated metadata is sent with PDF requests in `src/modules/resume/v2/api/index.ts`
- [X] T047 [US3] Update backend export tests for multi-page sanitized HTML if PDF payload shape changes in `backend/app/modules/resumes_v2/tests/test_export.py`

**Checkpoint**: User Story 3 is independently complete when the 3-page fixture renders all pages and exported PDF page count matches preview page count.

---

## Phase 6: User Story 4 - Safe Retirement of Legacy Resume Data (Priority: P2)

**Goal**: Older structured resumes remain accessible through the Markdown editor without exposing the legacy editor or losing visible content.

**Independent Test**: Open representative structured-only resumes. All non-empty visible text appears in Markdown or a clear conversion warning, and reopening does not duplicate content.

### Tests for User Story 4

- [X] T048 [P] [US4] Add structured-to-Markdown converter unit tests for basics, summary, experience, education, projects, skills, custom sections, and partial data in `src/modules/resume/converter/__tests__/legacy-to-markdown.test.ts`
- [X] T049 [P] [US4] Replace old 400-only legacy backend assertions with Markdown cutover expectations in `backend/app/modules/resumes_v2/tests/test_legacy_format.py`
- [X] T050 [P] [US4] Add frontend route/component tests for converted legacy resume hydration and warning display in `src/pages/__tests__/ResumeEditorV2.legacy-cutover.test.tsx`
- [X] T051 [P] [US4] Add Playwright legacy structured resume acceptance coverage in `tests/e2e/049-markdown-editor-cutover.spec.ts`

### Implementation for User Story 4

- [X] T052 [US4] Implement deterministic structured resume to Markdown conversion in `src/modules/resume/converter/legacy-to-markdown.ts`
- [X] T053 [US4] Export legacy conversion helpers for editor use in `src/modules/resume/converter/index.ts`
- [X] T054 [US4] Update backend GET behavior to return or stage convertible legacy content instead of a dead-end `LEGACY_FORMAT` response in `backend/app/modules/resumes_v2/api.py`
- [X] T055 [US4] Add backend conversion/recovery response shape support if needed in `backend/app/modules/resumes_v2/schemas.py`
- [X] T056 [US4] Hydrate converted Markdown, conversion warnings, and idempotency state in `src/pages/ResumeEditorV2.tsx`
- [X] T057 [US4] Persist converted Markdown without duplicating content on reopen in `src/modules/resume/v2/store/index.ts`
- [X] T058 [US4] Surface conversion warnings inside the Markdown editor route without offering legacy editing in `src/modules/resume/v2/editor/MarkdownResumeEditor.tsx`

**Checkpoint**: User Story 4 is independently complete when legacy fixtures open in Markdown mode with no dropped visible text and no repeated conversion.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, evidence, and requirement status updates after desired stories are complete.

- [X] T059 [P] Update resume renderer module documentation for contact rendering and pagination in `src/modules/resume/renderer/README.md`
- [X] T060 [P] Update pagination module documentation for measured Markdown page containers in `src/modules/resume/pagination/README.md`
- [X] T061 [P] Record contact and pagination evidence placeholders in `docs/evidence/049-markdown-editor-cutover/final-validation.md`
- [X] T062 Run targeted frontend unit tests from `specs/049-markdown-editor-cutover/quickstart.md` and record results in `docs/evidence/049-markdown-editor-cutover/final-validation.md`
- [X] T063 Run `npm run typecheck` and `npm run build`, then record results in `docs/evidence/049-markdown-editor-cutover/final-validation.md`
- [X] T064 Run `npm run e2e -- tests/e2e/049-markdown-editor-cutover.spec.ts --project=chromium` and save screenshots/PDF evidence under `docs/evidence/049-markdown-editor-cutover/`
- [X] T065 Run backend legacy/export tests if US4 or export payload changed and record results in `docs/evidence/049-markdown-editor-cutover/final-validation.md`
- [X] T066 Update requirement statuses and evidence links in `specs/049-markdown-editor-cutover/requirements-status.md`
- [X] T067 Update the active spec index after validation in `specs/README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Phase 1 and blocks all user stories.
- **User Stories (Phases 3-6)**: Depend on Phase 2.
- **Polish (Phase 7)**: Depends on all implemented stories and their validation evidence.

### User Story Dependencies

- **US1 Markdown-only editing (P1)**: Starts after Phase 2. MVP and product cutover foundation.
- **US2 Contact rendering (P1)**: Starts after Phase 2. Can run in parallel with US1 and US3 once shared types are ready.
- **US3 Multi-page rendering (P1)**: Starts after Phase 2. Can run in parallel with US2, but export parity should be checked again after US2 contact markup lands.
- **US4 Legacy data retirement (P2)**: Starts after Phase 2. Can run in parallel with US2/US3, but final route behavior should be reconciled with US1.

### Within Each User Story

- Write story tests first and confirm they fail for the intended reason.
- Implement the minimum code to pass the story tests.
- Validate the story independently at its checkpoint.
- Preserve previous story acceptance while adding later stories.

---

## Parallel Opportunities

- T002, T003, T004, T005, and T006 can run in parallel after T001.
- T008, T009, T011, and T012 can run in parallel after T007 is agreed.
- US1 tests T013, T014, and T015 can run in parallel.
- US2 tests T023, T024, and T025 can run in parallel.
- US3 tests T033, T034, T035, T036, and T037 can run in parallel.
- US4 tests T048, T049, T050, and T051 can run in parallel.
- Documentation/evidence tasks T059, T060, and T061 can run in parallel after story implementation.

---

## Parallel Example: User Story 1

```text
Task: T013 Add route/component test for Markdown editor hydration and restored settings in src/pages/__tests__/ResumeEditorV2.markdown-cutover.test.tsx
Task: T014 Add BuilderShell regression test proving legacy panels and dock controls are absent in src/modules/resume/v2/editor/__tests__/BuilderShell.markdown-cutover.test.tsx
Task: T015 Add Playwright entrypoint cutover coverage in tests/e2e/049-markdown-editor-cutover.spec.ts
```

## Parallel Example: User Story 2

```text
Task: T023 Add renderer unit tests for semantic contact row markup in src/modules/resume/renderer/__tests__/contact-container-rendering.test.ts
Task: T024 Add theme/component tests for wrapped contact rows across all three themes in src/modules/resume/v2/editor/__tests__/MarkdownResumeContactLayout.test.tsx
Task: T025 Add Playwright contact visual and PDF request assertions in tests/e2e/049-markdown-editor-cutover.spec.ts
```

## Parallel Example: User Story 3

```text
Task: T033 Add pagination unit tests for page state transitions and page break decisions in src/modules/resume/pagination/__tests__/markdown-pagination.test.ts
Task: T034 Add Markdown editor component tests for multi-page preview containers in src/modules/resume/v2/editor/__tests__/MarkdownResumePagination.test.tsx
Task: T036 Add API export payload tests for paginated HTML parity in src/modules/resume/v2/api/__tests__/export-v3.test.ts
```

## Parallel Example: User Story 4

```text
Task: T048 Add structured-to-Markdown converter unit tests in src/modules/resume/converter/__tests__/legacy-to-markdown.test.ts
Task: T049 Replace old 400-only legacy backend assertions in backend/app/modules/resumes_v2/tests/test_legacy_format.py
Task: T050 Add frontend route/component tests in src/pages/__tests__/ResumeEditorV2.legacy-cutover.test.tsx
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1 Markdown-only editing).
3. Stop and validate that every tested entry point opens the Markdown editor with no active legacy controls.

### P1 Completion

1. Add Phase 4 (US2 contact rendering) and validate contact screenshot/PDF parity.
2. Add Phase 5 (US3 multi-page rendering) and validate long-resume preview/export parity.
3. Re-run US1 acceptance after US2 and US3 because header/export/preview code is shared.

### P2 Completion

1. Add Phase 6 (US4 legacy data retirement).
2. Validate representative structured-only resumes and backend compatibility.
3. Run Phase 7 quality gates and update requirement statuses only after evidence exists.

---

## Summary

- Total tasks: 67
- Setup tasks: 6
- Foundational tasks: 6
- US1 tasks: 10
- US2 tasks: 10
- US3 tasks: 15
- US4 tasks: 11
- Polish tasks: 9
- Suggested MVP scope: Phase 1 + Phase 2 + Phase 3 (US1)

