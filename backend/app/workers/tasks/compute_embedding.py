"""[REQ-048 T-NEW-1] arq task: compute embedding for an error_question row.

Registered into ``app.workers.main.WorkerSettings.functions`` so the task
is picked up by the arq worker process. The body delegates to
``EmbeddingServiceClient.embed`` (T015) which calls the embedding
service's ``POST /embed`` endpoint.

Retries: handled by arq's ``max_tries=3`` setting on WorkerSettings.

AC coverage:
- AC-11b: arq worker race + cold start (warm-up 30s)
- AC-11c: cold/warm SLO separation (60s cold / 30s warm)

Behaviour
---------
- On success: writes embedding + embedding_computed_at + embedding_model
  to ``error_questions`` row.
- On failure: arq retries with exponential backoff; the row is left with
  ``embedding IS NULL`` so it can be re-enqueued via T-NEW-2 backfill.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import _session_cm
from app.services.embedding.client import EmbeddingServiceClient

logger = logging.getLogger(__name__)


async def compute_embedding_task(ctx: dict[str, Any], error_question_id: str) -> dict:
    """Compute embedding for one error_question row.

    Parameters
    ----------
    ctx:
        arq job context (unused directly — request_id is bound via
        ``on_job_start`` in ``app.workers.main``).
    error_question_id:
        UUID of the ``error_questions`` row to embed.

    Returns
    -------
    dict
        ``{"status": "ok" | "skipped", "error_question_id": str, "duration_ms": int}``
    """
    import time as _time

    started = _time.monotonic()
    settings = get_settings()
    client = EmbeddingServiceClient(
        base_url=settings.embedding_service_url,
        embed_timeout=float(settings.embedding_timeout_seconds),
    )

    # 1. Fetch the question_text for the row.
    try:
        row_uuid = UUID(str(error_question_id))
    except (ValueError, TypeError):
        logger.warning("embedding.compute.invalid_id", id=error_question_id)
        return {"status": "skipped", "error_question_id": str(error_question_id), "duration_ms": 0}

    async with _session_cm() as session:
        result = await session.execute(
            text(
                "SELECT question_text FROM error_questions WHERE id = :id"
            ),
            {"id": str(row_uuid)},
        )
        row = result.first()
    if row is None:
        logger.warning("embedding.compute.no_row", id=str(row_uuid))
        return {"status": "skipped", "error_question_id": str(row_uuid), "duration_ms": 0}

    question_text = row[0] if row else ""
    if not question_text:
        logger.info("embedding.compute.empty_text", id=str(row_uuid))
        return {"status": "skipped", "error_question_id": str(row_uuid), "duration_ms": 0}

    # 2. Call the embedding service.
    try:
        embeddings = await client.embed(
            [question_text],
            model=settings.embedding_model_name,
        )
    except (httpx.HTTPError, NotImplementedError) as exc:
        # T015 client may raise NotImplementedError if the body wasn't filled
        # in yet. We log + return so arq can retry per max_tries.
        logger.warning(
            "embedding.compute.service_unavailable",
            id=str(row_uuid),
            exc=str(exc),
        )
        raise

    if not embeddings:
        logger.warning("embedding.compute.empty_response", id=str(row_uuid))
        return {"status": "skipped", "error_question_id": str(row_uuid), "duration_ms": 0}

    embedding_vector = list(embeddings[0])

    # 3. Persist back to the row.
    async with _session_cm() as session:
        await session.execute(
            text(
                """
                UPDATE error_questions
                SET embedding = CAST(:emb AS vector),
                    embedding_computed_at = :now,
                    embedding_model = :model
                WHERE id = :id
                """
            ),
            {
                "id": str(row_uuid),
                "emb": "[" + ",".join(f"{float(v):.6f}" for v in embedding_vector) + "]",
                "now": datetime.now(UTC),
                "model": settings.embedding_model_name,
            },
        )
        await session.commit()

    duration_ms = int((_time.monotonic() - started) * 1000)
    logger.info(
        "embedding.compute.ok",
        id=str(row_uuid),
        model=settings.embedding_model_name,
        dim=len(embedding_vector),
        duration_ms=duration_ms,
    )
    return {
        "status": "ok",
        "error_question_id": str(row_uuid),
        "duration_ms": duration_ms,
    }


__all__ = ["compute_embedding_task"]