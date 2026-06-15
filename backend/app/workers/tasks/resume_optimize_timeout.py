"""ARQ task: resume_optimize_timeout — scan for stale M16 sessions.

Runs as periodic ARQ cron (every 5 minutes).
Releases locks on resume branches where the optimization thread
has been running for more than 30 minutes without a decision.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger("workers.resume_optimize_timeout")

_TIMEOUT_MINUTES = 30


async def resume_optimize_timeout(ctx: dict) -> dict:
    """Scan and release stale resume optimization locks.

    Iterates through active resume_optimize threads and releases
    locks on branches that have been waiting for user input
    beyond the timeout threshold.
    """
    logger.info("resume_optimize_timeout.scan_start")
    released_count = 0

    try:
        from app.agents.graphs.resume_optimize import get_resume_optimize_graph

        graph = get_resume_optimize_graph()
        released_count = await _scan_and_release(graph)
    except Exception as exc:
        logger.error("resume_optimize_timeout.error", error=str(exc))
        return {"status": "error", "error": str(exc), "released_count": 0}

    logger.info("resume_optimize_timeout.scan_end", released=released_count)
    return {"status": "ok", "released_count": released_count}


async def _scan_and_release(graph) -> int:
    """Scan active threads and release stale locks."""
    released = 0
    try:
        from app.core.db import get_session_factory
        from sqlalchemy import text

        factory = get_session_factory()
        async with factory() as session:
            # Find resume_branch locks older than 30 minutes
            result = await session.execute(
                text(
                    """SELECT resource_id FROM locks
                    WHERE resource_type = 'resume_branch'
                    AND acquired_at < now() - interval :timeout_minutes
                    AND status = 'locked'"""
                ),
                {"timeout_minutes": f"{_TIMEOUT_MINUTES} minutes"},
            )
            rows = result.fetchall()

            for row in rows:
                resource_id = row[0]
                try:
                    from app.modules.locks.redis_store import release as redis_release
                    from app.modules.locks.redis_store import _key

                    key = _key("resume_branch", str(resource_id))
                    await redis_release(key)
                    released += 1
                    logger.info("lock_released_stale", resource_id=str(resource_id))
                except Exception as exc:
                    logger.warning("lock_release_failed", resource_id=str(resource_id), error=str(exc))
    except Exception as exc:
        logger.warning("scan_failed", error=str(exc))

    return released


__all__ = ["resume_optimize_timeout"]
