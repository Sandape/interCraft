# Contract: Interview Resume UI

This is a UI contract for the existing interview resume flow. It does not define new backend endpoints.

## Route: Continue Interview

`GET /interview/:sessionId/live`

### Expected Restored State

When the session exists and is not completed:

- The page displays `data-testid="resumed-notice"`.
- The page displays `data-testid="resume-summary"` with restored answer/question/score counts.
- The page displays previous user answers using `data-testid^="restored-answer-"`.
- The answer input is available as `data-testid="answer-input"`.
- The submit action is available as `data-testid="submit-answer"`.

### Completed Session State

When the session is already completed:

- The page enters completed state.
- The detailed report link remains available.
- Live answer input is not shown.

### Resume Failure State

When session lookup or resume loading fails:

- The page displays `data-testid="resume-error-state"`.
- The error message is available as `data-testid="resume-error-message"`.
- Retry action is available as `data-testid="resume-retry"`.
- Return action is available as `data-testid="resume-return-list"`.
- New interview setup controls are not shown.

## Route: Interview List

`GET /interview`

For each visible interview session card:

- The card exposes `data-testid="session-card"` and `data-session-id="<sessionId>"`.
- In-progress and pending sessions expose `data-testid="continue-interview-<sessionId>"`.
- Delete actions keep their existing `data-testid="delete-interview-<sessionId>"`.

## Non-Goals

- No new backend API contract.
- No new persistent model.
- No changes to scoring or report generation.
