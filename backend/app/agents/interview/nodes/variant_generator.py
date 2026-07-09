"""[REQ-048 US5 T099] variant_generator node — LLM-based variant generation.

When ``state.use_variants == True`` the node calls the LLM once per source
question and replaces the question_text while preserving ``dimension`` +
``expected_points``. On LLM failure, the node falls back to the original
question_text and emits a ``variant_generation_failed`` analytics event.

The LLM client is injected via ``state['_llm_client']`` for unit tests;
in production the node uses the module-level ``LLMClient`` singleton.

AC-25 contract (R22): when ``use_variants`` is False (or absent), the
node is a no-op and the original ``state.questions`` are preserved by
the caller. The default-false behaviour is enforced at the upstream
state initialization layer (see graph.py + state.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.agents.interview.state import InterviewGraphState
from app.core.db import get_session_context
from app.observability import traced_node

logger = logging.getLogger(__name__)


VARIANT_PROMPT_ZHCN = (
    "请基于以下错题，生成一个不同问法但考点相同的题目。\n"
    "原题：{question_text}\n"
    "考察维度：{dimension}\n"
    "要点：{expected_points}\n\n"
    "要求：\n"
    "1. 新题目必须用中文（zh-CN），不要出现英文。\n"
    "2. 新题目考点与原题相同。\n"
    "3. 输出必须是 JSON 格式：{{\"new_question_text\": \"<新题目>\"}}\n"
)


def _strip_json_envelope(raw: str) -> str:
    """Strip code fences / extra whitespace from LLM JSON output."""
    raw = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(\{.*?\})\s*```$", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    return raw.strip()


async def _generate_one_variant(
    *,
    source_text: str,
    dimension: str,
    expected_points: list[str],
    llm_client: Any,
) -> str:
    """Call the LLM to generate a single variant. Returns the new question_text.

    Raises on LLM failure so the caller can apply the fallback path.
    """
    prompt = VARIANT_PROMPT_ZHCN.format(
        question_text=source_text,
        dimension=dimension,
        expected_points=" / ".join(expected_points),
    )
    # LLMClient interface (production + MockLLMClient share this method).
    if hasattr(llm_client, "complete_async"):
        response = await llm_client.complete_async(prompt=prompt, json_mode=True)
    else:
        # Backward-compat: sync complete() or raise.
        response = llm_client.complete(prompt=prompt, json_mode=True)
    raw = _strip_json_envelope(str(response))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Best-effort: take the raw text as the new question.
        return raw
    return str(data.get("new_question_text") or raw)


async def _write_analytics(
    *,
    user_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Best-effort analytics_events INSERT (never raises)."""
    blacklist = {"question_text", "score", "answer", "expected_points"}
    leaked = blacklist & set(payload.keys())
    if leaked:
        for k in leaked:
            payload.pop(k, None)
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        return
    try:
        async with get_session_context(user_id=user_uuid) as session:
            await session.execute(
                text(
                    "INSERT INTO analytics_events (user_id, event_type, payload) "
                    "VALUES (:uid, :etype, CAST(:payload AS jsonb))"
                ),
                {
                    "uid": str(user_uuid),
                    "etype": event_type,
                    "payload": json.dumps(payload, ensure_ascii=False),
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "variant_generator.analytics.insert_failed",
            event_type=event_type,
            exc=str(exc),
        )


@traced_node("interview.variant_generator")
async def variant_generator_node(state: InterviewGraphState) -> dict[str, Any]:
    """Generate variants for each error_question_id in state.

    AC-25 contract:
    - use_variants=False (default) → no-op (returns {}).
    - use_variants=True → for each candidate, call LLM once; on failure,
      keep the original question_text and emit ``variant_generation_failed``.

    Returns a state delta with the rewritten questions list. The caller
    (drill_selector / question_gen) is responsible for merging back.
    """
    use_variants = bool(state.get("use_variants", False))
    if not use_variants:
        return {}

    error_question_ids = state.get("error_question_ids") or []
    if not error_question_ids:
        return {}

    user_id = str(state.get("user_id", "") or "")
    if not user_id:
        logger.warning("variant_generator.no_user_id", state_keys=list(state.keys()))
        return {}

    # 1. Hydrate the source questions from the DB.
    async with get_session_context(user_id=UUID(user_id)) as session:
        stmt = text(
            """
            SELECT source_question_id, dimension, question_text
            FROM error_questions
            WHERE
                source_question_id = ANY(:ids)
                AND user_id = :uid
                AND deleted_at IS NULL
            """
        )
        result = await session.execute(
            stmt, {"ids": list(error_question_ids), "uid": str(UUID(user_id))}
        )
        rows = result.mappings().all()
    by_sid = {str(r["source_question_id"]): dict(r) for r in rows}
    if not by_sid:
        return {}

    # 2. Resolve LLM client (injected for tests; module default otherwise).
    llm_client = state.get("_llm_client")
    if llm_client is None:
        try:
            from app.agents.llm_client import LLMClient

            llm_client = LLMClient()
        except Exception as exc:  # noqa: BLE001
            logger.warning("variant_generator.no_llm_client", exc=str(exc))
            return {}

    # 3. Generate variants in parallel (one LLM call per source question).
    variant_results = await asyncio.gather(
        *(
            _generate_one_variant(
                source_text=by_sid[sid]["question_text"],
                dimension=by_sid[sid].get("dimension") or "tech_depth",
                expected_points=[],
                llm_client=llm_client,
            )
            for sid in error_question_ids
            if sid in by_sid
        ),
        return_exceptions=True,
    )

    # 4. Apply results: successful variants replace question_text; failures
    #    fall back to original + emit analytics event.
    new_questions = []
    success_count = 0
    for sid, result in zip(error_question_ids, variant_results):
        if sid not in by_sid:
            continue
        original = dict(by_sid[sid])
        if isinstance(result, Exception):
            await _write_analytics(
                user_id=user_id,
                event_type="variant_generation_failed",
                payload={
                    "source_question_id": sid,
                    "reason": type(result).__name__,
                    "fallback": "original_question_text",
                },
            )
            new_questions.append(original)
            continue

        new_text = str(result).strip()
        if not new_text or new_text == original["question_text"]:
            # LLM returned no change → treat as soft success (no event).
            new_questions.append(original)
            continue

        original["question_text"] = new_text
        new_questions.append(original)
        success_count += 1

    if success_count:
        await _write_analytics(
            user_id=user_id,
            event_type="variant_mode_enabled",
            payload={
                "variant_count": success_count,
                "total_candidates": len(new_questions),
            },
        )

    return {"questions": new_questions}


__all__ = ["variant_generator_node"]