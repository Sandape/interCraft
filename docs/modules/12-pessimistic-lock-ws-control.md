# M12 · 悲观锁 + WebSocket 控制面

> 状态: draft · 所属领域: D · 优先级: P0
> 引用原文档: §5.3, §5.4, §10.6 (sync 控制面)

## 1. 需求摘要

实现资源级悲观锁:申请 / 续期 / 释放;WebSocket 控制面 `sync.{user_id}` 频道推送 `lock.acquired / lock.released / resource.updated / notification.created`;支持冲突响应 423 + `current_holder` 信息;支持「强制抢锁」。本模块**只做锁与控制面 WS**,Agent 数据面 WS 由 M14 实现。

## 2. 验收标准

- [ ] `POST /api/v1/locks/{resource_type}/{resource_id}` 申请锁(TTL 300s,Redis SETNX)
- [ ] `POST /api/v1/locks/{resource_type}/{resource_id}/heartbeat` 续期 60s
- [ ] `DELETE /api/v1/locks/{resource_type}/{resource_id}` 释放
- [ ] `POST /api/v1/locks/{resource_type}/{resource_id}/force` 强制抢锁(原持有者会被踢出)
- [ ] 持有者元数据:`{holder_user_id, holder_device_id, acquired_at, ttl_remaining_sec}`
- [ ] WebSocket 接入 `ws://.../ws/sync` → 验签 JWT → 加入 `sync.{user_id}` 频道
- [ ] Redis Pub-Sub 转发(横向扩展):应用 publish → Redis → 所有 WS worker 收到 → 本地路由
- [ ] 业务写操作集成:写 resume_blocks 时校验持锁(无锁 423,持锁人是别人 423,自己持锁通过)
- [ ] 集成测试:浏览器 A 持锁,B 写入 → 423 + current_holder

## 3. 依赖与被依赖关系

**强依赖**: M03(Redis Pub-Sub)、M05(JWT 验签)
**弱依赖**: M11(facilitates 面试锁)
**被以下模块依赖**: M06(简历编辑锁)、M13(客户端 outbox 回放)、M15-M17(Agent 锁)、M23(前端锁状态 UI)
**外部依赖**: 无新增

## 4. 数据模型

无新表。锁元数据存 Redis:
```
KEY: lock:{resource_type}:{resource_id}
VALUE: JSON {holder_user_id, holder_device_id, acquired_at, last_heartbeat_at, force_count}
TTL: 300s(每次心跳重置)
```

可选审计:`locks_audit` 表(记录每次 acquire/release/force 历史),供调试。

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/locks/{type}/{id}` | 申请锁(返回 token) |
| POST | `/api/v1/locks/{type}/{id}/heartbeat` | 续期 |
| DELETE | `/api/v1/locks/{type}/{id}` | 释放 |
| POST | `/api/v1/locks/{type}/{id}/force` | 强制抢锁 |
| GET | `/api/v1/locks/{type}/{id}` | 查询当前持有者 |

**WebSocket** (`/ws/sync`,JWT 验签):
| Channel | 事件 | 触发 |
|---|---|---|
| `sync.{user_id}` | `lock.acquired` | 锁颁发 / 续期 |
| `sync.{user_id}` | `lock.released` | 锁释放 / 过期 / 被抢 |
| `sync.{user_id}` | `lock.force_attempted` | 被他人强抢(警告) |
| `sync.{user_id}` | `resource.updated` | 增量变更(可选,v1.1) |
| `sync.{user_id}` | `notification.created` | M10 通知 |

**事件 payload**:
```json
{
  "event": "lock.acquired",
  "resource_type": "resume_branch",
  "resource_id": "uuid",
  "holder": {"user_id": "...", "device_id": "..."},
  "ttl_sec": 300,
  "ts": "2026-06-12T..."
}
```

## 6. 关键设计点

- **SETNX + Lua 原子**:用 `SET key value NX EX 300`,避免竞态;Lua 脚本实现「同持有者续期 / 释放」
- **强制抢锁审计**:`force_count++`,WS 推 `lock.force_attempted` 给原持有者(警告)
- **心跳频率**:客户端 60s 一次,TTL 300s 留 4 次容错;长时间 idle 自动失效
- **Tab 失焦释放**:前端 `visibilitychange` + `beforeunload` → 主动 DELETE 锁
- **Redis Pub-Sub 转发**(横向扩展):
  ```
  应用 publish → Redis channel `sync_events` → 所有 WS worker 订阅 → 按 user_id 路由到本地 WS 连接
  ```
- **WebSocket 连接管理**:`WSConnectionRegistry` 单例,`{user_id: set[WebSocket]}`,断线清理
- **认证**:`/ws/sync?token=...`,verify JWT → 设置 connection.user_id;每分钟刷新 token 防过期
- **业务集成接口**:
  ```python
  async def require_lock(resource_type, resource_id, user_id, device_id):
      """装饰器 / 依赖,校验持锁;失败抛 423"""
  ```

## 7. 待澄清

- **[A3]** 离线 + 锁的冲突边界:本模块明确「锁 TTL 300s,离线超时自动释放,联网回放遭遇 423 需 UI 协商」
- 强制抢锁是否需要确认对话框:前端 UX 决定,M23 协调
- WebSocket 横向扩展(uvicorn 集群)选 Redis Pub-Sub 还是专用推送服务:本模块用 Redis Pub-Sub(简单)

## 8. 实现提示

- 文件: `backend/app/api/v1/locks.py`、`backend/app/api/v1/ws.py`、`backend/app/services/lock_service.py`、`backend/app/services/ws_service.py`、`backend/app/core/ws_registry.py`、`backend/app/middleware/lock_check.py`
- 复用: M03 Redis、M05 JWT verify
- 与 mockData 关系: 无(锁是新引入概念)
