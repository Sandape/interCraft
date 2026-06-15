# M05 · 会话 & 设备 & RLS 启用

> 状态: draft · 所属领域: B · 优先级: P0
> 引用原文档: §3.2 (auth_sessions), §4.2, §4.3

## 1. 需求摘要

完成多端会话管理:auth_sessions 表 + 设备指纹 + 5 设备限制 + 踢出最早空闲设备;在所有业务表实际启用 RLS 策略(在 M02 注入策略的基础上,M05 完成 `SET LOCAL` 的 FastAPI 依赖链与 e2e 验证)。

## 2. 验收标准

- [ ] `auth_sessions` 表落地,含设备元数据(参见 A11 方案 A)
- [ ] 登录时颁发 `device_id`(基于 UA + 屏幕 + 时区指纹),写 auth_sessions
- [ ] 同一用户登录超过 5 个活跃设备 → 自动 logout 最早 `last_seen_at` 的会话
- [ ] `GET /api/v1/users/me/sessions` 列出当前用户所有活跃设备
- [ ] `DELETE /api/v1/users/me/sessions/{session_id}` 主动撤销某设备(踢出)
- [ ] `current_user` 依赖在请求处理前完成 `SET LOCAL app.user_id`
- [ ] 集成测试:用户 A 的 token 查用户 B 的资源 → 返回空(RLS 验证)
- [ ] 集成测试:用户 A 的 token 强行 SQL 注入 user_id=B → RLS 阻断

## 3. 依赖与被依赖关系

**强依赖**: M02(auth_sessions 表 + RLS 策略注入)、M04(JWT / 登录流程)
**弱依赖**: 无
**被以下模块依赖**: 所有需要 RLS 实际生效的业务模块(M06-M22)
**外部依赖**: 无新增

## 4. 数据模型

**`auth_sessions` 表(基于 A11 方案 A)**:
```
id UUID PK
user_id UUID FK(users.id) NOT NULL
device_id TEXT NOT NULL UNIQUE  -- 指纹哈希
device_name TEXT NULL           -- 用户自定义(如 "MacBook Pro")
device_fingerprint TEXT NOT NULL  -- 原始指纹(可读)
last_seen_ip INET NULL
last_seen_ua TEXT NULL
refresh_token_hash TEXT NOT NULL  -- sha256(refresh_jti)
expires_at TIMESTAMPTZ NOT NULL
last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
trusted_at TIMESTAMPTZ NULL  -- 免 MFA
created_at / deleted_at  -- Mixin
```

**索引**:
- `(user_id, last_seen_at DESC)` 加速「找最早空闲设备」
- `(refresh_token_hash)` 查 refresh

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/users/me/sessions` | 当前用户所有活跃设备 |
| DELETE | `/api/v1/users/me/sessions/{session_id}` | 主动踢出某设备(撤销 refresh) |
| POST | `/api/v1/users/me/sessions/{session_id}/trust` | 标记可信(免 MFA,v1.1 启用) |

**Login 副作用** (M04 实现,本模块扩展):
- 登录时 → 检查活跃 session 数 ≥ 5 → 自动 soft_delete 最早 `last_seen_at` 的
- 每次请求 → 更新当前 session 的 `last_seen_at / last_seen_ip / last_seen_ua`

## 6. 关键设计点

- **设备指纹算法**:`sha256(UA + screen_resolution + timezone)`;前端 `navigator.userAgent + window.screen + Intl.DateTimeFormat().resolvedOptions().timeZone`
- **指纹不稳定的兜底**:UA 升级时指纹会变 → 接受多设备记录,5 设备上限按时间裁剪
- **RLS 注入**:
  ```python
  async def get_db_session(user: User = Depends(current_user)):
      async with engine.begin() as conn:
          await conn.execute(text("SET LOCAL app.user_id = :uid"), {"uid": str(user.id)})
          yield conn
  ```
- **超级用户绕过**:`admin` 角色可设置 `SET LOCAL app.is_admin = true`,RLS 策略 OR `current_setting('app.is_admin', true)::bool`
- **会话撤销级联**:踢出设备 → soft_delete auth_session → refresh 使用时 verify 失败
- **last_seen_at 更新**:不要每次请求都写库,使用 Redis 缓冲(1 分钟 flush 一次到 DB)

## 7. 待澄清

- **[A11]** 决定采用方案 A(合并 auth_sessions),已在本模块落实
- 「允许 / 拒绝并发」配置粒度:全局开关 vs 用户开关 → 推荐用户开关,放 `users.allow_concurrent_sessions bool`

## 8. 实现提示

- 文件: `backend/app/api/v1/sessions.py`、`backend/app/services/session_service.py`、`backend/app/core/deps.py`(current_user / get_db_session)、`backend/app/middleware/last_seen_tracker.py`
- 复用: M04 的 JWT 验签
- 与 mockData 关系: 无(前端目前无会话管理 UI)
