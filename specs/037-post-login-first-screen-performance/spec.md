# Feature Specification: Post-Login First-Screen Performance

**Feature Branch**: `037-post-login-first-screen-performance`

**Created**: 2026-06-30

**Status**: Draft

**Input**: User description: "当前的首屏加载很慢，每次登录后都要等一阵子才有后续，定位问题，并提出解决方案。记录为一个新的REQ"

## Problem Summary

Users report that after a successful login, the application pauses on the first screen before they can continue. Initial investigation found two user-visible contributors:

1. A confirmed login can be followed by a second identity validation state that temporarily makes the app treat the session as unresolved, so the protected app shell is held behind a full-screen loading state.
2. The dashboard first screen requests several independent data areas at once, including some optional recommendation and history data. Slow optional data can make the first screen feel blocked even when the user only needs navigation, greeting, and primary actions.

The proposed product direction is to separate "session is ready" from "background profile/data refresh is still running", and to make the dashboard render progressively from a small critical first-screen budget while secondary insights load independently.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Login Lands Without Reblocking (Priority: P1)

As a returning user, after entering valid credentials I need to land in the authenticated app without seeing another long "verifying login" pause, so I can continue immediately.

**Why this priority**: This is the reported pain point and affects every login. It is the minimum viable fix for perceived first-screen speed.

**Independent Test**: Simulate a valid login where the login response already contains the user identity, delay the follow-up identity refresh, and verify that the authenticated shell remains visible and interactive.

**Acceptance Scenarios**:

1. **Given** a user submits valid credentials, **When** login succeeds, **Then** the authenticated shell and dashboard route become visible without a full-screen login-verification pause.
2. **Given** the background identity refresh takes 3 seconds, **When** the user has just logged in successfully, **Then** navigation, top-level actions, and the dashboard route remain mounted during that refresh.
3. **Given** the background identity refresh later confirms the same user, **When** it completes, **Then** the displayed user information is updated without remounting the first screen.

---

### User Story 2 - Dashboard Renders Progressively (Priority: P1)

As a logged-in user, I need the dashboard shell, greeting, primary actions, and core empty/data states to appear quickly even if recommendations, activity history, or other secondary panels are still loading.

**Why this priority**: The dashboard is the default post-login destination. It must provide immediate continuity rather than waiting for every panel.

**Independent Test**: Delay secondary dashboard data sources while allowing critical first-screen data to resolve, then verify that the dashboard remains usable and shows independent loading or empty states for delayed panels.

**Acceptance Scenarios**:

1. **Given** optional recommendation data is slow, **When** the user reaches the dashboard, **Then** the main layout, greeting, and primary action buttons are visible within the performance budget.
2. **Given** activity, job, error-book, or suggestion data fails, **When** the dashboard opens, **Then** the page still renders with a non-blocking panel state instead of a blank or full-screen loader.
3. **Given** a brand-new user has no historical data, **When** the dashboard opens, **Then** the first screen shows useful empty states and primary next actions without waiting for unrelated lists.

---

### User Story 3 - First-Screen Data Budget Is Controlled (Priority: P2)

As a product owner, I need the post-login first screen to have a clear data budget so future dashboard additions do not silently slow down every login.

**Why this priority**: The current symptom can recur if new panels add more first-screen work without measurement or budget enforcement.

**Independent Test**: Capture the login-to-dashboard waterfall and assert that critical first-screen rendering is not blocked by duplicate or secondary data requests.

**Acceptance Scenarios**:

1. **Given** the dashboard needs data from multiple product areas, **When** it first renders after login, **Then** only critical first-screen data is allowed to block the visible shell.
2. **Given** two dashboard panels need the same domain data, **When** the first screen loads, **Then** the system reuses one result or defers non-critical detail instead of fetching duplicate first-screen data.
3. **Given** a secondary panel requires broader historical data, **When** the first screen loads, **Then** that panel loads after the shell is visible or uses a compact summary.

---

### User Story 4 - Performance Regression Evidence Exists (Priority: P2)

As an engineer maintaining InterCraft, I need repeatable measurements and tests for the login-to-dashboard path so that future changes cannot reintroduce the slow first-screen behavior unnoticed.

**Why this priority**: Performance fixes are only trustworthy if the before/after behavior is measured and guarded.

**Independent Test**: Run an automated scenario for valid login, slow identity refresh, and slow secondary dashboard data; verify timing, visible states, and request budget.

**Acceptance Scenarios**:

1. **Given** the login-to-dashboard scenario is executed in a browser, **When** the test completes, **Then** evidence records the time to authenticated shell, time to first dashboard content, and time until all panels settle.
2. **Given** identity refresh is artificially delayed, **When** the scenario runs, **Then** the test fails if the authenticated shell is replaced by a full-screen auth loader after login success.
3. **Given** optional dashboard data is artificially delayed or fails, **When** the scenario runs, **Then** the test fails if critical dashboard actions are blocked.

### Edge Cases

- Stale or expired tokens on cold page load must still be rejected before protected data is shown.
- Login success followed by a failed background identity refresh must show a recoverable session problem without leaving the user in an infinite loading state.
- First-time users with no resumes, interviews, jobs, activities, or error-book entries must still see a useful first screen.
- Users with an avatar must not have first-screen navigation blocked by avatar image loading.
- Slow backend or network conditions must degrade into panel-level loading states, not a full-page blank state.
- Logout and session expiry must continue to clear protected content promptly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: After a valid login response that includes user identity, the system MUST treat the session as ready for protected first-screen rendering.
- **FR-002**: Background identity refresh MUST NOT change a confirmed authenticated session back to an unresolved full-screen loading state unless the session is proven invalid.
- **FR-003**: Cold loads with missing, stale, or invalid tokens MUST continue to block protected content and route the user to login.
- **FR-004**: The post-login destination MUST define a critical first-screen content set: app shell, navigation, user greeting or fallback name, primary actions, and core dashboard skeleton or empty states.
- **FR-005**: Non-critical dashboard panels MUST load independently after the critical first-screen content is visible.
- **FR-006**: Failure of non-critical dashboard panels MUST NOT prevent the user from using primary navigation or dashboard actions.
- **FR-007**: The first-screen data plan MUST avoid duplicate blocking reads for the same domain data during the initial dashboard render.
- **FR-008**: Broader historical lists used only for recommendations MUST be deferred, summarized, or reused from existing first-screen data.
- **FR-009**: Avatar or decorative media loading MUST NOT block the authenticated shell or dashboard first-screen actions.
- **FR-010**: The login-to-dashboard path MUST expose measurable timing evidence for shell visibility, first dashboard content, and all-panels-settled states.
- **FR-011**: Automated coverage MUST include valid login with delayed identity refresh, stale-token cold load, delayed optional dashboard data, and optional dashboard failure.
- **FR-012**: User-facing loading states MUST distinguish between session verification, critical dashboard loading, and secondary panel loading.

### Key Entities

- **Session Readiness**: The user-visible state that determines whether the authenticated shell may render.
- **Critical First-Screen Content**: The minimum post-login content needed for the user to continue: shell, navigation, greeting, primary actions, and stable dashboard structure.
- **Secondary Dashboard Content**: Suggestions, activity history, broad historical lists, avatars, and other panels that can load after the first screen is usable.
- **Performance Evidence**: Browser-run timing and request-budget records for the login-to-dashboard path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the valid-login scenario, the authenticated app shell is visible within 1.0 second in local/staging synthetic validation.
- **SC-002**: After valid login success, no full-screen auth verification loader remains visible for more than 250 ms unless the session is later proven invalid.
- **SC-003**: Dashboard greeting, navigation, and primary actions are visible within 1.5 seconds under normal local/staging validation.
- **SC-004**: With secondary dashboard data delayed by 3 seconds, the dashboard shell and primary actions still become usable within 1.5 seconds.
- **SC-005**: With one secondary dashboard data source failing, the page remains usable and shows a panel-level empty/error state.
- **SC-006**: The initial dashboard render reduces blocking first-screen data reads by at least 40% from the measured baseline, or stays within an agreed budget of no more than four blocking data domains.
- **SC-007**: Stale-token cold-load behavior remains secure: protected content is not mounted before session validity is resolved.
- **SC-008**: A before/after browser evidence report records timing, request count, and screenshots or trace artifacts for the login-to-dashboard scenario.

## Assumptions

- The reported slowdown is observed in real API mode, not mock-only development mode.
- The login response contains enough user identity information to render the authenticated shell immediately after success.
- Security must not be weakened: stale tokens on app startup still require verification before protected content appears.
- The initial diagnosis points to session-readiness regression after login success plus dashboard first-screen data fan-out; implementation planning must confirm with a browser waterfall before changing behavior.
- Desktop web is the primary validation target for this REQ; mobile should not regress but is not the lead performance target.

## Out of Scope

- Redesigning the dashboard visual layout.
- Changing authentication methods or token lifetimes.
- Replacing existing dashboard product concepts.
- Optimizing deep editor, resume export, interview live session, or admin dashboard performance outside the login-to-dashboard path.
