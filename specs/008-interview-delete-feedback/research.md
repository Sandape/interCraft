# Research: Interview Delete Feedback

## Decision: Keep delete error state local to the confirmation dialog

**Rationale**: The error only matters while the destructive confirmation is active. Local state avoids expanding query or repository contracts and lets retry/cancel behavior remain explicit.

**Alternatives considered**:

- Global toast only: rejected because it can disappear while the dialog remains ambiguous.
- Repository-level error mapping: rejected because the existing request layer already normalizes errors and no new contract is needed.

## Decision: Reuse the existing delete mutation and invalidate interview sessions on success

**Rationale**: The current hook already centralizes delete mutation and list invalidation. The page only needs to show success/failure state around it.

**Alternatives considered**:

- Manually mutate cached list: rejected for this slice because invalidation is already established and safer with server truth.
- Add a new repository method: rejected because the existing `delete(id)` method is sufficient.

## Decision: Validate with request-routed Playwright E2E

**Rationale**: The feature is user-visible and depends on browser interaction plus API success/failure outcomes. Route fixtures can deterministically simulate 204, 500, and retry without relying on backend state.

**Alternatives considered**:

- Unit-only testing: rejected because the main risk is destructive-flow user behavior and visible feedback.
- Full backend E2E: rejected as unnecessary for a frontend feedback slice that does not alter backend semantics.
