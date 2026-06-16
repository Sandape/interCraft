# Contract: Global Search Endpoint

**Feature**: 011-global-search
**Date**: 2026-06-16
**Spec**: [spec.md](../spec.md)
**Data model**: [../data-model.md](../data-model.md)

## Endpoint

```
GET /api/v1/search
```

Authenticated. Per-user rate-limited. Returns aggregated results from resume branches, interview sessions, ability dimensions, FAQ, and learning resources.

## Request

### Headers

| Header                  | Required | Description                                      |
|-------------------------|----------|--------------------------------------------------|
| `Authorization`         | yes      | `Bearer <access_token>`                          |
| `X-Request-ID`          | no       | Existing convention; helpful for log correlation |
| `X-Device-Fingerprint`  | no       | Existing convention                              |

### Query parameters

| Name   | Type   | Required | Constraints                | Default | Description                          |
|--------|--------|----------|----------------------------|---------|--------------------------------------|
| `q`    | string | yes      | 1..200 chars, non-empty after trim | —  | Search query (case-insensitive ILIKE) |
| `limit`| int    | no       | 1..5                        | 5       | Per-type cap                          |

### Example

```
GET /api/v1/search?q=字节&limit=5
```

## Response

### 200 OK

```json
{
  "groups": [
    {
      "type": "resume",
      "label": "简历分支",
      "items": [
        {
          "id": "0190f5b7-1234-7abc-9def-0123456789ab",
          "type": "resume",
          "title": "字节跳动 · 高级前端",
          "subtitle": "高级前端工程师",
          "destination": "/resume/0190f5b7-1234-7abc-9def-0123456789ab",
          "score": 1.0,
          "meta": { "branch_status": "optimizing", "is_main": false }
        }
      ],
      "total": 1
    },
    {
      "type": "interview",
      "label": "面试记录",
      "items": [
        {
          "id": "0190f5b7-aaaa-7bbb-9ccc-1234567890ab",
          "type": "interview",
          "title": "字节跳动 · 高级前端",
          "subtitle": "字节跳动",
          "destination": "/interview/0190f5b7-aaaa-7bbb-9ccc-1234567890ab/report",
          "score": 1.0,
          "meta": { "session_status": "completed" }
        }
      ],
      "total": 1
    },
    {
      "type": "ability",
      "label": "能力维度",
      "items": [
        {
          "id": "ability::architecture",
          "type": "ability",
          "title": "架构能力",
          "subtitle": "Architecture",
          "destination": "/ability-profile/architecture",
          "score": 0.6,
          "meta": { "dimension_key": "architecture" }
        }
      ],
      "total": 1
    },
    {
      "type": "faq",
      "label": "常见问题",
      "items": [
        {
          "id": "0190f5b7-7777-7777-7777-777777777777",
          "type": "faq",
          "title": "如何删除面试记录？",
          "subtitle": "面试相关",
          "destination": "/help#faq/0190f5b7-7777-7777-7777-777777777777",
          "score": 0.4,
          "meta": { "category": "interview" }
        }
      ],
      "total": 1
    }
  ],
  "query": "字节",
  "took_ms": 42
}
```

### 422 Validation Error

```json
{
  "detail": [
    { "loc": ["query", "q"], "msg": "ensure this value has at least 1 characters", "type": "value_error.any_str.min_length" }
  ]
}
```

### 401 Unauthorized

```json
{ "detail": "Not authenticated" }
```

### 429 Too Many Requests

```json
{ "detail": "rate_limit.exceeded" }
```

Headers: `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

### 500 Internal Server Error

```json
{ "detail": "internal_error" }
```

## Group ordering and total cap

- Groups are emitted in a fixed order: `resume`, `interview`, `ability`, `faq`, `resource`.
- A group is omitted when `total == 0`.
- The sum of `len(items)` across all groups is hard-capped at 25. If a single type alone could return more, it is truncated; the other types still get their share.
- Within a group, items are ordered by `score DESC`, then `id ASC` (stable).

## Score semantics

- v1 uses a simple scoring: exact substring match = 1.0; prefix match = 0.8; case-insensitive substring = 0.6. We do not promise a specific algorithm; scores are intended for ordering, not for display.
- A future iteration may add recency (interview last 7 days) or fuzzy matching; the contract shape does not need to change.

## RLS / data isolation

- The endpoint uses `db_session_user_dep`, which binds the current `user_id` to the DB session via `SET LOCAL app.user_id`. The RLS policies on `resume_branches`, `interview_sessions`, and `ability_dimensions` therefore apply automatically.
- `help_faq` and `resources` are platform-wide and have no RLS; they are filtered by `is_published = true` (existing convention).
- The test suite includes an RLS isolation test (see [quickstart.md](../quickstart.md)).

## Future evolution

- Add `offset` / pagination when a user wants to browse the long tail of a type.
- Add `filters[type]=resume,interview` to scope to specific types.
- Add `recency_weight` for interview ordering.

None of these require a breaking contract change.
