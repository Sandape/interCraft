# Research: Topbar Utility Actions

## Decision: Reuse existing routes for all menu destinations

**Rationale**: The app already has `/help`, `/profile`, and `/settings`. Reusing these avoids adding duplicate pages and keeps the feature focused on converting fake controls into working navigation.

**Alternatives considered**:

- Create new pages for billing/export/profile actions: rejected because existing Settings sections already represent the intended destinations.
- Keep menu items as disabled placeholders: rejected because the user explicitly asked to implement fake frontend buttons.

## Decision: Implement notifications as a local panel

**Rationale**: There is no current notification feed contract in scope. A local panel gives the bell button an honest action, communicates the current state, and links to notification preferences without inventing backend data.

**Alternatives considered**:

- Add notification API and persistence: rejected as too large for this targeted shell fix.
- Navigate directly to notification settings on bell click: rejected because a bell conventionally opens a notification tray, and settings can still be provided inside the tray.

## Decision: Represent Settings sub-sections with `?tab=` query values

**Rationale**: Settings already renders sub-tabs inside one route. Query values provide reload-safe, shareable deep links without changing router structure.

**Alternatives considered**:

- Add nested `/settings/:tab` routes: rejected because it requires broader route changes for no user-visible advantage.
- Store active tab only in component state: rejected because topbar menu destinations would not be reload-safe.

## Decision: E2E coverage through authenticated shell route fixtures

**Rationale**: The changed behavior is primarily browser navigation and transient UI state. Playwright can validate the user-visible flows using existing app routes and lightweight route fixtures.

**Alternatives considered**:

- Unit-only tests: rejected because the highest risk is interaction between shell controls, routing, and settings state.
