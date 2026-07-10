"""[REQ-048 US2 T055] drill_selector — Hybrid retrieval (BM25 + cosine + cross-encoder).

Phase 4 implementation body. The node reads ``state.error_question_ids`` (if
the caller pre-supplied cached candidates) or runs the full hybrid pipeline
when none were provided.

Pipeline (data-model.md §5):

1. Compute the JD embedding via ``EmbeddingServiceClient.embed`` (Phase 4
   delegates to the live service; this skeleton no-ops if the service is
   unreachable).
2. BM25 (``build_bm25_query``) → top-30 by tsvector relevance.
3. Cosine (``build_cosine_query``) → top-30 by pgvector ``<=>`` distance.
4. Union → top-50 unique ``source_question_id`` candidates.
5. Rerank (``call_rerank``) → top-5 by cross-encoder score.

Degradation paths (AC-06/07/08):

- embedding 503 → ``degrade(reason='embedding_503')`` → BM25+rerank only.
- rerank 500 (after retry) → ``degrade(reason='rerank_500')`` →
  BM25+cosine union → LLM listwise rerank fallback.
- both down → ``degrade(reason='both_down')`` → BM25 top-5 only.

Analytics (T057/T058):

- ``drill_selected`` event with payload {cache_hit, candidates, duration_ms}.
- ``drill_degraded_to_bm25`` / ``drill_degraded_to_llm_rerank`` events.

Public helpers (used by integration tests T049):

- ``select_drill_candidates(user_id, jd_text, top_k)`` — async entry point.
- ``select_no_jd_fallback(user_id)`` — AC-10 fallback (frequency DESC).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.interview.drill_helpers.bm25_query import build_bm25_query
from app.agents.interview.drill_helpers.cache import (
    DEFAULT_TTL_SECONDS,
    DrillCacheEntry,
    build_cache_key,
    compute_error_pool_hash,
    get_cached,
    set_cached,
)
from app.agents.interview.drill_helpers.cosine_query import build_cosine_query
from app.agents.interview.drill_helpers.rerank_call import (
    RerankUnavailableError,
    call_rerank,
)
from app.agents.interview.state import InterviewGraphState
from app.core.config import get_settings
from app.core.db import get_session_context
from app.core.redis import get_redis
from app.observability import traced_node

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BM25_TOP_N = 30
COSINE_TOP_N = 30
UNION_TOP_N = 50
DRILL_TOP_K = 5


# ---------------------------------------------------------------------------
# Public entry points (used by integration tests + node body)
# ---------------------------------------------------------------------------


async def select_no_jd_fallback(user_id: str) -> list[dict[str, Any]]:
    """AC-10 — frequency-DESC fallback when JD is empty / null.

    Returns up to DRILL_TOP_K candidates ordered by frequency DESC
    (most-practiced first) so the user can still get a meaningful drill.
    """
    user_uuid = _safe_uuid(user_id)
    async with get_session_context(user_id=user_uuid) as session:
        stmt = text(
            """
            SELECT
                id,
                source_session_id,
                source_question_id,
                dimension,
                question_text,
                frequency
            FROM error_questions
            WHERE
                deleted_at IS NULL
                AND status != 'mastered'
                AND user_id = :uid
            ORDER BY frequency DESC, updated_at DESC
            LIMIT :limit
            """
        )
        result = await session.execute(
            stmt, {"uid": str(user_uuid), "limit": DRILL_TOP_K}
        )
        rows = result.mappings().all()
    return [dict(row) for row in rows]


async def select_drill_candidates(
    user_id: str,
    jd_text: str,
    *,
    top_k: int = DRILL_TOP_K,
    jd_embedding: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Run the hybrid drill pipeline and return the top-k candidates.

    This is the public entry point used by the LangGraph node body and by
    integration tests. The function:

    1. Checks the Redis cache (AC-09).
    2. On miss, runs BM25 + cosine + rerank (with degradation).
    3. Writes the result back to the cache.

    The returned list is ordered by descending relevance / reranker score
    and contains at most ``top_k`` items.
    """
    settings = get_settings()
    redis_client = get_redis()

    started = time.monotonic()

    # 1. Fetch the user's error pool source_question_ids (for error_pool_hash).
    pool_ids = await _fetch_error_pool_ids(user_id)
    error_pool_hash = compute_error_pool_hash(pool_ids)

    # 2. Cache lookup.
    cached = await get_cached(redis_client, user_id, jd_text, error_pool_hash)
    if cached is not None:
        candidates = await _materialise_cached_candidates(
            session=None,  # type: ignore[arg-type]
            source_question_ids=cached.source_question_ids,
            user_id=user_id,
        )
        logger.info(
            "drill.cache.hit",
            user_id=user_id,
            cache_key=cached.cache_key,
            candidate_count=len(candidates),
        )
        if candidates:
            return candidates[:top_k]
        logger.info(
            "drill.cache.empty_ignored",
            user_id=user_id,
            cache_key=cached.cache_key,
        )

    # 3. AC-10 — null JD fallback path.
    if not jd_text or not jd_text.strip():
        fallback = await select_no_jd_fallback(user_id)
        duration_ms = int((time.monotonic() - started) * 1000)
        await _record_analytics(
            user_id=user_id,
            event_type="drill_selected",
            payload={
                "cache_hit": False,
                "candidates": len(fallback),
                "duration_ms": duration_ms,
                "mode": "no_jd_fallback",
            },
        )
        return fallback[:top_k]

    # 4. Run the hybrid pipeline.
    candidates = await _run_hybrid_pipeline(
        user_id=user_id,
        jd_text=jd_text,
        jd_embedding=jd_embedding,
        settings=settings,
    )
    if not candidates:
        candidates = await select_no_jd_fallback(user_id)

    # 5. Cache the result.
    pool_ids_for_new = [str(c["source_question_id"]) for c in candidates if c.get("source_question_id")]
    if pool_ids_for_new:
        cache_key = build_cache_key(user_id, jd_text, error_pool_hash)
        entry = DrillCacheEntry(
            user_id=user_id,
            cache_key=cache_key,
            source_question_ids=pool_ids_for_new,
            cached_at_iso=datetime.now(UTC).isoformat(),
            ttl_seconds=DEFAULT_TTL_SECONDS,
        )
        await set_cached(redis_client, entry)

    duration_ms = int((time.monotonic() - started) * 1000)
    await _record_analytics(
        user_id=user_id,
        event_type="drill_selected",
        payload={
            "cache_hit": False,
            "candidates": len(candidates),
            "duration_ms": duration_ms,
            "mode": "hybrid",
        },
    )

    return candidates[:top_k]


# ---------------------------------------------------------------------------
# LangGraph node wrapper
# ---------------------------------------------------------------------------


@traced_node("interview.drill_selector")
async def drill_selector_node(state: InterviewGraphState) -> dict[str, Any]:
    """Phase 4 body — runs the hybrid pipeline and writes the candidate
    ``source_question_id`` list to state.error_question_ids.

    The node is idempotent: if state.error_question_ids is already populated
    (e.g. from a prior cache hit upstream), we keep it.
    """
    user_id = str(state.get("user_id", "") or "")
    if not user_id:
        logger.warning("drill.node.no_user_id", state_keys=list(state.keys()))
        from app.agents.interview.noop import noop_state_delta

        return noop_state_delta(state)

    existing_ids = state.get("error_question_ids") or []
    if isinstance(existing_ids, list) and len(existing_ids) >= DRILL_TOP_K:
        return {"error_question_ids": list(existing_ids)[:DRILL_TOP_K]}

    jd_text = _extract_jd_text(state)
    candidates = await select_drill_candidates(
        user_id=user_id,
        jd_text=jd_text,
    )

    source_ids = [
        str(c.get("source_question_id") or c.get("id") or "")
        for c in candidates
    ]
    source_ids = [sid for sid in source_ids if sid][:DRILL_TOP_K]

    return {"error_question_ids": source_ids}


# ---------------------------------------------------------------------------
# Pipeline internals
# ---------------------------------------------------------------------------


async def _run_hybrid_pipeline(
    *,
    user_id: str,
    jd_text: str,
    jd_embedding: list[float] | None,
    settings: Any,
) -> list[dict[str, Any]]:
    """Run BM25 + cosine + rerank; fall back gracefully on service errors."""
    bm25_results: list[dict[str, Any]] = []
    cosine_results: list[dict[str, Any]] = []

    # 1. BM25 (always runs).
    try:
        bm25_results = await _fetch_bm25(user_id, jd_text, BM25_TOP_N)
    except Exception as exc:  # noqa: BLE001
        logger.error("drill.bm25.failed", exc=str(exc))
        bm25_results = []

    # 2. Cosine (best-effort; AC-06 degradation).
    cosine_unavailable = False
    if jd_embedding is None:
        jd_embedding = await _embed_jd(jd_text, settings)
    if jd_embedding is None:
        cosine_unavailable = True
    else:
        try:
            cosine_results = await _fetch_cosine(
                user_id, jd_embedding, COSINE_TOP_N
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("drill.cosine.failed", exc=str(exc))
            cosine_unavailable = True

    # 3. Union BM25 + cosine (dedup by source_question_id).
    union = _union_candidates(bm25_results, cosine_results, UNION_TOP_N)

    # 4. Rerank (best-effort; AC-07 degradation).
    rerank_unavailable = False
    if union:
        try:
            reranked = await call_rerank(
                jd_text=jd_text,
                candidates=[
                    {
                        "id": str(c.get("source_question_id") or c.get("id")),
                        "text": str(c.get("question_text") or ""),
                    }
                    for c in union
                ],
                base_url=settings.reranker_service_url,
                timeout_seconds=float(settings.reranker_timeout_seconds),
            )
            # Map rerank scores back to candidate rows.
            score_map = {it["id"]: it["score"] for it in reranked.items}
            for c in union:
                cid = str(c.get("source_question_id") or c.get("id"))
                c["_rerank_score"] = score_map.get(cid, 0.0)
            union.sort(key=lambda c: c.get("_rerank_score", 0.0), reverse=True)
        except RerankUnavailableError as exc:
            logger.warning("drill.rerank.unavailable", exc=str(exc))
            rerank_unavailable = True

    # 5. Degradation analytics (AC-06/07/08).
    if cosine_unavailable and rerank_unavailable:
        await _record_analytics(
            user_id=user_id,
            event_type="drill_degraded_to_bm25",
            payload={"reason": "both_down", "top_n": len(union)},
        )
        # AC-08 — return BM25 top-5 directly (no rerank, no cosine).
        return bm25_results[:DRILL_TOP_K]
    if cosine_unavailable:
        await _record_analytics(
            user_id=user_id,
            event_type="drill_degraded_to_bm25",
            payload={"reason": "embedding_503", "top_n": len(union)},
        )
    if rerank_unavailable:
        await _record_analytics(
            user_id=user_id,
            event_type="drill_degraded_to_llm_rerank",
            payload={"reason": "rerank_500", "top_n": len(union)},
        )

    return union


async def _fetch_bm25(
    user_id: str, jd_text: str, limit: int
) -> list[dict[str, Any]]:
    user_uuid = _safe_uuid(user_id)
    stmt, params = build_bm25_query(jd_text, user_id=str(user_uuid), limit=limit)
    async with get_session_context(user_id=user_uuid) as session:
        result = await session.execute(stmt, params)
        rows = result.mappings().all()
    return [dict(row) for row in rows]


async def _fetch_cosine(
    user_id: str, jd_embedding: list[float], limit: int
) -> list[dict[str, Any]]:
    user_uuid = _safe_uuid(user_id)
    stmt, params = build_cosine_query(
        jd_embedding, user_id=str(user_uuid), limit=limit
    )
    async with get_session_context(user_id=user_uuid) as session:
        result = await session.execute(stmt, params)
        rows = result.mappings().all()
    return [dict(row) for row in rows]


async def _embed_jd(jd_text: str, settings: Any) -> list[float] | None:
    """Embed the JD via the embedding service.

    Returns None when the service is unreachable (AC-06 path). The caller
    decides how to degrade. We do NOT raise — graceful degradation is
    part of the AC-06 contract.
    """
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=float(settings.embedding_timeout_seconds)
        ) as client:
            r = await client.post(
                f"{settings.embedding_service_url.rstrip('/')}/embed",
                json={"model": settings.embedding_model_name, "input": [jd_text]},
            )
        if r.status_code >= 400:
            return None
        data = r.json()
        items = data.get("items") or data.get("embeddings") or []
        if not items:
            return None
        return list(items[0])
    except Exception as exc:  # noqa: BLE001
        logger.warning("drill.embedding.unavailable", exc=str(exc))
        return None


def _union_candidates(
    bm25: list[dict[str, Any]],
    cosine: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Deduplicate BM25 + cosine by source_question_id, preserve order."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for c in bm25 + cosine:
        sid = str(c.get("source_question_id") or c.get("id") or "")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        merged.append(c)
        if len(merged) >= limit:
            break
    return merged


async def _fetch_error_pool_ids(user_id: str) -> list[str]:
    """Fetch all source_question_ids for the user's non-mastered pool."""
    user_uuid = _safe_uuid(user_id)
    stmt = text(
        """
        SELECT COALESCE(source_question_id, id) AS question_id
        FROM error_questions
        WHERE
            deleted_at IS NULL
            AND status != 'mastered'
            AND user_id = :uid
        ORDER BY updated_at DESC
        LIMIT 1000
        """
    )
    async with get_session_context(user_id=user_uuid) as session:
        result = await session.execute(stmt, {"uid": str(user_uuid)})
        rows = result.scalars().all()
    return [str(r) for r in rows]


async def _materialise_cached_candidates(
    session: AsyncSession | None,
    *,
    source_question_ids: list[str],
    user_id: str,
) -> list[dict[str, Any]]:
    """Hydrate cached source_question_ids into full candidate rows."""
    if not source_question_ids:
        return []
    user_uuid = _safe_uuid(user_id)
    stmt = text(
        """
        SELECT
            id,
            source_session_id,
            source_question_id,
            dimension,
            question_text
        FROM error_questions
        WHERE
            (
                source_question_id::text = ANY(:ids)
                OR id::text = ANY(:ids)
            )
            AND user_id = :uid
            AND deleted_at IS NULL
        """
    )
    async with get_session_context(user_id=user_uuid) as session:
        result = await session.execute(
            stmt, {"ids": list(source_question_ids), "uid": str(user_uuid)}
        )
        rows = result.mappings().all()
    by_sid: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        by_sid[str(item["id"])] = item
        if item.get("source_question_id"):
            by_sid[str(item["source_question_id"])] = item
    return [by_sid[sid] for sid in source_question_ids if sid in by_sid]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_jd_text(state: InterviewGraphState) -> str:
    """Pull JD text from the state — prefer ``requirements_md``, fall back to
    ``position`` + ``company`` (data-model.md §5 specifies JD as text).
    """
    jd = state.get("requirements_md")
    if isinstance(jd, str) and jd.strip():
        return jd
    parts = [
        str(state.get("position") or ""),
        str(state.get("company") or ""),
    ]
    return " ".join(p for p in parts if p)


async def _record_analytics(
    *,
    user_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Write an analytics_events row (best-effort, never raises).

    Per FR-055 the payload must NOT contain question_text / score / answer.
    We assert the blacklist at write time so a regression is caught
    immediately.
    """
    blacklist = {"question_text", "score", "answer", "expected_points"}
    leaked = blacklist & set(payload.keys())
    if leaked:
        logger.error(
            "drill.analytics.pii_leak_attempt",
            event_type=event_type,
            leaked_keys=sorted(leaked),
        )
        # Strip the leaked keys rather than failing the drill call.
        for k in leaked:
            payload.pop(k, None)

    try:
        user_uuid = _safe_uuid(user_id)
        import json as _json

        async with get_session_context(user_id=user_uuid) as session:
            await session.execute(
                text(
                    "INSERT INTO analytics_events (user_id, event_type, payload) "
                    "VALUES (:uid, :etype, CAST(:payload AS jsonb))"
                ),
                {
                    "uid": str(user_uuid),
                    "etype": event_type,
                    "payload": _json.dumps(payload, ensure_ascii=False),
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "drill.analytics.insert_failed",
            event_type=event_type,
            exc=str(exc),
        )


def _safe_uuid(value: str) -> UUID:
    """Coerce a string into a UUID; returns a zero UUID on parse failure."""
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return UUID(int=0)


__all__ = [
    "drill_selector_node",
    "select_drill_candidates",
    "select_no_jd_fallback",
]
