"""bge-small-zh-v1.5 embedder wrapper (REQ-048 T013 — skeleton).

Phase 4 / US2 implementation will load FlagEmbedding BGEM3FlagModel (or
sentence-transformers) and expose ``encode(texts: list[str]) -> list[list[float]]``.
Skeleton keeps the import surface stable so callers can reference it.
"""
from __future__ import annotations


class BGESmallEmbedder:
    """Thin wrapper around the bge-small-zh-v1.5 model."""

    def __init__(self, model_name: str = "bge-small-zh-v1.5") -> None:
        self.model_name = model_name
        self.dim = 512  # bge-small-zh-v1.5 outputs 512-dim vectors

    async def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts to 512-dim embeddings (Phase 4 body)."""
        raise NotImplementedError("T013 body — fill in during Phase 4")


__all__ = ["BGESmallEmbedder"]