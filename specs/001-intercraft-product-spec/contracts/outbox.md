# Outbox API Contract

**Module**: M13 · **Phase**: 3 · **Base Path**: `/api/v1/outbox`

> 离线写操作回放端点。客户端离线期间将写操作存入 IndexedDB Outbox,联网后批量提交到此端点回放。

## 1. Common Headers

```
Authorization: Bearer <access_token>
Content-Type: application/json
X-Request-ID: <uuid>
```

## 2. Endpoints

### 2.1 Batch Replay

```
POST /api/v1/outbox/replay
```

**Request Body**:
```json
{
  "entries": [
    {
      "client_entry_id": 1,
      "entity_type": "error_question",
      "operation": "update",
      "entity_id": "019b5e6c-0000-7000-0000-000000000000",
      "payload": {
        "tags": ["系统设计", "分布式"],
        "notes": "复习了 CAP 定理"
      },
      "entity_updated_at": "2026-06-13T10:30:00Z",
      "client_timestamp": 1750000000000
    },
    {
      "client_entry_id": 2,
      "entity_type": "job",
      "operation": "update",
      "entity_id": "019b5e6c-0000-7000-0000-000000000001",
      "payload": {
        "status": "test"
      },
      "entity_updated_at": "2026-06-13T10:25:00Z",
      "client_timestamp": 1750000040000
    }
  ]
}
```

**Field descriptions**:

| Field | Type | Required | Description |
|---|---|---|---|
| `client_entry_id` | `number` | Yes | 客户端 Outbox 条目 ID(自增),服务端在响应中原样返回,用于客户端匹配 |
| `entity_type` | `string` | Yes | 实体类型:`error_question` / `activity` / `user_profile` / `job` / `task` |
| `operation` | `string` | Yes | `create` / `update` / `delete` |
| `entity_id` | `string(UUID)` | Yes | 操作对象 ID |
| `payload` | `object` | Yes | 操作负载(与对应 REST API 的 PATCH/POST body 格式一致) |
| `entity_updated_at` | `string(ISO8601)` | Yes | 离线编辑时客户端记录的 `updated_at`,用于冲突检测 |
| `client_timestamp` | `number(unix ms)` | Yes | 客户端操作时间戳 |

**Rate limit**: 30 entries per request max; `outbox.too_many_entries` 422 if exceeded.

**Service-side processing** (per R3-4):
- 逐条顺序处理,独立条目冲突不阻塞其余条目
- 每条处理逻辑:
  1. 根据 `entity_type` 路由到对应 service(replay_* 方法)
  2. 比较 `server.updated_at` vs `entry.entity_updated_at`
  3. 若 `server.updated_at <= client.updated_at`:正常处理,返回 `ok`
  4. 若 `server.updated_at > client.updated_at`:返回 `conflict` + 服务端当前版本
  5. `create` 操作无冲突检测(entity 不存在时创建;entity_id 已存在 → 幂等返回 `ok`,不重复创建)

**Response 200** (mixed results):
```json
{
  "results": [
    {
      "client_entry_id": 1,
      "status": "ok",
      "server_entity": {
        "id": "019b5e6c-0000-7000-0000-000000000000",
        "updated_at": "2026-06-13T10:30:01Z"
      }
    },
    {
      "client_entry_id": 2,
      "status": "conflict",
      "server_entity": {
        "id": "019b5e6c-0000-7000-0000-000000000001",
        "status": "test",
        "updated_at": "2026-06-13T10:28:00Z",
        "...": "(full current entity, enough for diff merge view)"
      },
      "conflict_fields": ["status"]
    }
  ],
  "summary": {
    "total": 2,
    "ok": 1,
    "conflict": 1,
    "failed": 0
  }
}
```

**Response 422** (too many entries):
```json
{
  "error": {
    "code": "outbox.too_many_entries",
    "message": "单次最多回放 30 条,收到 35 条",
    "limit": 30,
    "request_id": "..."
  }
}
```

---

### 2.2 Get Outbox Status (health endpoint)

```
GET /api/v1/outbox/status
```

Returns the server-side outbox processing status (not client-side). Primarily for observability.

**Response 200**:
```json
{
  "status": "healthy",
  "recent_replays": {
    "last_hour": 15,
    "conflict_rate": 0.05
  }
}
```

---

## 3. Client-Side Replay Logic

```
1. 网络恢复检测(navigator.onLine + periodic ping /healthz)
2. Dexie: outbox_entries.where({status: "pending"}).sortBy("client_timestamp")
3. 取前 30 条 → status = "syncing"
4. POST /api/v1/outbox/replay
5. 遍历 results:
   - status="ok"     → Dexie: status = "synced"
   - status="conflict" → Dexie: status = "conflict" → 存储 server_entity → 触发 diff 合并 UI
   - status="failed"  → retry_count++, 若 < 3: status = "pending"; 若 ≥ 3: status = "failed"
6. 若还有 pending: 重复步骤 2-5
7. 清理: synced 条目保留至多 50 条,旧条目 batchDelete
```

---

## 4. Conflict Resolution (Diff Merge)

触发条件:`result.status === "conflict"`

UI 流程:
1. 通知:"N 条离线更改存在冲突,请手动解决"
2. Diff 合并视图:逐字段展示 `本地版(Outbox payload)` vs `服务端版(server_entity)`
3. 用户逐字段选择保留哪版(字段级 LWW)
4. 确认后调用对应 REST API PATCH,成功后 Outbox 条目标记 `synced`

参见 spec FR-063 / E9 / 2026-06-13 澄清。

---

## 5. Entity Routing Table

服务端根据 `entity_type` 路由到对应 replay 方法:

| entity_type | Service Method | Conflict Detection | Notes |
|---|---|---|---|
| `error_question` | `ErrorService.replay_update(entity_id, payload, updated_at)` | `updated_at` 比较 | create → 幂等(entity_id 已存在返回 ok);delete → 软删除 |
| `activity` | `ActivityService.replay_create(entity_id, payload)` | 无(create-only,append-only) | 活动流仅追加,不更新 |
| `user_profile` | `UserService.replay_update(entity_id, payload, updated_at)` | `updated_at` 比较 | entity_id = user_id |
| `job` | `JobService.replay_update(entity_id, payload, updated_at)` | `updated_at` 比较 | status 变更可能触发 task 创建 |
| `task` | `TaskService.replay_update(entity_id, payload, updated_at)` | `updated_at` 比较 | 仅允许 update status,不允许 create(任务由服务端触发器创建) |

---

## 6. Error Codes Summary

| Code | HTTP Status | Description |
|---|---|---|
| `outbox.too_many_entries` | 422 | 单次超过 30 条 |
| `outbox.invalid_entity_type` | 422 | entity_type 不在枚举中 |
| `outbox.invalid_operation` | 422 | operation 对 entity_type 不合法 |
| `outbox.entity_not_found` | 404 | entity_id 不存在(delete 操作) |
| `outbox.replay_failed` | 500 | 服务端处理异常(标记 failed,客户端可重试) |
