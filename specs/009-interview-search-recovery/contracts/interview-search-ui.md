# UI Contract: Interview Search Recovery

## Surface

Interview history page at `/interview`.

## Selectors

- `data-testid="interview-search-input"`: Search input for company or position.
- `data-testid="session-card"`: Interview history card.
- `data-session-id="<session id>"`: Identifier attached to each history card.
- `data-testid="interview-search-empty"`: Query-specific no-results state.
- `data-testid="interview-search-empty-query"`: Visible current query in the no-results state.
- `data-testid="clear-interview-search"`: Clears the current query and restores the list.
- `data-testid="interview-history-empty"`: True empty-history state for users with no records.

## Expected Behavior

### Matching Search

1. User opens `/interview`.
2. User enters a company or position query in `interview-search-input`.
3. Matching cards remain visible.
4. Non-matching cards are hidden.

### No Results Recovery

1. User opens `/interview` with at least one interview record.
2. User enters a query with no matches.
3. `interview-search-empty` appears.
4. `interview-search-empty-query` shows the current query.
5. User clicks `clear-interview-search`.
6. Search input clears.
7. Full history list returns.

### True Empty History

1. User opens `/interview` with no interview records.
2. `interview-history-empty` appears.
3. `interview-search-empty` and `clear-interview-search` are not shown.
