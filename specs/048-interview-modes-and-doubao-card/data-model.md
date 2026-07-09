# Data Model — REQ-048

**Date**: 2026-07-07
**Purpose**: Document entity changes for Interview Mode Split + Doubao Card Export

---

## 1. Modified Entities

### 1.1 `interview_sessions` (existing table, ADD columns)

| Column | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `mode` | `text` CHECK IN ('quick_drill', 'full', 'doubao') | NOT NULL | 'full' | 面试模式（新增 US-1/US-4） |
| `max_questions` | `smallint` CHECK BETWEEN 7 AND 15 | NULL | NULL | 用户选择档位 10 / 15；doubao 模式为 NULL |
| `error_question_ids` | `uuid[]` | NULL | NULL | quick_drill 模式下的错题 source_question_id 列表（5 个） |
| `drill_cache_key` | `text` | NULL | NULL | Redis cache key 镜像（用于审计 + 缓存失效） |

**Migration**: `0028_interview_mode_split.py`
- ALTER TABLE interview_sessions ADD COLUMN mode text NOT NULL DEFAULT 'full' CHECK (mode IN ('quick_drill', 'full', 'doubao'));
- ALTER TABLE interview_sessions ADD COLUMN max_questions smallint CHECK (max_questions BETWEEN 7 AND 15) NOT VALID;  -- R16: NOT VALID 避免对 legacy `max_questions=5` 行触发 CheckViolation；后续异步 VALIDATE
- ALTER TABLE interview_sessions VALIDATE CONSTRAINT interview_sessions_max_questions_check;  -- R16: 异步 VALIDATE（在低峰窗口执行，避免生产长事务阻塞）
- ALTER TABLE interview_sessions ADD COLUMN error_question_ids uuid[];
- ALTER TABLE interview_sessions ADD COLUMN drill_cache_key text;
- CREATE INDEX idx_interview_sessions_mode_user ON interview_sessions(user_id, mode);

**Backfill**: 现有 session 全部 `mode='full'` + `max_questions=5`（DEFAULT）。

---

### 1.2 `error_questions` (existing table, ADD columns)

| Column | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `embedding` | `vector(512)` | NULL | NULL | bge-small-zh-v1.5 embedding，HNSW 索引 |
| `embedding_v2` | `vector(1024)` | NULL | NULL | 预留 v2 升 bge-large 时平滑迁移 |
| `embedding_computed_at` | `timestamptz` | NULL | NULL | embedding 计算时间（stale 检测） |
| `embedding_model` | `text` | NULL | NULL | 模型标识（如 'bge-small-zh-v1.5' / 'bge-large-zh-v1.5'） |

**Migration**: `0029_error_questions_embedding.py`
- CREATE EXTENSION IF NOT EXISTS vector;（前置）
- ALTER TABLE error_questions ADD COLUMN embedding vector(512);
- ALTER TABLE error_questions ADD COLUMN embedding_v2 vector(1024);
- ALTER TABLE error_questions ADD COLUMN embedding_computed_at timestamptz;
- ALTER TABLE error_questions ADD COLUMN embedding_model text;
- CREATE INDEX idx_error_questions_embedding ON error_questions USING hnsw (embedding vector_cosine_ops);
- CREATE INDEX idx_error_questions_user_status ON error_questions(user_id, status) WHERE status != 'mastered';
- CREATE INDEX idx_error_questions_tsvector ON error_questions USING gin(to_tsvector('simple', question_text || ' ' || coalesce(answer_text, '')));

**RLS impact**: 已有 RLS policy (`current_setting('app.user_id')::uuid = user_id`) 自动覆盖新列，无需迁移 RLS。

**Pre-existing**: `0014_024_drop_error_questions_archived_at.py` 已 drop 过 archived_at 列，本次复用同一表。

---

### 1.3 `analytics_events` (NEW table)

| Column | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `id` | `uuid` PK | NOT NULL | new_uuid_v7() | |
| `user_id` | `uuid` FK→users | NOT NULL | | |
| `event_type` | `text` | NOT NULL | | 如 'doubao_card_rendered', 'drill_degraded_to_bm25', 'variant_generation_failed' |
| `payload` | `jsonb` | NOT NULL | '{}' | 事件负载 |
| `created_at` | `timestamptz` | NOT NULL | now() | |

**Migration**: `0030_analytics_events.py`

**Index**: CREATE INDEX idx_analytics_events_user_type_created ON analytics_events(user_id, event_type, created_at DESC);

**RLS**: 启用 RLS（user-scoped data），policy 与现有表一致。

---

## 2. New Entities

### 2.1 `embedding_jobs` (NEW table, optional)

> 仅当 embedding 异步任务需要审计 / DLQ 时建。MVP 阶段可省，用 arq 自带 job 状态即可。

| Column | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `id` | `uuid` PK | NOT NULL | | |
| `source_table` | `text` | NOT NULL | | 'error_questions' |
| `source_id` | `uuid` | NOT NULL | | |
| `status` | `text` | NOT NULL | 'pending' | pending / running / success / failed |
| `retry_count` | `smallint` | NOT NULL | 0 | |
| `error_message` | `text` | NULL | | |
| `created_at` / `updated_at` | `timestamptz` | NOT NULL | now() | |

**Decision**: MVP 阶段**不建**此表，依赖 arq 自带 job 状态（arq 0.25+ 默认持久化）。

---

### 2.2 Redis Cache Keys (NEW)

| Key Pattern | TTL | Value | Purpose |
|---|---|---|---|
| `drill_cache:{user_id}:{key_hex}` (R18: key_hex = `sha256(jd_text.encode('utf-8') + error_pool_hash.encode('utf-8'))[:32]`, hash 算法 = SHA256) | 300s (5 min) | JSON list of source_question_id | 「快速补漏」5 分钟复用（FR-015, SC-013, AC-09c 锁定公式） |
| `card_cache:{hash(JD+plan)}` | 7d | PNG/JPG bytes | 卡片输出缓存（FR-063） |

---

## 3. Unchanged Entities (referenced but not modified)

| Entity | Use in REQ-048 |
|---|---|
| `users` | user_id source |
| `jobs` | requirements_md / base_location 读取（US-1 intake 已存在） |
| `interview_reports` | 「快速补漏」/「完整面试」生成报告（不变） |
| `interview_questions` (ai_messages) | 现状记录每题对话 |
| `agent_memories` (semantic_memories) | 长期记忆（不变；与 embedding 检索无关） |

---

## 4. State Machine

### 4.1 ErrorQuestion status（复用现有 service，A-007 标注风险）

```
fresh ──score<6──> reviewing ──score≥6×3──> mastered
  ↑                    │                       │
  └── score<6 ────────┘                       │
  │                                            │
  └── score<6 (regression) ───────────────────┘  mastered → reviewing
```

**待 plan 阶段验证**：现有 `app.modules.errors.service` 是否原生支持 `mastered → reviewing` 反向迁移（FR-041）。如不支持，需补 1 个 ~20 行 PR。

### 4.2 InterviewSession mode (new)

```
[created] ──user picks──> quick_drill | full | doubao
                              │          │       │
                              ↓          ↓       ↓
                       error_questions[]  ...    stop_after_planner
                       source_question_id         (no question_gen)
```

---

## 5. Embedding Lifecycle

### Write Path
1. `sink_error_node` writes `error_questions` row → enqueue `compute_embedding_task` (arq)
2. arq worker → calls `embedding_service` HTTP `/embed` → updates row
3. Retries: 3x exponential backoff (1s / 5s / 25s)

### Read Path
1. `quick_drill_node` triggers Hybrid retrieval
2. BM25: `SELECT ... FROM error_questions WHERE to_tsvector('simple', question_text) @@ plainto_tsquery(:jd_keywords) ORDER BY ... LIMIT 30`
3. Cosine: `SELECT id, embedding <=> :jd_embedding AS distance FROM error_questions ORDER BY distance LIMIT 30`
4. Union: `SELECT * FROM bm25_results UNION SELECT * FROM cosine_results` → 50 candidates
5. Rerank: POST `rerank_service` with `(JD, [50 candidates])` → top 5

### Cache Path
- Cache hit (>80% per SC-013): return cached source_question_id list
- Cache miss: full pipeline above

---

## 6. Validation Rules

| Entity.field | Rule |
|---|---|
| `interview_sessions.mode` | IN ('quick_drill', 'full', 'doubao') |
| `interview_sessions.max_questions` | 7 ≤ N ≤ 15 (CHECK constraint) |
| `interview_sessions.error_question_ids` | length = 5 (CHECK for quick_drill mode) |
| `error_questions.embedding` | dim = 512 (vector type enforces) |
| `error_questions.embedding_v2` | dim = 1024 (reserved) |
| `analytics_events.event_type` | IN whitelist (see R-12) |
| `drill_cache:{...}` | valid JSON list of UUID strings |