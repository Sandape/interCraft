# UI Contract: Interview Delete Feedback

## Surface

Interview history page at `/interview`.

## Selectors

- `data-testid="session-card"`: Interview history card.
- `data-session-id="<session id>"`: Identifier attached to each history card.
- `data-testid="delete-interview-<session id>"`: Opens the delete confirmation dialog.
- `data-testid="delete-confirm-dialog"`: Confirmation dialog wrapper.
- `data-testid="confirm-delete-btn"`: Confirms the delete action.
- `data-testid="cancel-delete-btn"`: Cancels deletion and closes the dialog.
- `data-testid="delete-error-message"`: Inline retryable error shown after delete failure.

## Expected Behavior

### Successful Delete

1. User opens `/interview`.
2. User clicks `delete-interview-<id>`.
3. Dialog `delete-confirm-dialog` appears.
4. User clicks `confirm-delete-btn`.
5. The delete request succeeds.
6. Dialog closes.
7. The card with `data-session-id="<id>"` is no longer visible.

### Failed Delete

1. User opens `/interview`.
2. User clicks `delete-interview-<id>`.
3. User clicks `confirm-delete-btn`.
4. The delete request fails.
5. Dialog remains visible.
6. `delete-error-message` is visible.
7. The card with `data-session-id="<id>"` remains visible.
8. User can retry or cancel.

### Cancel

1. User opens the confirmation dialog.
2. User clicks cancel.
3. Dialog closes.
4. No delete request is sent.
5. The target card remains visible.
