"""ARQ task: diagnose_after_interview (Phase 5 M18 full implementation).

Triggered after interview report generation.
Invokes the Ability Diagnose LangGraph subgraph.

REQ-061 T096: emits a canonical ability_insight acceptance envelope (quote /
milestone metadata) before graph work so score vs insight remain separable.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger("workers.ability_diagnose")


def _build_insight_runtime_envelope(user_id: str, session_id: str) -> dict:
    """Build a serializable runtime envelope without requiring a DB session."""
    from app.modules.ai_runtime.adapters import ability_insight as insight

    envelope = insight.build_runtime_envelope(
        user_id=user_id,
        session_id=session_id,
        service_tier="standard",
        trigger="interview",
    )
    return {
        "capability_code": envelope.capability_code,
        "action_code": envelope.action_code,
        "service_tier": envelope.service_tier,
        "input_snapshot_ref": envelope.input_snapshot_ref,
        "input_canonical_hash": envelope.input_canonical_hash,
        "allow_degrade": envelope.allow_degrade,
        "max_points": envelope.max_points,
        "milestones": [
            {
                "code": m.code,
                "label": m.label,
                "weight_basis_points": m.weight_basis_points,
                "max_points": m.max_points,
            }
            for m in envelope.milestones
        ],
        "metadata": dict(envelope.metadata),
        "deterministic_score_independent": True,
    }


async def diagnose_after_interview(ctx: dict, user_id: str, session_id: str) -> dict:
    """Full ability diagnosis using M18 Ability Diagnose subgraph.

    Retries: 3, with exponential backoff (1s/4s/16s).
    """
    logger.info("ability_diagnose.started", user_id=user_id, session_id=session_id)

    runtime_envelope: dict | None = None
    try:
        runtime_envelope = _build_insight_runtime_envelope(user_id, session_id)
        logger.info(
            "ability_diagnose.runtime_envelope",
            user_id=user_id,
            session_id=session_id,
            capability=runtime_envelope["capability_code"],
            max_points=runtime_envelope["max_points"],
            billing_mode=runtime_envelope["metadata"].get("billing_mode"),
        )
    except Exception as exc:
        # Envelope is advisory for dual-write; do not block diagnosis.
        logger.warning(
            "ability_diagnose.runtime_envelope_failed",
            user_id=user_id,
            session_id=session_id,
            error=str(exc),
        )

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
            "runtime_envelope": runtime_envelope,
            # Score updates happen in graph nodes; insight is the AI milestone.
            "failure_category": None,
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
            "runtime_envelope": runtime_envelope,
            # Insight failure must not imply score rollback (FR-040).
            "failure_category": "insight_generation_failed",
            "preserves_deterministic_score": True,
        }


__all__ = ["diagnose_after_interview", "_build_insight_runtime_envelope"]
