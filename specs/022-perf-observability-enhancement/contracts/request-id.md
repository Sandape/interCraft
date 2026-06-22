# Contract: X-Request-ID Header

**Feature**: 022-perf-observability-enhancement
**Related FRs**: FR-001 ~ FR-005

## Request Header

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `X-Request-ID` | string (UUID or opaque token) | No | 客户端可携带 request_id，未携带时服务端生成 UUID v4 |

## Response Header

| Header | Type | Always Present | Description |
|--------|------|----------------|-------------|
| `X-Request-ID` | string (UUID) | Yes | 服务端最终使用的 request_id（客户端传入或服务端生成）|

## Behavior

1. **Inbound**: FastAPI middleware `RequestIDMiddleware` 读取 `X-Request-ID` header；若为空则生成 `str(uuid.uuid4())`。
2. **Context**: `contextvars.ContextVar("request_id")` set 该值，整个请求生命周期可读。
3. **Outbound**: 响应头注入 `X-Request-ID: <value>`，无论请求是否成功。
4. **Logging**: structlog processor `merge_contextvars` 自动将 `request_id` 字段注入每条日志。
5. **LLM calls**: `llm_client.py` 的 `invoke` / `invoke_stream` / `retry` 日志含 `request_id` 字段。
6. **ARQ worker**: `on_job_start` 钩子中 `bind_contextvars(request_id=job_id)`，worker 中的 LLM 调用日志使用 job_id 作为 request_id。
7. **Error responses**: 即使 500 错误也必须注入 `X-Request-ID` 响应头，便于排障。

## Example

```http
GET /api/v1/agents/error-coach/{tid}/messages HTTP/1.1
Host: api.intercraft.dev
X-Request-ID: abc-123-xyz

HTTP/1.1 200 OK
X-Request-ID: abc-123-xyz
Content-Type: application/json
...
```

## Testing

- 单测: `test_request_id_middleware.py` 断言 (a) 客户端传入则透传；(b) 未传入则生成 UUID；(c) 响应头必有 `X-Request-ID`。
- 集成: HTTP 请求 → LLM 调用 → 日志按 request_id 关联。
- E2E: 既有 round-2 E2E 中断言响应头含 `X-Request-ID`。
