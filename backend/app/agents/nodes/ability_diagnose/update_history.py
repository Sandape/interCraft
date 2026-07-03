"""[AC-040-US2 FR-005] update_history node — write to ability_dimensions_history.

Append a snapshot row per dimension to ``ability_dimensions_history``.
The aggregate constraint allows only ``('month','day')``; we use ``'day'``
so each daily snapshot is a single upsert.

R1''' P0: same explicit OTel API + state.db_warnings pattern as
``update_dim_db``. On ``OperationalError`` the node re-raises so the
graph routes through ``update_dim_error_log`` (AC-5.7).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.core.db import get_session_factory
from app.observability import traced_node


@traced_node("ability_diagnose.update_history")
async def update_history_node(state: AbilityDiagnoseState) -> dict:
    """Append snapshot rows to ``ability_dimensions_history`` (one per dimension)."""
    user_id = state.get("user_id", "")
    diagnoses = state.get("diagnoses", [])

    if not user_id or not diagnoses:
        return {}

    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    today = date.today()

    try:
        async with factory() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            user_uuid = UUID(user_id)

            for d in diagnoses:
                dim = d["dimension"]
                score = d["current_score"]
                max_score = float(d.get("max_score", 10)) or 10.0
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
            await session.commit()

        span = trace.get_current_span()
        span.set_attribute("db.rows_affected", len(diagnoses))
        return {}
    except OperationalError as e:
        span = trace.get_current_span()
        span.set_status(StatusCode.ERROR, f"update_history OperationalError: {e}")
        span.record_exception(e)
        warnings = list(state.get("db_warnings", []))
        warnings.append(f"update_history: OperationalError: {e!s}")
        raise


__all__ = ["update_history_node"]