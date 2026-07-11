"""ARQ task functions for the interview-research pipeline (REQ-053).

Two functions are exposed:
- `scan_interview_research` — cron job, every 10 min, scans for jobs whose
  interview_time falls in [now+4h55m, now+5h5m] and enqueues
  execute_research_task for each match.
- `execute_research_task` — per-task pipeline: search → generate → save →
  deliver. Receives task_id as a keyword arg.

Both follow the standard ARQ cron/task contract:
    async def task(ctx: dict, **kwargs) -> dict
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.core.db import get_session_factory
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# Redis lock key + TTL for the scan cron (prevents overlapping scans).
SCAN_LOCK_KEY = "lock:scan_interview_research"
SCAN_LOCK_TTL_SECONDS = 540  # 9 minutes — cron runs every 10 minutes


async def scan_interview_research(ctx: dict) -> dict[str, Any]:
    """REQ-053 FR-009: scan jobs with interviews ~5h away, create tasks.

    Uses a Redis lock to prevent overlapping scans. Lock TTL is 9 minutes —
    if a scan is still running 9 min after starting, the next cron tick will
    skip it; after lock expires, normal scan resumes (US2-AC6).
    """
    redis = get_redis()
    lock_token = f"scan-{ctx.get('job_id', 'cron')}"

    acquired = await redis.set(SCAN_LOCK_KEY, lock_token, nx=True, ex=SCAN_LOCK_TTL_SECONDS)
    if not acquired:
        logger.info("scan_interview_research: lock held, skipping this tick")
        return {
            "skipped": True,
            "reason": "lock_held",
        }

    factory = get_session_factory()
    try:
        async with factory() as session:
            from app.modules.research.service import ResearchService
            svc = ResearchService(session)

            async def _enqueue(task_id: str) -> None:
                """Enqueue a research task to ARQ. Best-effort."""
                try:
                    from app.core.redis import enqueue_job
                    await enqueue_job("execute_research_task", task_id=task_id)
                except Exception as exc:
                    logger.warning("Failed to enqueue task %s: %s", task_id, exc)

            summary = await svc.scan_and_enqueue_jobs(enqueue_fn=_enqueue)
            summary["lock_token"] = lock_token
            return summary
    except Exception as exc:
        logger.exception("scan_interview_research failed: %s", exc)
        return {"error": str(exc)}
    finally:
        # Release the lock only if we still own it
        try:
            current = await redis.get(SCAN_LOCK_KEY)
            if current is not None:
                # Compare as string (redis returns bytes in some clients)
                current_str = current.decode() if isinstance(current, bytes) else str(current)
                if current_str == lock_token:
                    await redis.delete(SCAN_LOCK_KEY)
        except Exception:
            pass


def _research_runtime_preview(
    *,
    job_id: str,
    user_id: str,
    opt_in: bool,
    service_tier: str = "standard",
) -> dict[str, Any]:
    """REQ-061 T096 light wiring: quote/opt-in envelope before pipeline work."""
    from app.modules.ai_runtime.adapters import research as research_adapter

    preview = research_adapter.preview_quote(
        job_id=job_id,
        service_tier=service_tier,
        opt_in=opt_in,
    )
    gate = research_adapter.require_opt_in(opt_in=opt_in, accepted=opt_in)
    snap = research_adapter.build_input_snapshot(
        job_id=job_id,
        user_id=user_id,
        opt_in=opt_in,
        service_tier=service_tier,
    )
    return {
        "quote": {
            "job_id": preview.job_id,
            "service_tier": preview.service_tier,
            "max_points": preview.max_points,
            "opt_in": preview.opt_in,
            "can_disable": preview.can_disable,
            "consume_points_before_accept": preview.consume_points_before_accept,
        },
        "opt_in_gate": {
            "allowed": gate.allowed,
            "reason": gate.reason,
            "may_reserve_points": gate.metadata.get("may_reserve_points", False),
        },
        "input_snapshot": snap,
    }


def evidence_gated_plan_fallback_retry(
    *,
    plan_status: str = "failed",
    user_consented: bool = False,
    allow_degrade_on_quote: bool = True,
    report_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """REQ-061 T075 — plan fallback is independently retryable and evidence-gated.

    Does not charge points; returns a decision envelope for service/worker callers.
    """
    from app.modules.ai_runtime.adapters import interview as iv

    retry = iv.decide_retry(domain_status="failed", component="plan_fallback")
    degrade = iv.decide_degradation(
        plan_status=plan_status,
        user_consented=user_consented,
        allow_degrade_on_quote=allow_degrade_on_quote,
    )
    report_gate = None
    if report_evidence is not None:
        verdict = iv.evaluate_quality_gate(
            milestone_code="report",
            result_payload=report_evidence,
        )
        report_gate = {
            "code": verdict.code,
            "deliverable": verdict.deliverable,
            "chargeable": verdict.chargeable,
        }
    allowed = bool(retry.allowed and degrade.allowed)
    return {
        "allowed": allowed,
        "component": "plan_fallback",
        "retry": {
            "allowed": retry.allowed,
            "new_execution_required": retry.metadata.get("new_execution_required"),
        },
        "degrade": {
            "allowed": degrade.allowed,
            "reason": degrade.reason,
            "settlement_tier": degrade.metadata.get("settlement_tier"),
        },
        "report_gate": report_gate,
        "evidence_gated": True,
    }


async def execute_research_task(ctx: dict, task_id: str, **kwargs: Any) -> dict[str, Any]:
    """REQ-053: full pipeline for a single research task.

    The ``**kwargs`` swallows arq's framework kwargs (notably ``trace_ctx``
    injected by app.core.redis.enqueue_job — see ``build_arq_trace_metadata``).
    """
    # Fold any extra arq kwargs into ctx so downstream consumers (logging,
    # audit, etc.) can read them.
    if kwargs:
        ctx = {**ctx, **kwargs}
    # Optional opt-in flag for REQ-061 dual-write (defaults False = no auto charge).
    opt_in = bool(ctx.get("opt_in", kwargs.get("opt_in", False)))
    service_tier = str(ctx.get("service_tier", kwargs.get("service_tier", "standard")))
    factory = get_session_factory()
    try:
        async with factory() as session:
            from sqlalchemy import text

            from app.modules.research.service import ResearchService

            svc = ResearchService(session)
            # Bind RLS before the pipeline touches user-scoped tables
            # (ability_dimensions, error_questions, agents, …). Without this,
            # policies that cast ``current_setting('app.user_id')`` to uuid
            # raise ``invalid input syntax for type uuid: ""``.
            task = await svc.task_repo.get_by_id(UUID(task_id))
            runtime_envelope: dict[str, Any] | None = None
            if task is not None and task.get("user_id") is not None:
                await session.execute(
                    text("SELECT set_config('app.user_id', :u, true)"),
                    {"u": str(task["user_id"])},
                )
                try:
                    runtime_envelope = _research_runtime_preview(
                        job_id=str(task.get("job_id") or ""),
                        user_id=str(task["user_id"]),
                        opt_in=opt_in,
                        service_tier=service_tier,
                    )
                    if not runtime_envelope["opt_in_gate"]["allowed"]:
                        logger.info(
                            "execute_research_task: opt-in gate blocked reservation "
                            "task_id=%s reason=%s",
                            task_id,
                            runtime_envelope["opt_in_gate"]["reason"],
                        )
                except Exception as env_exc:
                    logger.warning(
                        "execute_research_task runtime envelope failed: %s", env_exc
                    )
            result = await svc.execute_research_task(UUID(task_id))
            if isinstance(result, dict) and runtime_envelope is not None:
                result = {**result, "runtime_envelope": runtime_envelope}
            return result
    except Exception as exc:
        logger.exception("execute_research_task(%s) failed: %s", task_id, exc)
        return {"task_id": task_id, "error": str(exc)}


__all__ = [
    "scan_interview_research",
    "execute_research_task",
    "_research_runtime_preview",
    "evidence_gated_plan_fallback_retry",
]