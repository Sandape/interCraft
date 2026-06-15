"""ARQ task: ability_diagnose (Phase 4 basic — T008).

Triggered after interview report generation.
Writes initial ability_dimensions + ability_dimensions_history.
Full agent implementation in Phase 5.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger("workers.ability_diagnose")


async def ability_diagnose(ctx: dict, user_id: str, session_id: str) -> dict:
    """Basic ability diagnosis — writes dimension scores.

    Phase 4 basic version: writes placeholder data.
    Full scoring agent in Phase 5.

    Retries: 3, with warning on final failure.
    """
    logger.info("ability_diagnose.started", user_id=user_id, session_id=session_id)
    # Placeholder — full implementation in Phase 5
    return {"status": "ok", "user_id": user_id, "session_id": session_id}


__all__ = ["ability_diagnose"]
