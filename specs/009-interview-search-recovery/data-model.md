# Data Model: Interview Search Recovery

## Interview Session

Existing mock interview history record shown in the interview list.

Fields used by this feature:

- `id`: Stable identifier used by list rendering and E2E selectors.
- `company`: Text matched by search.
- `position`: Text matched by search.
- `status`: Existing record status display.
- `overall_score` / `score`: Existing score display values.
- `created_at`: Existing list metadata.

## Search Query

Transient UI state entered by the user.

Fields:

- `rawValue`: Exact text currently in the search input.
- `normalizedValue`: Trimmed lowercase value used for matching.

Validation rules:

- Empty normalized value means no filtering.
- Non-empty normalized value filters by company or position.

## Search Empty State

Transient UI state shown when search has no matches.

Derived conditions:

- Total interview sessions count is greater than zero.
- Normalized search query is non-empty.
- Filtered interview sessions count is zero.

Actions:

- Clear search query.
- Restore full visible history list.
