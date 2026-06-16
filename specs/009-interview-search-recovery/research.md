# Research: Interview Search Recovery

## Decision: Normalize query with trim and lowercase before filtering

**Rationale**: Users expect search to ignore accidental leading/trailing spaces and case. This keeps the behavior predictable without changing API contracts.

**Alternatives considered**:

- Raw substring matching: rejected because whitespace and case mismatches create avoidable no-result states.
- Server-side search: rejected because the feature scope is currently loaded history recovery and does not require backend changes.

## Decision: Distinguish no-match search from true empty history

**Rationale**: A user with no records needs onboarding guidance, while a user with records but no search matches needs recovery. Combining both states would make the UI misleading.

**Alternatives considered**:

- Reuse the same empty copy for both states: rejected because it hides the active search query.
- Always show clear search: rejected because it would be irrelevant for true empty history with no active query.

## Decision: Validate with route-fixtured Playwright E2E

**Rationale**: The feature is interaction-heavy and depends on browser-visible list state. Route fixtures provide deterministic populated and empty history scenarios.

**Alternatives considered**:

- Component-only tests: rejected because they would not cover routing, auth bootstrap, and visible page recovery behavior.
- Full backend seeded E2E: rejected as unnecessary for a frontend-only search slice.
