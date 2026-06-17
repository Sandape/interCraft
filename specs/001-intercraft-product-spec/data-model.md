# Data Model: InterCraft Phase 1

**Status**: Phase 1 output · **Date**: 2026-06-12 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

> 本文档定义 Phase 1 涉及的**全部数据库实体**、SQLAlchemy 模型骨架、字段约束、关系、索引,以及与 `src/data/mockData.ts` 的字段映射。
> 全部业务表统一通过 Mixin 注入 `id / user_id / created_at / updated_at / deleted_at`(spec A13 修订)。
> 全部业务表启用 PostgreSQL RLS,策略统一为 `USING (user_id = current_setting('app.user_id', true)::uuid)`(spec FR-004)。

---

## 0. Mixins(在 `app/domain/mixins.py`)

所有业务表 MUST 继承下列 Mixin。Mixins 本身不创建表,仅注入列。

```python
# app/domain/mixins.py
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

class UUIDv7PrimaryKeyMixin:
    """主键 = uuidv7(时间有序,索引友好)。DEC-2:自写 app/core/ids.py::new_uuid_v7()。"""
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid_v7,  # 从 app.core.ids 导入
        server_default=func.least(  # 让 PG 端生成占位(主键默认总是应用层生成)
            text("gen_random_uuid()")  # 仅当应用层未传时兜底
        ),
    )

class TimestampedMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )

class SoftDeletableMixin:
    """软删除:deleted_at IS NULL 视为存活。所有 Repository 默认过滤。"""
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

class TenantScopedMixin:
    """租户隔离:user_id 必须来自 JWT。RLS 在数据库层强制,M05 启用。"""
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
```

**Phase 1 业务表组合**:
- `users` → `UUIDv7PrimaryKeyMixin + TimestampedMixin + SoftDeletableMixin`(无 TenantScopedMixin:用户表自身就是租户根)
- `user_credentials` → `TenantScopedMixin + TimestampedMixin`(无独立主键,与 user_id 1:1)
- `auth_sessions` → `UUIDv7PrimaryKeyMixin + TimestampedMixin + SoftDeletableMixin + TenantScopedMixin`
- `resume_branches` → `UUIDv7PrimaryKeyMixin + TimestampedMixin + SoftDeletableMixin + TenantScopedMixin`
- `resume_blocks` → `UUIDv7PrimaryKeyMixin + TimestampedMixin + SoftDeletableMixin + TenantScopedMixin`
- `resume_versions` → `UUIDv7PrimaryKeyMixin + TimestampedMixin + TenantScopedMixin`(immutable,无 `updated_at` / `deleted_at`)

---

## 1. 实体清单(Phase 1)

| # | 表名 | 实体 | 文档 | 落地阶段 |
|---|---|---|---|---|
| E-1 | `users` | User | spec §3.2 / M04 §4 | Phase 1 |
| E-2 | `user_credentials` | UserCredential | spec §3.2 / M04 §4 | Phase 1(表落地,凭据写入 Phase 2 启用) |
| E-3 | `auth_sessions` | AuthSession | spec §3.2 / M05 §4 | Phase 1 |
| E-4 | `resume_branches` | ResumeBranch | spec §3.2 / M06 §4 | Phase 1 |
| E-5 | `resume_blocks` | ResumeBlock | spec §3.2 / M06 §4 | Phase 1 |
| E-6 | `resume_versions` | ResumeVersion | spec §3.2 / M07 §4 | Phase 1 |

**显式不建表**(Phase 2-6 范畴,Phase 1 Alembic 迁移不含):`interview_*` / `error_questions` / `ability_*` / `tasks` / `activities` / `jobs` / `audit_logs` / `ai_*` / `checkpoints` / `tools` / `user_settings` / `subscriptions`。

---

## 2. E-1 · `users`(User)

**用途**:账号主体。R 流程(注册/登录)的核心。`subscription` / `monthly_token_*` 字段为 Phase 2 准备,Phase 1 仅落字段、不读不写(SPEC FR-002 / M04 §4)。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | UUIDPrimaryKeyMixin |
| `email` | TEXT | NOT NULL, UNIQUE 约束 | — | 注册用主键 |
| `email_sha256` | BYTEA | NOT NULL, UNIQUE 约束 | — | sha256(email.lower()),索引加速查询(同表不能 email+email_sha256 都建唯一,只 email_sha256) |
| `phone` | TEXT | NULL | NULL | Phase 1 不使用 |
| `phone_sha256` | BYTEA | NULL, UNIQUE 约束 | NULL | Phase 1 不使用 |
| `display_name` | TEXT | NULL | NULL | 用户昵称 |
| `password_hash` | TEXT | NOT NULL | — | bcrypt(cost=12) |
| `status` | TEXT | NOT NULL | `'active'` | active / soft_deleted / purged / frozen(M20) |
| `title` | TEXT | NULL | NULL | 岗位(求职目标) |
| `years_of_experience` | INT | NULL | NULL | 0-50 |
| `target_role` | TEXT | NULL | NULL | 目标岗位 |
| `llm_provider_pref` | JSONB | NULL | NULL | Phase 1 不使用 |
| `subscription` | TEXT | NOT NULL | `'free'` | free / pro / enterprise(Phase 6 启用切换 UI) |
| `monthly_token_quota` | INT | NOT NULL | 100000 | Phase 2 启用 |
| `monthly_token_used` | INT | NOT NULL | 0 | Phase 2 启用 |
| `quota_reset_at` | TIMESTAMPTZ | NOT NULL | `func.now()`(注册时) | Phase 2 重置 |
| `allow_concurrent_sessions` | BOOL | NOT NULL | TRUE | M05 §7(预留) |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | TimestampedMixin |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | TimestampedMixin |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | SoftDeletableMixin |

### 索引

- `UNIQUE (email)` —— 业务唯一
- `UNIQUE (email_sha256)` —— 索引加速
- `INDEX (status, deleted_at)` —— 加速「找活跃用户」

### 关系

- 1:N → `auth_sessions`(E-3)
- 1:N → `resume_branches`(E-4)
- 1:N → `resume_blocks`(E-5,通过 user_id)
- 1:N → `resume_versions`(E-6,通过 user_id)
- 1:1 → `user_credentials`(E-2)

---

## 3. E-2 · `user_credentials`(UserCredential)

**用途**:敏感凭据(身份证 / 真实姓名 / 薪资)加密存储。Phase 1 表落地但**不**开放 API(对应 spec FR-005 的延伸;M04 PATCH `/users/me/credentials` 在 Phase 2 启用)。Phase 1 仅用于审计可观测性验证(写一条假数据 → 读出来 → 验证解密)。

### 字段

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `user_id` | uuid | PK + FK → `users.id` | 1:1,无独立 id |
| `id_card_enc` | BYTEA | NULL | AES-256-GCM(密文 + nonce + tag 拼接) |
| `real_name_enc` | BYTEA | NULL | 同上 |
| `salary_range_enc` | BYTEA | NULL | 同上(本字段 M03 §6 标识为敏感) |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

### 索引

- 主键即 `user_id`(无额外索引)

### 加密格式(DEC-5 + M03 §6 决议)

```
plaintext
  ↓ AES-256-GCM(key=MASTER_KEY, nonce=random 12B, aad={user_id, field_name})
  ↓ ciphertext ‖ tag(16B)
  ↓ 拼接:key_version(1B) ‖ nonce(12B) ‖ ciphertext ‖ tag
  → 存 BYTEA 列
```

> AAD(additional authenticated data)绑定 user_id + 字段名,防止跨字段密文调换攻击(M03 §6 决议)。

---

## 4. E-3 · `auth_sessions`(AuthSession)

**用途**:多端会话 + 设备指纹 + 5 设备限制。RLS 隔离,5 设备上限按 `last_seen_at` 裁剪。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | TenantScopedMixin |
| `device_id` | TEXT | NOT NULL, UNIQUE | — | sha256(UA + screen + tz + lang) |
| `device_name` | TEXT | NULL | NULL | 用户自定义(Phase 1 暂不开放编辑) |
| `device_fingerprint` | TEXT | NOT NULL | — | 原始指纹(可读,供调试) |
| `last_seen_ip` | INET | NULL | NULL | Phase 1 由 middleware 填充 |
| `last_seen_ua` | TEXT | NULL | NULL | Phase 1 由 middleware 填充 |
| `refresh_token_hash` | TEXT | NOT NULL | — | sha256(refresh_jti) |
| `expires_at` | TIMESTAMPTZ | NOT NULL | — | refresh 过期时间(注册时 +7d) |
| `last_seen_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | 「找最早活跃设备」用 |
| `trusted_at` | TIMESTAMPTZ | NULL | NULL | Phase 1 字段就位,业务不启用(留 v1.1) |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | 踢出 = soft_delete |

### 索引

- `UNIQUE (device_id)` —— 设备指纹冲突保护(RK-4)
- `INDEX (user_id, last_seen_at DESC)` —— 5 设备上限裁剪
- `INDEX (refresh_token_hash)` —— refresh 验签快速查

### 约束

- `CHECK (length(device_id) = 64)` —— sha256 hex
- `CHECK (length(refresh_token_hash) = 64)` —— sha256 hex

### 状态机(逻辑)

```
register() ──► active ──► soft_deleted (登出/踢出/refresh 过期/被吊销)
                 │
                 └──► trusted (v1.1,Phase 1 不启用)
```

### 关系

- N:1 → `users`(E-1)

---

## 5. E-4 · `resume_branches`(ResumeBranch)

**用途**:树形分支(核心简历 + N 个针对不同公司的派生)。Notion 式简历的顶层容器。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | |
| `parent_id` | uuid | NULL, FK → `resume_branches.id` (self-ref) | NULL | 树形结构;`is_main=true` 的核心简历 `parent_id IS NULL` |
| `name` | TEXT | NOT NULL | — | 例「字节跳动 · 高级前端」 |
| `company` | TEXT | NULL | NULL | 目标公司 |
| `position` | TEXT | NULL | NULL | 目标岗位 |
| `status` | TEXT | NOT NULL | `'draft'` | draft / optimizing / ready / submitted / archived(M06 §6) |
| `match_score` | NUMERIC(5,2) | NULL | NULL | 0.00-100.00(AI 评估后写入,Phase 1 不写) |
| `is_main` | BOOL | NOT NULL | FALSE | 主简历(每用户唯一),`is_main=true` 时 `parent_id IS NULL` |
| `is_pinned` | BOOL | NOT NULL | FALSE | UI 置顶 |
| `last_edited_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | 编辑器写入时更新 |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | |

### 约束

- `CHECK (is_main = FALSE OR parent_id IS NULL)` —— 主简历无父
- `UNIQUE (user_id, is_main) WHERE is_main = TRUE` partial index —— 每用户 1 个主简历
- `CHECK (status IN ('draft','optimizing','ready','submitted','archived'))`

### 索引

- `INDEX (user_id, is_main DESC, last_edited_at DESC)` —— 「我的主简历 + 最近编辑」
- `INDEX (user_id, deleted_at)` —— 默认过滤
- `INDEX (parent_id)` —— 树形遍历

### 关系

- N:1 → `users`(E-1)
- self-ref: `parent_id` → `resume_branches.id`
- 1:N → `resume_blocks`(E-5,`branch_id`,无外键约束,COW 写时复制时不需要)
- 1:N → `resume_versions`(E-6)

### COW 写时复制(M06 §6)

新建分支时:
1. `INSERT INTO resume_branches (...)` 一条,**不**复制 blocks
2. 查询时,若 branch.blocks 为空,fallback 到 `parent.blocks`(用 UNION VIEW 或应用层 join)

首次编辑某块时(Phase 1 简化:克隆全部父分支 blocks,避免 view 复杂度;Phase 2 优化为真 COW):
1. `INSERT INTO resume_blocks (..., branch_id=new_id) SELECT ... FROM resume_blocks WHERE branch_id=parent_id`
2. 编辑目标块

> **Phase 1 简化说明**:M06 §6 的真 COW 涉及 UNION VIEW,实现复杂度高,Phase 1 采用「克隆全部」策略(每分支 ≤ 100 块,代价 < 10KB,符合 SC)。Phase 2 在 SLA 调研后决定是否切真 COW。

---

## 6. E-5 · `resume_blocks`(ResumeBlock)

**用途**:Notion 式简历块。7 类,支持拖拽排序、折叠、即时编辑。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | TenantScopedMixin(允许 RLS) |
| `branch_id` | uuid | NOT NULL | — | 逻辑 FK → `resume_branches.id`(应用层校验,无 DB 外键以支持 COW) |
| `type` | TEXT | NOT NULL | — | heading / summary / experience / project / skill / education / custom(M06 §4) |
| `title` | TEXT | NULL | NULL | 块标题(heading 必填,其他可选) |
| `content_md` | TEXT | NOT NULL | — | Markdown 原文 |
| `content_html` | TEXT | NULL | NULL | 派生缓存(M06 §6,Phase 1 不生成,NULL) |
| `meta` | JSONB | NULL | NULL | 自由扩展;`experience` 含 company/role/period;`skill` 含 tags[] |
| `order_index` | TEXT | NOT NULL | — | 字符串分数(fractional-indexing,DEC-3) |
| `collapsed` | BOOL | NOT NULL | FALSE | 折叠状态(不入版本快照,M07 §6) |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | |
| `deleted_at` | TIMESTAMPTZ | NULL | NULL | |

### 约束

- `CHECK (type IN ('heading','summary','experience','project','skill','education','custom'))`
- `CHECK (length(order_index) > 0 AND length(order_index) < 64)` —— 字符串分数健康度

### 索引

- `INDEX (branch_id, order_index) WHERE deleted_at IS NULL` —— 块列表查询
- `INDEX (user_id, deleted_at)` —— RLS 隔离
- `INDEX (user_id, type, deleted_at)` —— 类型过滤(Phase 2+ 报表用)

### 关系

- N:1 → `users`(E-1)
- 逻辑 N:1 → `resume_branches`(E-4,无 DB 外键)

### `meta` 字段 schema(各 type 强约束)

> Phase 1 暂不启用 JSON Schema 校验(简化),仅文档约定。前端编辑器按 type 渲染对应表单。

| `type` | `meta` 期望 schema |
|---|---|
| `heading` | `{}`(无扩展) |
| `summary` | `{ "tone"?: string }` |
| `experience` | `{ "company": string, "role": string, "start": "YYYY-MM", "end"?: "YYYY-MM" \| "present", "tags"?: string[] }` |
| `project` | `{ "name": string, "role"?: string, "start"?: "YYYY-MM", "end"?: "YYYY-MM", "tags"?: string[] }` |
| `skill` | `{ "category": string, "tags": string[] }` |
| `education` | `{ "school": string, "major"?: string, "degree"?: string, "start"?: "YYYY", "end"?: "YYYY" }` |
| `custom` | `Record<string, any>` |

---

## 7. E-6 · `resume_versions`(ResumeVersion)

**用途**:完整快照 + diff(JSON Patch RFC 6902)混合存储。手动/AI/定时触发。

### 字段

| 字段 | 类型 | 约束 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | uuid v7 | PK | `new_uuid_v7()` | |
| `user_id` | uuid | FK → `users.id`, NOT NULL | — | TenantScopedMixin |
| `branch_id` | uuid | NOT NULL | — | 逻辑 FK |
| `version_no` | INT | NOT NULL | — | 单分支内递增 |
| `label` | TEXT | NULL | NULL | 用户备注(如「投递字节前定稿」) |
| `is_full_snapshot` | BOOL | NOT NULL | — | M07 §4 决议 |
| `snapshot_json` | JSONB | NULL | NULL | 完整快照,`is_full_snapshot=true` 时 NOT NULL |
| `base_version_id` | uuid | NULL, FK → `resume_versions.id` (self-ref) | NULL | diff 起点 |
| `diff_patch` | JSONB | NULL | NULL | RFC 6902 patch 数组,`is_full_snapshot=false` 时 NOT NULL |
| `author_type` | TEXT | NOT NULL | — | user / ai |
| `actor_id` | uuid | NULL | NULL | user_id 或 agent_run_id |
| `trigger` | TEXT | NOT NULL | — | manual / auto / ai(M07 §4) |
| `created_at` | TIMESTAMPTZ | NOT NULL | `func.now()` | immutable |

### 约束

- `UNIQUE (branch_id, version_no) WHERE deleted_at IS NULL`(实际无 deleted_at,直接 `UNIQUE (branch_id, version_no)`)
- `CHECK (is_full_snapshot = TRUE  → snapshot_json IS NOT NULL AND diff_patch IS NULL)`
- `CHECK (is_full_snapshot = FALSE → diff_patch IS NOT NULL AND base_version_id IS NOT NULL AND snapshot_json IS NULL)`
- `CHECK (author_type IN ('user','ai'))`
- `CHECK (trigger IN ('manual','auto','ai'))`

### 索引

- `UNIQUE (branch_id, version_no)` —— 单调递增
- `INDEX (branch_id, is_full_snapshot DESC, version_no DESC)` —— 「最近 full snapshot」加速 diff 还原
- `INDEX (user_id, created_at DESC)` —— 用户时间线

### 关系

- N:1 → `users`(E-1)
- N:1 → `resume_branches`(E-4,逻辑 FK)
- self-ref: `base_version_id` → `resume_versions.id`

### 存储策略(M07 §6)

| 触发 | `is_full_snapshot` | `trigger` | `author_type` |
|---|---|---|---|
| 用户点击「保存版本」 | TRUE | manual | user |
| AI 优化后(Phase 5) | TRUE | ai | ai |
| 每 10 次自动快照 | TRUE | auto | user |
| 其他自动(30 min 一次,有变化) | FALSE | auto | user |
| 用户初始化分支(创建空快照) | TRUE | manual | user |
| 回滚(rollback 端点) | 创建新分支,不直接写 version | — | — |

### 完整快照 schema(`snapshot_json`)

```json
{
  "branch": {
    "id": "uuid",
    "name": "string",
    "company": "string|null",
    "position": "string|null",
    "status": "draft|optimizing|ready|submitted|archived"
  },
  "blocks": [
    {
      "id": "uuid",
      "type": "heading|summary|experience|project|skill|education|custom",
      "title": "string|null",
      "content_md": "string",
      "meta": "object|null",
      "order_index": "string"
    }
  ]
}
```

> `collapsed` 字段被剔除(M07 §6);`user_id` / `branch_id` / `created_at` 不重复。

### diff patch(`diff_patch`)

标准 RFC 6902 patch 数组,例:
```json
[
  { "op": "replace", "path": "/branch/status", "value": "ready" },
  { "op": "add", "path": "/blocks/-", "value": { "id": "...", "type": "skill", "...": "..." } },
  { "op": "remove", "path": "/blocks/2" }
]
```

---

## 8. Alembic 迁移策略

`migrations/versions/0001_initial.py` **一次**创建全部 6 张表 + 启用 RLS,按依赖顺序:
1. `users`(无依赖)
2. `user_credentials`(依赖 users)
3. `auth_sessions`(依赖 users)
4. `resume_branches`(依赖 users,self-ref)
5. `resume_blocks`(依赖 users + 逻辑 resume_branches)
6. `resume_versions`(依赖 users + 逻辑 resume_branches,self-ref)

**每张表迁移步骤**:
1. `op.create_table(...)`
2. `op.create_index(...)`
3. `op.execute("ALTER TABLE x ENABLE ROW LEVEL SECURITY;")`
4. `op.execute("ALTER TABLE x FORCE ROW LEVEL SECURITY;")`(强制表 owner 也受 RLS 约束)
5. `op.execute("CREATE POLICY x_user_isolation ON x USING (user_id = current_setting('app.user_id', true)::uuid);")`

**降级**:`op.drop_table(...)` 即可(连带 RLS 策略)。

**后续迁移命名**:`0002_add_<feature>.py`,Phase 2 起追加。Phase 1 一次到位。

---

## 9. RLS 策略统一模板

```sql
-- 启用 RLS
ALTER TABLE resume_branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_branches FORCE ROW LEVEL SECURITY;  -- 强制表 owner 也走 RLS

-- 策略
CREATE POLICY resume_branches_user_isolation ON resume_branches
  USING (user_id = current_setting('app.user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);
```

**`auth_sessions` 例外**:策略包含「查询自己 user 的会话」+「登录时(无 user context)允许 SELECT/UPDATE 通过 refresh_token_hash 找到 session」。Phase 1 简化:**未登录前不查 sessions**,登录成功后所有查询都带 user_context → RLS 通过。**故 auth_sessions 同样使用统一策略**。

**`users` 表特殊**:每条记录属于一个 user,策略与上述一致。但是 `register` 流程需要「无 user_context 插入」—— Phase 1 解决:
- 注册路由使用独立 DB session(不走 `get_db_session(user_id=...)` 依赖),**临时禁用 RLS**:`SET LOCAL row_security = off;`(只对 `INSERT INTO users` 这一刻)
- 注册成功后 → 用真实 user_id 走正常路径
- 集成测试覆盖:注册后用该 user token 查 → 200;用其他 user token 查 → 403/空

---

## 10. mockData.ts 字段映射(Phase 1 涉及)

| mockData 字段 | 对应后端表 / 字段 | Phase 1 状态 |
|---|---|---|
| `currentUser.id` | `users.id` | ✓ 真实 API |
| `currentUser.name` | `users.display_name` | ✓ |
| `currentUser.email` | `users.email` | ✓ |
| `currentUser.title` | `users.title` | ✓ |
| `currentUser.yearsOfExperience` | `users.years_of_experience` | ✓ |
| `currentUser.targetRole` | `users.target_role` | ✓ |
| `currentUser.subscription` | `users.subscription` | ✓(默认 'free') |
| `currentUser.avatar` | 暂无字段(Phase 6 启用头像) | mockData 保留 |
| `ResumeBranch.id` | `resume_branches.id` | ✓ |
| `ResumeBranch.name / company / position` | 一致 | ✓ |
| `ResumeBranch.status` | 一致(枚举对齐) | ✓ |
| `ResumeBranch.matchScore` | `match_score` | ✓(snake_case) |
| `ResumeBranch.lastEdited` | `last_edited_at` | ✓(snake_case) |
| `ResumeBranch.versionCount` | 聚合查询(`SELECT COUNT(*) FROM resume_versions`) | ✓(repository 提供 `get_version_count(branch_id)`) |
| `ResumeBranch.isMain / isPinned` | `is_main` / `is_pinned` | ✓(snake_case) |
| `ResumeBranch.parentId` | `parent_id` | ✓ |
| `ResumeBlock.id / type / title / content / meta` | `resume_blocks.id / type / title / content_md / meta` | ✓ |
| `ResumeBlock.collapsed` | `collapsed` | ✓ |

**Phase 1 不涉及**的 mockData 字段(继续走 mock,Phase 2-6 迁移):`InterviewHistory` / `interviewMessages` / `ErrorQuestion` / `abilityDimensions` / `jobs` / `resources` / `dashboardMetrics` / `activities` / `tasks` / `sessions`(前端设备列表)。

---

## 11. 状态机总览

```
[ User ]
  active ──► soft_deleted (Phase 6 M20 注销)
              ──► purged (90 天后物理清除,Phase 6)

[ AuthSession ]
  active ──► soft_deleted
    ├── 登出
    ├── refresh 过期
    ├── 主动踢出(其他设备)
    └── 5 设备上限裁剪

[ ResumeBranch ]
  draft ──► optimizing ──► ready ──► submitted
    ▲                              │
    └──────── 撤回后修改 ───────────┘(允许,生成新版本)
       archived(任意时刻)

[ ResumeVersion ]  immutable,append-only

[ ResumeBlock ]    软删除 = `deleted_at = now()`
```

---

## 12. 引用

- [PostgreSQL RLS](https://www.postgresql.org/docs/15/ddl-rowsecurity.html)
- [SQLAlchemy 2.0 Mapped](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#declarative-mapping-with-typed-mapped-attributes)
- Historical persistence requirement review folded into this spec.
- M04 §4, M05 §4, M06 §4, M07 §4
- 决议 DEC-2 (uuidv7) / DEC-3 (fractional-indexing) / DEC-4 (jsonpatch) / DEC-5 (PyJWT)
