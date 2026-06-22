# Data Model: Phase 2 (M5-M11) spec/code 偏差审计与修复

**Date**: 2026-06-22

## Entity Changes

### jobs (新增 4 列)

**Existing columns** (unchanged):
- `id` UUID PK
- `user_id` UUID FK
- `title` / `company` / `salary_range_text` / `status` / `source` / `status_history` JSONB
- `created_at` / `updated_at` / `deleted_at` TIMESTAMPTZ

**New columns** (FR-001):

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `offer_salary_text` | TEXT | Yes | Offer 薪资文本（如 "30K-50K/月"），用户在 status=offered/accepted 时录入 |
| `offer_contact_name` | TEXT | Yes | Offer 联系人姓名 |
| `offer_contact_info` | TEXT | Yes | Offer 联系方式（电话/邮箱/微信）|
| `offer_deadline_at` | TIMESTAMPTZ | Yes | Offer 截止日期 |

**Migration** (`add_jobs_offer_fields.py`):
```python
def upgrade():
    op.add_column("jobs", sa.Column("offer_salary_text", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("offer_contact_name", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("offer_contact_info", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("offer_deadline_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column("jobs", "offer_deadline_at")
    op.drop_column("jobs", "offer_contact_info")
    op.drop_column("jobs", "offer_contact_name")
    op.drop_column("jobs", "offer_salary_text")
```

### status_history (字段名对齐, 无表结构变更)

**Existing schema** (unchanged): `jobs.status_history` 是 JSONB 列，元素结构后端已用 `{from, to, at, note}`。

**Frontend type definition change** (FR-020):
```typescript
// Before
interface StatusHistoryEntry {
  from_status: string;
  to_status: string;
  changed_at: string;
  note?: string;
}

// After (aligned with backend)
interface StatusHistoryEntry {
  from: string;
  to: string;
  at: string;
  note?: string;
}
```

### error_questions (移除 archived_at 列)

**Existing columns** (to remove):
- `archived_at` TIMESTAMPTZ — 移除

**Migration** (`drop_error_questions_archived_at.py`):
```python
def upgrade():
    # 先迁移既有数据 (archived_at 非空 → deleted_at)
    op.execute("""
        UPDATE error_questions
        SET deleted_at = archived_at
        WHERE archived_at IS NOT NULL AND deleted_at IS NULL
    """)
    op.drop_column("error_questions", "archived_at")

def downgrade():
    op.add_column("error_questions", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
```

**FSM change** (`errors/service.py`):

Before:
```python
VALID_TRANSITIONS = {
    "fresh": {"practicing", "archived"},
    "practicing": {"mastered", "fresh", "archived"},  # 错误: 允许回退 + archived
    "mastered": {"fresh", "archived"},  # reset
}
```

After:
```python
VALID_TRANSITIONS = {
    "fresh": {"practicing"},
    "practicing": {"mastered"},
    "mastered": {"fresh"},  # reset only
}
```

### ability_profile_shares (移除 pin_hash 列)

**Existing columns** (to remove):
- `pin_hash` TEXT — 移除

**Migration** (`drop_ability_profile_pin_profileview.py`):
```python
def upgrade():
    op.drop_column("ability_profile_shares", "pin_hash")
    op.drop_table("profile_views")

def downgrade():
    op.add_column("ability_profile_shares", sa.Column("pin_hash", sa.Text(), nullable=True))
    op.create_table("profile_views", ...)  # 重建结构复杂, 建议测试环境 only
```

### profile_views (整表移除)

**Drop table**: `profile_views`（IP 追踪表，spec 006 未覆盖）。

**Migration**: 同 `drop_ability_profile_pin_profileview.py` 中 `op.drop_table("profile_views")`。

## No Other Entity Changes

- `resume_branches` / `resume_versions` / `resume_blocks` 不变。
- `ai_messages` / `outbox` (后端 outbox 表，与前端 outbox 不同) 不变。
- `users` / `auth_sessions` 不变。
- LangGraph checkpointer 表不变。

## API Contract Changes

### New Fields in `GET /api/v1/jobs/{id}` Response

```json
{
  "id": "uuid",
  "title": "...",
  "status": "offered",
  "status_history": [
    {"from": "fresh", "to": "applied", "at": "2026-06-22T10:00:00Z", "note": "投递"},
    {"from": "applied", "to": "interviewing", "at": "2026-06-22T11:00:00Z", "note": "面试邀请"},
    {"from": "interviewing", "to": "offered", "at": "2026-06-22T15:00:00Z", "note": "Offer 录入"}
  ],
  "offer_salary_text": "30K-50K/月",
  "offer_contact_name": "HR 张女士",
  "offer_contact_info": "hr@example.com / 13800138000",
  "offer_deadline_at": "2026-06-29T00:00:00Z"
}
```

### Removed Fields

- `GET /api/v1/ability-profile/shares/{id}` 响应不再含 `pin_hash` / `has_pin`。
- `GET /api/v1/ability-profile/shares/{id}/views` 端点移除（ProfileView 表删除）。

### Changed Endpoints

- `GET /api/v1/ability-profile/export-pdf`: 同步返回 PDF（Content-Type + Content-Disposition），不再返回 `{job_id}` JSON。
- `PATCH /api/v1/error-questions/{id}/status`: 对 `archived` 相关转换返回 422。
- `PATCH /api/v1/jobs/{id}`: 在 status=offered/accepted 时接受 4 个 offer_* 字段。
