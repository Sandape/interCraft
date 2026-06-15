# Lock API Contract

**Module**: M12 · **Phase**: 3 · **Base Path**: `/api/v1/locks`

> 悲观锁 REST API:获取锁、续期心跳、释放锁、查询锁状态。

## 1. Common Headers

```
Authorization: Bearer <access_token>
X-Request-ID: <uuid>
```

所有端点需要有效 JWT access token。锁操作绑定当前用户,不可跨用户操作他人锁。

## 2. Endpoints

### 2.1 Acquire Lock

```
POST /api/v1/locks/acquire
```

**Request Body**:
```json
{
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000"
}
```

**Validation**:
- `resource_type` ∈ `["resume_branch", "error_question"]`
- `resource_id` 必须是有效的 UUIDv7
- 同用户已在另一设备持有该资源锁 → 返回 409

**Response 201** (lock acquired):
```json
{
  "lock_id": "019b5e6c-0000-7000-0000-000000000001",
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000",
  "user_id": "019b5e6c-0000-7000-0000-000000000002",
  "device_id": "abc123def456",
  "acquired_at": "2026-06-13T10:30:00Z",
  "expires_at": "2026-06-13T10:35:00Z"
}
```

**Response 409** (already locked by another user):
```json
{
  "error": {
    "code": "lock.resource_locked",
    "message": "该资源正被其他用户编辑中",
    "details": {
      "locked_by": {
        "user_id": "019b5e6c-0000-7000-0000-000000000003",
        "user_name": "张三",
        "acquired_at": "2026-06-13T10:25:00Z"
      }
    },
    "request_id": "..."
  }
}
```

**Response 409** (already locked by same user, different device):
```json
{
  "error": {
    "code": "lock.already_held_by_you",
    "message": "你已在另一设备上编辑该资源",
    "details": {
      "device_id": "xyz789",
      "acquired_at": "2026-06-13T10:20:00Z"
    },
    "request_id": "..."
  }
}
```

---

### 2.2 Release Lock

```
DELETE /api/v1/locks/{lock_id}
```

**Response 200**:
```json
{
  "lock_id": "019b5e6c-0000-7000-0000-000000000001",
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000",
  "released_at": "2026-06-13T10:45:00Z"
}
```

**Response 404** (lock not found or already expired):
```json
{
  "error": {
    "code": "lock.not_found",
    "message": "锁不存在或已过期",
    "request_id": "..."
  }
}
```

**Response 403** (trying to release another user's lock):
```json
{
  "error": {
    "code": "lock.not_yours",
    "message": "无权释放他人持有的锁",
    "request_id": "..."
  }
}
```

---

### 2.3 Get Lock Status

```
GET /api/v1/locks/{resource_type}/{resource_id}
```

**Response 200** (locked):
```json
{
  "locked": true,
  "lock_id": "019b5e6c-0000-7000-0000-000000000001",
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000",
  "user_id": "019b5e6c-0000-7000-0000-000000000002",
  "user_name": "张三",
  "device_id": "abc123def456",
  "acquired_at": "2026-06-13T10:30:00Z",
  "expires_at": "2026-06-13T10:35:00Z"
}
```

**Response 200** (unlocked):
```json
{
  "locked": false,
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000"
}
```

---

## 3. WebSocket Events

**Connection**: `ws://<host>/api/v1/ws/locks?token=<access_token>`

### 3.1 Server → Client Events

#### lock.acquired
```json
{
  "type": "lock.acquired",
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000",
  "user_id": "019b5e6c-0000-7000-0000-000000000002",
  "user_name": "张三",
  "device_id": "abc123def456",
  "acquired_at": "2026-06-13T10:30:00Z"
}
```

#### lock.released
```json
{
  "type": "lock.released",
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000",
  "released_at": "2026-06-13T10:45:00Z",
  "reason": "manual | ttl_expired | heartbeat_lost"
}
```

#### lock.lost
```json
{
  "type": "lock.lost",
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000",
  "reason": "heartbeat_timeout | admin_revoked | session_evicted",
  "message": "锁已被释放:心跳超时。请保存本地更改后重新获取锁。"
}
```

> `lock.lost` 发送给**原持锁用户**;`lock.acquired` / `lock.released` 发送给**所有监听的在线用户**(同一资源)。前端按 resource_id 过滤:如果用户不是持锁者且收到 `lock.acquired` → UI 切换只读。

### 3.2 Client → Server Messages

#### lock.heartbeat
```json
{
  "type": "lock.heartbeat",
  "lock_id": "019b5e6c-0000-7000-0000-000000000001",
  "resource_type": "resume_branch",
  "resource_id": "019b5e6c-0000-7000-0000-000000000000"
}
```

服务端收到后:验证 lock 仍属于该用户 → `EXPIRE lock:... 300`(续 TTL) → 更新 `heartbeat_at` → 异步写 audit_log(action=heartbeat)。

### 3.3 WS Error Frame

```json
{
  "type": "error",
  "code": "lock.invalid_heartbeat",
  "message": "心跳对应的锁不存在或已过期,请重新获取",
  "request_id": "..."
}
```

---

## 4. Error Codes Summary

| Code | HTTP Status | Description |
|---|---|---|
| `lock.resource_locked` | 409 | 资源被其他用户锁定 |
| `lock.already_held_by_you` | 409 | 同用户另一设备已持有锁 |
| `lock.not_found` | 404 | 锁不存在或已过期 |
| `lock.not_yours` | 403 | 尝试操作他人锁 |
| `lock.invalid_resource_type` | 422 | resource_type 不在枚举中 |
| `lock.invalid_heartbeat` | 400 (WS) | 心跳无效,需重新获取锁 |

---

## 5. Timing Constants (from spec/clarifications)

| 常量 | 值 | 说明 |
|---|---|---|
| `LOCK_HEARTBEAT_INTERVAL` | 60s | 客户端心跳发送间隔 |
| `LOCK_AUTO_RELEASE` | 90s | 无心跳后自动释放(1.5 个心跳间隔) |
| `LOCK_TTL_HARD` | 300s | Redis key TTL,绝对上限 |
| `WS_DISCONNECT_GRACE` | 30s | WS 断线检测窗口(不立即释放,允许短暂网络抖动) |
