# Feature Specification: Topbar Utility Actions

**Feature Branch**: `[010-topbar-utility-actions]`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Continue mining the next requirement. Some frontend buttons are fake; implement concrete functionality."

## Clarifications

### Session 2026-06-16

- Q: Should topbar utilities introduce new backend-backed destinations or reuse existing app destinations? -> A: Reuse existing destinations; notifications use a local status panel in this increment.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Help and notifications are actionable (Priority: P1)

A signed-in user can use the topbar help and notification controls without dead-end clicks. Help takes the user to the existing help center. Notifications open a compact panel that explains the current notification state and offers relevant actions.

**Why this priority**: These buttons are always visible in the shell, so dead actions reduce trust across the entire app.

**Independent Test**: From any authenticated page, click Help and verify the Help page opens; return to the dashboard, click Notifications and verify a notification panel opens and closes predictably.

**Acceptance Scenarios**:

1. **Given** an authenticated user on the dashboard, **When** they click the help icon, **Then** they are routed to the help center.
2. **Given** an authenticated user on the dashboard, **When** they click the notification icon, **Then** a notification panel opens with a visible heading, unread count/status, and a link to notification settings.
3. **Given** the notification panel is open, **When** the user presses Escape or clicks outside the panel, **Then** the panel closes and focusable page controls remain usable.

---

### User Story 2 - User menu items navigate to real destinations (Priority: P2)

A signed-in user can open the avatar menu and use each non-logout menu item to navigate to the corresponding profile, settings, subscription, or data export destination.

**Why this priority**: The avatar menu currently appears complete but contains non-functional items, which creates misleading navigation.

**Independent Test**: Open the avatar menu and click each menu item independently, verifying the URL and visible destination match the item.

**Acceptance Scenarios**:

1. **Given** the avatar menu is open, **When** the user clicks Personal Profile, **Then** the profile page opens.
2. **Given** the avatar menu is open, **When** the user clicks Account Settings, **Then** the settings page opens on the profile tab.
3. **Given** the avatar menu is open, **When** the user clicks Upgrade, **Then** the settings page opens on the subscription tab.
4. **Given** the avatar menu is open, **When** the user clicks Data Export, **Then** the settings page opens on the export tab.

---

### User Story 3 - Settings tabs support direct links (Priority: P3)

A signed-in user can open a settings sub-section directly from a URL and tab clicks keep the URL in sync, so topbar menu destinations are shareable and reload-safe.

**Why this priority**: Topbar menu navigation depends on deterministic settings sub-routes without adding new pages.

**Independent Test**: Visit settings with `?tab=export`, verify the export tab is active, click another tab, reload, and verify the URL reflects the active tab.

**Acceptance Scenarios**:

1. **Given** a user opens settings with a supported tab query, **When** the page loads, **Then** that tab is active.
2. **Given** a user opens settings with an unsupported tab query, **When** the page loads, **Then** the profile tab is active and the UI remains stable.
3. **Given** a user selects a settings tab, **When** the tab changes, **Then** the browser URL updates to the matching `?tab=` value.

### Edge Cases

- Notification panel must not stay open after navigating away through its settings link.
- Avatar menu and notification panel must not be open at the same time.
- Unsupported settings tab query values must not render a blank settings content area.
- Keyboard users must be able to close the notification panel with Escape.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The topbar help control MUST navigate to the existing help center.
- **FR-002**: The topbar notification control MUST toggle a panel with a clear title, notification state, and a link to notification settings.
- **FR-003**: The notification panel MUST close when the user clicks outside it, presses Escape, or follows its settings link.
- **FR-004**: Opening the notification panel MUST close the avatar menu; opening the avatar menu MUST close the notification panel.
- **FR-005**: User menu items MUST navigate to real destinations for profile, account settings, subscription, and data export.
- **FR-006**: Settings MUST initialize the active tab from a supported `tab` query value.
- **FR-007**: Settings MUST fall back to the profile tab for missing or unsupported `tab` query values.
- **FR-008**: Settings tab changes MUST update the browser URL so reloads preserve the selected tab.
- **FR-009**: All new interactive controls MUST expose stable test identifiers and appropriate accessibility state for E2E verification.

### Key Entities

- **Topbar Utility Action**: A visible shell control such as help, notifications, or avatar menu item; key attributes include label, destination or panel behavior, and open/closed state.
- **Notification Panel State**: The transient visible state of the notification panel; key attributes include open status, notification count/status, and close trigger.
- **Settings Tab Selection**: The active settings tab represented by a supported tab key in the URL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of always-visible topbar utility buttons perform a user-visible action within one click.
- **SC-002**: Users can reach help, profile, subscription, export, and notification settings destinations from the topbar in under two clicks each.
- **SC-003**: Reloading a supported settings tab URL preserves the intended tab in 100% of tested tab values.
- **SC-004**: Notification panel open and close interactions complete without page reload and without blocking other page controls.

## Assumptions

- Existing authenticated shell, help page, profile page, and settings page are reused.
- The first version does not require a backend notification feed; it may show a local status/empty-state panel with links to notification settings.
- Existing logout behavior remains unchanged.
- This feature is scoped to desktop and responsive shell behavior already supported by the current topbar.
