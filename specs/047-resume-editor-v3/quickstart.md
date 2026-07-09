# Quickstart: Validate Resume Editor v3

This guide describes validation scenarios for the scoped REQ-047 resume editor.

## Prerequisites

- Node dependencies installed.
- Current active feature is `specs/047-resume-editor-v3`.
- Use representative Markdown fixtures from `docs/evidence/v3-editor-research/muji-2026-07-06/`.

## Core Commands

```bash
npm run typecheck
npm run test -- src/modules/resume/v2/schema/__tests__/markdown-metadata.test.ts src/modules/resume/v2/store/__tests__/markdown-settings.test.ts src/modules/resume/renderer/__tests__/muji-markdown-dialect.test.ts src/modules/resume/renderer/__tests__/muji-markdown-safety.test.ts src/modules/resume/pagination/__tests__/line-height-presets.test.ts src/modules/resume/pagination/__tests__/smart-one-page.test.ts src/modules/resume/themes/__tests__/muji-v3-themes.test.ts src/modules/resume/v2/editor/__tests__/MarkdownResumeEditor.test.tsx src/modules/resume/v2/editor/__tests__/MarkdownResumePreviewThemes.test.tsx src/modules/resume/v2/editor/__tests__/ThemeMenu.test.tsx src/modules/resume/v2/editor/__tests__/LineSpacingControl.test.tsx src/modules/resume/v2/editor/__tests__/SmartOnePageControl.test.tsx src/modules/resume/v2/editor/__tests__/ExportMenu.test.tsx src/modules/resume/converter/__tests__/markdown-export-v3.test.ts src/modules/resume/v2/api/__tests__/export-v3.test.ts
npm run build
npm run e2e -- tests/e2e/047-resume-editor-v3.spec.ts --project=chromium
cd backend && uv run pytest -q app/modules/resumes_v2/tests/test_markdown_metadata.py app/modules/resumes_v2/tests/test_export.py
```

Full `npm run test` is also useful as a repository health check. During the
REQ-047 implementation it was executed and recorded at
`docs/evidence/047-resume-editor-v3/vitest-full-results.json`; it still reports
pre-existing failures outside the REQ-047 target test set.

## Scenario 1 - Markdown Rendering Contract

1. Load the Markdown format-lab fixture.
2. Render it through the resume renderer.
3. Verify:
   - H1/H2/H3 mapping.
   - Muji-compatible `::: left/right`, `icon:*`, and icon-prefixed links.
   - Bold, italic, bold-italic, strikethrough, links, inline code tags.
   - Blockquote, horizontal rule, ordered/unordered/nested lists.
   - Task-list syntax remains literal.
   - Table renders as borderless resume columns.
   - External URL image renders or fails with safe fallback.

Expected result: preview contains all supported content and no unsupported content is silently deleted.

## Scenario 2 - Three Themes

1. Open the same Markdown resume.
2. Apply 默认（秋风同款）.
3. Apply 极简色.
4. Apply 平面大气主题.
5. Confirm source Markdown remains unchanged.

Expected result: each theme matches its Muji rendering pattern and preserves content.

## Scenario 3 - Line Spacing

1. Open line spacing control.
2. Verify presets 12 through 25 are available.
3. Select 12, 19, and 25.
4. Compare body/list/table density.

Expected result: body/list/table line-height changes visibly; section headings remain coherent.

## Scenario 4 - Smart One-Page

1. Set manual line spacing to 12.
2. Enable smart one-page.
3. Verify effective line spacing may be selected automatically.
4. Disable smart one-page.

Expected result: previous manual line spacing is restored. Content is never hidden or deleted.

## Scenario 5 - Export

1. Export Markdown.
2. Compare exported Markdown with source.
3. Export PDF for each of the three themes.
4. Export PDF with smart one-page enabled.
5. Simulate an export failure if the test harness supports it.

Expected result: Markdown preserves source; PDF matches live preview; pending/success/failure states are visible.

## Evidence

Final implementation evidence is under `docs/evidence/047-resume-editor-v3/`:

- `req-047-chromium-final.png`
- `req-047-export.md`
- `req-047-export.pdf`
- `vitest-full-results.json`
- `final-validation.md`
