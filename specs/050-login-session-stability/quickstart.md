# Quickstart: 登录会话稳定性 — Validation Guide

## Prerequisites

- Backend running: `make dev-backend` (uvicorn with hot reload)
- Frontend running: `make dev-frontend` (Vite dev server)
- PostgreSQL with auth tables migrated
- E2E test account: `demo@intercraft.io` / `test1234`

## Validation Scenarios

### Scenario 1: Single-tab session persistence (SC-001)

```bash
# 1. Login via API — get tokens
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@intercraft.io","password":"test1234","device_fingerprint":"test-scenario-1"}' \
  | jq '{access: .tokens.access_token[0:20], refresh: .tokens.refresh_token[0:20]}'

# 2. Wait 16 min (access_token TTL = 15 min, plus margin)

# 3. Call a protected endpoint — should auto-refresh
curl -s http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $ACCESS" \
  | jq '.email'

# Expected: 200 OK with user email (not 401)
```

**Expected**: After 16 min idle, request still succeeds (silent refresh works).

### Scenario 2: Multi-tab coexistence (SC-002)

```bash
# Tab A login
TAB_A=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@intercraft.io","password":"test1234","device_fingerprint":"tab-a-fp"}')
A_ACCESS=$(echo $TAB_A | jq -r '.tokens.access_token')

# Tab B login (same device_fingerprint — simulates same browser)
TAB_B=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@intercraft.io","password":"test1234","device_fingerprint":"tab-b-fp"}')
B_ACCESS=$(echo $TAB_B | jq -r '.tokens.access_token')

# Both tabs should work
curl -s http://localhost:8000/api/v1/users/me -H "Authorization: Bearer $A_ACCESS" | jq '.email'
curl -s http://localhost:8000/api/v1/users/me -H "Authorization: Bearer $B_ACCESS" | jq '.email'

# Expected: Both return 200. Refresh A's token:
B_REFRESH=$(echo $TAB_B | jq -r '.tokens.refresh_token')
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$B_REFRESH\"}"
# Expected: Both tabs still work after B refreshes
```

### Scenario 3: Transient 502 resilience (SC-003)

```bash
# 1. Login
TOKENS=$(curl -s -X POST http://localhost:8000/api/v1/auth/login ...)
ACCESS=$(echo $TOKENS | jq -r '.tokens.access_token')

# 2. Simulate network error (can't do this via curl alone)
# Use E2E test: tests/e2e/050-login-stability/transient-failure.spec.ts
# The test intercepts the next request with a 502 then checks retry

# Manual check: stop + restart backend
# kill $BE_PID; sleep 2; make dev-backend &
# Then immediately:
curl -s http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $ACCESS" \
  --connect-timeout 5
# Expected: Succeeds after backend restarts (transient 502 → retry → 200)
```

### Scenario 4: Eviction notification (SC-004)

```bash
# 1. Create 10 sessions for same user (simulate max_devices=10)
for i in $(seq 1 10); do
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"demo@intercraft.io\",\"password\":\"test1234\",\"device_fingerprint\":\"evict-test-$i\"}" > /dev/null
done

# 2. Try to refresh the oldest session's token
OLD_REFRESH="..."  # captured from first login
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$OLD_REFRESH\"}" | jq .

# Expected: 401 + code "auth.session_evicted"
```

### Scenario 5: Concurrent refresh safety (SC-005)

```bash
# 1. Login, wait for access_token to expire (15 min), then:
# Fire 3 simultaneous refresh requests
# This is done via E2E: tests/e2e/050-login-stability/concurrent-refresh.spec.ts

# Expected: At least 1 succeeds (first wins rotation), others get
# 401 "auth.refresh_reuse" but do NOT revoke other sessions
```

## E2E Test Specs

New E2E tests to add:

| Test | File | Scenario |
|------|------|----------|
| Single-tab keepalive | `tests/e2e/050-login-stability/single-tab.spec.ts` | SC-001 |
| Multi-tab coexistence | `tests/e2e/050-login-stability/multi-tab.spec.ts` | SC-002 |
| Transient 502 recovery | `tests/e2e/050-login-stability/transient-failure.spec.ts` | SC-003 |
| Eviction toast notification | `tests/e2e/050-login-stability/eviction-toast.spec.ts` | SC-004 |
| Concurrent refresh safety | `tests/e2e/050-login-stability/concurrent-refresh.spec.ts` | SC-005 |

## Backend Unit Tests

| Test | File | What |
|------|------|------|
| Session rotation (in-place) | `tests/unit/test_auth_service.py` | FR-009 |
| Refresh reuse reject (no revoke) | `tests/unit/test_auth_service.py` | FR-008 |
| Error code mapping | `tests/unit/test_auth_service.py` | FR-004 |
| max_active_sessions=10 | `tests/unit/test_auth_service.py` | FR-002 |
| list_active expires filter | `tests/unit/test_auth_service.py` | FR-003 |

## Integration Tests

| Test | File | What |
|------|------|------|
| Multi-tab session isolation | `tests/integration/test_auth_flow.py` | FR-001 |
| Eviction + re-login cycle | `tests/integration/test_auth_flow.py` | FR-004 |
| Concurrent refresh from 2 tabs | `tests/integration/test_auth_flow.py` | FR-008 + FR-009 |
