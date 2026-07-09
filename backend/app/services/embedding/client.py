"""Async httpx client wrapping the embedding + rerank service (REQ-048 T015 — skeleton)."""
from __future__ import annotations

import httpx


class EmbeddingServiceClient:
    """HTTP client for the embedding + rerank service.

    Phase 4 / US2 implementation calls /embed and /rerank endpoints with
    timeouts driven by ``Settings.embedding_timeout_seconds`` /
    ``Settings.reranker_timeout_seconds``.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8765",
        embed_timeout: float = 10.0,
        rerank_timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.embed_timeout = embed_timeout
        self.rerank_timeout = rerank_timeout

    async def health(self) -> dict:
        """Probe /health; returns parsed JSON."""
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{self.base_url}/health")
            r.raise_for_status()
            return r.json()

    async def embed(self, texts: list[str], model: str = "bge-small-zh-v1.5") -> list[list[float]]:
        """POST /embed — Phase 4 body fills in."""
        raise NotImplementedError("T015 body — fill in during Phase 4")

    async def rerank(
        self, query: str, documents: list[dict], model: str = "bge-reranker-v2-m3"
    ) -> list[dict]:
        """POST /rerank — Phase 4 body fills in."""
        raise NotImplementedError("T015 body — fill in during Phase 4")


__all__ = ["EmbeddingServiceClient"]