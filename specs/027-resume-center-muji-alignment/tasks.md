---

description: "Task list for 027-resume-center-muji-alignment feature implementation"
---

# Tasks: Resume Center Muji Alignment

**Input**: Design documents from `/specs/027-resume-center-muji-alignment/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Constitution mandates Test-First (NON-NEGOTIABLE). Each user story phase includes test tasks BEFORE implementation tasks. Tests must FAIL before impl, then PASS after.

**Organization**: Tasks grouped by user story (7 stories). Each story independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- Frontend: `src/` at repository root
- Backend: `backend/app/` and `backend/src/`
- E2E tests: `tests/e2e/`
- 木及源码参考: `D:\Project\react-resume-site\src\utils\` and `public\themes\`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, directory structure, theme resources, migration scaffolding.

- [X] T001 Add frontend dependencies to package.json: markdown-it@14, markdown-it-container@4, markdown-it-emoji@3, @types/markdown-it, rs-md-html-parser@0.2, @dnd-kit/core@6, @dnd-kit/sortable@8, react-color@2 (if not present). Run `npm install`.
- [X] T002 [P] Create library directory structure: `src/lib/resume-renderer/` (with `markdown-it-plugins/`, `icons/` subdirs), `src/lib/resume-pagination/`, `src/lib/resume-themes/`, `src/lib/version-diff/`, `src/lib/local-history/`, `src/lib/resume-ui-pref/`
- [X] T003 [P] Copy 4 theme CSS files from `D:\Project\react-resume-site\public\themes\` (default.css, blue.css, orange.css, pupple.css) to `public/themes/` — adapt selectors if needed for eGGG's style class names
- [X] T004 [P] Copy 木及 svgMap icons: `D:\Project\react-resume-site\src\utils\svgMap.ts` → `src/lib/resume-renderer/icons/svg-map.ts` — add TypeScript types, verify 14 icons present (github/email/blog/weixin/juejin/zhihu/weibo/qq/twitter/facebook/csdn/yuque/sifou/phone)
- [X] T005 [P] Create Alembic migration skeleton `backend/migrations/versions/xxxx_add_theme_to_resume_branch.py` (empty upgrade/downgrade, to be filled in US3)

**Checkpoint**: Dependencies installed, directories exist, theme resources in place. No functional change yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 [P] Port 木及 heading-block plugin: `D:\Project\react-resume-site\src\utils\markdown-it-h-container.ts` → `src/lib/resume-renderer/markdown-it-plugins/heading-block.ts` — add TS strict types, verify stack-based open/close algorithm for `#/##/###` wrapping in `<div class="h<N>_block block">`
- [X] T007 [P] Port 木及 blank-line plugin: `D:\Project\react-resume-site\src\utils\markdown-it-n.ts` → `src/lib/resume-renderer/markdown-it-plugins/blank-line.ts` — verify token.map line-number diff logic, insert `<span class="break-line">` × N
- [X] T008 [P] Port 木及 color-token plugin: `D:\Project\react-resume-site\src\utils\plugins.ts` (colorPlugin only) → `src/lib/resume-renderer/markdown-it-plugins/color-token.ts` — regex replace `#{color}` with accentColor hex
- [X] T009 [P] Create container plugin: `src/lib/resume-renderer/markdown-it-plugins/containers.ts` — `::: left/right/header/title` using markdown-it-container, emit `<div class="lr-container"><div class="left">` etc. (reference 木及 `helper.ts:24-45`)
- [X] T010 Assemble markdown-it instance: `src/lib/resume-renderer/parser.ts` — configure markdown-it with html:true, breaks:true, linkify:true; register MdEmjio (defs: svgMap, shortcuts: icon:<name>), MdHContainer, MdContainer (left/right/header/title), MdNContainer; export `markdownParserResume`
- [X] T011 [P] Create render engine index: `src/lib/resume-renderer/index.ts` — `renderMarkdown(md, opts) → {html, pageCount, styleClass}` orchestrating parser + colorPlugin + (optional) pagination
- [X] T012 [P] Create render engine README: `src/lib/resume-renderer/README.md` — public API, usage example, test fixture instructions
- [X] T013 [P] Create render engine CLI: `src/lib/resume-renderer/cli.ts` — `node cli.ts --input foo.md --theme default --color '#39393a' --style classic --output foo.html` (for E2E fixtures + local debug)
- [X] T014 Port 木及 window-scale: `D:\Project\react-resume-site\src\utils\window-event.ts` → `src/lib/resume-pagination/window-scale.ts` — A4 自适应缩放 resize listener, scale formula for window 1000-1250px
- [X] T015 Create `src/lib/resume-themes/registry.ts` — ResumeTheme interface + 4 themes (default/blue/orange/pupple) with id/name/defaultColor/cssUrl/isColorCustomizable
- [X] T016 Create `src/lib/resume-themes/index.ts` — `loadTheme(id)` fetch CSS + inject `<style id="rs-themes-data">`; `applyColor(hex)` set `document.body.style.setProperty('--bg', hex)`
- [X] T017 [P] Create `src/lib/resume-themes/README.md` — theme system API + how to add new theme
- [X] T018 Fill Alembic migration `backend/migrations/versions/xxxx_add_theme_to_resume_branch.py` — ADD COLUMN theme_id VARCHAR(32) DEFAULT 'default' NOT NULL, ADD COLUMN accent_color VARCHAR(7) DEFAULT '#39393a' NOT NULL; add CHECK constraints; downgrade reverses
- [X] T019 Run migration: `cd backend && uv run alembic upgrade head` — verify columns added

**Checkpoint**: Foundation ready. Render engine library compiles, theme system loads CSS, DB has new columns. User story implementation can begin.

---

## Phase 3: User Story 1 - 统一渲染引擎 (Priority: P1) 🎯 MVP

**Goal**: preview 与 PDF 用同一 HTML 生成器，消除渲染漂移。

**Independent Test**: 输入复杂 Markdown（表格/图片/内联 HTML/链接），确认预览与导出 PDF 视觉一致 ≥95%。

### Tests for User Story 1 (Test-First — MUST FAIL before impl)

- [X] T020 [P] [US1] Unit test: `src/lib/resume-renderer/__tests__/parser.test.ts` — assert markdown-it renders standard Markdown (headings, lists, bold, links, images, tables via GFM, code blocks)
- [X] T021 [P] [US1] Unit test: `src/lib/resume-renderer/__tests__/heading-block.test.ts` — assert `#` wraps in `<div class="h1_block block">`, `##` in `h2_block`, nested headings close properly
- [X] T022 [P] [US1] Unit test: `src/lib/resume-renderer/__tests__/blank-line.test.ts` — assert 3 consecutive blank lines produce 3 `<span class="break-line">` elements
- [X] T023 [P] [US1] Unit test: `src/lib/resume-renderer/__tests__/color-token.test.ts` — assert `#{color}` in markdown replaced with accentColor hex post-render
- [X] T024 [P] [US1] Unit test: `src/lib/resume-renderer/__tests__/render-markdown.test.ts` — assert `renderMarkdown(md, opts)` returns stable HTML (same input → same output, byte-identical)
- [X] T025 [P] [US1] Contract test: `backend/tests/test_pdf_renderer_html.py` — assert `POST /export/render` with `{html}` returns PDF binary; assert dangerous tags (`<script>`, `<iframe>`, `on*`) filtered
- [X] T026 [P] [US1] E2E: `tests/e2e/027-resume-muji/render-engine.spec.ts` — preview renders table/image/HTML/link; export PDF; assert preview screenshot vs PDF visually consistent (diff < 5%)

### Implementation for User Story 1

- [X] T027 [US1] Rewrite `src/components/resume/editor/ResumePreview.tsx` — replace react-markdown with `renderMarkdown()` from `src/lib/resume-renderer/`; render output HTML via `dangerouslySetInnerHTML` (HTML already sanitized by parser); apply style class + theme
- [X] T028 [US1] Refactor `src/api/export.ts` — change `exportResume` signature from `{markdown, style_id, format}` to `{html, format}`; update `ExportError` handling
- [X] T029 [US1] Update `src/components/resume/export/ExportMenu.tsx` — call `renderMarkdown(markdown, opts)` to generate HTML, then `exportResume({html, format})`
- [X] T030 [US1] Refactor backend `backend/app/api/v1/export.py` — change `RenderRequest` schema: remove `markdown`/`style_id`, add `html` (non-empty, ≤1MB); keep `format`
- [X] T031 [US1] Refactor `backend/src/services/pdf_renderer/renderer.py` — delete `_markdown_to_html`, `_load_css`, `_load_template`, `_escape`; new `render_with_playwright(html, format)` receives complete HTML, wraps in document, renders via Playwright
- [X] T032 [US1] Add HTML sanitizer in backend: `backend/src/services/pdf_renderer/sanitize.py` — filter `<script>`, `<iframe>`, `<object>`, `<embed>`, `on*` attributes, `javascript:` protocol (double-layer defense, frontend also sanitizes)
- [X] T033 [US1] Delete obsolete `backend/src/services/pdf_renderer/styles/` and `templates/` directories (CSS now inline in frontend-generated HTML)
- [X] T034 [US1] Verify `react-markdown` / `remark-gfm` / `rehype-raw` no longer imported anywhere in `src/components/resume/`; if confirmed unused, leave in package.json (don't uninstall — may be used elsewhere)

**Checkpoint**: US1 complete. Preview and PDF use same HTML generator. Run T020-T026 tests — all must pass.

---

## Phase 4: User Story 2 - 智能分页预览 (Priority: P1)

**Goal**: A4 真实分页线 + 页数指示器 + 单页/多页模式切换。

**Independent Test**: 输入超 A4 内容，确认分页线 + "2 页" 指示器；切换单页模式只显示第一页。

### Tests for User Story 2

- [X] T035 [P] [US2] Unit test: `src/lib/resume-pagination/__tests__/paginate.test.ts` — assert `paginateDom(node)` returns correct pageCount for short (<1 page) and long (>1 page) content
- [X] T036 [P] [US2] Component test: `src/components/resume/editor/__tests__/PageIndicator.test.tsx` — assert indicator shows "1 页" for short content, "2 页" for long; assert single-page mode toggles
- [X] T037 [P] [US2] E2E: `tests/e2e/027-resume-muji/pagination.spec.ts` — type long content in Code mode; assert `.rs-line-split` separator appears; assert page indicator updates; toggle single-page mode; export PDF single-page matches preview

### Implementation for User Story 2

- [X] T038 [US2] Create `src/lib/resume-pagination/index.ts` — `paginateDom(domNode)` wraps `rs-md-html-parser`'s `htmlParser()`; returns `{pageCount, separators}`; debounced 500ms wrapper
- [X] T039 [US2] Create `src/lib/resume-pagination/README.md` — API + debounce strategy + how rs-md-html-parser works
- [X] T040 [US2] Create `src/components/resume/editor/PageIndicator.tsx` — "1/2 页" display + single/multi-page toggle button; reads pageCount from preview state
- [X] T041 [US2] Integrate pagination into `ResumePreview.tsx` — after rendering HTML, call `paginateDom()` on rendered DOM; store pageCount in state; render `.rs-line-split` separators; apply single-page mode CSS (`overflow:hidden; height:1122px`) or multi-page (`overflow:visible; height:auto`)
- [X] T042 [US2] Wire window-scale listener in `ResumePreview.tsx` — attach `src/lib/resume-pagination/window-scale.ts` resize listener to scale A4 page on narrow windows
- [X] T043 [US2] Add PageIndicator to `UnifiedToolbar.tsx` or floating position over preview pane
- [X] T044 [US2] Pass single-page mode flag to export: when exporting in single-page mode, PDF contains only page 1 (set in renderMarkdown opts or trim HTML before POST)

**Checkpoint**: US2 complete. Smart pagination works. Run T035-T037 tests.

---

## Phase 5: User Story 3 - 主题系统与 color picker (Priority: P1)

**Goal**: 4 套木及主题 + color picker 即时生效 + 分支级持久化。

**Independent Test**: 切换 4 主题即时生效；color picker 改颜色即时全局更新；离开返回保留。

### Tests for User Story 3

- [X] T045 [P] [US3] Unit test: `src/lib/resume-themes/__tests__/registry.test.ts` — assert 4 themes registered with correct ids/defaultColors
- [X] T046 [P] [US3] Unit test: `src/lib/resume-themes/__tests__/load-theme.test.ts` — mock fetch, assert CSS injected into `<style id="rs-themes-data">`; assert `applyColor(hex)` sets `--bg` on body
- [X] T047 [P] [US3] Component test: `src/components/resume/editor/__tests__/ThemeSelector.test.tsx` — assert 4 theme thumbnails render; click switches theme
- [X] T048 [P] [US3] Component test: `src/components/resume/editor/__tests__/ColorPicker.test.tsx` — assert color change calls `applyColor` + persists to branch
- [X] T049 [P] [US3] Backend test: `backend/app/modules/resumes/tests/test_theme_persistence.py` — PATCH branch with theme_id/accent_color; GET returns persisted values; invalid theme_id 422; invalid color format 422
- [X] T050 [P] [US3] E2E: `tests/e2e/027-resume-muji/themes.spec.ts` — switch 4 themes (assert visual change via screenshot diff); pick color (assert `--bg` updated); leave and return (assert persisted)

### Implementation for User Story 3

- [X] T051 [US3] Extend backend `backend/app/modules/resumes/models.py` ResumeBranch — add `theme_id` (already migrated T018/T019) and `accent_color` mapped columns with CHECK constraints
- [X] T052 [US3] Extend `backend/app/modules/resumes/schemas.py` — add `theme_id`/`accent_color` to `ResumeBranchOut`, `PatchBranchInput`; validate theme_id ∈ registry, accent_color matches `^#[0-9a-fA-F]{6}$`
- [X] T053 [US3] Create `src/components/resume/editor/ThemeSelector.tsx` — 4 theme thumbnail cards (use mini SVG previews or color swatches); click calls `onThemeSelect(id)`; highlight current
- [X] T054 [US3] Create `src/components/resume/editor/ColorPicker.tsx` — react-color `<ChromePicker>`; `onChangeComplete` calls `applyColor(hex)` + `patchBranch({accent_color})`; live preview during drag
- [X] T055 [US3] Integrate ThemeSelector + ColorPicker into `UnifiedToolbar.tsx` — add buttons/popovers
- [X] T056 [US3] Wire theme loading in `ResumePreview.tsx` — on `theme_id` change, call `loadTheme(theme_id)`; on `accent_color` change, call `applyColor(accent_color)`
- [X] T057 [US3] Wire theme persistence: `useResumeBranch` query returns `theme_id`/`accent_color`; `usePatchBranch` mutation persists; optimistic update via `setQueryData`
- [X] T058 [US3] Pass theme + color to `renderMarkdown` opts so exported HTML includes correct theme CSS + `--bg` value

**Checkpoint**: US3 complete. Theme system works end-to-end. Run T045-T050 tests.

---

## Phase 6: User Story 4 - 木及自定义语法 (Priority: P2)

**Goal**: `::: left/right/header/title` + `icon:<name>` + `#{color}` + 空行保留 + heading-block（plugins 已在 Phase 2 搬运，本 phase 验证 + UI 辅助）。

**Independent Test**: 输入含容器/图标/颜色 token/空行的 Markdown，确认预览正确渲染。

### Tests for User Story 4

- [ ] T059 [P] [US4] Unit test: `src/lib/resume-renderer/__tests__/containers.test.ts` — assert `::: left / ::: right` produces `<div class="lr-container"><div class="left">...<div class="right">`; assert `::: header` / `::: title`
- [ ] T060 [P] [US4] Unit test: `src/lib/resume-renderer/__tests__/icons.test.ts` — assert `icon:github` produces inline SVG; assert `[icon:blog label](url)` produces icon + text + link
- [ ] T061 [P] [US4] Unit test: `src/lib/resume-renderer/__tests__/full-syntax.test.ts` — combined fixture with all custom syntax; assert output matches expected HTML snapshot
- [ ] T062 [P] [US4] E2E: `tests/e2e/027-resume-muji/custom-syntax.spec.ts` — type `::: left/right` two-column; type `icon:github`; type `#{color}` span; assert all render correctly; export PDF assert consistent

### Implementation for User Story 4

- [ ] T063 [US4] Verify containers plugin (T009) emits correct class names matching theme CSS selectors (`.lr-container`, `.left`, `.right`, `.header-block`, `.title-block`); adjust if mismatched
- [ ] T064 [US4] Verify svgMap icons (T004) render inline with correct `fill` color (should follow currentColor or `--bg`); adjust SVGs if hardcoded `fill="#ffffff"` breaks on light themes
- [ ] T065 [US4] Create `src/components/resume/editor/IconPicker.tsx` — modal grid of 14 icons; click inserts `icon:<name> ` at cursor (for MarkdownEditor)
- [ ] T066 [US4] Add icon picker trigger to MarkdownToolbar (created in US6 T078) — button opens IconPicker
- [ ] T067 [US4] Create icon syntax cheatsheet component: `src/components/resume/editor/IconCheatsheet.tsx` — clickable list of `icon:<name>` syntax; click copies to clipboard
- [ ] T068 [US4] Add cheatsheet entry point in UnifiedToolbar (small "?" button next to icon picker)

**Checkpoint**: US4 complete. All 木及 custom syntax renders. Run T059-T062 tests.

---

## Phase 7: User Story 5 - AI 优化增强 (Priority: P1)

**Goal**: pollState 真轮询 + per-patch 接受拒绝 + diff 视图 + 确认对话框。

**Independent Test**: 触发 AI 优化；确认轮询进度；patch 逐项勾选；diff 展示；应用前确认。

### Tests for User Story 5

- [ ] T069 [P] [US5] Hook test: `src/hooks/__tests__/useResumeOptimize.test.ts` — mock fetch; assert polling calls getState at intervals [1s,2s,4s,8s,16s,32s]; assert stops on `waiting_interrupt`; assert timeout at 60s; assert error + retry
- [ ] T070 [P] [US5] Component test: `src/components/resume/__tests__/AiOptimizePanel.test.tsx` — assert patch list renders with diff (green add / red remove / yellow modify); assert per-patch checkbox; assert apply button disabled until ≥1 selected; assert confirm dialog before apply
- [ ] T071 [P] [US5] Backend test: `backend/app/agents/resume_optimize/tests/test_confirm_accepted.py` — `POST /confirm` with `accepted_patches` subset applies only those; assert skipped patches not applied
- [ ] T072 [P] [US5] E2E: `tests/e2e/027-resume-muji/ai-optimize.spec.ts` — MockLLMClient returns 3 patches; assert polling progress; assert per-patch accept/reject; assert diff view; assert confirm dialog; assert only accepted applied; assert new version created

### Implementation for User Story 5

- [ ] T073 [US5] Rewrite `src/hooks/useResumeOptimize.ts` — implement polling state machine with exponential backoff [1s,2s,4s,8s,16s,32s]; 60s timeout; retry on error; restore polling on page return based on thread_id
- [ ] T074 [US5] Extend `src/api/types.ts` AIOptimizePatch — add `old_value?`, `block_id?`, `block_title?`, `accepted: boolean` (default false)
- [ ] T075 [US5] Rewrite `src/components/resume/AiOptimizePanel.tsx` — per-patch checkbox list; each patch shows diff (old_value vs value, line-level using `diff` lib); "应用选中" button disabled until ≥1 checked; confirm modal before apply
- [ ] T076 [US5] Update `src/repositories/resumeOptimizeRepo.ts` — `confirm(threadId, {decision, accepted_patches})` sends accepted path list
- [ ] T077 [US5] Extend backend `backend/app/agents/resume_optimize/` — confirm endpoint accepts `accepted_patches: string[]`; applies only listed patches; returns `{applied_count, skipped_count, new_version_id}`

**Checkpoint**: US5 complete. AI optimize usable. Run T069-T072 tests.

---

## Phase 8: User Story 6 - 编辑器交互增强 (Priority: P2)

**Goal**: DnD 拖拽 + 列表搜索筛选排序 + refresh-from-parent 确认 + Markdown 工具栏 + 键盘快捷键。

**Independent Test**: 拖拽 block 重排；列表搜索筛选；同步父级确认弹窗；工具栏加粗；Ctrl+S 保存。

### Tests for User Story 6

- [ ] T078 [P] [US6] Component test: `src/components/resume/editor/__tests__/QuickEditor-dnd.test.tsx` — assert drag handle reorders blocks; assert `PATCH /reorder` called with correct prev_id/next_id; assert network failure retries 3x then rollback
- [ ] T079 [P] [US6] Component test: `src/pages/__tests__/ResumeList-filter.test.tsx` — assert search input filters by name/company/position; assert status filter (multi-select); assert sort dropdown (edited/created/match_score)
- [ ] T080 [P] [US6] Component test: `src/components/resume/editor/__tests__/MarkdownToolbar.test.tsx` — assert bold button wraps selection in `**`; assert header/list/link buttons insert syntax; assert icon button opens picker
- [ ] T081 [P] [US6] Component test: `src/components/resume/editor/__tests__/keyboard-shortcuts.test.tsx` — assert Ctrl+S triggers save version dialog + prevents browser default; assert Ctrl+B wraps selection
- [ ] T082 [P] [US6] E2E: `tests/e2e/027-resume-muji/editor-ux.spec.ts` — drag-drop reorder; search filter; status filter; refresh-from-parent confirm dialog; toolbar bold; Ctrl+S; Ctrl+B

### Implementation for User Story 6

- [ ] T083 [US6] Add `@dnd-kit/core` + `@dnd-kit/sortable` to `QuickEditor.tsx` — replace ↑/↓ buttons with `GripVertical` drag handle; on drag end compute new order_index via `generate_key_between`; call `reorder.mutate`; optimistic update; rollback on failure (3 retries)
- [ ] T084 [US6] Create `src/components/resume/list/ResumeListToolbar.tsx` — search Input (debounced 200ms), status multi-select dropdown, sort dropdown
- [ ] T085 [US6] Integrate ResumeListToolbar into `src/pages/ResumeList.tsx` — wire search/filter/sort to query params or local state; re-fetch with backend params (extend API T086)
- [ ] T086 [US6] Extend backend `backend/app/modules/resumes/api.py` list endpoint — add `search` (ILIKE name/company/position), `status_filter` (comma-separated), `sort` (edited/created/match_score) query params; update `repository.list_for_user`
- [ ] T087 [US6] Add confirm dialog to "同步父级" in `ResumeEditor.tsx` — Modal warning "此操作将覆盖当前分支的所有本地修改，是否继续？"; cancel aborts; confirm proceeds
- [ ] T088 [US6] Create `src/components/resume/editor/MarkdownToolbar.tsx` — bold/italic/H1/H2/H3/unordered-list/link/icon buttons; operates on Monaco editor selection via `editor.executeEdits` or snippet insertion
- [ ] T089 [US6] Integrate MarkdownToolbar into `MarkdownEditor.tsx` — render toolbar above Monaco; wire buttons to editor instance
- [ ] T090 [US6] Add keyboard shortcuts in `MarkdownEditor.tsx` — `Ctrl+S` triggers `onSaveVersion` + `e.preventDefault()`; `Ctrl+B` wraps selection in `**`; `Ctrl+I` wraps in `*`
- [ ] T091 [US6] Fix `PrimaryResumeCard.tsx` — add hover action buttons (edit/pin/delete) matching regular cards; pass `previewText` from `ResumeList.tsx` (extract first ~100 chars of first block content_md)
- [ ] T092 [US6] Fix `ReorderBlocksInput` schema drift — remove `block_id` from backend `backend/app/modules/resumes/schemas.py` `ReorderBlocksInput` (use URL path); update frontend type to match

**Checkpoint**: US6 complete. Editor UX enhanced. Run T078-T082 tests.

---

## Phase 9: User Story 7 - 版本对比与本地历史 (Priority: P2)

**Goal**: 版本 diff 视图 + localStorage 8 条 FIFO 历史 + UI 偏好持久化。

**Independent Test**: 选两版本对比 diff；编辑后 localStorage 新增历史；切模式刷新恢复。

### Tests for User Story 7

- [ ] T093 [P] [US7] Unit test: `src/lib/version-diff/__tests__/block-diff.test.ts` — assert LCS matching; assert add/remove/modify classification; assert modify produces line_diff
- [ ] T094 [P] [US7] Unit test: `src/lib/local-history/__tests__/local-history.test.ts` — assert FIFO 8-cap; assert push shifts oldest; assert restore returns entry
- [ ] T095 [P] [US7] Unit test: `src/lib/resume-ui-pref/__tests__/ui-pref.test.ts` — assert save/load mode/splitRatio/scrollPos; assert per-branch isolation
- [ ] T096 [P] [US7] Backend test: `backend/app/modules/versions/tests/test_diff_endpoint.py` — `GET /versions/:v1/diff/:v2` returns correct diff structure; assert 404 for non-existent version; assert 422 for cross-branch
- [ ] T097 [P] [US7] E2E: `tests/e2e/027-resume-muji/version-diff.spec.ts` — save 2 versions; open diff; assert green/red/yellow blocks; edit content (wait 2s); assert localStorage history entry; switch mode + adjust split + refresh → assert restored

### Implementation for User Story 7

- [ ] T098 [US7] Create `src/lib/version-diff/block-diff.ts` — `diffBlocks(old, new) → BlockDiff[]` using LCS on `type+title` key; modify entries compute line_diff via `diff` lib
- [ ] T099 [US7] Create `src/lib/version-diff/index.ts` — `diffVersions(v1, v2) → VersionDiff` orchestrator; `src/lib/version-diff/README.md`
- [ ] T100 [US7] Create `src/components/resume/editor/VersionDiffView.tsx` — render BlockDiff[] with color coding (green add / red remove / yellow modify); expandable modify entries showing line_diff
- [ ] T101 [US7] Add version diff UI to version history drawer in `ResumeEditor.tsx` — select 2 versions (checkboxes) + "对比" button → opens VersionDiffView modal
- [ ] T102 [US7] Backend: implement `create_diff_snapshot` in `backend/app/modules/versions/repository.py` + `service.py` — compute diff from base, write `diff_patch` + `base_version_id`, `is_full_snapshot=False`
- [ ] T103 [US7] Backend: implement `diff_versions(v1, v2)` in `backend/app/modules/versions/service.py` — load both snapshots, call `diffBlocks` equivalent in Python, return VersionDiff
- [ ] T104 [US7] Backend: add `GET /api/v1/resume-branches/:branchId/versions/:v1/diff/:v2` endpoint in `backend/app/modules/versions/api.py`
- [ ] T105 [US7] Create `src/lib/local-history/index.ts` — `pushHistory(branchId, entry)` FIFO 8-cap; `getHistory(branchId)`; `restoreHistory(branchId, index)`; localStorage key `rs-history-{branchId}`; 100KB per entry cap
- [ ] T106 [US7] Wire local history into `ResumeEditor.tsx` — debounce 2s after edit stop; push `{markdown, theme_id, accent_color, timestamp}`; add "本地历史" entry in sidebar
- [ ] T107 [US7] Create `src/lib/resume-ui-pref/index.ts` — `savePref(branchId, pref)` / `loadPref(branchId)`; localStorage key `rs-ui-pref-{branchId}`
- [ ] T108 [US7] Wire UI pref persistence in `ResumeEditor.tsx` — save mode on toggle; save splitRatio on drag end; save scrollPos on scroll debounce 500ms; load on mount

**Checkpoint**: US7 complete. Versioning + history enhanced. Run T093-T097 tests.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Regression, cleanup, validation.

- [ ] T109 [P] Run full regression: `npm run e2e` — assert round-1 + round-2 + existing 002/017/019/M16 tests all pass (no regression)
- [ ] T110 [P] Run full unit: `npm run test` + `cd backend && uv run pytest -q` — assert all pass
- [ ] T111 [P] Run typecheck: `npm run typecheck` — assert 0 errors
- [ ] T112 [P] Run build: `npm run build` — assert success; assert `dist/themes/*.css` present
- [ ] T113 Verify backend migration reversible: `cd backend && uv run alembic downgrade -1 && uv run alembic upgrade head` — assert clean
- [ ] T114 [P] Update `specs/README.md` — add 027 row to Done table after implementation
- [ ] T115 [P] Create feature README: `specs/027-resume-center-muji-alignment/README.md` — summary + evidence links
- [ ] T116 [P] Create `requirements-status.md`: `specs/027-resume-center-muji-alignment/requirements-status.md` — 7 US + 63 FR + 15 SC status table
- [ ] T117 Run quickstart.md validation scenarios 1-7 end-to-end — all pass
- [ ] T118 [P] Memory: update `C:\Users\30803\.claude\projects\D--Project-eGGG\memory\` — add 027 feature memory (scope, decisions, gotchas)
- [ ] T119 Security review: verify no HMAC keys in client code; verify HTML sanitizer covers XSS vectors; verify `accepted_patches` path validation prevents injection
- [ ] T120 Performance: profile render engine on 50KB Markdown; assert < 500ms; profile pagination on 5-page content; assert < 300ms

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phases 3-9)**: All depend on Foundational
  - US1 (Phase 3) is MVP — blocks US2 (pagination needs render engine) and US3 (theme needs render engine)
  - US2, US3 can run in parallel after US1
  - US4 depends on US1 (custom syntax needs render engine)
  - US5 independent (AI optimize, reuses existing agent)
  - US6 independent (editor UX, DnD/list/toolbar)
  - US7 independent (version diff, local history)
- **Polish (Phase 10)**: After all desired stories complete

### User Story Dependencies

- **US1 (P1) 🎯 MVP**: Foundational → US1. Blocks US2, US3, US4.
- **US2 (P1)**: Foundational → US1 → US2. Needs render engine for pagination.
- **US3 (P1)**: Foundational → US1 → US3. Needs render engine to apply theme.
- **US4 (P2)**: Foundational → US1 → US4. Needs render engine plugins (already ported in Foundational).
- **US5 (P1)**: Foundational → US5. Independent of render engine (AI optimize reuses existing agent).
- **US6 (P2)**: Foundational → US6. Independent (DnD/list/toolbar).
- **US7 (P2)**: Foundational → US7. Independent (version diff/history).

### Within Each User Story

- Tests written FIRST and FAIL before impl (Constitution III)
- Library/algorithm before component
- Component before page integration
- Frontend before backend (for API changes) or backend before frontend (for new endpoints)
- Story complete (all tests pass) before next priority

### Parallel Opportunities

- Phase 1: T002-T005 all [P] (different dirs)
- Phase 2: T006-T009, T011-T013, T015-T017 all [P] (different files)
- US1: T020-T026 all [P] (test files independent)
- US2: T035-T037 [P]
- US3: T045-T050 [P]
- US5, US6, US7 can run in parallel after US1+US2+US3+US4 (different files, no shared state)
- Within US6: T078-T082 [P]

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel (before impl, must FAIL):
Task: "Unit test parser.test.ts — T020"
Task: "Unit test heading-block.test.ts — T021"
Task: "Unit test blank-line.test.ts — T022"
Task: "Unit test color-token.test.ts — T023"
Task: "Unit test render-markdown.test.ts — T024"
Task: "Contract test pdf_renderer_html.py — T025"
Task: "E2E render-engine.spec.ts — T026"

# After tests FAIL, launch impl in parallel where [P]:
# (US1 impl tasks are sequential — T027→T028→T029 depend on renderMarkdown)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (render engine + themes + migration)
3. Complete Phase 3: US1 (统一渲染引擎)
4. **STOP and VALIDATE**: preview↔PDF 一致性 ≥95%
5. If ready, demo to user

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. + US1 → 统一渲染引擎 (MVP — preview↔PDF 一致)
3. + US2 → 智能分页 (A4 分页线 + 页数)
4. + US3 → 主题系统 (4 主题 + color picker)
5. + US4 → 木及自定义语法 (容器/图标/token)
6. + US5 → AI 优化增强 (轮询/per-patch/diff)
7. + US6 → 编辑器交互 (DnD/搜索/工具栏/快捷键)
8. + US7 → 版本对比与本地历史
9. Polish → 回归 + 文档 + 安全审查

### Sub-Agent Collaboration Strategy

For implementation phase, dispatch parallel dev sub-agents:
- After US1 MVP validated, launch US5 + US6 + US7 in parallel (independent, different files)
- US2 + US3 + US4 sequential after US1 (all depend on render engine, but US2/US3/US4 touch overlapping files — coordinate)
- Each sub-agent: read spec.md + relevant contract + tasks for its US; implement; run its tests; report

---

## Notes

- Constitution Test-First (NON-NEGOTIABLE): test tasks (T020-T026, T035-T037, etc.) MUST be written and FAIL before impl tasks in same phase
- [P] tasks = different files, no dependencies — safe to parallelize
- [Story] label maps task to US for traceability
- Each US independently completable and testable — stop at checkpoint to validate
- Commit after each task or logical group
- 木及源码 reference: `D:\Project\react-resume-site\src\utils\` + `public\themes\`
- Avoid: vague tasks, same-file conflicts, cross-story dependencies breaking independence
- Render engine is the keystone — US1 must complete before US2/US3/US4 (they depend on `renderMarkdown`)
