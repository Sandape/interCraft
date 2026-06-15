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


__all__ = [
    "auth_active_sessions",
    "auth_login_attempts_total",
    "auth_register_attempts_total",
    "http_request_duration_seconds",
    "http_requests_total",
    "lock_acquire_attempts_total",
    "lock_audit_write_failures_total",
    "lock_heartbeat_latency_seconds",
    "outbox_conflict_total",
    "outbox_replay_total",
    "resume_branches_total",
    "resume_versions_total",
]
