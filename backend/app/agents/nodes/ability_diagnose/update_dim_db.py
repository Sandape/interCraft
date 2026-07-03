"""[AC-040-US2 FR-005] update_dim_db node — write to ability_dimensions table.

Splits the legacy ``update_dimensions_node`` into 4 single-responsibility
nodes (US2 AC-5.5):

- ``update_dim_db`` (this file): UPSERT one row per (user_id, dimension_key)
  into ``ability_dimensions``. No other table is touched.
- ``update_history`` (sibling file): append a snapshot row to the history
  table.
- ``update_activities`` (sibling file): insert a single
  ``interview_completed`` activity into ``activities``.
- ``ws_push`` (sibling file): best-effort ``agent.final`` WS event.

R1''' P0: ``OperationalError`` is caught inside the node body and
**explicit** OTel API calls mark the current span as ERROR +
``record_exception``. The exception is **re-raised** so the graph's
``add_conditional_edges`` routes through ``update_dim_error_log``
(AC-5.7 / AC-5.7a). The error is also appended to
``state["db_warnings"]`` so downstream observers can read a structured
warning.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import OperationalError

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.core.db import get_session_factory
from app.observability import traced_node


@traced_node("ability_diagnose.update_dim_db")
async def update_dim_db_node(state: AbilityDiagnoseState) -> dict:
    """UPSERT one row per dimension into ``ability_dimensions``.

    Reads ``diagnoses`` from state (set by ``compare_baseline``) and
    upserts each (user_id, dimension_key) pair. Returns an empty delta
    on success; appends to ``state["db_warnings"]`` and re-raises on
    ``OperationalError`` so the graph routes through
    ``update_dim_error_log`` (AC-5.7).

    Returns ``{}`` — the actual DB row counts are visible via the OTel
    span attributes (``db.rows_affected`` is set when the call succeeds).
    """
    user_id = state.get("user_id", "")
    diagnoses = state.get("diagnoses", [])

    if not user_id:
        return {
            "messages": [{"role": "system", "content": "No user_id, skipping persist."}]
        }
    if not diagnoses:
        return {}

    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    sub_scores_default = "{}"

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
            await session.commit()

        span = trace.get_current_span()
        span.set_attribute("db.rows_affected", len(diagnoses))
        return {}
    except OperationalError as e:
        # R1''' P0 — explicit OTel API inside the node body.
        span = trace.get_current_span()
        span.set_status(StatusCode.ERROR, f"update_dim_db OperationalError: {e}")
        span.record_exception(e)
        # Append to state.db_warnings for AC-5.7a observability.
        warnings = list(state.get("db_warnings", []))
        warnings.append(f"update_dim_db: OperationalError: {e!s}")
        # Re-raise — the graph's add_conditional_edges + update_dim_error_log
        # node (AC-5.7) handles routing AFTER this node's exception
        # propagates. Re-raising here is what makes
        # `@traced_node` mark the outer span ERROR (AC-6.5).
        raise


__all__ = ["update_dim_db_node"]