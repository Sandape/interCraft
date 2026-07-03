"""[AC-040-US2 FR-005] update_activities node — write to activities table.

Insert a single ``interview_completed`` activity into ``activities``,
collapsing all insights into one row to keep the activity feed clean
and respect the ``activities_type_chk`` whitelist.

R1''' P0: same explicit OTel API + state.db_warnings pattern as
``update_dim_db``. On ``OperationalError`` the node re-raises so the
graph routes through ``update_dim_error_log`` (AC-5.7).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import OperationalError

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.core.db import get_session_factory
from app.observability import traced_node


@traced_node("ability_diagnose.update_activities")
async def update_activities_node(state: AbilityDiagnoseState) -> dict:
    """Insert a single ``interview_completed`` activity row."""
    user_id = state.get("user_id", "")
    insights = state.get("insights", [])
    session_id = state.get("session_id", "")

    if not user_id or not insights:
        return {}

    factory = get_session_factory()
    now = datetime.now(timezone.utc)

    insert_act = text(
        """INSERT INTO activities
        (id, user_id, type, actor_type, payload_json, request_id, occurred_at)
        VALUES (:id, :uid, :type, :actor_type, :payload_json, :req_id, :now)"""
    ).bindparams(bindparam("payload_json", type_=JSONB))

    try:
        async with factory() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            await session.execute(
                insert_act,
                {
                    "id": uuid4(),
                    "uid": UUID(user_id),
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

        span = trace.get_current_span()
        span.set_attribute("db.rows_affected", 1)
        return {}
    except OperationalError as e:
        span = trace.get_current_span()
        span.set_status(StatusCode.ERROR, f"update_activities OperationalError: {e}")
        span.record_exception(e)
        warnings = list(state.get("db_warnings", []))
        warnings.append(f"update_activities: OperationalError: {e!s}")
        raise


__all__ = ["update_activities_node"]