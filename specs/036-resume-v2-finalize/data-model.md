# Data Model: 036 Resume v2 Finalize

**Date**: 2026-06-30 | **Plan**: [plan.md](./plan.md)

> Phase 1 — 影响的数据模型与表结构。

---

## Overview

036 仅做 **数据清理 + v1 触点下线**，**不动数据模型 schema**。本节列出清理前/后状态。

---

## Tables Affected

### 1. `resume_branches`（v1）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | v1 分支 ID |
| `user_id` | UUID FK | 用户 ID |
| `name` | varchar | 分支名 |
| `content` | text | Markdown 内容 |
| `status` | enum | draft/optimizing/ready/submitted/archived |
| `is_main` | bool | 是否主分支 |
| `job_id` | UUID FK nullable | 关联岗位 |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**清理前**：可能含历史用户 v1 数据 + 测试数据
**清理后**：行数 = 0；保留 schema 便于回滚
**清理方式**：`TRUNCATE TABLE resume_branches RESTART IDENTITY CASCADE;`

### 2. `resumes_v2`（v2）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK (UUIDv7) | v2 简历 ID |
| `user_id` | UUID FK | 用户 ID |
| `name` | varchar 1-64 | 简历名 |
| `slug` | varchar unique per user | URL slug |
| `tags` | text[] | 标签 |
| `is_public` | bool | 是否公开 |
| `is_locked` | bool | 永久只读锁 |
| `password_hash` | varchar nullable | 公开密码 |
| `data` | jsonb | ResumeDataV2 |
| `version` | int | 乐观并发版本号 |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**清理前**：可能含 mock 测试数据 + 演示数据 + 034 验证时注入的数据
**清理后**：行数 = 0；Playwright 验收时新建 1 份
**清理方式**：`TRUNCATE TABLE resumes_v2 RESTART IDENTITY CASCADE;`

### 3. `resume_statistics_v2`（1:1 with resumes_v2）

| 字段 | 类型 | 说明 |
|---|---|---|
| `resume_id` | UUID PK FK | resumes_v2.id |
| `views` | int | 浏览数 |
| `downloads` | int | 下载数 |
| `last_viewed_at` | timestamptz nullable | |
| `last_downloaded_at` | timestamptz nullable | |

**清理后**：行数 = 0（CASCADE 自动跟随 resumes_v2）

### 4. `resume_analysis_v2`（1:1 with resumes_v2）

| 字段 | 类型 | 说明 |
|---|---|---|
| `resume_id` | UUID PK FK | resumes_v2.id |
| `analysis` | jsonb | AI 分析结果 |
| `status` | enum | 'success' / 'failed' |
| `failure_reason` | text nullable | |

**清理后**：行数 = 0（CASCADE 自动跟随 resumes_v2）

### 5. `outbox`（悬挂外键清理）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | |
| `aggregate_type` | varchar | e.g. 'resume' / 'resume_v2' |
| `aggregate_id` | UUID | 关联的简历 ID |
| `event_type` | varchar | |
| `payload` | jsonb | |
| `created_at` | timestamptz | |
| `processed_at` | timestamptz nullable | |

**清理方式**：
```sql
DELETE FROM outbox
WHERE aggregate_type IN ('resume', 'resume_v2')
  AND aggregate_id NOT IN (SELECT id FROM resumes_v2)
  AND aggregate_id NOT IN (SELECT id FROM resume_branches);
```

---

## Cleanup Script

**文件**：`backend/scripts/cleanup_resume_data.py`

**CLI 接口**（Constitution II）：
```bash
# Dry-run：打印将影响的行数；不实际删除
uv run python -m app.scripts.cleanup_resume_data --dry-run --json

# Execute：执行清理
uv run python -m app.scripts.cleanup_resume_data --execute

# Backup + Execute：先 dump 关键表到 docs/evidence/036-*/db-backup.sql
uv run python -m app.scripts.cleanup_resume_data --backup --execute

# Verify：清理后查行数
uv run python -m app.scripts.cleanup_resume_data --verify --json
```

**退出码**：
- `0` — 成功
- `1` — 操作失败（如 DB 连接中断）
- `2` — 参数错误
- `3` — 安全检查失败（如尝试在生产环境执行）

**输出格式**（默认人类可读）：
```
[2026-06-30 12:34:56] cleanup_resume_data starting...
[2026-06-30 12:34:56] environment detected: dev (safe to proceed)
[2026-06-30 12:34:56] row counts BEFORE cleanup:
  resume_branches: 12
  resumes_v2: 5
  resume_statistics_v2: 5
  resume_analysis_v2: 3
  outbox (resume-related): 28
[2026-06-30 12:34:57] backup written to docs/evidence/036-data-cleanup-20260630-123456/db-backup.sql (42KB)
[2026-06-30 12:34:57] executing cleanup...
[2026-06-30 12:34:58] TRUNCATE resume_branches OK (12 rows)
[2026-06-30 12:34:58] TRUNCATE resumes_v2 CASCADE OK (5 rows)
[2026-06-30 12:34:58] resume_statistics_v2 CASCADE OK (5 rows affected)
[2026-06-30 12:34:58] resume_analysis_v2 CASCADE OK (3 rows affected)
[2026-06-30 12:34:58] outbox cleanup OK (28 rows)
[2026-06-30 12:34:58] row counts AFTER cleanup:
  resume_branches: 0
  resumes_v2: 0
  resume_statistics_v2: 0
  resume_analysis_v2: 0
  outbox (resume-related): 0
[2026-06-30 12:34:58] cleanup complete; logs at docs/evidence/036-data-cleanup-20260630-123456/cleanup.log
```

**`--json` 模式**：
```json
{
  "before": {
    "resume_branches": 12,
    "resumes_v2": 5,
    "resume_statistics_v2": 5,
    "resume_analysis_v2": 3,
    "outbox_resume": 28
  },
  "after": {
    "resume_branches": 0,
    "resumes_v2": 0,
    "resume_statistics_v2": 0,
    "resume_analysis_v2": 0,
    "outbox_resume": 0
  },
  "backup_path": "docs/evidence/036-data-cleanup-20260630-123456/db-backup.sql",
  "duration_seconds": 1.8,
  "exit_code": 0
}
```

---

## RLS Considerations

- `resumes_v2` / `resume_branches` 启用 RLS（per-user isolation）
- 清理脚本以 superuser 或 service role 连接（绕过 RLS）
- 普通用户 session 无法跨用户操作（保留）
- 清理后所有用户的 `/resume` 列表为空

---

## Alembic Migration

**文件**：`backend/alembic/versions/036_cleanup_resume_data.py`

```python
"""036 cleanup resume data (dev only)

Revision ID: 036_cleanup_resume_data
Revises: <latest>
Create Date: 2026-06-30

Idempotent: safe to run multiple times.
"""
from alembic import op
import sqlalchemy as sa

revision = "036_cleanup_resume_data"
down_revision = "<latest>"

def upgrade():
    # 仅 dev 环境执行；生产环境需要 DBA 单独 review
    bind = op.get_bind()
    env = bind.execute(sa.text("SELECT current_setting('app.environment', true)")).scalar()
    if env not in ("dev", "development", "test"):
        raise RuntimeError(f"Refusing to run cleanup in env={env}")
    
    # 1. 清理 outbox 悬挂行
    op.execute("""
        DELETE FROM outbox
        WHERE aggregate_type IN ('resume', 'resume_v2')
          AND aggregate_id NOT IN (SELECT id FROM resumes_v2)
          AND aggregate_id NOT IN (SELECT id FROM resume_branches)
    """)
    
    # 2. 清空 resume_branches（保留 schema）
    op.execute("TRUNCATE TABLE resume_branches RESTART IDENTITY CASCADE")
    
    # 3. 清空 resumes_v2（CASCADE 自动清空子表）
    op.execute("TRUNCATE TABLE resumes_v2 RESTART IDENTITY CASCADE")

def downgrade():
    # 不支持回滚 — 清理脚本本身不可逆
    # 若需回滚，从 db-backup.sql 恢复
    raise NotImplementedError(
        "Cleanup migration is irreversible. "
        "Restore from docs/evidence/036-data-cleanup-*/db-backup.sql if needed."
    )
```

---

## Verification (Post-Cleanup)

用 `mcp__postgres__query` 实查（per memory `feedback_postgres_mcp_validation`）：

```sql
SELECT 
  (SELECT COUNT(*) FROM resume_branches) AS v1_count,
  (SELECT COUNT(*) FROM resumes_v2) AS v2_count,
  (SELECT COUNT(*) FROM resume_statistics_v2) AS stats_count,
  (SELECT COUNT(*) FROM resume_analysis_v2) AS analysis_count,
  (SELECT COUNT(*) FROM outbox WHERE aggregate_type IN ('resume', 'resume_v2')) AS outbox_count;
```

**期望结果**：全部 = 0

---

## Playwright 创建后的最终状态

| 表 | 清理后 | Playwright 创建后 |
|---|---|---|
| `resume_branches` | 0 | 0 |
| `resumes_v2` | 0 | **1**（李祖荫 大模型应用开发工程师） |
| `resume_statistics_v2` | 0 | **1**（初始 views=0, downloads=0） |
| `resume_analysis_v2` | 0 | 0（AI 分析未触发） |
| `outbox (resume)` | 0 | **1~2**（创建事件 + 首次保存事件） |

---

## References

- 036 spec: `specs/036-resume-v2-finalize/spec.md`
- 036 plan: `specs/036-resume-v2-finalize/plan.md`
- 036 research: `specs/036-resume-v2-finalize/research.md`