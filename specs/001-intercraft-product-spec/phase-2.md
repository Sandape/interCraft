# Implementation Plan: InterCraft Phase 2 — P1 业务实体上线

**Branch**: `001-intercraft-product-spec` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md) | **Phase 1 Plan**: [plan.md](./plan.md) | **Phase 2 Research**: [research-phase-2.md](./research-phase-2.md) | **Phase 2 Data Model**: [data-model-phase-2.md](./data-model-phase-2.md) | **Phase 2 Quickstart**: [quickstart-phase-2.md](./quickstart-phase-2.md)

**Input**: Phase 2 范围来自 spec §5.2(澄清 2026-06-13 决议 5 项),叠加 Phase 1 已就位的基础设施(账号/RLS/版本快照/前端 Repository 模式)。
**Note**: 本 plan.md 是「Phase 2 增量计划」;Phase 1 plan 仍为基础设施基线,Phase 2 在其上叠加 M08/M09/M10/M11 后端 + M23 P1.5 前端迁移。

---

## Summary

落地 **Phase 2 — P1 业务实体**:Profile / Jobs / 错题本(无 Agent)的纯 CRUD 部分上线,前端 mock 切换到真实 API。配套 6 维度能力画像只读、M11 面试历史只读骨架、ARQ cron 占位(每月 1 日 00:00 UTC 重置 token 配额)、Settings「资料」tab 迁移。后端 4 模块(M08/M09/M10/M11)+ 前端 3 页面 + 1 个 Settings tab,**不**涉及 LangGraph(M14+)、悲观锁(M12)、离线(M13)、Agent 子图(M16/M17/M18/M19)。

**技术路径**(沿用 Phase 1 DEC-1 ~ DEC-12,Phase 2 新增决议见 research-phase-2.md):
- 后端 FastAPI + SQLAlchemy 2.0 async + asyncpg + ARQ + Redis 7 + PostgreSQL 15(uuidv7 + RLS `SET LOCAL app.user_id`)
- 错题状态机:`fresh / practicing / mastered` + `frequency (0-3)`,状态推进在 M08 service 内封装
- 任务幂等:DB `UNIQUE (user_id, type, related_entity_id)` + service `find_or_create`(澄清 Q2 决议,2026-06-13)
- 能力画像 6 维度:子项 JSONB 存储,新用户注册时 seed 6 行零值(待定,见 research-phase-2.md R-2)
- 月度配额重置:ARQ cron 每月 1 日 00:00 UTC 批量重置(澄清 Q1 决议,2026-06-13)
- M11 只读:表落地 + list/get 读 API,无 create/update/delete(澄清 Q3 决议,2026-06-13)
- 错题 Phase 2 数据源:仅手动创建(FR-042),无 seed(澄清 Q4 决议,2026-06-13)
- 前端 M23 P1.5 迁移:Profile / Jobs / ErrorBook + Settings「资料」tab 切真实 API(澄清 Q5 决议,2026-06-13)
- 一键回退:`VITE_USE_MOCK=true` 走 mock,默认 `false` 走真实 API(沿用 Phase 1)

---

## Technical Context

**Language/Version**(沿用 Phase 1):
- 后端:Python 3.11+(`pyproject.toml` 锁定)
- 前端:TypeScript 5.6 strict mode
- 数据库 SQL:PostgreSQL 15 方言

**Primary Dependencies**(沿用 Phase 1,Phase 2 无新增关键依赖):
- 后端:沿用 `fastapi / sqlalchemy[asyncio] / asyncpg / alembic / pydantic-settings / structlog / arq / redis / jsonpatch / python-fractional-indexing / pytest`
- 前端:沿用 `react / react-router-dom / zustand / @tanstack/react-query / openapi-typescript / fast-json-patch / fractional-indexing / vitest / @testing-library/react / happy-dom / msw / @playwright/test`
- Phase 2 不引入新依赖;若 R-1(游标分页)决议需要 `empath` 或 `cursor-pagination`,在 research-phase-2.md 拍板后追加

**Storage**:
- 主库:PostgreSQL 15(沿用 T008b 在线 DB `81.71.152.210:5432/interCraft`,2026-06-12 解封)
- 缓存/Pub-Sub:Redis 7(沿用本地 6379)
- Phase 2 不新增 Redis 使用场景(ARQ cron 走 scheduler,锁与 outbox 留 Phase 3)
- 文件:`docs/` 持久化(规范/计划/报告),`.specify/` 持久化(spec-kit 元数据)
- 不在 Phase 2:对象存储(用户导出 zip 是 Phase 6 范畴)

**Testing**:
- 后端单测:`pytest` + `pytest-asyncio`,就近放在 `backend/app/<module>/tests/test_*.py`
- 后端集成:`tests/integration/`,起真实 PostgreSQL + Redis(沿用 T008b + 本地 Redis),httpx.AsyncClient
- 后端契约:OpenAPI schema 自动(`/api/v1/openapi.json`),由前端 `openapi-typescript` 消费
- 前端单测:`vitest` + `@testing-library/react` + MSW 拦截,文件就近 `src/**/*.test.ts(x)`
- 前端 E2E:`playwright`,`tests/e2e/`,走真实 dev server(真实后端)

**Target Platform**:
- 后端:Linux 容器(本地开发 Windows + WSL2,CI 跑 Linux),Docker Compose(沿用 Phase 1)
- 前端:现代桌面浏览器(Chrome / Edge / Firefox / Safari 最近 2 个大版本);移动端按 spec A2 「可用但非主战场」不专门优化

**Project Type**:**web**(frontend + backend,Phase 1 已分两个独立子项目,共享契约通过 OpenAPI)。

**Performance Goals**(对齐 spec §4 SC-010 ~ SC-013):
- SC-010 关键 REST API P95 ≤ 500ms
- SC-013 Dashboard 首屏 LCP ≤ 2s(4G)
- Phase 2 演示场景:三个页面在 `VITE_USE_MOCK=false` 下完全可用,所有列表/详情数据来自真实后端
- 列表分页接口 P95 ≤ 300ms(本地 DB,小数据集)

**Constraints**:
- 离线/Outbox 暂不实现(Phase 3)
- WS 业务端点暂不引入(Phase 4)
- 锁资源(ResumeBranch/ErrorQuestion 强化)悲观锁暂不实现(Phase 3);Phase 2 错题强化只读/手动改 status,frequency 推进留 Phase 5 M17
- 第三方 OAuth 仅留路由占位
- 移动端不专门优化
- i18n 不实现(默认 zh-CN,文案写在组件内)
- 多端同步未启用,无悲观锁(后写覆盖;Phase 3 引入)
- 错题 Phase 2 无 AI:仅手动 + FR-042 编辑/归档,无 NLP 去重、无 embedding 相似度
- 能力画像 Phase 2 无异步聚合:仅读;写路径在 Phase 4 M18 异步触发

**Scale/Scope**(Phase 2 范围):
- 用户数:≤ 1000(开发期)
- 错题:每用户 ≤ 200(开发期,生产预期 ≤ 1000)
- 任务:每用户 ≤ 100
- 活动流:每用户 ≤ 10000,游标分页 limit ≤ 50
- Jobs:每用户 ≤ 50
- 6 维度 + 3-5 子项:每用户 ≤ 30 行(`ability_dimensions`)
- 历史快照(`ability_dimensions_history`):每用户 ≤ 365/年
- InterviewSession 表(只读骨架):每用户 ≤ 200(开发期)
- 12 个 UI 页面中 Phase 2 涉及 4 个:**Profile** + **Jobs** + **ErrorBook** + **Settings 资料 tab**;其余页面继续读 mockData
- 演示场景:三个页面在 `VITE_USE_MOCK=false` 下完全可用,所有列表/详情数据来自真实后端

---

## Constitution Check

*GATE: Must pass before Phase 2 research. Re-check after Phase 2 design.*

依据 `.specify/memory/constitution.md` v1.0.0 的 5 大原则 + 技术约束 + 工作流,逐条校验:

### 原则 I — Library-First

| 检查点 | Phase 2 落点 | 状态 |
|---|---|---|
| 后端每个模块自包含(M08-M11),有 README + 公开 API + 配置 + 示例命令 | 每个模块在 `backend/app/modules/<module>/` 下有 `README.md`,`uv run python -m app.modules.<module>.cli --help` 可跑 | ✅ |
| AI 编排子图是「库」 | Phase 2 不涉及(Phase 4-5 范畴) | N/A |
| 前端特性模块是「库」 | `src/repositories/` 每个新文件(ErrorsRepo / AbilitiesRepo / TasksRepo / JobsRepo / SessionsRepo) + `src/api/` 客户端 = 独立模块,有自己的 README | ✅ |

### 原则 II — CLI Interface

| 检查点 | Phase 2 落点 | 状态 |
|---|---|---|
| 文本 I/O,默认人类可读,`--json` 模式可机读 | 每个模块 CLI 入口在 `backend/app/modules/<module>/cli.py`,`make_*.py --json` 输出 JSON | ✅ |
| CLI 退出码有文档(`0` 成功 / 非 0 失败) | README 中列出 | ✅ |
| 本地优先,无需启动完整 Web 栈 | `uv run python -m app.modules.<module>.cli ...` 直接可用 | ✅ |
| 前端核心逻辑可被 CLI 验证 | 错题状态机 reducer / 任务幂等校验 / 6 维度归一化提供 `node scripts/*.mjs` 命令;至少 `scripts/check-task-dedup.mjs` + `scripts/check-error-fsm.mjs` | ✅ |

### 原则 III — Test-First(NON-NEGOTIABLE)

| 检查点 | Phase 2 落点 | 状态 |
|---|---|---|
| 写测试 → 看红 → 签收 → 最小实现 → 重构 | tasks.md 中每个模块任务都先列「test 任务」再做「impl 任务」 | ✅ |
| UI 任务:组件测试 / hook 测试 / E2E 故事先于组件 | Profile / Jobs / ErrorBook 改 mock 接入真实 API 时,先写 MSW 拦截 + 组件测试再改代码 | ✅ |
| AI prompt 任务:评估样例先于 prompt | Phase 2 不涉及 | N/A |
| 任务只有在测试就位且为绿时才视为「完成」 | tasks.md 用 `[T]` 前缀标记测试任务,完成定义 = 测试绿 | ✅ |

### 原则 IV — Integration & Synchronization Testing

| 检查点 | Phase 2 落点 | 状态 |
|---|---|---|
| 跨服务通信(WS、REST)在真实或内存级适配器上端到端跑通 | `tests/integration/` 起真实 Postgres+Redis(沿用 T135/T137),不走 mock;`tests/e2e/` Playwright 走真实后端 | ✅ |
| 同步与离线路径 | Phase 2 不涉及同步/离线(Phase 3) | N/A |
| AI 编排边界 | Phase 2 不涉及 | N/A |
| 不允许「全部 mock 的快乐路径」 | 关键集成测试 = 真实 DB + 真实 Redis;前端 E2E = 真实后端;`VITE_USE_MOCK=true` 仅作为 dev fallback,**测试套件不依赖 mock** | ✅ |

### 原则 V — Observability

| 检查点 | Phase 2 落点 | 状态 |
|---|---|---|
| 结构化日志(JSON / key=value),含 `timestamp / level / request_id / message` | 沿用 Phase 1 `app/core/logging.py`(structlog);M08/M09/M10/M11 所有 service 走 logger 上下文 | ✅ |
| 请求关联 ID 跨服务传播 | 沿用 Phase 1 中间件;新接口自动透传 `X-Request-ID` | ✅ |
| 指标:请求率 / 错误率 / 延迟(p50/p95/p99) | 沿用 Phase 1 `GET /metrics` Prometheus 端点;M08/M09/M10/M11 自动通过 FastAPI 计数器暴露 | ✅ |
| 任务自动创建入 audit-style 日志 | `TaskService.find_or_create` 记录 `task.created` / `task.duplicate_skipped` 事件(可观测性,不阻塞主流程) | ✅ |
| AI 专用指标 | Phase 2 不涉及 | N/A |
| 错误上下文含足够复现信息 | 沿用 Phase 1 `app/core/exceptions.py`;新模块复用统一异常类型 | ✅ |
| CLI 即可观测:从保存的输入夹具重放失败场景 | 至少 `app.modules.tasks.cli replay` 落地(展示幂等场景) | ✅ |

### Technology & Stack Constraints

| 检查点 | Phase 2 落点 | 状态 |
|---|---|---|
| 前端 TS strict + React 18 + Vite + TailwindCSS | 沿用 Phase 1 | ✅ |
| 前端路由 `react-router-dom` v6 | 沿用 Phase 1 | ✅ |
| 组件库 / 状态方案需在 plan 给出书面理由 | 沿用 Phase 1(Zustand + React Query) | ✅ |
| 后端 MUST 暴露 HTTP 契约 + 机器可读 schema | 沿用 Phase 1 FastAPI OpenAPI;Phase 2 新增端点进入 `/api/v1/openapi.json` | ✅ |
| 持久层 MUST 用项目标准 ORM + 迁移工具,不允许即兴 SQL | SQLAlchemy 2.0 async + Alembic;新表走 `migrations/versions/0002_phase2_*.py` 单次迁移 | ✅ |
| AI 编排基于 LangGraph | Phase 2 不涉及 | N/A |
| 同步与离线客户端 | Phase 2 不涉及 | N/A |
| 安全与隐私:用户数据 MUST 静态 + 传输加密;密钥从环境变量读 | 沿用 Phase 1 | ✅ |
| 会话与 RLS(M05)是用户范围数据的唯一合法通道,强制启用 | 新表 `error_questions / ability_dimensions / ability_dimensions_history / tasks / activities / jobs / interview_sessions` **全部**走 RLS 策略 + `get_db_session(user_id=...)` 强制 `SET LOCAL app.user_id` | ✅ |

### Development Workflow

| 检查点 | Phase 2 落点 | 状态 |
|---|---|---|
| 分支命名 `[###-feature-name]` | 沿用 `001-intercraft-product-spec` | ✅ |
| 每个 PR 至少 1 次批准,reviewer 校验 I-V 合规 | Phase 2 沿用 | ✅ |
| 质量门禁:lint / typecheck / 单测 / 集成 / 契约 | 沿用 Phase 1 pre-commit + CI;新表 schema 变更触发 `openapi-typescript` 重建 | ✅ |
| Constitution Check 门禁 | 本节 + Phase 2 design 后 Re-evaluation | ✅ |
| Semantic Versioning + 公开 API 版本化 | `app/__version__.py` → `0.2.0`;REST 路径仍为 `/api/v1/` | ✅ |
| 库级 README(原则 I) | 每个新模块 `README.md` | ✅ |

### 治理

- 原则/约束如需偏离,必须在 Complexity Tracking 中给出理由。
- 任何运行时变更(配置 / 环境 / 工具)与宪法冲突时,以宪法为准。
- 本 plan 与宪法 v1.0.0 完全兼容;无未声明的偏离。

### Constitution Check 结论

**PASS — 无违规项**。Complexity Tracking 为空(下方保留结构占位)。

---

## Project Structure

### Documentation (this feature)

```text
specs/001-intercraft-product-spec/
├── plan.md                    # Phase 1 plan(已存在,基础设施基线)
├── phase-2.md                 # 本文件
├── research.md                # Phase 1 research(已存在)
├── research-phase-2.md       # Phase 2 research(本次新增)
├── data-model.md              # Phase 1 data model(已存在)
├── data-model-phase-2.md      # Phase 2 data model(本次新增)
├── quickstart.md              # Phase 1 quickstart(已存在)
├── quickstart-phase-2.md      # Phase 2 quickstart(本次新增)
├── contracts/                 # Phase 1 + Phase 2(增量)
│   ├── README.md              # 总览(更新:追加 Phase 2 端点)
│   ├── health.md              # /healthz
│   ├── events.md              # 共享错误响应
│   ├── auth.md                # 鉴权(M04)
│   ├── users.md               # 用户/资料(M04)
│   ├── sessions.md            # 设备/会话(M05)+ M11 面试会话只读端点
│   ├── resumes.md             # 简历分支(M06)
│   ├── blocks.md              # 简历块(M06)
│   ├── versions.md            # 简历版本(M07)
│   ├── error-questions.md     # 错题本(M08)— 本次新增
│   ├── abilities.md           # 能力画像(M09)— 本次新增
│   ├── tasks.md               # 任务(M10)— 本次新增
│   ├── activities.md          # 活动流(M10)— 本次新增
│   └── jobs.md                # 求职追踪(M10)— 本次新增
├── checklists/
│   └── requirements.md        # Spec quality checklist(已存在)
├── spec.md                    # 全产品 spec(已存在,Phase 2 澄清已写入 §Clarifications)
└── tasks.md                   # Phase 1 + Phase 2 任务(由 /speckit-tasks 生成)
```

### Source Code (repository root,Phase 2 增量)

> 仅列 Phase 2 新增/修改项;未变动的 Phase 1 目录省略。完整结构见 [plan.md](./plan.md)。

```text
D:\Project\eGGG\
├── backend/
│   ├── migrations/
│   │   └── versions/
│   │       └── 0002_phase2_entities.py    # 一次迁移:M08-M11 全部新表 + RLS
│   ├── app/
│   │   ├── core/
│   │   │   ├── pagination.py              # 扩:游标分页工具(cursor opaque base64)
│   │   │   └── scheduler.py               # 新:ARQ cron 注册(monthly_quota_reset 占位)
│   │   ├── domain/
│   │   │   ├── enums.py                   # 新:AbilityDimension / ErrorStatus / JobStatus / TaskStatus / ActivityType / InterviewStatus
│   │   │   └── pagination.py              # 新:CursorPage[T] 泛型 + encode/decode
│   │   ├── modules/
│   │   │   ├── auth/                      # 修改:user_credentials PATCH 路由开放
│   │   │   ├── errors/                    # 新(M08)
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py              # ErrorQuestion
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py             # 状态机 reducer(fresh→practicing→mastered)
│   │   │   │   ├── repository.py
│   │   │   │   ├── api.py                 # /error-questions CRUD(全开放)
│   │   │   │   ├── cli.py
│   │   │   │   └── tests/
│   │   │   ├── abilities/                 # 新(M09)
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py              # AbilityDimension / AbilityDimensionHistory
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py             # read + seed(注册时初始化 6 行零值)
│   │   │   │   ├── repository.py
│   │   │   │   ├── api.py                 # /ability-dimensions GET + /ability-dimensions/history?aggregate=
│   │   │   │   ├── cli.py
│   │   │   │   └── tests/
│   │   │   ├── tasks/                     # 新(M10 tasks 部分)
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py              # Task
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py             # find_or_create 幂等
│   │   │   │   ├── repository.py
│   │   │   │   ├── api.py                 # /tasks GET/POST/PATCH
│   │   │   │   ├── triggers.py            # 监听 jobs.status_change → 创建任务
│   │   │   │   ├── cli.py
│   │   │   │   └── tests/
│   │   │   ├── activities/                # 新(M10 activities 部分)
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py              # Activity
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py             # 游标分页(encode/decode)
│   │   │   │   ├── repository.py
│   │   │   │   ├── api.py                 # /activities?cursor=&limit=
│   │   │   │   ├── cli.py
│   │   │   │   └── tests/
│   │   │   ├── jobs/                      # 新(M10 jobs 部分)
│   │   │   │   ├── README.md
│   │   │   │   ├── models.py              # Job
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py             # 状态机 + 触发 task
│   │   │   │   ├── repository.py
│   │   │   │   ├── api.py                 # /jobs CRUD + /jobs/{id}/status PATCH
│   │   │   │   ├── cli.py
│   │   │   │   └── tests/
│   │   │   └── interviews/                # 新(M11)
│   │   │       ├── README.md
│   │   │       ├── models.py              # InterviewSession(只读骨架)
│   │   │       ├── schemas.py
│   │   │       ├── service.py             # list/get,无 create/update
│   │   │       ├── repository.py
│   │   │       ├── api.py                 # /interview-sessions GET + /interview-sessions/{id} GET
│   │   │       ├── cli.py
│   │   │       └── tests/
│   │   ├── workers/
│   │   │   ├── main.py                    # 修改:注册 monthly_quota_reset
│   │   │   └── tasks/
│   │   │       ├── dummy.py               # 沿用
│   │   │       └── monthly_quota_reset.py # 新:Phase 2 占位(对 Phase 1 已就位字段重置)
│   │   ├── api/
│   │   │   └── v1/
│   │   │       └── __init__.py            # 修改:挂载 errors/abilities/tasks/activities/jobs/interviews 路由
│   │   └── repositories/                   # 沿用 Phase 1 抽象,新模块不重写
│   └── tests/
│       └── integration/
│           ├── test_error_questions_crud.py
│           ├── test_abilities_read.py
│           ├── test_task_dedup.py         # 幂等键验证
│           ├── test_activities_pagination.py
│           ├── test_jobs_lifecycle.py
│           ├── test_interview_sessions_read.py
│           └── test_rls_isolation_phase2.py
│
├── src/                                    # 前端
│   ├── api/
│   │   ├── client.ts                       # 沿用
│   │   ├── schema.d.ts                     # openapi-typescript 重建(包含 Phase 2 端点)
│   │   └── env.ts                          # 沿用
│   ├── repositories/                       # 增:5 个新 repo
│   │   ├── ErrorQuestionRepository.ts      # 新
│   │   ├── AbilityRepository.ts            # 新
│   │   ├── TaskRepository.ts               # 新
│   │   ├── ActivityRepository.ts           # 新
│   │   ├── JobRepository.ts                # 新
│   │   ├── InterviewSessionRepository.ts   # 新(只读)
│   │   └── index.ts                        # 修改:导出 5 个新 repo
│   ├── hooks/
│   │   ├── queries/                        # 增
│   │   │   ├── useErrorQuestions.ts
│   │   │   ├── useAbilities.ts
│   │   │   ├── useTasks.ts
│   │   │   ├── useActivities.ts
│   │   │   ├── useJobs.ts
│   │   │   └── useInterviewSessions.ts
│   │   └── mutations/                      # 增
│   │       ├── useCreateErrorQuestion.ts
│   │       ├── useUpdateErrorQuestion.ts
│   │       ├── useArchiveErrorQuestion.ts
│   │       ├── useUpdateTaskStatus.ts
│   │       ├── useCreateJob.ts
│   │       ├── useUpdateJobStatus.ts
│   │       └── useUpdateProfile.ts
│   ├── pages/
│   │   ├── Profile.tsx                     # ✓ 改 mock → 真实 API
│   │   ├── Jobs.tsx                        # ✓ 改 mock → 真实 API
│   │   ├── ErrorBook.tsx                   # (原 src/pages/ 是否有此文件?确认后改 mock) — 若无,新建
│   │   ├── Settings.tsx                    # ✓ 仅「资料」tab 改真实 API;其他 tab 仍 mock
│   │   ├── Dashboard.tsx                   # 保持 mock(Phase 5 改)
│   │   ├── InterviewList.tsx               # 保持 mock(Phase 4 改)
│   │   ├── InterviewLive.tsx               # 保持 mock
│   │   ├── InterviewReport.tsx             # 保持 mock
│   │   ├── Resources.tsx                   # 保持 mock(Phase 6 改)
│   │   └── Help.tsx                        # 保持 mock(Phase 6 改)
│   ├── components/
│   │   └── settings/
│   │       └── ProfileTab.tsx              # 新(从 Settings.tsx 抽出,便于测试)
│   ├── data/
│   │   └── mockData.ts                     # 保留,给 MockRepository 用
│   └── main.tsx                            # 沿用
│
└── tests/
    └── tests/e2e/
        └── phase2/                         # 新
            ├── profile-from-api.spec.ts
            ├── jobs-from-api.spec.ts
            ├── errorbook-from-api.spec.ts
            └── settings-profile-tab.spec.ts
```

**Structure Decision**: 沿用 Phase 1 web-application 布局(frontend + backend 分两个子项目)。Phase 2 在 backend 新增 6 个 `app/modules/<module>/`,在 frontend 新增 6 个 `src/repositories/<X>Repository.ts` + 4 个新 `src/hooks/queries/` + 7 个 `src/hooks/mutations/`。Repository 模式 + Zustand + React Query 三层架构不变(沿用 FR-110)。

---

## Implementation Strategy

> Phase 2 实施按 spec §5.2 后端模块顺序 + 前端页面迁移顺序,**测试任务在前**。每个模块都是「先测试 → 再实现 → 再契约 → 再 E2E」闭环。

### 阶段 1:基础设施(共 1 周)

| # | 任务 | 产出 | 测试 |
|---|---|---|---|
| 1.1 | [T] 扩 `app/core/pagination.py` + `app/domain/pagination.py`:`CursorPage[T]` 泛型 + base64 编码/解码 + 单测 | 工具模块 | pytest unit |
| 1.2 | [T] 扩 `app/domain/enums.py`:6 维度 + 错题状态 + Job 状态 + Task 状态 + Activity 类型 + Interview 状态 | enum 模块 | pytest unit |
| 1.3 | [I] Alembic 迁移 `0002_phase2_entities.py` 一次性创建 7 张表 + RLS 策略 + 索引(`UNIQUE (user_id, type, related_entity_id)` for tasks)+ 6 维度 seed 钩子 | 迁移 | alembic upgrade head 成功 |
| 1.4 | [T][I] `app/core/scheduler.py` + `app/workers/tasks/monthly_quota_reset.py`:cron 注册 + 占位函数 | 调度器 | arq worker 启动 + cron 触发 dry-run |
| 1.5 | [T][I] `app/repositories/base.py` 扩:`find_or_create` 通用方法(供 tasks 模块使用) | Repository | pytest unit |

### 阶段 2:后端模块并行(共 1.5-2 周)

每个模块独立推进,Test-First 顺序:**test_api → test_service → test_repository → impl_repository → impl_service → impl_api → impl_cli**。

#### 2A. M11 面试历史(只读骨架,优先级最高 — 阻塞点最少,先打通,免得拖到后面)

- M11.1 [T] `test_interview_sessions_read.py`:`GET /interview-sessions` 返回 200 / `GET /interview-sessions/{id}` 返回 200 / 不存在返回 404
- M11.2 [T] `test_rls_isolation.py`:用户 A 拿到 B 的 session_id → 404(RLS 强制空集)
- M11.3 [I] `interviews/models.py` InterviewSession + `repository.py` + `service.py` + `api.py` + `cli.py`

#### 2B. M08 错题本(全 CRUD)

- M08.1 [T] `test_error_questions_crud.py`:list / get / create / patch(改 status,改 frequency)/ archive(soft_delete)
- M08.2 [T] `test_error_fsm.py`:state machine reducer — `fresh` → `practicing`(frequency 3→2,需手动)→ `mastered`(frequency=0);非法转换报错
- M08.3 [T] `test_error_dimensions.py`:6 维度 enum 校验,非法 dimension 422
- M08.4 [I] `errors/models.py` + `repository.py` + `service.py`(FSM reducer) + `api.py` + `cli.py`

#### 2C. M09 能力画像(只读 + 注册 seed)

- M09.1 [T] `test_abilities_read.py`:`GET /ability-dimensions` 返回 6 行 / `GET /ability-dimensions/history?aggregate=month` 返回时序
- M09.2 [T] `test_abilities_seed.py`:新用户注册后,`ability_dimensions` 自动 seed 6 行(零值)+ 子项 JSONB 与 mockData 一致
- M09.3 [T] `test_rls_isolation_abilities.py`:用户 A 读 B 的 dimensions → 404
- M09.4 [I] `abilities/models.py` + `service.py`(read + seed hook) + `repository.py` + `api.py` + `cli.py`
- M09.5 [I] `app/modules/auth/service.py` 修改:注册成功后调用 `AbilityService.seed_for_new_user(user_id)`(M04 钩子)

#### 2D. M10 任务 + 活动流 + Jobs(数据模型关联,放一起)

- M10.1 [T] `test_task_dedup.py`:相同 `(user_id, type, related_entity_id)` 二次创建不重复(find_or_create)
- M10.2 [T] `test_task_unique_constraint.py`:DB 唯一约束触发 `IntegrityError` → 409
- M10.3 [T] `test_activities_pagination.py`:游标分页 forward-only,`cursor=opaque_base64(occurred_at,id)`,limit 1-50,空 cursor 从头开始
- M10.4 [T] `test_jobs_lifecycle.py`:创建 job status=applied → 自动创建 task「准备 X 公司面试」→ PATCH status 推进到 test/oa/hr/offer/rejected/withdrawn → activities 写入
- M10.5 [T] `test_jobs_to_dashboard_funnel.py`:Phase 2 不要求 Dashboard 切真实;但 jobs 数据写入后,`GET /jobs/stats` 返回各 status 计数(供 Phase 5 dashboard 消费)
- M10.6 [I] `tasks/` + `activities/` + `jobs/` 三个模块,共享 `app/domain/enums.py` + `app/core/scheduler.py` 触发钩子

### 阶段 3:集成与契约(共 0.5 周)

- 3.1 [T] `tests/contract/test_openapi_schema.py` 扩:校验 7 个新模块所有端点 + 路径存在 + 必需 schema 字段
- 3.2 [T] `tests/integration/test_rls_isolation_phase2.py`:7 张表全部 2 用户互访 → 404
- 3.3 [T] `tests/integration/test_monthly_quota_reset.py`:手工调用 `monthly_quota_reset` 函数 → 验证 `monthly_token_used=0, quota_reset_at=now()`
- 3.4 [I] `openapi-typescript` 重新生成 → `src/api/schema.d.ts` 更新
- 3.5 [I] 跨端 parity smoke test:后端 pytest 23+ 单测 + 集成套件全绿,前端 `npm run typecheck` 通过

### 阶段 4:前端迁移(共 1 周)

每个页面独立 PR,按 spec M23 拆分:
- 4.1 [T] `src/repositories/ErrorQuestionRepository.ts` 单测(MSW handlers 对齐后端)
- 4.2 [T] `useErrorQuestions` + `useCreateErrorQuestion` 等 7 个 hook 单测
- 4.3 [I] `ErrorBook.tsx` 改真实 API(`mockData.ts` 注释标注「Phase 2 不再使用,留 mock 仓库内部使用」)
- 4.4-4.6 同样三步套用 Jobs / Profile / Settings 资料 tab
- 4.7 [T] `tests/e2e/phase2/*.spec.ts`:Playwright 走真实后端,验证 VITE_USE_MOCK=false 下「新建错题 → 列表出现」/「创建 job → 自动 task 出现」/「编辑资料 → 刷新持久化」
- 4.8 [I] `Settings.tsx` 拆出 `ProfileTab.tsx`,其他 tab 标「Phase 6 上线」占位

### 阶段 5:演示验证(共 0.5 周)

- 5.1 走 [quickstart-phase-2.md](./quickstart-phase-2.md) 全部场景
- 5.2 录屏演示:从登录 → Profile / Jobs / ErrorBook / Settings 资料 tab 真实数据展示
- 5.3 更新 spec §4 SC-002 / SC-006 状态,Phase 2 入口验收勾选

---

## Risks & Mitigations

| # | 风险 | 等级 | 缓解 |
|---|---|---|---|
| R-2.1 | A6 `thread_id` 派生规则未拍板,Phase 2 留 schema 但 Phase 4 才用 | 中 | `interview_sessions.thread_id` 列就位(nullable,text),Phase 2 文档说明「占位,Phase 4 决议」 |
| R-2.2 | 6 维度 + 子项 JSONB 设计的子项命名与 spec §3.2 mockData 对齐,Phase 4 写路径是否会变 schema | 中 | 子项用 JSONB 而非独立表,演进成本低;Phase 2 写 fixture 锁住基线 |
| R-2.3 | 任务触发器在 `JobService` 内显式调用 `TaskService.find_or_create` 违反单一职责 | 低 | 抽 `app/modules/jobs/triggers.py`,显式 import;test 覆盖幂等 |
| R-2.4 | 游标分页的 cursor 编码格式(opaque base64)前后端需一致,易出 drift | 中 | 共享 TypeScript 类型 + Python Pydantic 模型,加 parity test |
| R-2.5 | ARQ cron 漂移(本地时间 vs UTC)导致月重置不准 | 低 | 显式 UTC 调度 + `quota_reset_at` 字段保护(M04 schema 已就位) |
| R-2.6 | 错题状态机在 Phase 5 M17 Error Coach 子图会改规则,Phase 2 FSM 可能要重写 | 中 | FSM reducer 抽离 `errors/service.py::reduce_status()` 纯函数,便于 Phase 5 替换 |
| R-2.7 | Phase 2 演示需要登录后看到空数据,与 Phase 1 演示「5 分钟跑通 CRUD」体感落差 | 中 | 演示脚本强调「先点新建 → 体验真实 API」,quickstart 准备一条「演示最小集」步骤 |
| R-2.8 | 端点数量从 Phase 1 的 23 个增加到 30+,OpenAPI schema 变大,前端 `schema.d.ts` 重建耗时 | 低 | 沿用 openapi-typescript 7.x 增量生成,无影响 |

---

## Out of Scope (Phase 2 明确不做)

- ❌ LangGraph(M14) / 子图(Interview/ResumeOpt/ErrorCoach/AbilityDiag/General Coach)
- ❌ WS 业务端点(M14+)
- ❌ 悲观锁(M12)/ 离线 / Outbox(M13)
- ❌ 错题强化子图(Phase 5 M17):FR-043「Error Coach 完成后 frequency 减 1」留 Phase 5 实现
- ❌ Ability Diagnose 异步聚合(Phase 4-5 M18):FR-031/032/033 写路径留后续,Phase 2 仅读
- ❌ Interview Session 写入(M11 Phase 2 只读):create/update/delete 留 Phase 4
- ❌ 资源/帮助/数据导出/导入/注销/订阅档位变更:Phase 6
- ❌ Settings 其余 3 tab(设备 / 订阅 / 安全)
- ❌ Dashboard 切真实 API(Phase 5):Phase 2 仍读 mock,虽然 Jobs 数据已入库,Dashboard 漏斗不展示
- ❌ 移动端优化 / i18n / 多人协作 / HR 视角(延续 spec OOS)
- ❌ 错题 seed/示例数据 / Onboarding(澄清 Q4 决议)

---

## Open Questions(Phase 2 plan 阶段必须拍板)

> 这些问题不阻塞本 plan 通过,但必须在 `/speckit-tasks` 之前明确答案。

- **Q-P2-1**: AbilityDimension 6 个维度的**子项**(sub_keys)具体定义 — 已在 mockData `abilityDimensions.ts` 落地;若与 spec §3.2 不一致,以哪个为准?
- **Q-P2-2**: AbilityDimension 写路径(schema 是否允许写 actual_score)的 Phase 2 范围 — 仅读?还是开放 PATCH 供用户手动校正?
- **Q-P2-3**: 任务 `type` 枚举值清单 — 当前枚举为 `interview_prep / branch_optimize / application_followup / manual`;是否足够?
- **Q-P2-4**: 活动流 `type` 枚举值清单 — `task_created / task_completed / job_status_changed / interview_started / interview_completed / branch_created / error_logged / manual`
- **Q-P2-5**: 错题 `dimension` 字段是否可选(Phase 2 手动创建时用户可能不确定归类)?
- **Q-P2-6**: Jobs 状态变更触发的「准备 X 公司面试」任务 — 是否仅 status=applied 时创建一次,后续状态推进不重复创建?

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (无) | — | — |

**宪法 v1.0.0 完全对齐,Complexity Tracking 为空。**

---

## Phase 2 vs Phase 1 差异速查

| 维度 | Phase 1 | Phase 2 |
|---|---|---|
| 后端模块 | M01-M07(7) | M08-M11(4)+ M04 user_credentials 开放 + M22 scheduler |
| 前端页面 | Login + ResumeList + ResumeEditor(3)| Profile + Jobs + ErrorBook + Settings 资料 tab(4 块)|
| 新增表 | 6 张 | 7 张(error_questions / ability_dimensions / ability_dimensions_history / tasks / activities / jobs / interview_sessions)|
| RLS 策略 | 6 张表 | 13 张表(全部业务表)|
| 新增 ARQ cron | 1(auto_snapshot_branch 30min)| 1(monthly_quota_reset 月度)|
| 测试套件 | 47 pass / 22 skip(沿用 T135) | 预计 70+ pass(增量 ~25 个 Phase 2 用例)|
| OpenAPI 端点 | 23 | 30+ |
| Constitution Check | PASS | PASS |

---

## Next Step

`/speckit-tasks` 生成 Phase 2 任务列表(按本 plan 实施策略 5 阶段展开),随后按 tasks.md 推进 TDD 实施。
