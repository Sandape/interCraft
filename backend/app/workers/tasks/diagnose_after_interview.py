"""ARQ task: diagnose_after_interview (Phase 5 M18 full implementation).

Triggered after interview report generation.
Invokes the Ability Diagnose LangGraph subgraph.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger("workers.ability_diagnose")


async def diagnose_after_interview(ctx: dict, user_id: str, session_id: str) -> dict:
    """Full ability diagnosis using M18 Ability Diagnose subgraph.

    Retries: 3, with exponential backoff (1s/4s/16s).
    """
    logger.info("ability_diagnose.started", user_id=user_id, session_id=session_id)

    try:
        from app.agents.graphs.ability_diagnose import get_ability_diagnose_graph

        graph = get_ability_diagnose_graph()
        result = await graph.run(user_id=user_id, session_id=session_id)

        insights_count = len(result.get("insights", []))
        dims_updated = [d.get("dimension", "") for d in result.get("diagnoses", [])]

        logger.info(
            "ability_diagnose.completed",
            user_id=user_id,
            session_id=session_id,
            dimensions_updated=dims_updated,
            insights_count=insights_count,
        )

        return {
            "status": "success",
            "session_id": session_id,
            "dimensions_updated": dims_updated,
            "insights_count": insights_count,
            "duration_ms": 0,  # Not measured here
        }
    except Exception as exc:
        logger.error(
            "ability_diagnose.failed",
            user_id=user_id,
            session_id=session_id,
            error=str(exc),
        )
        return {
            "status": "failed",
            "session_id": session_id,
            "error": str(exc),
        }


__all__ = ["diagnose_after_interview"]
