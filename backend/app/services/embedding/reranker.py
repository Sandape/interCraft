"""bge-reranker-v2-m3 cross-encoder wrapper (REQ-048 T014 — skeleton)."""
from __future__ import annotations


class BGERerankerV2M3:
    """Thin wrapper around the bge-reranker-v2-m3 cross-encoder."""

    def __init__(self, model_name: str = "bge-reranker-v2-m3") -> None:
        self.model_name = model_name

    async def rerank(self, query: str, documents: list[dict]) -> list[dict]:
        """Return ranked ``[{"id": ..., "score": ...}, ...]`` (Phase 4 body)."""
        raise NotImplementedError("T014 body — fill in during Phase 4")


__all__ = ["BGERerankerV2M3"]