# Data Model: 性能与可观测性增强

**Date**: 2026-06-22

## Entity Changes

### error_questions (索引新增, 字段不变)

**Existing columns (unchanged)**:
- `id` UUID PK
- `user_id` UUID FK → users.id
- `status` TEXT (fresh / practicing / mastered)
- `frequency` INTEGER
- `created_at` TIMESTAMPTZ
- `deleted_at` TIMESTAMPTZ NULLABLE

**New index**:
```sql
CREATE INDEX CONCURRENTLY idx_error_questions_user_status_freq_created
  ON error_questions (user_id, status, frequency, created_at)
  WHERE deleted_at IS NULL;
```

**Migration notes**:
- 使用 `CONCURRENTLY` 避免长锁表（生产环境）。
- Alembic 需 `op.execute()` 手写 SQL，因 Alembic `create_index` 不支持 `postgresql_concurrently` 参数（需 `op.create_index(..., postgresql_concurrently=True)` 在新版 SQLAlchemy 支持）。
- 部分索引通过 `postgresql_where="deleted_at IS NULL"` 参数指定。
- 回滚: `DROP INDEX CONCURRENTLY idx_error_questions_user_status_freq_created`。

### resume_branches (响应字段扩展, 表结构不变)

**Existing columns (unchanged)**:
- `id` UUID PK
- `user_id` UUID FK
- `title` TEXT
- `parent_id` UUID NULLABLE
- `created_at` / `updated_at` TIMESTAMPTZ

**Response virtual fields (不落库)**:
- `version_count: INTEGER` — 该分支下的版本数（聚合得出）
- `block_count: INTEGER` — 该分支下所有版本的所有块数总和（聚合得出）

**Aggregation logic**:
```python
# service.py 伪代码
branches = await session.execute(
    select(ResumeBranch)
    .options(selectinload(ResumeBranch.versions).selectinload(ResumeVersion.blocks))
    .where(ResumeBranch.user_id == user_id, ResumeBranch.deleted_at.is_(None))
)
return [
    {
        **branch.to_dict(),
        "version_count": len(branch.versions),
        "block_count": sum(len(v.blocks) for v in branch.versions),
    }
    for branch in branches
]
```

### ai_messages (不改表, 仅日志关联)

**Existing column** (already in schema):
- `request_id` TEXT NULLABLE — 既有字段，本 feature 确保所有写入路径填值。

**No schema change**, 仅 `llm_client.py` 日志和 `ai_messages` 写入路径从 ContextVar 读 request_id。

## Metrics Entities (in-memory, prometheus_client)

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `llm_quota_exhausted_total` | Counter | `user_id` | LLM 配额耗尽事件总数 |
| `llm_quota_available` | Gauge | `user_id` | 当前可用 LLM 配额 |
| `checkpointer_reconnect_total` | Counter | — | checkpointer 重连次数 |
| `ws_connections_active` | Gauge | — | 当前活跃 WebSocket 连接数 |
| `arq_jobs_queued` | Gauge | `queue` | ARQ 队列中待处理任务数 |
| `arq_jobs_failed_total` | Counter | `queue` | ARQ 任务失败总数 |

**Registry**: 使用 `prometheus_client.REGISTRY`（默认全局 registry），既有 5 类指标（HTTP / auth / resume / lock / outbox）继续使用。

## No Other Entity Changes

- `users` / `resume_versions` / `resume_blocks` / `jobs` / `error_questions` 表结构不变。
- `checkpoints` / `checkpoint_writes` / `checkpoint_blobs` 表（LangGraph checkpointer）不变。
- 所有 API 响应契约不变（除 `resume_branches` 响应新增 `version_count` / `block_count`）。
