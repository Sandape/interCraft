# Data Model: Interview Delete Feedback

## Interview Session

Existing mock interview history item shown in the interview list.

Fields used by this feature:

- `id`: Stable identifier used to target deletion.
- `company`: Display label component.
- `position`: Display label component.
- `status`: Determines whether the card shows continue or report actions.
- `overall_score` / `score`: Existing score display values.
- `created_at`: Existing list metadata.

Lifecycle impact:

- Before delete: visible in interview history.
- Successful delete: removed from visible history after list refresh.
- Failed delete: remains visible and unchanged.

## Delete Confirmation

Temporary UI state for a pending destructive action.

Fields:

- `id`: Target interview session identifier.
- `label`: Human-readable target label.
- `errorMessage`: Last delete failure message, if any.
- `isPending`: Mutation state inherited from the delete action.

Validation rules:

- `id` must be present before confirm is enabled.
- `errorMessage` clears when a new target is selected or retry starts.
- Cancel closes the confirmation and clears `errorMessage`.

State transitions:

```text
closed -> open -> deleting -> closed
                 |          ^
                 v          |
              failed -> retrying
```
