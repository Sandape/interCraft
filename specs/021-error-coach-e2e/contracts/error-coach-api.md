# Contract: Error Coach REST API

**Branch**: `021-error-coach-e2e` | **Date**: 2026-06-22

REST contract snapshot for `/agents/error-coach/*`. This contract is
**unchanged** from 004; included here as a reference for E2E assertions.
Source: `backend/app/api/v1/agents_error_coach.py`.

---

## Base URL

`/api/v1/agents/error-coach`

## Auth

All endpoints require `Authorization: Bearer <JWT>` (fastapi-users).

---

## Endpoints

### POST /start

Start a new Error Coach session for a specific error question.

**Request**:
```json
{
  "error_question_id": "<uuid string>"
}
```

**Response** `201`:
```json
{
  "thread_id": "<uuid string>",
  "status": "running",
  "current_node": "fetch_question"
}
```

**Errors**:
- `500` on internal error (graph start failure)

---

### POST /{thread_id}/messages

Submit a user answer in an existing session.

**Request**:
```json
{
  "content": "<user answer text>"
}
```

**Response** `200`:
```json
{
  "thread_id": "<uuid string>",
  "status": "running" | "completed" | "not_found",
  "current_node": "hint_ladder" | "evaluate" | "loop_or_finish" | null,
  "score": <int 0-10> | null,
  "correct_count": <int> | null,
  "hint_level": "small" | "medium" | "detailed" | null,
  "hint_content": "<string>" | null
}
```

**Notes**:
- `status=not_found` when `thread_id` has no checkpoint (HTTP 200, business status)
- `score` / `correct_count` / `hint_level` / `hint_content` may be null on first response (before evaluate runs)

**Errors**:
- `500` on internal error

---

### POST /{thread_id}/abort

User-initiated abort.

**Response** `200`:
```json
{
  "thread_id": "<uuid string>",
  "status": "aborted",
  "correct_count_achieved": <int>
}
```

**Behavior**:
- Sets `session_aborted=True` in thread state
- Triggers `loop_or_finish` → END
- Calls `decrement_frequency` once (session ended)
- Returns `correct_count` from final state as `correct_count_achieved`

---

### GET /{thread_id}/state

Read current thread state.

**Response** `200`:
```json
{
  "thread_id": "<uuid string>",
  "status": "running" | "completed",
  "correct_count": <int>,
  "attempt_count": <int>,
  "current_hint_level": "small" | "medium" | "detailed"
}
```

**Errors**:
- `404` on thread not found

---

## E2E Assertion Cheat Sheet

| Endpoint | Field | HAPPY-01 expected | EDGE-01 expected | ABORT-01 expected |
|---|---|---|---|---|
| POST /start | `status` | `running` | `running` | `running` |
| POST /{tid}/messages #1 | `correct_count` | 1 | 0 | 1 |
| POST /{tid}/messages #1 | `hint_level` | `small` | `small` | `small` |
| POST /{tid}/messages #2 | `correct_count` | 2 | 1 | — |
| POST /{tid}/messages #3 | `correct_count` | 3 | 2 | — |
| POST /{tid}/messages #3 | `status` | `completed` | `running` | — |
| POST /{tid}/messages #4 | `correct_count` | — | 3 | — |
| POST /{tid}/messages #4 | `status` | — | `completed` | — |
| POST /{tid}/abort | `status` | — | — | `aborted` |
| POST /{tid}/abort | `correct_count_achieved` | — | — | 1 |
| GET /{tid}/state (final) | `status` | `completed` | `completed` | `completed` |
| DB `error_questions.frequency` | — | 3 → 2 | 3 → 2 | 3 → 2 |
