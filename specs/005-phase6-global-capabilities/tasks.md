---

description: "Task list for Phase 6 — 全局能力收尾"
---

# Tasks: Phase 6 — 全局能力收尾

**Input**: Design documents from `/specs/005-phase6-global-capabilities/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: 包含测试任务。遵循 Constitution Test-First 原则,测试先于实现。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3...)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/`, `backend/tests/`
- **Frontend**: `frontend/src/`, `frontend/tests/`
- **Migrations**: `backend/migrations/versions/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 数据库迁移、环境变量配置

- [X] T001 Create migration: add `role`/`scheduled_purge_at`/`cancellation_deadline` to `users` table in `backend/migrations/versions/XXX_add_lifecycle_fields.py`
- [X] T002 Create migration: `audit_logs` table with monthly partitioning in `backend/migrations/versions/XXX_create_audit_logs.py`
- [X] T003 Create migration: `export_tasks` table in `backend/migrations/versions/XXX_create_export_tasks.py`
- [X] T004 [P] Create migration: `resources` and `help_faq` tables in `backend/migrations/versions/XXX_create_content_tables.py`
- [X] T005 [P] Create migration: `subscription_plans` table with seed data in `backend/migrations/versions/XXX_create_subscription_plans.py`
- [X] T006 Add `EXPORT_STORAGE_PATH` env var (default `/tmp/exports/`) in `backend/.env` and `backend/app/core/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**Purpose**: Admin 鉴权、审计中间件、站内通知基础设施

- [X] T007 [P] Add `role` field to User model and admin role check dependency in `backend/app/auth/dependencies.py`
- [X] T008 [P] Create notification service (站内通知 CRUD) in `backend/app/account/notification.py`
- [X] T009 [P] Create notification center endpoint `GET /api/v1/account/notification-center` in `backend/app/account/router.py`

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 — 账号生命周期 (Priority: P1) 🎯 MVP

**Goal**: 用户可发起注销、7 天冷静期内取消、90 天后物理清除

**Independent Test**: `curl POST /api/v1/account/delete` → status=soft_deleted → `curl POST /api/v1/account/cancel-deletion` → status=active

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T010 [P] [US1] Unit test for lifecycle status transitions (`active→soft_deleted→purged→deleted`) in `backend/tests/unit/account/test_lifecycle.py`
- [ ] T011 [P] [US1] Unit test for cancellation deadline enforcement in `backend/tests/unit/account/test_lifecycle.py`
- [ ] T012 [P] [US1] Integration test for full lifecycle flow (delete → cancel → re-delete → wait for purge cron) in `backend/tests/integration/test_m20_lifecycle.py`
- [ ] T013 [US1] Integration test for ARQ cron `purge_expired_accounts` in `backend/tests/integration/test_m20_lifecycle.py`
- [ ] T014 [US1] Integration test for ARQ cron `physical_cleanup` in `backend/tests/integration/test_m20_lifecycle.py`

### Implementation for User Story 1

- [X] T015 [US1] Implement lifecycle service (`delete_account`/`cancel_deletion`/`get_deletion_status`) in `backend/app/account/lifecycle.py`
- [X] T016 [US1] Implement lifecycle endpoints (`POST /api/v1/account/delete`, `POST /api/v1/account/cancel-deletion`, `GET /api/v1/account/deletion-status`) in `backend/app/account/router.py`
- [X] T017 [US1] Implement ARQ cron `purge_expired_accounts` (daily: mark purged) in `backend/app/workers/tasks/purge_expired_accounts.py`
- [X] T018 [US1] Implement ARQ cron `physical_cleanup` (weekly: delete purged > 7d, batch 100) in `backend/app/workers/tasks/physical_cleanup.py`
- [ ] T019 [US1] Integrate lifecycle events with email + notification service (注销确认/取消/过期通知)

**Checkpoint**: US1 fully functional — user can create/cancel account and cron jobs handle cleanup

---

## Phase 4: User Story 2 — 数据导入导出 (Priority: P2)

**Goal**: 用户可 ZIP 导出全量数据,支持 JSON/Markdown 导入简历

**Independent Test**: Export: `POST /api/v1/account/export` → wait → `GET /api/v1/account/export/{id}/download` → ZIP with 5+ data types. Import: `POST /api/v1/resumes/import` with `.md` file → new branch created.

### Tests for User Story 2

- [ ] T020 [P] [US2] Unit test for export ZIP generation and structure in `backend/tests/unit/account/test_export_service.py`
- [ ] T021 [P] [US2] Unit test for JSON resume import parsing in `backend/tests/unit/account/test_import_service.py`
- [ ] T022 [P] [US2] Unit test for Markdown resume import parsing in `backend/tests/unit/account/test_import_service.py`
- [ ] T023 [US2] Integration test for export→store→notify→download→expire full flow in `backend/tests/integration/test_m21_export_import.py`
- [ ] T024 [US2] Integration test for import→create branch→verify blocks flow in `backend/tests/integration/test_m21_export_import.py`

### Implementation for User Story 2

- [X] T025 [P] [US2] Implement export service (ZIP packaging with JSON + Markdown) in `backend/app/account/export_service.py`
- [X] T026 [P] [US2] Implement import service (JSON + Markdown parsing) in `backend/app/account/import_service.py`
- [X] T027 [US2] Implement export endpoints (`POST /api/v1/account/export`, `GET /api/v1/account/export/{id}/status`, `GET /api/v1/account/export/{id}/download`) in `backend/app/account/router.py`
- [X] T028 [US2] Implement import endpoint (`POST /api/v1/resumes/import`) in `backend/app/account/router.py`
- [X] T029 [US2] Implement ARQ task `export_user_data` in `backend/app/workers/main.py`
- [X] T030 [US2] Implement ARQ cron `cleanup_expired_exports` (hourly) in `backend/app/workers/tasks/cleanup_expired_exports.py`
- [ ] T031 [US2] Integrate export completion with email + notification service

**Checkpoint**: US2 fully functional — data export/import works independently

---

## Phase 5: User Story 3 — 审计可观测完整版 (Priority: P2)

**Goal**: 所有写操作 + Agent 子图关键节点写入 audit_logs,用户和 admin 可查询,可选 LangSmith

**Independent Test**: Perform any write operation → `GET /api/v1/audit-logs` shows the record → (admin) `GET /api/v1/admin/audit-logs` shows all users' records

### Tests for User Story 3

- [ ] T032 [P] [US3] Unit test for audit_logs write operation (all action types) in `backend/tests/unit/audit/test_audit_service.py`
- [ ] T033 [P] [US3] Unit test for RLS filtering (user sees only own logs) in `backend/tests/unit/audit/test_audit_service.py`
- [ ] T034 [P] [US3] Unit test for admin audit query in `backend/tests/unit/audit/test_audit_service.py`
- [ ] T035 [US3] Integration test for write→audit→query→admin full flow in `backend/tests/integration/test_m22_audit.py`

### Implementation for User Story 3

- [X] T036 [US3] Implement audit service (write/query with RLS) in `backend/app/audit/service.py`
- [X] T037 [US3] Implement audit middleware decorator `@audit_log(action, resource_type)` in `backend/app/audit/middleware.py`
- [X] T038 [US3] Implement user audit endpoint `GET /api/v1/audit-logs` in `backend/app/audit/router.py`
- [X] T039 [US3] Implement admin audit endpoint `GET /api/v1/admin/audit-logs` in `backend/app/audit/router.py`
- [ ] T040 [US3] Add audit decorator to existing Phase 1-5 write endpoints (resume CRUD, interview session CRUD, etc.)
- [ ] T041 [US3] Add audit decorator to Agent subgraph key nodes (interrupt/score/diagnose/suggest/end) in Phase 4/5 agent code
- [ ] T042 [US3] Enable LangSmith tracing (optional, via env var) in `backend/app/core/llm.py`
- [X] T043 [US3] Implement ARQ cron `create_next_audit_partition` (monthly: create next month's partition) in `backend/app/workers/tasks/create_next_audit_partition.py`

**Checkpoint**: US3 fully functional — all operations are audited and queryable

---

## Phase 6: User Story 4 — Settings 全部 tab 迁移 (Priority: P2)

**Goal**: 设备/订阅/安全/导出 4 个 tab 从 mock 切换到真实 API,订阅管理与 token 配额控制

**Independent Test**: Visit `/settings` → each tab shows real data → devices tab shows current device → subscription tab shows plan+usage → security tab shows change password form → export tab shows export button

### Tests for User Story 4

- [ ] T044 [P] [US4] Unit test for subscription service (quota check, plan info) in `backend/tests/unit/account/test_subscription.py`
- [ ] T045 [P] [US4] Unit test for subscription cron `reset_monthly_quota` in `backend/tests/unit/account/test_subscription.py`
- [ ] T046 [P] [US4] Unit test for DevicesTab component in `frontend/tests/unit/components/settings/DevicesTab.test.tsx`
- [ ] T047 [P] [US4] Unit test for SubscriptionTab component in `frontend/tests/unit/components/settings/SubscriptionTab.test.tsx`
- [ ] T048 [P] [US4] Unit test for SecurityTab component in `frontend/tests/unit/components/settings/SecurityTab.test.tsx`
- [ ] T049 [P] [US4] Unit test for ExportTab component in `frontend/tests/unit/components/settings/ExportTab.test.tsx`
- [ ] T050 [US4] E2E test for Settings tab flow in `frontend/tests/e2e/settings-flow.spec.ts`

### Implementation for User Story 4 — Backend

- [X] T051 [P] [US4] Implement devices endpoint (`GET /api/v1/settings/devices`, `POST /api/v1/settings/devices/logout-others`) in `backend/app/account/router.py`
- [X] T052 [P] [US4] Implement security endpoint (`POST /api/v1/settings/change-password`, `GET /api/v1/settings/login-history`) in `backend/app/account/router.py`
- [X] T053 [P] [US4] Implement subscription endpoints (`GET /api/v1/subscription/plans`, `GET /api/v1/subscription/current`, `POST /api/v1/subscription/pre-check`) in `backend/app/account/subscription.py`
- [X] T054 [US4] Implement ARQ cron `reset_monthly_quota` (monthly 1st UTC 00:00) in `backend/app/workers/tasks/reset_monthly_quota_cron.py`

### Implementation for User Story 4 — Frontend

- [X] T055 [P] [US4] Create account API service (`src/api/account.ts`) with all Settings endpoints
- [X] T056 [P] [US4] Create DevicesTab component in `src/components/settings/DevicesTab.tsx`
- [X] T057 [P] [US4] Create SubscriptionTab component in `src/components/settings/SubscriptionTab.tsx`
- [X] T058 [P] [US4] Create SecurityTab component (change password form + login activity list + 注销入口) in `src/components/settings/SecurityTab.tsx`
- [X] T059 [P] [US4] Create ExportTab component (export button + progress + download) in `src/components/settings/ExportTab.tsx`
- [X] T060 [US4] Update `src/pages/Settings.tsx` to wire all 4 tabs to real API, remove "Phase 6 上线" placeholders

**Checkpoint**: US4 fully functional — all Settings tabs show real data and support all operations

---

## Phase 7: User Story 5 — Resources & Help 真实内容 (Priority: P3)

**Goal**: Resources 和 Help 页面从 mock 替换为真实内容,支持分类筛选、全文搜索

**Independent Test**: Visit `/resources` → categorized articles → click one → full content. Visit `/help` → FAQ accordion → search "注销" → matching results

### Tests for User Story 5

- [ ] T061 [P] [US5] Unit test for content service (CRUD + search) in `backend/tests/unit/content/test_content_service.py`
- [ ] T062 [P] [US5] Unit test for ResourceCard component in `frontend/tests/unit/components/content/ResourceCard.test.tsx`
- [ ] T063 [P] [US5] Unit test for FaqAccordion component in `frontend/tests/unit/components/content/FaqAccordion.test.tsx`
- [ ] T064 [US5] Integration test for content API (CRUD + search) in `backend/tests/integration/test_content_api.py`

### Implementation for User Story 5 — Backend

- [X] T065 [P] [US5] Implement content service (resources CRUD + FAQ CRUD + search) in `backend/app/content/service.py`
- [X] T066 [P] [US5] Implement content endpoints (`GET /api/v1/resources`, `GET /api/v1/resources/{id}`, `GET /api/v1/help/faq`, `GET /api/v1/help/faq/{id}`, `GET /api/v1/help/search`) in `backend/app/content/router.py`
- [X] T067 [US5] Create seed data for resources (5-10 articles) and FAQ (5-10 items per category) in `backend/app/content/seed.py`

### Implementation for User Story 5 — Frontend

- [X] T068 [P] [US5] Create content API service in `src/api/content.ts`
- [ ] T069 [P] [US5] Create ResourceCard component in `src/components/content/ResourceCard.tsx`
- [ ] T070 [P] [US5] Create FaqAccordion component in `src/components/content/FaqAccordion.tsx`
- [X] T071 [P] [US5] Update Resources page in `src/pages/Resources.tsx` (category filter + list + detail)
- [X] T072 [P] [US5] Update Help page in `src/pages/Help.tsx` (FAQ accordion + search)

**Checkpoint**: US5 fully functional — Resources/Help show real content with search

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 收尾清理、Voice Mode 残留移除、quickstart 验证

- [X] T073 [P] Remove voice mode UI entries from interview setup page and related components in `src/pages/InterviewList.tsx`
- [X] T074 [P] Remove "Phase 6 上线" placeholder text from Settings tabs
- [ ] T075 [P] Remove voice mode option from `interview_sessions.mode` frontend enum (keep DB field, hide UI)
- [ ] T076 Run quickstart.md validation scenarios (S1-S7) to verify all endpoints work end-to-end
- [ ] T077 [P] Run all tests: `cd backend && uv run pytest tests/unit/ tests/integration/ -v`
- [ ] T078 [P] Run frontend tests: `cd frontend && npx vitest run && npx playwright test`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 — 账号生命周期 (Phase 3)**: Depends on Phase 2 — No dependencies on other stories
- **US2 — 数据导入导出 (Phase 4)**: Depends on Phase 2 — independent of US1/US3
- **US3 — 审计可观测 (Phase 5)**: Depends on Phase 2 — partially depends on US1 (audit lifecycle events → add audit decorator to lifecycle endpoints)
- **US4 — Settings tab (Phase 6)**: Depends on Phase 2 + US1 (SecurityTab links to 注销) + US2 (ExportTab links to 导出)
- **US5 — Resources/Help (Phase 7)**: Depends on Phase 2 — independent of all other stories
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Phase 2 → Start (MVP scope: just lifecycle)
- **US2 (P2)**: Phase 2 → Start (independent of US1)
- **US3 (P2)**: Phase 2 → Start (independent of US1/US2)
- **US4 (P2)**: Phase 2 + US1 + US2 → Start (wires to prior US endpoints)
- **US5 (P3)**: Phase 2 → Start (fully independent)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Story complete before moving to next priority

### Parallel Opportunities

- All Phase 1 [P] tasks can run in parallel (T002/T004/T005 are independent migrations)
- T007/T008/T009 are independent
- All test tasks within a story marked [P] can run in parallel
- US2 (backend), US3 (backend), and US5 (backend+frontend) can be implemented in parallel after Phase 2
- Frontend components within US4 (T056-T059) can all run in parallel
- Frontend components within US5 (T069-T072) can all run in parallel

---

## Parallel Example: Phase 3 (US1)

```bash
# Write all tests first (in parallel):
Task: T010 Unit test lifecycle status transitions
Task: T011 Unit test cancellation deadline
Task: T012 Integration test full lifecycle flow
# Then implementation (sequential):
Task: T015 Lifecycle service
Task: T016 Lifecycle endpoints
Task: T017-T018 ARQ cron tasks
```

## Parallel Example: Phase 4 + Phase 5 + Phase 7

```bash
# These phases are independent and can run in parallel after Phase 2:
# Dev A: US2 (export/import)
Task: T025 Export service
Task: T026 Import service
Task: T027 Export endpoints

# Dev B: US3 (audit)
Task: T036 Audit service
Task: T037 Audit middleware
Task: T038-T039 Audit endpoints

# Dev C: US5 (Resources/Help)
Task: T065 Content service
Task: T066 Content endpoints
Task: T067 Seed data
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (migrations + env config)
2. Complete Phase 2: Foundational (admin role + notification)
3. Complete Phase 3: US1 (lifecycle)
4. **STOP and VALIDATE**: Test US1 independently
5. Deploy/demo if ready — core account lifecycle is live

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (lifecycle) → Test independently → Deploy/Demo
3. Add US2 (export/import) → Test independently → Deploy
4. Add US3 (audit) → Test independently → Deploy
5. Add US4 (Settings) + US5 (Resources/Help) → Test → Deploy

### Parallel Team Strategy

With multiple developers:

1. Team completes Phase 1 + Phase 2 together
2. Once Phase 2 is done:
   - Developer A: US1 (lifecycle) — highest priority
   - Developer B: US3 (audit) — independent backend module
   - Developer C: US5 (Resources/Help) — independent full stack
3. After US1 done:
   - Developer A moves to US2 (export/import)
   - Developer B moves to US4 (Settings tab — backend)
   - Developer C continues with US5 (frontend)
4. All stories integrate independently

---

## Notes

- [P] tasks = different files, no dependencies — can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Constitution §III)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Voice mode is deferred — no voice-related tasks in Phase 6
- Total tasks: 78 (T001-T078)
