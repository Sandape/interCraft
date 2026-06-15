---
description: "Phase 2 (P1 entities) 任务列表 — M08/M09/M10/M11 + M23 P1.5 前端迁移"
---

# Tasks: InterCraft Phase 2 — P1 业务实体上线

**Input**: Design documents from `/specs/001-intercraft-product-spec/`
- Plan: [phase-2.md](./phase-2.md)
- Spec: [spec.md](./spec.md)
- Research: [research-phase-2.md](./research-phase-2.md)
- Data Model: [data-model-phase-2.md](./data-model-phase-2.md)
- Contracts: [contracts/README.md](./contracts/README.md)
- Quickstart: [quickstart-phase-2.md](./quickstart-phase-2.md)
- Phase 1 baseline tasks: [tasks.md](./tasks.md)(T001-T156 全部完成)

**Tests**: TDD 强制(Constitution III NON-NEGOTIABLE);**所有** user story 任务都先写测试 → 看红 → 签收 → 最小实现 → 重构。

**Organization**: 按 user story 分组(US5/US6/US8/US11/US4-partial),每组独立可演示、独立可测试。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 不同文件 / 无依赖 / 可并行
- **[Story]**: 任务归属 user story(US5/US6/US8/US11/US4);Setup/Foundational/Polish 阶段无标签
- 路径:后端在 `backend/app/...`、前端在 `src/...`、根配置 `.specify/...`

---

## Phase 1: Setup (Phase 2 基础设施)

**Purpose**: Phase 2 特有基础设施(沿用 Phase 1 基础设施,只扩不改)

- [X] T001 扩 `backend/app/core/pagination.py` + `backend/app/domain/pagination.py`:`CursorPage[T]` 泛型 + `encode_cursor` / `decode_cursor`(base64url JSON,DEC-P2-1)
- [X] T002 扩 `backend/app/domain/enums.py`:新增 `AbilityDimension / ErrorStatus / JobStatus / TaskType / TaskStatus / ActivityType / ActivityActor / InterviewStatus / InterviewMode` 9 个枚举(见 [data-model-phase-2.md §9](../specs/001-intercraft-product-spec/data-model-phase-2.md))
- [X] T003 创建 Alembic 迁移 `backend/migrations/versions/0002_phase2_entities.py` 一次性创建 7 张表(error_questions / ability_dimensions / ability_dimensions_history / tasks / activities / jobs / interview_sessions)+ 全部索引 + 全部 CHECK 约束 + RLS 启用 + 7 张表 user_isolation 策略(见 [data-model-phase-2.md §10-11](../specs/001-intercraft-product-spec/data-model-phase-2.md))
- [X] T004 [P] 创建 `backend/app/core/scheduler.py` + `backend/app/workers/tasks/monthly_quota_reset.py`:`async def monthly_quota_reset(ctx)` 函数 + ARQ cron 注册 `0 0 1 * *` UTC,容错窗口 00:00-00:05(澄清 Q1 决议 2026-06-13,DEC-P2-4)
- [X] T005 [P] 扩 `backend/app/repositories/base.py`:`async def find_or_create(session, **fields) -> T` 通用方法,实现 SELECT-then-INSERT + `IntegrityError` 兜底重试(供 tasks 模块使用)
- [X] T006 修改 `backend/app/main.py` + `backend/app/api/v1/__init__.py`:挂载 `/internal/*` 路由前缀 + `internal_ip_middleware` 校验 source IP = api 进程(127.0.0.1 / Docker network)
- [X] T007 [P] 修改 `backend/app/workers/main.py`:在 `WorkerSettings.cron_jobs` 列表注册 `monthly_quota_reset`(`name / cron / coroutine` 字段)

**Checkpoint**: 启动后端 + worker,验证 7 张表存在、cron 注册、pagination 工具可独立 import

---

## Phase 2: Foundational (Foundational Tasks)

**Purpose**: 跨 user story 的基础验证,完成后所有 US 可并行

- [X] T008 [P] 创建 `backend/tests/integration/test_cursor_parity.py` + `src/lib/__tests__/cursor.test.ts`:跨端游标编解码 parity 测试(DEC-P2-1)
- [X] T009 [P] 创建 `backend/tests/integration/test_rls_isolation_phase2.py`:7 张新表 2-user 互访 → 全部 404(RLS 强制空集,spec FR-004)
- [X] T010 [P] 创建 `backend/tests/integration/test_monthly_quota_reset.py`:手工调用 `monthly_quota_reset()` → 验证 `monthly_token_used=0, quota_reset_at=now()`(DEC-P2-4)
- [X] T011 [P] 扩 `backend/tests/contract/test_openapi_schema.py`:校验 7 个新模块所有端点存在 + 405/501 路由正确 + 必需 schema 字段(端点 23→30+)
- [X] T012 跑 `npm run gen:api` 重新生成 `src/api/schema.d.ts`(包含 Phase 2 端点)

**Checkpoint**: 后端 `pytest tests/integration/test_rls_isolation_phase2.py` + `test_monthly_quota_reset.py` 全绿,前端 `vitest src/lib/__tests__/cursor.test.ts` 全绿

---

## Phase 3: User Story 5 — 能力画像(P1) 🎯 Phase 2 P1

**Goal**: 6 维度能力画像只读 + 注册时 seed + 用户手动校正(spec US5 / FR-030~033 / 澄清 2026-06-13 §Clarifications)

**Independent Test**:
1. 注册新用户 → `GET /ability-dimensions` 返回 6 行(actual=0, ideal=10)
2. `PATCH /ability-dimensions/tech_depth` 改 sub_scores → 刷新页面仍可见
3. 禁用某维度 → 雷达图不展示该维度
4. 用户 A token 读 B 的 dimensions → 404

### Tests for User Story 5

- [X] T013 [P] [US5] 创建 `backend/tests/integration/test_abilities_read.py`:`GET /ability-dimensions` 返回 200 / 6 行 / 字段完整;空用户 `data: []`
- [X] T014 [P] [US5] 创建 `backend/tests/integration/test_abilities_seed.py`:注册成功后 6 维度自动 seed + `dimensions_meta` 端点返回 18 子项
- [X] T015 [P] [US5] 创建 `backend/tests/integration/test_abilities_toggle.py`:`POST /ability-dimensions/{key}/toggle` 切换 is_active
- [X] T016 [P] [US5] 创建 `backend/tests/integration/test_abilities_history.py`:`GET /ability-dimensions/history?aggregate=month` 时序数据(空用户返回 `[]`)
- [X] T017 [P] [US5] 创建 `backend/tests/integration/test_rls_isolation_abilities.py`:用户 A token 读 B 的 dimensions → 404

### Backend Implementation for User Story 5

- [X] T018 [P] [US5] 创建 `backend/app/modules/abilities/models.py`:`AbilityDimension` + `AbilityDimensionHistory` SQLAlchemy 模型(见 [data-model-phase-2.md §3-4](../specs/001-intercraft-product-spec/data-model-phase-2.md))
- [X] T019 [P] [US5] 创建 `backend/app/modules/abilities/schemas.py`:Pydantic In/Out/Patch schemas(6 维度 + 18 子项 + is_active toggle)
- [X] T020 [US5] 创建 `backend/app/modules/abilities/repository.py`:`AbilityDimensionRepository` 封装 CRUD + `seed_for_new_user(user_id)` 方法
- [X] T021 [US5] 创建 `backend/app/modules/abilities/service.py`:`AbilityService.read() / patch() / toggle() / history()` 业务逻辑(depends on T018, T019, T020)
- [X] T022 [US5] 创建 `backend/app/modules/abilities/api.py`:6 个端点(GET list / GET /{key} / PATCH /{key} / POST /{key}/toggle / GET /history / GET /dimensions-meta)
- [X] T023 [P] [US5] 创建 `backend/app/modules/abilities/cli.py`:`uv run python -m app.modules.abilities.cli --help` + `seed --user-id <uuid>` 子命令
- [X] T024 [P] [US5] 创建 `backend/app/modules/abilities/README.md`(库自描述)
- [X] T025 [US5] 修改 `backend/app/modules/auth/service.py`:`on_after_register(user_id)` 钩子调用 `AbilityService.seed_for_new_user(user_id)`(DEC-P2-2)

### Frontend Implementation for User Story 5

- [X] T026 [P] [US5] 创建 `src/repositories/__tests__/AbilityRepository.test.ts`:MSW handlers 覆盖 list / get / patch / toggle / history / dimensions-meta
- [X] T027 [US5] 创建 `src/repositories/AbilityRepository.ts`:6 方法对应后端 6 端点(depends on T026)
- [X] T028 [US5] 创建 `src/hooks/queries/useAbilities.ts`:React Query 包装 list + get,缓存 60s
- [X] T029 [P] [US5] 创建 `src/hooks/mutations/usePatchAbility.ts` + `useToggleAbility.ts`(depends on T027)
- [X] T030 [US5] 修改 `src/pages/Profile.tsx`:从 `mockData.ts` 切真实 API,渲染 6 维度雷达图(depends on T028, T029)

**Checkpoint**: 注册新用户 → /profile 显示 6 维度空态雷达图 → PATCH 校正 → 刷新持久化;VITE_USE_MOCK=false 走真实 API

---

## Phase 4: User Story 6 — 错题本(P2) 🎯 Phase 2 P2

**Goal**: 错题本手动 CRUD + 状态机推进(spec US6 / FR-040~043 / 澄清 Q4 决议 2026-06-13,Phase 2 无 AI,仅手动创建)

**Independent Test**:
1. 创建错题(可选 dimension)→ 列表出现
2. 状态推进 fresh → practicing → mastered,frequency 联动
3. 非法状态转换返回 409
4. reset mastered → fresh
5. 列表按维度/状态/频次筛选 + 排序

### Tests for User Story 6

- [X] T031 [P] [US6] 创建 `backend/tests/integration/test_error_questions_crud.py`:list / get / create / patch(改 status/frequency)/ archive(soft_delete)全流程
- [X] T032 [P] [US6] 创建 `backend/tests/integration/test_error_fsm.py`:状态机 `reduce_status()` 纯函数 + 非法转换 409(DEC-P2-5)
- [X] T033 [P] [US6] 创建 `backend/tests/integration/test_error_dimensions.py`:6 维度 enum 校验 + `dimension` 字段可空(POST null / POST 非法 enum → 422)
- [X] T034 [P] [US6] 创建 `backend/tests/integration/test_error_reset.py`:`POST /error-questions/{id}/reset` 行为(mastered → fresh, frequency 0 → 3)
- [X] T035 [P] [US6] 创建 `backend/tests/integration/test_rls_isolation_errors.py`:用户 A token 访问 B 的错题 → 404

### Backend Implementation for User Story 6

- [X] T036 [P] [US6] 创建 `backend/app/modules/errors/models.py`:`ErrorQuestion` SQLAlchemy 模型(见 [data-model-phase-2.md §2](../specs/001-intercraft-product-spec/data-model-phase-2.md))
- [X] T037 [P] [US6] 创建 `backend/app/modules/errors/schemas.py`:Pydantic In/Out/Patch
- [X] T038 [US6] 创建 `backend/app/modules/errors/repository.py`:`ErrorQuestionRepository` 封装 list(过滤 + 排序) / get / create / patch / soft_delete
- [X] T039 [US6] 创建 `backend/app/modules/errors/service.py`:`reduce_status(current, target, frequency)` 纯函数 + `ErrorService.crud()` 调用(depends on T036, T037, T038)
- [X] T040 [US6] 创建 `backend/app/modules/errors/api.py`:7 端点(GET list / POST / GET /{id} / PATCH /{id} / DELETE /{id} / POST /{id}/reset)
- [X] T041 [P] [US6] 创建 `backend/app/modules/errors/cli.py` + `app/modules/errors/README.md`

### Frontend Implementation for User Story 6

- [X] T042 [P] [US6] 创建 `src/repositories/__tests__/ErrorQuestionRepository.test.ts`:MSW 覆盖 7 端点
- [X] T043 [US6] 创建 `src/repositories/ErrorQuestionRepository.ts`
- [X] T044 [P] [US6] 创建 `src/hooks/queries/useErrorQuestions.ts` + `useErrorQuestion.ts`
- [X] T045 [P] [US6] 创建 `src/hooks/mutations/useCreateErrorQuestion.ts` + `useUpdateErrorQuestion.ts` + `useArchiveErrorQuestion.ts` + `useResetErrorQuestion.ts`
- [X] T046 [US6] 创建/修改 `src/pages/ErrorBook.tsx`:从 mockData 切真实 API,渲染列表 + 表单 + 状态机 UI(依赖 T042-T045)
- [X] T047 [P] [US6] 创建 `src/components/errors/StatusBadge.tsx` + `FrequencyBadge.tsx`(UI 组件,从 mockData 抽出便于测试)

**Checkpoint**: 创建错题 → 列表出现 → 状态推进 UI 联动 → 非法转换 Toast 报错

---

## Phase 5: User Story 8 — 求职追踪 + 任务 + 活动流(P2) 🎯 Phase 2 P2

**Goal**: Jobs 全 CRUD + 状态机触发任务(DEC-P2-6)+ Tasks 幂等(find_or_create,澄清 Q2 决议)+ Activities 游标分页(DEC-P2-1)

**Independent Test**:
1. 创建 Job → 状态默认 applied + 自动创建「准备 X 公司面试」任务 + 写 activity
2. 推进 applied → test → oa → hr → offer → 任务 title 持续更新
3. 推进 → rejected/withdrawn → 任务归档
4. 多次状态推进不创建重复任务(UNIQUE 约束)
5. 漏斗统计 `GET /jobs/stats` 正确
6. 活动流游标分页 forward-only
7. 用户 A token 访问 B 的 jobs → 404

### Tests for User Story 8 (Jobs)

- [X] T048 [P] [US8] 创建 `backend/tests/integration/test_jobs_lifecycle.py`:create → 状态推进 → 触发任务 → activities 写入 全流程
- [X] T049 [P] [US8] 创建 `backend/tests/integration/test_jobs_status_machine.py`:合法转换矩阵 + 非法转换 409(见 [contracts/jobs.md §8 状态机](../specs/001-intercraft-product-spec/contracts/jobs.md))
- [X] T050 [P] [US8] 创建 `backend/tests/integration/test_jobs_stats.py`:`GET /jobs/stats` 各 status 计数 + total
- [X] T051 [P] [US8] 创建 `backend/tests/integration/test_jobs_timeline.py`:`GET /jobs/{id}/timeline` 返回 status_history
- [X] T052 [P] [US8] 创建 `backend/tests/integration/test_rls_isolation_jobs.py`:跨用户 → 404

### Backend Implementation for User Story 8 (Jobs)

- [X] T053 [P] [US8] 创建 `backend/app/modules/jobs/models.py`:`Job` SQLAlchemy 模型(见 [data-model-phase-2.md §7](../specs/001-intercraft-product-spec/data-model-phase-2.md))
- [X] T054 [P] [US8] 创建 `backend/app/modules/jobs/schemas.py`:Pydantic In/Out/Patch/UpdateStatus
- [X] T055 [US8] 创建 `backend/app/modules/jobs/repository.py`:`JobRepository` 封装 list / get / create / patch / update_status(状态机校验)
- [X] T056 [US8] 创建 `backend/app/modules/jobs/service.py`:`JobService.update_status()` 内部调 `TaskService.find_or_create(user_id, 'interview_prep', job.id, "准备 {company} · {position} 面试 · {new_status_cn}")`(DEC-P2-6)
- [X] T057 [US8] 创建 `backend/app/modules/jobs/api.py`:8 端点(GET list / POST / GET /{id} / PATCH /{id} / PATCH /{id}/status / DELETE /{id} / GET /stats / GET /{id}/timeline)
- [X] T058 [P] [US8] 创建 `backend/app/modules/jobs/cli.py` + `app/modules/jobs/README.md`

### Tests for User Story 8 (Tasks + Activities)

- [X] T059 [P] [US8] 创建 `backend/tests/integration/test_task_dedup.py`:相同 `(user_id, type, related_entity_id)` 二次创建不重复(find_or_create,DEC-P2-3)
- [X] T060 [P] [US8] 创建 `backend/tests/integration/test_task_unique_constraint.py`:DB `UNIQUE (user_id, type, related_entity_id)` 触发 `IntegrityError` → 409
- [X] T061 [P] [US8] 创建 `backend/tests/integration/test_activities_pagination.py`:游标分页 forward-only / cursor opaque base64 / limit 1-50
- [X] T062 [P] [US8] 创建 `backend/tests/integration/test_rls_isolation_tasks_activities.py`:跨用户 → 404

### Backend Implementation for User Story 8 (Tasks + Activities)

- [X] T063 [P] [US8] 创建 `backend/app/modules/tasks/models.py`:`Task` SQLAlchemy 模型 + `UNIQUE (user_id, type, related_entity_id) WHERE related_entity_id IS NOT NULL` 索引
- [X] T064 [P] [US8] 创建 `backend/app/modules/tasks/schemas.py` + `backend/app/modules/activities/models.py` + `schemas.py`
- [X] T065 [US8] 创建 `backend/app/modules/tasks/repository.py` + `backend/app/modules/tasks/service.py`:`TaskService.find_or_create()` + `crud()`(depends on T063, T064)
- [X] T066 [US8] 创建 `backend/app/modules/tasks/api.py`:6 端点(GET list / POST / GET /{id} / PATCH /{id} / DELETE /{id})+ 内部 `POST /internal/tasks/find-or-create`
- [X] T067 [P] [US8] 创建 `backend/app/modules/tasks/cli.py` + `app/modules/tasks/README.md` + 占位 `triggers.py`
- [X] T068 [US8] 创建 `backend/app/modules/activities/repository.py` + `backend/app/modules/activities/service.py`:`encode_cursor` / `decode_cursor` + 游标查询
- [X] T069 [US8] 创建 `backend/app/modules/activities/api.py`:1 公开端点(`GET /activities`)+ 1 内部端点(`POST /internal/activities/log`)
- [X] T070 [P] [US8] 创建 `backend/app/modules/activities/cli.py` + `app/modules/activities/README.md`

### Frontend Implementation for User Story 8 (Jobs + Tasks + Activities)

- [X] T071 [P] [US8] 创建 `src/repositories/__tests__/JobRepository.test.ts` + `TaskRepository.test.ts` + `ActivityRepository.test.ts`(MSW 三件套)
- [X] T072 [P] [US8] 创建 `src/repositories/JobRepository.ts` + `TaskRepository.ts` + `ActivityRepository.ts`
- [X] T073 [P] [US8] 创建 `src/hooks/queries/useJobs.ts` + `useTasks.ts` + `useActivities.ts` + `useJobStats.ts`
- [X] T074 [P] [US8] 创建 `src/hooks/mutations/useCreateJob.ts` + `useUpdateJobStatus.ts` + `useUpdateTaskStatus.ts`
- [X] T075 [US8] 修改 `src/pages/Jobs.tsx`:从 mockData 切真实 API,渲染列表 + 漏斗 + 状态推进 UI(depends on T071-T074)
- [X] T076 [P] [US8] 创建 `src/components/jobs/StatusBadge.tsx` + `JobTimeline.tsx` + `FunnelChart.tsx`(UI 组件)
- [X] T077 [P] [US8] 创建 `src/components/tasks/TaskList.tsx` + `TaskStatusChip.tsx`(UI 组件,Phase 5 Dashboard 复用)

**Checkpoint**: 创建 Job → 自动任务出现 → 状态推进 → 漏斗 + 时间线正确;活动流游标翻页 OK

---

## Phase 6: User Story 11 — 设置(资料 tab)(P2) 🎯 Phase 2 P2

**Goal**: Settings「资料」tab 从 mock 切真实 API(澄清 Q5 决议 2026-06-13);其他 tab 留 mock 等待 Phase 6 迁移

**Independent Test**:
1. 访问 /settings → 切到「资料」tab → 显示 4 字段当前值
2. 修改 4 字段 → 保存 → 刷新仍可见
3. 试图改 email / subscription → 422
4. 其他 tab(设备/订阅/安全)仍为 mock,显示「Phase 6 上线」占位

### Tests for User Story 11

- [X] T078 [P] [US11] 创建 `backend/tests/integration/test_settings_profile_update.py`:`PATCH /users/me` 4 字段成功 + 非法字段(email / subscription)422
- [X] T079 [P] [US11] 创建 `src/hooks/mutations/__tests__/useUpdateProfile.test.ts`

### Backend Implementation for User Story 11

- [X] T080 [US11] 修改 `backend/app/modules/auth/schemas.py`:`PatchUser` schema 限定 4 字段(`display_name / title / years_of_experience / target_role`),email / subscription 字段移除
- [X] T081 [US11] 修改 `backend/app/modules/auth/api.py`:`PATCH /users/me` 端点验证 4 字段范围(R-7:length 校验,DEC-P2-7)

### Frontend Implementation for User Story 11

- [X] T082 [US11] 创建 `src/hooks/mutations/useUpdateProfile.ts`:React Query mutation 包装 PATCH /users/me(depends on T079)
- [X] T083 [P] [US11] 创建 `src/components/settings/ProfileTab.tsx`:从 Settings.tsx 抽出的「资料」tab 组件
- [X] T084 [US11] 修改 `src/pages/Settings.tsx`:仅「资料」tab 切真实 API,其他 tab(设备/订阅/安全)显示「Phase 6 上线」占位(depends on T082, T083)

**Checkpoint**: /settings 资料 tab 4 字段 PATCH 成功 + 刷新持久化;其他 tab 保持 mock

---

## Phase 7: User Story 4 partial — M11 面试历史只读骨架

**Goal**: 面试会话表落地 + list/get 读 API + 显式 405/501(澄清 Q3 决议 2026-06-13);Phase 4 M15 Agent 启动时补 create/update

**Independent Test**:
1. `GET /interview-sessions` 返回 200 + 数据(可能为空)
2. `GET /interview-sessions/{id}` 返回详情 / 404
3. `POST /interview-sessions` 返回 405 + `Allow: GET`
4. `POST /internal/interview-sessions` 返回 501(占位)
5. 跨用户 → 404

### Tests for User Story 4 (M11 partial)

- [X] T085 [P] [US4] 创建 `backend/tests/integration/test_interview_sessions_read.py`:`GET /interview-sessions` / `GET /interview-sessions/{id}` + 空态
- [X] T086 [P] [US4] 创建 `backend/tests/integration/test_interview_sessions_405.py`:POST / PATCH / DELETE 全部 405
- [X] T087 [P] [US4] 创建 `backend/tests/integration/test_interview_sessions_internal_501.py`:`POST /internal/interview-sessions` 501
- [X] T088 [P] [US4] 创建 `backend/tests/integration/test_rls_isolation_interview_sessions.py`:跨用户 → 404

### Backend Implementation for User Story 4 (M11 partial)

- [X] T089 [P] [US4] 创建 `backend/app/modules/interviews/models.py`:`InterviewSession` SQLAlchemy 模型(见 [data-model-phase-2.md §8](../specs/001-intercraft-product-spec/data-model-phase-2.md),thread_id 列占位 NULL)
- [X] T090 [P] [US4] 创建 `backend/app/modules/interviews/schemas.py`:Pydantic Out(只读)
- [X] T091 [US4] 创建 `backend/app/modules/interviews/repository.py`:`InterviewSessionRepository.list() / get()`,无 create/update/delete
- [X] T092 [US4] 创建 `backend/app/modules/interviews/service.py` + `app/modules/interviews/api.py`:`GET /interview-sessions` + `GET /interview-sessions/{id}` + `POST /internal/interview-sessions` 501 占位
- [X] T093 [P] [US4] 创建 `backend/app/modules/interviews/cli.py` + `app/modules/interviews/README.md`

### Frontend Implementation for User Story 4 (M11 partial,只读骨架)

- [X] T094 [P] [US4] 创建 `src/repositories/__tests__/InterviewSessionRepository.test.ts`
- [X] T095 [US4] 创建 `src/repositories/InterviewSessionRepository.ts`
- [X] T096 [P] [US4] 创建 `src/hooks/queries/useInterviewSessions.ts`

**Checkpoint**: 2 公开端点 200,POST/PATCH/DELETE 405,内部 501;前端 InterviewList 仍读 mockData(Phase 4 迁移)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: E2E + 跨切面 + 文档

- [X] T097 [P] 创建 `tests/e2e/phase2/profile-from-api.spec.ts`:Playwright 走真实后端,验证 Profile 雷达图从 API 渲染
- [X] T098 [P] 创建 `tests/e2e/phase2/jobs-from-api.spec.ts`:Jobs 创建 → 状态推进 → 任务自动出现
- [X] T099 [P] 创建 `tests/e2e/phase2/errorbook-from-api.spec.ts`:错题 CRUD + 状态机
- [X] T100 [P] 创建 `tests/e2e/phase2/settings-profile-tab.spec.ts`:Settings 资料 tab PATCH
- [X] T101 [P] 创建 `tests/e2e/phase2/abilities-toggle.spec.ts`:维度禁用 → 雷达图隐藏
- [X] T102 [P] 创建 `tests/e2e/phase2/activities-pagination.spec.ts`:游标翻页 + has_more 正确
- [X] T103 [P] 创建 `tests/e2e/phase2/cursor-parity.spec.ts`:跨端 cursor 编码一致
- [X] T104 [P] 创建 `tests/e2e/phase2/rls-isolation-phase2.spec.ts`:7 张表 2-user 互访 → 404
- [X] T105 [P] 创建 `scripts/check-task-dedup.mjs` + `scripts/check-error-fsm.mjs` + `scripts/check-ability-normalize.mjs`:前端核心逻辑 CLI 验证(Constitution II)
- [X] T106 [P] 创建 `backend/app/modules/jobs/cli.py`:`replay` 子命令(从 fixture 重放幂等场景,Constitution V Observability)
- [X] T107 [P] 创建 `docs/PHASE2_RELEASE_NOTES.md`:Phase 2 演示场景 + 验收清单 + 与 Phase 1 差异 + 风险回顾
- [X] T108 [P] 验证 VITE_USE_MOCK=true 回归:Profile / Jobs / ErrorBook / Settings 资料 tab 仍可走 mock,无后端依赖
- [X] T109 [P] 走 [quickstart-phase-2.md](./quickstart-phase-2.md) §0-§3 全 8 场景 + 录屏脚本
- [X] T110 [P] 更新 `docs/modules/08-error-book.md` / `09-ability-profile.md` / `10-task-activity.md` / `11-interview-history.md`:补 Phase 2 决议引用(澄清 2026-06-13 决议)
- [X] T111 [P] Constitution v1.0.0 Phase 2 Re-evaluation:逐条校验 5 原则,无新违规则 `phase-2-done.md` 总结

**Checkpoint**: Phase 2 入口验收(三个页面在 `VITE_USE_MOCK=false` 下完全可用)+ E2E 套件全绿 + 文档齐备

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖,可立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1,完成才解锁所有 US
- **Phase 3-7 (US5 / US6 / US8 / US11 / US4)**: 依赖 Phase 2;US 间相互独立可并行
  - US8 内部顺序:Jobs 端点 → Tasks 触发 → Activities 写入(强依赖)
  - US11 强依赖 Phase 1 auth(api.py 改 PATCH /users/me 字段)
  - US4 partial 独立,无跨 US 依赖
- **Phase 8 (Polish)**: 依赖 Phase 3-7 全部完成

### User Story Dependencies

- **US5 (P1)**: Phase 1 完成后可独立
- **US6 (P2)**: Phase 1 完成后可独立
- **US8 (P2)**: Phase 1 完成后可独立;Jobs 创建需 TaskService.find_or_create 可用(同 Phase 5)
- **US11 (P2)**: 强依赖 Phase 1 auth(改 PATCH /users/me)
- **US4 partial (P1)**: Phase 1 完成后可独立(无跨 US 依赖,Phase 4 M15 时再激活)

### Within Each User Story

- **Tests MUST FAIL first**(Constitution III)
- Backend 顺序:tests → models → schemas → repository → service → api → cli/README
- Frontend 顺序:tests → repository → hooks(queries + mutations)→ pages
- 同模块内多文件(API+Service+Repo)可顺序;不同模块 [P] 标记

### Parallel Opportunities

- Phase 1: T001/T002/T003/T004/T005/T006/T007 全部 [P]
- Phase 2: T008/T009/T010/T011 全部 [P];T012 在前 4 个完成后
- Phase 3 (US5): T013-T017 tests 全 [P];T018-T020 models/schemas [P];T021-T024 service+api+cli+readme 跨文件 [P];T026/T028 [P];T030 末位
- Phase 4 (US6): T031-T035 tests [P];T036-T037 models/schemas [P];T041 cli/readme [P]
- Phase 5 (US8): T048-T052 jobs tests [P];T053-T054 models/schemas [P];T058 cli/readme [P];T059-T062 tasks/activities tests [P];T063-T064 models/schemas [P];T067 cli/readme [P];T070 cli/readme [P];T071-T072 repos [P];T073-T074 hooks [P]
- Phase 6 (US11): T078-T079 tests [P];T080-T081 backend 顺序;T082-T083 frontend [P]
- Phase 7 (US4): T085-T088 tests [P];T089-T090 models/schemas [P];T093 cli/readme [P]
- Phase 8: T097-T104 E2E 8 个 [P];T105-T111 polish 7 个 [P]

---

## Parallel Example: User Story 5 (Phase 3)

```bash
# Launch all US5 contract + integration tests in parallel (must FAIL first):
Task T013: backend/tests/integration/test_abilities_read.py
Task T014: backend/tests/integration/test_abilities_seed.py
Task T015: backend/tests/integration/test_abilities_toggle.py
Task T016: backend/tests/integration/test_abilities_history.py
Task T017: backend/tests/integration/test_rls_isolation_abilities.py

# Then models + schemas in parallel (different files):
Task T018: backend/app/modules/abilities/models.py
Task T019: backend/app/modules/abilities/schemas.py

# Then repository + service + api (sequential within module):
Task T020: backend/app/modules/abilities/repository.py (depends on T018)
Task T021: backend/app/modules/abilities/service.py (depends on T018, T019, T020)
Task T022: backend/app/modules/abilities/api.py (depends on T021)

# CLI + README in parallel:
Task T023: backend/app/modules/abilities/cli.py
Task T024: backend/app/modules/abilities/README.md

# Frontend can fully parallel:
Task T026: src/repositories/__tests__/AbilityRepository.test.ts
Task T028: src/hooks/queries/useAbilities.ts
Task T029: src/hooks/mutations/usePatchAbility.ts + useToggleAbility.ts
```

---

## Parallel Example: User Story 8 (Phase 5, 跨模块)

```bash
# All US8 backend tests in parallel (must FAIL first):
Task T048: test_jobs_lifecycle.py
Task T049: test_jobs_status_machine.py
Task T050: test_jobs_stats.py
Task T051: test_jobs_timeline.py
Task T052: test_rls_isolation_jobs.py
Task T059: test_task_dedup.py
Task T060: test_task_unique_constraint.py
Task T061: test_activities_pagination.py
Task T062: test_rls_isolation_tasks_activities.py

# Models across 3 modules in parallel (different files):
Task T053: backend/app/modules/jobs/models.py
Task T063: backend/app/modules/tasks/models.py
Task T064: backend/app/modules/activities/models.py (combined with schemas)

# Schemas in parallel:
Task T054: jobs/schemas.py
# (tasks/activities schemas in T064)

# Service + repository depend on models (per module):
Task T055: jobs/repository.py
Task T056: jobs/service.py (uses TaskService.find_or_create from T065)
Task T065: tasks/repository.py + service.py
Task T068: activities/repository.py + service.py
Task T057: jobs/api.py (depends on T055, T056)
Task T066: tasks/api.py
Task T069: activities/api.py

# CLI + README in parallel:
Task T058: jobs/cli.py + README.md
Task T067: tasks/cli.py + README.md + triggers.py
Task T070: activities/cli.py + README.md

# Frontend in parallel:
Task T071: 3 个 Repository test 文件
Task T072: 3 个 Repository 文件
Task T073: 4 个 hooks(queries)
Task T074: 3 个 hooks(mutations)
Task T075: pages/Jobs.tsx
```

---

## Implementation Strategy

### MVP First (US5 + US6 only)

1. **Phase 1 (T001-T007)**: Setup — 1 周
2. **Phase 2 (T008-T012)**: Foundational — 0.5 周
3. **Phase 3 (US5) + Phase 4 (US6)**: 1.5-2 周
4. **STOP and VALIDATE**: 注册新用户 → Profile 雷达图 + 错题本 CRUD 可走通
5. Deploy/demo(无 Jobs / Settings 迁移,Dashboard 仍 mock)

### Incremental Delivery (推荐路径)

1. **Phase 1+2** → Setup + Foundational(0.5-1 周)
2. **+ Phase 3 (US5)** → Ability dimensions 演示(0.5 周)
3. **+ Phase 4 (US6)** → 错题本演示(0.5 周)
4. **+ Phase 5 (US8)** → Jobs + Tasks + Activities 演示(1 周;**Phase 2 入口验收通过**)
5. **+ Phase 6 (US11)** → Settings 资料 tab(0.5 周)
6. **+ Phase 7 (US4 partial)** → M11 只读骨架(0.5 周)
7. **+ Phase 8** → E2E + Polish + 录屏(0.5 周)

### Parallel Team Strategy

- **Week 1**: Phase 1+2(whole team)
- **Week 2**: Split:
  - Dev A: Phase 3 (US5) backend + frontend
  - Dev B: Phase 4 (US6) backend + frontend
  - Dev C: Phase 5 (US8 Jobs) backend
- **Week 3**: Split:
  - Dev A: Phase 5 (US8 Tasks/Activities) backend + frontend
  - Dev B: Phase 6 (US11) + Phase 7 (US4) backend
  - Dev C: Phase 8 (E2E + Polish) — 持续
- **Week 4**: Integration + 录屏 + release

---

## Notes

- `[P]` = 不同文件 / 无依赖;同模块内(API 依赖 service)不可 [P]
- `[Story]` 标签 = US5/US6/US8/US11/US4(partial);Setup/Foundational/Polish 无标签
- **测试 MUST 先红后绿**(Constitution III 强制)
- **RLS 是安全边界** — 任何跨表查询都走 `get_db_session(user_id=...)`;T009 + T052 + T062 + T088 必须绿
- **无 mock in test suite**(Constitution IV)— 后端集成用真实 Postgres/Redis;前端 E2E 用真实后端;`VITE_USE_MOCK=true` 仅 dev fallback
- **Phase 2 显式禁止引入**(grep 关键词 = 退审):`langgraph / langchain-anthropic / ai_messages / checkpoints / langsmith / dexie / i18n 库 / OAuth 真实实现 / 悲观锁 / Outbox / WS 业务端点`
- **Phase 2 显式不做**:`POST/PATCH/DELETE /interview-sessions` (405)、`POST /internal/interview-sessions` (501,Phase 4 M15 启用)、WS 业务端点、Outbox 重放
- **Commit cadence**: 每个 task 或逻辑组提交一次;phase 边界 PR
- **Stop at any checkpoint** 验证 US 独立可演示后再继续
- See [quickstart-phase-2.md](./quickstart-phase-2.md) §3 入口验收清单
- See [phase-2.md](./phase-2.md) §「Constitution Check」Phase 2 Re-evaluation
