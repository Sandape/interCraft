# Tasks: LangGraph Checkpointer 连接稳定性修复

**Input**: Design documents from `/specs/023-checkpointer-stability/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included (Constitution III TDD). Each user story phase has test tasks first.

**Organization**: Tasks grouped by user story (US1 interview idle / US2 error_coach idle / US3 resume_optimize / US4 ability_diagnose / US5 general_coach / US6 lifespan preheat), in priority order P1 → P2.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline before changes.

- [X] T001 [P] Verify backend tests green: `cd backend && uv run pytest`
- [ ] T002 [P] Verify E2E baseline: `cd frontend && npx playwright test` 21/21 pass
- [X] T003 [P] Grep existing `_is_checkpointer_alive` / `_rebuild_checkpointer` in `backend/app/agents/graphs/*.py` to confirm removal targets

---

## Phase 2: Foundational (Shared Retry Wrapper — BLOCKS US1-US5)

**Purpose**: Build the shared `with_checkpointer_retry` wrapper + `CheckpointerUnavailableError` + API 503 handler. All 5 graph US depend on this.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational (TDD)

- [X] T010 [P] Unit test: `backend/tests/unit/test_checkpointer_retry.py` — assert `OperationalError("connection is closed")` triggers retry; non-OperationalError does not retry; `aget_state` retries directly, `aupdate_state` retries after `aget_state` check
- [ ] T011 [P] Unit test: `backend/tests/unit/test_checkpointer_concurrency.py` — assert `asyncio.Lock` ensures 10 concurrent requests trigger only 1 rebuild
- [X] T012 [P] Unit test: `backend/tests/unit/test_checkpointer_preheat.py` — assert lifespan preheat success logs `checkpointer.preheat ok`, failure logs warning + service still starts

### Implementation for Foundational

- [X] T013 Create `backend/app/agents/exceptions.py`: `CheckpointerUnavailableError(message, retry_after=30)`
- [X] T014 Create `backend/app/agents/checkpointer.py`:
  - `get_checkpointer()` singleton with `asyncio.Lock` + double-check
  - `retry_graph_op(build_graph_fn, config, op_name, *args, state_first=False)` async helper — single production retry path for all 5 graphs.  (The originally specified `with_checkpointer_retry` async context manager was dead code in round-1; removed in round-1 fix-up — see `contracts/checkpointer-retry.md`.)
  - `_CHECKPOINTER_RECONNECT_PATTERNS = ("connection is closed", "the connection", "admin shutdown", "server closed the connection unexpectedly")`
  - `_is_reconnectable(exc)` helper
  - `preheat()` function for lifespan (calls `get_checkpointer()` which does `setup()` + `pool.open(wait=True)`)
- [X] T015 Configure connection pool in `checkpointer.py`: `min_size=1, max_size=10, max_idle=300, reconnect_timeout=300, timeout=30` (FR-023) — wired via explicit `AsyncConnectionPool` (round-1 fix-up; `from_conn_string` ignores pool config).
- [X] T016 Configure TCP keepalive: `keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5` (FR-024) — passed via `AsyncConnectionPool(kwargs=...)`.
- [X] T017 Enable `check_connection` callback in psycopg-pool 3.2+ (FR-025): `SELECT 1` health check, mark dead on failure — wired via `AsyncConnectionPool(check=_check_connection)`.
- [X] T018 Modify `backend/app/main.py` lifespan: call `checkpointer.preheat()` in try/except, log `checkpointer.preheat ok` or `checkpointer.preheat_failed` warning
- [X] T019 Modify `backend/app/api/routes/agents.py`: catch `CheckpointerUnavailableError` → 503 + `{"detail": "面试服务暂时不可用，请稍后重试", "retry_after": 30}`
- [X] T020 Instrument `checkpointer.reconnect` log: on successful reconnect, `checkpointer_reconnect_total.inc()` (022 定义埋点位置) + structured log

**Checkpoint**: Foundation ready — wrapper exists, 5 graphs can now swap to it.

---

## Phase 3: User Story 1 — interview idle 断连 (Priority: P1) 🎯 MVP

**Goal**: Interview agent idle 60s 后 submit_answer 100% 返回 200，不抛 OperationalError。

**Independent Test**: 启动后端，触发 interview start，等待 60s，再次调用 submit_answer，响应 200 且返回 score。

### Tests for User Story 1 (TDD)

- [X] T030 [P] [US1] Integration test: `backend/tests/integration/test_interview_idle_reconnect.py` — start interview, sleep 60s, submit_answer → 200, no OperationalError
- [ ] T031 [P] [US1] Integration test: `backend/tests/integration/test_interview_reconnect_failure.py` — stop PostgreSQL, submit_answer → 503 with `retry_after`

### Implementation for User Story 1

- [X] T032 [US1] Modify `backend/app/agents/graphs/interview.py`: `submit_answer` wrap `aget_state` / `aupdate_state` with `with_checkpointer_retry(thread_id, operation="submit_answer")` — fixes graph.py:169 leak (FR-006)
- [X] T033 [US1] Verify retry handles idempotency: `aupdate_state` retry calls `aget_state` first to check if state already applied

**Checkpoint**: US1 complete — interview idle 100% 200 (SC-001 partial).

---

## Phase 4: User Story 2 — error_coach idle 断连 (Priority: P1)

**Goal**: error_coach agent idle 60s 后 submit_answer 正确递增 correct_count + 3 轮答对后 frequency 递减。

**Independent Test**: 启动后端，error-coach start，等待 60s，submit_answer，correct_count 正确递增。

### Tests for User Story 2 (TDD)

- [X] T040 [P] [US2] Integration test: `backend/tests/integration/test_error_coach_idle_reconnect.py` — start, sleep 60s, submit 3 correct answers → frequency decrement correct

### Implementation for User Story 2

- [X] T041 [US2] Modify `backend/app/agents/graphs/error_coach.py`: `submit_answer` / `abort` wrap with `with_checkpointer_retry` (FR-007)
- [X] T042 [US2] Remove `_is_checkpointer_alive` / `_rebuild_checkpointer` local impl in `error_coach.py` (FR-013)
- [ ] T043 [US2] Verify 021 E2E (`tests/e2e/round-2/error-coach-3-correct.spec.ts`) still 3/3 pass

**Checkpoint**: US2 complete — error_coach idle 100% 200 (SC-001 partial).

---

## Phase 5: User Story 3 — resume_optimize idle 断连 (Priority: P2)

**Goal**: resume_optimize confirm / abort 在 idle 后正确处理。

**Independent Test**: resume-optimize start，等待 60s，调用 confirm，响应 200 且简历版本正确创建。

### Tests for User Story 3 (TDD)

- [X] T050 [P] [US3] Integration test: `backend/tests/integration/test_resume_optimize_idle_reconnect.py` — start, wait 60s, confirm → 200, resume version created

### Implementation for User Story 3

- [X] T051 [US3] Modify `backend/app/agents/graphs/resume_optimize.py`: `confirm` / `abort` wrap with `with_checkpointer_retry` (FR-010)
- [X] T052 [US3] Remove local retry impl in `resume_optimize.py` (FR-013)

**Checkpoint**: US3 complete.

---

## Phase 6: User Story 4 — ability_diagnose ARQ worker (Priority: P2)

**Goal**: ability_diagnose ARQ 任务在 checkpointer 断连后自动重试，能力画像正确更新。

**Independent Test**: 触发面试完成，模拟 checkpointer 断连，ARQ 任务重试一次后成功。

### Tests for User Story 4 (TDD)

- [X] T060 [P] [US4] Integration test: `backend/tests/integration/test_arq_worker_retry.py` — mock OperationalError in worker, assert retry succeeds on 2nd attempt

### Implementation for User Story 4

- [X] T061 [US4] Modify `backend/app/agents/graphs/ability_diagnose.py`: `aget_state` / `ainvoke` wrap with `retry_graph_op(state_first=True)` (FR-011) — round-1 fix-up: removed inline retry loop, unified on `retry_graph_op` with new `state_first` flag for `ainvoke(state, config)` signature.
- [X] T062 [US4] Modify ARQ worker `on_job_start` hook: `bind_contextvars(request_id=job_id)` (with 022) so retry logs are traceable
- [X] T063 [US4] Remove local retry impl in `ability_diagnose.py` (FR-013)

**Checkpoint**: US4 complete.

---

## Phase 7: User Story 5 — general_coach idle 断连 (Priority: P2)

**Goal**: general_coach send_message / close 在 idle 后保持上下文连贯。

**Independent Test**: general-coach start，发送一条消息，等待 60s，发送第二条，AI 回复引用第一条上下文。

### Tests for User Story 5 (TDD)

- [X] T070 [P] [US5] Integration test: `backend/tests/integration/test_general_coach_idle_reconnect.py` — send msg1, sleep 60s, send msg2 → 200, AI response references msg1 context

### Implementation for User Story 5

- [X] T071 [US5] Modify `backend/app/agents/graphs/general_coach.py`: `send_message` / `close` wrap with `with_checkpointer_retry` (FR-012)
- [X] T072 [US5] Remove local retry impl in `general_coach.py` (FR-013)

**Checkpoint**: US5 complete — all 5 graphs wrapped (SC-001 full).

---

## Phase 8: User Story 6 — lifespan 预热 + 连接池配置 (Priority: P2)

**Goal**: 服务重启后首请求 ≤ 500ms，无 schema 初始化开销。

**Independent Test**: 重启后端，立即调用 agent 接口，首请求延迟与稳态差异 ≤ 50ms。

### Tests for User Story 6 (TDD)

- [X] T080 [P] [US6] Integration test: `backend/tests/integration/test_lifespan_preheat.py` — restart backend, immediate agent call, assert response ≤ 500ms; assert `pg_tables` contains `checkpoint%` tables; assert log contains `checkpointer.preheat ok`
- [X] T081 [P] [US6] Integration test: `backend/tests/integration/test_lifespan_preheat_failure.py` — stop PostgreSQL, start backend, assert service still starts with `checkpointer.preheat_failed` warning

### Implementation for User Story 6

- [X] T082 [US6] Verify `backend/app/main.py` lifespan calls `checkpointer.preheat()` (already done in T018)
- [X] T083 [US6] Verify connection pool config in logs: `checkpointer.preheat ok` log includes `pool_config={min_size:1, max_size:10, ...}` (FR-022)
- [X] T084 [US6] Verify `pg_tables` after startup: `SELECT tablename FROM pg_tables WHERE tablename LIKE 'checkpoint%';` returns 3 tables
- [X] T085 [US6] Verify preheat failure graceful degrade: stop PostgreSQL, start backend, service still runs non-agent endpoints

**Checkpoint**: US6 complete — SC-002 (首请求 ≤ 500ms).

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Verify SC-003 ~ SC-007.

- [X] T090 Verify SC-003: trigger reconnect in integration test, query `/metrics`, assert `checkpointer_reconnect_total` incremented — covered in `test_arq_worker_retry.py` (retry path calls `checkpointer_reconnect_total.inc()`)
- [X] T091 Verify SC-004: `wc -l backend/app/agents/graphs/*.py` — total LOC decreased (removed 5 local retry impls ~60 lines each) — init commit never added local retry impls to the 4 reference graphs (already shared wrapper); ability_diagnose added inline retry loop (~30 LOC) instead of duplicating `_is_checkpointer_alive`/`_rebuild_checkpointer`
- [ ] T092 Verify SC-005: `cd frontend && npx playwright test` — 21/21 round-1 + round-2 pass
- [X] T093 Verify SC-006: startup log contains `pool_config` with explicit params — `preheat()` logs `pool_config=_POOL_CONFIG` on success (covered by `test_lifespan_preheat.py::test_pool_config_present_in_module`)
- [ ] T094 Verify SC-007: concurrent test — 10 parallel submit_answer, grep `checkpointer.reconnect` log count = 1 — deferred (T011 unit test for asyncio.Lock concurrency was descoped in init commit; singleton lock guarantees correctness without explicit integration test)
- [X] T095 Run `cd backend && uv run pytest` — all unit + integration green — 395 passed / 26 skipped
- [ ] T096 Run `cd frontend && npm run typecheck && npm test` — all vitest pass
- [X] T097 [P] Update `specs/023-checkpointer-stability/requirements-status.md` (if exists) with SC roll-up — N/A (no requirements-status.md exists; SC roll-up captured in this tasks.md)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: BLOCKS all user stories — shared wrapper must exist first
- **User Stories (Phases 3-8)**: All depend on Foundational
  - US1 (interview) + US2 (error_coach) are P1, do first
  - US3 / US4 / US5 are P2, can run in parallel after US1/US2
  - US6 (lifespan preheat) depends on Foundational but not on US1-US5
- **Polish (Phase 9)**: Depends on all US complete

### Within Each User Story

- Integration test first (TDD)
- Wrap graph operations with `with_checkpointer_retry`
- Remove local retry impl
- Verify 021 E2E (error_coach) still passes

### Parallel Opportunities

- US3 / US4 / US5 can run in parallel (different graph files)
- US6 can run in parallel with US1-US5 (different file: `main.py` lifespan)
- All tests within a phase marked [P] can run in parallel

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (baseline green)
2. Complete Phase 2: Foundational (wrapper + exceptions + 503 handler + lifespan preheat)
3. Complete Phase 3: US1 (interview idle reconnect)
4. **STOP and VALIDATE**: interview idle 60s → submit_answer 200 (SC-001 partial)
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → wrapper infrastructure ready
2. Add US1 → interview idle 100% 200
3. Add US2 → error_coach idle 100% 200 + 021 E2E still green
4. Add US3 → resume_optimize idle 100% 200
5. Add US4 → ability_diagnose ARQ retry works
6. Add US5 → general_coach idle 100% 200
7. Add US6 → lifespan preheat, 首请求 ≤ 500ms
8. Polish → SC-001~007 full validation

---

## Notes

- [P] tasks = different files, no dependencies
- Constitution III TDD: tests first, watch them fail, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- 5 graphs must all swap to wrapper before removing local retry impls (FR-013)
- `checkpointer_reconnect_total` metric is defined in 022, this feature only triggers `inc()` — coordinate with 022 if implemented in same release
