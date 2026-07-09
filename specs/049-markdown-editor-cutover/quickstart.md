# Quickstart: REQ-049 Markdown Editor Cutover and Pagination

## Preconditions

- Install project dependencies with the existing repository workflow.
- Ensure the active feature context points to `specs/049-markdown-editor-cutover` in `.specify/feature.json`.
- Do not rely on bash-only SpecKit scripts in this Windows environment unless bash is installed.

## Targeted Validation Commands

```bash
npm run typecheck
npm run test -- src/modules/resume/v2/store/__tests__/markdown-cutover-status.test.ts
npm run test -- src/modules/resume/renderer/__tests__/contact-container-rendering.test.ts src/modules/resume/v2/editor/__tests__/MarkdownResumeContactLayout.test.tsx
npm run test -- src/modules/resume/pagination/__tests__/markdown-pagination.test.ts src/modules/resume/v2/editor/__tests__/MarkdownResumePagination.test.tsx
npm run test -- src/modules/resume/v2/api/__tests__/export-v3.test.ts src/modules/resume/v2/editor/__tests__/ExportMenu.test.tsx
npm run test -- src/modules/resume/converter/__tests__/legacy-to-markdown.test.ts
npm run test -- src/pages/__tests__/ResumeEditorV2.markdown-cutover.test.tsx src/pages/__tests__/ResumeEditorV2.legacy-cutover.test.tsx
npm run test -- src/modules/resume/v2/editor/__tests__/BuilderShell.test.tsx src/modules/resume/v2/editor/__tests__/BuilderShell.markdown-cutover.test.tsx
npm run build
npm run e2e -- tests/e2e/049-markdown-editor-cutover.spec.ts --project=chromium
```

Run backend tests only if the implementation changes resume v2 API/export compatibility:

```bash
cd backend && uv run pytest -q app/modules/resumes_v2/tests/test_markdown_metadata.py app/modules/resumes_v2/tests/test_legacy_format.py app/modules/resumes_v2/tests/test_export.py
```

## Manual/E2E Acceptance Scenarios

1. Create a new resume from the resume list. The editor opens directly in Markdown mode.
2. Open an existing Markdown resume. Source, theme, line height, smart one-page state, and export controls are restored.
3. Open a structured-only older resume. All non-empty visible content appears as Markdown or a clear recoverable conversion warning.
4. Attempt a stale old editor link. The user lands on the Markdown editor route, not the structured editor.
5. Paste `fixtures/049-markdown-editor-cutover/contact-format-lab.md`. Verify contact rows in all three themes.
6. Paste `fixtures/049-markdown-editor-cutover/long-three-page.md`. Verify multiple preview pages with visible boundaries and no clipped content.
7. Enable smart one-page on the long fixture. Verify `infeasible` feedback and all pages remain visible.
8. Export PDF and Markdown. PDF page count matches preview; Markdown export preserves source without pagination artifacts.

## Required Evidence Before Marking Done

- Vitest output for renderer/contact/conversion/pagination/editor coverage.
- Playwright trace or screenshot evidence for Markdown-only entry points.
- Screenshots for contact format lab in all three themes.
- Screenshot or PDF evidence for 3-page pagination and export parity.
- Requirement status updates in [requirements-status.md](./requirements-status.md).
