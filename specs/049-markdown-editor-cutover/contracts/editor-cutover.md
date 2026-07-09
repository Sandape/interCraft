# Contract: Markdown-Only Editor Cutover

## Purpose

Guarantee that users can no longer reach the legacy structured resume editor as an active editing experience after REQ-049.

## Entry Points

The following paths must land on the Markdown editor:

- Resume list create action.
- Resume list open/edit action.
- Duplicate/open flow for an existing resume.
- Direct route `/resume/:id`.
- Any stale in-app link or bookmark that previously opened the structured editor.

## Required UI Contract

When the editor is loaded:

- `data-testid="markdown-source-editor"` is present.
- Markdown preview pages are present.
- Theme control, line spacing control, smart one-page control, and export controls are available.
- Legacy structured-section controls are absent from the active UI.
- Legacy template/gallery/dock controls are absent from the active UI.
- Product copy does not expose internal labels such as `REQ-047`, `REQ-049`, or `v3`.

## Legacy Route Behavior

Older links must be redirected or resolved to the Markdown editor without data loss.

Expected outcomes:

- If the resume has Markdown source, restore the source and render settings.
- If the resume has structured content only, run the legacy migration contract.
- If the resume cannot be loaded, show the existing not-found/forbidden/error states without offering the old editor as an edit target.

## Test Contract

Automated coverage must include:

- Component or route tests proving `ResumeEditorV2` mounts the Markdown editor.
- Regression tests that fail if `BuilderShell` exposes old section editing controls as the active editor.
- E2E tests for create, open, direct route, and stale-link behavior.
- DOM assertions that no active old structured editor controls are visible.

## Acceptance Gates

- 100 percent of tested resume editing entry points open the Markdown editor.
- No active legacy editing controls are visible in acceptance screenshots.
- Existing Markdown resumes preserve source, theme, line height, smart state, and export availability.

