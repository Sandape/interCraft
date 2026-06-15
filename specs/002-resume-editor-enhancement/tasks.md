# Tasks: Resume Editor Enhancement

**Input**: Design documents from `/specs/002-resume-editor-enhancement/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/pdf-service.md, quickstart.md

**Tests**: Included per Constitution Principle III (Test-First — NON-NEGOTIABLE). Tests MUST be written and FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend**: `src/` at repository root
- **Backend**: `backend/src/services/pdf_renderer/`
- **Tests**: `tests/unit/`, `tests/component/`, `tests/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install dependencies, apply database migration, scaffold new module directories

- [x] T001 Install frontend Markdown editor dependencies: `npm install @monaco-editor/react react-markdown remark-gfm remark-parse remark-frontmatter rehype-raw unified`
- [x] T002 [P] Install Python PDF service dependencies: `cd backend && uv pip install playwright markdown pyyaml && playwright install chromium`
- [x] T003 [P] Create module directory structure under `src/lib/markdown-converter.ts`, `src/lib/resume-styles/`, `src/lib/export/`, `src/components/resume/editor/`, `src/components/resume/export/`, `src/components/resume/import/`, `src/components/resume/list/`
- [x] T004 [P] Create backend PDF renderer directory structure under `backend/src/services/pdf_renderer/` with `__init__.py`, `renderer.py`, `server.py`, `templates/`, `styles/`
- [x] T005 Apply database migration: add `style_preference VARCHAR(64) NOT NULL DEFAULT 'compact-one-page'` column to `resume_branches` table

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared modules that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 [P] Implement block → Markdown serialization (Quick → WYSIWYG) in `src/lib/markdown-converter.ts` (export function `blocksToMarkdown(branch: ResumeBranch, blocks: ResumeBlock[]): string`)
- [x] T007 [P] Implement Markdown → block parsing (WYSIWYG → Quick) in `src/lib/markdown-converter.ts` (export function `markdownToBlocks(markdown: string): ParsedBlock[]`)
- [x] T008 [P] Define style registry with 2 styles and their metadata in `src/lib/resume-styles/index.ts`
- [x] T009 [P] Create style CSS file for "紧凑一页" (Compact One-Page) style in `src/styles/resume-compact-one-page.css`
- [x] T010 [P] Create style CSS file for "现代双栏" (Modern Two-Column) style in `src/styles/resume-modern-two-column.css`
- [x] T011 [P] Scaffold PDF rendering server with FastAPI in `backend/src/services/pdf_renderer/server.py` (health endpoint, basic structure)
- [x] T012 [P] Copy style CSS files to backend: `backend/src/services/pdf_renderer/styles/compact-one-page.css` and `backend/src/services/pdf_renderer/styles/modern-two-column.css`
- [x] T013 [P] Write unit tests for blocksToMarkdown conversion in `tests/unit/markdown-converter.test.ts`
- [x] T014 [P] Write unit tests for markdownToBlocks parsing in `tests/unit/markdown-parser.test.ts`

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 — WYSIWYG Resume Editing (Priority: P1) 🎯 MVP

**Goal**: Users can toggle between Quick Mode and WYSIWYG Mode (split-pane: left Markdown editor + right live A4 preview). Content preserved in both directions.

**Independent Test**: Open resume editor, toggle to WYSIWYG mode, type in left editor, verify right preview updates within 1s, toggle back to Quick Mode, verify blocks are correctly recreated.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T015 [P] [US1] Write component test for MarkdownEditor (Monaco wrapper) in `tests/component/MarkdownEditor.test.tsx`
- [ ] T016 [P] [US1] Write component test for ResumePreview (A4 preview pane) in `tests/component/ResumePreview.test.tsx`
- [ ] T017 [P] [US1] Write component test for WysiwygEditor (split-pane container) in `tests/component/WysiwygEditor.test.tsx`
- [ ] T018 [US1] Write integration test for mode toggle (Quick ↔ WYSIWYG data integrity) in `tests/component/ModeToggle.test.tsx` (depends on T006, T007)

### Implementation for User Story 1

- [x] T019 [P] [US1] Implement MarkdownEditor component (Monaco editor wrapper with markdown language) in `src/components/resume/editor/MarkdownEditor.tsx`
- [x] T020 [P] [US1] Implement ResumePreview component (react-markdown with A4 page container and selected style CSS) in `src/components/resume/editor/ResumePreview.tsx`
- [x] T021 [US1] Implement WysiwygEditor component (split-pane: MarkdownEditor left + ResumePreview right, handles content state) in `src/components/resume/editor/WysiwygEditor.tsx`
- [x] T022 [US1] Implement mode toggle logic: aggregate blocks → Markdown on switch to WYSIWYG, parse Markdown → blocks on switch to Quick in `src/components/resume/editor/useModeToggle.ts`
- [x] T023 [US1] Implement UnifiedToolbar component (mode toggle segmented control, export button placeholder, style selector placeholder, version controls) in `src/components/resume/editor/UnifiedToolbar.tsx`
- [x] T024 [US1] Refactor existing Quick Mode block editor into `src/components/resume/editor/QuickEditor.tsx` (extract BlockRow + block list logic from ResumeEditor page, keep auto-save intact)
- [x] T025 [US1] Update ResumeEditor page to use UnifiedToolbar + conditional rendering of QuickEditor vs WysiwygEditor based on mode state in `src/pages/ResumeEditor.tsx`

**Checkpoint**: WYSIWYG editing fully functional — type in left, see preview on right, toggle back to Quick Mode

---

## Phase 4: User Story 2 — Resume Export (Priority: P1)

**Goal**: Users can export resume as Markdown (.md), PDF (.pdf via server-side Puppeteer), PNG, and JPEG at 2x resolution.

**Independent Test**: In editor, click export → select format → verify browser downloads correct file with correct content.

### Tests for User Story 2

- [ ] T026 [P] [US2] Write unit test for Markdown export logic in `tests/unit/markdown-export.test.ts`
- [ ] T027 [P] [US2] Write unit test for export hook (useExport) in `tests/unit/useExport.test.ts`
- [ ] T028 [P] [US2] Write API contract test for PDF rendering endpoint in `tests/contract/test-pdf-service.spec.ts`
- [ ] T029 [P] [US2] Write backend unit test for Puppeteer renderer in `backend/tests/test_pdf_renderer.py`

### Implementation for User Story 2

- [ ] T030 [P] [US2] Implement Markdown export (aggregate blocks → .md file download) in `src/lib/export/markdown-export.ts`
- [ ] T031 [P] [US2] Implement export API client (POST /api/export/render with markdown + style_id + format) in `src/api/export.ts`
- [ ] T032 [US2] Implement useExport hook (orchestrates export flow, handles loading/error/download states) in `src/hooks/useExport.ts`
- [ ] T033 [US2] Implement ExportMenu dropdown component (format selection: Markdown / PDF / PNG / JPEG) in `src/components/resume/export/ExportMenu.tsx`
- [ ] T034 [US2] Implement PDF/Image export via server-side Puppeteer renderer in `backend/src/services/pdf_renderer/renderer.py` (Markdown → HTML template with style CSS → Puppeteer page.pdf / page.screenshot at 2x)
- [ ] T035 [US2] Implement POST /api/export/render endpoint in `backend/src/services/pdf_renderer/server.py` (accepts markdown + style_id + format, calls renderer, returns binary)
- [ ] T036 [US2] Integrate ExportMenu into UnifiedToolbar (export button triggers dropdown) in `src/components/resume/editor/UnifiedToolbar.tsx`
- [ ] T037 [US2] Add empty-content guard: show "简历内容为空，无法导出" when no blocks exist, disable export button

**Checkpoint**: All 4 export formats working — Markdown, PDF, PNG, JPEG

---

## Phase 5: User Story 3 — Markdown Resume Import (Priority: P2)

**Goal**: Users can import a .md file, system parses Markdown into blocks and creates a new branch.

**Independent Test**: On resume list page, click import, select .md file, verify branch created with correct block types.

### Tests for User Story 3

- [ ] T038 [P] [US3] Write unit test for Markdown import parser (remark-parse → blocks mapping) in `tests/unit/markdown-import.test.ts`
- [ ] T039 [P] [US3] Write component test for ImportModal in `tests/component/ImportModal.test.tsx`

### Implementation for User Story 3

- [ ] T040 [P] [US3] Implement Markdown import parser (file read → remark-parse AST → heuristic block type detection → ParsedBlock[]) in `src/lib/markdown-parser.ts`
- [ ] T041 [US3] Implement ImportModal component (file picker, branch name input pre-filled, validation, create branch flow) in `src/components/resume/import/ImportModal.tsx`
- [ ] T042 [US3] Add "导入 Markdown" button to resume list page in `src/pages/ResumeList.tsx`
- [ ] T043 [US3] Handle edge cases: invalid file type (.md only), oversized file (>100KB), empty file, unsupported syntax fallback to custom block

**Checkpoint**: Markdown import working — external .md files can be imported as resume branches

---

## Phase 6: User Story 4 — Primary Resume Prominent Card (Priority: P2)

**Goal**: Main resume displayed as a full-width horizontal card above the feature branch grid, with metadata + text preview excerpt.

**Independent Test**: Visit resume list page, verify main resume shown as large horizontal card at top, distinct from grid cards below.

### Tests for User Story 4

- [ ] T044 [P] [US4] Write component test for PrimaryResumeCard in `tests/component/PrimaryResumeCard.test.tsx`

### Implementation for User Story 4

- [ ] T045 [P] [US4] Implement PrimaryResumeCard component (full-width card with: name, status badge, company/position, last edited, block count, first 150 chars of content preview, "主简历 (数据源)" label) in `src/components/resume/list/PrimaryResumeCard.tsx`
- [ ] T046 [US4] Update ResumeList page: render PrimaryResumeCard above the grid if a main resume exists, hide if no main resume, keep existing grid for derived branches in `src/pages/ResumeList.tsx`
- [ ] T047 [US4] Add visual separator between primary card and grid (e.g., section header "派生简历" with count)

**Checkpoint**: Main resume prominently displayed, visually distinct from derived branch grid

---

## Phase 7: User Story 5 — Resume Style Switching (Priority: P2)

**Goal**: Users can switch between 2 minimalist resume styles (Compact One-Page / Modern Two-Column) with live preview update, per-branch persistence.

**Independent Test**: In editor, switch style in selector, verify preview re-renders immediately, navigate away and back, verify style remembered per branch.

### Tests for User Story 5

- [ ] T048 [P] [US5] Write unit test for useStylePreference hook in `tests/unit/useStylePreference.test.ts`
- [ ] T049 [P] [US5] Write component test for StyleSelector in `tests/component/StyleSelector.test.tsx`

### Implementation for User Story 5

- [ ] T050 [P] [US5] Implement useStylePreference hook (read/write style_preference per branch, persist to API via patchBranch) in `src/hooks/useStylePreference.ts`
- [ ] T051 [US5] Implement StyleSelector dropdown component (shows current style name, dropdown with 2 style options with labels + descriptions) in `src/components/resume/editor/StyleSelector.tsx`
- [ ] T052 [US5] Create HTML page templates for backend rendering: `backend/src/services/pdf_renderer/templates/compact-one-page.html` and `backend/src/services/pdf_renderer/templates/modern-two-column.html`
- [ ] T053 [US5] Update ResumePreview to apply selected style CSS dynamically (import both CSS files, apply class based on style state) in `src/components/resume/editor/ResumePreview.tsx`
- [ ] T054 [US5] Integrate StyleSelector into UnifiedToolbar (style selector dropdown next to mode toggle) in `src/components/resume/editor/UnifiedToolbar.tsx`
- [ ] T055 [US5] Ensure style selection persists per branch across sessions (hook reads `style_preference` on mount, writes on change)

**Checkpoint**: Style switching fully functional — preview updates instantly, selection remembered per branch

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, E2E validation, final hardening

- [ ] T056 [P] Write E2E test for WYSIWYG editing + mode toggle in `tests/e2e/resume-editor.spec.ts`
- [ ] T057 [P] Write E2E test for export flow (all 4 formats) in `tests/e2e/resume-export.spec.ts`
- [ ] T058 [P] Write E2E test for import flow in `tests/e2e/resume-import.spec.ts`
- [ ] T059 [P] Write E2E test for style switching + persistence in `tests/e2e/resume-styles.spec.ts`
- [ ] T060 Handle PDF service unavailable gracefully (show user-friendly message, Markdown export still works as fallback)
- [ ] T061 Ensure lock indicator works correctly in WYSIWYG mode (readonly blocks editing in both left editor and mode toggle)
- [ ] T062 Run quickstart.md validation scenarios VS-1 through VS-11

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 — WYSIWYG (Phase 3)**: Depends on Foundational (Phase 2)
- **US2 — Export (Phase 4)**: Depends on Foundational (Phase 2); integrates with US1 via UnifiedToolbar
- **US3 — Import (Phase 5)**: Depends on Foundational (Phase 2)
- **US4 — Primary Card (Phase 6)**: Depends on Foundational (Phase 2)
- **US5 — Style Switching (Phase 7)**: Depends on Foundational (Phase 2); integrates with US1 (preview) and US2 (export)
- **Polish (Phase 8)**: Depends on all desired user stories

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — No dependencies on other stories
- **US2 (P1)**: Can start after Foundational — Shares UnifiedToolbar with US1 (T036 needs T023)
- **US3 (P2)**: Can start after Foundational — Fully independent
- **US4 (P2)**: Can start after Foundational — Fully independent
- **US5 (P2)**: Can start after Foundational — Integrates with US1/US2 preview and export

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/libraries before components
- Components before page integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- Phase 2: T006, T007, T008, T009, T010, T011, T012 can all start in parallel; T013-T014 after T006-T007
- Once Foundational completes: US1, US2, US3, US4, US5 can all start in parallel (by different developers)
- Within each US: all test tasks [P] can run in parallel; many implementation tasks also [P]
- Phase 8: all E2E tests [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Step 1: Launch all US1 tests together (they FAIL first):
Task: "T015 [P] [US1] Component test for MarkdownEditor in tests/component/MarkdownEditor.test.tsx"
Task: "T016 [P] [US1] Component test for ResumePreview in tests/component/ResumePreview.test.tsx"
Task: "T017 [P] [US1] Component test for WysiwygEditor in tests/component/WysiwygEditor.test.tsx"

# Step 2: Launch independent components together:
Task: "T019 [P] [US1] Implement MarkdownEditor in src/components/resume/editor/MarkdownEditor.tsx"
Task: "T020 [P] [US1] Implement ResumePreview in src/components/resume/editor/ResumePreview.tsx"
Task: "T023 [US1] Implement UnifiedToolbar in src/components/resume/editor/UnifiedToolbar.tsx"

# Step 3: Integration (depends on T019, T020):
Task: "T021 [US1] Implement WysiwygEditor in src/components/resume/editor/WysiwygEditor.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (WYSIWYG Editing)
4. **STOP and VALIDATE**: Toggle modes, edit in WYSIWYG, verify data integrity
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1: WYSIWYG Editing → **MVP!** Users can edit with live preview
3. Add US2: Export → Users can download resumes in all formats
4. Add US5: Style Switching → Visual variety for exported/previewed resumes
5. Add US4: Primary Card → Better resume list UX
6. Add US3: Import → External Markdown migration
7. Each story adds value without breaking previous stories

### Recommended MVP Order (considering integration)

US1 → US2 + US5 together (preview + style + export are tightly coupled) → US4 → US3

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- **Verify tests fail before implementing** (Constitution III)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US2 (export) backend work (T034, T035) can be done in parallel with frontend export work (T030-T033)
- US5 style CSS files must be kept in sync between frontend (`src/styles/`) and backend (`backend/.../styles/`)
