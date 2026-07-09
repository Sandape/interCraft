"""Prometheus metrics."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---- HTTP ----
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ---- Auth ----
auth_login_attempts_total = Counter(
    "auth_login_attempts_total",
    "Auth login attempts",
    ["result"],  # success | failed | locked
)
auth_register_attempts_total = Counter(
    "auth_register_attempts_total",
    "Auth registration attempts",
    ["result"],
)
auth_active_sessions = Gauge(
    "auth_active_sessions",
    "Current number of active auth sessions",
)
auth_refresh_attempts_total = Counter(
    "auth_refresh_attempts_total",
    "Total auth refresh attempts by result and reason",
    ["result", "reason"],
)

# ---- Resume ----
resume_branches_total = Gauge("resume_branches_total", "Current number of active resume branches")
resume_versions_total = Counter(
    "resume_versions_total",
    "Resume versions created",
    ["trigger"],  # manual | auto | ai
)


# ---- Lock (Phase 3) ----
lock_acquire_attempts_total = Counter(
    "lock_acquire_attempts_total",
    "Lock acquire attempts",
    ["result"],  # ok | conflict
)
lock_heartbeat_latency_seconds = Histogram(
    "lock_heartbeat_latency_seconds",
    "Lock heartbeat latency (seconds)",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
lock_audit_write_failures_total = Counter(
    "lock_audit_write_failures_total",
    "Lock audit log write failures",
)

# ---- Outbox (Phase 3) ----
outbox_replay_total = Counter(
    "outbox_replay_total",
    "Outbox replay entries processed",
    ["result"],  # ok | conflict | failed
)
outbox_conflict_total = Counter(
    "outbox_conflict_total",
    "Outbox replay conflicts detected",
)

# ---- Feature 022: LLM quota & AI layer ----
llm_quota_exhausted_total = Counter(
    "llm_quota_exhausted_total",
    "Total LLM quota exhaustion events",
    ["user_id"],
)
llm_quota_available = Gauge(
    "llm_quota_available",
    "Current available LLM quota per user",
    ["user_id"],
)

# ---- Feature 022: Checkpointer (埋点位置由 023 触发递增) ----
checkpointer_reconnect_total = Counter(
    "checkpointer_reconnect_total",
    "Total checkpointer reconnection attempts",
)

# ---- Feature 022: WebSocket ----
ws_connections_active = Gauge(
    "ws_connections_active",
    "Current active WebSocket connections",
)

# ---- Feature 022: ARQ ----
arq_jobs_queued = Gauge(
    "arq_jobs_queued",
    "Current ARQ jobs queued per queue",
    ["queue"],
)
arq_jobs_failed_total = Counter(
    "arq_jobs_failed_total",
    "Total ARQ jobs failed per queue",
    ["queue"],
)

# ---- Feature 038: Structured output observability ----
structured_invocation_total = Counter(
    "structured_invocation_total",
    "Total structured LLM invocations",
    ["node", "contract", "status", "failure_category", "fallback_used"],
)


# ---- Feature 043: Observability (US-1) + Checkpoint pool (US-2) ----
# Per spec FR-008 (Constitution V Observability compliance) + L041-001
# mini-batch naming convention: each metric is independent and additive
# — we don't replace the existing checkpointer_reconnect_total; the
# new pool_size gauge complements the legacy reconnect counter.
llm_call_total = Counter(
    "llm_call_total",
    "Total LLM calls by agent + model",
    ["agent", "model"],
)
llm_call_latency_seconds = Histogram(
    "llm_call_latency_seconds",
    "LLM call latency in seconds by agent",
    ["agent"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)
node_execution_total = Counter(
    "node_execution_total",
    "Total LangGraph node executions",
    ["agent", "node", "outcome"],  # outcome: ok | error
)
checkpointer_pool_size = Gauge(
    "checkpointer_pool_size",
    "Active connections in checkpointer pool",
    ["pool_id"],
)
checkpointer_reconnect_attempts_total = Counter(
    "checkpointer_reconnect_attempts_total",
    "Total checkpointer reconnect attempts by level + outcome",
    ["level", "outcome"],  # level: L1|L2|L3  outcome: retry|rebuild|fail
)
langsmith_export_total = Counter(
    "langsmith_export_total",
    "Total LangSmith export attempts by outcome",
    ["outcome"],  # ok | skip | error
)

# ---- REQ-045: LLM Ops eval workflow ----
llm_ops_eval_runs_total = Counter(
    "llm_ops_eval_runs_total",
    "Total REQ-045 LLM Ops eval runs by bounded suite/environment/status labels",
    ["suite", "environment", "status"],
)
llm_ops_export_decisions_total = Counter(
    "llm_ops_export_decisions_total",
    "Total REQ-045 external export decisions",
    ["destination", "environment", "representation_level", "decision"],
)
llm_ops_judge_calibration_total = Counter(
    "llm_ops_judge_calibration_total",
    "Total REQ-045 judge calibration outcomes",
    ["rubric", "status"],
)
llm_ops_trace_coverage_ratio = Gauge(
    "llm_ops_trace_coverage_ratio",
    "REQ-045 covered AI workflow trace correlation ratio",
    ["surface", "environment"],
)
llm_ops_langsmith_sync_latency_seconds = Histogram(
    "llm_ops_langsmith_sync_latency_seconds",
    "REQ-045 LangSmith sync latency in seconds",
    ["mode", "status"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)


__all__ = [
    "arq_jobs_failed_total",
    "arq_jobs_queued",
    "structured_invocation_total",
    "auth_active_sessions",
    "auth_login_attempts_total",
    "auth_refresh_attempts_total",
    "auth_register_attempts_total",
    "checkpointer_pool_size",
    "checkpointer_reconnect_attempts_total",
    "checkpointer_reconnect_total",
    "http_request_duration_seconds",
    "http_requests_total",
    "langsmith_export_total",
    "llm_ops_eval_runs_total",
    "llm_ops_export_decisions_total",
    "llm_ops_judge_calibration_total",
    "llm_ops_langsmith_sync_latency_seconds",
    "llm_ops_trace_coverage_ratio",
    "llm_call_latency_seconds",
    "llm_call_total",
    "llm_quota_available",
    "llm_quota_exhausted_total",
    "lock_acquire_attempts_total",
    "lock_audit_write_failures_total",
    "lock_heartbeat_latency_seconds",
    "node_execution_total",
    "outbox_conflict_total",
    "outbox_replay_total",
    "resume_branches_total",
    "resume_versions_total",
    "ws_connections_active",
]
