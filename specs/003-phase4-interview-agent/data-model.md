# Data Model: Phase 4 — Interview Agent

**Status**: Phase 1 output · **Date**: 2026-06-13 · **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

> 本文档定义 Phase 4 涉及的**新增数据库实体**、对 Phase 2 已有表的扩展,以及 LangGraph checkpointer schema。Phase 4 新增 2 张业务表(interview_reports / ai_messages)+ 1 个独立 schema(langgraph.checkpoints 等 3 张表由 langgraph-checkpoint-postgres 库管理)。

## 0. Phase 2 已有表 — Phase 4 变更

| 表 | Phase 2 状态 | Phase 4 变更 |
|---|---|---|
| `interview_sessions` | 只读表,status 默认 'pending' | **扩展字段**:`checkpoint_ns` 列(已有),`thread_id` 列(已有)。**新增写入**:POST/PATCH。status 状态机启用(pending→in_progress→completed/expired) |
| `ability_dimensions` | 6 行零值 seed(Phase 2) | Phase 4 通过 ARQ 异步任务首次写入真实数据 |
| `ability_dimensions_history` | append-only 空表 | Phase 4 写入首条历史快照 |

## 1. 新增业务表

### E-14 · `interview_reports`(InterviewReport)

**用途**:存储面试完成后的报告数据。1:1 InterviewSession。

**字段**:

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid | PK, uuidv7 | gen | 报告唯一标识 |
| `session_id` | uuid | FK → interview_sessions.id, UNIQUE, NOT NULL | — | 1:1 关联面试会话 |
| `overall_score` | numeric(4,2) | CHECK(0-10), NOT NULL | — | 加权平均总分 |
| `per_question_score` | jsonb | NOT NULL | — | `[{question_no, dimension, score, feedback}]` |
| `dimension_scores` | jsonb | NOT NULL | — | `{dim_key: avg_score}` 6 维均分 |
| `strengths` | jsonb | NOT NULL | — | `[{dimension, score, detail}]` 最高 2 维 |
| `improvements` | jsonb | NOT NULL | — | `[{dimension, score, detail, suggestions}]` 最低 2 维 |
| `summary_md` | text | NOT NULL | — | 自然语言摘要(Markdown) |
| `generated_at` | timestamptz | NOT NULL | now() | 报告生成时间 |
| `created_at` | timestamptz | NOT NULL | now() | — |
| `updated_at` | timestamptz | NOT NULL | now() | — |

**约束**:
- `session_id` UNIQUE:一个 session 只有一份报告
- `overall_score` CHECK(0 <= score <= 10)
- `per_question_score` JSONB 结构:`[{"question_no": 1, "dimension": "tech_depth", "score": 7.5, "feedback": "..."}]`
- `dimension_scores` JSONB 结构:`{"tech_depth": 7.2, "architecture": 6.5, ...}`
- `strengths` JSONB 结构:`[{"dimension": "tech_depth", "score": 7.2, "detail": "..."}]`
- `improvements` JSONB 结构:`[{"dimension": "architecture", "score": 6.5, "detail": "...", "suggestions": ["..."]}]`

**索引**:
- `idx_report_session(session_id)` — 按 session 查报告
- `idx_report_overall_score(overall_score DESC)` — 排行榜查询(Phase 5)

**Mixin**:TimestampedMixin(无 SoftDeletableMixin — 报告不允许删除;无 TenantScopedMixin — user 隔离通过 session 级联)

**RLS**:不直接启用(user_id 不在本表,通过 `session_id → interview_sessions.user_id` 间接隔离;API 层校验 user ownership)

### E-15 · `ai_messages`(AiMessage)

**用途**:记录每次 LLM 调用的请求/响应元数据,与 LangGraph checkpoints 形成双源,支撑审计与对账。

**字段**:

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid | PK, uuidv7 | gen | 记录唯一标识 |
| `user_id` | uuid | FK → users.id, NOT NULL | — | 用户隔离(RR-004) |
| `thread_id` | text | NOT NULL | — | LangGraph thread_id |
| `checkpoint_ns` | text | NOT NULL, DEFAULT '' | '' | LangGraph checkpoint namespace |
| `checkpoint_id` | text | NULL | — | 关联 LangGraph checkpoint |
| `node_name` | text | NOT NULL | — | intake / question_gen / score / report |
| `role` | text | CHECK(IN('system','user','assistant','tool')), NOT NULL | — | 消息角色 |
| `model` | text | NOT NULL | — | claude-opus-4-7 / claude-sonnet-4-6 / claude-haiku-4-5 |
| `prompt_tokens` | integer | CHECK(>=0), NOT NULL | — | 输入 token 数 |
| `completion_tokens` | integer | CHECK(>=0), NOT NULL | — | 输出 token 数 |
| `cache_hit` | boolean | NOT NULL, DEFAULT false | — | prompt cache 是否命中 |
| `duration_ms` | integer | CHECK(>=0), NOT NULL | — | LLM 调用耗时 |
| `occurred_at` | timestamptz | NOT NULL | now() | 调用发生时间 |
| `created_at` | timestamptz | NOT NULL | now() | — |

**约束**:
- `user_id` + `thread_id` + `checkpoint_ns` + `node_name`:非唯一(一个节点可能多次调用 LLM,如 question_gen 内部可能多轮)
- `cache_hit` 仅在 Anthropic prompt caching 启用时有效
- `model` 字符串不设 FK(模型名可能变化,保持灵活性)

**索引**:
- `idx_ai_msg_user_thread(user_id, thread_id, occurred_at)` — 按用户+thread 查询
- `idx_ai_msg_checkpoint(checkpoint_id)` — 对账 JOIN
- `idx_ai_msg_occurred(occurred_at)` — 对账时间窗口扫描

**Mixin**:UserScopedMixin(user_id) + TimestampedMixin(created_at only,无 updated_at — ai_messages append-only)

**RLS**:启用(TenantScopedMixin 等价:`USING (user_id = current_setting('app.user_id', true)::uuid)`)

## 2. LangGraph Checkpointer Schema

**Schema 名**:`langgraph`(与 public 业务表隔离)

**表**:由 `langgraph-checkpoint-postgres` 库自动创建,Phase 4 仅在 migration 中执行 `CREATE SCHEMA IF NOT EXISTS langgraph`:

| 表 | 用途 | 管理方 |
|---|---|---|
| `langgraph.checkpoints` | 每个 node 执行后的 state 快照(thread_id + checkpoint_ns + checkpoint_id) | langgraph-checkpoint-postgres |
| `langgraph.checkpoint_writes` | pending writes(中断节点的未完成写入) | 同上 |
| `langgraph.checkpoint_blobs` | 大字段分离存储(channel values) | 同上 |

**清理策略**:
- TTL:90 天(ARQ 周级 cron:`DELETE FROM langgraph.checkpoints WHERE created_at < NOW() - INTERVAL '90 days'`)
- 清理时级联删除 writes + blobs
- 清理前检查:不删除 `status = 'in_progress'` 的活跃 thread(24h 内更新的)

## 3. 实体关系图

```
users (Phase 1)
  │
  ├── interview_sessions (Phase 2 建表, Phase 4 写入)
  │     ├── 1:1 interview_reports (Phase 4 新增)
  │     └── 1:N ai_messages (Phase 4 新增)
  │
  ├── ability_dimensions (Phase 2 建表, Phase 4 首次写入)
  │     └── 1:N ability_dimensions_history (Phase 2 建表, Phase 4 首次写入)
  │
  └── langgraph.checkpoints (Phase 4 新增, 独立 schema)
        └── 与 ai_messages 通过 checkpoint_id 关联(对账)
```

## 4. 数据迁移

**Phase 2→4 迁移**:
- `interview_sessions` 表已有 `thread_id` / `checkpoint_ns` / `started_at` / `ended_at` / `duration_sec` 列(NULLABLE),Phase 4 开始填充
- `interview_reports` / `ai_messages` 为新表,无历史数据需迁移
- `langgraph` schema 为新创建

**Alembic migration**:`backend/migrations/versions/0004_phase4_agent.py`:
1. `CREATE SCHEMA IF NOT EXISTS langgraph` → langgraph-checkpoint-postgres 接管
2. `CREATE TABLE interview_reports(...)` + 索引
3. `CREATE TABLE ai_messages(...)` + 索引 + RLS 启用
4. `ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS checkpoint_ns TEXT`(Phase 2 已有则不执行)

## 5. 与 mockData 的字段映射

前端 `src/data/mockData.ts` 中 interview 相关字段 → 真实表:

| mockData 字段 | 真实表 | 备注 |
|---|---|---|
| `interviewSessions[].id` | `interview_sessions.id` | 直接映射 |
| `interviewSessions[].status` | `interview_sessions.status` | 枚举值对齐 |
| `interviewSessions[].questions` | `ai_messages`(role='assistant') + `interview_reports.per_question_score` | mock 中嵌入,真实数据分离 |
| `interviewSessions[].report` | `interview_reports` | mock 中嵌入,真实数据独立表 |
| 无(新增) | `ai_messages` | mock 中无审计数据,全新 |
