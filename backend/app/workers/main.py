"""ARQ WorkerSettings entry point.

Run: `uv run arq app.workers.main.WorkerSettings`
"""
from __future__ import annotations

import os
from typing import Any, ClassVar

from arq.connections import RedisSettings
from arq.cron import cron

# REQ-053 fix: use app.core.config.get_settings() instead of raw os.environ.get()
# so that the .env file is honored by pydantic-settings. Without this, ARQ
# workers would fall back to localhost:6379 and fail to consume jobs even
# when REDIS_URL is correctly set in .env.
from app.core.config import get_settings as _get_app_settings
from app.core.logging import bind_request_context
from app.core.metrics import arq_jobs_failed_total
from app.observability.tracing import TraceContext, bind_trace_context, extract_trace_context
from app.modules.locks.service import LockService
from app.modules.versions.auto_snapshot import auto_snapshot_branch
from app.workers.tasks.ability_diagnose import ability_diagnose
from app.workers.tasks.cleanup_expired_exports import cleanup_expired_exports
from app.workers.tasks.compute_embedding import compute_embedding_task
from app.workers.tasks.create_next_audit_partition import create_next_audit_partition
from app.workers.tasks.daily_reconcile import daily_reconcile
from app.workers.tasks.interview_research import execute_research_task, scan_interview_research
from app.workers.tasks.monthly_quota_reset import monthly_quota_reset
from app.workers.tasks.physical_cleanup import physical_cleanup
from app.workers.tasks.purge_expired_accounts import purge_expired_accounts
from app.workers.tasks.reset_monthly_quota_cron import reset_monthly_quota_cron
from app.workers.tasks.agents_outbound_drain import agents_outbound_drain

REDIS_URL = _get_app_settings().redis_url

_auto_release = LockService()


async def on_job_start(ctx: dict[str, Any]) -> None:
    """Bind request_id for non-HTTP context (022 US1 FR-004)."""
    job_id = str(ctx.get("job_id", ""))
    if job_id:
        bind_request_context(request_id=job_id)
    bind_arq_trace_context(ctx)


def bind_arq_trace_context(ctx: dict[str, Any]) -> TraceContext:
    raw = ctx.get("trace_ctx") or {}
    if isinstance(raw, dict):
        trace_ctx = extract_trace_context(raw)
    else:
        trace_ctx = TraceContext(run_id=str(ctx.get("job_id", "")) or None)
    if trace_ctx.run_id is None and ctx.get("job_id"):
        trace_ctx = TraceContext(
            run_id=str(ctx.get("job_id")),
            trace_id=trace_ctx.trace_id,
            span_id=trace_ctx.span_id,
        )
    bind_trace_context(
        run_id=trace_ctx.run_id,
        trace_id=trace_ctx.trace_id,
        span_id=trace_ctx.span_id,
    )
    return trace_ctx


async def on_failure(ctx: dict[str, Any]) -> None:
    """Job lifecycle: increment failed counter (022 US5)."""
    arq_jobs_failed_total.labels(queue="default").inc()


async def auto_release_stale(ctx: dict[str, Any]) -> list[Any]:
    """ARQ cron: scan and release stale locks every 30s (Phase 3 T062)."""
    return await _auto_release.auto_release_stale()


class WorkerSettings:
    functions: ClassVar = [
        auto_snapshot_branch,
        monthly_quota_reset,
        auto_release_stale,
        daily_reconcile,
        ability_diagnose,
        purge_expired_accounts,
        physical_cleanup,
        cleanup_expired_exports,
        create_next_audit_partition,
        reset_monthly_quota_cron,
        # REQ-048 T-NEW-1 — register compute_embedding_task so arq workers
        # pick it up. Without this entry the task would be defined but
        # never invoked by the worker process.
        compute_embedding_task,
        # REQ-052: outbound safety net cron. Picks up pending outbound
        # messages whose ilink_pool long-poll task is degraded / cancelled
        # and would otherwise sit pending forever.
        agents_outbound_drain,
        # REQ-053: scan + execute interview research tasks.
        scan_interview_research,
        execute_research_task,
    ]
    redis_settings: ClassVar = RedisSettings.from_dsn(REDIS_URL)
    cron_jobs: ClassVar = [
        cron(monthly_quota_reset, name="monthly_quota_reset", month=1, day=1, hour=0, minute=0),
        cron(auto_release_stale, name="auto_release_stale", second={0, 30}),
        cron(daily_reconcile, name="daily_reconcile", hour=3, minute=0),
        cron(purge_expired_accounts, name="purge_expired_accounts", hour=2, minute=0),
        cron(physical_cleanup, name="physical_cleanup", weekday="sun", hour=3, minute=0),
        cron(cleanup_expired_exports, name="cleanup_expired_exports", minute=0),
        cron(create_next_audit_partition, name="create_next_audit_partition", month=1, day=1, hour=0, minute=0),
        cron(reset_monthly_quota_cron, name="reset_monthly_quota_cron", month=1, day=1, hour=0, minute=0),
        cron(agents_outbound_drain, name="agents_outbound_drain", second={0, 30}),
        # REQ-053: scan every 10 minutes for interviews ~5h away.
        cron(scan_interview_research, name="scan_interview_research", minute={0, 10, 20, 30, 40, 50}),
    ]
    keep_result: ClassVar = 60
    max_tries: ClassVar = 3
    on_job_start: ClassVar = on_job_start
    on_failure: ClassVar = on_failure


__all__ = ["REDIS_URL", "WorkerSettings", "bind_arq_trace_context"]
