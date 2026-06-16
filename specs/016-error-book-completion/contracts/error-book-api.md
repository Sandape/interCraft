# Error Book API Contract

Base path: `/api/v1/error-questions`

Auth: Bearer access token for every endpoint.

## GET `/`

Lists current user's non-deleted error questions.

### Query Parameters

| Name | Type | Required | Notes |
|------|------|----------|-------|
| `dimension` | string | no | Existing controlled dimension value |
| `status` | string | no | `fresh`, `practicing`, `mastered`, `archived` |
| `frequency_min` | integer | no | 0-3, default 0 |
| `limit` | integer | no | 1-50, default 20 |

### 200 Response

```json
{
  "data": [
    {
      "id": "00000000-0000-7000-8000-000000000001",
      "source_session_id": null,
      "dimension": "algorithm",
      "question_text": "What is quicksort average complexity?",
      "answer_text": "O(n log n)",
      "reference_answer_md": null,
      "score": null,
      "status": "fresh",
      "frequency": 3,
      "tags": null,
      "archived_at": null,
      "last_practiced_at": null,
      "created_at": "2026-06-16T10:00:00Z",
      "updated_at": "2026-06-16T10:00:00Z"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

## POST `/`

Creates an error question.

### Request

```json
{
  "question_text": "What is quicksort average complexity?",
  "answer_text": "O(n log n)",
  "dimension": "algorithm",
  "score": 4,
  "tags": ["sorting"]
}
```

### Responses

- `201`: created `ErrorQuestion`
- `401`: unauthenticated
- `422`: invalid request body

## GET `/{id}`

Returns one current-user, non-deleted error question.

### Responses

- `200`: `ErrorQuestion`
- `404`: not found, deleted, or belongs to another user

## PATCH `/{id}`

Partially updates editable fields and preserves existing compatibility for direct status changes.

### Request

```json
{
  "question_text": "Updated question text",
  "answer_text": "Updated answer"
}
```

### Responses

- `200`: updated `ErrorQuestion`
- `404`: not found, deleted, or belongs to another user
- `409`: illegal state transition
- `422`: invalid request body or invalid frequency/status combination

## DELETE `/{id}`

Soft-deletes an error question.

### Responses

- `204`: deleted
- `404`: not found, already deleted, or belongs to another user

## POST `/{id}/recall`

Records “answered correctly once”.

### Behavior

- frequency 3 -> 2, status `practicing`
- frequency 2 -> 1, status `practicing`
- frequency 1 -> 0, status `mastered`
- updates `last_practiced_at`

### Responses

- `200`: updated `ErrorQuestion`
- `404`: not found, deleted, or belongs to another user
- `409`: already mastered or otherwise cannot recall

## POST `/{id}/reset`

Resets a mastered error question to fresh.

### Responses

- `200`: updated `ErrorQuestion` with `status=fresh`, `frequency=3`
- `404`: not found, deleted, or belongs to another user
- `409`: current status is not mastered
