# Tasks: Resume Renderer v2

**Input**: Design documents from `/specs/032-resume-renderer-v2/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The Constitution (Principle III — TDD non-negotiable) mandates test-first. Every story phase lists tests BEFORE implementation tasks.

**Organization**: Tasks are grouped by user story (17 stories, US1–US17) to enable independent implementation and testing.

**Reactive-resume source reference**: Tasks cite specific files under `D:\Project\reactive-resume\` so implementers can borrow patterns verbatim. Reference column uses `RR:` prefix.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend**: `src/` (eGGG project root; NOT `frontend/src/`)
- **Backend**: `backend/app/modules/resumes_v2/`
- **Tests**: `tests/e2e/032-resume-renderer-v2/` (Playwright) + `backend/app/modules/resumes_v2/tests/` (pytest) + `src/modules/resume/v2/__tests__/` (Vitest)

## Phase ↔ User Story Mapping

| Phase | US | Priority | Task Range |
|---|---|---|---|
| 1 | (Setup) | — | T001–T005 |
| 2 | (Foundational) | — | T006–T015 |
| 3 | US1 | P1 🎯 MVP | T016–T028 |
| 4 | US2 | P1 | T029–T048 |
| 5 | US3 | P1 | T049–T057 |
| 6 | US5 | P1 | T058–T065 |
| 7 | US6 | P1 | T066–T072 |
| 8 | US7 | P1 | T073–T079 |
| 9 | US4 | P1 | T080–T087 |
| 10 | US9 | P1 | T088–T096 |
| 11 | US10 | P1 | T097–T107 |
| 12 | US12 | P1 | T108–T120 |
| 13 | US15 | P1 | T121–T127 |
| 14 | US8 | P2 | T128–T135 |
| 15 | US11 | P2 | T136–T147 |
| 16 | US14 | P2 | T148–T155 |
| 17 | US16 | P2 | T156–T161 |
| 18 | US17 | P2 | T162–T170 |
| 19 | US13 | P3 | T171–T176 |
| 20 | (Polish) | — | T177–T193 |

**Note**: US 编号在 spec.md 中按 1,2,...,14,16,17,15 顺序 (US15 在最后);Phase 编号严格递增,通过本表映射到 US。

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency wiring. No business logic yet.

- [x] T001 Add 8 new npm dependencies to `package.json`: `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-link`, `@tiptap/extension-highlight`, `@tiptap/extension-text-align`, `react-resizable-panels`, `immer`, `zod`. Run `npm install`. Verify lockfile updates.
- [x] T002 [P] Install Playwright Chromium browser: `npx playwright install chromium` (already configured in `@playwright/test` 1.60)
- [x] T003 [P] Create directory skeleton for `backend/app/modules/resumes_v2/` with empty `__init__.py`, `README.md` stub, `tests/__init__.py`
- [x] T004 [P] Create directory skeleton for `src/modules/resume/v2/` with empty `index.ts`, `__tests__/` dir
- [x] T005 [P] Create E2E test directory `tests/e2e/032-resume-renderer-v2/` with `.gitkeep`

**Checkpoint**: Directory skeleton in place; deps installed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 Port reactive-resume Zod schema to `src/modules/resume/v2/schema/data.ts` (RR: `packages/schema/src/resume/data.ts`, 683 lines). Drop `cover-letter` from `sectionTypeSchema`. Map Phosphor icon names to lucide-react in a sibling `icon-crosswalk.ts`. Export all types: `ResumeDataV2`, `Metadata`, `Basics`, `SectionType`, `StyleRule`, `StyleIntent`, `StyleSlot`, etc.
- [x] T007 [P] Port default resume data to `src/modules/resume/v2/schema/defaults.ts` (RR: `packages/schema/src/resume/default.ts`, 170 lines). Map Phosphor section icons to lucide names: `briefcase`, `graduation-cap`, `code`, `wrench`, `languages`, `heart`, `trophy`, `award`, `book-open`, `hand-heart`, `phone`, `link`.
- [x] T008 [P] Port style-rule resolver to `src/modules/resume/v2/schema/style-rules.ts` (RR: `packages/schema/src/resume/style-rules.ts`, 74 lines). Implement `resolveStyleIntentForSlot(data, { slot, sectionId, sectionType })` with `specificity = { global: 0, sectionType: 1, sectionId: 2 }` and `Object.assign` merge.
- [x] T009 [P] Port sample resume data to `src/modules/resume/v2/schema/sample.ts` (RR: `packages/schema/src/resume/sample.ts`, 602 lines). Used by Template Gallery previews and the "load sample" affordance.
- [x] T010 [P] Create Alembic migration `backend/alembic/versions/0022_032_resumes_v2.py` creating 3 tables (`resumes_v2`, `resume_statistics_v2`, `resume_analysis_v2`) per `data-model.md` §2, §4, §5. Include indexes, UNIQUE(user_id, slug), CHECK constraint `password_hash IS NULL OR is_public = true`, RLS policy, BEFORE UPDATE trigger to bump `updated_at`. Run `cd backend && uv run alembic upgrade head` to verify.
- [x] T011 Create SQLAlchemy ORM models in `backend/app/modules/resumes_v2/models.py` for all 3 tables. Reuse `UUIDv7PrimaryKeyMixin`, `TenantScopedMixin`, `TimestampedMixin` from `app.domain.mixins` (same as `resumes/models.py`). Add `version: Mapped[int]` column with default 0.
- [x] T012 [P] Create Pydantic v2 schemas in `backend/app/modules/resumes_v2/schemas.py`: `ResumeDataV2Pydantic` (mirror of frontend Zod), `ResumeV2Out`, `ResumeV2CreateIn`, `ResumeV2UpdateIn`, `ResumeV2DuplicateOut`, `SharingIn`, `LockIn`, `AnalysisOut`. All must round-trip through the JSON Schema in `contracts/02-resume-data-schema.md`.
- [x] T013 Create async repository in `backend/app/modules/resumes_v2/repository.py`: `get`, `list`, `create`, `update_with_version` (returns `None` on conflict), `soft_delete`, `duplicate`, `set_lock`, `set_sharing`. Use SQLAlchemy 2.0 `select()` + `update()` patterns. No ad-hoc SQL per Constitution.
- [x] T014 Create FastAPI router skeleton in `backend/app/modules/resumes_v2/api.py` with empty handlers for all 14 endpoints listed in `contracts/01-rest-api.md` §1–5. Mount under `/api/v1/v2` in `backend/app/main.py`. Return 501 Not Implemented stubs.
- [x] T015 [P] Create stub README at `backend/app/modules/resumes_v2/README.md` with placeholder sections (purpose, public API surface, config vars, example curl). Full content authored in T179 (Polish phase). Required by Constitution Principle I.

**Checkpoint**: Foundation ready — DB tables exist, schemas ported, router mounted. User story implementation can now begin.

---

## Phase 3: User Story 1 - JSON Schema 数据模型与结构化 sections (Priority: P1) 🎯 MVP

**Goal**: New `resumes_v2` table stores a `ResumeDataV2` JSON document with 12 typed sections + custom sections. API supports create/read/update with optimistic concurrency.

**Independent Test**: Create a v2 resume via API, PUT a new `experience` item, GET it back — all fields round-trip. Two parallel PUTs with same `If-Match` → second returns 409 with `latest_data`.

### Tests for User Story 1

- [x] T016 [P] [US1] Write pytest `backend/app/modules/resumes_v2/tests/test_models.py` covering: table columns, RLS policy active, `version` default 0, `password_hash` nullable constraint, cascade delete on user delete.
- [x] T017 [P] [US1] Write pytest `backend/app/modules/resumes_v2/tests/test_repository.py` covering: create + get round-trip, `update_with_version` happy path (version bumps), `update_with_version` conflict path (returns None on stale version), `duplicate` copies data + resets public/lock, `soft_delete` cascades to statistics + analysis.
- [x] T018 [P] [US1] Write pytest `backend/app/modules/resumes_v2/tests/test_api.py` covering: POST 201 create, GET 200 fetch, PUT 200 with If-Match, PUT 409 conflict response shape (latest_version + latest_data), PUT 400 MISSING_IF_MATCH, PUT 423 RESUME_LOCKED, DELETE 204, GET 404 NOT_FOUND, GET 403 NOT_OWNER.
- [x] T019 [P] [US1] Write Vitest `src/modules/resume/v2/__tests__/schema.test.ts` covering Zod parse of minimal sample, full sample, invalid (rejects out-of-range fontSize, invalid rgba, missing required fields).
- [x] T020 [P] [US1] Write Vitest `src/modules/resume/v2/__tests__/style-rules.test.ts` covering `resolveStyleIntentForSlot` specificity: global only, sectionType overrides global, sectionId overrides sectionType, multiple matching rules merge via Object.assign.

### Implementation for User Story 1

- [x] T021 [US1] Wire `ResumeService` in `backend/app/modules/resumes_v2/service.py`: `create_resume(user_id, name, slug, template, from_sample)` (applies `defaultResumeDataV2()` when from_sample), `get_resume(id, user_id)`, `update_resume(id, user_id, if_match, payload)` (calls `repo.update_with_version`; on None, fetches latest and returns conflict tuple), `delete_resume`, `duplicate_resume` (per FR-098..100).
- [x] T022 [US1] Implement all 5 CRUD endpoints in `backend/app/modules/resumes_v2/api.py` (list, create, get, update, delete). Each returns the contract shapes from `contracts/01-rest-api.md` §1. Inject `db_session_user_dep` and `get_current_user_id` from `app.api.deps`.
- [x] T023 [US1] Implement optimistic concurrency in `repository.update_with_version`: `UPDATE resumes_v2 SET data = :data, version = version + 1, updated_at = now() WHERE id = :id AND user_id = :uid AND version = :if_match RETURNING version`. Detect 0 rows returned → return None → service builds 409 response with `{ latest_version, latest_data }` from a fresh `get()`.
- [x] T024 [US1] Implement `is_locked` check: any PUT to a locked resume returns 423 RESUME_LOCKED before touching DB. `is_locked` is independent of `version`.
- [x] T025 [US1] Implement legacy rejection: if `data.format_version == "v1"` (legacy block resumes don't have this field, so check is by route — v2 endpoints reject requests with `data_format_version=v1` query), return 400 LEGACY_FORMAT per FR-012.
- [x] T026 [US1] Author CLI at `backend/app/modules/resumes_v2/cli.py` per Constitution Principle II: `seed-test-data --user <email>` (creates Pikachu sample resume), `show <id>` (prints JSON), `analyze <id>` (placeholder), `duplicate <id>`, `dump-schema` (writes `contracts/02-resume-data-schema.md` content). All commands support `--json` flag.
- [x] T027 [US1] Frontend API client at `src/modules/resume/v2/api.ts`: `listResumes()`, `getResume(id)`, `createResume(payload)`, `updateResume(id, version, payload)` (sends `If-Match` header), `deleteResume(id)`, `duplicateResume(id)`. Reuse `getAccessToken` + `deviceFingerprint` + `newRequestId` from `src/api/`.
- [x] T028 [US1] Frontend route + page: add `/resume/v2/:id` to `src/App.tsx` rendering `<ResumeEditorV2 />` placeholder (just shows resume name + version). Add `/resume/v2/new` route that creates via `createResume` and navigates.

**Checkpoint**: US1 functional. API + DB + frontend scaffold in place. Can create/read/update a v2 resume via Playwright or curl.

---

## Phase 4: User Story 2 - 10 套精选模板与可视化 Gallery (Priority: P1)

**Goal**: 10 HTML/CSS templates (`onyx/azurill/kakuna/chikorita/ditgar/bronzor/pikachu/lapras/scizor/rhyhorn`) ship in `src/modules/resume/v2/templates/`. Template Gallery modal lists them with thumbnails; clicking switches the live preview.

**Independent Test**: Open Template Gallery, see 10 thumbnails. Click Onyx → preview becomes minimal. Click Pikachu → preview becomes colored header card. Reload → template persists.

### Tests for User Story 2

- [x] T029 [P] [US2] Write Vitest `src/modules/resume/v2/templates/__tests__/dispatcher.test.tsx` covering `templateMap` has all 10 IDs, `getTemplatePage('unknown')` falls back to Onyx, each template component renders without throwing on `defaultResumeDataV2`.
- [x] T030 [P] [US2] Write Vitest `src/modules/resume/v2/__tests__/template-switch.test.tsx` (structural mirror of the Playwright visual snapshot test) covering: switching template does NOT mutate data, re-render is synchronous, completes within 100ms.
- [x] T031 [P] [US2] Write Playwright `tests/e2e/032-resume-renderer-v2/02-template-switch.spec.ts` (from quickstart S02): open gallery, click Onyx, verify preview updates within 1s, verify section item count unchanged.

### Implementation for User Story 2

- [x] T032 [P] [US2] Create shared template primitives in `src/modules/resume/v2/templates/shared/`: `<Section>`, `<Heading>`, `<Text>`, `<Link>`, `<Icon>`, `<Image>`, `<ContactItem>`, `<CustomFieldItem>`. Mirror the API of `D:/Project/reactive-resume/packages/pdf/src/templates/shared/primitives.tsx` but emit HTML (React DOM), not React-PDF `<View>`. NOTE: `<LevelDisplay>` is implemented in T064 (US5), not here.
- [x] T033 [P] [US2] Create shared CSS file `src/modules/resume/v2/templates/shared/template.css` with CSS variables: `--color-primary`, `--color-text`, `--color-background`, `--font-body`, `--font-heading`, `--font-size-body`, `--font-size-heading`, `--line-height-body`, `--line-height-heading`, `--level-icon`. Driven by `metadata.design` and `metadata.typography`.
- [x] T034 [P] [US2] Create template manifest at `public/templates/manifest.json` per `contracts/04-template-gallery.md`. 10 entries, each with id, name (zh), description, 3-5 tags, category, thumbnail path, sidebar position, recommended page format, recommended colors, partial defaults.
- [x] T035 [P] [US2] Implement Onyx template (minimal text) at `src/modules/resume/v2/templates/onyx/{Template.tsx,template.css}` (RR: `packages/pdf/src/templates/onyx/OnyxPage.tsx`). Single-column layout, top header with name+headline+contact, vertical section list.
- [x] T036 [P] [US2] Implement Azurill template (left sidebar 35%) at `src/modules/resume/v2/templates/azurill/{Template.tsx,template.css}` (RR: `packages/pdf/src/templates/azurill/`). Right main column renders sections in order; left sidebar shows skills/languages/interests.
- [x] T037 [P] [US2] Implement Kakuna template (centered symmetric) at `src/modules/resume/v2/templates/kakuna/{Template.tsx,template.css}` (RR: `kakuna/`). Header centered, body single-column centered, no sidebar.
- [x] T038 [P] [US2] Implement Chikorita template (right solid sidebar, inverted text) at `src/modules/resume/v2/templates/chikorita/{Template.tsx,template.css}` (RR: `chikorita/`). Left main + right solid-color sidebar with white text.
- [x] T039 [P] [US2] Implement Ditgar template (left tint sidebar + 2px item line) at `src/modules/resume/v2/templates/ditgar/{Template.tsx,template.css}` (RR: `ditgar/`).
- [x] T040 [P] [US2] Implement Bronzor template (row-style sections) at `src/modules/resume/v2/templates/bronzor/{Template.tsx,template.css}` (RR: `bronzor/`). Section title left, items right, horizontal divider between sections.
- [x] T041 [P] [US2] Implement Pikachu template (colored header card) at `src/modules/resume/v2/templates/pikachu/{Template.tsx,template.css}` (RR: `pikachu/`). Top primary-color rounded card with name+headline+contact, below: left sidebar + right main.
- [x] T042 [P] [US2] Implement Lapras template (rounded card + floating titles) at `src/modules/resume/v2/templates/lapras/{Template.tsx,template.css}` (RR: `lapras/`). Header card + each section heading floats on the section border.
- [x] T043 [P] [US2] Implement Scizor template (letterhead editorial) at `src/modules/resume/v2/templates/scizor/{Template.tsx,template.css}` (RR: `scizor/`). Top primary-color letterhead band + uppercase section headings + heavy font weight.
- [x] T044 [P] [US2] Implement Rhyhorn template (pipe-separated contact) at `src/modules/resume/v2/templates/rhyhorn/{Template.tsx,template.css}` (RR: `rhyhorn/`). Top header with contact items separated by `|`.
- [x] T045 [US2] Create template dispatcher at `src/modules/resume/v2/templates/index.ts` exporting `templateMap: Record<TemplateId, ComponentType<TemplateProps>>` and `getTemplatePage(id): ComponentType`. NOTE: We use STATIC imports here (not React.lazy) so vitest's jsdom can exercise the dispatcher; tree-shaking + per-template CSS bundling still gives the production bundle good shape.
- [x] T046 [US2] Generate 10 template thumbnails at `public/templates/jpg/<id>.jpg` (400×565 px). One-off Python Playwright script `scripts/render_template_thumbnails.py` reuses the existing `pdf_renderer` Chromium.
- [x] T047 [US2] Implement Template Gallery modal at `src/modules/resume/v2/editor/dialogs/TemplateGallery.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/template.tsx`). 4-column grid, each card: thumbnail + name + 3-5 tags. Click → close dialog + dispatch `setMetadata({ template: <id> })`.
- [x] T048 [US2] Wire `metadata.template` PUT: when user clicks a gallery card, the store dispatches `setMetadata({ template })`, which triggers 500ms debounced save (US12). Preview re-renders via `templateMap[data.metadata.template]`. US2 ships a local-state stand-in via `PreviewTest.tsx`; the real Zustand store + debouncedSave land with US12.

**Checkpoint**: US2 functional. All 10 templates render. Template switch is live.

---

## Phase 5: User Story 3 - 三栏编辑器与 12+12 settings 面板 (Priority: P1)

**Goal**: 3-column `ResizableGroup` (left sections / center preview / right settings). 12 settings panels rendered as accordion.

**Independent Test**: Open editor — 3 columns visible at 22/56/22. Drag left edge → width changes. Reload → width persisted. All 12 right-panel accordions fold/unfold. All 16 left sections present.

### Tests for User Story 3

- [x] T049 [P] [US3] Write Vitest `src/modules/resume/v2/editor/__tests__/BuilderShell.test.tsx` covering: 3 panels render, default sizes 22/56/22, panel resize updates store, accordion fold/unfold.
- [x] T050 [P] [US3] Write Playwright `tests/e2e/032-resume-renderer-v2/03-resizable-layout.spec.ts` (S03): drag left sidebar edge, verify width changes, reload, verify persistence.

### Implementation for User Story 3

- [x] T051 [US3] Implement `BuilderShell.tsx` at `src/modules/resume/v2/editor/BuilderShell.tsx` using `react-resizable-panels` `<PanelGroup direction="horizontal">` with 3 panels. Persist sizes to `localStorage` key `v2.panel-sizes`.
- [x] T052 [P] [US3] Implement left `SectionsPanel.tsx` at `src/modules/resume/v2/editor/left/SectionsPanel.tsx` listing 16 entries: Picture, Basics, Summary, 12 built-in sections, Custom, Custom Fields (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/left/index.tsx`). Each entry: icon + title + chevron. Click expands to show items list.
- [x] T053 [P] [US3] Implement center `PreviewPane.tsx` at `src/modules/resume/v2/editor/center/PreviewPane.tsx` rendering the current template via `templateMap[data.metadata.template]` with `data` from store. Include zoom controls (0.5×–5×) and page stacking toggle (delegates to US10 dock).
- [x] T054 [P] [US3] Implement right `SettingsPanel.tsx` at `src/modules/resume/v2/editor/right/SettingsPanel.tsx` containing 12 accordion items: Template, Layout, Typography, Design, Styles, Page, Notes, Sharing, Statistics, Analysis, Export, Information. Each collapsible.
- [x] T055 [P] [US3] Implement top `Header.tsx` at `src/modules/resume/v2/editor/Header.tsx`: centered breadcrumb (`/` + resume name + caret dropdown), left + right sidebar toggle buttons (RR: `apps/web/src/routes/builder/$resumeId/-components/header.tsx`).
- [x] T056 [US3] Mobile responsive: when viewport < `sm` breakpoint, left+right panels collapse to 48px icon rails. Click icon → overlay panel.
- [x] T057 [US3] Wire route `src/pages/ResumeEditorV2.tsx`: load resume by id via TanStack Query, hydrate store via `resetFromServer`, render `<BuilderShell>`. Handle 404 (resume not found) + 403 (not owner).

**Checkpoint**: US3 functional. Editor scaffold complete. Settings panels are empty stubs (filled by US4–US11).

---

## Phase 6: User Story 5 - 主题色三色系统与 level 设计 (Priority: P1)

**Goal**: Design panel exposes `primary/text/background` rgba pickers + level type combobox + level icon picker. All changes reflect live in preview.

**Independent Test**: Adjust primary color #0084d1 → #ff8c00. Preview sidebar background + heading underline + icon + level bar all turn orange. Switch level type star → progress-bar. Skills/Languages levels render as progress bars.

### Tests for User Story 5

- [x] T058 [P] [US5] Write Vitest `src/modules/resume/v2/editor/right/__tests__/DesignPanel.test.tsx` covering: 3 color pickers bind to `metadata.design.colors`, 22 quick swatches apply on click, level type combobox has 7 options, level icon picker filters lucide icons.
- [x] T059 [P] [US5] Write Playwright `tests/e2e/032-resume-renderer-v2/design-panel.spec.ts`: open Design panel, change primary color, verify preview `[style*="--color-primary"]` updates within 100ms.

### Implementation for User Story 5

- [x] T060 [P] [US5] Implement `DesignPanel.tsx` at `src/modules/resume/v2/editor/right/DesignPanel.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/design.tsx`). Two sub-sections: Colors + Level.
- [x] T061 [P] [US5] Implement color picker: 3 rgba inputs (primary/text/background) using `react-color` (already in deps). Provide 22 quick swatches (curated palette). Manual hex/rgba input field.
- [x] T062 [P] [US5] Implement level type combobox: 7 options (`hidden/circle/square/rectangle/rectangle-full/progress-bar/icon`). On change → `metadata.design.level.type`.
- [x] T063 [P] [US5] Implement level icon picker: searchable combobox of lucide-react icon names. Filter by typing. Default `star`. On change → `metadata.design.level.icon`.
- [x] T064 [US5] Implement `<LevelDisplay>` primitive at `src/modules/resume/v2/templates/shared/LevelDisplay.tsx` (RR: `packages/pdf/src/templates/shared/level-display.tsx`). Switches render based on `metadata.design.level.type`: hidden = null, circle/square/rectangle = N filled + (5-N) outline shapes, rectangle-full = single filled bar, progress-bar = `<progress>` element, icon = N lucide icons.
- [x] T065 [US5] Wire CSS variables: `shared/template.css` defines `:root { --color-primary: rgba(...); ... }` and the `<PreviewPane>` writes the CSS variables from `metadata.design.colors` into a `<style>` tag before rendering the template.

**Checkpoint**: US5 functional. Color + level design live.

---

## Phase 7: User Story 6 - Typography 字体与排版 (Priority: P1)

**Goal**: Typography panel — Body + Heading groups. Each: Font Family (20+ options), Font Weight (100-900 multi-select), Font Size (6-24pt), Line Height (0.5-4).

**Independent Test**: Body font IBM Plex Serif → Fira Sans. Preview body text changes. Heading size 14 → 18. Section headings grow. Line height 1.5 → 1.2. Row spacing tightens.

### Tests for User Story 6

- [x] T066 [P] [US6] Write Vitest `src/modules/resume/v2/editor/right/__tests__/TypographyPanel.test.tsx` covering body+heading independent control, font family list ≥ 20 entries, font weight multi-select, font size 6-24, line height 0.5-4.
- [x] T067 [P] [US6] Write Playwright `tests/e2e/032-resume-renderer-v2/typography-panel.spec.ts`: change body font, verify preview `<body>` font-family updates; change heading size, verify `h1-h6` font-size updates.

### Implementation for User Story 6

- [x] T068 [P] [US6] Implement `TypographyPanel.tsx` at `src/modules/resume/v2/editor/right/TypographyPanel.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/typography.tsx`). Two `<TypographyItemEditor>` instances (body + heading).
- [x] T069 [P] [US6] Implement font family combobox with 20+ web-safe + Google Font options: IBM Plex Sans/Serif, Fira Sans/Serif/Condensed, Roboto, Inter, Lato, Source Sans Pro, Open Sans, Montserrat, Raleway, PT Sans, Noto Sans, JetBrains Mono. Provide preview text per option.
- [x] T070 [P] [US6] Implement font weight multi-select (100-900, 9 options). Font size input 6-24 pt. Line height input 0.5-4 with 0.1 step.
- [x] T071 [US6] Font loading: lazy-load Google Fonts via `<link>` injection on first use. Cache `document.fonts.load()` promises. Fallback to system font if load fails.
- [x] T072 [US6] Wire CSS variables `--font-body`, `--font-heading`, `--font-size-body`, `--font-size-heading`, `--line-height-body`, `--line-height-heading` from `metadata.typography`.

**Checkpoint**: US6 functional.

---

## Phase 8: User Story 7 - Page 页面格式与边距 (Priority: P1)

**Goal**: Page panel — Language, Format (A4/Letter/Free-form), marginX/Y, gapX/Y, hide* switches.

**Independent Test**: Format A4 → Letter. Preview aspect ratio changes 1:1.414 → 1:1.294. marginX 14 → 30. Preview content width shrinks. hideSectionIcons off → section heading icons appear.

### Tests for User Story 7

- [x] T073 [P] [US7] Write Vitest `src/modules/resume/v2/editor/right/__tests__/PagePanel.test.tsx` covering all 9 fields bind correctly; format enum has 3 options; hide* switches default values.
- [x] T074 [P] [US7] Write Playwright `tests/e2e/032-resume-renderer-v2/page-panel.spec.ts`: switch format A4↔Letter, verify preview container aspect ratio; toggle hideSectionIcons, verify icons appear/disappear.

### Implementation for User Story 7

- [x] T075 [P] [US7] Implement `PagePanel.tsx` at `src/modules/resume/v2/editor/right/PagePanel.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/page.tsx`). All 9 fields.
- [x] T076 [P] [US7] Implement language combobox with BCP-47 locale list (en-US, zh-CN, ja-JP, ko-KR, fr-FR, de-DE, es-ES, etc.).
- [x] T077 [P] [US7] Implement format combobox (3 options). On change → preview container `<div>` gets `data-format` attribute; CSS sets width/height per format (A4 = 794×1123, Letter = 816×1056, free-form = auto).
- [x] T078 [US7] Implement margin/gap inputs (number inputs in pt). Wire to CSS `--margin-x`, `--margin-y`, `--gap-x`, `--gap-y` variables.
- [x] T079 [US7] Implement 3 hide switches: `hideLinkUnderline` (CSS `.rs-link { text-decoration: none !important; }`), `hideIcons` (item-level icons `display: none`), `hideSectionIcons` (section heading icons, default true).

**Checkpoint**: US7 functional.

---

## Phase 9: User Story 4 - Layout 多页布局与 dnd-kit 拖拽 (Priority: P1)

**Goal**: Layout panel — multi-page (add/delete), main/sidebar columns, Full Width toggle, Sidebar Width slider (10-50%). Sections draggable between main/sidebar via `@dnd-kit/sortable`.

**Independent Test**: Default 1 page. Add Page → 2 pages. Drag Profiles from main to sidebar → preview moves it. Toggle Full Width → sidebar merges into main. Delete Page (last disabled).

### Tests for User Story 4

- [x] T080 [P] [US4] Write Vitest `src/modules/resume/v2/editor/right/__tests__/LayoutPanel.test.tsx` covering: default 1 page, Add Page increments, Delete Page (last disabled), Full Width toggle moves sidebar→main, Sidebar Width slider 10-50 bounds.
- [x] T081 [P] [US4] Write Playwright `tests/e2e/032-resume-renderer-v2/layout-dnd.spec.ts`: drag section from main to sidebar, verify `metadata.layout.pages[0].sidebar` includes the section id; verify preview re-orders.

### Implementation for User Story 4

- [x] T082 [P] [US4] Implement `LayoutPanel.tsx` at `src/modules/resume/v2/editor/right/LayoutPanel.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/layout/`). Renders N page cards + Add Page button + Sidebar Width slider.
- [x] T083 [P] [US4] Implement `PageCard.tsx` at `src/modules/resume/v2/editor/right/layout/PageCard.tsx`: Full Width switch + main column list + sidebar column list + Delete Page button.
- [x] T084 [US4] Implement dnd-kit sortable lists: each column (main/sidebar) is a `<SortableContext>`. Each section item is a `useSortable` item. On `onDragEnd`, update `metadata.layout.pages[i].main` or `.sidebar` array. Implement drop indicator / placeholder (FR-054): use `DragOverlay` from `@dnd-kit/core` to render a preview of the dragged section at the cursor position; render a dashed-border placeholder in the target column where the section will land.
- [x] T085 [US4] Implement Full Width: when toggled on, move all sidebar items to main, clear sidebar array. When toggled off, leave empty sidebar (user must drag items back).
- [x] T086 [US4] Implement Sidebar Width slider 10-50 (%). Wire to CSS `--sidebar-width` variable on the template root.
- [x] T087 [US4] Validate: a section id can only appear in ONE column across ALL pages (Zod refinement). If user drags to a column where it already exists on another page, the dnd handler refuses + toasts.

**Checkpoint**: US4 functional. Multi-page + drag works.

---

## Phase 10: User Story 9 - Tiptap 富文本编辑器 (Priority: P1)

**Goal**: Summary, Experience description, Project description etc. use Tiptap. Toolbar: B/I/U/S/Highlight/Text Color/Heading 1-6/align/Bullet/Ordered/Outdent/Indent/Link/Inline Code/Code Block/Table/Hard Break/HR. Fullscreen mode.

**Independent Test**: Edit Experience description, bold "Engineer" → preview shows `<strong>Engineer</strong>`. Switch to Bullet List, type 3 items → preview shows `<ul><li>`. Click Fullscreen → editor covers 95svh × 95svw.

### Tests for User Story 9

- [x] T088 [P] [US9] Write Vitest `src/modules/resume/v2/editor/dialogs/__tests__/RichTextEditor.smoke.test.tsx` covering: toolbar renders 18+ buttons, bold toggle wraps selection in `<strong>`, link button only accepts http/https, fullscreen toggles `data-fullscreen` attribute.
- [x] T089 [P] [US9] Write Playwright `tests/e2e/032-resume-renderer-v2/04-tiptap-roundtrip.spec.ts` (S04): edit item description, bold a word, verify `data.description` HTML contains `<strong>`; verify preview renders bold.

### Implementation for User Story 9

- [x] T090 [US9] Add Tiptap dependencies activation: `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-link`, `@tiptap/extension-highlight`, `@tiptap/extension-text-align` (added in T001). Configure StarterKit with Table, Hard Break, HR enabled.
- [x] T091 [US9] Implement `RichTextEditor.tsx` at `src/modules/resume/v2/editor/dialogs/RichTextEditor.tsx`. Wrap `<EditorContent>` with toolbar. Bind `onUpdate` to write HTML to the parent form field.
- [x] T092 [P] [US9] Implement toolbar component with 18+ buttons. Use lucide-react icons for each. Each button calls the corresponding Tiptap command (`chain().focus().toggleBold().run()` etc.). Configure StarterKit with Table, HardBreak, HorizontalRule, CodeBlock enabled (these are StarterKit sub-extensions; ensure they are not disabled). Add Link (restrict to http/https via FR-065), Highlight, TextAlign extensions explicitly.
- [x] T093 [US9] Implement Link extension with `validateURL` returning `http`/`https` only (FR-065). Show error toast on invalid input.
- [x] T094 [US9] Implement Fullscreen mode: `<Dialog>` overlay covering 95svh × 95svw. ESC or close button exits. Content preserved.
- [x] T095 [US9] Implement RTL support: when `metadata.page.locale` is an RTL locale (ar, he, fa), add `dir="rtl"` to the editor root. Tiptap handles cursor direction automatically.
- [x] T096 [US9] Integrate into all item-edit dialogs: Experience/Education/Project/Award/Certification/Publication/Volunteer/Reference description fields, Summary content, Notes panel (US11/FR-048). Replace existing `<textarea>` with `<RichTextEditor>`.

**Checkpoint**: US9 functional. Rich text editing works across all description fields.

---

## Phase 11: User Story 10 - 8 个 dock 按钮与导出 (Priority: P1)

**Goal**: Bottom-center floating dock (`rounded-full`) with 8 icon buttons: Zoom in/out, Center view, Toggle page stacking, Open AI agent, Copy URL, Download JSON, Download PDF.

**Independent Test**: Click Download PDF → file `senior-eng-2026-06-25.pdf` downloads. Click Download JSON → JSON downloads. Click Copy URL → clipboard contains `/r/{username}/{slug}`.

### Tests for User Story 10

- [x] T097 [P] [US10] Write Vitest `src/modules/resume/v2/editor/center/__tests__/Dock.test.tsx` covering 8 buttons render with tooltips, each button has hover animation (y:-1, scale:1.04).
- [x] T098 [P] [US10] Write Playwright `tests/e2e/032-resume-renderer-v2/01-happy-path.spec.ts` (S01) — already created in US2; extend with PDF download assertion + JSON download assertion.

### Implementation for User Story 10

- [x] T099 [P] [US10] Implement `Dock.tsx` at `src/modules/resume/v2/editor/center/Dock.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-components/dock.tsx`). Fixed `bottom-4 center`, `rounded-full`, 8 buttons with tooltip on top.
- [x] T100 [P] [US10] Implement Zoom in/out: store `zoom: number` in Zustand (0.5-5). Buttons adjust by 0.25 steps. `<PreviewPane>` applies `transform: scale(zoom)`.
- [x] T101 [P] [US10] Implement Center view: resets zoom to 1 + scroll preview to top.
- [x] T102 [P] [US10] Implement Toggle page stacking: store `stacking: 'horizontal' | 'vertical'`. Buttons flip the value. `<PreviewPane>` flex-direction changes.
- [x] T103 [P] [US10] Implement Open AI agent: navigates to `/agent/new?resumeId={id}` via `useNavigate`.
- [x] T104 [P] [US10] Implement Copy URL: `navigator.clipboard.writeText('{origin}/r/{username}/{slug}')` + toast "Copied".
- [x] T105 [P] [US10] Implement Download JSON: serialize `ResumeDataV2` to JSON, `Blob` + `downloadBlob()` (existing util). Filename `{slug}.json`.
- [x] T106 [US10] Implement Download PDF: call `jsonToHtml(data)` (US15 renderer) → POST `/api/v1/v2/export/render` with `format: 'pdf', resume_id`. Backend renders via Playwright (reuse 027 `backend/src/services/pdf_renderer/`). Filename `{slug}-{YYYY-MM-DD}.pdf`. Increment `downloads` counter.
- [x] T107 [US10] Add Export settings panel at `src/modules/resume/v2/editor/right/ExportPanel.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/export.tsx`). Two buttons: Download JSON, Download PDF (same as dock). No DOCX (per clarification).

**Checkpoint**: US10 functional. Export pipeline works end-to-end.

---

## Phase 12: User Story 12 - 500ms auto-save 与实时同步 (Priority: P1)

**Goal**: Zustand store + immer. 500ms debounced PUT with `If-Match`. 409 → toast + auto-GET. SSE via LISTEN/NOTIFY for cross-tab sync.

**Independent Test**: Edit a field → 500ms later PUT fires. Refresh → data restored. Two tabs open same resume; edit in tab A → tab B sees update within 2s. PUT with stale If-Match → 409 + toast + reload.

### Tests for User Story 12

- [x] T108 [P] [US12] Write Vitest `src/modules/resume/v2/store/__tests__/persistence.test.ts` covering: 500ms debounce coalesces 2 edits to 1 PUT, AbortController cancels in-flight on new edit, 409 triggers `applyServerDiff` + toast, 423 reverts.
- [x] T109 [P] [US12] Write Vitest `src/modules/resume/v2/hooks/__tests__/useResumeSse.test.ts` covering: subscription opens EventSource, receives `resume.updated` event, calls `applyServerDiff`.
- [x] T110 [P] [US12] Write pytest `backend/app/modules/resumes_v2/tests/test_sse.py` covering: LISTEN/NOTIFY round-trip, SSE endpoint streams events, heartbeat every 25s, max 5 connections per user.
- [x] T111 [P] [US12] Write Playwright `tests/e2e/032-resume-renderer-v2/05-autosave-concurrency.spec.ts` (S05): edit field, verify PUT after 500ms; simulate concurrent PUT via API, verify toast + reload.

### Implementation for User Story 12

- [x] T112 [US12] Implement Zustand store at `src/modules/resume/v2/store/index.ts` per `contracts/05-frontend-store.md`. Include `resume`, `original`, `isDirty`, `pendingSave`, `saving`, `lastError`, `hydrated`. Use `immer` middleware.
- [x] T113 [US12] Implement `setData(mutator)` using immer `produce()`. Triggers `debouncedSave()` after each mutation.
- [x] T114 [US12] Implement `debouncedSave()`: 500ms setTimeout; cancels previous; creates new AbortController; calls `updateResume(id, version, data)`; on 200 → `resetFromServer(response)`; on 409 → `applyServerDiff(body.latest_data, body.latest_version)` + toast; on 423 → revert + toast.
- [x] T115 [US12] Implement `beforeunload` handler: if `isDirty`, call `flushSave()` synchronously (best-effort). Also set `event.preventDefault()` + `event.returnValue = ''` for browser prompt.
- [x] T116 [US12] Implement SSE endpoint `GET /api/v1/v2/resumes/events?resume_id={id}` at `backend/app/api/v1/ws/resume_v2.py`. Subscribe to Postgres LISTEN channel `resume_update_v2`. Stream events as SSE per `contracts/03-sse-events.md`. Heartbeat every 25s.
- [x] T117 [US12] Emit NOTIFY on every `update_with_version` success: `SELECT pg_notify('resume_update_v2', json_build_object('type','resume.updated','resume_id',:id,'version',:v,'user_id',:u,'updated_at',:ts)::text)`.
- [x] T118 [US12] Implement `useResumeSse(resumeId)` hook at `src/modules/resume/v2/hooks/useResumeSse.ts`. Opens EventSource, parses events, dispatches to store. Returns unsubscribe on unmount.
- [x] T119 [US12] Implement `applyServerDiff(next, version)`: if no pending save → silent replace; if pending save exists → toast + replace; if version matches → no-op.
- [x] T120 [US12] Implement Ctrl+S handler: `event.preventDefault()` + toast "Your changes are saved automatically." (per FR-081 acceptance 8).

**Checkpoint**: US12 functional. Auto-save + SSE working. Data never lost.

---

## Phase 13: User Story 15 - 模板切换实时预览 + 数据兼容 (Priority: P1)

**Goal**: Template switch updates preview in <1s without modifying `data`. v1 block resumes open read-only with banner. `metadata.template` field persists.

**Independent Test**: Switch template → preview updates; data unchanged (verify via API GET). Open v1 resume → banner shows; no edit affordances.

### Tests for User Story 15

- [x] T121 [P] [US15] Write Vitest `src/modules/resume/v2/templates/__tests__/template-switch.test.ts` covering: switching template doesn't mutate `data` (deep equality check), preview re-renders within 1s.
- [x] T122 [P] [US15] Write Playwright `tests/e2e/032-resume-renderer-v2/10-legacy-readonly.spec.ts` (S10): open v1 block resume via `/resume/v2/{id}` → redirect to `/resume/{id}` + banner "该简历使用旧版格式".

### Implementation for User Story 15

- [x] T123 [US15] Implement `jsonToHtml(data)` at `src/modules/resume/v2/renderer/jsonToHtml.ts`: takes `ResumeDataV2`, returns HTML string. Looks up `templateMap[data.metadata.template]`, renders to static HTML via `renderToStaticMarkup`. Wraps in `<div data-template="...">` for CSS scoping.
- [x] T124 [US15] Wire `metadata.template` persistence: `setMetadata({ template })` updates store → debounced save → preview re-renders via `jsonToHtml`.
- [x] T125 [US15] Implement v1 detection: backend `GET /api/v1/v2/resumes/{id}` returns 400 LEGACY_FORMAT if the row's `data_format_version = 'v1'` (legacy block resumes have this column; new v2 resumes don't).
- [x] T126 [US15] Frontend: on 400 LEGACY_FORMAT, redirect to `/resume/{id}` (v1 editor) + show banner toast "该简历使用旧版格式，请创建新版 v2 简历".
- [x] T127 [US15] Performance: ensure template switch < 1s (500ms debounce + render). Add `<React.Suspense>` around lazy-loaded template with `<Spinner>` fallback.

**Checkpoint**: US15 functional. Templates switch live. Legacy handled.

---

## Phase 14: User Story 8 - Style Rules 自定义样式 (Priority: P2)

**Goal**: Styles panel — add/edit/delete style rules. Each rule: Target (global/sectionType/sectionId) + Slots (15) + Intent (Color/Text/Spacing/Border). Specificity: sectionId > sectionType > global.

**Independent Test**: Add rule: target sectionId=experience, slot heading, intent color=orange. Preview Experience heading turns orange. Change to target global, slot link, textDecoration=underline. All links underlined.

### Tests for User Story 8

- [x] T128 [P] [US8] Write Vitest `src/modules/resume/v2/editor/right/__tests__/StylesPanel.test.tsx` covering: Add rule dialog opens, target scope selector (3 options), slots multi-select (15), intent editor 4 groups, specificity resolution.
- [x] T129 [P] [US8] Write Playwright `tests/e2e/032-resume-renderer-v2/style-rules.spec.ts`: add rule, verify preview reflects, delete rule, verify preview reverts.

### Implementation for User Story 8

- [x] T130 [P] [US8] Implement `StylesPanel.tsx` at `src/modules/resume/v2/editor/right/StylesPanel.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/custom-styles.tsx`). List rules + Add button + edit dialog.
- [x] T131 [P] [US8] Implement rule editor dialog: Target scope (global/sectionType/sectionId) + selector (sectionType: 12 enum dropdown; sectionId: autocomplete from current section ids). Slots multi-select (15 StyleSlot checkboxes). Intent editor: 4 tabs (Color/Text/Spacing/Border).
- [x] T132 [US8] Implement style rule application: in `jsonToHtml`, before rendering each `<Section>`, call `resolveStyleIntentForSlot(data, { slot, sectionId, sectionType })` for each of the 15 slots. Apply as inline `style={...}` on the corresponding element.
- [x] T133 [US8] Implement specificity: rely on `resolveStyleIntentForSlot` algorithm from `src/modules/resume/v2/schema/style-rules.ts` (T008). Verify in unit tests (T020).
- [x] T134 [US8] Implement rule enable/disable toggle: `enabled: false` rules are filtered out in resolver.
- [x] T135 [US8] Cap rules at 50 per resume (per `data-model.md` §7 `styleRules` validation).

**Checkpoint**: US8 functional. Style rules work.

---

## Phase 15: User Story 11 - 公开分享链接 + 密码保护 + 统计 (Priority: P2)

**Goal**: Sharing panel — Allow Public Access switch, public URL display, Set Password (6-64). Statistics panel — views/downloads counts + last viewed/downloaded time. `<meta robots noindex>` on public page.

**Independent Test**: Enable public → URL `localhost/r/alice/senior-eng` works incognito. Set password `secret123` → incognito prompts password. Wrong password rejected. Correct password → 10-min cookie. Visit increments views. Download increments downloads.

### Tests for User Story 11

- [x] T136 [P] [US11] Write pytest `backend/app/modules/resumes_v2/tests/test_public.py` covering: GET public resume 200, 401 PASSWORD_REQUIRED when password set + no cookie, 401 on wrong password, 200 + Set-Cookie on correct password, owner's own visit does NOT increment views.
- [x] T137 [P] [US11] Write pytest `backend/app/modules/resumes_v2/tests/test_statistics.py` covering: views counter atomic increment, downloads counter atomic increment, last_viewed_at + last_downloaded_at update.
- [x] T138 [P] [US11] Write Playwright `tests/e2e/032-resume-renderer-v2/06-public-sharing.spec.ts` (S06): enable public + password, verify incognito flow + cookie + 10-min TTL.

### Implementation for User Story 11

- [x] T139 [P] [US11] Implement `SharingPanel.tsx` at `src/modules/resume/v2/editor/right/SharingPanel.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/sharing.tsx`). Allow Public Access switch, URL display + copy button, Set Password / Remove Password.
- [x] T140 [P] [US11] Implement `StatisticsPanel.tsx` at `src/modules/rese/v2/editor/right/StatisticsPanel.tsx` (RR: `.../sections/statistics.tsx`). Disabled state when not public. Live counts + timestamps.
- [x] T141 [US11] Implement backend `PUT /api/v1/v2/resumes/{id}/sharing` endpoint: sets `is_public` + bcrypt-hashes password (cost 12) when provided; clears `password_hash` when password is null.
- [x] T142 [US11] Implement `GET /api/v1/v2/public/{username}/{slug}` endpoint: returns public resume data (no auth required). If `is_public=false` → 404. If `password_hash` set + no valid cookie → 401 PASSWORD_REQUIRED.
- [x] T143 [US11] Implement `POST /api/v1/v2/public/{username}/{slug}/verify-password` endpoint: bcrypt verify; on success, set HttpOnly cookie `v2_public_pw_<hash>` (10-min TTL, SameSite=Lax, Path=/).
- [x] T144 [US11] Implement public PDF download `GET /api/v1/v2/public/{username}/{slug}/pdf`: same cookie flow + render via Playwright + increment `downloads` (if non-owner).
- [x] T145 [US11] Implement view counter increment: on every public GET (non-owner, identified by IP+user-agent hash), atomic `UPDATE resume_statistics_v2 SET views = views + 1, last_viewed_at = now() WHERE resume_id = :id`.
- [x] T146 [US11] Implement frontend public page at `src/pages/PublicResumeV2.tsx` route `/r/:username/:slug`. Renders the template (read-only, no editor affordances). Inject `<meta name="robots" content="noindex, follow">` per FR-080 via `useEffect` on mount: `const meta = document.createElement('meta'); meta.name = 'robots'; meta.content = 'noindex, follow'; document.head.appendChild(meta); return () => meta.remove();` (React SPA head management; no react-helmet dependency needed for a single meta tag).
- [x] T147 [US11] Implement SSE event `resume.public-changed` per `contracts/03-sse-events.md` §2.3. Emit on sharing update.

**Checkpoint**: US11 functional. Public sharing + statistics work.

---

## Phase 16: User Story 14 - AI 简历分析 (Priority: P2)

**Goal**: Analysis panel — Analyze button + Overall Score (0-100 circle) + 10 dimensions (progress bars) + 3-5 Strengths + 3-5 Suggestions (high/medium/low impact, each with why + example rewrite).

**Independent Test**: Click Analyze → loading 30s → results. Overall score + 10 dimensions + strengths + suggestions. Click Analyze again → updates same row (count=1 in DB).

### Tests for User Story 14

- [x] T148 [P] [US14] Write pytest `backend/app/modules/resumes_v2/tests/test_analysis.py` covering: DeepSeek 200 → analysis stored with status='success', DeepSeek 429 → retry 3× (1s/2s/4s) → status='failed' with failure_reason, prompt template renders resume data correctly, dimensions array has exactly 10 entries.
- [x] T149 [P] [US14] Write Playwright `tests/e2e/032-resume-renderer-v2/07-ai-analysis.spec.ts` (S07): click Analyze, wait ≤60s, verify overall score + 10 dimensions + ≥3 strengths + ≥3 suggestions.

### Implementation for User Story 14

- [x] T150 [P] [US14] Author AI prompt template at `backend/app/modules/resumes_v2/prompts/analyze.md`: instructs DeepSeek to output JSON with `overallScore`, `dimensions[10]`, `strengths[3-5]`, `suggestions[3-5]` (each: impact, text, why, exampleRewrite). Force JSON-only output via system message.
- [x] T151 [P] [US14] Implement `AnalysisPanel.tsx` at `src/modules/resume/v2/editor/right/AnalysisPanel.tsx` (RR: `apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/resume-analysis.tsx`). Analyze button + circular score gauge + 10 progress bars + strengths list + suggestions list.
- [x] T152 [US14] Implement backend `POST /api/v1/v2/resumes/{id}/analyze` endpoint: calls DeepSeek via `app.agents.llm_client`. Retry 3× on 429/5xx with exponential backoff (1s/2s/4s). On 3rd failure, store `status='failed'` + `failure_reason`. On success, store `analysis` JSONB + `status='success'`. UPSERT (1 row per resume — overwrites previous analysis). NO in-memory cache (FR-091a): each Analyze click calls DeepSeek fresh; no per-user quota. UPSERT is storage-layer semantics, not caching.
- [x] T153 [US14] Implement `GET /api/v1/v2/resumes/{id}/analysis` endpoint: returns latest analysis row or 404 if never analyzed.
- [x] T154 [US14] Implement DisabledState: if `app.agents.llm_client` is not configured (DeepSeek API key missing), Analysis panel shows "AI provider not configured" + a link to settings (per FR-091c).
- [x] T155 [US14] Emit SSE event `analysis.completed` per `contracts/03-sse-events.md` §2.5 on success/failure.

**Checkpoint**: US14 functional. AI analysis works.

---

## Phase 17: User Story 16 - Duplicate 简历变体 (Priority: P2)

**Goal**: Duplicate button on list card + dock. Creates new v2 resume with copied data + new UUID + new slug + "(Copy)" suffix.

**Independent Test**: Resume A "Senior Engineer" slug `senior-eng`. Click Duplicate. New resume B: name "Senior Engineer (Copy)", slug `senior-eng-copy-1`, data identical to A, is_public=false, no analysis record. Edit B → A unchanged. Delete B → A unchanged.

### Tests for User Story 16

- [x] T156 [P] [US16] Write pytest `backend/app/modules/resumes_v2/tests/test_duplicate.py` covering: deep copy of data, new UUIDv7, slug `-copy-N` increment when collisions exist, name "(Copy)" suffix, is_public=false, is_locked=false, password_hash=null, no statistics row, no analysis row.
- [x] T157 [P] [US16] Write Playwright `tests/e2e/032-resume-renderer-v2/08-duplicate.spec.ts` (S08): click Duplicate on list card, verify new resume appears, verify isolation.

### Implementation for User Story 16

- [x] T158 [P] [US16] Implement `POST /api/v1/v2/resumes/{id}/duplicate` endpoint: service `duplicate_resume(id, user_id)`. Deep-copy `data` (jsonb). Generate new UUIDv7. Compute new slug: `<original-slug>-copy-<N>` where N is 1 + max(existing N values). Query existing copies with regex extraction: `SELECT COALESCE(MAX((regexp_match(slug, '^<orig>-copy-(\\d+)$'))[1]::int), 0) FROM resumes_v2 WHERE user_id=:uid AND slug ~ ('^' || :orig || '-copy-[0-9]+$')`. Avoid `LIKE '<orig>-copy-%'` (would match `senior-eng-copy-10` when querying for `senior-eng-copy-1`). Name suffix " (Copy)" (zh-CN: " (副本)" — i18n-aware via `Accept-Language` header).
- [x] T159 [P] [US16] Add Duplicate button to resume list card at `src/pages/ResumeListV2.tsx` (next to existing edit/delete buttons). Icon: `lucide-react/Copy`.
- [x] T160 [P] [US16] Add Duplicate button to editor Header (next to breadcrumb in `src/modules/resume/v2/editor/Header.tsx` from T055). NOT to the bottom dock — FR-067 mandates exactly 8 dock buttons; clarification "顶部 dock" refers to the top Header. Icon: `lucide-react/Copy`.
- [x] T161 [US16] On duplicate success, navigate to `/resume/v2/{new_id}` (auto-open new resume in editor).

**Checkpoint**: US16 functional.

---

## Phase 18: User Story 17 - Undo/Redo 20 步历史栈 (Priority: P2)

**Goal**: Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z redo. 20-step stack. 30-min TTL clears stack. New edit clears redo stack.

**Independent Test**: Edit 5 fields. Ctrl+Z 4 times → fields revert. Ctrl+Shift+Z 2 times → restore. Type new value → redo stack empty. Idle 30 min → Ctrl+Z → toast "历史已过期".

### Tests for User Story 17

- [x] T162 [P] [US17] Write Vitest `src/modules/resume/v2/store/__tests__/history.test.ts` covering: push 21 entries → oldest dropped (depth 20), undo/redo cycle, new edit clears redo, 30-min TTL clears stack + returns toast on next undo.
- [x] T163 [P] [US17] Write Playwright `tests/e2e/032-resume-renderer-v2/09-undo-redo.spec.ts` (S09): edit 5 fields, Ctrl+Z 5 times, verify revert; Ctrl+Shift+Z, verify restore.

### Implementation for User Story 17

- [x] T164 [US17] Implement history stack at `src/modules/resume/v2/store/history.ts`: `undoStack: HistoryEntry[]` (max 20), `redoStack: HistoryEntry[]`, `lastEditAt: number | null`. Each entry = `{ ts, data, label? }`.
- [x] T165 [US17] Modify `setData(mutator)` to push current `data` to `undoStack` BEFORE applying mutator. Cap at 20 (drop oldest). Clear `redoStack`. Update `lastEditAt`.
- [x] T166 [US17] Implement `undo()`: pop `undoStack`, push current `data` to `redoStack`, set `data = popped.data`, trigger debounced save.
- [x] T167 [US17] Implement `redo()`: pop `redoStack`, push current `data` to `undoStack`, set `data = popped.data`, trigger debounced save.
- [x] T168 [US17] Implement 30-min TTL: setInterval(60s) checks `Date.now() - lastEditAt > 30 * 60 * 1000`. If true, clear both stacks + set `historyTTLExpired = true`. Next Ctrl+Z shows toast "历史已过期".
- [x] T169 [US17] Bind Ctrl/Cmd+Z → `undo()`, Ctrl/Cmd+Shift+Z → `redo()` via `useEffect` keyboard listener on `BuilderShell`.
- [x] T170 [US17] Exclude Duplicate from history stack (per FR / spec acceptance 7). Duplicate creates a new resume; it's a navigation, not an edit.

**Checkpoint**: US17 functional.

---

## Phase 19: User Story 13 - 模板市场 (Square 模板市场兼容) (Priority: P3)

**Goal**: Existing Square marketplace (`/resume/marketplace`) gains a v2 toggle. v2 items create a new v2 resume with template config applied.

**Independent Test**: Open marketplace. Toggle "数据格式" v2. Click Pikachu template "Use this template". New v2 resume created with Pikachu template + sample data. Navigate to editor.

### Tests for User Story 13

- [x] T171 [P] [US13] Write Vitest `src/modules/resume/marketplace/__tests__/Square-v2.test.tsx` covering: v2 toggle visible, v2 template list loads from `/api/v1/v2/templates`, clicking "Use this template" calls `createResume({ template, from_sample: true })`.
- [x] T172 [P] [US13] Write Playwright `tests/e2e/032-resume-renderer-v2/marketplace-v2.spec.ts`: open marketplace, switch to v2, click Pikachu, verify new resume + Pikachu template applied.

### Implementation for User Story 13

- [x] T173 [US13] Extend `Square.tsx` at `src/modules/resume/marketplace/Square.tsx` with a "数据格式" toggle (v1 / v2). v1 path unchanged. v2 path loads `/api/v1/v2/templates` manifest, renders cards from `manifest.templates[]`.
- [x] T174 [US13] Implement v2 "Use this template" flow: call `createResume({ name: t.name, slug: t.name.toLowerCase().replace(/\s+/g, '-'), template: t.id, from_sample: true })`. Backend applies `t.defaults` overlay on `defaultResumeDataV2()` via deep merge. Navigate to `/resume/v2/{new_id}`.
- [x] T175 [US13] Implement v1 → v2 fallback mapping: when loading v1 template items (legacy JSON), map fields to v2 schema. Missing fields get defaults. Document the mapping table in `src/modules/resume/marketplace/v1-to-v2-map.ts`.
- [x] T176 [US13] Implement filter by industry + style on the v2 marketplace UI. Industry + style derive from template `tags` array.

**Checkpoint**: US13 functional. Marketplace works for v2.

---

## Phase 20: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories.

- [x] T177 [P] Add structured logging to all backend handlers in `backend/app/modules/resumes_v2/api.py`: `resume_v2.create`, `resume_v2.update.conflict`, `resume_v2.duplicate`, `resume_v2.analyze.retry`, `resume_v2.sse.subscribe`, `resume_v2.export.render`. Include `request_id`, `user_id`, `resume_id`, `version` fields.
- [x] T178 [P] Add OpenTelemetry spans (reuse 029/030 skeleton) for: PUT update, SSE subscribe, AI analysis call, PDF render. Emit token usage + retry count metrics for AI.
- [x] T179 [P] Author `backend/app/modules/resumes_v2/README.md` per Constitution Principle I: purpose, public API (14 endpoints + CLI commands), config vars (`DEEPSEEK_API_KEY`, `RESUME_V2_SSE_MAX_CONN`), example `curl`, example CLI invocation.
- [x] T180 [P] Run full E2E suite `npm run e2e -- tests/e2e/032-resume-renderer-v2/`. Fix any failures. Commit evidence screenshots to `docs/evidence/032-resume-renderer-v2/` (gitignored).
- [x] T181 [P] Run `npm run typecheck` and `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/`. All must pass before merge.
- [x] T182 [P] Performance: profile template switch latency. Add `<Suspense>` + `React.memo` on template components if switch > 1s.
- [x] T183 [P] Security review: verify RLS on `resumes_v2`, verify bcrypt cost 12, verify HttpOnly + SameSite cookies, verify no SQL injection (parameterized queries only), verify HTML sanitizer (`backend/src/services/pdf_renderer/sanitize.py`) covers all Tiptap output.
- [x] T184 [P] Cross-browser test: Chrome 120+, Edge 120+, Firefox 121+, Safari 17+. Verify `react-resizable-panels`, Tiptap, `@dnd-kit`, SSE all work.
- [x] T185 [P] Update `docs/architecture/source-map.md` to add `resumes_v2` module + `src/modules/resume/v2/` tree.
- [x] T186 [P] Update `specs/README.md` to mark 032 status as `in_progress` → `done` after merge.
- [x] T187 Run `/speckit-analyze` to cross-check spec.md ↔ plan.md ↔ tasks.md consistency. Fix any flagged gaps.
- [x] T188 [P] Verify SC-002: template switch latency < 1s. Write Playwright perf trace test `tests/e2e/032-resume-renderer-v2/perf-template-switch.spec.ts` measuring time from gallery click to preview re-render. Assert p95 < 1000ms.
- [x] T189 [P] Verify SC-003: preview↔PDF zero drift. Write Playwright `tests/e2e/032-resume-renderer-v2/zero-drift.spec.ts` rendering same data to preview (DOM snapshot) and PDF (rasterized), compute pixel diff via `pixelmatch`. Assert diff < 1% of pixels.
- [x] T190 [P] Verify SC-005: PDF export success rate ≥ 99%. Write script `scripts/verify-pdf-success-rate.ts` running 100 PDF exports with varied data, count successes. Assert ≥ 99/100 succeed; failures must auto-retry within 5s.
- [x] T191 [P] Verify SC-007: 500ms debounce merges 2 edits to 1 PUT. Extend `tests/e2e/032-resume-renderer-v2/05-autosave-concurrency.spec.ts` with assertion that 2 rapid edits trigger exactly 1 network PUT.
- [x] T192 [P] Verify SC-008: SSE propagation latency < 2s. Write Playwright `tests/e2e/032-resume-renderer-v2/sse-latency.spec.ts` opening 2 tabs, editing in tab A, measuring time until tab B receives SSE event. Assert p95 < 2000ms.
- [x] T193 [P] Verify SC-011: AI analysis response < 60s. Extend `tests/e2e/032-resume-renderer-v2/07-ai-analysis.spec.ts` with timing assertion. Assert typical ≤ 30s, p99 < 60s.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories.
- **US1 (Phase 3)**: Depends on Foundational. MVP entry point.
- **US2 (Phase 4)**: Depends on US1 (needs `ResumeDataV2` schema + store).
- **US3 (Phase 5)**: Depends on US1 + US2 (needs templates to render in preview).
- **US5/6/7 (Phases 6-8)**: Depend on US3 (need right-panel accordion).
- **US4 (Phase 9)**: Depends on US3 (LayoutPanel is a right-panel child).
- **US9 (Phase 10)**: Depends on US3 (Tiptap dialogs open from left panel).
- **US10 (Phase 11)**: Depends on US3 + US15 (dock renders preview; PDF export needs `jsonToHtml`).
- **US12 (Phase 12)**: Depends on US1 (PUT endpoint) + US3 (store).
- **US15 (Phase 13)**: Depends on US2 (template switch) + US10 (export) — actually US15 is the renderer glue; should be done with US2 but listed here per spec §Notes.
- **US8 (Phase 14)**: Depends on US3 (StylesPanel) + US2 (templates render slots).
- **US11 (Phase 15)**: Depends on US1 (sharing endpoint) + US12 (SSE for public-changed event).
- **US14 (Phase 16)**: Depends on US1 (analysis endpoint) + US12 (SSE for analysis.completed).
- **US16 (Phase 17)**: Depends on US1 (duplicate endpoint).
- **US17 (Phase 18)**: Depends on US12 (store + persistence).
- **US13 (Phase 19)**: Depends on US2 (template manifest) + US1 (create endpoint).
- **Polish (Phase 20)**: Depends on all user stories being complete.

### User Story Independence

Each user story is independently testable per its `Independent Test` scenario. Stories can be implemented in parallel by different developers once their dependencies are met:

- After Foundational: US1 starts.
- After US1: US2, US12, US16 can start in parallel.
- After US2 + US3: US4, US5, US6, US7, US9, US10, US13, US15 can start in parallel.
- After US12: US11, US14, US17 can start in parallel.

### Within Each User Story

- Tests written FIRST and must FAIL before implementation (Constitution Principle III).
- Models/schemas before services.
- Services before endpoints.
- Core implementation before integration.
- Story complete before moving to next priority.

### Parallel Opportunities

- All Setup tasks marked [P] (T002–T005) can run in parallel.
- All Foundational tasks marked [P] (T007–T10, T012, T015) can run in parallel.
- Within US2: all 10 template implementations (T035–T044) are [P] — 10-way parallel.
- Within US3: left/center/right panel scaffolds (T052–T055) are [P].
- Within US5/6/7: panel + primitive tasks are [P].
- Within US10: dock buttons (T100–T105) are [P].
- Within US11: Sharing + Statistics panels (T139–T140) are [P].
- Within US14: prompt + AnalysisPanel (T150–T151) are [P].
- Within US16: list button + dock button (T159–T160) are [P].
- Within Polish: all of T177–T186 are [P].

---

## Parallel Example: User Story 2 (Templates)

```bash
# Launch all 10 template implementations in parallel:
Task: "Implement Onyx template at src/modules/resume/v2/templates/onyx/{Template.tsx,template.css}"
Task: "Implement Azurill template at src/modules/resume/v2/templates/azurill/{Template.tsx,template.css}"
Task: "Implement Kakuna template at src/modules/resume/v2/templates/kakuna/{Template.tsx,template.css}"
Task: "Implement Chikorita template at src/modules/resume/v2/templates/chikorita/{Template.tsx,template.css}"
Task: "Implement Ditgar template at src/modules/resume/v2/templates/ditgar/{Template.tsx,template.css}"
Task: "Implement Bronzor template at src/modules/resume/v2/templates/bronzor/{Template.tsx,template.css}"
Task: "Implement Pikachu template at src/modules/resume/v2/templates/pikachu/{Template.tsx,template.css}"
Task: "Implement Lapras template at src/modules/resume/v2/templates/lapras/{Template.tsx,template.css}"
Task: "Implement Scizor template at src/modules/resume/v2/templates/scizor/{Template.tsx,template.css}"
Task: "Implement Rhyhorn template at src/modules/resume/v2/templates/rhyhorn/{Template.tsx,template.css}"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T005).
2. Complete Phase 2: Foundational (T006–T015) — CRITICAL, blocks all stories.
3. Complete Phase 3: US1 (T016–T028) — JSON Schema data model + CRUD API.
4. **STOP and VALIDATE**: `curl POST /api/v1/v2/resumes` creates a resume; `curl PUT` updates with `If-Match`; 409 on conflict.
5. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → API + DB + schema (MVP — backend-only).
3. US2 + US3 → 10 templates + 3-column editor (visual MVP).
4. US5/6/7 → design/typography/page panels (design MVP).
5. US4 → layout drag (interactive MVP).
6. US9 + US10 → rich text + export (functional MVP).
7. US12 → auto-save + SSE (production-ready MVP).
8. US15 → template switch + legacy compat.
9. US8/US11/US14/US16/US17 → advanced features (sharing, AI, duplicate, undo).
10. US13 → marketplace compatibility.
11. Polish → observability + docs + cross-browser.

### Parallel Team Strategy

With 3 developers after Foundational:

- Developer A: US1 → US12 → US14 → US17 (backend-heavy).
- Developer B: US2 → US3 → US5/6/7 → US4 → US9 (template + panel-heavy).
- Developer C: US10 → US15 → US11 → US16 → US13 (integration + sharing).

---

## Reactive-Resume Source Reference Index

For each task group, the corresponding reactive-resume source files to consult:

| Task | Reactive-Resume Reference |
|---|---|
| Schema port (T006–T009) | `D:/Project/reactive-resume/packages/schema/src/resume/{data.ts,default.ts,style-rules.ts,sample.ts}` |
| Template implementations (T035–T044) | `D:/Project/reactive-resume/packages/pdf/src/templates/<name>/<Name>Page.tsx` + `shared/primitives.tsx` |
| Section form components (US3 left panel) | `D:/Project/reactive-resume/apps/web/src/routes/builder/$resumeId/-sidebar/left/sections/*.tsx` |
| Settings panels (US3 right panel) | `D:/Project/reactive-resume/apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/*.tsx` |
| Layout panel (US4) | `D:/Project/reactive-resume/apps/web/src/routes/builder/$resumeId/-sidebar/right/sections/layout/` |
| Dock (US10) | `D:/Project/reactive-resume/apps/web/src/routes/builder/$resumeId/-components/dock.tsx` |
| Header (US3) | `D:/Project/reactive-resume/apps/web/src/routes/builder/$resumeId/-components/header.tsx` |
| Preview page (US3 center) | `D:/Project/reactive-resume/apps/web/src/routes/builder/$resumeId/-components/preview-page.tsx` |
| Store patterns (US12) | `D:/Project/reactive-resume/apps/web/src/routes/builder/$resumeId/-store/` |

**IMPORTANT**: eGGG uses **HTML/CSS** for rendering (not React-PDF). When porting a reactive-resume `<View>` component, translate to `<div>` + CSS. When porting `<Text>`, use `<span>` or `<p>`. The visual identity should match reactive-resume but the implementation technology differs.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Each user story should be independently completable and testable.
- Verify tests fail before implementing (Constitution Principle III).
- Commit after each task or logical group.
- Stop at any checkpoint to validate story independently.
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence.
- The spec contains 17 user stories (US1–US17); US16 (Duplicate) and US17 (Undo/Redo) were added via clarification on 2026-06-25.
- DOCX export is removed per clarification (FR-070 deleted; Export panel has JSON + PDF only).
- CLI at `backend/app/modules/resumes_v2/cli.py` is mandatory per Constitution Principle II.