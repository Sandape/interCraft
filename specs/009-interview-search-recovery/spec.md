# Feature Specification: Interview Search Recovery

**Feature Branch**: `009-interview-search-recovery`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Improve mock interview history search so users can filter by company or position, understand empty search results, and clear the query to recover the full list."

## Clarifications

### Session 2026-06-16

- Q: What should happen when search returns no interview records? -> A: Show a query-specific empty state with a clear-search action that restores the full interview history list.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Filter interview history (Priority: P1)

An authenticated user with interview history can search by company or position and see only matching interview records.

**Why this priority**: Search only creates value if the filtered result is accurate and immediately understandable.

**Independent Test**: Can be fully tested by loading history with multiple records, entering a company or position query, and verifying only matching records remain visible.

**Acceptance Scenarios**:

1. **Given** the history list contains records from multiple companies, **When** the user searches for one company name, **Then** only matching company records remain visible.
2. **Given** the history list contains multiple positions, **When** the user searches for a position keyword, **Then** only matching position records remain visible.

---

### User Story 2 - Recover from no search results (Priority: P1)

An authenticated user whose search returns no records can see that the query has no matches and clear the query with one action.

**Why this priority**: Empty search results without recovery make the list look broken or permanently empty.

**Independent Test**: Can be fully tested by entering a query with no matches, verifying a query-specific empty state appears, clicking clear, and verifying all records return.

**Acceptance Scenarios**:

1. **Given** interview history contains records, **When** the user searches for a term with no matches, **Then** the UI shows a no-results state that includes the current query.
2. **Given** the no-results state is visible, **When** the user clicks clear search, **Then** the search field is emptied and the full history list is restored.

---

### User Story 3 - Preserve true empty history behavior (Priority: P2)

An authenticated user with no interview records still sees the original empty-history guidance rather than search-specific recovery UI.

**Why this priority**: A user with no records needs onboarding guidance, not search recovery.

**Independent Test**: Can be fully tested by loading an empty history response and verifying the original first-interview prompt remains visible.

**Acceptance Scenarios**:

1. **Given** the user has no interview records, **When** the history tab loads, **Then** the UI shows first-interview guidance and does not show a clear-search action.

### Edge Cases

- Search queries with leading or trailing spaces should behave like the trimmed query.
- Search should be case-insensitive for company and position fields.
- Clearing search from a no-results state should restore the current history tab without changing tabs.
- Empty history should remain distinct from no matching search results.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a searchable interview history input.
- **FR-002**: System MUST filter interview history by company and position text.
- **FR-003**: System MUST treat search matching as case-insensitive.
- **FR-004**: System MUST ignore leading and trailing whitespace in search queries.
- **FR-005**: System MUST show a query-specific no-results state when records exist but none match the current query.
- **FR-006**: Users MUST be able to clear the search query from the no-results state.
- **FR-007**: System MUST restore the full visible history list after clearing search.
- **FR-008**: System MUST preserve the existing true empty-history state when no interview records exist.

### Key Entities

- **Interview Session**: A mock interview history record with company, position, status, score, and timestamps.
- **Search Query**: User-entered text used to filter visible interview sessions.
- **Search Empty State**: UI state shown only when history records exist and the normalized query has no matches.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can filter a populated history list by company or position in under 5 seconds.
- **SC-002**: 100% of no-match searches show the searched query and a clear-search action.
- **SC-003**: 100% of clear-search actions restore the full history list without a page reload.
- **SC-004**: E2E coverage verifies matching search, no-result recovery, and true empty history behavior.

## Assumptions

- The feature is limited to the interview history tab.
- Existing API responses and pagination behavior are unchanged.
- Search remains client-side over the currently loaded history response.
- Existing design-system primitives and list card layout should be reused.
