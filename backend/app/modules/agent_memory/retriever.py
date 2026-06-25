"""Memory retriever — fetches active semantic memories for an agent call.

Spec FR-010: "Each of the 5 graphs MUST be able to retrieve relevant
memories (by user id + query) before invoking the LLM, and inject them
into the prompt context."

Spec FR-011: "Memory retrieval MUST be relevance-ranked (semantic
similarity) and capped at a configurable token budget per call."

Spec FR-013: "Memory retrieval failure (e.g., vector store down) MUST
degrade gracefully — the agent proceeds without memory and no
user-facing error is raised."

US1 scope:
  - Relevance ranking: created_at DESC (newest first). Embedding-based
    ranking is ⏳ (US2/US3).
  - Token budget: rough estimate at 4 chars/token (English+Chinese
    mixed — conservative). Caller can override.
  - Graceful degrade: ALL exceptions are caught, logged, and an empty
    MemoryRetrieveOut is returned. The MemoryRetrievalLog row is still
    written when possible (so observability shows the failure).
"""
from __future__ import annotations

import time
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent_memory.repository import AgentMemoryRepository
from app.modules.agent_memory.schemas import (
    MemoryRetrieveOut,
    SemanticMemoryOut,
)

logger = structlog.get_logger(__name__)

# Rough chars-per-token estimate. DeepSeek V4 tokenizer averages ~3.5
# chars/token for Chinese + ~4 chars/token for English. Use 4 to be
# conservative (over-estimate budget usage → fewer memories injected).
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Rough token estimate. US1 scope — no tokenizer dependency."""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _format_memory_for_budget(mem: SemanticMemoryOut) -> str:
    """The text used to estimate token cost of injecting this memory.

    Matches the format used by planner_generate's `_format_memory_section`
    so the budget estimate is realistic.
    """
    return f"- {mem.fact_key}: {mem.fact_value} (置信度 {mem.confidence:.2f}, 来源 {mem.source})"


async def retrieve_active_memories(
    *,
    user_id: UUID,
    graph: str,
    node: str,
    session: AsyncSession,
    query: str | None = None,
    token_budget: int = 500,
) -> MemoryRetrieveOut:
    """Retrieve active semantic memories for a user, capped by token budget.

    Always returns a `MemoryRetrieveOut` — never raises. On any error,
    logs `memory.retrieve.failed` and returns an empty result with
    `degraded=True`.

    The caller is responsible for setting `app.user_id` via RLS context
    before invoking this function (the planner_context_node does this
    via `SET LOCAL`).
    """
    started = time.monotonic()
    repo = AgentMemoryRepository(session)

    try:
        memories = await repo.list_active_memories(user_id, limit=50)
    except Exception:
        latency = int((time.monotonic() - started) * 1000)
        logger.warning(
            "memory.retrieve.failed",
            user_id=str(user_id),
            graph=graph,
            node=node,
            latency_ms=latency,
            exc_info=True,
        )
        # Best-effort log the failure. If even the log write fails, swallow.
        try:
            await repo.log_retrieval(
                user_id=user_id,
                graph=graph,
                node=node,
                query=query,
                retrieved_memory_ids=[],
                token_budget_used=0,
                retrieval_latency_ms=latency,
            )
            await session.commit()
        except Exception:
            logger.warning("memory.retrieve.log_failed", exc_info=True)
        return MemoryRetrieveOut(
            memories=[],
            token_budget_used=0,
            retrieval_latency_ms=latency,
            degraded=True,
        )

    # Rank + cap by token budget.
    selected: list[SemanticMemoryOut] = []
    used = 0
    for mem in memories:
        out = SemanticMemoryOut.model_validate(mem)
        cost = _estimate_tokens(_format_memory_for_budget(out))
        if used + cost > token_budget:
            # Drop lowest-relevance first when over budget (FR-011 edge case).
            # Since memories are already sorted by created_at DESC, the first
            # ones we drop are the oldest (lowest relevance in US1's exact-match
            # ranking). Just break — keep what fits.
            logger.info(
                "memory.retrieve.budget_exceeded",
                user_id=str(user_id),
                graph=graph,
                node=node,
                budget_tokens=token_budget,
                used_tokens=used,
                skipped_count=len(memories) - len(selected),
            )
            break
        selected.append(out)
        used += cost

    latency = int((time.monotonic() - started) * 1000)

    # Best-effort observability log. Failure here MUST NOT affect retrieval.
    try:
        await repo.log_retrieval(
            user_id=user_id,
            graph=graph,
            node=node,
            query=query,
            retrieved_memory_ids=[str(m.id) for m in selected],
            token_budget_used=used,
            retrieval_latency_ms=latency,
        )
        await session.commit()
    except Exception:
        logger.warning("memory.retrieve.log_failed", exc_info=True)

    logger.info(
        "memory.retrieve.complete",
        user_id=str(user_id),
        graph=graph,
        node=node,
        retrieved_count=len(selected),
        token_budget_used=used,
        latency_ms=latency,
    )

    return MemoryRetrieveOut(
        memories=selected,
        token_budget_used=used,
        retrieval_latency_ms=latency,
        degraded=False,
    )


__all__ = ["retrieve_active_memories"]
