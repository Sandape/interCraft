# Data Model: Interview Resume Guardrails

No new persistent data model is introduced.

## Existing Entities Referenced

### Interview Session

Represents an existing interview record.

Relevant fields:
- `id`: Stable session identifier
- `status`: `pending`, `in_progress`, or `completed`
- `position`: Target role label
- `company`: Target company label
- `duration_sec`: Stored elapsed interview duration
- `overall_score`: Completed interview score, when available

### Resume Snapshot

Represents the existing resume endpoint payload.

Relevant fields:
- `values.messages`: Saved conversation messages
- `values.questions`: Generated interview questions
- `values.scores`: Score cards produced for answered questions

Validation rules:
- Missing arrays are treated as empty arrays.
- Duplicate questions are ignored by question text.
- Duplicate scores are ignored by `question_no`.
- Malformed payloads enter the resume error state rather than the setup flow.

### Restored Answer

Client-side view model reconstructed from user messages.

Fields:
- `content`: User answer text
- `seqNo`: Zero-based answer sequence used for the next visible timeline ordering

Lifecycle:
1. Created from resume snapshot messages during restore.
2. Rendered before new user input.
3. Appended to when the user submits the next answer.

### Resume Error State

Client-side state for failed restore.

Fields:
- `sessionId`: Route session id
- `message`: User-safe error message
- `retryAvailable`: Always true when route session id is present
- `returnAvailable`: Always true

Lifecycle:
1. Entered when session lookup or resume payload loading fails.
2. Retry reloads the same live route.
3. Return navigates to interview list.
