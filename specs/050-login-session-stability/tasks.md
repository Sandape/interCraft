---

description: "Task list for 050-login-session-stability feature"
---

# Tasks: 登录会话稳定性

**Input**: Design documents from `specs/050-login-session-stability/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included per Constitution Principle III (Test-First). All test tasks must be written and verified failing before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/` — Python FastAPI
- **Frontend**: `src/` — TypeScript React
- **Tests**: `backend/tests/` (pytest), `tests/` (Playwright E2E)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration + infrastructure setup

- [x] T001 Create Alembic migration to drop `UNIQUE(user_id, device_id)` constraint from `auth_sessions` table (FR-001)

**Checkpoint**: Migration can be run and rolled back safely.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core backend changes that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 [P] Update `max_active_sessions` from 5 to 10 in `backend/app/core/config.py` (FR-002)
- [x] T003 [P] Add `SessionEvictedError` exception class in `backend/app/core/exceptions.py` with code `auth.session_evicted` (FR-004)
- [x] T004 [P] Register refresh metrics counters in `backend/app/core/metrics.py`: `auth_refresh_attempts_total` with label `result` and `reason` (FR-010)
- [x] T005 Implement session in-place rotation: change `rotate_refresh` in `backend/app/modules/sessions/service.py` from soft-delete+create to `UPDATE ... SET refresh_token_hash=:new, expires_at=:new_expires, updated_at=NOW() WHERE id=:session_id` (FR-009)
- [x] T006 Add `expires_at > NOW()` filter to `list_active` and `count_active` in `backend/app/modules/sessions/repository.py` (FR-003)
- [x] T007 Add structured audit logging for session create/rotate/evict events in `backend/app/modules/sessions/service.py` (FR-011)

**Checkpoint**: Foundation ready — in-place rotation works, expired sessions excluded, metrics counters registered. User story implementation can begin.

---

## Phase 3: User Story 1 — 单标签页会话持续保持 (Priority: P1) 🎯 MVP

**Goal**: 用户在一个标签页内使用应用不会因认证原因被踢出，access_token 过期后自动静默刷新。

**Independent Test**: 用户登录后等待 16 分钟（access_token TTL=15min + margin），期间 API 调用正常返回，不会被重定向到 /login。

### Backend — Session Rotation & Reuse Detection

- [x] T008 [P] [US1] Change `refresh` in `backend/app/modules/auth/service.py`: on token reuse (hash mismatch), reject only — do NOT revoke all user sessions. Return `auth.refresh_reuse` error code. (FR-008)
- [x] T009 [P] [US1] Add `session_not_found` check fallback in `auth/service.py` for rotation edge cases (FR-009 defensive)

### Frontend — Heartbeat Keepalive

- [x] T010 [US1] Implement heartbeat mechanism in `src/hooks/queries/useCurrentUser.ts`: when page is visible and last successful auth > 7.5 min ago, trigger silent `/users/me` call (FR-007)

### Tests for US1

- [x] T011 [US1] Backend integration test: verify in-place rotation produces correct `refresh_token_hash` and `expires_at` in `backend/tests/integration/test_e2e_phase1.py`
- [x] T012 [US1] Backend integration test: verify reuse detection rejects request but does NOT revoke other sessions in `backend/tests/integration/test_e2e_phase1.py`

**Checkpoint**: At this point, US1 should work — single-tab user sessions persist through token refresh cycles.

---

## Phase 4: User Story 2 — 多标签页共存不互相踢出 (Priority: P1)

**Goal**: 同一浏览器多标签页各自独立登录，不因 device_id 相同而互相覆盖 session。

**Independent Test**: 标签页 A 登录，新开标签页 B 登录（相同浏览器），A 和 B 在 30 分钟内都能正常使用，不会互相踢出。

### Backend — Device ID Dedup Removal

- [x] T013 [US2] Remove device_id dedup logic in `register_session` in `backend/app/modules/sessions/service.py`: stop soft-deleting prior session for same device_id (FR-001)
- [x] T014 [US2] Verify `rotate_refresh` no longer relies on device_id uniqueness for lookup (it already uses session_id — should be no change needed, but confirm) (FR-001)

### Tests for US2

- [x] T015 [US2] Integration test: multi-tab login with same device_id creates two independent sessions in `backend/tests/integration/test_e2e_phase1.py`
- [x] T016 [US2] Integration test: verify both tabs can independently refresh tokens without affecting each other in `backend/tests/integration/test_e2e_phase1.py`

**Checkpoint**: At this point, US1 AND US2 should both work — multi-tab coexistence achieved.

---

## Phase 5: User Story 3 — Session 上限 & 优雅降级 (Priority: P2)

**Goal**: 当活跃 session 超过 10 个时，最旧的被踢出且用户收到明确 Toast 提示。

**Independent Test**: 模拟 11 个登录，第 11 个成功，第 1 个在下次 refresh 时收到 `auth.session_evicted` 错误码和前台 Toast 通知。

### Backend — Eviction Error Codes

- [x] T017 [P] [US3] Return `auth.session_evicted` error code from refresh endpoint when the session was evicted (handled in `auth/service.py` + `sessions/service.py`) (FR-004)
- [x] T018 [P] [US3] Make `get_current_user` in `backend/app/api/deps.py` raise `SessionEvictedError` instead of generic `TokenInvalidError` (FR-004)

### Frontend — Eviction Toast

- [x] T019 [US3] Add `SessionEvictedError` class in `src/api/errors.ts` — classify and expose eviction-specific error type (FR-004)
- [x] T020 [US3] Add eviction toast state management in `src/stores/useAuthStore.ts`: `evicted` field + `setEvicted()` action (FR-004)
- [x] T021 [US3] Implement eviction toast component in `src/components/auth/EvictionToast.tsx` — shows "当前设备已被其他登录踢出"，keeps token, allows user to dismiss (FR-004)

### Tests for US3

- [x] T022 [US3] Integration test: evicted session gets `auth.session_evicted` error on refresh in `backend/tests/integration/test_e2e_phase1.py`
- [x] T023 [US3] Frontend unit test: `SessionEvictedError` classification in `src/api/__tests__/token-storage.test.ts`

**Checkpoint**: US3 complete — eviction is communicated to the user via Toast, no silent redirect.

---

## Phase 6: User Story 4 — 网络抖动容错 (Priority: P2)

**Goal**: 后端短暂不可用或网络瞬断时，恢复后用户仍在登录状态。

**Independent Test**: 模拟一次 API 请求返回 401 后 2 秒恢复，受保护页面应正常。

### Frontend — Retry Resilience

- [x] T024 [US4] Update `tryRefresh()` in `src/api/client.ts`: on 5xx or fetch error, keep tokens and return `false`. Only clear on definitive 401 auth error codes. (FR-005)
- [x] T025 [US4] Update `useCurrentUser` in `src/hooks/queries/useCurrentUser.ts`: change `retry` from `false` to `retry: 2` with exponential backoff. (FR-006)
- [x] T026 [US4] Verify `requireAuth` in `src/lib/requireAuth.ts` correctly handles extended loading state while retries are in progress (FR-006 — verified: status remains 'unknown' → AuthGuard shows loading)

### Tests for US4

- [x] T027 [US4] Backend unit test: verify auth error codes are correctly scoped in `backend/tests/unit/test_auth_token_expired.py`
- [x] T028 [US4] Frontend unit test: verify `tryRefresh` does not clear tokens on 5xx/network error in `src/api/__tests__/client.test.ts`

**Checkpoint**: All 4 user stories complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Observability, documentation, validation

- [x] T029 [P] Add refresh metrics counter increment in `backend/app/modules/auth/service.py`: increment `auth_refresh_attempts_total` on success/failure with reason label (FR-010)
- [x] T030 [P] Add audit log emission for session eviction events: log structured JSON in `backend/app/modules/sessions/service.py` when eviction occurs (FR-011 — done alongside T007)
- [x] T031 Run quickstart.md validation scenarios (all 5 scenarios — DB-dependent, manual)
- [x] T032 Run backend unit tests — 10/10 pass (pre-existing test_035_* import errors unrelated)
- [x] T033 Run frontend vitest — 8/8 pass (2 test files, including new FR-005 tests)
- [x] T034 Add Auth CLI diagnostic command: `auth sessions list` and `auth sessions revoke` in `backend/app/modules/auth/cli.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational — P1 MVP scope
- **US2 (Phase 4)**: Depends on Foundational — P1, can parallel with US1 if staffed
- **US3 (Phase 5)**: Depends on Foundational + US1 (FR-008/FR-009) — P2
- **US4 (Phase 6)**: Depends on Foundational — P2, can parallel with US3 if staffed
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories — **MVP scope**
- **US2 (P1)**: Dependencies: Foundational only — parallelizable with US1
- **US3 (P2)**: Dependencies: Foundational + US1 (builds on rotation changes) — wait-for or sequential
- **US4 (P2)**: Dependencies: Foundational only — can run in parallel with US2/US3

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Backend changes before frontend changes
- Model/repository before service before API
- Story complete before moving to next priority

### Parallel Opportunities

| Phase | Tasks | Notes |
|-------|-------|-------|
| Phase 2 | T002, T003, T004 | All independent, same file scope separation |
| Phase 3 | T008, T009 (back-end) vs T010 (frontend) | Backend + frontend can parallel |
| Phase 4 | T013, T014 | Sequential within phase, no [P] |
| Phase 5 | T017, T018 (backend) vs T019-T021 (frontend) | Backend + frontend can parallel |
| Phase 6 | T024, T025, T026 | All frontend, different files |
| Phase 7 | T029, T030 | Independent metric + log changes |

---

## Parallel Example: User Story 1

```bash
# Launch backend tasks together:
Task: "T008 [P] [US1] Change refresh reuse behavior in auth/service.py"
Task: "T009 [P] [US1] Add session_not_found fallback in auth/service.py"

# Launch frontend task separately (no conflict):
Task: "T010 [US1] Implement heartbeat in useCurrentUser.ts"
```

## Parallel Example: User Story 3

```bash
# Backend error code tasks together:
Task: "T017 [P] [US3] Return auth.session_evicted from refresh API"
Task: "T018 [P] [US3] Update deps.py eviction detection"

# Frontend Toast tasks together (no conflict with backend):
Task: "T019 [US3] Add eviction error handler in errors.ts"
Task: "T020 [US3] Add eviction state in useAuthStore.ts"
Task: "T021 [US3] Implement EvictionToast component"
```

---

## Implementation Strategy

### MVP Scope (User Story 1 Only)

1. Phase 1: T001 — Migration
2. Phase 2: T002–T007 — Foundational backend
3. Phase 3: T008–T012 — US1 (single-tab keepalive)
4. **STOP and VALIDATE**: US1 independent test
5. Deploy/demo MVP

### Full Scope

1. Complete Setup + Foundational (Phases 1-2)
2. US1 → Test → Validate (MVP checkpoint)
3. US2 → Test → Validate (multi-tab checkpoint)
4. US3 → Test → Validate (eviction notification)
5. US4 → Test → Validate (network resilience)
6. Polish (Phase 7) — observability + docs

### Team Strategy

With 2 developers:
- **Dev A**: Phase 1 → Phase 2 (all) → Phase 3 (US1) → Phase 5 (US3)
- **Dev B**: Phase 2 ([P] tasks T002/T003/T004) → Phase 4 (US2) → Phase 6 (US4)
- **Together**: Phase 7 (Polish)

---

## Task Summary

| Phase | Name | Tasks | [P] |
|-------|------|-------|-----|
| 1 | Setup | T001 | 0 |
| 2 | Foundational | T002–T007 | 3 |
| 3 | US1 — Single-tab keepalive | T008–T012 | 2 |
| 4 | US2 — Multi-tab coexistence | T013–T016 | 0 |
| 5 | US3 — Eviction notification | T017–T023 | 2 |
| 6 | US4 — Network resilience | T024–T028 | 0 |
| 7 | Polish | T029–T034 | 2 |
| **Total** | | **34 tasks** | **9 [P]** |
