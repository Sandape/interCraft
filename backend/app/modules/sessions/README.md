# M05 — Session / Device / RLS

**Purpose**: 5-device cap, refresh-token rotation with reuse detection, session listing / revocation.

**Public API**:
- `GET    /api/v1/users/me/sessions` — list current user's active sessions.
- `DELETE /api/v1/users/me/sessions/{id}` — revoke a session (kick a device).
- `POST   /api/v1/users/me/sessions/{id}/trust` — **501 placeholder** (v1.1).

**CLI**:
```bash
uv run python -m app.modules.sessions.cli list   --user-id <UUID> --json
uv run python -m app.modules.sessions.cli revoke --session-id <UUID> --user-id <UUID>
```

**Notes**:
- `register_session` enforces the 5-device cap (oldest `last_seen_at` is evicted first).
- Reuse of a refresh token (mismatched hash) → **all** user sessions revoked.
- RLS on `auth_sessions` is enabled in the initial migration. The CLI must run with a
  user-context session in production; for dev convenience, the CLI calls
  `register_session`/`revoke_session` directly with explicit user_id.
