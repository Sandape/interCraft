# Implementation Plan: Resume Editor v3 for InterCraft v2

**Branch**: `047-resume-editor-v3` | **Date**: 2026-07-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/047-resume-editor-v3/spec.md`

**Setup Note**: `.specify/scripts/bash/setup-plan.sh --json` could not run because `bash` is unavailable in this Windows environment. Equivalent paths were resolved from `.specify/feature.json`, and this plan was created at `specs/047-resume-editor-v3/plan.md`.

## Summary

Build the first scoped InterCraft v2 resume editor v3 by fully replicating Muji CV's observed behavior for Markdown resume rendering, three themes, line spacing, smart one-page, and PDF/MD export. The implementation should reuse and harden the existing `src/modules/resume` boundaries: `renderer`, `themes`, `pagination`, `converter`, `editor`, `api`, and related tests.

## Technical Context

**Language/Version**: TypeScript 5.6, React 18, Vite 5

**Primary Dependencies**: markdown-it, markdown-it-container, markdown-it-emoji, rs-md-html-parser, React Testing Library, Vitest, Playwright E2E, existing resume v2 API client

**Storage**: Existing resume v2 persistence for Markdown source and per-resume settings; no new backend persistence model is required unless implementation discovers current resume data shape cannot store Markdown source plus render settings.

**Testing**: Vitest for renderer/themes/pagination/export units and components; Playwright E2E in `tests/e2e/` for end-to-end editor/export behavior; `npm run typecheck`; `npm run build`.

**Target Platform**: Web application in the existing InterCraft frontend, backed by existing FastAPI resume v2/export endpoints where needed.

**Project Type**: Frontend feature module with existing backend export integration.

**Performance Goals**:

- Markdown preview updates within one second after edits settle.
- Line spacing/theme/smart one-page changes update preview within one second for representative one-page and near-two-page resumes.
- Export actions surface a pending state within 500ms and complete or fail with visible feedback.

**Constraints**:

- First version scope is limited to Muji-compatible Markdown rendering, exactly three themes, line spacing 12-25, smart one-page, and PDF/MD export.
- User-facing product copy must not expose internal "v3" naming.
- Smart one-page must not hide or delete content.
- Local image upload/crop is out of scope; Markdown image syntax supports external URL images only.
- PDF export fidelity is a release gate.

**Scale/Scope**:

- Three themes: 默认（秋风同款）, 极简色, 平面大气主题.
- Markdown dialect covers standard syntax plus Muji-compatible containers/icons captured in competitor evidence.
- Representative resumes: fitting one-page, near-one-page, infeasible multi-page, tables, external images, long URLs, nested lists.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Result | Plan Response |
|---|---|---|
| I. Library-First | PASS | Keep Markdown renderer, theme registry/CSS, line-height/smart one-page engine, and export adapter as self-contained module boundaries under `src/modules/resume`. |
| II. CLI Interface | PASS | Preserve/extend renderer CLI contract for Markdown fixture rendering; document validation commands in `quickstart.md`. No new backend CLI required for this frontend-scoped feature. |
| III. Test-First | PASS | Tasks must start with failing Vitest/Playwright coverage for Markdown syntax, theme snapshots, line-height, smart one-page, and export states. |
| IV. Integration & Synchronization Testing | PASS | Add E2E coverage for editor preview, theme/line-height/smart one-page interactions, and PDF/MD export entry points. |
| V. Observability | PASS | Export and smart one-page failures must produce visible UI states and structured client-side error context where existing logging facilities support it. |

## Project Structure

### Documentation (this feature)

```text
specs/047-resume-editor-v3/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── markdown-rendering-contract.md
│   ├── theme-spacing-onepage-contract.md
│   └── export-contract.md
├── requirements-status.md
└── tasks.md              # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
src/modules/resume/
├── renderer/             # Muji-compatible Markdown parser/render pipeline
├── themes/               # Three-theme registry and runtime CSS
├── styles/               # Theme/style CSS assets
├── pagination/           # Page measurement and smart one-page helpers
├── converter/            # Markdown import/export helpers
├── editor/               # Markdown source editor, preview, toolbar controls
├── api/                  # Existing v2 API/export integration types
└── v2/                   # Existing persisted resume shell and export API client

tests/e2e/
└── 047-resume-editor-v3.spec.ts
```

**Structure Decision**: Use the existing `src/modules/resume` self-contained module as the feature boundary. Add or harden submodule APIs rather than creating a separate `resume-v3` tree.

## Phase 0: Research Output

See [research.md](./research.md). All planning-time decisions are resolved; no `NEEDS CLARIFICATION` items remain.

## Phase 1: Design Output

- Data model: [data-model.md](./data-model.md)
- Contracts:
  - [markdown-rendering-contract.md](./contracts/markdown-rendering-contract.md)
  - [theme-spacing-onepage-contract.md](./contracts/theme-spacing-onepage-contract.md)
  - [export-contract.md](./contracts/export-contract.md)
- Validation guide: [quickstart.md](./quickstart.md)

## Constitution Check - Post-Design

| Principle | Gate Result | Notes |
|---|---|---|
| I. Library-First | PASS | Data model and contracts keep renderer/theme/pagination/export boundaries independent. |
| II. CLI Interface | PASS | Quickstart includes renderer CLI-style validation and standard npm commands. |
| III. Test-First | PASS | Quickstart and contracts define testable behavior before implementation tasks are generated. |
| IV. Integration & Synchronization Testing | PASS | E2E scenarios cover cross-boundary editor behavior and export parity. |
| V. Observability | PASS | Export/smart-one-page failure states are contractual and testable. |

## Complexity Tracking

No constitution violations are introduced by this plan.

