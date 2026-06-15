# Data Model: InterCraft Phase 3

**Status**: Phase 3 output · **Date**: 2026-06-13 · **Spec**: [spec.md](./spec.md) | **Phase 1 Data Model**: [data-model.md](./data-model.md) | **Phase 2 Data Model**: [data-model-phase-2.md](./data-model-phase-2.md) | **Phase 3 Research**: [research-phase-3.md](./research-phase-3.md) | **Phase 3 Plan**: [phase-3.md](./phase-3.md)

> 本文档定义 Phase 3 涉及的**全部新增数据实体**。Phase 3 不新增 PostgreSQL 业务表(锁状态在 Redis,审计表 1 张),新增客户端 IndexedDB Outbox schema。

---

## 0. 设计原则

Phase 3 数据模型分层:
- **Redis**:活跃锁状态(临时,重启丢失可接受),TTL 自动过期,Pub/Sub 事件通知
- **PostgreSQL**:`lock_audit_logs` 审计表(append-only,永久),供调试与可观测性
- **IndexedDB(浏览器)**:`outbox_entries` 离线写队列(客户端侧,非服务端)

无新增业务实体表;锁本身不是业务实体,是资源访问控制层。

---

## 1. Redis 锁状态

### 1.1 Key 设计

```
Key:   lock:{resource_type}:{resource_id}
Value: JSON
TTL:   300s (每次心跳续期为 300s)
```

### 1.2 Value Schema

```json
{
  "lock_id": "uuidv7",
  "resource_type": "resume_branch | error_question",
  "resource_id": "uuid",
  "user_id": "uuid",
  "device_id": "string (device fingerprint hash)",
  "session_id": "uuid (auth_sessions.id)",
  "acquired_at": "ISO8601",
  "heartbeat_at": "ISO8601",
  "expires_at": "ISO8601 (= heartbeat_at + 300s)"
}
```

### 1.3 Pub/Sub Channel

```
Channel: lock:{resource_id}
Message: JSON (see contracts/locks.md §WS Events)
```

订阅者:所有持有该用户 session 的 WS 连接(按 user_id 路由,收到消息后按 resource_id 过滤推送给对应前端)。

### 1.4 生命周期

```
[不存在]  →  SET lock:... EX 300  →  [活跃]
[活跃]    →  EXPIRE lock:... 300   →  [活跃] (心跳续期)
[活跃]    →  DEL lock:...          →  [已释放] (主动释放)
[活跃]    →  TTL 到期              →  [不存在] (自动过期)
[活跃]    →  90s 无心跳            →  DEL + PUBLISH lock.lost (服务端主动释放)
```

---

## 2. PostgreSQL lock_audit_logs

### 2.1 表结构

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK, uuidv7 | 审计记录 ID |
| `resource_type` | `VARCHAR(64)` | NOT NULL | `resume_branch` / `error_question` |
| `resource_id` | `UUID` | NOT NULL | 被锁资源 ID |
| `user_id` | `UUID` | NOT NULL | 持锁用户 |
| `device_id` | `VARCHAR(128)` | NOT NULL | 设备指纹 |
| `session_id` | `UUID` | NOT NULL | auth_sessions.id |
| `action` | `VARCHAR(16)` | NOT NULL | `acquired` / `released` / `expired` / `heartbeat` |
| `metadata_json` | `JSONB` | DEFAULT '{}' | 附加信息(release_reason, heartbeat_count 等) |
| `occurred_at` | `TIMESTAMPTZ` | NOT NULL, INDEX | 事件发生时间 |

### 2.2 索引

```sql
CREATE INDEX idx_lock_audit_resource ON lock_audit_logs (resource_type, resource_id, occurred_at DESC);
CREATE INDEX idx_lock_audit_user ON lock_audit_logs (user_id, occurred_at DESC);
```

### 2.3 Mixin 组合

| 表 | PrimaryKey | Timestamped | SoftDeletable | TenantScoped |
|---|---|---|---|---|
| `lock_audit_logs` | ✅(uuidv7) | ❌(无 updated_at,只有 occurred_at) | ❌(永不复用) | ❌(跨用户审计,不走 RLS) |

> `lock_audit_logs` 不走 RLS:审计日志需要管理员/运维视角全局可查。`user_id` 列用于过滤,但不强制 `SET LOCAL app.user_id`。

### 2.4 写入策略

异步写入,不在锁服务热路径上阻塞:
- FastAPI `BackgroundTasks` 或 `asyncio.create_task` fire-and-forget
- 写入失败不影响锁操作(记录 error log,`lock_audit_log.write_failed` 计数器告警)

---

## 3. IndexedDB Outbox(客户端)

### 3.1 数据库

```
数据库名: intercraft_outbox
版本: 1
```

### 3.2 outbox_entries 表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `auto-increment` (PK) | 自增主键 |
| `entity_type` | `string` | 实体类型:`error_question` / `activity` / `user_profile` / `job` / `task` |
| `operation` | `string` | 操作:`create` / `update` / `delete` |
| `entity_id` | `string` (UUID) | 操作对象 ID(create 时可为客户端预生成 UUIDv7) |
| `payload` | `object` (JSON) | 操作负载(与对应 API PATCH/POST body 一致) |
| `entity_updated_at` | `string` (ISO8601) | 离线编辑时客户端记录的 `updated_at`(用于冲突检测,R3-5) |
| `client_timestamp` | `number` (unix ms) | 客户端操作时间戳(用于排序回放) |
| `retry_count` | `number` (default 0) | 重试次数(max 3) |
| `status` | `string` | `pending` / `syncing` / `synced` / `conflict` / `failed` |
| `error_message` | `string?` | 最后一次失败的错误信息 |

### 3.3 Dexie Schema (TypeScript)

```typescript
interface OutboxEntry {
  id?: number;
  entity_type: 'error_question' | 'activity' | 'user_profile' | 'job' | 'task';
  operation: 'create' | 'update' | 'delete';
  entity_id: string;
  payload: Record<string, unknown>;
  entity_updated_at: string;
  client_timestamp: number;
  retry_count: number;
  status: 'pending' | 'syncing' | 'synced' | 'conflict' | 'failed';
  error_message?: string;
}

const db = new Dexie('intercraft_outbox');
db.version(1).stores({
  outbox_entries: '++id, entity_type, status, client_timestamp'
});
```

### 3.4 条目生命周期

```
[用户离线操作]  →  INSERT status=pending          (IndexedDB)
[联网后回放]    →  UPDATE status=syncing           (逐批)
[服务端 200]    →  UPDATE status=synced            (可清理)
[服务端 409]    →  UPDATE status=conflict          (触发 diff 合并视图)
[重试 3 次失败]  →  UPDATE status=failed            (用户手动重试或丢弃)
[synced 条目]   →  DELETE (保留最近 50 条,旧条目后台清理)
```

---

## 4. 现有表变更(Phase 3)

Phase 3 **不修改**任何 Phase 1/Phase 2 表结构。锁是独立控制层,Outbox 是客户端侧存储,均不侵入业务 schema。

Alembic 迁移 `0003_phase3_lock_audit.py` 仅创建 `lock_audit_logs` 表。

---

## 5. 实体关系概览

```
┌──────────────────────────────────────────────────────┐
│  Redis (临时)                                         │
│  ┌──────────────────────────────────────────────┐    │
│  │ lock:{resource_type}:{resource_id}            │    │
│  │ TTL 300s, 心跳续期, Pub/Sub 通知              │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
         │ PUBLISH lock:<resource_id>
         ▼
┌──────────────────────────────────────────────────────┐
│  FastAPI WS 连接池 {user_id: [WebSocket, ...]}       │
│  收到 Redis 消息 → 路由到对应 user WS → 前端          │
└──────────────────────────────────────────────────────┘
         │
         ▼ (异步 fire-and-forget)
┌──────────────────────────────────────────────────────┐
│  PostgreSQL: lock_audit_logs (永久)                    │
│  ┌──────────────────────────────────────────────┐    │
│  │ id | resource_type | resource_id | user_id   │    │
│  │ device_id | action | metadata_json | ts      │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘

浏览器端:
┌──────────────────────────────────────────────────────┐
│  IndexedDB: intercraft_outbox                         │
│  ┌──────────────────────────────────────────────┐    │
│  │ outbox_entries (Dexie.js 管理)                │    │
│  │ ++id, entity_type, operation, payload,        │    │
│  │ entity_updated_at, client_timestamp,          │    │
│  │ retry_count, status, error_message            │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```
