# Server-Sent Events — Resume v2

**Endpoint**: `GET /api/v1/v2/resumes/events?resume_id={id}`
**Content-Type**: `text/event-stream`
**Cache-Control**: `no-cache, no-transform`
**Connection**: `keep-alive`

---

## 1. Transport

- The endpoint accepts an optional `resume_id` query parameter. When set, the
  server filters emitted events to that one resume. When omitted, the server
  streams events for all resumes the caller owns.
- Authentication via `Authorization: Bearer …` header (same as REST).
- Heartbeat: `: heartbeat\n\n` every 25 seconds (comment line, ignored by EventSource).
- Reconnect: client uses `EventSource` native retry; server emits an `id:` line
  on every event so the `Last-Event-ID` header can be used to resume.

---

## 2. Event types

### 2.1 `resume.updated`

Emitted on every successful PUT to `resumes_v2`. The client should compare
`version` to its local copy:

- `version > local.version` AND no local unsaved changes → silently replace.
- `version > local.version` AND local unsaved changes → toast + show "Reload?"
  affordance (per FR-086 metadata merge; v2 simplifies to full reload).

Payload:

```json
{
  "type": "resume.updated",
  "resume_id": "0192a3b4-...-v7",
  "version": 8,
  "user_id": "018f...-v7",
  "updated_at": "2026-06-25T10:00:00Z",
  "action": "updated"
}
```

### 2.2 `resume.locked` / `resume.unlocked`

Emitted when `is_locked` flips. Clients with the editor open should refresh
the read-only state and disable input.

Payload:

```json
{
  "type": "resume.locked",
  "resume_id": "0192a3b4-...-v7",
  "is_locked": true,
  "user_id": "018f...-v7",
  "version": 8,
  "updated_at": "2026-06-25T10:01:00Z"
}
```

### 2.3 `resume.public-changed`

Emitted when `is_public` flips. Affects the public URL liveness.

Payload:

```json
{
  "type": "resume.public-changed",
  "resume_id": "0192a3b4-...-v7",
  "is_public": true,
  "password_set": true,
  "public_url": "/r/alice/senior-eng"
}
```

### 2.4 `resume.deleted`

Emitted on soft delete. Clients should navigate away.

Payload:

```json
{
  "type": "resume.deleted",
  "resume_id": "0192a3b4-...-v7"
}
```

### 2.5 `analysis.completed`

Emitted when async analysis finishes (success or failure).

Payload:

```json
{
  "type": "analysis.completed",
  "resume_id": "0192a3b4-...-v7",
  "status": "success",
  "overall_score": 78,
  "updated_at": "2026-06-25T10:02:00Z"
}
```

---

## 3. Wire format (raw SSE)

```
id: 1
event: resume.updated
data: {"type":"resume.updated","resume_id":"0192a3b4-...","version":8,"user_id":"018f...","updated_at":"2026-06-25T10:00:00Z","action":"updated"}

: heartbeat

id: 2
event: resume.locked
data: {"type":"resume.locked","resume_id":"0192a3b4-...","is_locked":true,"user_id":"018f...","version":8,"updated_at":"2026-06-25T10:01:00Z"}

```

`data:` is a single JSON line; multiline content is JSON-encoded with `\n`.

---

## 4. Backpressure & scaling

- One LISTEN/NOTIFY channel per Postgres publication: `resume_update_v2`.
- Each SSE connection subscribes to the channel via a dedicated Postgres
  `LISTEN` session (per connection).
- Maximum SSE connections per user: 5 (configurable in `core.config`).
- Idle connections closed after 5 minutes (browser will auto-reconnect).

---

## 5. Client contract

```ts
type SseEvent =
  | { type: 'resume.updated'; resume_id: string; version: number; user_id: string; updated_at: string; action: 'updated' }
  | { type: 'resume.locked'; resume_id: string; is_locked: true; user_id: string; version: number; updated_at: string }
  | { type: 'resume.unlocked'; resume_id: string; is_locked: false; user_id: string; version: number; updated_at: string }
  | { type: 'resume.public-changed'; resume_id: string; is_public: boolean; password_set: boolean; public_url: string | null }
  | { type: 'resume.deleted'; resume_id: string }
  | { type: 'analysis.completed'; resume_id: string; status: 'success' | 'failed'; overall_score?: number; updated_at: string }

function subscribeResumeEvents(
  resumeId: string,
  onEvent: (event: SseEvent) => void
): () => void                                  // unsubscribe
```

Implementation: native `EventSource`. The hook in
`src/modules/resume/v2/hooks/useResumeSse.ts` returns the unsubscribe function
on unmount.

---

## 6. Failure handling

| Symptom | Client action |
|---|---|
| Connection drops | EventSource auto-reconnects with `Last-Event-ID` |
| 401 (token expired) | Show re-auth banner; stop retrying |
| 403 (not owner) | Close; show toast "session changed" |
| Repeated `: heartbeat` only | Continue; treat as no-op |
| `resume.deleted` | Navigate to `/resume/list` |