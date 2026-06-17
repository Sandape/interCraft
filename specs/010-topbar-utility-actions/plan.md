# Implementation Plan: Topbar Utility Actions

**Branch**: `[010-topbar-utility-actions]` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-topbar-utility-actions/spec.md`

## Summary

Make always-visible topbar utility controls actionable: Help navigates to the help center, Notifications opens a local status panel with a settings link, Avatar menu items navigate to existing profile/settings destinations, and Settings supports query-driven tab selection for reliable deep links.

## Technical Context

**Language/Version**: TypeScript with React 18

**Primary Dependencies**: react-router-dom, lucide-react, existing Button/Avatar/ThemeToggle UI components

**Storage**: N/A; notification panel is local UI state

**Testing**: Playwright E2E plus TypeScript typecheck

**Target Platform**: Browser web application shell

**Project Type**: Frontend web application

**Performance Goals**: Utility panel opens/closes immediately from user perspective; no network dependency for notification panel

**Constraints**: Reuse existing routes and UI primitives; do not add backend notification feed scope

**Scale/Scope**: One shell component, one settings page deep-link behavior, one E2E test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Library-first: PASS. The change stays inside existing shell/page modules and does not create a new cross-cutting library.
- CLI interface: PASS with justified frontend exception. Validation is provided through existing npm scripts rather than a new CLI.
- Test-first: PASS. E2E tasks are defined before implementation and cover the changed interactions.
- Integration & synchronization testing: PASS. Browser-level E2E covers navigation and menu state transitions.
- Observability: PASS. No production data mutation or backend interaction is introduced.

## Project Structure

### Documentation (this feature)

```text
specs/010-topbar-utility-actions/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- topbar-utility-ui.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/
|-- components/
|   `-- layout/
|       `-- Topbar.tsx
`-- pages/
    `-- Settings.tsx

tests/
`-- tests/e2e/
    `-- topbar-utility-actions.spec.ts
```

**Structure Decision**: Implement in existing frontend shell/page files. No backend, repository, or shared data model additions are required.

## Complexity Tracking

No constitution violations requiring complexity justification.
