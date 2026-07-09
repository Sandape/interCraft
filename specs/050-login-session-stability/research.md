# Research: 登录会话稳定性

## Overview

All NEEDS CLARIFICATION markers from the spec were resolved during the `/speckit-clarify` session (2026-07-07). This document consolidates the research findings that inform the implementation plan.

## 1. Multi-tab Session Collision Resolution

**Decision**: Remove `UNIQUE(user_id, device_id)` constraint; allow multiple rows per device_id

**Rationale**:
- Current constraint + `register_session` device-id dedup logic means second tab's login soft-deletes first tab's session
- With constraint removed, each tab's login creates a new session row; tabs coexist independently
- Same `device_fingerprint()` across tabs (same UA + screen + TZ + language → same device_id) no longer causes collision
- Queries always locate sessions by `session_id` (from JWT), not device_id — removing the constraint has no query impact

**Alternatives considered**:
- Adding session-level entropy to device_id: changes semantics, requires fingerprint generation changes
- Partial unique index on `(user_id, device_id) WHERE deleted_at IS NULL`: UNIQUE NULL behavior in PG is per-row (NULLs are not considered equal), so soft-deleted rows with NULL `deleted_at` would still conflict

## 2. Session Rotation Strategy

**Decision**: In-place update (update existing row) instead of soft-delete + new row

**Rationale**:
- Current soft-delete + create-new creates an obvious race window: concurrent `rotate_refresh` calls may both try to soft-delete the old session, then fail on UNIQUE constraint or end up with a dangling reference
- In-place update is atomic (`UPDATE auth_sessions SET refresh_token_hash=..., expires_at=... WHERE id=...`); no race window
- Eliminates the root cause of the "session not found" error during concurrent refresh
- Also eliminates the moderate but real risk of session table bloat from 7-day refresh cycle (a single active user generates ~672 soft-deleted rows over 7 days = 15 min intervals)

**Tradeoff**: Loses the history of old refresh_token_hashes for forensic audit. Mitigation: FR-011 (audit logging) adds explicit log events for rotation.

## 3. Refresh Reuse Detection Behavior

**Decision**: On hash mismatch, REJECT the refresh request only; do NOT revoke all user sessions

**Rationale**:
- Current behavior (`rotate_refresh` line 108-109) revokes ALL active sessions on a single hash mismatch
- This was intended as security against stolen refresh tokens, but is overly aggressive for concurrent refresh scenarios
- A single rejected refresh is sufficient security: the attacker can't use the old refresh token anyway; the legitimate user's other devices keep working
- Aligns with industry best practices (OAuth 2.0 refresh rotation spec recommends rejecting the reused token, not revoking everything)

## 4. Session Eviction Notification Pattern

**Decision**: Toast notification — no token clear, no page redirect

**Rationale**:
- Modal is too disruptive for a background event (session eviction shouldn't prevent ongoing work)
- Auto-redirect to `/login` would destroy the user's current page state
- Toast + keep token lets user: ① finish current task, ② save work, ③ then decide to proceed to login
- Token kept means the Toast can persist across page navigations until user acknowledges

## 5. Frontend Resilience Against Transient Failures

**Decision**: Network errors and 5xx don't clear tokens; only definitive auth errors (401 with specific code) do

**Rationale**:
- Current `tryRefresh()` clears tokens on ANY non-200 response, including 502/503 from deployment restarts
- Network fetch exceptions (TypeError: Failed to fetch) go through the `catch` branch and also clear tokens
- New behavior: only `401` + `auth.token_invalid` / `auth.session_evicted` / `auth.refresh_expired` clear tokens
- 5xx + fetch exceptions: keep tokens, `tryRefresh` returns `false`, but next request triggers another refresh attempt

## 6. Observability Signals

**Decision**: Three-level observability (metrics + logs + audit)

**Rationale**:
- Metrics: Prometheus-style counters for refresh success/failure by reason — enables dashboards + alerts
- Logs: Structured events for session create/evict — supports per-user debugging
- Audit: Tamper-evident trail for reuse detection events — security monitoring

**Metrics schema (counters)**:

| Metric | Labels | Description |
|--------|--------|-------------|
| `auth_refresh_attempts_total` | result={success,failure}, reason={expired,evicted,reuse,invalid} | Count of refresh requests |
| `auth_sessions_created_total` | — | Count of new session rows |
| `auth_sessions_evicted_total` | cause={max_devices,admin,reuse} | Count of evicted sessions |

## 7. Rate Limiting

**Decision**: No additional rate limiting on refresh endpoint; share existing auth pool (10/minute)

**Rationale**: Normal refresh cadence = ~4 requests/hour per device. Worst-case retry storm = ~2-3 additional requests. Both well under the 10/minute limit.

## Key Technology References

| Technology | Version | Usage |
|------------|---------|-------|
| PostgreSQL | 16 | `auth_sessions` table, RLS, UNIQUE constraint changes |
| SQLAlchemy | 2.0+ | Alembic migration for constraint removal + field changes |
| FastAPI | 0.115+ | API routes for refresh/error code changes |
| React Query | 5.x | `useCurrentUser` retry + staleTime config |
| Zustand | 4.x | Auth store eviction state |
| Prometheus counter | — | Refresh/session metrics |
