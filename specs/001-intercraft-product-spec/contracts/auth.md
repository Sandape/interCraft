# Auth Endpoints (M04)

> 鉴权核心:注册、登录、刷新 access、登出。
> 鉴权库:`fastapi-users[sqlalchemy]` 13.x(JWT strategy + bcrypt,DEC-1);JWT 实现:`PyJWT[cryptography]`(DEC-5)。
> access token TTL = 15 分钟;refresh token TTL = 7 天(spec FR-002)。

## 共享类型

```ts
// 对应 Pydantic schema
type TokenPair = {
  access_token: string;     // JWT
  refresh_token: string;    // 32-byte URL-safe base64
  token_type: "Bearer";
  expires_in: 900;          // 15 min,以秒为单位
}

type PublicUser = {
  id: string;               // uuid v7
  email: string;
  display_name: string | null;
  title: string | null;
  years_of_experience: number | null;
  target_role: string | null;
  bio: string | null;
  subscription: "free" | "pro" | "enterprise";
  created_at: string;       // ISO 8601
  updated_at: string;
}
```

---

## 1. `POST /api/v1/auth/register`

**用途**:邮箱注册。返回 user + token pair(自动登录)。

**Auth**:不需要

**请求**:
```json
{
  "email": "haoran.lin@example.com",
  "password": "P@ssw0rd123",
  "display_name": "林浩然"   // 可选
}
```

**字段校验**:
| 字段 | 规则 | 错误码 |
|---|---|---|
| `email` | 必填,符合 RFC 5322,长度 ≤ 254,服务端 `.lower()` | `validation.format` / `validation.required` |
| `password` | 必填,≥ 8 位 + 数字 + 字母(spec FR-001,plan DEC-8) | `auth.password_too_weak` |
| `display_name` | 可选,长度 ≤ 64 | `validation.range` |

**响应 201**:
```json
{
  "user": { /* PublicUser */ },
  "tokens": { /* TokenPair */ }
}
```

**副作用**:
- 创建 `users` 记录
- 创建 `auth_sessions` 记录(自动登录)
- 5 设备限制检查:若已有 5 个 active session,踢出最早(`last_seen_at` 最小)的 session
- 审计日志:Phase 1 仅结构化日志,`audit_logs` 表在 Phase 6 启用
- `X-Request-ID` 写入日志

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 409 | `auth.email_taken` | 邮箱已被注册(含软删) |
| 422 | `auth.password_too_weak` | 密码策略不达标 |
| 422 | `auth.email_invalid` | 邮箱格式错 |
| 429 | `rate_limit.exceeded` | 触发限流(每 IP 10 req/min) |

---

## 2. `POST /api/v1/auth/login`

**用途**:邮箱 + 密码登录。

**Auth**:不需要

**请求**:
```json
{
  "email": "haoran.lin@example.com",
  "password": "P@ssw0rd123",
  "device_name": "MacBook Pro"  // 可选,设备自定义名
}
```

**响应 200**:
```json
{
  "user": { /* PublicUser */ },
  "tokens": { /* TokenPair */ },
  "evicted_session_id": "uuid-or-null"  // 若触发了 5 设备限制,这里给出被踢出的 session_id
}
```

**副作用**:
- 验证 `password_hash`(bcrypt cost=12,~250ms)
- 创建 `auth_sessions` 记录
- 5 设备限制:删除(soft_delete)最早 `last_seen_at` 的 session
- 被踢出的 session 关联的 refresh token 立即失效(下次 refresh 返回 401)
- 计数指标:`auth_login_attempts_total{result="success"|"failed"|"locked"}`

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.invalid_credentials` | 邮箱不存在 / 密码错 |
| 422 | `auth.email_invalid` | 邮箱格式错 |
| 429 | `rate_limit.exceeded` | 每 IP 10 req/min;失败尝试 5 次锁 15 分钟 |

**错误信息统一**:无论邮箱不存在还是密码错,均返回 `auth.invalid_credentials`(防账号枚举攻击)。

---

## 3. `POST /api/v1/auth/refresh`

**用途**:用 refresh token 换新的 access token。可选地旋转(refresh rotation)。

**Auth**:不需要 access(用 refresh),但需要 `Refresh-Token` 头(避免 Authorization 头语义混淆)

**请求**:
```
POST /api/v1/auth/refresh
Refresh-Token: <refresh_token>
```

**响应 200**:
```json
{
  "tokens": { /* TokenPair */ }
}
```

**Refresh 旋转策略**(spec FR-002):
- 每次成功 refresh → 撤销旧 refresh,颁发新 refresh(refresh rotation)
- 旧 refresh 立即加入黑名单(`auth_sessions.deleted_at = now()`)
- 若旧 refresh 在被撤销后**再次**使用 → **整个用户的所有 session 撤销**(防 token 复用攻击,类似 OAuth2 spec)
- `expires_in` 仍 = 900(仅 access 续期,refresh TTL 在每次 refresh 时重置为 7 天)

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.refresh_invalid` | refresh 伪造 / 过期 / 已撤销 / 已软删 |
| 429 | `rate_limit.exceeded` | 限流 |

---

## 4. `POST /api/v1/auth/logout`

**用途**:登出当前会话(撤销 refresh)。

**Auth**:Bearer access

**请求**:无 body

**响应 204**:No Content

**副作用**:
- 当前 `auth_sessions` soft_delete
- 当前 refresh token 立即失效
- **不**影响其他设备(每端独立 logout)

---

## 5. JWT Payload Schema

```json
{
  "sub": "<user_id>",
  "exp": 1735689600,        // unix timestamp
  "iat": 1735688700,
  "jti": "<unique_token_id>",
  "type": "access",         // 或 "refresh"
  "session_id": "<auth_session_id>"  // 用于 last_seen 更新 + 主动踢出
}
```

**算法**:`HS256`(`JWT_SECRET` 从环境变量读,≥ 32 字节)

**Claims 验证**:
- `exp` 必须未过期
- `type` 必须匹配端点要求(`/auth/refresh` 只接 `type=refresh`)
- `jti` 必须存在于 `auth_sessions.refresh_token_hash`(仅 refresh)

**主动踢出**:`PATCH auth_sessions.deleted_at = now()` → 下次 refresh 或 access 请求返回 401(`auth.session_revoked`)

---

## 6. 密码策略细节(plan DEC-8)

```python
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRES_DIGIT = True
PASSWORD_REQUIRES_LETTER = True
PASSWORD_REQUIRES_UPPERCASE = False  # 可配置
PASSWORD_REQUIRES_SYMBOL = False     # 可配置(更宽松,降低 onboarding 摩擦)
```

**Phase 1 落地**:`≥ 8 位 + 至少 1 个数字 + 至少 1 个字母`。
**未来对齐 M04 §2**:`≥ 10 位 + 数字 + 大写 + 小写 + 符号` —— Phase 2 启动时与 M04 文档 v0.3 修订同步切换。
