"""M18 node — update_dimensions: persist results to DB + WS push."""
from __future__ import annotations

import json
from uuid import UUID, uuid4

from sqlalchemy import text

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.core.db import get_session_factory


async def update_dimensions_node(state: AbilityDiagnoseState) -> dict:
    """Write diagnoses to ability_dimensions, history, and activities. Push WS event."""
    user_id = state.get("user_id", "")
    insights = state.get("insights", [])
    diagnoses = state.get("diagnoses", [])
    session_id = state.get("session_id", "")

    if not user_id:
        return {"messages": [{"role": "system", "content": "No user_id, skipping persist."}]}

    factory = get_session_factory()
    async with factory() as session:
        # Set RLS context
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )
        user_uuid = UUID(user_id)

        # Update ability_dimensions actual scores
        for d in diagnoses:
            dim = d["dimension"]
            score = d["current_score"]
            await session.execute(
                text(
                    """UPDATE ability_dimensions
                    SET actual = :score, updated_at = now()
                    WHERE user_id = :uid AND dimension = :dim"""
                ),
                {"score": score, "uid": user_uuid, "dim": dim},
            )

            # Insert history record
            await session.execute(
                text(
                    """INSERT INTO ability_dimensions_history
                    (user_id, dimension, actual, recorded_at)
                    VALUES (:uid, :dim, :score, now())"""
                ),
                {"uid": user_uuid, "dim": dim, "score": score},
            )

        # Write insights to activities
        for insight in insights:
            dim = insight.get("dimension", "general")
            suggestions = insight.get("suggestions", [])
            for suggestion in suggestions:
                await session.execute(
                    text(
                        """INSERT INTO activities (id, user_id, type, title, content, meta, created_at)
                        VALUES (:id, :uid, :type, :title, :content, :meta, now())"""
                    ),
                    {
                        "id": uuid4(),
                        "uid": user_uuid,
                        "type": "ability.suggestion",
                        "title": f"改进建议 - {dim}",
                        "content": suggestion,
                        "meta": json.dumps({"dimension": dim, "session_id": session_id, "source": "ability_diagnose"}),
                    },
                )

        await session.commit()

    # Push WS agent.final event
    try:
        from app.core.ws import connection_manager
        from app.core.ws_events import make_agent_final

        dims_updated = [d["dimension"] for d in diagnoses]
        dims_summary = ", ".join([f"{d}: +{d.get('delta', 0)}" for d in diagnoses])
        event = make_agent_final(
            thread_id=session_id or "",
            graph="ability_diagnose",
            summary=f"能力画像已更新:{dims_summary}",
            dimensions_updated=True,
        )
        await connection_manager.send_to_user(user_id, event)
    except Exception:
        pass  # WS push is best-effort

    return {
        "messages": [{"role": "system", "content": f"Updated {len(diagnoses)} dimensions, {len(insights)} insights written."}],
    }


__all__ = ["update_dimensions_node"]
