# Implementation Plan: Interview Resume Guardrails

**Branch**: `007-interview-resume-guardrails` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-interview-resume-guardrails/spec.md`

## Summary

Improve the existing mock interview continuation path so a candidate who re-enters an in-progress interview sees clear continuity: restored answers/questions/scores, elapsed time, a visible resumed notice, and stable test selectors. If resume loading fails, the live page must show a dedicated retryable error state instead of the new-interview setup form. The implementation is frontend-focused and reuses the existing interview session repository and live route.

## Technical Context

**Language/Version**: TypeScript 5.6 strict mode, React 18, Vite 5

**Primary Dependencies**: React Router, TanStack Query, lucide-react, existing interview session repository, Playwright for browser E2E

**Storage**: Existing backend interview session state only; no new storage

**Testing**: Vitest for component/logic coverage where useful; Playwright/browser control for focused E2E

**Target Platform**: Modern desktop browser in the existing Vite app

**Project Type**: Web application frontend slice

**Performance Goals**: Resume state renders within 10 seconds after continue; no duplicate session creation during resume

**Constraints**: Reuse existing `/interview/:id/live` route and interview session contracts; do not add backend endpoints or migrations; keep selectors stable without changing user-facing copy unnecessarily

**Scale/Scope**: One page (`src/pages/InterviewLive.tsx`), one list view selector update (`src/pages/InterviewList.tsx`), focused E2E coverage

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Library-First | Scope stays within existing interview frontend module; no new global state or cross-module abstraction | PASS |
| II. CLI Interface | Browser feature has no new CLI; validation is via existing npm scripts | PASS |
| III. Test-First | Tasks place E2E tests before implementation and verify failure/success paths | PASS |
| IV. Integration & Synchronization Testing | Resume success and failure are validated through browser E2E with network routing | PASS |
| V. Observability | UI exposes explicit resumed/error states and stable selectors for diagnostics | PASS |

No constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/007-interview-resume-guardrails/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- resume-ui.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/
|-- pages/
|   |-- InterviewLive.tsx
|   `-- InterviewList.tsx

tests/
`-- e2e/
    `-- interview-resume-guardrails.spec.ts
```

**Structure Decision**: Use the existing frontend page structure. No new backend module, migration, or repository is needed.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |

## Re-evaluation after Phase 1 design

The design remains frontend-only, test-first, and contract-preserving. Constitution status remains PASS.
