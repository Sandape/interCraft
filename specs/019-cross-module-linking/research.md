# Phase 0 Research: Cross-Module Linking

**Status**: Phase 0 output · **Date**: 2026-06-17 · **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

> 本文档记录 019-cross-module-linking 中需要研究决议的不确定点。Spec §Clarifications(2026-06-17,8 项决议)已收敛大部分范围,本 research 聚焦于 alembic 迁移兼容性 / 错题 UPSERT 实现路径 / LLM prompt 注入截断策略 / E2E mock 方案 / outbox 行为一致性这 5 个落地细节。

## 0. 上下文

019 目标(参见 spec):把 Job / Resume / Interview / ErrorBook / AbilityProfile 五个模块按"以岗位为枢轴"串起来,只做增量联动层(不重写 014 / 016 / 006 / Phase 4)。

Phase 1/2/3 + 014 + 016 + 006 + Phase 4 基础设施已就位:
- 014:`jobs` 表 + 7 端点 + 状态机 + 详情抽屉时间线 + outbox
- 016:`error_questions` 表 + Recall/Reset 流程
- 006:`ability_dimensions` 时间衰减加权聚合 + 雷达图 + 详情面板
- Phase 4:LangGraph 子图 + DeepSeek V4 Pro + WS 流式 + ability_diagnose 异步触发
- Phase 3:outbox 模式(`src/lib/outbox/` + `backend/app/modules/outbox/`)

019 不涉及:语音模式 / 简历编辑器增强 / 邮箱解析 / 邮件集成 / Offer 谈判追踪 / 通用 i18n。

## 1. 已知决策(从 spec + 014/016/006/Phase 4 继承)

| # | 决策 | 来源 | 019 是否需要进一步研究 |
|---|---|---|---|
| D-1 | 后端 = FastAPI + SQLAlchemy 2.0 + asyncpg | Phase 1 research D-1 | 否 |
| D-2 | DB = PostgreSQL 15(本地 + 在线托管) | Phase 1 research D-2 | 否 |
| D-3 | 队列 = ARQ + Redis 7 | Phase 1 research D-3/D-4 | 否(019 不需要新队列) |
| D-4 | 鉴权 = JWT + RLS(`SET LOCAL app.user_id`) | Phase 1 research D-6/D-10 | 否 |
| D-5 | AI 编排 = LangGraph | spec §6 A6 | 否 |
| D-6 | LLM = DeepSeek V4 Pro(`deepseek-chat`),OpenAI 协议 | Phase 4 决议 | 否 |
| D-7 | outbox 模式(Phase 3) | Phase 3 plan | 否 |
| D-8 | `error_questions.source_session_id` 外键已存在 | 016 数据模型 | **是**:如何与新增 `source_question_id` 协同 |
| D-9 | 错题 frequency / recall / reset 流程 | 016 spec | 否 |
| D-10 | 014 PATCH /jobs/{id} 走 outbox | 014 plan | 否 |
| D-11 | ability_diagnose → 006 时间衰减加权聚合 | Phase 4 + 006 plan | 否(019 不修改) |
| D-12 | Job 字段扩展 = base_location / requirements_md / employment_type / salary_range_text / headcount | spec Clarifications Q1(2026-06-17) | **是**:默认值 / 校验规则 |
| D-13 | Resume 创建入口 = Job 详情 + 新建简历页双向 | spec Clarifications Q2(2026-06-17) | **是**:URL 模板 + 预填逻辑 |
| D-14 | Interview 入口 = Job 详情启动 + 必选简历分支 | spec Clarifications Q3(2026-06-17) | **是**:branch_id 必选校验 |
| D-15 | 错题自动沉淀 = 阈值 + 用户复审(移除 / 删除) | spec Clarifications Q4(2026-06-17) | **是**:UPSERT 实现 / 阈值常量 |
| D-16 | Ability Profile 链路 = 已就位,本 SPEC 不重复 | spec Clarifications Q5(2026-06-17) | 否 |
| D-17 | SPEC 范围 = 仅增量联动层 | spec Clarifications Q6(2026-06-17) | 否 |
| D-18 | SPEC 位置 = specs/019-cross-module-linking/spec.md | spec Clarifications Q7(2026-06-17) | 否 |
| D-19 | SPEC 语言 = 全中文 | spec Clarifications Q8(2026-06-17) | 否 |

## 2. 019 需要研究的不确定点

### R-1: alembic 迁移兼容性(`interview_sessions.job_id`)

**问题**:spec FR-009 明确在 `interview_sessions` 加 `job_id` 列。若该列已存在(开发期多次应用迁移),迁移脚本会失败。

**研究范围**:
- 用 `dbq.py`(Phase 1 工具,`backend/scripts/dbq.py`)先查 `information_schema.columns WHERE table_name='interview_sessions' AND column_name='job_id'`
- 迁移脚本使用 `op.add_column('interview_sessions', sa.Column('job_id', ..., nullable=True))` + `IF NOT EXISTS`(PG 原生)
- alembic 提供 `op.execute("ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...")` 写法
- 历史 session(job_id 为 NULL)允许存在,FK ON DELETE SET NULL 保证 job 删除时 session 不级联

**评估结论**:选 **先 dbq 校验 + IF NOT EXISTS + nullable** 三重保险。

**理由**:
- `IF NOT EXISTS` 是 PostgreSQL 原生(9.6+),零额外开销
- 可空列 + 无 server_default 是最保守的破坏性最小的扩展
- dbq 校验让开发者在 plan 阶段先看到"已有 vs 未有"的事实,避免运行时翻车

**风险**:若 dbq 显示 `job_id` 已存在(被合并的某个 feature 抢先),需在 plan 阶段立即决定:
- a) 重命名为 `interview_job_id`
- b) 复用现有列(若语义一致)

**降级**:降级方案 a,改名 + 同步 schema。

**产出**:`backend/alembic/versions/019_interview_job_id.py` + `dbq.py` 校验脚本片段。

---

### R-2: 错题自动沉淀 UPSERT 实现路径

**问题**:spec FR-016 要求 `ErrorQuestionService.maybe_create_from_question(session_id, question_id, score)`:score < 6 时创建,重评不重复。

**研究范围**:
- 数据库层:PG `INSERT ... ON CONFLICT (source_question_id) WHERE source_question_id IS NOT NULL DO UPDATE SET score=EXCLUDED.score, ...`
- 部分唯一约束:`UNIQUE(source_question_id) WHERE source_question_id IS NOT NULL`(PG 原生支持)
- 应用层:`SELECT FOR UPDATE` 锁后 INSERT/UPDATE(性能差)
- ORM 层:SQLAlchemy 2.0 `postgresql.insert().on_conflict_do_update()`(PG dialect)

**评估结论**:选 **部分唯一约束 + ON CONFLICT DO UPDATE**(两层保险,DB 层保证,ORM 层简化)。

**理由**:
- 部分唯一约束是"声明式"约束,不依赖应用层逻辑,即使直接 SQL 也保证幂等
- `ON CONFLICT DO UPDATE` 让"创建与更新"是单条 SQL,事务内自动原子化
- 测试可分两层:DB 层直接跑 SQL 验证约束生效;ORM 层 mock 验证 service 调用

**额外检查**:
- 若 `interview_questions.id` 在 score 节点写入时被并发更新(理论可能),UPSERT 用 `score = EXCLUDED.score` 会覆盖;但 score 节点本身是串行执行(LangGraph state),并发不构成风险
- 错题 `dimension / question_text` 在重评时**不**覆盖(以首次创建时为准,避免历史记录被改写);只更新 `score / answer_text / reference_answer_md`

**产出**:`backend/app/modules/errors/repository.py` 的 `upsert_auto_error(...)` 方法 + `backend/app/modules/errors/service.py` 的 `maybe_create_from_question(...)` 方法。

---

### R-3: LLM prompt 注入 `requirements_md` 截断策略

**问题**:spec FR-013 要求 `question_gen` 节点 prompt 注入 `requirements_md` 前 1500 token(tiktoken 截断),GraphState 标记 `requirements_provided`。

**研究范围**:
- tiktoken:`tiktoken.encoding_for_model("gpt-4")` 兼容 OpenAI / DeepSeek tokenizer
- 截断策略:
  - a) 字符截断:前 N 字符(简单但不准,中文 1 字 ≈ 1.5 token)
  - b) token 截断:tiktoken 编码后切前 1500 token,再 decode(准确但慢)
- 注入位置:prompt 的 `context` 段(在 system / user message 之间)
- 占位符:用 `{{requirements_md}}` 让 prompt template 替换
- 截断日志:`logger.info("truncated_requirements_md", original_chars=..., truncated_tokens=1500, ratio=...)`

**评估结论**:选 **token 截断 + 占位符替换 + 结构化日志**。

**理由**:
- token 截断保证"不超 1500 token"是硬性约束(LLM 上下文窗限)
- 占位符让 prompt template 与代码解耦,可在测试中 mock
- 结构化日志让生产可观测(Phase 4 已有 logger 模式)

**额外检查**:
- DeepSeek V4 Pro 上下文窗限制:`deepseek-chat` 默认 32K context,1500 token 占 4.7%,安全
- 截断后内容可能丢失关键需求(如"必须会 Rust"),但 spec E6 允许该降级;后续可加"招聘需求摘要"子节点提炼关键需求
- 若 `requirements_md` 为空,prompt 不注入,GraphState 标记 `requirements_provided=false`

**产出**:`backend/app/agents/interview/graph.py` 的 prompt 构造函数 + `backend/app/agents/interview/state.py` 的 GraphState 新增字段。

---

### R-4: E2E mock 方案

**问题**:spec US5 端到端冒烟 5 步链路需真实 LLM,跑测慢且 flaky。

**研究范围**:
- Phase 4 现有 mock 框架:后端 `app/core/llm_client.py` 支持 `VITE_USE_MOCK=true` 时返回 mock response
- 5 轮对话 mock 答案:预定义 5 个问题 + 5 个低分答案(让至少 1 题 score < 6)
- Playwright fixture:`globalSetup` 注入 `VITE_USE_MOCK=true`,启动 mock backend
- 错题自动沉淀验证:跑完面试后查 `/error-book`,断言至少有 1 条 `source_session_id IS NOT NULL` 的错题

**评估结论**:选 **沿用 Phase 4 mock 框架 + Playwright mock fixture + 预设 5 题答案**。

**理由**:
- Phase 4 已有 mock 客户端,019 不重复实现
- 预设 5 题答案让测试可重复(LLM 输出有随机性)
- 端到端 mock 不破坏真实集成测试(014/016/006 既有测试零回归)

**额外检查**:
- mock LLM 必须返回 1 题低分(score < 6)触发错题自动沉淀;预设第 2 题返回 `{"score": 3.5, ...}`
- mock LLM 必须返回 5 个不同的问题 + 5 个评分,否则 Phase 4 5 轮循环卡住
- 错题详情断言:source_session_id 等于该场 session.id(用 Playwright `data-testid` 锁定)

**产出**:`tests/e2e/019-cross-module-linking.spec.ts` + `tests/e2e/fixtures/mock-llm.ts`。

---

### R-5: 014 outbox 行为一致性(`PATCH /jobs/{id}` 回填 branch_id)

**问题**:spec FR-008 要求分支保存成功后 `PATCH /jobs/{jobId}` 把 `branch_id` 设为新分支,断网时入 outbox,网络恢复后重放。

**研究范围**:
- 014 outbox 模式:`src/lib/outbox/` + `backend/app/modules/outbox/`
- 写操作入 outbox:创建 / 改状态 / 编辑 / 删除 4 类
- 前端 mutation:React Query `mutate` 触发 `enqueue(outboxEntry)` + 立即本地更新
- 后端 worker:ARQ cron 重放未同步 entry

**评估结论**:选 **沿用 014 outbox 模式 + React Query mutation 触发 + Toast 失败提示**。

**理由**:
- 019 不重写 outbox,沿用 014 既有实现
- 前端 mutation 与 014 编辑 mutation 共用同一 enqueue 通道
- 失败时 Toast 明确告知"简历已保存,但岗位绑定失败,请到求职追踪里手动绑定",避免用户困惑

**额外检查**:
- outbox 重放成功后,前端 React Query 自动 refetch `useJob(id)` 触发 UI 同步
- 多端冲突:outbox 重放不锁,允许并发 PATCH;最后成功的值为准
- 若用户删除该分支,Job.branch_id 自动 SET NULL(已有 ON DELETE SET NULL)

**产出**:`src/hooks/useJobs.ts` 的 `bindBranchToJob(jobId, branchId)` mutation + Toast 文案。

---

## 3. 决议汇总

| # | 决议 | 选型 | 关键理由 |
|---|---|---|---|
| R-1 | `interview_sessions.job_id` 迁移 | dbq 校验 + IF NOT EXISTS + nullable | 三重保险,零破坏性 |
| R-2 | 错题 UPSERT | 部分唯一约束 + ON CONFLICT DO UPDATE | DB 层保证 + ORM 层简化 |
| R-3 | requirements_md 截断 | tiktoken 1500 token + 占位符 + 结构化日志 | 硬性 token 限制 + 可观测 |
| R-4 | E2E mock | 沿用 Phase 4 mock + 预设 5 题答案 | 可重复 + 不破坏真实集成 |
| R-5 | outbox 回填 | 沿用 014 模式 + Toast 失败提示 | 既有契约 + 用户感知清晰 |

## 4. 019 不涉及的研究点(已确认 Out-of-scope)

- ❌ 简历编辑器增强(002 spec) — 019 仅用预填 name/company/position,不进入编辑器增强
- ❌ 错题 AI 强化对话(M17 Error Coach) — 016 spec 已记为 Out-of-scope
- ❌ 个人画像归因(`job_id` 影响画像变化) — 留待后续 feature,019 仅确认数据刷新
- ❌ 邮件解析 / 自动入库岗位 — 014 spec 已记为 Out-of-scope
- ❌ Offer 谈判追踪 / 面试日程日历集成 — 014 spec 已记为 Out-of-scope
- ❌ 通用 i18n 框架 — 019 全简体中文,与现有规范一致
- ❌ 简历分支元数据扩展(`requirements_md / base_location` 进 ResumeBranch) — 留待后续 feature,019 仅通过"预填 name/company/position"满足

## 5. 风险与缓解(摘录 plan.md §Risk)

| # | 风险 | 缓解 | 验证 |
|---|---|---|---|
| R1 | `interview_sessions.job_id` 字段已存在 | dbq.py 校验 + IF NOT EXISTS | T0.1 阶段手动跑 dbq |
| R3 | requirements_md 注入导致出题质量下降 | tiktoken 截断 + 日志 | T-B8 单测验证 |
| R8 | E2E 5 步链路 flaky | 沿用 Phase 4 mock + 预设答案 | T-E1 Playwright |
