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


async def execute_research_task(ctx: dict, task_id: str, **kwargs: Any) -> dict[str, Any]:
    """REQ-053: full pipeline for a single research task.

    The ``**kwargs`` swallows arq's framework kwargs (notably ``trace_ctx``
    injected by app.core.redis.enqueue_job — see ``build_arq_trace_metadata``).
    """
    # Fold any extra arq kwargs into ctx so downstream consumers (logging,
    # audit, etc.) can read them.
    if kwargs:
        ctx = {**ctx, **kwargs}
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
            if task is not None and task.get("user_id") is not None:
                await session.execute(
                    text("SELECT set_config('app.user_id', :u, true)"),
                    {"u": str(task["user_id"])},
                )
            return await svc.execute_research_task(UUID(task_id))
    except Exception as exc:
        logger.exception("execute_research_task(%s) failed: %s", task_id, exc)
        return {"task_id": task_id, "error": str(exc)}


__all__ = ["scan_interview_research", "execute_research_task"]