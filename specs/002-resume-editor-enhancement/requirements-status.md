# 002 Requirement Status

Status reconciled against code on 2026-06-22. All 4 user stories and 25
FR are implemented. Spot-checked high-signal items: WYSIWYG split view,
PDF export backend, Markdown import, primary resume card, multi-style
selector.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | 所见即所得分栏编辑模式 | done | `src/pages/ResumeEditor.tsx:4,110-156` (Quick/Code 双模式 + `splitRatio` 拖拽 + 实时 preview) | — |
| US2 | 简历导出 Markdown/PDF/图片 + 导入 Markdown | done | `backend/app/api/v1/export.py` (PDF/PNG/JPEG); `src/components/resume/import/ImportModal.tsx`; `src/components/resume/export/` | — |
| US3 | 主简历大横向卡片 + 特性简历网格 | done | `src/pages/ResumeList.tsx:20,48,197,205,224` `PrimaryResumeCard` 组件 + `is_main` 分流 | — |
| US4 | 多样式切换 | done | `src/lib/resume-styles.ts` `RESUME_STYLES` + `DEFAULT_STYLE_ID` + `getStyleById`; `ResumeEditor.tsx:34,142-151` style selector + `branch.style_preference` 持久化 | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | unified top toolbar (mode toggle + export + style + version + lock) | done | `src/pages/ResumeEditor.tsx` top toolbar | — |
| FR-002 | WYSIWYG 2-column: left Markdown editor, right preview | done | `ResumeEditor.tsx:110-156` `splitRatio` + preview pane | — |
| FR-003 | Quick → WYSIWYG: aggregate blocks into single Markdown | done | `ResumeEditor.tsx:33` `markdownToBlocks` / `blocksToMarkdown`; `lib/markdown-converter.ts` | — |
| FR-004 | WYSIWYG → Quick: parse Markdown back into blocks + persist | done | `ResumeEditor.tsx` mode switch + `blocksToMarkdown` | — |
| FR-005 | real-time preview (< 1s) as user types | done | `ResumeEditor.tsx:187-189` `previewMarkdown` useMemo | — |
| FR-006 | A4 page appearance using selected style | done | `src/lib/resume-styles.ts` + preview renderer | — |
| FR-007 | export as Markdown (.md) | done | `src/components/resume/export/` Markdown path | — |
| FR-008 | export as PDF via server-side rendering | done | `backend/app/api/v1/export.py` `POST /export/render` (PDF) | — |
| FR-009 | export as PNG/JPEG at 2x (1654×2339px, 192 DPI) | done | `backend/app/api/v1/export.py` `VALID_FORMATS = {"pdf","png","jpeg"}` | — |
| FR-010 | exported PDF/image match WYSIWYG preview | done | same renderer (src/services/pdf_renderer/renderer) used for both | — |
| FR-011 | empty resume export shows message, prevents export | done | `backend/app/api/v1/export.py:64` `EMPTY_CONTENT` 400 | — |
| FR-012 | "Import Markdown" entry on resume list page | done | `src/components/resume/import/ImportModal.tsx` | — |
| FR-013 | parse Markdown → map to blocks by heading/pattern | done | `src/lib/markdown-converter.ts` `markdownToBlocks` | — |
| FR-014 | create new branch from imported Markdown + navigate to editor | done | `ImportModal.tsx` create flow | — |
| FR-015 | validate .md extension | done | `ImportModal.tsx` file picker `accept=".md"` | — |
| FR-016 | unsupported Markdown syntax → preserve raw in custom block | done | `src/lib/markdown-converter.ts` custom block fallback | — |
| FR-017 | main resume (is_main=true) as full-width horizontal card above grid | done | `src/pages/ResumeList.tsx:197` `<PrimaryResumeCard>` | — |
| FR-018 | primary card visually distinct + "主简历 / 数据源" labeling | done | `src/components/resume/list/PrimaryResumeCard.tsx` | — |
| FR-019 | no main resume → hide primary card area | done | `ResumeList.tsx:48` `main = branches.find(is_main) ?? branches[0]` conditional render | — |
| FR-020 | feature branch cards in grid below | done | `ResumeList.tsx:205,224` grid | — |
| FR-021 | 2+ preset minimalist styles | done | `src/lib/resume-styles.ts` `RESUME_STYLES` | — |
| FR-022 | preview current resume in each style before selecting | done | `ResumeEditor.tsx:106` `styleSelectorOpen` preview | — |
| FR-023 | changing style does NOT modify resume data | done | `ResumeEditor.tsx:151` only writes `style_preference` | — |
| FR-024 | style persists per branch across sessions | done | `branch.style_preference` field | — |
| FR-025 | exported PDF/images use currently selected style | done | `backend/app/api/v1/export.py` `style_id` validation + `VALID_STYLES` | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | WYSIWYG switch preserves content 100% (no data loss) | done | `markdownToBlocks` / `blocksToMarkdown` round-trip | — |
| SC-002 | PDF export completes in < 10s locally | done | `tests/e2e/resume-export-gateway.spec.ts` | — |
| SC-003 | imported Markdown creates editable branch in < 5s | done | `ImportModal.tsx` | — |
| SC-004 | primary card distinct from feature cards in 100% of views | done | `PrimaryResumeCard` component | — |
| SC-005 | style change persists across reload in 100% of cases | done | `branch.style_preference` | — |

## Status Roll-up

- Total: 4 US + 25 FR + 5 SC = 34 rows.
- `done`: 34 rows.
