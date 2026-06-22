# Tasks: 性能与可观测性增强

**Input**: Design documents from `/specs/022-perf-observability-enhancement/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included (Constitution III TDD is non-negotiable). Each user story phase has test tasks first.

**Organization**: Tasks grouped by user story (US1 request_id / US2 N+1 / US3 index / US4 lazy / US5 metrics / US6 manualChunks), in priority order P1 → P2 → P3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project init needed — existing backend + frontend structure reused. This phase only documents baseline.

- [ ] T001 [P] Verify backend test command `cd backend && uv run pytest` baseline green
- [ ] T002 [P] Verify frontend test command `cd frontend && npm run typecheck && npm test` baseline green
- [ ] T003 [P] Verify E2E baseline `cd frontend && npx playwright test` 21/21 green

**Checkpoint**: Baseline established before any change.

---

## Phase 2: Foundational (No Blocking Prerequisites)

**Purpose**: This feature has no shared blocking infrastructure — each US is independent. Skip to US phases.

---

## Phase 3: User Story 1 — request_id 关联 (Priority: P1) 🎯 MVP

**Goal**: LLM 日志通过 `X-Request-ID` 关联 HTTP 请求，覆盖率 100%。

**Independent Test**: 在 `/api/v1/agents/error-coach/{tid}/messages` 请求头注入 `X-Request-ID: abc-123`，触发 evaluate 节点 LLM 调用后，grep LLM 日志按 `request_id=abc-123` 找到 `llm.invoke` 事件。

### Tests for User Story 1 (TDD — write first, watch fail)

- [ ] T010 [P] [US1] Unit test: `backend/tests/unit/test_request_id_middleware.py` — assert X-Request-ID 透传 / 生成 UUID / 响应头注入
- [ ] T011 [P] [US1] Unit test: `backend/tests/unit/test_llm_client_request_id.py` — assert `llm.invoke` 日志含 request_id 字段 (mock ContextVar)
- [ ] T012 [P] [US1] Integration test: `backend/tests/integration/test_request_id_propagation.py` — HTTP 请求 → LLM 调用 → 日志按 request_id 关联

### Implementation for User Story 1

- [ ] T013 [US1] Create `backend/app/middleware/request_id.py`: `ContextVar` + FastAPI middleware (read X-Request-ID or gen UUID, inject response header)
- [ ] T014 [US1] Modify `backend/app/main.py`: register `RequestIDMiddleware`
- [ ] T015 [US1] Modify `backend/app/observability/logging.py`: structlog `merge_contextvars` processor auto-injects request_id
- [ ] T016 [US1] Modify `backend/app/agents/llm_client.py`: `invoke` / `invoke_stream` / `retry` logs read request_id from ContextVar (remove ad-hoc UUID generation)
- [ ] T017 [US1] Modify ARQ worker `on_job_start` hook: `bind_contextvars(request_id=job_id)` for non-HTTP context (FR-004)
- [ ] T018 [US1] Verify all `llm.invoke` / `llm.retry` / `llm.mock_invoke` log events carry request_id field

**Checkpoint**: US1 complete — request_id 覆盖率 100% (SC-001).

---

## Phase 4: User Story 2 — Resume 列表 N+1 修复 (Priority: P1)

**Goal**: Resume 列表 10 分支首屏 P95 ≤ 300ms，SQL 查询 ≤ 2 次。

**Independent Test**: 创建 1 用户 + 10 分支（每分支 3 版本 + 5 块），访问 `GET /api/v1/resume-branches`，断言 SQL 计数 ≤ 2 + P95 ≤ 300ms。

### Tests for User Story 2 (TDD)

- [ ] T020 [P] [US2] Integration test: `backend/tests/integration/test_resume_branch_list_n_plus_1.py` — assert 10 branches → SQL count ≤ 2 (hook `before_cursor_execute`)
- [ ] T021 [P] [US2] Contract test: `backend/tests/unit/test_resume_branch_list_response.py` — assert response items contain `version_count` + `block_count` fields

### Implementation for User Story 2

- [ ] T022 [US2] Modify `backend/app/modules/resume/service.py`: list query uses `selectinload(ResumeBranch.versions).selectinload(ResumeVersion.blocks)` + in-memory aggregation
- [ ] T023 [US2] Modify `backend/app/modules/resume/api.py`: response schema add `version_count` / `block_count` virtual fields
- [ ] T024 [US2] Verify existing field name: grep `versions_count` vs `version_count` in existing schema, use whichever is already in contract (FR-013)
- [ ] T025 [US2] Modify `frontend/src/repositories/ResumeRepository.ts`: extend type with `version_count` / `block_count`
- [ ] T026 [US2] Modify `frontend/src/pages/ResumeListPage.tsx` (or equivalent): use `branch.version_count` / `branch.block_count` from response, remove per-branch COUNT requests

**Checkpoint**: US2 complete — SC-002 (P95 ≤ 300ms).

---

## Phase 5: User Story 3 — errors 表复合索引 (Priority: P2)

**Goal**: `error_questions` 表新增 `(user_id, status, frequency, created_at) WHERE deleted_at IS NULL` 部分索引，P95 ≤ 200ms。

**Independent Test**: 插入 500 条错题，`EXPLAIN ANALYZE` 输出含 `Index Scan`，P95 ≤ 200ms。

### Tests for User Story 3 (TDD)

- [ ] T030 [P] [US3] Integration test: `backend/tests/integration/test_error_questions_index.py` — assert `EXPLAIN` output contains `Index Scan` not `Seq Scan` for 500 rows

### Implementation for User Story 3

- [ ] T031 [US3] Create Alembic migration `backend/alembic/versions/xxxx_add_error_questions_compound_index.py`: `CREATE INDEX CONCURRENTLY idx_error_questions_user_status_freq_created ON error_questions (user_id, status, frequency, created_at) WHERE deleted_at IS NULL`
- [ ] T032 [US3] Run migration locally: `cd backend && uv run alembic upgrade head`
- [ ] T033 [US3] Verify index used: `EXPLAIN ANALYZE SELECT * FROM error_questions WHERE user_id='...' AND deleted_at IS NULL ORDER BY status, frequency, created_at LIMIT 500;`

**Checkpoint**: US3 complete — SC-003 (P95 ≤ 200ms).

---

## Phase 6: User Story 4 — 前端路由懒加载 (Priority: P2)

**Goal**: 登录页首屏 JS gzip ≤ 500KB，非首屏页面 `React.lazy` 加载。

**Independent Test**: `npm run build` 后 `dist/index.html` 首屏引用的 JS gzip ≤ 500KB，访问 `/login` 仅下载 `index` + `vendor` + `Login` chunk。

### Tests for User Story 4 (TDD)

- [ ] T040 [P] [US4] Build artifact test: `frontend/tests/unit/test_route_lazy.test.ts` — assert `dist/assets/` has separate chunks for ResumeEditor / InterviewLive / InterviewReport / ErrorBook / Profile / Jobs / Settings

### Implementation for User Story 4

- [ ] T041 [US4] Modify `frontend/src/App.tsx`: wrap all non-login pages with `React.lazy(() => import(...))`, wrap routes in `<Suspense fallback={<Skeleton/>}>`
- [ ] T042 [US4] Keep `/login` route eager (first screen optimization)
- [ ] T043 [US4] Run `cd frontend && npm run build`, verify chunk separation
- [ ] T044 [US4] Verify gzip size: `gzip -c dist/assets/index-*.js | wc -c` ≤ 500000

**Checkpoint**: US4 complete — SC-004 (首屏 ≤ 500KB).

---

## Phase 7: User Story 5 — metrics 覆盖补全 (Priority: P2)

**Goal**: `/metrics` 端点暴露 ≥ 15 个指标名，含新增 LLM quota / checkpointer / WS / ARQ 四类。

**Independent Test**: 触发 LLM 配额不足 + WS 连接，`/metrics` 含 `llm_quota_exhausted_total{user_id=...}` + `ws_connections_active` 指标。

### Tests for User Story 5 (TDD)

- [ ] T050 [P] [US5] Unit test: `backend/tests/unit/test_metrics_collectors.py` — assert 6 new metrics exist with correct type (Counter/Gauge) and labels

### Implementation for User Story 5

- [ ] T051 [US5] Modify `backend/app/observability/metrics.py`: add `llm_quota_exhausted_total` (Counter, labels=[user_id])
- [ ] T052 [P] [US5] Modify `backend/app/observability/metrics.py`: add `llm_quota_available` (Gauge, labels=[user_id])
- [ ] T053 [P] [US5] Modify `backend/app/observability/metrics.py`: add `checkpointer_reconnect_total` (Counter) —埋点位置为 023 的 with_checkpointer_retry，本 feature 仅定义 metric
- [ ] T054 [P] [US5] Modify `backend/app/observability/metrics.py`: add `ws_connections_active` (Gauge)
- [ ] T055 [P] [US5] Modify `backend/app/observability/metrics.py`: add `arq_jobs_queued` (Gauge, labels=[queue])
- [ ] T056 [P] [US5] Modify `backend/app/observability/metrics.py`: add `arq_jobs_failed_total` (Counter, labels=[queue])
- [ ] T057 [US5] Instrument LLM quota check path: `llm_quota_exhausted_total.inc(user_id=...)` on quota exceeded
- [ ] T058 [US5] Instrument WS connection accept/disconnect: `ws_connections_active.inc()` / `.dec()`
- [ ] T059 [US5] Instrument ARQ `on_job_start` / `on_failure`: `arq_jobs_queued.set()` / `arq_jobs_failed_total.inc()`
- [ ] T060 [US5] Verify `/metrics` endpoint returns ≥ 15 distinct metric names

**Checkpoint**: US5 complete — SC-005 (≥ 15 metrics).

---

## Phase 8: User Story 6 — Vite manualChunks (Priority: P3)

**Goal**: `vendor-*.js` 独立分包，体积 ≥ 40% 总 JS，hash 在依赖未变时稳定。

**Independent Test**: `npm run build` 后 `dist/assets/vendor-*.js` 体积 ≥ 40% 总 JS，仅改业务代码 vendor hash 不变。

### Tests for User Story 6 (TDD)

- [ ] T070 [P] [US6] Build artifact test: `frontend/tests/unit/test_vendor_chunk.test.ts` — assert `vendor-*.js` exists, ≥ 40% of total JS size

### Implementation for User Story 6

- [ ] T071 [US6] Modify `frontend/vite.config.ts`: add `build.rollupOptions.output.manualChunks` function form, split `react` / `react-dom` / `react-router-dom` / `@tanstack/react-query` into `vendor` chunk
- [ ] T072 [US6] Run `npm run build`, verify `vendor-*.js` exists
- [ ] T073 [US6] Verify vendor hash stability: modify `src/pages/Login.tsx` (add comment), rebuild, `vendor-*.js` hash unchanged
- [ ] T074 [US6] Verify vendor hash change: bump `react` version in package.json, rebuild, `vendor-*.js` hash changes

**Checkpoint**: US6 complete — SC-006 (vendor ≥ 40%, hash stable).

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 验证 SC-007 既有 E2E 零回归。

- [ ] T090 Run `cd backend && uv run pytest` — all unit + integration tests pass
- [ ] T091 Run `cd frontend && npm run typecheck && npm test` — all vitest pass
- [ ] T092 Run `cd frontend && npx playwright test --config=playwright.config.ts` — round-1 + round-2 21/21 pass
- [ ] T093 Verify SC-001: request_id 100% coverage (grep LLM logs by request_id)
- [ ] T094 Verify SC-002: Resume list 10 branches P95 ≤ 300ms (quickstart Scenario 2)
- [ ] T095 Verify SC-003: errors list 500 rows P95 ≤ 200ms (quickstart Scenario 3)
- [ ] T096 Verify SC-004: first-screen JS gzip ≤ 500KB (quickstart Scenario 4)
- [ ] T097 Verify SC-005: `/metrics` ≥ 15 metric names (quickstart Scenario 5)
- [ ] T098 Verify SC-006: vendor chunk ≥ 40%, hash stable (quickstart Scenario 6)
- [ ] T099 Verify SC-007: E2E 21/21 pass (quickstart Scenario 7)
- [ ] T100 [P] Update `specs/022-perf-observability-enhancement/requirements-status.md` (if exists) with SC roll-up

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Empty (no blocking prereqs)
- **User Stories (Phases 3-8)**: All independent, can run in parallel if team capacity allows
- **Polish (Phase 9)**: Depends on all US phases complete

### User Story Dependencies

- **US1 (P1) request_id**: Independent, no deps
- **US2 (P1) N+1**: Independent, no deps
- **US3 (P2) index**: Independent, no deps
- **US4 (P2) lazy**: Independent, no deps
- **US5 (P2) metrics**: Independent — `checkpointer_reconnect_total` is defined here but埋点 is in 023
- **US6 (P3) manualChunks**: Depends on US4 (both touch build config, but different files)

### Within Each User Story

- Tests MUST be written first (Constitution III TDD non-negotiable)
- Backend tests before backend impl
- Frontend tests before frontend impl
- Migration before index test (US3)
- Build verification after config change (US4/US6)

### Parallel Opportunities

- All Setup tasks T001-T003 can run in parallel
- All US1 test tasks T010-T012 can run in parallel
- All US5 metric definitions T051-T056 can run in parallel (different metrics, same file — coordinate to avoid merge conflicts or split into separate commits)
- US1 / US2 / US3 / US4 can all run in parallel after Setup (different modules/files)

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (baseline green)
2. Complete Phase 3: US1 (request_id)
3. **STOP and VALIDATE**: request_id 覆盖率 100% (SC-001)
4. Deploy/demo if ready

### Incremental Delivery

1. Setup + US1 → request_id 关联 MVP
2. Add US2 → Resume 列表性能修复
3. Add US3 → errors 索引性能修复
4. Add US4 → 路由懒加载首屏优化
5. Add US5 → metrics 可观测性补全
6. Add US6 → vendor 分包稳定
7. Polish → E2E 零回归验证

---

## Notes

- [P] tasks = different files, no dependencies
- Each user story is independently completable and testable
- Constitution III TDD: tests first, watch them fail, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
