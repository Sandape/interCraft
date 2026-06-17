# Implementation Plan: Cross-Module Linking (Job ↔ Resume ↔ Interview, Interview → Error Book)

**Branch**: `019-cross-module-linking` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-cross-module-linking/spec.md` + 014(Job Tracking)/016(Error Book)/006(Ability Profile)/Phase 4(Interview Agent) baselines.

**Note**: 本 plan.md 是「增量联动层」实施计划,严格不重写 014 / 016 / 006 / Phase 4 内部逻辑,只在保持向后兼容的前提下扩展字段 / 端点 / UI 入口。Ability Profile 链路(Phase 4 ability_diagnose → 006 时间衰减加权)在 Phase 4 / 006 已就位,本 plan 仅在数据冒烟上验证。

---

## Summary

落地 **Cross-Module Linking** —— 把求职追踪(Job)、简历中心(Resume Branch)、模拟面试(Interview)、错题本(Error Book)、个人画像(Ability Profile)五个模块按"以岗位为枢轴"串起来:

1. **Job 字段扩展** — 新增 5 列(base_location / requirements_md / employment_type / salary_range_text / headcount),让岗位元数据可结构化查询与跨模块传递。
2. **Job → Resume 双向入口** — Job 详情面板新增「为该岗位创建简历分支」CTA,Topbar「新建简历」下拉新增「基于岗位创建」,预填 name/company/position,自动回填 `jobs.branch_id`。
3. **Job → Interview 入口** — Job 详情面板新增「为该岗位开始模拟面试」CTA(仅 branch_id 已绑时可点),创建 `interview_sessions` 时同步落 `job_id`,Intake 阶段预填 4 个字段,`question_gen` 节点 prompt 注入 `requirements_md` 截断片段。
4. **Interview → Error Book 自动沉淀** — score 节点写入 `score < 6` 时同步 UPSERT 到 `error_questions`(frequency=3, status=fresh, source_session_id / source_question_id 溯源);提供「移除自动来源」(清溯源)与「删除」(直接丢弃,复用 016 现有 DELETE 流程)两个操作。
5. **Ability Profile 链路确认** — Phase 4 ability_diagnose → 006 聚合链路不修改,本 plan 仅在数据冒烟上验证 `ability_dimensions.updated_at` 在面试完成后刷新。

**技术路径**(沿用 Phase 1/2/3 + 014/016/006 + Phase 4 决议,本 plan 新增决议见 research.md):
- 后端扩展:`backend/app/modules/jobs/{models,schemas,api}.py`、`backend/app/modules/interviews/*`、`backend/app/modules/errors/{models,schemas,service,api}.py`
- 三个 alembic 迁移:`019_job_fields` / `019_interview_job_id` / `019_error_source_question_id`,各自 down-migration
- LLM prompt 注入 `requirements_md` 前 1500 token(tiktoken 截断),`question_gen` 节点 GraphState 标记 `requirements_provided`
- 前端扩展:`src/pages/Jobs/{DetailPanel,EditDrawer,CreateDrawer}.tsx`、`src/components/Topbar/NewResumeMenu.tsx`、`src/pages/Resume/Editor.tsx`、`src/pages/Interview/IntakeForm.tsx`、`src/pages/ErrorBook/{List,Detail}.tsx`、`src/api/{jobs,interviews,errors}.ts`
- 不引入新依赖,沿用现有 FastAPI / SQLAlchemy / alembic / tiktoken / React 18 + react-query + zustand / Vitest / Playwright 栈

---

## Technical Context

**Language/Version**(沿用 Phase 1/2/3):
- 后端:Python 3.11+(pyproject.toml 锁定)
- 前端:TypeScript 5.6 strict mode

**Primary Dependencies**:**无新增依赖**——全部沿用现有栈。
- 后端沿用:alembic / pydantic v2 / SQLAlchemy 2.0 async / FastAPI / tiktoken(Phase 4 已落地) / openai SDK
- 前端沿用:React 18 / Vite / TailwindCSS / react-router-dom / @tanstack/react-query / zustand
- 测试沿用:pytest + pytest-asyncio(后端) / vitest + @testing-library/react(前端) / Playwright(E2E)

**Storage**:
- 主库:PostgreSQL 15(沿用 Phase 1 在线 DB,本地 REDIS 6379)
- alembic 迁移:3 个新文件
  - `019_job_fields.py` — `jobs` 加 5 列
  - `019_interview_job_id.py` — `interview_sessions` 加 `job_id` FK + 索引
  - `019_error_source_question_id.py` — `error_questions` 加 `source_question_id` FK + 索引 + 部分唯一约束

**Testing**:
- 后端单测:`pytest`,覆盖新字段 Pydantic 校验 / ErrorQuestionService.maybe_create_from_question UPSERT 逻辑 / `PATCH /error-questions/{id}/clear-source` / Job ↔ branch_id 回填 / InterviewSessionCreate 接受 job_id
- 后端集成:`tests/integration/`,起真实 PostgreSQL,跑 alembic 迁移前后兼容性
- 后端契约:OpenAPI 自动生成,新增 `PATCH /error-questions/{id}/clear-source` + 扩展既有 ~6 个端点
- 前端单测:`vitest`,覆盖 CTA 可见性分支(branch_id 存在/缺失) / 表单预填 / 错题筛选 source / 删除 vs 移除按钮条件渲染
- 前端 E2E:Playwright,5 步联动链路 US5

**Target Platform**:
- 后端:Linux 容器(本地 Windows + WSL2 + uv)
- 前端:现代桌面浏览器(Chrome/Edge/Firefox/Safari 最近 2 个大版本)

**Project Type**: **web**(frontend + backend,Phase 1 已确立)

**Performance Goals**(对齐 spec §SC):
- SC-003:从 Job 详情开面试 → 5 轮出题平均延迟不受影响(沿用 Phase 4 的 < 1.5s/节点)
- SC-004:score 节点写库后 100ms 内同步触发 ErrorQuestionService.maybe_create_from_question
- SC-006:E2E 5 步联动一次通过,无 4xx/5xx

**Constraints**:
- 错题自动沉淀阈值 = 6 分(`AUTO_ERROR_THRESHOLD = 6`),写死在 `backend/app/modules/errors/service.py`,不为单用户暴露 UI 配置
- LLM prompt 注入 `requirements_md` 必须 tiktoken 截断 1500 token,不允许全量
- 不引入新前端路由,`/resume/{id}?source_job_id={jobId}` 走现有路由 + query param
- 不修改 014 / 016 / 006 / Phase 4 内部逻辑,只允许向后兼容扩展
- 严格遵循 Constitution 原则 I-V(见下文 Constitution Check)

**Scale/Scope**(本 feature 范围):
- 用户数:≤ 1000(开发期,沿用 Phase 1 上限)
- Job 字段新增 5 列:`jobs` 表所有行(已存在用户 0-100 jobs,新增)
- `interview_sessions.job_id`:可空 FK,允许历史 session 不带 job_id
- `error_questions.source_question_id`:可空 FK + 部分唯一约束,允许手动录入错题不带 source
- 错题自动沉淀触发量:每场 5 题面试平均触发 1-3 条错题(假设 30-60% 低分率)
- E2E 5 步链路:1 个 Playwright spec,1 场面试 5 轮完整对话(可用 mock LLM 加速)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 本 plan 合规性 | 说明 |
|---|---|---|
| **I. Library-First** | ✅ 合规 | 不新建顶层模块,扩展现有 `backend/app/modules/{jobs,interviews,errors}` 与 `src/{pages,components,api}`;每个 Pydantic schema / 端点 / 组件都在现有库内自包含 |
| **II. CLI Interface** | ✅ 合规 | 沿用 Phase 1 的 `cli.py` 模式;`ErrorQuestionService.maybe_create_from_question` 可被 CLI 夹具调用(`python -m app.modules.errors.cli ...`);3 个 alembic 迁移脚本均提供 down-migration |
| **III. Test-First (NON-NEGOTIABLE)** | ✅ 合规 | 本 plan 所有任务按 TDD 顺序:先写 Pydantic schema 单测 → 再写 Pydantic 类 → 端点单测 → 端点;前端 CTA 单测 → 组件实现 → 集成测试;Playwright E2E spec 先于手动验证 |
| **IV. Integration & Synchronization Testing** | ✅ 合规 | 后端用真实 PostgreSQL 跑 alembic 迁移(就近生产形态种子数据);前端 Playwright 跑通 5 步联动;错题 UPSERT 用真实 DB 验证幂等;outbox 重放在 014 已验证,本 plan 不重做 |
| **V. Observability** | ✅ 合规 | 新增端点走现有结构化日志(`app.core.logging`);`ErrorQuestionService.maybe_create_from_question` 记录 `event=auto_error_created / source_question_id / score`;LLM prompt 注入 `requirements_md` 时记录截断日志(`truncated_from_chars / truncated_to_tokens`) |

**Gate 结果**:无违规,无需 Complexity Tracking。

---

## Project Structure

### Documentation (this feature)

```text
specs/019-cross-module-linking/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出:研究决议
├── data-model.md        # Phase 1 输出:数据模型变更
├── contracts/           # Phase 1 输出:端点契约
│   ├── jobs-fields.md           # Job 5 字段扩展契约
│   ├── interview-job-id.md      # InterviewSession.job_id 契约
│   ├── error-questions-source.md # ErrorQuestion.source_question_id + clear-source 契约
│   └── requirements-md-prompt.md # question_gen 节点 prompt 注入契约
├── quickstart.md        # Phase 1 输出:验证冒烟指南
└── tasks.md             # Phase 2 输出(speckit-tasks 生成,本 plan 不含)
```

### Source Code(增量变更点)

```text
backend/
├── alembic/versions/
│   ├── 019_job_fields.py                  # NEW
│   ├── 019_interview_job_id.py            # NEW
│   └── 019_error_source_question_id.py    # NEW
├── app/modules/jobs/
│   ├── models.py                          # EXTEND: 5 字段
│   ├── schemas.py                         # EXTEND: CreateJobInput / PatchJobInput / JobOut / JobListOut
│   ├── api.py                             # EXTEND: 字段透传
│   └── repository.py                      # EXTEND: 字段读写
├── app/modules/interviews/
│   ├── models.py                          # EXTEND: job_id FK + 索引
│   ├── schemas.py                         # EXTEND: InterviewSessionCreate / Out / StartOut / ListOut 接受 job_id
│   ├── api.py                             # EXTEND: POST 接受 job_id,GET 返回
│   └── repository.py                      # EXTEND: 字段读写
├── app/modules/errors/
│   ├── models.py                          # EXTEND: source_question_id + 部分唯一约束
│   ├── schemas.py                         # EXTEND: ErrorQuestionOut 加 source_question_id;ErrorQuestionListOut 接受 source 参数
│   ├── service.py                         # EXTEND: AUTO_ERROR_THRESHOLD 常量 + maybe_create_from_question + clear_source
│   ├── repository.py                      # EXTEND: UPSERT 逻辑 + source 过滤
│   └── api.py                             # EXTEND: PATCH /error-questions/{id}/clear-source;List 接受 source 参数
├── app/agents/
│   ├── interview/
│   │   └── graph.py                       # EXTEND: question_gen 节点 prompt 注入 requirements_md 截断
│   └── score/
│       └── nodes.py                       # EXTEND: score 写入后同步调用 ErrorQuestionService.maybe_create_from_question
└── tests/
    ├── unit/
    │   ├── test_jobs_extended_fields.py           # NEW
    │   ├── test_interview_job_id.py               # NEW
    │   ├── test_error_question_auto_create.py     # NEW
    │   └── test_error_question_clear_source.py    # NEW
    └── integration/
        └── test_019_alembic_migrations.py         # NEW: 迁移前后兼容性

frontend/
├── src/
│   ├── api/
│   │   ├── jobs.ts                                # EXTEND: 5 字段类型 + CreateJobInput
│   │   ├── interviews.ts                          # EXTEND: job_id 类型
│   │   └── errors.ts                              # EXTEND: source_question_id + clearSource mutation
│   ├── pages/
│   │   ├── Jobs/
│   │   │   ├── DetailPanel.tsx                    # EXTEND: 5 字段展示 + 两个 CTA
│   │   │   ├── EditDrawer.tsx                     # EXTEND: 5 字段编辑
│   │   │   └── CreateDrawer.tsx                   # EXTEND: 5 字段创建
│   │   ├── Resume/
│   │   │   └── Editor.tsx                         # EXTEND: ?source_job_id 预填 + 招聘需求折叠卡片
│   │   ├── Interview/
│   │   │   └── IntakeForm.tsx                     # EXTEND: 4 字段预填(3 只读 + 1 参考卡片)
│   │   └── ErrorBook/
│   │       ├── List.tsx                           # EXTEND: source 筛选(全部 / 来自面试 / 手动录入)
│   │       └── Detail.tsx                         # EXTEND: 溯源文案 + 两个操作按钮
│   ├── components/
│   │   └── Topbar/
│   │       └── NewResumeMenu.tsx                  # EXTEND: 「基于岗位创建」二级入口
│   └── hooks/
│       ├── useJobs.ts                             # EXTEND: 新字段 + createFromJob mutation
│       └── useErrorQuestions.ts                   # EXTEND: source 筛选 + clearSource mutation
├── tests/
│   ├── unit/
│   │   ├── JobsDetailPanel.test.tsx               # NEW: CTA 可见性分支
│   │   ├── ResumeEditorSourceJob.test.tsx         # NEW: 预填逻辑
│   │   ├── IntakeFormPrefill.test.tsx             # NEW: 4 字段预填
│   │   └── ErrorBookDetail.test.tsx               # NEW: 移除/删除按钮条件渲染
│   └── tests/e2e/
│       └── 019-cross-module-linking.spec.ts       # NEW: 5 步联动冒烟
```

**Structure Decision**: Option 2 — Web 应用(frontend + backend),Phase 1 已确立。本 feature 在此结构内增量扩展,**不引入**新的顶级目录。

---

## Risk & Mitigation

| # | 风险 | 等级 | 缓解策略 |
|---|---|---|---|
| R1 | `interview_sessions.job_id` 字段若已存在会导致迁移失败 | 中 | Plan 阶段 T0.1 先用 `dbq.py`(沿用 Phase 1 工具)查表确认;若有同名,在迁移脚本中改名 + plan 阶段协商;迁移脚本使用 `IF NOT EXISTS`(PostgreSQL `ADD COLUMN IF NOT EXISTS`) |
| R2 | `error_questions.source_question_id` 部分唯一约束在已有数据上可能冲突 | 低 | 当前 `error_questions.source_question_id` 不存在(已确认);新增列时允许 NULL,NULL 不触发部分唯一约束 |
| R3 | `requirements_md` 注入 LLM prompt 过长导致出题质量下降 / token 超限 | 中 | tiktoken 截断 1500 token + 记录截断日志;Phase 4 已有 token 配额预扣,可自然 cover |
| R4 | score 节点同步调用 ErrorQuestionService 引入额外延迟,影响 Phase 4 节点 P95 ≤ 1.5s | 中 | maybe_create_from_question 是单条 UPSERT,实测 < 50ms;若超阈值,改为 ARQ 异步(降级方案,留待 Phase 6 重构) |
| R5 | Topbar「基于岗位创建」下拉岗位数 > 100 时全量渲染卡顿 | 低 | 复用 014 现有 useResumeBranches 的虚拟滚动 / 搜索下拉实现 |
| R6 | 014 PATCH /jobs/{id} 走 outbox,前端"创建分支后回填 branch_id"可能在断网时延后,导致用户看到不一致 | 低 | UI 在 PATCH 期间显示"绑定中…"占位;前端乐观更新 local state;outbox 重放后由 React Query 重新 fetch 触发 UI 同步 |
| R7 | 多端同时点击 CTA 创建分支,产生 race condition | 低 | 服务端不锁,允许两条;前端根据 409/200 区分;最后 PATCH 成功值为准 |
| R8 | E2E 5 步链路需真实 LLM,跑测慢且 flaky | 中 | E2E 用 `VITE_USE_MOCK=true` + 后端 mock LLM 响应(沿用 Phase 4 现有 mock 框架);5 轮对话用预设 mock 答案覆盖 |
| R9 | `error_questions.source_question_id` 与 `source_session_id` 联合去重约束可能误伤(同 session 多题同分) | 低 | 部分唯一约束只针对 `source_question_id` 单列,允许同 session 多题 |
| R10 | 错题"删除"操作复用 016 DELETE 端点,但 016 现有确认弹窗文案不区分 source | 中 | 前端确认弹窗按 `source_session_id IS NOT NULL` 分支渲染文案(US4 4a/4b 已明确) |

---

## Phased Plan

### Phase A:数据迁移与后端 schema(Foundation)

**目标**:3 个 alembic 迁移 + 后端 Pydantic schema 扩展,**零业务逻辑变更**,保证既有 014/016/Phase 4 测试零回归。

| Task | 描述 | 依赖 |
|---|---|---|
| T-A1 | 写 `019_job_fields.py` 迁移,加 5 列(base_location NOT NULL DEFAULT '' / requirements_md / employment_type NOT NULL DEFAULT 'unspecified' / salary_range_text / headcount) | — |
| T-A2 | 扩展 `backend/app/modules/jobs/models.py:Job` 加 5 列 | T-A1 |
| T-A3 | 扩展 `backend/app/modules/jobs/schemas.py`(`CreateJobInput` / `PatchJobInput` / `JobOut` / `JobListOut`)加 5 字段 + Pydantic 校验 | T-A2 |
| T-A4 | 写 `019_interview_job_id.py` 迁移,加 `job_id` UUID FK `jobs.id` ON DELETE SET NULL + 索引 `interview_sessions_job_id_idx`;迁移前用 `dbq.py` 校验列不存在 | T-A1 |
| T-A5 | 扩展 `backend/app/modules/interviews/models.py:InterviewSession` 加 `job_id` 列 | T-A4 |
| T-A6 | 扩展 `backend/app/modules/interviews/schemas.py`(`InterviewSessionCreate / Out / StartOut / ListOut`)加 `job_id` | T-A5 |
| T-A7 | 写 `019_error_source_question_id.py` 迁移,加 `source_question_id` UUID FK `interview_questions.id` ON DELETE SET NULL + 索引 + 部分唯一约束 `UNIQUE(source_question_id) WHERE source_question_id IS NOT NULL` | T-A1 |
| T-A8 | 扩展 `backend/app/modules/errors/models.py:ErrorQuestion` 加 `source_question_id` 列 | T-A7 |

**校验点**:跑 `pytest backend/tests` 与 `npm run test`(vitest)全部通过,既有 014 / 016 / Phase 4 测试零回归。

---

### Phase B:后端业务逻辑与端点

**目标**:3 个新端点 / 扩展 + 错题自动沉淀 hook + LLM prompt 注入。

| Task | 描述 | 依赖 |
|---|---|---|
| T-B1 | 后端单测:5 字段 Pydantic 校验(空 body / 超长 / 非法枚举 / headcount=0)→ 实现 | T-A3 |
| T-B2 | 后端单测:`InterviewSessionCreate` 接受 `job_id` / 不存在 job 422 / 不同 user 422 → 实现 | T-A6 |
| T-B3 | 后端单测:`ErrorQuestionService.maybe_create_from_question(session_id, question_id, score)`:score < 6 创建 / score >= 6 不创建 / 重评 UPSERT 不重复 → 实现 | T-A8 |
| T-B4 | 后端单测:`PATCH /error-questions/{id}/clear-source`:清空 source_session_id / source_question_id / 置 NULL → 实现 | T-B3 |
| T-B5 | 后端单测:`GET /error-questions?source=auto/manual/all` 三档过滤 → 实现 | T-B3 |
| T-B6 | 扩展 score 节点(`backend/app/agents/score/nodes.py`)在写入 `interview_questions.score` 后同步调用 `ErrorQuestionService.maybe_create_from_question` | T-B3 |
| T-B7 | 扩展 `question_gen` 节点(`backend/app/agents/interview/graph.py`)prompt 注入 `requirements_md` 前 1500 token(tiktoken),GraphState 标记 `requirements_provided` | T-A6 |
| T-B8 | 后端单测:report 节点输出含"该面试基于以下招聘需求(摘要)"段,前 500 字符 | T-B7 |
| T-B9 | 集成测试 `test_019_alembic_migrations.py`:起真实 PostgreSQL,跑 3 个迁移,验证 schema + 默认值 + FK + 部分唯一约束 | T-A1, T-A4, T-A7 |

**校验点**:`pytest backend/tests` 全部通过;既有 Phase 4 节点测试无回归。

---

### Phase C:前端 - Job 字段与联动 CTA

**目标**:Jobs 详情面板展示 5 字段 + 两个 CTA + Topbar 「基于岗位创建」下拉。

| Task | 描述 | 依赖 |
|---|---|---|
| T-C1 | 前端单测:`Jobs/DetailPanel.tsx` 5 字段渲染(base_location 默认占位"未填写"/ employment_type 默认"未指定" / 其他 NULL 占位) → 实现 | T-A3 |
| T-C2 | 前端单测:`Jobs/CreateDrawer.tsx` 5 字段输入控件 + 字符计数 → 实现 | T-A3 |
| T-C3 | 前端单测:`Jobs/EditDrawer.tsx` 5 字段编辑 + PATCH outbox → 实现 | T-A3 |
| T-C4 | 前端单测:`Jobs/DetailPanel.tsx` 两个 CTA 可见性分支:`branch_id IS NULL` 时 Resume CTA 可点 / Interview CTA 置灰 + tooltip;`branch_id IS NOT NULL` 时两者都可点 → 实现 | T-A3, T-A6 |
| T-C5 | 前端单测:`Topbar/NewResumeMenu.tsx` 二级下拉显示 job 列表(默认按 `last_status_changed_at DESC` / 可搜索) → 实现 | T-C4 |
| T-C6 | 前端实现:Resume 编辑器(`/resume/{id}`)读取 `?source_job_id` query param → 调用 `GET /jobs/{id}` → 预填 name/company/position + `requirements_md ≥ 50 字符` 时显示折叠卡片 | T-C5 |
| T-C7 | 前端实现:分支保存成功后 PATCH /jobs/{jobId} 把 `branch_id` 设为新分支 id(走 outbox),失败 Toast「简历已保存,但岗位绑定失败」 | T-C6 |
| T-C8 | 前端 E2E 片段:User Story 1 + 2 完整链路(添加 Job → 创建分支 → 详情显示绑定) | T-C7 |

**校验点**:`npm run test` 通过;手动 Playwright 跑 014 既有测试零回归。

---

### Phase D:前端 - Interview 联动 + Error Book 联动

**目标**:Job 详情启动面试 → Intake 预填 → score 自动沉淀错题 → ErrorBook 筛选 + 移除/删除。

| Task | 描述 | 依赖 |
|---|---|---|
| T-D1 | 前端单测:`Jobs/DetailPanel.tsx` 「为该岗位开始模拟面试」CTA 点击 → `POST /interview-sessions { job_id, branch_id }` → 跳 InterviewLive | T-C4, T-B2 |
| T-D2 | 前端单测:`Interview/IntakeForm.tsx` 4 字段预填(position/company/base_location 只读带说明 + requirements_md 折叠卡片) + 用户改写优先 | T-D1, T-B7 |
| T-D3 | 前端实现:`useInterviews.ts` mutation `createFromJob(jobId, branchId)` 调用 `POST /interview-sessions` 带 job_id + branch_id | T-D1 |
| T-D4 | 前端单测:`ErrorBook/List.tsx` source 筛选三选项(全部 / 来自面试 / 手动录入) → 实现 | T-B5 |
| T-D5 | 前端单测:`ErrorBook/Detail.tsx` 条件渲染:source_session_id 非空 → 显示溯源文案 + 两个按钮(移除/删除);为空 → 仅删除按钮 → 实现 | T-B4 |
| T-D6 | 前端实现:`useErrorQuestions.ts` mutation `clearSource(id)` 调用 `PATCH /error-questions/{id}/clear-source` | T-D5 |
| T-D7 | 前端 E2E 片段:User Story 3 + 4 完整链路(从 Job 开面试 → mock LLM 答 5 题 → 1 题低分 → ErrorBook 看到自动沉淀 + 移除/删除) | T-D6 |

**校验点**:`npm run test` 通过;手动 Playwright 跑 016 既有测试零回归。

---

### Phase E:端到端联动冒烟(US5)

**目标**:Playwright 5 步联动一次跑通。

| Task | 描述 | 依赖 |
|---|---|---|
| T-E1 | Playwright `019-cross-module-linking.spec.ts`:5 步联动(添加 Job → 创建分支 → 编辑分支 → 开面试 → mock 答 5 题 → ErrorBook 自动沉淀 → Profile 更新) | T-D7 |
| T-E2 | 手动验证:浏览器打开 `/jobs` 添加 job(base_location / requirements_md / employment_type 都填)→ 详情点 CTA 创建分支 → 编辑分支 → 点 CTA 开面试 → Intake 预填 4 字段确认 → mock LLM 答 5 题 → /error-book 看到自动沉淀 → /profile 看到画像刷新 | T-E1 |
| T-E3 | 跑 `pytest backend/tests` + `npm run test` + `npx playwright test` 三件套全绿 | T-E2 |

**校验点**:全部任务勾选完毕,功能完成。

---

## 实施顺序与依赖图

```
T-A1 (迁移 job_fields)
├── T-A2 (Job models)
│   └── T-A3 (Job schemas)
│       └── T-B1 (单测:Job 字段校验)
└── T-A4 (迁移 interview_job_id)
    └── T-A5 (Interview models)
        └── T-A6 (Interview schemas)
            ├── T-B2 (单测:Interview job_id)
            └── T-C4 (单测:CTA 可见性) ←── T-A3
                ├── T-D1 (单测:启动面试)
                └── T-C5 (Topbar 下拉)
                    └── T-C6 (Resume 编辑器预填)
                        └── T-C7 (回填 branch_id)
                            └── T-C8 (US1+2 E2E)

T-A1
└── T-A7 (迁移 error_source_question_id)
    └── T-A8 (Error models)
        └── T-B3 (单测:maybe_create_from_question)
            ├── T-B4 (单测:clear-source)
            ├── T-B5 (单测:source 过滤)
            └── T-B6 (score 节点集成)
                └── T-D5 (单测:Detail 按钮条件)
                    └── T-D6 (mutation)
                        └── T-D7 (US3+4 E2E)

T-B7 (question_gen prompt 注入) ←── T-A6
└── T-B8 (单测:report 输出)
    └── T-D2 (单测:IntakeForm 预填)

T-B9 (集成测试:迁移) ←── T-A1, T-A4, T-A7
└── T-E1 (E2E 5 步) ←── T-C8, T-D7
    └── T-E2 (手动验证)
        └── T-E3 (三件套全绿)
```

**可并行**:
- Phase A 3 个迁移可并行(T-A1 / T-A4 / T-A7)
- Phase B 业务逻辑 T-B1 / T-B2 / T-B3 / T-B4 / T-B5 写单测阶段可并行(不同文件)
- Phase C / D 前端各组件单测可并行

**必须串行**:
- T-A1 → T-A2 → T-A3(模型依赖 schema)
- T-B3 → T-B6(score 节点 hook 依赖 service)
- T-C7 → T-C8(E2E 依赖回填实现)
- T-D7 → T-E1(联动 E2E 依赖 US3+4)

---

## 验证清单(Definition of Done)

- [ ] 3 个 alembic 迁移全部跑通,既有 schema 不破坏
- [ ] `pytest backend/tests` 全部通过(新增 ~6 个单测 + 1 个集成测试)
- [ ] `npm run test` 全部通过(新增 ~6 个 vitest 单测)
- [ ] `npx playwright test tests/e2e/019-cross-module-linking.spec.ts` 通过
- [ ] 既有 014 / 016 / 006 / Phase 4 单元测试零回归
- [ ] Constitution 5 原则全部满足
- [ ] 3 个风险缓解策略(R1/R3/R8)验证通过
- [ ] 8 个 Success Criteria(SC-001 ~ SC-008)全部命中
- [ ] 15 个 Edge Cases(E1 ~ E15)覆盖测试
