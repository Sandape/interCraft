# API Contracts: InterCraft

**Status**: Phase 1 + Phase 2 + Phase 3 output · **Date**: 2026-06-13 · **Phase 1 Plan**: [../plan.md](../plan.md) · **Phase 2 Plan**: [../phase-2.md](../phase-2.md) · **Phase 3 Plan**: [../phase-3.md](../phase-3.md)

> 本目录定义 **Phase 1 + Phase 2** 全部 **REST API 契约**。
> 全部契约通过 FastAPI 自动生成 OpenAPI 3.1 schema(`/api/v1/openapi.json`)并由前端 `openapi-typescript` 消费(plan DEC-9)。
> 端点路径前缀统一为 `/api/v1/`(versioning)。
> 鉴权:Bearer JWT(本目录契约除 `/healthz`、`/auth/register`、`/auth/login`、`/auth/refresh` 外,均要求 `Authorization: Bearer <access_token>`)。
> 内部 API 路径 `/internal/*`,仅供 service 间调用,需 internal middleware 校验 source IP。

## 文件清单

### Phase 1(M01-M07 + M04/M05)

| 文件 | 端点 | 模块 |
|---|---|---|
| [health.md](./health.md) | `GET /healthz`,`GET /api/v1/openapi.json` | M01 |
| [events.md](./events.md) | 共享响应:错误码 / 状态码 / 错误响应 schema / 请求头约定 | — |
| [auth.md](./auth.md) | `POST /auth/register`,`POST /auth/login`,`POST /auth/refresh`,`POST /auth/logout` | M04 |
| [users.md](./users.md) | `GET /users/me`,`PATCH /users/me` | M04 |
| [sessions.md](./sessions.md) | `GET /users/me/sessions`,`DELETE /users/me/sessions/{id}`,`GET /users/me/sessions/{id}` | M05 |
| [resumes.md](./resumes.md) | `GET /resume-branches`,`POST /resume-branches`,`GET /resume-branches/{id}`,`PATCH /resume-branches/{id}`,`DELETE /resume-branches/{id}`,`POST /resume-branches/{id}/refresh-from-parent` | M06 |
| [blocks.md](./blocks.md) | `GET /resume-branches/{id}/blocks`,`POST /resume-branches/{id}/blocks`,`PATCH /resume-blocks/{id}`,`PATCH /resume-blocks/{id}/reorder`,`DELETE /resume-blocks/{id}` | M06 |
| [versions.md](./versions.md) | `GET /resume-branches/{id}/versions`,`POST /resume-branches/{id}/versions`,`GET /resume-branches/{id}/versions/{version_no}`,`POST /resume-branches/{id}/versions/{version_no}/rollback` | M07 |

### Phase 2(M08-M11)

| 文件 | 端点 | 模块 |
|---|---|---|
| [error-questions.md](./error-questions.md) | `GET /error-questions`,`POST /error-questions`,`GET /error-questions/{id}`,`PATCH /error-questions/{id}`,`DELETE /error-questions/{id}`,`POST /error-questions/{id}/reset` | M08 |
| [abilities.md](./abilities.md) | `GET /ability-dimensions`,`GET /ability-dimensions/{key}`,`PATCH /ability-dimensions/{key}`,`POST /ability-dimensions/{key}/toggle`,`GET /ability-dimensions/history`,`GET /ability-dimensions/dimensions-meta` | M09 |
| [tasks.md](./tasks.md) | `GET /tasks`,`POST /tasks`,`GET /tasks/{id}`,`PATCH /tasks/{id}`,`DELETE /tasks/{id}` + 内部 `POST /internal/tasks/find-or-create` | M10 |
| [activities.md](./activities.md) | `GET /activities`(游标分页)+ 内部 `POST /internal/activities/log` | M10 |
| [jobs.md](./jobs.md) | `GET /jobs`,`POST /jobs`,`GET /jobs/{id}`,`PATCH /jobs/{id}`,`PATCH /jobs/{id}/status`,`DELETE /jobs/{id}`,`GET /jobs/stats`,`GET /jobs/{id}/timeline` | M10 |
| [interview-sessions.md](./interview-sessions.md) | `GET /interview-sessions`,`GET /interview-sessions/{id}`(Phase 2 只读骨架;POST/PATCH/DELETE 405) | M11 |

### Phase 3(M12-M13)

| 文件 | 端点 | 模块 |
|---|---|---|
| [locks.md](./locks.md) | `POST /locks/acquire`,`DELETE /locks/{id}`,`GET /locks/{resource_type}/{resource_id}` + WS `/api/v1/ws/locks` | M12 |
| [outbox.md](./outbox.md) | `POST /outbox/replay`,`GET /outbox/status` | M13 |

## 公共约定

详见 [events.md](./events.md):
- 状态码:200 / 201 / 204 / 400 / 401 / 403 / 404 / 405 / 409 / 422 / 423 / 429 / 500 / 501
- 错误响应统一 schema:`{ error: { code, message, details? } }`
- 请求头:`Authorization: Bearer <access_token>`,`X-Request-ID`(可选,无则服务端生成)
- 响应头:`X-Request-ID`(与请求对齐),`ETag`(资源版本,GUID),`Cache-Control: no-store`(用户数据)
- **Phase 2 新增状态码**:
  - `405 Method Not Allowed` — M11 interview-sessions 的 POST/PATCH/DELETE(Phase 2 范围外)
  - `501 Not Implemented` — 内部 API 占位路由(Phase 4 启用)

## 速率限制

- `/auth/*` 路由:每 IP 10 req/min(token bucket)
- 业务路由:每 user 600 req/min
- 触发后返回 `429 Too Many Requests` + `Retry-After: <seconds>`
- **Phase 2 备注**:`/internal/*` 路由不参与速率限制(internal middleware 校验 source IP)

## 版本化

- 当前:`/api/v1/`
- 不兼容变更 → `/api/v2/`(spec §「Development Workflow」Semantic Versioning)
- Pydantic Schema 字段增减必须经过 OpenAPI 校验
- **Phase 2 版本**:`app/__version__.py = "0.2.0"`(Phase 1 = 0.1.0)
- **Phase 3 版本**:`app/__version__.py = "0.3.0"`

## 自动生成与消费

```bash
# 后端:启动时自动生成
GET http://localhost:8000/api/v1/openapi.json → openapi.json
# Phase 2 端点数:23 → 30+
# Phase 3 端点数:30+ → 35+(+5 REST + 1 WS)

# 前端:从 openapi.json 生成 TS 类型
npm run gen:api
# 输出:src/api/schema.d.ts(纳入 .gitignore,构建时生成)
```

## WS 契约

- **Phase 3**:`/api/v1/ws/locks` 端点上线(锁事件推送:lock.acquired / lock.released / lock.lost + 客户端心跳)。详见 [locks.md](./locks.md) §3。
- **Phase 4** (M14 LangGraph 基础设施):新增 AI streaming WS 端点(token.delta / node.started / etc.),届时追加 `ws-interview.md`。
- 客户端 WS 骨架:`src/api/ws.ts`(Phase 1 就位,Phase 3 扩展锁事件处理)。

## 内部 API

- 路径前缀:`/internal/*`(Phase 2 新增)
- 鉴权:middleware 校验 source IP = api 进程(127.0.0.1 / Docker network 内)
- 用途:Service 内部调用,避免公开暴露
- Phase 2 已定义:
  - `POST /internal/tasks/find-or-create`(JobService 调用)
  - `POST /internal/activities/log`(各 Service 调用)
  - `POST /internal/interview-sessions`(M15 启用,Phase 2 占位 501)
  - `PATCH /internal/interview-sessions/{id}`(M15 启用,Phase 2 占位 501)
- OpenAPI schema 中标记为 `internal: true`,前端 `openapi-typescript` 跳过生成

## 契约测试

- 后端:`backend/tests/contract/test_openapi_schema.py` 校验 schema 合法 + 必需路径存在 + Pydantic 校验逻辑
- **Phase 2 扩展**:校验 7 个新模块(M08-M11)所有端点存在 + 405/501 路由正确返回
- 前端:`src/repositories/__tests__/*.test.ts` 跑 MSW 拦截(handlers.ts 与真实后端对齐)
- **Phase 2 新增**:5 个新 Repository 的 MSW handler 测试
- 跨端:每次后端 PR 触发 `openapi-typescript` diff,前端仓库自动 PR bot 提示类型漂移
- **Phase 2 新增**:游标分页跨端 parity test(activities 端点)
