# Contract: Auth Session Error Codes & Events

## API Contract Changes

### POST /api/v1/auth/refresh — Error Codes

Current errors (no changes):

| Status | Code | Description |
|--------|------|-------------|
| 401 | `auth.token_missing` | No refresh token provided |
| 401 | `auth.token_expired` | Refresh token has expired |
| 401 | `auth.token_invalid` | Refresh token is malformed or invalid signature |

New error codes in this feature:

| Status | Code | Description | Trigger |
|--------|------|-------------|---------|
| 401 | `auth.session_evicted` | Session was evicted due to max devices exceeded | FR-004: refresh with a session that was soft-deleted via eviction |
| 401 | `auth.refresh_reuse` | Refresh token hash mismatch — possible token reuse | FR-008: hash mismatch (was revoking all, now only rejects one) |
| 401 | `auth.session_not_found` | Session row no longer exists | FR-009: defensive fallback (should be rare after in-place rotation) |

### Auth Error Code Contract

```typescript
// Frontend error classification (src/api/errors.ts)
// ADD:
export type AuthErrorCode =
  | 'auth.session_evicted'     // NEW: show Toast → user decides next step
  | 'auth.refresh_reuse'       // NEW: single-request reject, no Toast needed (transient)
  | 'auth.session_not_found'   // NEW: defensive, treat as evicted
  // Existing:
  | 'auth.token_missing'
  | 'auth.token_expired'
  | 'auth.token_invalid'
  | 'auth.invalid_credentials'
  | 'auth.email_taken'
  | 'auth.password_too_weak'
```

### Frontend tryRefresh() Behavior

| Backend Response | Current Behavior | New Behavior (FR-005) |
|------------------|-----------------|----------------------|
| 200 OK | Set tokens, return true | ✅ Same |
| 401 `auth.session_evicted` | Clear tokens → redirect /login | Show Toast, return false, keep tokens |
| 401 `auth.refresh_expired` | Clear tokens → redirect /login | ✅ Same (legitimate expiry) |
| 401 `auth.refresh_reuse` | Clear tokens, throw TokenInvalid | Return false, keep tokens (transient) |
| 5xx (502/503) | Clear tokens → redirect /login | Keep tokens, return false, next request retries |
| Fetch throws (network error) | Catch → clearTokens() | Keep tokens, return false, next request retries |

### Session Eviction Event Log Schema (FR-011)

```json
{
  "event": "session_evicted",
  "timestamp": "2026-07-07T12:00:00Z",
  "actor_user_id": "sha256$abc123...",
  "target_session_id": "01900000-0000-7000-8000-000000000001",
  "cause": "max_devices_exceeded",
  "evicted_by_session_id": "01900000-0000-7000-8000-000000000002",
  "device_id": "sha256$def456..."
}
```

### Refresh Metrics Contract (FR-010)

```
auth_refresh_attempts_total{result="success", reason=""} COUNTER
auth_refresh_attempts_total{result="failure", reason="session_evicted"} COUNTER
auth_refresh_attempts_total{result="failure", reason="token_expired"} COUNTER
auth_refresh_attempts_total{result="failure", reason="reuse_detected"} COUNTER
auth_refresh_attempts_total{result="failure", reason="session_not_found"} COUNTER
auth_refresh_attempts_total{result="failure", reason="invalid_token"} COUNTER
```

### GET /api/v1/users/me — Retry Behavior (FR-006)

| Attempt | Backoff | Behavior |
|---------|---------|----------|
| 1st | immediate | Normal query — if 401, trigger tryRefresh then retry |
| 2nd | 1s | If still 401 after refresh, retry once more |
| 3rd | — | Fail definitively → setStatus('unauthenticated') → redirect /login |

### AuthGuard Loading State (FR-006)

While `useCurrentUser` is retrying (status remains `'unknown'`), the AuthGuard renders:
```
<div data-testid="auth-loading">正在校验登录状态…</div>
```
This gives the silent refresh + retry time to complete before redirecting.
