# Contract: /metrics Endpoint

**Feature**: 022-perf-observability-enhancement
**Related FRs**: FR-040 ~ FR-046

## Endpoint

```
GET /metrics
```

No authentication (Prometheus scrape convention). 若有反爬需求可加 IP 白名单或 mTLS，本 feature 不涉及。

## Response Format

Prometheus text exposition format:

```
# HELP llm_quota_exhausted_total Total LLM quota exhaustion events
# TYPE llm_quota_exhausted_total counter
llm_quota_exhausted_total{user_id="uuid"} 3

# HELP llm_quota_available Current available LLM quota per user
# TYPE llm_quota_available gauge
llm_quota_available{user_id="uuid"} 497000

# HELP checkpointer_reconnect_total Total checkpointer reconnection attempts
# TYPE checkpointer_reconnect_total counter
checkpointer_reconnect_total 7

# HELP ws_connections_active Current active WebSocket connections
# TYPE ws_connections_active gauge
ws_connections_active 12

# HELP arq_jobs_queued Current ARQ jobs queued per queue
# TYPE arq_jobs_queued gauge
arq_jobs_queued{queue="default"} 5
arq_jobs_queued{queue="ability"} 0

# HELP arq_jobs_failed_total Total ARQ jobs failed per queue
# TYPE arq_jobs_failed_total counter
arq_jobs_failed_total{queue="default"} 2
arq_jobs_failed_total{queue="ability"} 0

# ... 既有 5 类指标 (http / auth / resume / lock / outbox)
```

## Metric Catalog (≥ 15 names)

| # | Metric | Type | Source |
|---|--------|------|--------|
| 1 | `http_requests_total` | Counter | 既有 |
| 2 | `http_request_duration_seconds` | Histogram | 既有 |
| 3 | `auth_logins_total` | Counter | 既有 |
| 4 | `auth_login_failures_total` | Counter | 既有 |
| 5 | `resume_exports_total` | Counter | 既有 |
| 6 | `lock_acquisitions_total` | Counter | 既有 |
| 7 | `lock_contentions_total` | Counter | 既有 |
| 8 | `outbox_pending` | Gauge | 既有 |
| 9 | `outbox_flushed_total` | Counter | 既有 |
| 10 | `llm_quota_exhausted_total` | Counter | **新增** |
| 11 | `llm_quota_available` | Gauge | **新增** |
| 12 | `checkpointer_reconnect_total` | Counter | **新增** |
| 13 | `ws_connections_active` | Gauge | **新增** |
| 14 | `arq_jobs_queued` | Gauge | **新增** |
| 15 | `arq_jobs_failed_total` | Counter | **新增** |

## Performance Contract

- `/metrics` 响应时间 < 50ms（P95）。
- Prometheus scrape 间隔 15s，不引入 > 5ms 业务请求延迟。
- Counter/Gauge 更新是 O(1) 原子操作，对业务请求零开销。

## Testing

- 单测 `test_metrics_collectors.py`: 断言每个指标的 type 和 label keys。
- 集成: 触发 LLM 配额耗尽 → `/metrics` 含 `llm_quota_exhausted_total{user_id=...} N`。
- E2E: 不在 round-2 覆盖（metrics 是运维端点），仅单测 + 集成验证。
