# Data Model: Personal Ability Profile

**Status**: Phase 1 output · **Date**: 2026-06-16 · **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

> 本文档定义本特性**新增的数据库实体**。本特性复用的已有实体(ability_dimensions、ability_dimensions_history)请参考 Phase 2 data-model。
>
> 全部新表遵循项目标准 Mixin:`UUIDv7PrimaryKeyMixin` + `TimestampedMixin` + `TenantScopedMixin` + `SoftDeletableMixin`(如适用)。
> 全部新表启用 PostgreSQL RLS,策略统一为 `USING (user_id = current_setting('app.user_id', true)::uuid)`。
> 3 张新表在单次 Alembic 迁移 `0007_ability_profile.py` 中创建。

---

## 0. 新增 Mixin / 复用 Mixin

复用 Phase 1 Mixin(见 Phase 1 data-model §0),无新增 Mixin。

| 表 | PrimaryKey | Timestamped | SoftDeletable | TenantScoped | 说明 |
|---|---|---|---|---|---|
| `profile_share_links` | ✅ | ✅ | ❌ | ✅ | 软删无意义,增 revoked_at 标记 |
| `profile_views` | ✅ | ✅(仅 created_at) | ❌ | ❌ | append-only 日志,无 user_id |
| `export_logs` | ✅ | ✅ | ❌ | ✅ | export 完成后保留记录即可 |

---

## 1. `profile_share_links` — 分享链接

**用途**:记录用户生成的能力画像分享链接。每个活跃链接可被公开访问(只读)。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | 分享者 |
| `token` | TEXT | UNIQUE, NOT NULL | — | UUID v7 token,用于公开 URL |
| `pin_hash` | TEXT | NULL | NULL | 可选 4 位 PIN 的 bcrypt hash |
| `expires_at` | TIMESTAMPTZ | NULL | NULL | 可选过期时间;NULL = 永不过期 |
| `revoked_at` | TIMESTAMPTZ | NULL | NULL | 用户手动撤销时间 |
| `last_accessed_at` | TIMESTAMPTZ | NULL | NULL | 上次访问时间 |
| `access_count` | INTEGER | NOT NULL | 0 | 累计访问次数 |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |

### 约束

- `CHECK (length(token) = 36)` — UUID v7 格式
- `CHECK (revoked_at IS NULL OR expires_at IS NULL OR revoked_at < expires_at)` — 撤销时间早于过期时间
- `CHECK (access_count >= 0)`
- 业务不变量:同一用户活跃(未撤销+未过期)分享链接 ≤ 10

### 索引

- `UNIQUE INDEX idx_share_links_token (token)` — 快速查找
- `INDEX idx_share_links_user_id (user_id)` — 用户列表查询
- `INDEX idx_share_links_active (user_id) WHERE revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())` — 活跃链接

### 状态机

```
active ── revoke() ──► revoked
active ── expire() ──► expired (cron 或 on-read 惰性)  
```

---

## 2. `profile_views` — 访问日志

**用途**:记录分享链接的被访问情况(审计/监控目的)。append-only,无 update/delete。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `share_link_id` | uuid | FK → `profile_share_links.id`, NOT NULL | — | 被访问的分享链接 |
| `ip_prefix` | TEXT | NOT NULL | — | IP 前两段(如 "203.0.113.x") |
| `user_agent` | TEXT | NULL | NULL | User-Agent 原始值 |
| `pin_verified` | BOOLEAN | NOT NULL | false | 是否通过 PIN 验证 |
| `viewed_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | 访问时间 |

### 约束

- `CHECK (length(ip_prefix) BETWEEN 3 AND 45)`
- `profile_views` 不启用 RLS(公开资源访问日志,不绑定用户)

### 索引

- `INDEX idx_profile_views_share_link (share_link_id, viewed_at DESC)` — 按链接查询访问记录

---

## 3. `export_logs` — 导出日志

**用途**:跟踪 PDF 导出请求的状态(排队中/完成/失败)。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | 导出者 |
| `status` | TEXT | NOT NULL | `'pending'` | pending / processing / completed / failed |
| `file_path` | TEXT | NULL | NULL | 生成 PDF 的存储路径 |
| `file_size_bytes` | INTEGER | NULL | NULL | PDF 文件大小 |
| `error_message` | TEXT | NULL | NULL | 失败原因 |
| `requested_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `completed_at` | TIMESTAMPTZ | NULL | NULL | 完成/失败时间 |
| `expires_at` | TIMESTAMPTZ | NOT NULL | `now() + interval '24 hours'` | 文件自动清理时间 |

### 约束

- `CHECK (status IN ('pending','processing','completed','failed'))` 
- `CHECK (file_size_bytes IS NULL OR file_size_bytes > 0)`
- `CHECK (completed_at IS NULL OR completed_at >= requested_at)`
- `CHECK (status != 'completed' OR file_path IS NOT NULL)` — 完成状态必须存在文件

### 索引

- `INDEX idx_export_logs_user (user_id, requested_at DESC)` — 用户查询导出历史
- `INDEX idx_export_logs_expires (expires_at) WHERE status = 'completed'` — 清理任务

### 状态机

```
pending ── worker pickup ──► processing ── worker done ──► completed
processing ── worker error ──► failed
```

---

## 4. 与 Phase 2 `ability_dimensions` 的关系

本特性**不新增**能力维度相关的表。所有能力数据来自已有的:

- **`ability_dimensions`** — 6 维度 actual_score / ideal_score / sub_scores 数据
- **`ability_dimensions_history`** — 历史快照(用于成长曲线)

本特性新增的 `profile_share_links` / `profile_views` / `export_logs` 与能力维度表无直接 FK 关系,通过 `user_id` 关联。

```

ability_dimensions (Phase 2)
├── id / user_id / dimension_key / actual_score / ideal_score / sub_scores / source / is_active
├── 静态 6 行 per user,由 service 层聚合展示
└── ability_dimensions_history (Phase 2)
    └── 时间序列数据 → 成长曲线

profile_share_links (NEW)
└── user_id → users.id

profile_views (NEW)
└── share_link_id → profile_share_links.id

export_logs (NEW)
└── user_id → users.id
```
