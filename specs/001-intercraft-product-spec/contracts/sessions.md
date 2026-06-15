# Sessions & Devices Endpoints (M05)

> 多端会话管理 + 设备指纹 + 5 设备限制 + 主动踢出。
> 设备指纹算法:`sha256(UA + screen + tz + lang)`,前端在 `src/api/device-fingerprint.ts` 计算(plan DEC-7)。

## 共享类型

```ts
type DeviceSession = {
  id: string;                  // auth_sessions.id
  device_id: string;           // sha256 指纹(64 hex)
  device_name: string | null;
  device_fingerprint: string;  // 原始指纹
  last_seen_at: string;        // ISO 8601
  last_seen_ip: string | null;
  last_seen_ua: string | null;
  trusted_at: string | null;   // v1.1 启用
  created_at: string;
  is_current: boolean;         // 当前请求 session_id 是否为这个
}
```

---

## 1. `GET /api/v1/users/me/sessions`

**用途**:列出当前用户所有活跃 session(供「设备管理」页)。

**Auth**:Bearer access

**请求**:无

**响应 200**:
```json
{
  "sessions": [ /* DeviceSession[] */ ]
}
```

**排序**:按 `last_seen_at DESC`(最近活跃在前)

**Phase 1 行为**:
- `last_seen_at` 由中间件每分钟 flush 一次到 DB(M05 §6,Redis 缓冲)
- `is_current` 由后端基于 `Authorization` 头中的 `session_id` 字段判断
- 5 设备上限通过登录流程保证,此端点**不**主动裁剪

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |

---

## 2. `DELETE /api/v1/users/me/sessions/{session_id}`

**用途**:主动踢出某设备。

**Auth**:Bearer access(踢出者必须是同一 user;RLS 兜底)

**请求**:无

**响应 204**:No Content

**副作用**:
- `auth_sessions.deleted_at = now()`(软删)
- 该 session 的 refresh token 立即失效
- 该 session 关联的 access token **立即**失效(后端每次请求都校验 `auth_sessions.session_id` 是否仍存活)
- **被踢出的设备 5 分钟内强制登出**(M05 §2)

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `session.not_found` | session_id 不存在或已软删 |
| 403 | `auth.session_other_user` | 跨用户踢出 |

---

## 3. `POST /api/v1/users/me/sessions/{session_id}/trust` *(v1.1 启用,Phase 1 占位)*

> Phase 1 不实现。`auth_sessions.trusted_at` 字段已落表,Phase 1 写 501 Not Implemented。
> 预期:设置 `trusted_at = now()`,免 MFA(MFA 本身 v1.1)。

```json
{
  "error": {
    "code": "not_implemented",
    "message": "设备信任标记将在 v1.1 启用",
    "request_id": "..."
  }
}
```

---

## 4. 5 设备限制(后端逻辑)

**触发**:`POST /auth/login` / `POST /auth/register` 时。

**算法**:
1. 查询当前 user 的 active session 数
2. 若 ≥ 5,按 `last_seen_at ASC` 排序,取最早 N 个 soft_delete(N = 当前数 - 4)
3. 创建新 session
4. 记录被踢出的 session_id 到登录响应(供前端 Toast 提示)

**并发竞态**(research RK-4):
- 登录事务用 SERIALIZABLE 隔离
- 唯一约束 `UNIQUE (device_id)`(同一指纹不可重复)
- 冲突时:返回 409 Conflict + `auth.concurrent_login`,前端重试一次

**事务伪代码**:
```python
async with db.begin(isolation="SERIALIZABLE"):
    active = await session_repo.list_active(user_id)  # deleted_at IS NULL
    if len(active) >= 5:
        to_evict = sorted(active, key=lambda s: s.last_seen_at)[:len(active) - 4]
        for s in to_evict:
            await session_repo.soft_delete(s.id)
    new_session = await session_repo.create({...})
```

---

## 5. last_seen 跟踪(M05 §6 决议)

**中间件**:`app/core/middleware.py::LastSeenTracker`
- 每个请求末尾(响应后)将 `(session_id, ip, ua)` push 到 Redis list
- 后台 flush worker(ARQ 任务,每分钟一次)批量 `UPDATE auth_sessions SET last_seen_at=now(), last_seen_ip=?, last_seen_ua=? WHERE id IN (...)`
- Redis 不可用时降级:同步写 DB(性能下降但功能正常)

**Phase 1 简化**:若 ARQ worker 未启动,中间件**同步**写 DB(可接受,因为登录后才进入此路径,且仅 1 次 UPDATE/请求)。**Phase 2 优化**:ARQ 异步 flush。
