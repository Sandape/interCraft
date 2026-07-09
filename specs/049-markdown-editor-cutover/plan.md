# Implementation Plan: Markdown Editor Cutover and Pagination (REQ-049)

**Branch**: `049-markdown-editor-cutover` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/049-markdown-editor-cutover/spec.md`

**Setup Note**: `.specify/scripts/bash/setup-plan.sh --json` could not run because `bash` is unavailable in this Windows environment. Equivalent paths were resolved from `.specify/feature.json`: `FEATURE_SPEC=specs/049-markdown-editor-cutover/spec.md`, `IMPL_PLAN=specs/049-markdown-editor-cutover/plan.md`, `SPECS_DIR=specs/049-markdown-editor-cutover`. The current git branch is `master`; the SpecKit feature branch name remains `049-markdown-editor-cutover`.

## Summary

Retire the legacy structured resume editor from all user-facing resume editing routes and make the REQ-047 Markdown editor the single editing surface. Harden the Markdown route by adding deterministic legacy-content conversion, correcting Muji-compatible `::: left` and `::: right` contact/icon rendering, and replacing the current single-page preview estimate with real page-aware preview pagination that PDF export uses as the source of truth.

The implementation should extend the existing `src/modules/resume` boundaries instead of creating a separate resume editor stack. The highest-risk code paths are `src/pages/ResumeEditorV2.tsx`, `src/modules/resume/v2/editor/BuilderShell.tsx`, legacy structured editor panels under `src/modules/resume/v2/editor/left|dialogs|center`, the Markdown editor in `src/modules/resume/v2/editor/MarkdownResumeEditor.tsx`, the renderer container plugin in `src/modules/resume/renderer/markdown-it-plugins/containers.ts`, and pagination helpers under `src/modules/resume/pagination`.

## Technical Context

**Language/Version**: TypeScript 5.6, React 18, Vite 5 for the frontend. Python 3.11 and FastAPI are relevant only where existing resume v2 APIs or export services must preserve compatibility.

**Primary Dependencies**: markdown-it, markdown-it-container, markdown-it-emoji, rs-md-html-parser, Zustand, TanStack Query, React Testing Library, Vitest, Playwright E2E, existing resume v2 API/export clients.

**Storage**: Reuse existing resume v2 persistence. Markdown source and render settings continue to live in `metadata.markdown`. Older structured `data` remains recoverable and is converted into Markdown on open or through an explicit safe fallback path. No new database table is planned unless implementation discovers that a durable conversion audit is required.

**Testing**: Vitest for renderer, contact block, conversion, pagination, smart one-page, route/component behavior, and export payload units. Playwright E2E in `tests/e2e/` for full edit-preview-export acceptance. Backend pytest only if API/export or legacy-format behavior changes.

**Target Platform**: Existing authenticated web application resume editor plus existing PDF/Markdown export paths.

**Project Type**: Frontend-dominant web app feature with existing backend resume v2/export integration.

**Performance Goals**:

- Markdown preview reflects edits within 1 second after typing settles.
- Pagination recalculates within 1 second for a representative 3-page resume after theme, line-height, or source changes settle.
- Export presents a pending state within 500 ms and exports the same page count/order as preview.
- Contact block layout remains stable while switching across the three REQ-047 themes.

**Constraints**:

- No user-facing path may open the legacy structured editor after cutover.
- Product copy must not expose internal names such as `REQ-047`, `REQ-049`, or `v3`.
- Cutover must not silently delete or hide older resume content.
- Smart one-page may reduce line height within the existing 12-25 range, but it must not clip or remove content.
- PDF export fidelity for contact alignment and pagination is a release gate.
- Keep existing dirty worktree changes intact; implementation tasks must not revert unrelated historical editor code unless the task explicitly removes or disconnects it.

**Scale/Scope**:

- One authenticated resume editing surface.
- Three REQ-047 Markdown themes: `muji-default-autumn`, `muji-minimal-color`, `muji-flat-atmospheric`.
- Representative fixtures: Markdown source resume, older structured resume without Markdown, contact format lab, and at least one 3-page Markdown resume with headings, lists, tables, links, and contact containers.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Result | Plan Response |
|---|---|---|
| I. Library-First | PASS | Keep conversion, renderer/contact normalization, pagination, smart one-page, and export-page serialization as self-contained module boundaries under `src/modules/resume`. |
| II. CLI Interface | PASS | Frontend core logic must expose pure helpers and fixture-driven tests. Existing `src/modules/resume/renderer/cli.ts` remains the CLI-style validation surface for Markdown rendering. No new backend CLI is required. |
| III. Test-First | PASS | Tasks must begin with failing Vitest and Playwright coverage for each user story before implementation changes. |
| IV. Integration & Synchronization Testing | PASS | E2E coverage must traverse creation, direct old links, legacy conversion, contact rendering, pagination, smart one-page fallback, and PDF/MD export parity. |
| V. Observability | PASS | Conversion warnings, pagination states, smart one-page infeasible status, and export failures must surface user-visible feedback and structured debug context through existing logging/error facilities where available. |

## Project Structure

### Documentation (this feature)

```text
specs/049-markdown-editor-cutover/
|-- README.md
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- requirements-status.md
|-- contracts/
|   |-- editor-cutover.md
|   |-- contact-container-rendering.md
|   |-- pagination-preview-export.md
|   `-- legacy-content-migration.md
`-- tasks.md                 # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
src/
|-- App.tsx                                      # resume editor route registration
|-- pages/
|   `-- ResumeEditorV2.tsx                       # cutover entrypoint and legacy handling
`-- modules/resume/
    |-- renderer/
    |   |-- index.ts                             # Markdown render pipeline
    |   |-- parser.ts
    |   |-- types.ts
    |   |-- cli.ts
    |   |-- markdown-it-plugins/
    |   |   `-- containers.ts                    # left/right/header/title container rendering
    |   `-- icons/
    |-- pagination/
    |   |-- index.ts                             # DOM pagination integration
    |   |-- smart-one-page.ts
    |   |-- line-height.ts
    |   `-- constants.ts
    |-- themes/
    |   `-- registry.ts
    |-- converter/
    |   |-- markdown-converter.ts
    |   |-- markdown-export.ts
    |   `-- markdown-parser.ts
    `-- v2/
        |-- editor/
        |   |-- MarkdownResumeEditor.tsx         # Markdown-only editor surface
        |   |-- markdown-resume.css
        |   |-- controls/
        |   |-- BuilderShell.tsx                 # legacy structured shell to retire or bypass
        |   |-- left/ dialogs/ center/           # legacy structured controls to remove from UX
        |-- store/
        |-- schema/
        `-- api/

backend/app/modules/resumes_v2/
|-- api.py
|-- service.py
|-- schemas.py
|-- repository.py
|-- cli.py
`-- tests/                                      # only touched if compatibility/export contracts change

tests/e2e/
|-- 049-markdown-editor-cutover.spec.ts
`-- fixtures/049-markdown-editor-cutover/
    |-- contact-format-lab.md
    |-- long-three-page.md
    `-- legacy-structured-resume.json
```

**Structure Decision**: Use the existing `src/modules/resume` feature module. REQ-049 is a cutover and hardening pass over REQ-047, not a new editor product tree. Legacy structured editor files may remain in the repository during the first implementation slice, but they must be disconnected from active user-facing editing routes and covered by regression tests that prevent their controls from appearing.

## Phase 0: Research Output

See [research.md](./research.md). All planning-time unknowns are resolved.

## Phase 1: Design Output

- Data model: [data-model.md](./data-model.md)
- Contracts:
  - [editor-cutover.md](./contracts/editor-cutover.md)
  - [contact-container-rendering.md](./contracts/contact-container-rendering.md)
  - [pagination-preview-export.md](./contracts/pagination-preview-export.md)
  - [legacy-content-migration.md](./contracts/legacy-content-migration.md)
- Validation guide: [quickstart.md](./quickstart.md)

## Constitution Check - Post-Design

| Principle | Gate Result | Notes |
|---|---|---|
| I. Library-First | PASS | Design keeps conversion, contact rendering, pagination, smart one-page, and export contracts modular and testable. |
| II. CLI Interface | PASS | Quickstart includes renderer CLI-style checks and fixture-driven commands; pure helpers are required for browser-independent validation. |
| III. Test-First | PASS | Contracts define testable failures before task generation, including E2E acceptance gates. |
| IV. Integration & Synchronization Testing | PASS | Contracts require route-to-editor, migration, preview, pagination, and export integration tests. |
| V. Observability | PASS | User-visible warnings and debug state are explicit model fields and acceptance criteria. |

## Complexity Tracking

No constitution violations are introduced by this plan.
