# Requirements Status: Resume Editor v3 for InterCraft v2

Status vocabulary follows `specs/README.md`. REQ-047 is implemented and
validated for the scoped InterCraft v2 resume editor surface.

Primary evidence:

- `docs/evidence/047-resume-editor-v3/final-validation.md`
- `docs/evidence/047-resume-editor-v3/req-047-chromium-final.png`
- `docs/evidence/047-resume-editor-v3/req-047-export.md`
- `docs/evidence/047-resume-editor-v3/req-047-export.pdf`
- `test-results/round-1-results.json`

| Requirement | Status | Evidence / Notes |
|---|---|---|
| FR-001 Markdown source editor and live preview | done | `MarkdownResumeEditor.test.tsx`; Chromium E2E opens editor and syncs preview. |
| FR-002 Supported Markdown syntax set | done | `muji-markdown-dialect.test.ts`; format-lab E2E fixture. |
| FR-003 H1 maps to resume title | done | Renderer dialect test and E2E preview assertion. |
| FR-004 H2 maps to major sections | done | Renderer dialect test and final screenshot. |
| FR-005 H3 maps to item/subsection titles | done | Renderer dialect test. |
| FR-006 Inline code renders as tag-style element | done | Renderer dialect test and shared fixture. |
| FR-007 Tables render as resume-friendly columns | done | Renderer dialect test; Chromium E2E asserts table visibility. |
| FR-008 Unsupported syntax fallback | done | `muji-markdown-safety.test.ts`; unsafe local image path stripped before render. |
| FR-009 Preview sync within one second | done | Component live-preview test and Chromium E2E editor flow. |
| FR-010 Exactly three v3 themes | done | `muji-v3-themes.test.ts`; `ThemeMenu.test.tsx`. |
| FR-011 Classic, minimal, accent-band theme coverage | done | Three CSS files plus `MarkdownResumePreviewThemes.test.tsx`. |
| FR-012 Theme switching does not mutate Markdown | done | Theme preview tests and Chromium E2E source-preservation assertion. |
| FR-013 Persist selected theme per resume | done | `metadata.markdown.themeId` schema/store tests and PUT mock in E2E. |
| FR-014 Themes preserve supported content | done | Shared fixture rendered under all three themes in preview tests. |
| FR-015 Visible line spacing control | done | `LineSpacingControl.test.tsx`; final screenshot. |
| FR-016 Persist line spacing when smart one-page is off | done | `markdown-settings.test.ts`. |
| FR-017 Apply line spacing to body/list/table content | done | Theme CSS height classes and Chromium E2E `height12` assertion. |
| FR-018 Keep heading decoration readable with spacing changes | done | Theme CSS plus final screenshot visual evidence. |
| FR-019 Define line spacing range | done | `line-height-presets.test.ts` verifies integer presets 12-25. |
| FR-020 Smart one-page toggle | done | `SmartOnePageControl.test.tsx`; Chromium E2E toggles it. |
| FR-021 Indicate smart one-page active state | done | Smart control tests and final screenshot status text. |
| FR-022 Fit without hiding/deleting content | done | `smart-one-page.test.ts`; algorithm reports statuses without content mutation. |
| FR-023 Report infeasible one-page fit | done | `smart-one-page.test.ts`; `SmartOnePageControl.test.tsx`. |
| FR-024 Define smart/manual spacing precedence | done | Store tests verify manual restore and smart override behavior. |
| FR-025 Export to PDF | done | `ExportMenu.test.tsx`; Chromium E2E saves `req-047-export.pdf`. |
| FR-026 Export to Markdown | done | `markdown-export-v3.test.ts`; Chromium E2E saves `req-047-export.md`. |
| FR-027 PDF matches preview | done | `export-v3.test.ts` sends current HTML/theme/line-height/smart state; E2E export route asserts preview HTML. |
| FR-028 Markdown export preserves source | done | Markdown export unit test and saved E2E artifact. |
| FR-029 Export progress/success/failure states | done | `ExportMenu.test.tsx`; final screenshot shows success state. |
