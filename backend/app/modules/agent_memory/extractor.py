"""Semantic memory extractor — pulls facts from completed interview state.

Spec FR-005: "System MUST extract new memories from completed agent
interactions via a post-node hook."

US1 scope: rule-based extractor (no LLM call). Reads position / company /
dimension_scores from the post-interview state and produces 3 fact types:

  - target_position (source=user_asserted, confidence=1.0)
      The user entered this in the session create form; high confidence.
  - target_company (source=user_asserted, confidence=1.0)
      Same as above.
  - identified_weakness (source=extracted_from_llm_output, confidence=0.7)
      Bottom-2 dimensions from the interview report. Confidence is
      lower because the dimension scores are noisy (5-question sample).
  - stated_preference (source=system_inferred, confidence=0.4)
      Extracted from interview_plan.focus_areas if weights are skewed
      (≥0.4 on a single area). Low confidence because plan weights are
      LLM-generated.

The extractor is deterministic — given the same input state, it always
produces the same facts. This makes it testable without LLM mocks.

Conflict resolution: handled by AgentMemoryRepository.upsert_semantic_memory
(latest-wins). The extractor just produces candidates; the repository
decides whether to supersede.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.modules.agent_memory.redactor import redact
from app.modules.agent_memory.repository import AgentMemoryRepository

logger = structlog.get_logger(__name__)


# Dimension labels (mirrors DIMENSION_LABELS in ability_profile api.py)
_DIM_LABELS: dict[str, str] = {
    "tech_depth": "技术深度",
    "architecture": "架构能力",
    "engineering_practice": "工程实践",
    "communication": "沟通表达",
    "algorithm": "算法能力",
    "business": "业务理解",
}

# Confidence scores per fact type. Keep these in one place so reviewers
# can reason about the extractor's belief calibration.
_CONFIDENCE = {
    "target_position": 1.0,
    "target_company": 1.0,
    "identified_weakness": 0.7,
    "stated_preference": 0.4,
}


def extract_facts(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure function: extract fact candidates from interview state.

    Returns a list of dicts with keys:
      fact_key, fact_value, confidence, source, meta

    The caller (extract_and_store) is responsible for redaction + persistence.
    """
    facts: list[dict[str, Any]] = []

    position = state.get("position") or _from_plan(state, "target_position")
    company = state.get("company") or _from_plan(state, "target_company")

    if position:
        facts.append({
            "fact_key": "target_position",
            "fact_value": str(position),
            "confidence": _CONFIDENCE["target_position"],
            "source": "user_asserted",
            "meta": {"extracted_from": "interview_session"},
        })
    if company:
        facts.append({
            "fact_key": "target_company",
            "fact_value": str(company),
            "confidence": _CONFIDENCE["target_company"],
            "source": "user_asserted",
            "meta": {"extracted_from": "interview_session"},
        })

    # Identified weakness — single worst-scoring dimension below the
    # weakness threshold. Using ONE fact_key="identified_weakness" means
    # latest-wins supersession across interviews reflects "the user's
    # most recent worst weakness". If we stored per-dimension weaknesses
    # as separate fact_keys, the planner would see a growing list and
    # latest-wins wouldn't apply cleanly.
    report = state.get("interview_report") or {}
    dim_scores = report.get("dimension_scores") or {}
    if isinstance(dim_scores, dict) and dim_scores:
        # Pre-filter to numeric scores — non-numeric values cannot be ranked.
        numeric_dims: list[tuple[str, float]] = []
        for dim_key, score in dim_scores.items():
            try:
                numeric_dims.append((str(dim_key), float(score)))
            except (TypeError, ValueError):
                continue
        # Sort ascending — lowest scores first.
        numeric_dims.sort(key=lambda kv: kv[1])
        for dim_key, score_f in numeric_dims:
            # Only flag as weakness if score < 7.0 (out of 10).
            if score_f >= 7.0:
                continue
            label = _DIM_LABELS.get(dim_key, dim_key)
            facts.append({
                "fact_key": "identified_weakness",
                "fact_value": f"{label} ({dim_key}, 得分 {score_f:.1f})",
                "confidence": _CONFIDENCE["identified_weakness"],
                "source": "extracted_from_llm_output",
                "meta": {
                    "extracted_from": "interview_report",
                    "dimension": dim_key,
                    "score": score_f,
                },
            })
            # Only one weakness per interview — break after the first
            # sub-threshold dimension (the worst one).
            break

    # Stated preferences — focus areas with weight ≥0.4 indicate user
    # cares about that area (proxy for preference).
    plan = state.get("interview_plan") or {}
    focus_areas = plan.get("focus_areas") or []
    if isinstance(focus_areas, list):
        for fa in focus_areas:
            if not isinstance(fa, dict):
                continue
            weight = fa.get("weight")
            try:
                w = float(weight) if weight is not None else 0.0
            except (TypeError, ValueError):
                continue
            if w >= 0.4:
                area = str(fa.get("area") or "").strip()
                if area:
                    facts.append({
                        "fact_key": "stated_preference",
                        "fact_value": f"重点关注方向: {area}",
                        "confidence": _CONFIDENCE["stated_preference"],
                        "source": "system_inferred",
                        "meta": {
                            "extracted_from": "interview_plan",
                            "weight": w,
                        },
                    })

    return facts


def _from_plan(state: dict[str, Any], key: str) -> str | None:
    plan = state.get("interview_plan") or {}
    val = plan.get(key)
    if val:
        return str(val)
    return None


async def extract_and_store(
    *,
    user_id: UUID,
    session_id: UUID,
    state: dict[str, Any],
    repo: AgentMemoryRepository,
) -> dict[str, Any]:
    """Extract facts from `state` and persist via `repo`.

    Applies PII redaction (FR-009). Blocked facts are dropped with a
    warning log. Returns a summary dict for observability.

    This function is safe to call from an ARQ task — it does NOT commit
    the session (caller's transaction boundary). The ARQ task wrapper
    opens its own session via `get_session_context()`.
    """
    facts = extract_facts(state)
    stored: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for fact in facts:
        redacted, was_blocked = redact(fact["fact_value"])
        if was_blocked:
            logger.warning(
                "memory.extract.blocked_pii",
                user_id=str(user_id),
                fact_key=fact["fact_key"],
            )
            blocked.append({"fact_key": fact["fact_key"], "reason": "pii_heavy"})
            continue

        # Inject session_id into meta for traceability.
        meta = fact.get("meta") or {}
        meta["session_id"] = str(session_id)

        row = await repo.upsert_semantic_memory(
            user_id=user_id,
            fact_key=fact["fact_key"],
            fact_value=redacted,
            confidence=fact["confidence"],
            source=fact["source"],
            schema_version=1,
            meta=meta,
        )
        stored.append({
            "fact_key": row.fact_key,
            "fact_value": row.fact_value,
            "version": row.version,
            "status": row.status,
        })

    logger.info(
        "memory.extract.complete",
        user_id=str(user_id),
        session_id=str(session_id),
        facts_extracted=len(facts),
        facts_stored=len(stored),
        facts_blocked=len(blocked),
    )
    return {
        "extracted": len(facts),
        "stored": len(stored),
        "blocked": len(blocked),
        "details": stored,
    }


__all__ = ["extract_and_store", "extract_facts"]
