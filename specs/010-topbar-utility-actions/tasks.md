# Tasks: Topbar Utility Actions

**Input**: Design documents from `/specs/010-topbar-utility-actions/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/topbar-utility-ui.md, quickstart.md

**Tests**: E2E tests are required by the feature scope and constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm existing files and selectors needed for this shell feature.

- [x] T001 Review existing topbar and settings structure in src/components/layout/Topbar.tsx and src/pages/Settings.tsx

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add tests first so fake controls are captured before implementation.

- [x] T002 [P] Create E2E coverage for help navigation, notifications panel, avatar menu destinations, and settings tab deep links in tests/e2e/topbar-utility-actions.spec.ts

**Checkpoint**: Tests describe the required behavior before UI implementation.

---

## Phase 3: User Story 1 - Help and notifications are actionable (Priority: P1) MVP

**Goal**: Help navigates and notifications open/close a concrete panel.

**Independent Test**: Click help and notification controls from the authenticated shell and verify routing/panel behavior.

### Implementation for User Story 1

- [x] T003 [US1] Implement Help navigation and stable selector in src/components/layout/Topbar.tsx
- [x] T004 [US1] Implement notification panel state, close behavior, settings link, accessibility state, and stable selectors in src/components/layout/Topbar.tsx

**Checkpoint**: User Story 1 is independently functional.

---

## Phase 4: User Story 2 - User menu items navigate to real destinations (Priority: P2)

**Goal**: Avatar menu items navigate to profile and existing settings destinations.

**Independent Test**: Open avatar menu and click each non-logout menu item, verifying the destination.

### Implementation for User Story 2

- [x] T005 [US2] Add navigation behavior, menu close behavior, accessibility state, and stable selectors for avatar menu items in src/components/layout/Topbar.tsx

**Checkpoint**: User Story 2 is independently functional.

---

## Phase 5: User Story 3 - Settings tabs support direct links (Priority: P3)

**Goal**: Settings supports `?tab=` deep links and keeps tab clicks in URL sync.

**Independent Test**: Visit supported and unsupported settings tab query values and verify active content; click tabs and verify URL changes.

### Implementation for User Story 3

- [x] T006 [US3] Add supported tab validation, URL initialization, tab click URL synchronization, and stable selectors in src/pages/Settings.tsx

**Checkpoint**: User Story 3 is independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete feature.

- [x] T007 Run npm run typecheck
- [x] T008 Run npx playwright test tests/e2e/topbar-utility-actions.spec.ts --workers=1
- [ ] T009 Verify the feature manually in the in-app Chrome browser

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): No dependencies.
- Foundational (Phase 2): Depends on setup and blocks implementation.
- User Story 1 (Phase 3): Depends on tests being written.
- User Story 2 (Phase 4): Can proceed after User Story 1 because it touches the same topbar file.
- User Story 3 (Phase 5): Can proceed after tests are written and is independent from topbar implementation.
- Polish (Phase 6): Depends on implemented stories.

### Parallel Opportunities

- T002 can be drafted while reviewing source context after T001.
- T006 touches Settings.tsx and can be implemented independently from T003-T005 if needed.

## Implementation Strategy

### MVP First

1. Complete T001-T004 to make help and notifications actionable.
2. Validate User Story 1 independently.
3. Add avatar menu destinations and settings deep links.
4. Run typecheck, E2E, and browser verification.
