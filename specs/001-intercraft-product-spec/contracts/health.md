# Health & OpenAPI Endpoints

> M01 — 项目骨架。最小契约,Phase 1 演示用 `/healthz` 验证服务可用。

## 1. `GET /healthz`

**用途**:健康检查(数据库 + Redis + 版本号)。供 docker-compose healthcheck + CI 验证。

**Auth**:不需要

**请求**:无

**响应 200**:
```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "version": "0.1.0"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `"ok" \| "degraded" \| "down"` | 整体状态 |
| `db` | `"ok" \| "down"` | PostgreSQL 连通性(`SELECT 1`) |
| `redis` | `"ok" \| "down"` | Redis 连通性(`PING`) |
| `version` | `string` | `app.__version__` |

**响应 503**(`status="down"`):
```json
{
  "status": "down",
  "db": "down",
  "redis": "ok",
  "version": "0.1.0"
}
```

**注**:Phase 1 设计为:**任何一个依赖 down,status=down**(fail-fast,便于 demo 排查)。生产环境可改为 `degraded`(降级但可用)。

---

## 2. `GET /api/v1/openapi.json`

**用途**:OpenAPI 3.1 schema 导出。前端 `openapi-typescript` 消费。

**Auth**:不需要

**响应 200**:标准 OpenAPI 3.1 JSON,体积较大(几十 KB)。生成时间 < 200ms。

**契约测试**:`backend/tests/contract/test_openapi_schema.py` 校验:
- 必需 paths 存在(自动遍历)
- 必需 schemas 存在
- `info.version` == `app.__version__`
- `info.title` == "InterCraft API"

---

## 3. `GET /api/v1/redoc`

**用途**:ReDoc 渲染的 API 文档(开发期)。

**Auth**:不需要

**响应 200**:`text/html`

---

## 4. `GET /metrics`

**用途**:Prometheus 文本格式指标。M01 起步,Phase 1 仅暴露基础 counter/histogram(plan §「Observability」决议)。

**Auth**:不需要(内网/Pod 间)

**响应 200**:`text/plain; version=0.0.4`
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",path="/api/v1/auth/login",status="200"} 42
...
# HELP http_request_duration_seconds HTTP request latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.005",method="GET",path="/api/v1/users/me"} 100
...
```

**Phase 1 暴露的指标**:
- `http_requests_total{method,path,status}` (counter)
- `http_request_duration_seconds{method,path,status}` (histogram)
- `auth_login_attempts_total{result}` (counter,result=success/failed/locked)
- `auth_active_sessions{user_id}` (gauge,采样)
- `resume_branches_total` (gauge)
- `resume_versions_total` (gauge)

AI 专用指标在 Phase 4 引入。
