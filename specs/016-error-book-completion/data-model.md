# Data Model: Error Book Completion

## ErrorQuestion

Represents one user-owned mistake record.

### Fields

- `id`: stable identifier
- `user_id`: owner; all reads and writes are scoped to this user
- `source_session_id`: optional source interview session
- `dimension`: optional controlled ability dimension
- `question_text`: required question content, 1-2000 characters
- `answer_text`: optional user/reference answer shown in detail
- `reference_answer_md`: optional markdown reference used by coaching flows
- `score`: optional 0-10 score
- `status`: `fresh`, `practicing`, `mastered`, or `archived`
- `frequency`: integer 0-3 representing remaining weakness count
- `tags`: optional labels
- `archived_at`: optional archive timestamp
- `last_practiced_at`: timestamp of last recall/practice action
- `created_at`, `updated_at`, `deleted_at`: lifecycle timestamps

### Validation Rules

- `question_text` must be non-empty after user input trimming and must not exceed 2000 characters.
- `dimension`, when present, must be one of the existing six ability dimensions.
- `score`, when present, must be between 0 and 10.
- `frequency` must be between 0 and 3.
- `fresh` implies `frequency=3`.
- `practicing` implies `frequency=1` or `frequency=2`.
- `mastered` implies `frequency=0`.
- Deleted questions are not returned by normal list/detail operations.

### State Transitions

```text
fresh --recall--> practicing/frequency=2
practicing/frequency=2 --recall--> practicing/frequency=1
practicing/frequency=1 --recall--> mastered/frequency=0
mastered --reset--> fresh/frequency=3
fresh|practicing|mastered --delete--> deleted
```

Direct PATCH status transitions remain compatible with existing behavior, but the primary UI uses recall/reset/delete actions.

## RecallAction

Represents a successful review attempt.

### Fields

- `error_question_id`: target question
- `user_id`: actor and owner
- `occurred_at`: practice timestamp
- `previous_frequency`, `next_frequency`
- `previous_status`, `next_status`

### Rules

- Recall is rejected for deleted or missing questions.
- Recall is rejected for questions already at `frequency=0`.
- Recall is atomic: frequency, status, and last practiced time change together.

## ErrorBookViewState

Frontend-only workflow state.

### Fields

- `statusFilter`: all/fresh/practicing/mastered
- `dimensionFilter`: controlled dimension or all
- `search`: local keyword filter
- `selectedId`: current selected question id
- `feedback`: current operation error/success message

### Rules

- Selected detail clears when the selected question disappears due to delete or filtering.
- Leaving and returning to the page reloads server state rather than relying on stale local data.
