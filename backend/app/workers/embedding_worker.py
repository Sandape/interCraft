"""arq worker task: compute embedding for an error_question row (REQ-048 T006).

Registered into ``app.workers.main.WorkerSettings.functions`` by
``T-NEW-1`` (Phase 4 / US2) so the task is picked up by the arq worker
process.

The body delegates to ``app.services.embedding.client.EmbeddingServiceClient``
which calls the embedding service's ``POST /embed`` endpoint. Retries
(default 3) are handled by arq itself via the ``retry`` setting on the
function decorator (added in T-NEW-1 wiring).
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


async def compute_embedding_task(ctx, error_question_id: str) -> dict:
    """Compute embedding for one error_question row and persist it.

    Phase 4 body fills in: call EmbeddingServiceClient.embed + UPDATE row.
    Currently logs and no-ops so the function can be registered without
    surfacing a hard import error in Phase 1 / Phase 2 dev.

    Parameters
    ----------
    ctx:
        arq job context (unused in skeleton).
    error_question_id:
        UUID of the error_questions row to embed.
    """
    logger.info(
        "embedding.compute.skeleton",
        error_question_id=error_question_id,
        note="T006 skeleton — Phase 4 US2 fills body",
    )
    return {"status": "skeleton", "error_question_id": error_question_id}


__all__ = ["compute_embedding_task"]