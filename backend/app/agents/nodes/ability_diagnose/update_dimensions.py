"""M18 node — update_dimensions: persist results to DB + WS push."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.core.db import get_session_factory


async def update_dimensions_node(state: AbilityDiagnoseState) -> dict:
    """Write interview-derived scores to ability_dimensions (additive, source='interview'),
    ability_dimensions_history, and activity feed. Push WS event.

    Schema (verified against migrations 0001/0007):
        ability_dimensions(id, user_id, dimension_key, actual_score, ideal_score,
                           sub_scores, is_active, source, last_updated_at,
                           created_at, updated_at)
        ability_dimensions_history(id, user_id, dimension_key, snapshot_date,
                                   aggregate, actual_score, ideal_score, created_at)
        activities(id, user_id, type, actor_type, payload_json, request_id, occurred_at)
    """
    user_id = state.get("user_id", "")
    insights = state.get("insights", [])
    diagnoses = state.get("diagnoses", [])
    session_id = state.get("session_id", "")

    if not user_id:
        return {"messages": [{"role": "system", "content": "No user_id, skipping persist."}]}

    factory = get_session_factory()
    async with factory() as session:
        # Set RLS context for ability_dimensions / activities (both user-scoped).
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )
        user_uuid = UUID(user_id)

        now = datetime.now(timezone.utc)
        today = date.today()
        sub_scores_default = json.dumps({})

        # 1) Upsert ability_dimensions (one row per (user_id, dimension_key) per
        # the unique constraint ability_dimensions_user_key_unique). An interview
        # score replaces the manual baseline in place — last-write-wins by
        # `source` priority. `id` has no DB default — supply uuid4() per row.
        # `sub_scores` is jsonb; bind via bindparam(type_=JSONB) — see project memory.
        upsert_dim = text(
            """INSERT INTO ability_dimensions
            (id, user_id, dimension_key, actual_score, ideal_score, sub_scores,
             is_active, source, last_updated_at, created_at, updated_at)
            VALUES (:id, :uid, :dim, :score, :ideal, :sub_scores,
                    true, 'interview', :now, :now, :now)
            ON CONFLICT (user_id, dimension_key) DO UPDATE
            SET actual_score = EXCLUDED.actual_score,
                ideal_score = EXCLUDED.ideal_score,
                source = 'interview',
                last_updated_at = EXCLUDED.last_updated_at,
                updated_at = EXCLUDED.updated_at"""
        ).bindparams(bindparam("sub_scores", type_=JSONB))

        for d in diagnoses:
            dim = d["dimension"]
            score = d["current_score"]
            max_score = float(d.get("max_score", 10)) or 10.0
            await session.execute(
                upsert_dim,
                {
                    "id": uuid4(),
                    "uid": user_uuid,
                    "dim": dim,
                    "score": Decimal(str(score)),
                    "ideal": Decimal(str(max_score)),
                    "sub_scores": sub_scores_default,
                    "now": now,
                },
            )

            # 2) Append a history row for the dashboard timeline. The aggregate
            # check constraint allows only ('month','day'); we use 'day' so each
            # daily snapshot is a single upsert. `id` has no DB default.
            await session.execute(
                text(
                    """INSERT INTO ability_dimensions_history
                    (id, user_id, dimension_key, snapshot_date, aggregate,
                     actual_score, ideal_score, created_at)
                    VALUES (:id, :uid, :dim, :snapshot_date, 'day',
                            :score, :ideal, :now)
                    ON CONFLICT (user_id, dimension_key, aggregate, snapshot_date) DO UPDATE
                    SET actual_score = EXCLUDED.actual_score,
                        ideal_score = EXCLUDED.ideal_score,
                        created_at = EXCLUDED.created_at"""
                ),
                {
                    "id": uuid4(),
                    "uid": user_uuid,
                    "dim": dim,
                    "snapshot_date": today,
                    "score": Decimal(str(score)),
                    "ideal": Decimal(str(max_score)),
                    "now": now,
                },
            )

        # 3) Surface the diagnosis as a single activity in the user's feed.
        # `activities_type_chk` whitelists type values; "interview_completed" is
        # the natural bucket for ability-diagnosis follow-ups from an interview.
        # jsonb binding rule — see note above.
        insert_act = text(
            """INSERT INTO activities
            (id, user_id, type, actor_type, payload_json, request_id, occurred_at)
            VALUES (:id, :uid, :type, :actor_type, :payload_json, :req_id, :now)"""
        ).bindparams(bindparam("payload_json", type_=JSONB))

        if insights:
            # Collapse all insights into one activity — keeps the feed clean and
            # avoids exceeding the check constraint whitelist.
            await session.execute(
                insert_act,
                {
                    "id": uuid4(),
                    "uid": user_uuid,
                    "type": "interview_completed",
                    "actor_type": "agent",
                    "payload_json": json.dumps(
                        {
                            "session_id": session_id,
                            "source": "ability_diagnose",
                            "title": "能力诊断已生成",
                            "content": "模拟面试后的能力画像与改进建议",
                            "insights": insights,
                        },
                        ensure_ascii=False,
                    ),
                    "req_id": None,
                    "now": now,
                },
            )

        await session.commit()

    # Push WS agent.final event (best-effort)
    try:
        from app.core.ws import connection_manager
        from app.core.ws_events import make_agent_final

        dims_summary = ", ".join(
            f"{d['dimension']}: {d.get('current_score', 0):.1f}" for d in diagnoses
        )
        event = make_agent_final(
            thread_id=session_id or "",
            graph="ability_diagnose",
            summary=f"能力画像已更新:{dims_summary}",
            dimensions_updated=True,
        )
        await connection_manager.send_to_user(user_id, event)
    except Exception:
        pass

    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    f"Updated {len(diagnoses)} dimensions, "
                    f"{len(insights)} insights written."
                ),
            }
        ],
    }


__all__ = ["update_dimensions_node"]
