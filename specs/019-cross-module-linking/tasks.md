---
description: "Feature 019 — Cross-Module Linking 任务列表 (Job ↔ Resume ↔ Interview, Interview → Error Book)"
---

# Tasks: Cross-Module Linking (Job ↔ Resume ↔ Interview, Interview → Error Book)

**Input**: Design documents from `/specs/019-cross-module-linking/`
- Plan: [plan.md](./plan.md)
- Spec: [spec.md](./spec.md)
- Research: [research.md](./research.md)
- Data Model: [data-model.md](./data-model.md)
- Contracts: [contracts/](./contracts/)
  - [jobs-fields.md](./contracts/jobs-fields.md)
  - [interview-job-id.md](./contracts/interview-job-id.md)
  - [error-questions-source.md](./contracts/error-questions-source.md)
  - [requirements-md-prompt.md](./contracts/requirements-md-prompt.md)
- Quickstart: [quickstart.md](./quickstart.md)

**Scope**: 019 增量联动层(Job 5 字段 / Job→Resume 双向入口 / Job→Interview 入口 / Interview→ErrorBook 自动沉淀 / Ability Profile 链路确认);US1 / US2 / US3 / US4(P1),US5(P2 E2E)。
**User Stories**: US1(登记完整岗位信息) / US2(从岗位创建简历分支) / US3(从岗位开始模拟面试) / US4(模拟面试自动沉淀错题)— P1;US5(端到端联动冒烟)— P2。

**Tests**: TDD 强制(Constitution III NON-NEGOTIABLE);所有 user story 任务都先写测试 → 看红 → 签收 → 最小实现 → 重构。

**Inherited baselines**:
- 014 Job Tracking(已交付,本 SPEC 仅扩字段与 CTA,不重写)
- 016 Error Book Completion(已交付,本 SPEC 复用 DELETE 端点)
- 006 Personal Ability Profile(已交付,本 SPEC 仅在数据冒烟上验证)
- Phase 4 Interview Agent(已交付,本 SPEC 扩 question_gen prompt 与 score 节点 hook)
- Phase 3 outbox(已交付,本 SPEC 沿用)

**Local Environment Constraints** (inherited):
- Redis 7: ✅ 本机 `localhost:6379`
- PostgreSQL 15: ✅ 在线 DB(沿用 Phase 1)
- DeepSeek API key: ✅ `backend/.env`
- `dbq.py`: ✅ `backend/scripts/dbq.py`

**Format**: `[ID] [P?] [Story] Description`
- **[P]**: 不同文件 / 无依赖 / 可并行
- **[Story]**: 任务归属 user story(US1-US5);Setup/Foundational/Polish 阶段无标签
- 路径:后端在 `backend/app/...`、前端在 `src/...`、测试在 `backend/tests/...` / `tests/...`

---

## Phase 1: Setup(019 前置检查与工具)

**Purpose**: 验证 019 前置条件(014 / 016 / 006 / Phase 4 已就位);不引入新依赖,只做基线检查。

- [ ] T001 [P] Verify deepseek & db config in `backend/.env`:`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` / `MONTHLY_TOKEN_QUOTA`;run `cd backend && uv sync`;confirm `python -c "from app.main import app"` 无报错
- [ ] T002 [P] Verify dbq.py works:run `python backend/scripts/dbq.py --query "SELECT 1"` 期望返回 1 行;若失败则 `pip install -r backend/scripts/requirements.txt`
- [ ] T003 [P] Verify 014 / 016 / 006 / Phase 4 baselines pass:run `cd backend && pytest tests/ -k "jobs or errors or ability or interview or agent" -q` 期望既有测试 0 失败;若失败则排查依赖或回滚至上一稳定 commit
- [ ] T004 [P] Verify frontend baselines:run `cd frontend && npm run test` 期望所有 vitest 通过;`npm run build` 无 typecheck 错误
- [ ] T005 [P] Run dbq column existence check before migrations:
  ```sql
  -- 在 dbq.py 跑
  SELECT column_name FROM information_schema.columns
  WHERE table_name='interview_sessions' AND column_name='job_id';
  -- 期望:0 行
  SELECT column_name FROM information_schema.columns
  WHERE table_name='error_questions' AND column_name='source_question_id';
  -- 期望:0 行
  SELECT column_name FROM information_schema.columns
  WHERE table_name='jobs' AND column_name IN ('base_location','requirements_md','employment_type','salary_range_text','headcount');
  -- 期望:0 行
  ```
  若任一列已存在,在 PR description 中说明(可能需改名或复用,见 plan.md R1 / data-model.md §2)

**Checkpoint**: 019 前置条件全部就绪;可进入 Foundational 阶段

---

## Phase 2: Foundational(3 alembic 迁移 + 后端 schema 扩展)

**Purpose**: 3 个迁移 + 后端 Pydantic / SQLAlchemy 模型扩展,**零业务逻辑变更**;保证 014 / 016 / Phase 4 既有测试零回归。所有 User Story 的阻塞前置。

### T006-T010:3 个 alembic 迁移(可并行)

- [ ] T006 [P] Create alembic migration `backend/alembic/versions/019_job_fields.py` per [data-model.md §1](./data-model.md):
  - `op.add_column('jobs', sa.Column('base_location', sa.Text(), nullable=False, server_default=''))`
  - `op.add_column('jobs', sa.Column('requirements_md', sa.Text(), nullable=True))`
  - `op.add_column('jobs', sa.Column('employment_type', sa.Text(), nullable=False, server_default='unspecified'))`
  - `op.add_column('jobs', sa.Column('salary_range_text', sa.Text(), nullable=True))`
  - `op.add_column('jobs', sa.Column('headcount', sa.Integer(), nullable=True))`
  - down-migration: `op.drop_column(...)` × 5
- [ ] T007 [P] Create alembic migration `backend/alembic/versions/019_interview_job_id.py` per [data-model.md §2](./data-model.md):
  - `op.execute("ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS job_id UUID REFERENCES jobs(id) ON DELETE SET NULL")`
  - `op.create_index('interview_sessions_job_id_idx', 'interview_sessions', ['job_id'])`
  - down-migration:`op.drop_index(...)` + `op.drop_column(...)`
  - 校验前置 T005 通过(列不存在)
- [ ] T008 [P] Create alembic migration `backend/alembic/versions/019_error_source_question_id.py` per [data-model.md §3](./data-model.md):
  - `op.execute("ALTER TABLE error_questions ADD COLUMN IF NOT EXISTS source_question_id UUID REFERENCES interview_questions(id) ON DELETE SET NULL")`
  - `op.create_index('error_questions_source_question_id_idx', 'error_questions', ['source_question_id'])`
  - 部分唯一索引:`op.execute("CREATE UNIQUE INDEX error_questions_source_question_id_uidx ON error_questions (source_question_id) WHERE source_question_id IS NOT NULL")`
  - down-migration:部分唯一索引 DROP + 索引 DROP + 列 DROP
  - 校验前置 T005 通过(列不存在)
- [ ] T009 Run `cd backend && bash scripts/db_migrate.sh` 验证 3 迁移顺序跑通;若失败则 `alembic downgrade -1` 回滚到上一个 head 排查
- [ ] T010 Run `dbq.py` post-migration column existence check:
  ```sql
  -- 5 + 1 + 1 列全部存在
  SELECT column_name FROM information_schema.columns
  WHERE table_name='jobs' AND column_name IN ('base_location','requirements_md','employment_type','salary_range_text','headcount');
  -- 期望:5 行
  ```

### T011-T016:后端 Pydantic / SQLAlchemy 模型扩展(可并行)

- [ ] T011 [P] Extend `backend/app/modules/jobs/models.py` `Job` class:加 5 列 mapped_column(base_location / requirements_md / employment_type / salary_range_text / headcount);不修改既有列
- [ ] T012 [P] Extend `backend/app/modules/jobs/schemas.py`:
  - `CreateJobInput`:加 5 字段(base_location Field(default=None, max_length=50) / requirements_md Field(default=None, max_length=5000) / employment_type Literal["internship","campus","experienced","contract","unspecified"] = "unspecified" / salary_range_text Field(default=None, max_length=100) / headcount Field(default=None, ge=1))
  - `PatchJobInput`:加 5 字段(全部 Optional)
  - `JobOut` + `JobListOut`:加 5 字段输出
  - 见 [contracts/jobs-fields.md](./contracts/jobs-fields.md)
- [ ] T013 [P] Extend `backend/app/modules/interviews/models.py` `InterviewSession` class:加 `job_id: Mapped[UUID | None]` mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
- [ ] T014 [P] Extend `backend/app/modules/interviews/schemas.py`:
  - `InterviewSessionCreate`:加 `job_id: UUID | None = None`
  - `InterviewSessionOut` + `InterviewSessionStartOut` + `InterviewSessionListOut`:加 `job_id` 字段输出
  - 见 [contracts/interview-job-id.md](./contracts/interview-job-id.md)
- [ ] T015 [P] Extend `backend/app/modules/errors/models.py` `ErrorQuestion` class:加 `source_question_id: Mapped[UUID | None]` mapped_column(ForeignKey("interview_questions.id", ondelete="SET NULL"), nullable=True)
- [ ] T016 [P] Extend `backend/app/modules/errors/schemas.py`:
  - `ErrorQuestionOut`:加 `source_question_id: UUID | None = None`
  - `ErrorQuestionListOut`:接受 `source: Literal["auto","manual","all"] = "all"` Query 参数
  - 见 [contracts/error-questions-source.md §3](./contracts/error-questions-source.md)

### T017:集成测试(迁移前后兼容性)

- [ ] T017 Create `backend/tests/integration/test_019_alembic_migrations.py`:
  - test_migration_019_job_fields_adds_5_columns:起真实 PostgreSQL fixture,up-migrate → 校验 5 列存在 + 默认值 + down-migrate → 校验 5 列被 DROP
  - test_migration_019_interview_job_id_adds_column_with_fk:同上,校验 FK + 索引 + ON DELETE SET NULL
  - test_migration_019_error_source_question_id_adds_column_with_partial_unique:校验部分唯一索引 + IF NOT EXISTS 兼容已存在
  - test_migrations_idempotent:up + up 两次不报错(IF NOT EXISTS 保证)

**Checkpoint**: 3 个迁移跑通;后端 schema 扩展完毕;既有 014 / 016 / Phase 4 测试零回归;可进入 User Story 阶段

---

## Phase 3: User Story 1 — 登记完整岗位信息(P1)🎯 MVP

**Goal**: 用户在「添加职位」弹窗填完整岗位信息(base_location / requirements_md / employment_type / salary_range_text / headcount),保存后 Job 详情面板看到这些字段;后续 US2 / US3 / US4 都依赖这些字段。

**Independent Test**: 在 `/jobs` 新建一个 job,填 base_location=北京 / requirements_md=200 字 / employment_type=experienced,保存后刷新,详情面板显示这三项;再次打开编辑,字段值保留。详细步骤见 [quickstart.md §2](./quickstart.md)。

### Tests(先写测试 → 看红 → 签收 → 最小实现)

- [ ] T018 [P] [US1] Create `backend/tests/unit/test_jobs_extended_fields.py` — unit tests for Pydantic schemas per [contracts/jobs-fields.md §5](./contracts/jobs-fields.md):
  - test_create_job_minimal_uses_defaults:只填 company+position,期望 5 字段默认值入库
  - test_create_job_with_all_5_fields_succeeds
  - test_base_location_over_50_chars_rejected(422)
  - test_requirements_md_over_5000_chars_rejected(422)
  - test_employment_type_invalid_value_rejected(422)
  - test_salary_range_text_over_100_chars_rejected(422)
  - test_headcount_zero_or_negative_rejected(422)
  - test_patch_job_partial_updates_5_fields
  - test_job_out_includes_5_fields
- [ ] T019 [P] [US1] Create `tests/unit/JobsDetailPanel.test.tsx` per [contracts/jobs-fields.md §6](./contracts/jobs-fields.md):
  - test_renders_5_fields_with_proper_chinese_labels:base_location / 招聘需求 / 岗位类型 / 薪资范围 / 招聘人数
  - test_renders_default_placeholders:base_location="" → "未填写", employment_type="unspecified" → "未指定"
  - test_requirements_md_foldable_card_with_markdown_render

### Implementation(最小实现)

- [ ] T020 [US1] Implement Pydantic schema in `backend/app/modules/jobs/schemas.py` per T018 测试用例(spec.md FR-002)
- [ ] T021 [P] [US1] Implement `backend/app/modules/jobs/api.py` / `repository.py` 字段透传(创建 / 列表 / 详情 / PATCH 全部接受 5 字段)
- [ ] T022 [P] [US1] Implement `src/pages/Jobs/CreateDrawer.tsx`:加 5 字段输入控件(文本 / Markdown textarea / 下拉枚举 / 数字)+ 字符计数(spec.md FR-004)
- [ ] T023 [P] [US1] Implement `src/pages/Jobs/EditDrawer.tsx`:加 5 字段编辑(沿用 014 既有 PATCH outbox 流程)
- [ ] T024 [P] [US1] Implement `src/pages/Jobs/DetailPanel.tsx`:基本信息区按"base 地 / 招聘需求(折叠) / 岗位类型 / 薪资范围 / headcount"顺序展示 5 字段(spec.md FR-003)

**Checkpoint**: pytest `test_jobs_extended_fields.py` 9 通过;npm `JobsDetailPanel.test.tsx` 3 通过;Playwright 手动跑既有 014 测试零回归

---

## Phase 4: User Story 2 — 从岗位创建简历分支(P1)

**Goal**: Job 详情面板新增「为该岗位创建简历分支」CTA,Topbar「新建简历」下拉新增「基于岗位创建」,预填 name/company/position,自动回填 jobs.branch_id。

**Independent Test**: 在一个 branch_id IS NULL 的 job 上点 CTA,验证:跳转 /resume/{newId}?source_job_id={jobId}、分支编辑器显示预填的 name / company / position、招聘需求折叠卡片可见、保存分支后 /jobs 详情面板的「绑定的简历分支」字段由"(无)"变为新分支名。详细步骤见 [quickstart.md §3](./quickstart.md)。

### Tests(先写测试)

- [ ] T025 [P] [US2] Create `backend/tests/integration/test_019_branch_bind.py`:
  - test_create_branch_then_patch_job_branch_id_succeeds:创建分支 → PATCH /jobs/{id} { branch_id } → GET /jobs/{id} 校验 branch_id 更新
  - test_patch_job_branch_id_to_invalid_uuid_rejected(422)
  - test_patch_job_branch_id_to_other_users_branch_rejected(422 / 404)
- [ ] T026 [P] [US2] Create `tests/unit/JobsDetailPanel-CTA.test.tsx` per spec.md US2:
  - test_resume_cta_visible_only_when_branch_id_null:`branch_id IS NULL` 时「为该岗位创建简历分支」CTA 可见可点;`branch_id IS NOT NULL` 时 CTA 隐藏,改为「换绑简历分支」下拉
  - test_interview_cta_disabled_with_tooltip_when_branch_id_null:`branch_id IS NULL` 时「为该岗位开始模拟面试」CTA 置灰 + tooltip "请先绑定简历分支";`branch_id IS NOT NULL` 时可点
- [ ] T027 [P] [US2] Create `tests/unit/ResumeEditorSourceJob.test.tsx`:
  - test_prefills_name_company_position_from_job:URL 含 `?source_job_id=xxx` 时,调用 `GET /jobs/{id}` 后把 name="字节 · 前端" / company="字节" / position="前端" 预填到表单
  - test_renders_requirements_md_foldable_card_when_over_50_chars
  - test_does_not_prefill_when_no_source_job_id:普通创建分支不触发预填
- [ ] T028 [P] [US2] Create `tests/unit/TopbarNewResumeMenu.test.tsx`:
  - test_renders_job_submenu_with_loading_state:二级下拉显示 job 列表(默认按 last_status_changed_at DESC)
  - test_search_jobs_in_submenu
  - test_clicking_job_navigates_to_source_job_url

### Implementation

- [ ] T029 [US2] Implement `src/pages/Jobs/DetailPanel.tsx`:加两个 CTA(spec.md FR-005);CTA 可见性逻辑用 `branch_id` 字段
- [ ] T030 [P] [US2] Implement `src/hooks/useJobs.ts`:加 `bindBranchToJob(jobId, branchId)` mutation(spec.md FR-008);走 outbox;失败 Toast「简历已保存,但岗位绑定失败,请到求职追踪里手动绑定」
- [ ] T031 [P] [US2] Implement `src/components/Topbar/NewResumeMenu.tsx`:加「基于岗位创建」二级入口(spec.md FR-006);二级下拉列 job(可搜索)
- [ ] T032 [P] [US2] Implement `src/pages/Resume/Editor.tsx`:URL `?source_job_id` 解析 → `GET /jobs/{id}` → 预填 name/company/position + `requirements_md ≥ 50 字符` 显示折叠卡片(spec.md FR-007)
- [ ] T033 [US2] Verify Job 详情面板的「绑定的简历分支」字段可点击跳转 `/resume/{branchId}`(沿用 014 既有逻辑)

**Checkpoint**: pytest `test_019_branch_bind.py` 3 通过;npm `JobsDetailPanel-CTA.test.tsx` 2 通过;`ResumeEditorSourceJob.test.tsx` 3 通过;`TopbarNewResumeMenu.test.tsx` 3 通过;Playwright US2 端到端命中

---

## Phase 5: User Story 3 — 从岗位开始模拟面试(P1)

**Goal**: Job 详情面板新增「为该岗位开始模拟面试」CTA(仅 branch_id 已绑时可点);点击后创建 interview_sessions 时同步落 job_id;Intake 阶段预填 4 字段(position/company/base_location/requirements_md);question_gen 节点 prompt 注入 requirements_md 截断片段。

**Independent Test**: 在 branch_id 已绑的 job 上点 CTA → POST /interview-sessions { job_id, branch_id } 返回 200 → 跳 InterviewLive → Intake 表单 4 字段预填 → 完成 5 轮后 GraphState 含 requirements_md 截断片段 → report 节点输出"该面试基于以下招聘需求(摘要)"段。详细步骤见 [quickstart.md §4](./quickstart.md)。

### Tests

- [ ] T034 [P] [US3] Create `backend/tests/unit/test_interview_job_id.py` per [contracts/interview-job-id.md §5](./contracts/interview-job-id.md):
  - test_create_session_without_job_id_succeeds(向后兼容,job_id=None)
  - test_create_session_with_valid_job_id_succeeds
  - test_create_session_with_nonexistent_job_id_rejected(422)
  - test_create_session_with_other_users_job_id_rejected(422)
  - test_create_session_with_branch_id_mismatch_rejected(422)
  - test_session_out_includes_job_id
- [ ] T035 [P] [US3] Create `backend/tests/unit/test_question_gen_prompt.py` per [contracts/requirements-md-prompt.md §7](./contracts/requirements-md-prompt.md):
  - test_build_requirements_block_empty:requirements_md=None → ("", False, False, 0)
  - test_build_requirements_block_short:md < 1500 token → 完整注入,truncated=False
  - test_build_requirements_block_long:md > 1500 token → tiktoken 截断到 1500 token,truncated=True
  - test_intake_node_loads_requirements_from_job:state["job_id"] 存在时,intake 节点从 jobs.requirements_md 读取并放入 GraphState
  - test_report_node_includes_requirements_summary:requirements_provided=True 时 report 节点输出 "## 该面试基于以下招聘需求(摘要)\n..."
  - test_report_node_skips_requirements_summary_when_not_provided
- [ ] T036 [P] [US3] Create `tests/unit/IntakeFormPrefill.test.tsx`:
  - test_prefills_3_readonly_fields_with_source_label:position/company/base_location 预填 + 只读 + "(来自岗位信息)"灰色说明
  - test_renders_requirements_md_foldable_card:折叠卡片只读
  - test_user_override_takes_precedence:用户改写任意字段后,提交时以用户值为准
- [ ] T037 [P] [US3] Create `tests/unit/StartInterviewFromJob.test.tsx`:
  - test_cta_calls_post_with_job_id_and_branch_id:点击「为该岗位开始模拟面试」→ 调用 `POST /interview-sessions { job_id, branch_id }` → 跳 InterviewLive
  - test_cta_disabled_when_branch_id_null:CTA 置灰,鼠标悬停显示 tooltip "请先绑定简历分支"
  - test_422_error_shows_error_toast

### Implementation

- [ ] T038 [US3] Implement Pydantic schema `backend/app/modules/interviews/schemas.py` `InterviewSessionCreate` 加 `job_id` 字段(spec.md FR-010)
- [ ] T039 [P] [US3] Implement `backend/app/modules/interviews/service.py` / `repository.py`:`create_session` 接受 job_id,服务端校验:存在 + 同属当前 user + branch_id 与 job.branch_id 一致(spec.md FR-011)
- [ ] T040 [P] [US3] Implement `backend/app/agents/interview/state.py` `InterviewGraphState`:加 4 字段(requirements_md / requirements_provided / requirements_truncated / requirements_original_chars)
- [ ] T041 [P] [US3] Implement `backend/app/agents/interview/graph.py` `build_requirements_block(requirements_md) -> (text, provided, truncated, original_chars)` per [contracts/requirements-md-prompt.md §2.2](./contracts/requirements-md-prompt.md)
- [ ] T042 [US3] Implement `backend/app/agents/interview/nodes/intake.py`:`intake` 节点读取 `state["job_id"]` → 查 `jobs.requirements_md` → 放入 `state["requirements_md"]`;若不存在则该字段为 None(spec.md FR-013)
- [ ] T043 [P] [US3] Implement `backend/app/agents/interview/graph.py` `question_gen` 节点 prompt 注入:在 system message 中插入 `{{requirements_md_block}}`,截断到 1500 token(spec.md FR-013)
- [ ] T044 [P] [US3] Implement `backend/app/agents/interview/nodes/report.py` `report_node`:若 `state["requirements_provided"]` 则在 report 中追加 `requirements_summary` 段(前 500 字符)
- [ ] T045 [US3] Implement `src/hooks/useInterviews.ts` mutation `createFromJob(jobId, branchId)`:调 `POST /interview-sessions { job_id, branch_id }`;成功后 router.push 跳 InterviewLive
- [ ] T046 [P] [US3] Implement `src/pages/Interview/IntakeForm.tsx`:4 字段预填(position/company/base_location 只读带说明 + requirements_md 折叠卡片);用户改写优先(spec.md FR-012)
- [ ] T047 [P] [US3] Implement `src/pages/Jobs/DetailPanel.tsx` 「为该岗位开始模拟面试」CTA 点击 → 调用 T45 mutation(spec.md FR-014)

**Checkpoint**: pytest `test_interview_job_id.py` 6 通过;`test_question_gen_prompt.py` 6 通过;npm `IntakeFormPrefill.test.tsx` 3 通过;`StartInterviewFromJob.test.tsx` 3 通过;Playwright US3 端到端命中

---

## Phase 6: User Story 4 — 模拟面试自动沉淀错题(P1)

**Goal**: score 节点写入 score < 6 时同步 UPSERT error_questions(frequency=3 / status=fresh / source_session_id / source_question_id 溯源);前端 ErrorBook 列表 source 筛选 + 详情面板「移除自动来源」+「删除」双按钮。

**Independent Test**: 完成一场 5 轮面试(其中第 2 题 score=3.5)→ 查 error_questions 表,该场 session 的 score < 6 题目都已创建错题记录;在 /error-book 选筛选「来自面试」看到这些错题;点「移除自动来源」清溯源,刷新后 source 标签消失但题目仍在;点「删除」直接丢弃,默认列表移除。详细步骤见 [quickstart.md §5](./quickstart.md)。

### Tests

- [ ] T048 [P] [US4] Create `backend/tests/unit/test_error_question_auto_create.py` per [contracts/error-questions-source.md §4](./contracts/error-questions-source.md):
  - test_maybe_create_when_score_below_threshold:score=3.5 → 创建错题(frequency=3, status=fresh, source_session_id, source_question_id 都非空)
  - test_maybe_create_when_score_at_or_above_threshold:score=6 → 不创建;score=10 → 不创建
  - test_upsert_on_same_question_id_does_not_duplicate:同 source_question_id 二次调用 → UPSERT,只更新 score / answer_text / reference_answer_md
  - test_first_create_wins_on_dimension_and_question_text:首次创建时 dimension / question_text 锁定,后续 UPSERT 不覆盖
  - test_logs_auto_error_created:调用 service 后有 `auto_error_created` 结构化日志
- [ ] T049 [P] [US4] Create `backend/tests/unit/test_error_question_clear_source.py` per [contracts/error-questions-source.md §2.1](./contracts/error-questions-source.md):
  - test_clear_source_sets_both_to_null:成功清空 source_session_id + source_question_id
  - test_clear_source_not_found_returns_404
  - test_clear_source_already_cleared_returns_400
  - test_clear_source_other_users_question_returns_404
- [ ] T050 [P] [US4] Create `backend/tests/unit/test_error_question_source_filter.py`:
  - test_list_with_source_auto_returns_only_with_source_session_id
  - test_list_with_source_manual_returns_only_null_source_session_id
  - test_list_with_source_all_returns_both(default)
- [ ] T051 [P] [US4] Create `tests/unit/ErrorBookDetail.test.tsx`:
  - test_renders_source_label_and_two_buttons_when_source_present:`source_session_id` 非空 → 显示「来自 {company} · {position} · {time}」+「移除自动来源」+「删除」按钮
  - test_renders_only_delete_button_when_source_null:`source_session_id` 为空 → 只显示「删除」按钮(016 既有文案)
  - test_delete_button_confirm_dialog_text_differs_by_source:`source_session_id` 非空 → 「删除『来自 XX 公司 · YY 岗位 · HH:mm 的错题』」;为空 → 「删除『{question_text 前 30 字}』」
  - test_clear_source_mutation_calls_patch_endpoint:点击「移除自动来源」→ `PATCH /error-questions/{id}/clear-source`
- [ ] T052 [P] [US4] Create `tests/unit/ErrorBookList.test.tsx`:
  - test_renders_source_filter_three_options:列表筛选区三选项(全部 / 来自面试 / 手动录入),默认"全部"
  - test_selecting_source_auto_filters_correctly

### Implementation

- [ ] T053 [US4] Implement `backend/app/modules/errors/repository.py` `upsert_auto_error(...)` per [contracts/error-questions-source.md §4](./contracts/error-questions-source.md):SQLAlchemy `postgresql.insert(...).on_conflict_do_update()` ON CONFLICT (source_question_id) WHERE source_question_id IS NOT NULL
- [ ] T054 [US4] Implement `backend/app/modules/errors/service.py`:
  - `AUTO_ERROR_THRESHOLD = 6` 常量(spec.md FR-020)
  - `async def maybe_create_from_question(*, user_id, session_id, question_id, score, dimension, question_text, answer_text, reference_answer_md, db) -> ErrorQuestion | None` 调用 T53 repository;记录 `auto_error_created` 结构化日志
- [ ] T055 [US4] Implement `backend/app/modules/errors/api.py`:
  - 新增 `PATCH /error-questions/{id}/clear-source` 端点(spec.md FR-017):清空 source_session_id + source_question_id + updated_at
  - 扩展 `GET /error-questions?source=auto|manual|all`(spec.md FR-018)
  - 复用 016 `DELETE /error-questions/{id}` 软删除(不新增端点)
- [ ] T056 [US4] Implement `backend/app/agents/score/nodes.py`:`score_node` 在写入 `interview_questions.score` 后同步调用 `await ErrorQuestionService.maybe_create_from_question(...)`(spec.md FR-016)
- [ ] T057 [P] [US4] Implement `src/hooks/useErrorQuestions.ts`:加 `clearSource(id)` mutation 调用 T55 PATCH 端点
- [ ] T058 [P] [US4] Implement `src/pages/ErrorBook/List.tsx`:加 source 筛选三选项(全部 / 来自面试 / 手动录入)(spec.md FR-019)
- [ ] T059 [P] [US4] Implement `src/pages/ErrorBook/Detail.tsx`:条件渲染 — `source_session_id` 非空 → 溯源文案 + 两个按钮;为空 → 仅删除按钮(016 文案)(spec.md FR-019)
- [ ] T060 [US4] Verify「移除自动来源」操作后,前端 React Query refetch 触发 UI 同步,列表筛选「来自面试」自动排除该错题

**Checkpoint**: pytest `test_error_question_auto_create.py` 5 通过;`test_error_question_clear_source.py` 4 通过;`test_error_question_source_filter.py` 3 通过;npm `ErrorBookDetail.test.tsx` 4 通过;`ErrorBookList.test.tsx` 2 通过;Playwright US4 端到端命中

---

## Phase 7: User Story 5 — 端到端联动冒烟(P2)

**Goal**: Playwright 5 步联动一次跑通(添加 Job → 创建分支 → 编辑分支 → 开面试 → mock 答 5 题 → ErrorBook 自动沉淀 → Profile 更新);完整链路无 4xx/5xx 与 console error。

**Independent Test**: 自动化 E2E 脚本一次跑完上述链路,验证每个节点状态字段正确写入,前端 6 个页面均能看到正确数据。详细步骤见 [quickstart.md §6-7](./quickstart.md)。

### Tests + Implementation

- [ ] T061 [P] [US5] Create `tests/e2e/fixtures/mock-llm.ts`:mock LLM 响应(5 个不同问题 + 5 个评分,其中 1 题 score=3.5 触发错题自动沉淀);沿用 Phase 4 现有 mock 框架
- [ ] T062 [US5] Create `tests/e2e/019-cross-module-linking.spec.ts` Playwright spec(5 步联动):
  - step_1_add_job:打开 /jobs → 点「添加职位」→ 填 company=字节 / position=前端 / base_location=北京 / requirements_md=200 字 / employment_type=experienced → 保存 → 详情抽屉显示 5 字段
  - step_2_create_branch_from_job:点「为该岗位创建简历分支」→ 验证跳转 URL 含 `?source_job_id=xxx` → 验证 name/company/position 预填 → 编辑 → 保存 → 验证 jobs.branch_id 回填
  - step_3_start_interview:点「为该岗位开始模拟面试」→ 验证跳 InterviewLive Intake → 验证 4 字段预填
  - step_4_complete_5_rounds_with_mock_llm:用 mock LLM 答 5 题(其中第 2 题 score=3.5) → 验证报告页生成 → 验证 report 含"该面试基于以下招聘需求(摘要)"段
  - step_5_verify_error_book_and_profile:打开 /error-book → 验证至少 1 条自动沉淀错题 → 验证 source_session_id 非空 → 验证「移除自动来源」按钮可见 → 打开 /profile → 验证 ability_dimensions 至少 1 个 updated_at 在面试之后
- [ ] T063 [US5] Run `cd frontend && npx playwright test tests/e2e/019-cross-module-linking.spec.ts -v`;若失败则排查(常见:Q1 R8 风险,E2E mock 设置不正确)
- [ ] T064 [US5] Manual smoke test in browser:打开 http://localhost:5173,完整走 5 步联动(spec.md SC-006 验收)

**Checkpoint**: Playwright 5 步联动一次通过;手动浏览器验证 OK

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 回归测试 + 文档 + Definition of Done 校验

- [ ] T065 [P] Run `cd backend && pytest tests/ -v` 期望全部通过(既有 + 新增 ~25 个单测 + 1 个集成测试)
- [ ] T066 [P] Run `cd frontend && npm run test` 期望全部通过(既有 + 新增 ~16 个 vitest 单测)
- [ ] T067 [P] Run `cd frontend && npm run build` 期望 typecheck + build 无错误
- [ ] T068 [P] Run `cd frontend && npx playwright test tests/e2e/` 期望 019 spec + 既有 e2e 全部通过
- [ ] T069 [P] Verify data-testid 暴露稳定 per spec.md FR-026 / FR-028:所有新增按钮 / 卡片 / 输入控件带 `data-testid`(`job-detail-resume-cta` / `job-detail-interview-cta` / `topbar-new-resume-from-job` / `intake-prefill-card` / `errorbook-source-filter-auto` / `errorbook-clear-source-btn` / `errorbook-delete-btn` 等)
- [ ] T070 [P] Verify 文案全简体中文 per spec.md FR-026:grep 新增 UI 字符串无英文
- [ ] T071 [P] Verify 8 个 Success Criteria(SC-001 ~ SC-008)全部命中(spec.md §Success Criteria)
- [ ] T072 [P] Verify 15 个 Edge Cases(E1 ~ E15)覆盖测试(后端 + 前端单测 / E2E)
- [ ] T073 [P] Verify Constitution 5 原则全部满足(plan.md §Constitution Check 表格)
- [ ] T074 [P] Verify 3 个风险缓解策略(R1 / R3 / R8)验证通过:
  - R1:dbq 校验列不存在 → 3 个迁移跑通
  - R3:tiktoken 截断 → test_build_requirements_block_long 命中
  - R8:E2E mock → Playwright 5 步联动一次通过
- [ ] T075 Update CLAUDE.md feature status from "planned" to "in progress" or "done"

**Checkpoint**: 全部任务勾选完毕;功能完成,可 PR review

---

## 依赖图(用户故事完成顺序)

```
Phase 1 (T001-T005): Setup
    ↓
Phase 2 (T006-T017): Foundational — 3 迁移 + 6 schema 扩展 + 1 集成测试
    ↓
┌─────────────────────────────────────────────┐
│  US1 (T018-T024)         P1  MVP           │  ← Phase 3
│  Job 5 字段扩展                                │
│  ↓ 提供 base_location / requirements_md 给下游  │
│  ┌───────────────────────────────────────┐  │
│  │  US2 (T025-T033)         P1           │  │  ← Phase 4
│  │  Job → Resume 双向入口                │  │
│  │  ↓ 提供 jobs.branch_id 给 US3        │  │
│  │  ┌──────────────────────────────┐    │  │
│  │  │  US3 (T034-T047)  P1         │    │  │  ← Phase 5
│  │  │  Job → Interview 入口        │    │  │
│  │  │  ↓ 触发 score 节点           │    │  │
│  │  │  ┌────────────────────┐      │    │  │
│  │  │  │  US4 (T048-T060)  │      │    │  │  ← Phase 6
│  │  │  │  Interview →      │      │    │  │
│  │  │  │  ErrorBook 自动沉淀 │      │    │  │
│  │  │  └────────────────────┘      │    │  │
│  │  └──────────────────────────────┘    │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
    ↓
US5 (T061-T064): 端到端联动冒烟 (P2) ← Phase 7
    ↓
Polish (T065-T075): 回归 + DoD ← Phase 8
```

**User Story 依赖关系**:
- US1 → 无依赖(可在 Phase 3 单独完成)
- US2 → 依赖 US1(读取 job 5 字段)
- US3 → 依赖 US1 + US2(读取 base_location / requirements_md / jobs.branch_id)
- US4 → 依赖 US3(score 节点触发)
- US5 → 依赖 US1 + US2 + US3 + US4(端到端)

## 并行执行示例(US3)

T034 / T035 / T036 / T037 都是不同文件,可并行:
- Backend: T034 (test_interview_job_id.py) + T035 (test_question_gen_prompt.py)
- Frontend: T036 (IntakeFormPrefill.test.tsx) + T037 (StartInterviewFromJob.test.tsx)

Backend 与 Frontend 各自可独立运行。

## MVP 范围(最小可行切片)

**Phase 1 + Phase 2 + US1(T001-T024)= MVP**
- 3 个迁移 + Job 5 字段落地
- 用户可在 /jobs 登记完整岗位信息并查看
- **不包含**:Job→Resume / Job→Interview 联动 / ErrorBook 自动沉淀

MVP 后增量交付 US2 → US3 → US4 → US5 → Polish。

## Definition of Done

- [ ] 全部 75 个任务勾选完毕
- [ ] `pytest backend/tests` 全部通过(新增 ~25 个单测 + 1 个集成测试)
- [ ] `npm run test` 全部通过(新增 ~16 个 vitest 单测)
- [ ] `npm run build` 无 typecheck 错误
- [ ] `npx playwright test tests/e2e/019-cross-module-linking.spec.ts` 通过
- [ ] 既有 014 / 016 / 006 / Phase 4 测试零回归
- [ ] 8 个 Success Criteria(SC-001 ~ SC-008)命中
- [ ] 15 个 Edge Cases(E1 ~ E15)覆盖
- [ ] Constitution 5 原则满足
- [ ] 3 个风险(R1 / R3 / R8)缓解策略验证通过
- [ ] CLAUDE.md 已更新
- [ ] PR description 引用 spec §FR + SC
