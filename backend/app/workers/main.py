"""ARQ WorkerSettings entry point.

Run: `uv run arq app.workers.main.WorkerSettings`
"""

from __future__ import annotations

from typing import Any, ClassVar

from arq.connections import RedisSettings
from arq.cron import cron

from app import __version__

# REQ-053 fix: use app.core.config.get_settings() instead of raw os.environ.get()
# so that the .env file is honored by pydantic-settings. Without this, ARQ
# workers would fall back to localhost:6379 and fail to consume jobs even
# when REDIS_URL is correctly set in .env.
from app.core.config import get_settings as _get_app_settings
from app.core.db import dispose_engine
from app.core.logging import bind_request_context, configure_logging, get_logger
from app.core.redis import (
    ARQ_HEALTH_CHECK_INTERVAL_SECONDS,
    ARQ_HEALTH_CHECK_KEY,
    ARQ_QUEUE_NAME,
)

# REQ-061: ARQ composition root — workers assemble ExecutionContext via
# ``create_worker_execution_context`` rather than importing FastAPI deps.
from app.modules.ai_runtime.composition import (  # noqa: F401
    create_worker_execution_context,
)
from app.modules.locks.service import LockService
from app.modules.versions.auto_snapshot import auto_snapshot_branch
from app.observability.tracing import (
    TraceContext,
    TracingConfig,
    bind_trace_context,
    extract_trace_context,
    init_tracing,
    shutdown_tracing,
)
from app.workers.tasks.ability_diagnose import ability_diagnose
from app.workers.tasks.agent_command_outbox_drain import agent_command_outbox_drain
from app.workers.tasks.agent_task_recovery import (
    recover_agent_task,
    scan_agent_task_recovery,
)
from app.workers.tasks.agents_outbound_drain import agents_outbound_drain
from app.workers.tasks.ai_cost_guard import ai_cost_guard
from app.workers.tasks.ai_daily_point_grant import ai_daily_point_grant
from app.workers.tasks.ai_daily_reconciliation import ai_daily_reconciliation
from app.workers.tasks.ai_data_deletion import run_ai_data_deletion
from app.workers.tasks.ai_evaluation import ai_evaluation
from app.workers.tasks.ai_point_expiry import ai_point_expiry
from app.workers.tasks.ai_projection_delivery import deliver_ai_projections
from app.workers.tasks.ai_release_guard import ai_release_guard
from app.workers.tasks.ai_task_dispatch import dispatch_ai_task_intent
from app.workers.tasks.ai_task_recovery import recover_ai_task, scan_ai_task_recovery
from app.workers.tasks.cleanup_expired_exports import cleanup_expired_exports
from app.workers.tasks.compute_embedding import compute_embedding_task
from app.workers.tasks.create_next_audit_partition import create_next_audit_partition
from app.workers.tasks.daily_reconcile import daily_reconcile
from app.workers.tasks.dummy import ping
from app.workers.tasks.interview_research import (
    execute_research_task,
    scan_interview_research,
)
from app.workers.tasks.monthly_quota_reset import monthly_quota_reset
from app.workers.tasks.physical_cleanup import physical_cleanup
from app.workers.tasks.purge_expired_accounts import purge_expired_accounts
from app.workers.tasks.reset_monthly_quota_cron import reset_monthly_quota_cron
from app.workers.tasks.resume_analysis import execute_resume_analysis
from app.workers.tasks.resume_derive import execute_resume_derive

REDIS_URL = _get_app_settings().redis_url

_auto_release = LockService()
log = get_logger("arq.worker")


async def on_worker_startup(ctx: dict[str, Any]) -> None:
    """Initialize the same process-wide observability surface as the API.

    REQ-081 P0: validate the checkpointer init state BEFORE the ARQ
    worker starts consuming graph-backed business jobs. When the
    readiness snapshot does NOT report ``up``, this function raises
    ``CheckpointerUnavailableError`` — ARQ catches it internally and
    the worker main loop stops, preventing business-job consumption
    until the dependency is restored or the deployment is rolled back.

    The preheat call itself is fail-closed (returns readiness even on
    internal exception) so this function only sees typed states; the
    raise/no-raise decision is based on ``readiness.state`` alone.

    ``ctx["intercraft_worker_started"]`` is set to ``True`` only when
    the checkpointer is confirmed healthy. ``on_worker_shutdown`` uses
    this flag to log an honest ``started`` count.
    """
    configure_logging()
    settings = _get_app_settings()
    init_tracing(
        TracingConfig(
            service_name=f"{settings.otel_service_name}-worker",
            exporter="otlp" if settings.otel_enabled else "none",
            otlp_endpoint=settings.otel_exporter_otlp_endpoint or None,
            sample_ratio=settings.otel_trace_sample_ratio,
            langsmith_api_key=settings.langsmith_api_key or None,
            langsmith_project=settings.langsmith_project,
        )
    )
    from app.agents.checkpointer import preheat as _checkpointer_preheat

    readiness = await _checkpointer_preheat()
    is_ready = readiness.state == "up"
    ctx["checkpointer_ready"] = is_ready
    ctx["checkpointer_reason"] = readiness.reason
    ctx["intercraft_worker_started"] = is_ready
    log.info(
        "worker.start",
        version=__version__,
        env=settings.app_env,
        queue=ARQ_QUEUE_NAME,
        health_check_key=ARQ_HEALTH_CHECK_KEY,
        health_check_interval_seconds=ARQ_HEALTH_CHECK_INTERVAL_SECONDS,
        checkpointer_state=readiness.state,
        checkpointer_reason=readiness.reason,
        started=is_ready,
    )
    # REQ-081 P0: prevent ARQ from consuming graph-backed jobs when
    # the checkpointer is not healthy.  ARQ does not read ctx flags
    # from the health record — the only way to keep the worker from
    # consuming is to raise here so ARQ stops its main loop.
    if not is_ready:
        from app.agents.exceptions import CheckpointerUnavailableError

        raise CheckpointerUnavailableError(
            f"checkpointer state={readiness.state} reason={readiness.reason}; "
            "worker startup aborted to prevent silent graph-op failures",
            retry_after=30,
        )


async def on_worker_shutdown(ctx: dict[str, Any]) -> None:
    """Release application-owned clients without touching ARQ's pool.

    Closes the shared singleton pool and every shard pool exactly once
    (tolerating already-closed pools). Does NOT close ARQ's Redis
    client — ARQ owns its own pool and the heartbeat probe relies on
    that client staying open during the graceful drain window.
    """
    from app.agents.checkpointer import close_checkpointer

    await close_checkpointer()
    try:
        from app.agents.checkpointer_pool import close_all_pools

        await close_all_pools()
    except Exception:
        log.exception("worker.shard_pool_shutdown_failed")
    try:
        from app.channels.message_handler import shutdown_llm_client

        await shutdown_llm_client()
    except Exception:
        log.exception("worker.llm_client_shutdown_failed")
    await dispose_engine()
    shutdown_tracing()
    log.info("worker.stop", started=bool(ctx.get("intercraft_worker_started")))


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


async def auto_release_stale(ctx: dict[str, Any]) -> list[Any]:
    """ARQ cron: scan and release stale locks every 30s (Phase 3 T062)."""
    return await _auto_release.auto_release_stale()


class WorkerSettings:
    functions: ClassVar = [
        # No-cost structured transport smoke used by lifecycle verification.
        ping,
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
        agent_command_outbox_drain,
        recover_agent_task,
        scan_agent_task_recovery,
        # REQ-053: scan + execute interview research tasks.
        scan_interview_research,
        execute_research_task,
        # REQ-055: one-click resume derive.
        execute_resume_derive,
        execute_resume_analysis,
        # REQ-061: AI runtime projections, recovery, metering schedules.
        deliver_ai_projections,
        run_ai_data_deletion,
        dispatch_ai_task_intent,
        scan_ai_task_recovery,
        recover_ai_task,
        ai_daily_point_grant,
        ai_point_expiry,
        ai_daily_reconciliation,
        ai_cost_guard,
        # REQ-061 US11: online eval + gray release guard.
        ai_evaluation,
        ai_release_guard,
    ]
    redis_settings: ClassVar = RedisSettings.from_dsn(REDIS_URL)
    queue_name: ClassVar = ARQ_QUEUE_NAME
    health_check_key: ClassVar = ARQ_HEALTH_CHECK_KEY
    health_check_interval: ClassVar = ARQ_HEALTH_CHECK_INTERVAL_SECONDS
    cron_jobs: ClassVar = [
        cron(monthly_quota_reset, name="monthly_quota_reset", month=1, day=1, hour=0, minute=0),
        cron(auto_release_stale, name="auto_release_stale", second={0, 30}),
        cron(daily_reconcile, name="daily_reconcile", hour=3, minute=0),
        cron(purge_expired_accounts, name="purge_expired_accounts", hour=2, minute=0),
        cron(physical_cleanup, name="physical_cleanup", weekday="sun", hour=3, minute=0),
        cron(cleanup_expired_exports, name="cleanup_expired_exports", minute=0),
        cron(
            create_next_audit_partition,
            name="create_next_audit_partition",
            month=1,
            day=1,
            hour=0,
            minute=0,
        ),
        cron(
            reset_monthly_quota_cron,
            name="reset_monthly_quota_cron",
            month=1,
            day=1,
            hour=0,
            minute=0,
        ),
        cron(agents_outbound_drain, name="agents_outbound_drain", second={0, 30}),
        cron(
            agent_command_outbox_drain,
            name="agent_command_outbox_drain",
            second={5, 15, 25, 35, 45, 55},
        ),
        cron(
            scan_agent_task_recovery,
            name="scan_agent_task_recovery",
            second={15, 45},
        ),
        # REQ-053: scan every 10 minutes for interviews ~5h away.
        cron(
            scan_interview_research, name="scan_interview_research", minute={0, 10, 20, 30, 40, 50}
        ),
        # REQ-061 recovery + projections + Shanghai point grant/expiry.
        cron(scan_ai_task_recovery, name="scan_ai_task_recovery", second={20, 50}),
        cron(deliver_ai_projections, name="deliver_ai_projections", second={10, 40}),
        cron(ai_daily_point_grant, name="ai_daily_point_grant", hour=16, minute=5),  # ~00:05 CST
        cron(ai_point_expiry, name="ai_point_expiry", hour=16, minute=10),
        # Preliminary prior-day reconciliation before next Shanghai noon (~04:00 CST).
        cron(ai_daily_reconciliation, name="ai_daily_reconciliation", hour=20, minute=0),
        # Budget / abnormal-consumption scan every hour.
        cron(ai_cost_guard, name="ai_cost_guard", minute=15),
        # REQ-061 US11: online eval hourly; gray-stage guard every 10 min.
        cron(ai_evaluation, name="ai_evaluation", minute=25),
        cron(ai_release_guard, name="ai_release_guard", minute={0, 10, 20, 30, 40, 50}),
    ]
    keep_result: ClassVar = 60
    max_tries: ClassVar = 3
    on_startup: ClassVar = on_worker_startup
    on_shutdown: ClassVar = on_worker_shutdown
    on_job_start: ClassVar = on_job_start


__all__ = ["REDIS_URL", "WorkerSettings", "bind_arq_trace_context"]
