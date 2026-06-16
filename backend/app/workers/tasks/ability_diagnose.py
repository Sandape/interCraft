"""ARQ task: ability_diagnose — runs the M18 Ability Diagnose subgraph.

Triggered by app.modules.interviews.service after a 5-question interview
completes. Calls the LangGraph state graph to:
    1. aggregate per-dimension scores from the interview report
    2. compare with the user's historical baseline
    3. generate improvement insights via the LLM
    4. persist new ability_dimensions / history / activity rows

Retries: 3 (ARQ WorkerSettings.max_tries), with warning on final failure.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger("workers.ability_diagnose")


async def ability_diagnose(ctx: dict, user_id: str, session_id: str) -> dict:
    """Execute the ability diagnosis subgraph for a finished interview.

    ARQ calls this with positional (ctx, **kwargs). The kwargs match the names
    passed to `enqueue_job("ability_diagnose", user_id=..., session_id=...)`.
    """
    logger.info(
        "ability_diagnose.started",
        user_id=user_id,
        session_id=session_id,
    )
    try:
        from app.agents.graphs.ability_diagnose import get_ability_diagnose_graph

        graph = get_ability_diagnose_graph()
        result = await graph.run(user_id=user_id, session_id=session_id)
        logger.info(
            "ability_diagnose.completed",
            user_id=user_id,
            session_id=session_id,
            diagnoses=len(result.get("diagnoses", []) or []),
            insights=len(result.get("insights", []) or []),
        )
        return {
            "status": "ok",
            "user_id": user_id,
            "session_id": session_id,
            "diagnoses": len(result.get("diagnoses", []) or []),
            "insights": len(result.get("insights", []) or []),
        }
    except Exception:
        logger.error(
            "ability_diagnose.failed",
            user_id=user_id,
            session_id=session_id,
            exc_info=True,
        )
        raise


__all__ = ["ability_diagnose"]
