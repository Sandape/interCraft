# REST API Contract — Resume v2

**Base path**: `/api/v1/v2`
**Auth**: Bearer JWT (eGGG access token) unless noted as public.
**Content-Type**: `application/json; charset=utf-8`.
**Errors**: JSON body with `{ error: <code>, message: <string>, request_id: <string> }`.

---

## 1. Resume CRUD

### 1.1 List resumes

```
GET /api/v1/v2/resumes
```

| Query | Type | Default | Notes |
|---|---|---|---|
| `search` | string | `null` | Matches name OR slug |
| `tags` | string | `null` | CSV; AND semantics |
| `is_public` | bool | `null` | Filter |
| `sort` | enum | `updated` | `updated` \| `created` \| `name` |

Response 200:

```json
{
  "data": [
    {
      "id": "0192a3b4-...-v7",
      "name": "Senior Engineer",
      "slug": "senior-eng",
      "tags": ["english", "remote"],
      "is_public": false,
      "is_locked": false,
      "version": 7,
      "created_at": "2026-06-25T10:00:00Z",
      "updated_at": "2026-06-25T11:30:00Z",
      "statistics": { "views": 12, "downloads": 3 }
    }
  ]
}
```

### 1.2 Create resume

```
POST /api/v1/v2/resumes
```

Body:

```json
{
  "name": "Senior Engineer",
  "slug": "senior-eng",
  "template": "pikachu",
  "from_sample": true
}
```

When `from_sample = true`, server seeds `data` from `defaultResumeDataV2()`.
Response 201: same shape as 1.3 (below).

Errors: 400 `INVALID_SLUG`, 409 `SLUG_TAKEN`.

### 1.3 Fetch resume

```
GET /api/v1/v2/resumes/{id}
```

Response 200:

```json
{
  "id": "0192a3b4-...-v7",
  "user_id": "018f...-v7",
  "name": "Senior Engineer",
  "slug": "senior-eng",
  "tags": [],
  "is_public": false,
  "is_locked": false,
  "password_set": false,
  "data": { /* ResumeDataV2 — see 02-resume-data-schema.md */ },
  "version": 7,
  "created_at": "...",
  "updated_at": "..."
}
```

### 1.4 Update resume (optimistic concurrency)

```
PUT /api/v1/v2/resumes/{id}
Headers:
  If-Match: <integer version>
```

Body:

```json
{
  "name": "Senior Engineer (v2)",
  "tags": ["remote"],
  "data": { /* full ResumeDataV2 — client sends the whole tree */ }
}
```

Response 200:

```json
{
  "id": "...",
  "version": 8,                 // bumped
  "updated_at": "..."
}
```

Response 409 (conflict):

```json
{
  "error": "VERSION_CONFLICT",
  "message": "Stored version is 9, you sent 7.",
  "request_id": "...",
  "latest_version": 9,
  "latest_data": { /* full ResumeDataV2 */ },
  "latest_updated_at": "..."
}
```

Response 423 (locked):

```json
{ "error": "RESUME_LOCKED", "message": "..." }
```

Errors: 400 `MISSING_IF_MATCH`, 400 `LEGACY_FORMAT`, 409, 423.

### 1.5 Delete resume

```
DELETE /api/v1/v2/resumes/{id}
```

Soft delete. Response 204. Cascades to statistics + analysis tables.

---

## 2. Side actions

### 2.1 Duplicate

```
POST /api/v1/v2/resumes/{id}/duplicate
```

Response 201:

```json
{
  "id": "0192a3b4-...-v7",          // new UUID
  "name": "Senior Engineer (Copy)",
  "slug": "senior-eng-copy-1",
  "version": 0,
  "data": { /* deep copy of source */ },
  "is_public": false,
  "is_locked": false,
  "password_set": false
}
```

Errors: 404 `NOT_FOUND`.

### 2.2 Lock / unlock

```
PUT /api/v1/v2/resumes/{id}/lock
Body: { "locked": true }
```

Response 200: `{ "is_locked": true }`. Reversible. Independent of `version`.

### 2.3 Sharing

```
PUT /api/v1/v2/resumes/{id}/sharing
Body: {
  "is_public": true,
  "password": "secret123" | null    // null = remove password
}
```

Response 200: `{ "is_public": true, "password_set": true, "public_url": "/r/alice/senior-eng" }`.

Validation: `password` 6..64 chars when set; bcrypt cost 12 server-side.

### 2.4 Statistics

```
GET /api/v1/v2/resumes/{id}/statistics
```

Response 200:

```json
{
  "views": 12,
  "downloads": 3,
  "last_viewed_at": "2026-06-25T10:00:00Z",
  "last_downloaded_at": "2026-06-25T10:05:00Z"
}
```

Empty (`{views: 0, downloads: 0, …}`) if `is_public = false`.

---

## 3. AI analysis

```
POST /api/v1/v2/resumes/{id}/analyze
```

Async-friendly: returns 202 with a `job_id` if running; 200 with `analysis`
embedded if cached. Per FR-091b, retries 3× on 429/5xx from DeepSeek before
returning `status='failed'`.

Response 200:

```json
{
  "status": "success",
  "analysis": {
    "overallScore": 78,
    "dimensions": [
      { "name": "contentCompleteness", "score": 8 },
      { "name": "quantification",       "score": 6 },
      ...
    ],
    "strengths": [{ "text": "..." }, ...],
    "suggestions": [
      { "impact": "high", "text": "...", "why": "...", "exampleRewrite": "..." }
    ]
  },
  "updated_at": "2026-06-25T..."
}
```

Response 200 (failure):

```json
{
  "status": "failed",
  "failure_reason": "LLM provider returned 503 after 3 retries.",
  "updated_at": "..."
}
```

---

## 4. Public access (no auth)

### 4.1 Public view

```
GET /api/v1/v2/public/{username}/{slug}
```

Response 200 (same shape as 1.3 but `is_locked` always false here, `password_set`
shown).

If password-protected AND no valid cookie: 401 `PASSWORD_REQUIRED`.

### 4.2 Verify password

```
POST /api/v1/v2/public/{username}/{slug}/verify-password
Body: { "password": "secret123" }
```

Response 200: sets cookie `v2_public_pw_<hash>` (HttpOnly, SameSite=Lax,
Path=/, Max-Age=600). Body: `{ "ok": true }`.

Response 401 on bad password.

### 4.3 Public PDF download

```
GET /api/v1/v2/public/{username}/{slug}/pdf
```

Same flow as the public view (cookie required if password-protected), then
renders via the export pipeline. Increments `downloads` if caller ≠ owner.

---

## 5. Server-Sent Events

```
GET /api/v1/v2/resumes/events?resume_id={id}
Accept: text/event-stream
```

See `03-sse-events.md` for payload format. Heartbeat every 25s.

---

## 6. Export gateway (v2 routes only)

```
POST /api/v1/v2/export/render
Body: { "html": "...", "format": "pdf" | "json", "resume_id": "..." }
```

The export pipeline accepts complete HTML (same as v1 /api/v1/export/render)
and increments `downloads` when `resume_id` is provided.

The `format: "json"` response is `application/json` and contains the full
`ResumeDataV2`. The `format: "pdf"` response is `application/pdf`.

---

## 7. Error catalogue

| HTTP | Code | Trigger |
|---|---|---|
| 400 | `MISSING_IF_MATCH` | PUT without If-Match |
| 400 | `INVALID_IF_MATCH` | If-Match not an integer |
| 400 | `LEGACY_FORMAT` | Data format is v1 block-based |
| 400 | `INVALID_SLUG` | Slug fails regex |
| 400 | `INVALID_TEMPLATE` | template not in 10 enum |
| 400 | `FIELD_TOO_LONG` | Field exceeds char limit |
| 400 | `TOO_MANY_ITEMS` | Section items > 100 |
| 401 | `UNAUTHENTICATED` | No Bearer token |
| 403 | `NOT_OWNER` | Accessing someone else's resume |
| 404 | `NOT_FOUND` | Resume id not found |
| 409 | `VERSION_CONFLICT` | Optimistic concurrency lost |
| 409 | `SLUG_TAKEN` | Slug already used by another resume |
| 413 | `CONTENT_TOO_LARGE` | HTML > 1 MB |
| 423 | `RESUME_LOCKED` | Resume is locked |
| 429 | `RATE_LIMITED` | (Reserved) |
| 500 | `INTERNAL_ERROR` | Unhandled |
| 503 | `LLM_UNAVAILABLE` | AI analysis failed after 3 retries |