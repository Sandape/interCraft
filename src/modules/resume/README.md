# Resume Module

This module owns InterCraft resume editing, rendering, theming, pagination, and
export behavior. REQ-049 makes the Markdown resume editor the only active
resume editing route. Legacy structured resume data is converted into Markdown
on open and staged back through the v2 resume API.

## REQ-047 Boundaries

- `renderer/`: Muji-compatible Markdown to safe HTML. The public entry point is
  `renderMarkdown`; unsafe protocols and raw scripts are stripped and surfaced as
  render warnings.
- `themes/`: exactly three v3 themes are exposed through `listV3Themes()`:
  `muji-default-autumn`, `muji-minimal-color`, and `muji-flat-atmospheric`.
- `pagination/`: line-height presets (`12` through `25`) and smart one-page
  fitting live in `line-height.ts` and `smart-one-page.ts`.
- `v2/schema` and `v2/store`: `metadata.markdown` persists source Markdown,
  selected theme, manual line-height, smart one-page state, and effective
  smart-fit results.
- `v2/editor/MarkdownResumeEditor.tsx` and `v2/editor/controls/`: the live
  Markdown editor, preview, theme menu, line spacing menu, smart one-page
  toggle, and PDF/Markdown export controls.

## Fixtures

- Unit renderer fixture:
  `src/modules/resume/renderer/__fixtures__/muji-format-lab.md`
- E2E fixtures:
  `tests/e2e/fixtures/047-resume-editor-v3/format-lab.md`
  `tests/e2e/fixtures/047-resume-editor-v3/format-lab-inline.ts`
  `tests/e2e/fixtures/047-resume-editor-v3/smart-one-page-fixtures.ts`

## Validation

REQ-047 target validation:

```bash
npm run test -- src/modules/resume/v2/schema/__tests__/markdown-metadata.test.ts src/modules/resume/v2/store/__tests__/markdown-settings.test.ts src/modules/resume/renderer/__tests__/muji-markdown-dialect.test.ts src/modules/resume/renderer/__tests__/muji-markdown-safety.test.ts src/modules/resume/pagination/__tests__/line-height-presets.test.ts src/modules/resume/pagination/__tests__/smart-one-page.test.ts src/modules/resume/themes/__tests__/muji-v3-themes.test.ts src/modules/resume/v2/editor/__tests__/MarkdownResumeEditor.test.tsx src/modules/resume/v2/editor/__tests__/MarkdownResumePreviewThemes.test.tsx src/modules/resume/v2/editor/__tests__/ThemeMenu.test.tsx src/modules/resume/v2/editor/__tests__/LineSpacingControl.test.tsx src/modules/resume/v2/editor/__tests__/SmartOnePageControl.test.tsx src/modules/resume/v2/editor/__tests__/ExportMenu.test.tsx src/modules/resume/converter/__tests__/markdown-export-v3.test.ts src/modules/resume/v2/api/__tests__/export-v3.test.ts
npm run e2e -- tests/e2e/047-resume-editor-v3.spec.ts --project=chromium
```

Full release validation evidence is recorded in
`docs/evidence/047-resume-editor-v3/final-validation.md`.

## REQ-049 Cutover Boundaries

- `/resume/:id` is the canonical editor route. Stale `/resume/v2/:id` links
  redirect to the same Markdown editor route.
- `v2/editor/BuilderShell.tsx` renders the Markdown editor, duplicate action,
  and PDF/Markdown export controls. Retired structured panels, template gallery
  controls, and dock controls are not part of the active shell.
- `converter/legacy-to-markdown.ts` converts older structured resume data into
  editable Markdown and records conversion status in `metadata.markdown`.
- `pagination/markdown-pages.ts` splits rendered Markdown HTML into ordered A4
  preview pages used by preview and export parity checks.
- REQ-049 validation evidence is recorded in
  `docs/evidence/049-markdown-editor-cutover/final-validation.md`.
