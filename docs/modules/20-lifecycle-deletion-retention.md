# M20 · 生命周期 / 注销 / 保留期

> 状态: draft · 所属领域: F · 优先级: P1
> 引用原文档: §3.4(软删除)、§9.1(注销流程)、§9.2(保留期)

## 1. 需求摘要

实现用户数据生命周期的「**软删除 → 保留期 → 硬删除 / 匿名化**」三段式管理,以及注销主动请求的数据擦除流程。所有业务表在删除时使用 `deleted_at` 软删(可恢复 30 天);注销请求进入 90 天宽限期(可撤销),宽限期后硬删除 PII + 匿名化 AI 数据;活动流 90 天归档、AI 对话 6 月冷存(GPG 加密归档到对象存储)。本模块是合规与可观测之外的另一条**全用户级别**横切能力。

## 2. 验收标准

- [ ] 所有业务表软删除(`UPDATE ... SET deleted_at = now()`),普通查询自动过滤 `WHERE deleted_at IS NULL`(Repository 层强制)
- [ ] 软删 30 天内可恢复(管理员 / 用户本人通过恢复端点)
- [ ] 30 天后 ARQ 任务执行硬删除(PII 物理 DELETE,AI 消息/工具日志 ANONYMIZE)
- [ ] 注销请求:用户提交 → 进入 90 天宽限期(status=`pending_deletion`),可撤销
- [ ] 注销撤销后:status 恢复 `active`,所有数据原样保留
- [ ] 90 天到期 ARQ 任务执行:删除 PII(users / user_credentials / 设备会话),匿名化 AI 痕迹(`ai_messages.content='[redacted by account deletion]'`),保留能力画像历史用于脱敏聚合
- [ ] 活动流(activities)90 天后归档(从主表迁出到 `activities_archive` 分区表),前端查询自动路由
- [ ] AI 消息 / 工具调用 6 月后冷存到对象存储(S3 兼容),DB 仅保留 metadata + pointer
- [ ] 所有删除 / 匿名化操作写入 `audit_logs`(`action='data.hard_delete'` / `'data.anonymize'`)
- [ ] 注销时强制吊销所有 auth_sessions、释放所有锁
- [ ] 单元测试:软删 → 恢复 → 软删 → 硬删的完整状态机
- [ ] 集成测试:90 天宽限期到期自动触发硬删(通过冻结时间或显式 trigger)

## 3. 依赖与被依赖关系

**强依赖**: M02(ORM/Repository)、M03(队列/加密)、M04(账号)
**弱依赖**: M22(audit_logs 写入)
**被以下模块依赖**: 无(横切模块,被其他模块隐式消费)
**外部依赖**: S3 兼容对象存储(冷存);定时任务调度(ARQ cron)

## 4. 数据模型

**新表**:
```sql
-- 注销请求记录
account_deletion_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  requested_at timestamptz NOT NULL DEFAULT now(),
  scheduled_purge_at timestamptz NOT NULL,  -- requested_at + 90d
  status text NOT NULL DEFAULT 'pending_deletion',  -- pending_deletion | cancelled | purged
  cancelled_at timestamptz,
  purged_at timestamptz,
  reason text,
  ip inet, ua text,  -- 申请时上下文
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 归档活动流(分区)
activities_archive (LIKE activities INCLUDING ALL) PARTITION BY RANGE (occurred_at);
-- 每月一个分区,超 90 天的活动移入

-- 冷存指针(AI 消息 6 月后)
ai_messages_cold (
  message_id uuid PRIMARY KEY,
  cold_storage_uri text NOT NULL,  -- s3://bucket/ai-messages/{yyyy}/{mm}/{uuid}.gpg
  archived_at timestamptz NOT NULL,
  byte_size int,
  checksum_sha256 text
);
```

**所有业务表隐含字段**(参见 [A13]):
```sql
created_at timestamptz NOT NULL DEFAULT now(),
updated_at timestamptz NOT NULL DEFAULT now(),
deleted_at timestamptz  -- 软删标记,默认 NULL
```

**生命周期状态机**:
```
active ──[delete 操作]──> soft_deleted(deleted_at 已设)
soft_deleted ──[恢复端点(30d 内)]──> active
soft_deleted ──[30d 后 ARQ cron]──> hard_deleted / anonymized
active ──[注销请求]──> pending_deletion(scheduled_purge_at = +90d)
pending_deletion ──[撤销]──> active
pending_deletion ──[90d 到期]──> purged(PII 删 + AI 匿名)
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/account/deletion-requests` | 申请注销(需二次确认密码) |
| GET | `/api/v1/account/deletion-requests/current` | 查询当前注销状态 |
| DELETE | `/api/v1/account/deletion-requests/current` | 撤销注销 |
| POST | `/api/v1/admin/restores/{table}/{id}` | 管理员恢复软删记录 |
| GET | `/api/v1/admin/lifecycle/audit` | 查询某用户的删除/恢复历史 |

**ARQ 任务**:
```python
@worker_task
async def purge_expired_soft_deletes(ctx, batch_size: int = 100):
    """每小时扫:deleted_at < now() - 30d → 硬删或匿名化"""

@worker_task
async def purge_due_account_deletions(ctx, batch_size: int = 10):
    """每小时扫:scheduled_purge_at < now() AND status='pending_deletion' → purge"""

@worker_task
async def archive_old_activities(ctx, days: int = 90, batch_size: int = 1000):
    """每天 03:00 跑:90 天前活动 → activities_archive"""

@worker_task
async def cold_store_old_ai_messages(ctx, months: int = 6, batch_size: int = 500):
    """每天 04:00 跑:6 月前 AI 消息 → GPG 加密到 S3,留 pointer 在 ai_messages_cold"""
```

**WebSocket**: 注销 / 硬删完成时 `sync.{user_id}` 推 `account.lifecycle_changed` 事件,前端登出。

## 6. 关键设计点

- **软删实现**:`BaseRepository` 提供 `soft_delete(id)` / `restore(id)`;所有 `get` / `list` 方法自动注入 `WHERE deleted_at IS NULL`
- **二次确认**:注销接口需 `password` 字段(再次输入密码)+ `confirm_phrase="delete my account"`(防误触)
- **宽限期机制**:`users.status` 字段在 90 天宽限期内设为 `pending_deletion`(阻止登录但保留数据);宽限期外 `purged`
- **登录拦截**:JWT 验证时若 `users.status='pending_deletion'`,返回 410 Gone + 提示「账号正在注销中,可在 X 时间内撤销」
- **PII vs 匿名化**:
  - **PII 字段**(users.email / phone / user_credentials / auth_sessions / devices / account_deletion_requests.reason)→ 物理 DELETE
  - **AI 内容**(ai_messages.content / tool_call_logs.arguments)→ 替换为 `'[redacted by account deletion, original_id={uuid}]'`,保留外键关联以便脱敏聚合
  - **能力画像**(ability_dimensions / ability_history)→ 保留数值(score 字段),但 `user_id` 改为 `null` + 加 `anonymized_user_marker` 哈希
  - **任务 / 活动流**→ 物理 DELETE(无聚合价值)
- **冷存加密**:6 月 AI 消息导出为 JSONL → GPG 对 KMS-managed key 加密 → 上传 S3 → DB 记录 pointer
- **可恢复性**:30 天软删期内,任何 API 都不暴露「已删除」的数据;只有管理员端点(带 audit)可查
- **可审计性**:所有 lifecycle 操作(`soft_delete` / `restore` / `hard_delete` / `anonymize` / `purge` / `cold_store`)全部写入 `audit_logs`(`action` 前缀 `data.*`)
- **ARQ 任务幂等**:每个任务必须支持重复执行(用 `account_deletion_requests.status` / `ai_messages_cold.archived_at` 做去重)
- **__version__ = "1.0.0"**

## 7. 待澄清

- 30 天软删恢复 / 90 天注销宽限期具体数值:产品可配(可放到 `app_settings` 表,运营可调)
- 冷存保留期:6 月冷存后再多久彻底删除?GDPR 通常要求「无合法目的后删除」,建议冷存 2 年后物理 delete S3 对象
- 匿名化 vs 假名化的法律边界:本方案采用**假名化**(保留聚合维度,删除直接标识符);如需严格匿名(不可逆),需要再评估
- 管理员恢复端点的权限:仅 super_admin?还是机构 admin?涉及多租户时需要再分层

## 8. 实现提示

- 文件:
  - `backend/app/services/lifecycle_service.py`(`LifecycleService.soft_delete / restore / hard_delete / anonymize`)
  - `backend/app/services/account_deletion_service.py`
  - `backend/app/workers/tasks/lifecycle_cron.py`(`purge_expired_soft_deletes` / `purge_due_account_deletions` / `archive_old_activities` / `cold_store_old_ai_messages`)
  - `backend/app/api/v1/account_deletion.py`
  - `backend/app/api/v1/admin/lifecycle.py`
  - `backend/app/core/cold_storage.py`(S3 + GPG 封装)
- 复用: M02 BaseRepository;M03 encryptor(KMS key 引用);M22 audit_service
- 与 mockData 关系:无(mockData 不含已删除数据,生命周期是后端独占能力)
- 测试:`tests/integration/lifecycle/` 用 `freezegun` 冻结时间验证状态机
