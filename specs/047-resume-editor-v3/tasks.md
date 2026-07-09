# Tasks: Resume Editor v3 for InterCraft v2

**Input**: Design documents from `specs/047-resume-editor-v3/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required. The plan and constitution require test-first coverage for renderer, theme, line spacing, smart one-page, export, and cross-boundary editor behavior.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare reusable fixtures, evidence folders, and test helpers for the scoped v3 work.

- [X] T001 Create the format-lab fixture at `tests/e2e/fixtures/047-resume-editor-v3/format-lab.md` from `docs/evidence/v3-editor-research/muji-2026-07-06/sample-markdown-format-lab.md`
- [X] T002 Create one-page, near-one-page, and infeasible Markdown fixtures in `tests/e2e/fixtures/047-resume-editor-v3/smart-one-page-fixtures.ts`
- [X] T003 [P] Create renderer fixture copy in `src/modules/resume/renderer/__fixtures__/muji-format-lab.md`
- [X] T004 [P] Create feature evidence landing file in `docs/evidence/047-resume-editor-v3/README.md`
- [X] T005 [P] Create shared frontend test data helpers in `src/modules/resume/v2/editor/__tests__/resumeV3TestData.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared data shape, type contracts, and persistence hooks that every story depends on.

**Critical**: No user story implementation should begin until this phase is complete.

### Tests First

- [X] T006 [P] Add failing frontend metadata schema tests for Markdown source, three theme ids, line-height 12-25, and smart one-page state in `src/modules/resume/v2/schema/__tests__/markdown-metadata.test.ts`
- [X] T007 [P] Add failing backend metadata schema tests for preserving Markdown render settings in `backend/app/modules/resumes_v2/tests/test_markdown_metadata.py`
- [X] T008 [P] Add failing store tests for Markdown source edits, theme changes, manual line-height persistence, and smart override restoration in `src/modules/resume/v2/store/__tests__/markdown-settings.test.ts`

### Implementation

- [X] T009 Add Muji-compatible shared TypeScript types for `MujiThemeId`, `LineHeightPreset`, `ResumeRenderSettings`, and render warnings in `src/modules/resume/renderer/types.ts`
- [X] T010 Extend frontend `Metadata` and `resumeDataV2Schema` with a `markdown` settings object in `src/modules/resume/v2/schema/data.ts`
- [X] T011 Extend frontend defaults with initial Markdown source, `muji-default-autumn`, manual line-height 19, and smart one-page disabled in `src/modules/resume/v2/schema/defaults.ts`
- [X] T012 Extend backend `Metadata` and defaults with the same Markdown settings object in `backend/app/modules/resumes_v2/schemas.py` and `backend/app/modules/resumes_v2/defaults.py`
- [X] T013 Add store actions/selectors for `sourceMarkdown`, `themeId`, `manualLineHeight`, `smartOnePageEnabled`, `smartLineHeight`, and `effectiveLineHeight` in `src/modules/resume/v2/store/index.ts`
- [X] T014 [P] Re-export the v3 renderer/theme/pagination contracts from `src/modules/resume/index.ts`
- [X] T015 [P] Document the v3 module boundaries and fixture commands in `src/modules/resume/README.md`

**Checkpoint**: The resume document can persist Markdown source and render settings without breaking existing v2 data validation.

---

## Phase 3: User Story 1 - Markdown Resume Rendering (Priority: P1) - MVP

**Goal**: Users can write Markdown and see a faithful, Muji-compatible live resume preview.

**Independent Test**: Paste the format-lab Markdown fixture and verify H1/H2/H3, contact containers, icons, inline formats, blockquote, rule, lists, literal task-list text, table layout, external images, and unsafe fallback behavior render according to contract.

### Tests for User Story 1

- [X] T016 [P] [US1] Add failing renderer unit tests for the full Muji Markdown dialect in `src/modules/resume/renderer/__tests__/muji-markdown-dialect.test.ts`
- [X] T017 [P] [US1] Add failing renderer safety and fallback tests for unsafe links, raw HTML, local image paths, and unsupported syntax in `src/modules/resume/renderer/__tests__/muji-markdown-safety.test.ts`
- [X] T018 [P] [US1] Add failing Markdown editor/live preview component tests in `src/modules/resume/v2/editor/__tests__/MarkdownResumeEditor.test.tsx`
- [X] T019 [US1] Add failing E2E coverage for format-lab paste, live preview synchronization under one second, and unsupported syntax preservation in `tests/e2e/047-resume-editor-v3.spec.ts`

### Implementation for User Story 1

- [X] T020 [US1] Update `markdown-it` configuration and Muji plugin behavior for containers, icons, strikethrough, literal task-list text, tables, and external URL images in `src/modules/resume/renderer/parser.ts`
- [X] T021 [US1] Add render warnings, URL sanitization, and unsupported syntax fallback handling in `src/modules/resume/renderer/index.ts`
- [X] T022 [US1] Update container/icon plugin behavior needed by `::: left/right`, `icon:*`, and icon-prefixed links in `src/modules/resume/renderer/markdown-it-plugins/containers.ts`
- [X] T023 [US1] Create the Markdown-first editor and preview component in `src/modules/resume/v2/editor/MarkdownResumeEditor.tsx`
- [X] T024 [US1] Wire the Markdown editor into the existing v2 page shell in `src/modules/resume/v2/editor/BuilderShell.tsx`
- [X] T025 [US1] Ensure `ResumeEditorV2` hydrates Markdown metadata and falls back to defaults for older v2 resumes in `src/pages/ResumeEditorV2.tsx`
- [X] T026 [US1] Document supported Markdown syntax and fallback behavior in `src/modules/resume/renderer/README.md`

**Checkpoint**: US1 works independently with the default theme and no theme switching, line spacing controls, smart one-page, or export polish required.

---

## Phase 4: User Story 2 - Three Resume Themes (Priority: P1)

**Goal**: Users can switch among exactly three scoped Muji-compatible themes without changing Markdown source.

**Independent Test**: Apply 默认（秋风同款）, 极简色, and 平面大气主题 to the same Markdown fixture; verify source text is unchanged and H1/H2/body/list/table/icon rendering follows each observed pattern.

### Tests for User Story 2

- [X] T027 [P] [US2] Add failing theme registry tests for exactly three v3 themes and their display names/patterns in `src/modules/resume/themes/__tests__/muji-v3-themes.test.ts`
- [X] T028 [P] [US2] Add failing preview style tests for dark-header, minimal-line, and accent-band rendering in `src/modules/resume/v2/editor/__tests__/MarkdownResumePreviewThemes.test.tsx`
- [X] T029 [US2] Add failing E2E coverage for theme switching, source preservation, and PDF-ready active theme classes in `tests/e2e/047-resume-editor-v3.spec.ts`

### Implementation for User Story 2

- [X] T030 [US2] Split the theme registry so v3 selectors expose exactly `muji-default-autumn`, `muji-minimal-color`, and `muji-flat-atmospheric` while legacy callers remain stable in `src/modules/resume/themes/registry.ts`
- [X] T031 [P] [US2] Add Muji default autumn theme CSS in `public/themes/muji-default-autumn.css`
- [X] T032 [P] [US2] Add Muji minimal color theme CSS in `public/themes/muji-minimal-color.css`
- [X] T033 [P] [US2] Add Muji flat atmospheric theme CSS in `public/themes/muji-flat-atmospheric.css`
- [X] T034 [US2] Update theme loading helpers and public exports for v3 theme ids in `src/modules/resume/themes/index.ts`
- [X] T035 [US2] Create the v3 theme menu control in `src/modules/resume/v2/editor/controls/ThemeMenu.tsx`
- [X] T036 [US2] Wire theme selection, source preservation, and persistence through `src/modules/resume/v2/editor/BuilderShell.tsx`
- [X] T037 [US2] Document the three theme patterns and evidence mapping in `src/modules/resume/themes/README.md`

**Checkpoint**: US2 works independently on top of US1; theme changes preserve Markdown source and render all supported syntax.

---

## Phase 5: User Story 3 - Line Spacing Adjustment (Priority: P1)

**Goal**: Users can choose Muji-compatible integer line spacing presets from 12 through 25 and see the preview update immediately.

**Independent Test**: Select line-height 12, 19, and 25 and compare body text, lists, and tables while section heading decoration remains coherent.

### Tests for User Story 3

- [X] T038 [P] [US3] Add failing line-height preset and effective-line-height unit tests in `src/modules/resume/pagination/__tests__/line-height-presets.test.ts`
- [X] T039 [P] [US3] Add failing line spacing control component tests in `src/modules/resume/v2/editor/__tests__/LineSpacingControl.test.tsx`
- [X] T040 [US3] Add failing E2E coverage for line-height menu values 12-25 and before/after preview density in `tests/e2e/047-resume-editor-v3.spec.ts`

### Implementation for User Story 3

- [X] T041 [US3] Add `LINE_HEIGHT_PRESETS`, `DEFAULT_LINE_HEIGHT`, and validation helpers in `src/modules/resume/pagination/line-height.ts`
- [X] T042 [US3] Create the line spacing control in `src/modules/resume/v2/editor/controls/LineSpacingControl.tsx`
- [X] T043 [US3] Apply `height12` through `height25` classes and CSS variables to the Markdown preview root in `src/modules/resume/v2/editor/MarkdownResumeEditor.tsx`
- [X] T044 [US3] Add line-height class rules for body text, lists, and tables in `public/themes/muji-default-autumn.css`, `public/themes/muji-minimal-color.css`, and `public/themes/muji-flat-atmospheric.css`
- [X] T045 [US3] Persist manual line-height updates only when smart one-page is off in `src/modules/resume/v2/store/index.ts`

**Checkpoint**: US3 works independently on top of US1; manual line spacing persists and visibly affects body/list/table density.

---

## Phase 6: User Story 4 - Smart One-Page (Priority: P1)

**Goal**: Users can enable smart one-page mode, which temporarily chooses a safe one-page layout when feasible and restores manual line spacing when disabled.

**Independent Test**: Toggle smart one-page for already-fitting, near-fitting, and infeasible fixtures; verify content is never hidden or deleted, status is visible, and manual line spacing restores on disable.

### Tests for User Story 4

- [X] T046 [P] [US4] Add failing smart one-page algorithm tests for `already-fit`, `fit`, and `infeasible` statuses in `src/modules/resume/pagination/__tests__/smart-one-page.test.ts`
- [X] T047 [P] [US4] Add failing smart one-page toggle and restore component tests in `src/modules/resume/v2/editor/__tests__/SmartOnePageControl.test.tsx`
- [X] T048 [US4] Add failing E2E coverage for already-fit, near-fit, infeasible, and manual-line-height restoration scenarios in `tests/e2e/047-resume-editor-v3.spec.ts`

### Implementation for User Story 4

- [X] T049 [US4] Implement safe line-height fitting and status selection in `src/modules/resume/pagination/smart-one-page.ts`
- [X] T050 [US4] Create the smart one-page toggle control in `src/modules/resume/v2/editor/controls/SmartOnePageControl.tsx`
- [X] T051 [US4] Store previous manual line-height, selected smart line-height, and status transitions in `src/modules/resume/v2/store/index.ts`
- [X] T052 [US4] Integrate DOM measurement and recomputation after Markdown/theme/spacing changes in `src/modules/resume/v2/editor/MarkdownResumeEditor.tsx`
- [X] T053 [US4] Surface active, already-fit, fit, and infeasible messages in `src/modules/resume/v2/editor/controls/SmartOnePageControl.tsx`

**Checkpoint**: US4 works independently on top of US1 and US3; smart mode never deletes content and manual spacing is restored after disabling.

---

## Phase 7: User Story 5 - PDF and Markdown Export (Priority: P1)

**Goal**: Users can export the current resume as PDF or Markdown with clear pending, success, and failure states.

**Independent Test**: Export the same Markdown under each theme and line-height state; verify PDF receives current rendered preview HTML and Markdown export preserves source.

### Tests for User Story 5

- [X] T054 [P] [US5] Add failing Markdown export preservation tests for source, containers, icons, tables, and external image syntax in `src/modules/resume/converter/__tests__/markdown-export-v3.test.ts`
- [X] T055 [P] [US5] Add failing PDF export request tests for current HTML, active theme, effective line-height, and smart one-page state in `src/modules/resume/v2/api/__tests__/export-v3.test.ts`
- [X] T056 [US5] Add failing E2E coverage for Markdown download, PDF download, pending state, failure message, and source preservation in `tests/e2e/047-resume-editor-v3.spec.ts`

### Implementation for User Story 5

- [X] T057 [US5] Extend export types to include Markdown export results while keeping binary PDF export stable in `src/modules/resume/v2/api/index.ts`
- [X] T058 [US5] Implement preserved-source Markdown download for v3 metadata in `src/modules/resume/converter/markdown-export.ts`
- [X] T059 [US5] Create the v3 PDF/Markdown export menu in `src/modules/resume/v2/editor/controls/ExportMenu.tsx`
- [X] T060 [US5] Wire header export actions to current Markdown source, active theme, effective line-height, and smart one-page state in `src/modules/resume/v2/editor/Header.tsx`
- [X] T061 [US5] Ensure export pending, success, and failure feedback is visible and source-safe in `src/modules/resume/v2/editor/Header.tsx`
- [X] T062 [US5] Update backend export tests only if the PDF render request contract changes beyond existing HTML binary export in `backend/app/modules/resumes_v2/tests/test_export.py`

**Checkpoint**: US5 works independently on top of US1, US2, US3, and US4; Markdown export preserves source and PDF export matches the live preview contract.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, evidence, docs, and status tracking across all stories.

- [X] T063 [P] Update quickstart validation details and commands in `specs/047-resume-editor-v3/quickstart.md`
- [X] T064 [P] Update requirement traceability after implementation in `specs/047-resume-editor-v3/requirements-status.md`
- [X] T065 [P] Capture final screenshots, traces, and export artifacts in `docs/evidence/047-resume-editor-v3/final-validation.md`
- [X] T066 Run `npm run typecheck` and record results in `docs/evidence/047-resume-editor-v3/final-validation.md`
- [X] T067 Run `npm run test` and record results in `docs/evidence/047-resume-editor-v3/final-validation.md`
- [X] T068 Run `npm run build` and record results in `docs/evidence/047-resume-editor-v3/final-validation.md`
- [X] T069 Run `npm run e2e -- tests/e2e/047-resume-editor-v3.spec.ts` and record results in `docs/evidence/047-resume-editor-v3/final-validation.md`
- [X] T070 Run `cd backend && uv run pytest -q app/modules/resumes_v2/tests/test_markdown_metadata.py app/modules/resumes_v2/tests/test_export.py` and record results in `docs/evidence/047-resume-editor-v3/final-validation.md`
- [X] T071 Update feature status in `specs/README.md` after implementation and validation evidence exists

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **US1 Markdown Rendering**: Depends on Phase 2 and is the MVP slice.
- **US2 Themes**: Depends on Phase 2 and US1 preview rendering.
- **US3 Line Spacing**: Depends on Phase 2 and US1 preview rendering.
- **US4 Smart One-Page**: Depends on Phase 2, US1 preview rendering, and US3 line-height helpers.
- **US5 Export**: Depends on US1 for Markdown/HTML output and should include US2/US3/US4 state when those stories are enabled.
- **Polish**: Depends on all desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: First MVP; no dependency on other stories after foundation.
- **US2 (P1)**: Can start after US1 render root exists.
- **US3 (P1)**: Can start after US1 render root exists.
- **US4 (P1)**: Starts after US3 line-height helpers because smart one-page selects an effective line-height.
- **US5 (P1)**: Starts after US1; full acceptance requires US2, US3, and US4 state parity.

### Within Each User Story

- Write tests first and confirm they fail for the intended reason.
- Implement the smallest code needed for the tests to pass.
- Re-run story-specific unit/component tests before adding E2E assertions.
- Keep source Markdown preservation checks in every story that changes UI state.

---

## Parallel Opportunities

- Phase 1 fixture/evidence tasks T003-T005 can run in parallel.
- Foundation tests T006-T008 can run in parallel, then implementation T009-T015 should be coordinated around shared schema/store files.
- US1 unit and component tests T016-T018 can run in parallel; T019 should be serialized with later edits to `tests/e2e/047-resume-editor-v3.spec.ts`.
- US2 CSS tasks T031-T033 can run in parallel after T030 defines final theme ids.
- US3 tests T038-T039 can run in parallel before T041-T045.
- US4 tests T046-T047 can run in parallel before T049-T053.
- US5 tests T054-T055 can run in parallel before T057-T062.
- Polish evidence/doc tasks T063-T065 can run in parallel after implementation, while validation commands T066-T070 should run serially.

---

## Parallel Example: US1

```text
Task: "T016 [P] [US1] Add renderer unit tests in src/modules/resume/renderer/__tests__/muji-markdown-dialect.test.ts"
Task: "T017 [P] [US1] Add safety tests in src/modules/resume/renderer/__tests__/muji-markdown-safety.test.ts"
Task: "T018 [P] [US1] Add editor component tests in src/modules/resume/v2/editor/__tests__/MarkdownResumeEditor.test.tsx"
```

## Parallel Example: US2

```text
Task: "T031 [P] [US2] Add Muji default autumn theme CSS in public/themes/muji-default-autumn.css"
Task: "T032 [P] [US2] Add Muji minimal color theme CSS in public/themes/muji-minimal-color.css"
Task: "T033 [P] [US2] Add Muji flat atmospheric theme CSS in public/themes/muji-flat-atmospheric.css"
```

## Parallel Example: US5

```text
Task: "T054 [P] [US5] Add Markdown export tests in src/modules/resume/converter/__tests__/markdown-export-v3.test.ts"
Task: "T055 [P] [US5] Add PDF export request tests in src/modules/resume/v2/api/__tests__/export-v3.test.ts"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 Markdown rendering.
3. Stop and validate the format-lab fixture in preview before implementing controls.

### Incremental Delivery

1. Add US2 themes and validate source preservation.
2. Add US3 line spacing and validate 12, 19, 25 density changes.
3. Add US4 smart one-page and validate override/restore behavior.
4. Add US5 export and validate PDF/Markdown parity.
5. Finish Phase 8 evidence and status updates.

### Validation Commands

```bash
npm run typecheck
npm run test
npm run build
npm run e2e -- tests/e2e/047-resume-editor-v3.spec.ts
cd backend && uv run pytest -q app/modules/resumes_v2/tests/test_markdown_metadata.py app/modules/resumes_v2/tests/test_export.py
```

---

## Notes

- `[P]` tasks touch different files and can run in parallel after their dependencies are met.
- `[US#]` labels map directly to the five user stories in `spec.md`.
- Existing pre-047 requirements remain sealed v1/baseline material unless this task list explicitly reintroduces behavior.
- Do not add local image upload or crop tools in this scope.
- User-facing copy should not expose internal labels such as "v3".
