# M04 · 账号 & 认证

> 状态: draft · 所属领域: B · 优先级: P0
> 引用原文档: §3.2 (users / user_credentials), §4.1, §4.2 (部分), §13.1

## 1. 需求摘要

落地账号体系:邮箱+密码注册、登录(密码 / 短信验证码 / 第三方 OAuth 占位)、JWT 颁发(access 15min + refresh 30 day),敏感凭据(身份证 / 真实姓名 / 薪资范围)加密存储。本模块**不含多端会话管理**(交给 M05)。

## 2. 验收标准

- [ ] `POST /api/v1/auth/register` 邮箱+密码注册,bcrypt cost=12 哈希
- [ ] `POST /api/v1/auth/login` 返回 access(15min) + refresh(30d) token
- [ ] `POST /api/v1/auth/refresh` 用 refresh 换 access,refresh 滚动续期
- [ ] `GET /api/v1/users/me` 用 access 拿当前用户
- [ ] `PATCH /api/v1/users/me/credentials` 写身份证 / 真实姓名 / 薪资,自动 AES-GCM 加密
- [ ] 密码策略校验(≥10 位、大小写、数字、符号)
- [ ] 邮箱 / 手机用 sha256 索引列加速查询
- [ ] 月度 token 配额字段就绪(`monthly_token_quota / monthly_token_used / quota_reset_at`)
- [ ] 每月 1 日 ARQ 任务自动重置 `monthly_token_used = 0`

## 3. 依赖与被依赖关系

**强依赖**: M02(users / user_credentials 表)、M03(加密 / ARQ Worker)
**弱依赖**: 无
**被以下模块依赖**: M05(会话/设备/RLS 启用)、所有需要 user_id 的模块
**外部依赖**:
- `fastapi-users[sqlalchemy]` 或自研 JWT 方案(决策见 §13.1)
- `bcrypt`、`python-jose[cryptography]`
- 第三方 OAuth(MVP 可仅占位 URL)

## 4. 数据模型

**`users` 表关键字段**(基于 §3.2 扩展):
```
id UUID PK
email TEXT NOT NULL UNIQUE
email_sha256 BYTEA NOT NULL UNIQUE  -- 索引用
phone TEXT NULL
phone_sha256 BYTEA NULL UNIQUE
display_name TEXT NULL
password_hash TEXT NOT NULL  -- bcrypt
status TEXT NOT NULL DEFAULT 'active'  -- active / soft_deleted / purged / frozen
llm_provider_pref JSONB NULL
monthly_token_quota INT NOT NULL DEFAULT 100000
monthly_token_used INT NOT NULL DEFAULT 0
quota_reset_at TIMESTAMPTZ NOT NULL  -- 见 A8
created_at / updated_at / deleted_at  -- Mixin
```

**`user_credentials` 表**:
```
user_id UUID PK FK(users.id)
id_card_enc BYTEA NULL  -- AES-256-GCM
real_name_enc BYTEA NULL
salary_range_enc BYTEA NULL
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/auth/register` | 注册,返回 user + access/refresh |
| POST | `/api/v1/auth/login` | 邮箱+密码 / 短信验证码登录 |
| POST | `/api/v1/auth/refresh` | refresh 换 access |
| POST | `/api/v1/auth/logout` | 撤销当前 refresh |
| GET | `/api/v1/users/me` | 当前用户 |
| PATCH | `/api/v1/users/me` | 更新基础资料 |
| PATCH | `/api/v1/users/me/credentials` | 更新敏感凭据(自动加密) |
| POST | `/api/v1/auth/oauth/{provider}/callback` | OAuth 回调(GitHub/Google/微信) |

**WebSocket**: 无(M05 引入)

## 6. 关键设计点

- **JWT payload**: `{sub: user_id, exp, jti, type: 'access'|'refresh'}`,refresh 的 jti 写库便于撤销
- **第三方 OAuth(MVP)**: 仅 GitHub + Google,通过 fastapi-users 内置实现;微信 / 飞书 / 钉钉延后
- **MFA(v1.1)**: TOTP 字段预留 `users.mfa_secret BYTEA NULL`,本模块只埋点不启用
- **凭据展示策略**: 身份证脱敏 `110***********1234`,真实姓名仅本人可见,薪资范围仅本人可见
- **审计**: 登录 / 注销 / 凭据修改全部入 `audit_logs`(具体表由 M22 实现,本模块只发事件)
- **配额重置**: ARQ cron `0 0 1 * *`(每月 1 日 00:00 UTC)→ `UPDATE users SET monthly_token_used=0, quota_reset_at=now()`

## 7. 待澄清

- **[A8]** monthly_token 配额重置策略:本模块实现「每月 1 日 UTC 重置」;按订阅日定制延后
- **[A11]** 设备元数据:决定方案 A(合并到 auth_sessions)还是方案 B(独立 devices 表)→ 本模块采用**方案 A**,M05 落地
- **鉴权选型**: 用 fastapi-users 还是自研 JWT?推荐 fastapi-users(快起步、OAuth 内置)

## 8. 实现提示

- 文件: `backend/app/api/v1/auth.py`、`backend/app/api/v1/users.py`、`backend/app/services/auth_service.py`、`backend/app/services/credentials_service.py`、`backend/app/workers/tasks/monthly_quota_reset.py`、`backend/app/core/security.py`
- 复用: M03 的 `encrypt/decrypt` 给 user_credentials 使用
- 与 mockData 关系: `mockData.ts:7-16` `currentUser`(id, name, email, avatar, title, yearsOfExperience, targetRole, subscription)→ 映射到 users 表;`subscription` 字段需要决定单独建 subscriptions 表还是放 users(MVP 放 users)
