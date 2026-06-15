# Data Model: Phase 6 — 全局能力收尾

## 新增与变更实体

### 1. User (变更)

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|---|---|---|---|---|
| `role` | TEXT | NOT NULL, CHECK IN ('user','admin') | `'user'` | 用户角色。admin 用于 M22 审计端点 |
| `scheduled_purge_at` | TIMESTAMPTZ | NULL | NULL | 计划物理清除时间,发起注销后 90 天 |
| `cancellation_deadline` | TIMESTAMPTZ | NULL | NULL | 冷静期截止时间,发起注销后 7 天 |
| `subscription` | TEXT | NOT NULL, CHECK IN ('free','pro','enterprise') | `'free'` | 订阅方案,Phase 1 已有字段 |
| `monthly_token_quota` | INTEGER | NOT NULL | `500000` | 月度 token 配额,Phase 4 已有字段 |
| `monthly_token_used` | INTEGER | NOT NULL | `0` | 月度已用 token,Phase 4 已有字段 |

**状态流转**:
```
active ──(用户发起注销)──► soft_deleted (scheduled_purge_at = NOW+90d, cancellation_deadline = NOW+7d)
soft_deleted ──(7 天内取消)──► active (scheduled_purge_at/cancellation_deadline 清空)
soft_deleted ──(90 天后 cron)──► purged (purge_expired_accounts 每日巡检)
purged ──(7 天后 cron)──► 物理删除 (physical_cleanup 每周巡检,每批 100 条)
```

### 2. audit_logs (新增)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| `actor_id` | UUID | NOT NULL, FK -> User.id | 操作者 |
| `action` | TEXT | NOT NULL | 操作类型: `create`/`update`/`delete`/`soft_delete`/`purge`/`export`/`import`/`agent.interrupt`/`agent.score`/`agent.diagnose`/`agent.suggest`/`agent.end` |
| `resource_type` | TEXT | NOT NULL | 资源类型: `resume`/`resume_branch`/`resume_block`/`resume_version`/`interview_session`/`interview_report`/`error_question`/`ability_dimension`/`activity`/`user`/`export_task`/`subscription` |
| `resource_id` | UUID | NULL | 资源 ID |
| `old_values` | JSONB | NULL | 变更前值(快照或关键字段) |
| `new_values` | JSONB | NULL | 变更后值(快照或关键字段) |
| `ip_address` | TEXT | NULL | 请求来源 IP |
| `user_agent` | TEXT | NULL | 请求 User-Agent |
| `token_usage` | INTEGER | NULL | Agent 子图节点 token 用量(仅 agent.* action) |
| `duration_ms` | INTEGER | NULL | Agent 子图节点耗时(仅 agent.* action) |
| `node_input_summary` | TEXT | NULL | Agent 节点输入摘要(仅 agent.* action) |
| `node_output_summary` | TEXT | NULL | Agent 节点输出摘要(仅 agent.* action) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 记录时间 |

**分区**: 按 `created_at` 月分区(`PARTITION BY RANGE (created_at)`)。

**索引**:
- `(actor_id, created_at DESC)` — 用户查看自己的操作日志
- `(resource_type, resource_id, created_at DESC)` — 按资源查看变更历史
- `(action, created_at DESC)` — admin 按操作类型筛选
- `(created_at DESC)` — admin 全量倒序查看

**保留策略**: 12 个月,按分区自动删除。

### 3. export_tasks (新增)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| `user_id` | UUID | NOT NULL, FK -> User.id | 导出请求者 |
| `status` | TEXT | NOT NULL, CHECK IN ('pending','processing','completed','failed') | 任务状态 |
| `file_path` | TEXT | NULL | ZIP 文件路径(完成后) |
| `file_size_bytes` | BIGINT | NULL | 文件大小 |
| `expires_at` | TIMESTAMPTZ | NULL | 下载链接过期时间 |
| `error_message` | TEXT | NULL | 失败原因 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| `completed_at` | TIMESTAMPTZ | NULL | 完成时间 |

**索引**: `(user_id, created_at DESC)`

### 4. resources (新增)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| `title` | TEXT | NOT NULL | 标题 |
| `summary` | TEXT | NOT NULL | 摘要 |
| `category` | TEXT | NOT NULL | 分类: `interview_tips`/`resume_guide`/`tech_prep` |
| `tags` | TEXT[] | NOT NULL, DEFAULT '{}' | 标签数组 |
| `content` | TEXT | NOT NULL | Markdown 正文 |
| `content_type` | TEXT | NOT NULL, CHECK IN ('article','video','template') | 内容类型 |
| `read_time_minutes` | INTEGER | NULL | 预估阅读时长(分钟) |
| `video_url` | TEXT | NULL | 视频链接(仅 content_type=video) |
| `sort_order` | INTEGER | NOT NULL, DEFAULT 0 | 排序权重 |
| `is_published` | BOOLEAN | NOT NULL, DEFAULT true | 是否发布 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**索引**:
- `(category, sort_order)` — 按分类展示
- `GIN(tags)` — 标签筛选
- `GIN(to_tsvector('simple', title || ' ' || summary))` — 全文搜索

### 5. help_faq (新增)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| `question` | TEXT | NOT NULL | 问题 |
| `answer` | TEXT | NOT NULL | Markdown 答案 |
| `category` | TEXT | NOT NULL, CHECK IN ('account','interview','resume','subscription','technical') | FAQ 分类 |
| `sort_order` | INTEGER | NOT NULL, DEFAULT 0 | 排序权重 |
| `is_published` | BOOLEAN | NOT NULL, DEFAULT true | 是否发布 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**索引**:
- `(category, sort_order)` — 按分类展示
- `GIN(to_tsvector('simple', question || ' ' || answer))` — 全文搜索

### 6. subscription_plans (新增,配置驱动)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `plan` | TEXT | PK | `free` / `pro` / `enterprise` |
| `monthly_token_quota` | INTEGER | NOT NULL | 月度 token 配额 |
| `features` | JSONB | NOT NULL, DEFAULT '{}' | 特性标志(如 `{"voice_mode":false}`) |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | 是否启用 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |

**种子数据**:

| plan | monthly_token_quota | features |
|---|---|---|
| `free` | 500000 | `{}` |
| `pro` | 5000000 | `{"priority_support": true}` |
| `enterprise` | 50000000 | `{"priority_support": true, "custom_quota": true}` |

---

## 实体关系图

```
User (1) ────< export_tasks (N)
User (1) ────< audit_logs (N)   [via actor_id]
User (1) ────> subscription_plans (1)  [via User.subscription]

resources / help_faq: 独立表,不关联用户数据
```

---

## 迁移计划

```sql
-- 1. User 表变更
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'
  CHECK (role IN ('user', 'admin'));
ALTER TABLE users ADD COLUMN scheduled_purge_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN cancellation_deadline TIMESTAMPTZ;

-- 2. audit_logs 表(按月分区)
-- 参见 research.md D10

-- 3. export_tasks 表
CREATE TABLE export_tasks (...);

-- 4. resources 表
CREATE TABLE resources (...);

-- 5. help_faq 表
CREATE TABLE help_faq (...);

-- 6. subscription_plans 表(种子数据)
CREATE TABLE subscription_plans (...);
INSERT INTO subscription_plans VALUES
  ('free', 500000, '{}'),
  ('pro', 5000000, '{"priority_support": true}'),
  ('enterprise', 50000000, '{"priority_support": true, "custom_quota": true}');
```
