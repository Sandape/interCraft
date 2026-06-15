# Shared API Conventions: InterCraft Phase 1

> 跨所有契约的公共约定:状态码、错误响应 schema、请求/响应头、限流、版本化。

## 1. URL 约定

- 全部业务 API 路径前缀:`/api/v1/`
- 资源用复数名词:`/resume-branches`、`/resume-blocks`、`/users`、`/sessions`
- 关系子资源:`/resume-branches/{id}/blocks`、`/resume-branches/{id}/versions`
- 动作子资源(动词):`/resume-blocks/{id}/reorder`、`/resume-branches/{id}/refresh-from-parent`
- 路径参数:UUID v7,小写 36 字符
- 查询参数:`snake_case`

## 2. 请求头

| 头 | 必填 | 说明 |
|---|---|---|
| `Authorization` | 视端点 | `Bearer <access_token>`,除 `/healthz`、`/auth/register`、`/auth/login`、`/auth/refresh` 外必填 |
| `Content-Type` | POST/PATCH 必填 | `application/json; charset=utf-8` |
| `Accept` | 可选 | `application/json`(默认) |
| `X-Request-ID` | 可选 | 客户端生成的 UUID(透传到日志);无则服务端生成 |
| `X-Idempotency-Key` | POST 写操作建议 | 防止重复提交(Phase 1 暂不强制消费,Phase 3 启用) |
| `If-Match` | PATCH/DELETE 资源时建议 | ETag,Phase 1 暂不强制消费 |

## 3. 响应头

| 头 | 必有 | 说明 |
|---|---|---|
| `Content-Type` | 必有 | `application/json; charset=utf-8` |
| `X-Request-ID` | 必有 | 与请求对齐 |
| `X-RateLimit-Limit` | 必有 | 当前配额(每分钟请求数) |
| `X-RateLimit-Remaining` | 必有 | 剩余配额 |
| `X-RateLimit-Reset` | 必有 | 重置时间(UNIX 秒) |
| `ETag` | 资源返回 200/201 时 | 资源指纹(uuid v7),强校验 |
| `Cache-Control` | 必有 | `no-store`(用户数据) |

## 4. 状态码语义

| 状态 | 语义 | Phase 1 触发场景 |
|---|---|---|
| 200 OK | 成功 + 返回数据 | GET / PATCH / POST(非创建) |
| 201 Created | 创建成功,返回新资源 | POST 创建类(register、create branch、create block、create version) |
| 204 No Content | 成功 + 无 body | DELETE 成功 / logout 成功 |
| 400 Bad Request | 请求格式错误(JSON 解析失败、字段类型错) | 普遍 |
| 401 Unauthorized | 未提供 token / token 无效 / 过期 | 普遍 |
| 403 Forbidden | RLS 阻断 / 跨用户访问 | 跨用户访问测试用 |
| 404 Not Found | 资源不存在 / 已软删除 | 访问已删资源 |
| 409 Conflict | 唯一键冲突 / 状态机冲突 | 创建已存在的 email / 重复用户名 |
| 422 Unprocessable Entity | 字段值不合法(密码强度、邮箱格式) | 业务校验失败 |
| 423 Locked | 资源被其他会话持锁 | Phase 3 启用,Phase 1 暂不返回 |
| 429 Too Many Requests | 限流触发 | 超阈值时 |
| 500 Internal Server Error | 内部错误,带 `X-Request-ID` 供追溯 | 普遍 |
| 503 Service Unavailable | DB / Redis 不可用 | 启动期或维护期 |

## 5. 错误响应统一 Schema

**所有非 2xx 响应** 必走下列 JSON 结构(`application/problem+json` 也可接受,Phase 1 用 JSON):

```json
{
  "error": {
    "code": "string_machine_readable",
    "message": "string_human_readable",
    "details": {
      "field_errors": [
        {
          "field": "email",
          "code": "invalid_format",
          "message": "邮箱格式不合法"
        }
      ]
    },
    "request_id": "uuid"
  }
}
```

| 字段 | 必有 | 说明 |
|---|---|---|
| `error.code` | 必有 | 机器可读错误码(参见 §6) |
| `error.message` | 必有 | 人类可读消息(i18n 前只用中文) |
| `error.details` | 可选 | 附加上下文(如字段级错误) |
| `error.details.field_errors` | 422 时必有 | 字段级错误列表 |
| `error.request_id` | 必有 | 与 `X-Request-ID` 头一致,供追溯 |

## 6. 错误码(Error Code 字典)

| code | HTTP | 说明 |
|---|---|---|
| `auth.invalid_credentials` | 401 | 邮箱/密码错误 |
| `auth.token_expired` | 401 | access 过期(refresh 可用) |
| `auth.token_invalid` | 401 | token 伪造 / 格式错 |
| `auth.token_missing` | 401 | 未提供 Authorization |
| `auth.email_taken` | 409 | 邮箱已被注册 |
| `auth.password_too_weak` | 422 | 密码策略不达标 |
| `auth.email_invalid` | 422 | 邮箱格式错 |
| `auth.refresh_invalid` | 401 | refresh 无效 / 过期 / 已撤销 |
| `auth.too_many_devices` | 409 | 5 设备限制触发(实际是踢出最早,**不**应返回 409;保留代码) |
| `user.not_found` | 404 | 用户不存在 |
| `user.deleted` | 410 | 账号已注销(Phase 6) |
| `resume.not_found` | 404 | 简历分支不存在 |
| `resume.version_not_found` | 404 | 版本不存在 |
| `resume.invalid_status` | 422 | status 枚举值错 |
| `block.not_found` | 404 | 块不存在 |
| `block.invalid_order_index` | 422 | 字符串分数非法 |
| `version.not_full_snapshot` | 422 | rollback 目标必须能完整还原 |
| `version.base_deleted` | 409 | base_version 已被删除(E7) |
| `validation.required` | 422 | 必填字段缺失 |
| `validation.type` | 422 | 字段类型错 |
| `validation.format` | 422 | 字段格式错(email / uuid / etc.) |
| `validation.range` | 422 | 字段值越界 |
| `rate_limit.exceeded` | 429 | 触发限流 |
| `internal.error` | 500 | 内部错误 |
| `internal.unavailable` | 503 | 服务不可用 |

## 7. 分页

> Phase 1 仅 `GET /resume-branches` / `GET /resume-branches/{id}/blocks` / `GET /resume-branches/{id}/versions` 需要分页。

请求:
```
?cursor=<opaque>&limit=20&order_by=-last_edited_at
```

响应:
```json
{
  "data": [ ... ],
  "pagination": {
    "next_cursor": "opaque_or_null",
    "has_more": true
  }
}
```

- 游标分页(spec FR-051)
- 默认 `limit=20`,最大 `limit=100`
- `order_by` 形如 `-field`(降序)或 `field`(升序);Phase 1 白名单:`-last_edited_at`、`-created_at`、`-version_no`、`order_index`

## 8. 软删除语义

- 删除 = `deleted_at = now()`(物理保留)
- 所有 `GET / LIST` 默认过滤 `deleted_at IS NULL`
- 跨用户访问已软删除资源 → `404`(而不是 `410`,与未存在一致,避免泄露存在性)

## 9. CORS

- Phase 1 开发:`Access-Control-Allow-Origin: http://localhost:5173`
- 生产:动态 origin(配置 `CORS_ALLOWED_ORIGINS` 环境变量,逗号分隔)
- `Access-Control-Allow-Credentials: true`(支持 cookie / 鉴权头)
- 预检 OPTIONS:204

## 10. Content Negotiation

- 仅支持 `application/json`
- 不支持 `application/xml`、`text/plain`(返回 406)
