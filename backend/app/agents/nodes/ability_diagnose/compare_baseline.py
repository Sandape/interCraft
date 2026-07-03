"""M18 node — compare_baseline: calculate delta + trend markers (no LLM).

Reads ability_dimensions_history for the last 90 days and compares
with current aggregated scores.
"""
from __future__ import annotations

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.observability import traced_node


@traced_node("ability_diagnose.compare_baseline")
async def compare_baseline_node(state: AbilityDiagnoseState) -> dict:
    """Compare current scores with historical baseline."""
    interview_scores = state.get("interview_scores", [])
    user_id = state.get("user_id", "")

    # Read historical dimensions from DB
    historical_dims = await _query_historical_dimensions(user_id)

    # Compute diagnoses: delta + trend per dimension
    diagnoses = []
    for score in interview_scores:
        dim = score["dimension"]
        current = score["score"]

        historical = _find_historical(historical_dims, dim)
        previous = historical.get("average", current) if historical else current
        delta = current - previous

        if delta > 1.0:
            trend = "up"
        elif delta < -1.0:
            trend = "down"
        else:
            trend = "stable"

        diagnoses.append({
            "dimension": dim,
            "current_score": current,
            "previous_score": previous,
            "delta": round(delta, 1),
            "trend": trend,
            "max_score": score.get("max_score", 10),
            "weight": score.get("weight", 1.0),
        })

    return {
        "historical_dims": historical_dims,
        "current_dims": [{"dimension": d["dimension"], "score": d["current_score"]} for d in diagnoses],
        "diagnoses": diagnoses,
    }


async def _query_historical_dimensions(user_id: str) -> list[dict]:
    """Query ability_dimensions_history for the last 90 days."""
    from uuid import UUID

    from sqlalchemy import text

    from app.core.db import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                """SELECT dimension_key, actual_score, snapshot_date
                FROM ability_dimensions_history
                WHERE user_id = :uid
                AND snapshot_date > current_date - interval '90 days'
                ORDER BY snapshot_date DESC"""
            ),
            {"uid": UUID(user_id) if user_id else UUID(int=0)},
        )
        rows = result.fetchall()
        dims: dict[str, list[float]] = {}
        for row in rows:
            dim = row[0]
            score = float(row[1]) if row[1] is not None else 0
            if dim not in dims:
                dims[dim] = []
            dims[dim].append(score)

        result_list = []
        for dim, scores in dims.items():
            avg = sum(scores) / len(scores) if scores else 0
            result_list.append({
                "dimension": dim,
                "scores": scores,
                "average": round(avg, 1),
                "count": len(scores),
            })
        return result_list


def _find_historical(historical_dims: list[dict], dimension: str) -> dict:
    for h in historical_dims:
        if h["dimension"] == dimension:
            return h
    return {}


__all__ = ["compare_baseline_node"]