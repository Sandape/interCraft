"""Embedding + Rerank HTTP server (REQ-048 T016).

Exposes ``POST /embed``, ``POST /rerank``, ``GET /health``. Lazily loads
the bge-small-zh-v1.5 embedder + bge-reranker-v2-m3 cross-encoder on the
first request to keep cold-start cheap. CPU-only inference per plan.md
R-1/R-2.

Routes:
- ``POST /embed`` — body ``{"texts": [...], "model": "bge-small-zh-v1.5"}`` →
  ``{"embeddings": [[...512 floats...]], "model": ..., "duration_ms": ...}``
- ``POST /rerank`` — body ``{"query": "...", "documents": [{"id": ..., "text": ...}]}`` →
  ``{"ranked": [{"id": ..., "score": ...}], "model": ..., "duration_ms": ...}``
- ``GET /health`` — ``{"status": "ok", "models_loaded": [...], "uptime_seconds": ...}``
"""
from __future__ import annotations

import time

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi import Request

router = APIRouter()

_start_time = time.time()
_loaded_models: list[str] = []
_cached_embedder = None
_cached_reranker = None


def _get_embedder():
    """Lazy-load BGEM3FlagModel on first call. CPU inference per plan.md R-1."""
    global _loaded_models, _cached_embedder
    if _cached_embedder is not None:
        return _cached_embedder
    try:
        from FlagEmbedding import BGEM3FlagModel
        _cached_embedder = BGEM3FlagModel("BAAI/bge-small-zh-v1.5", use_fp16=False)
        _loaded_models.append("bge-small-zh-v1.5")
        return _cached_embedder
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"embedder unavailable: {e}")


def _get_reranker():
    """Lazy-load FlagEmbedding reranker on first call."""
    global _loaded_models, _cached_reranker
    if _cached_reranker is not None:
        return _cached_reranker
    try:
        from FlagEmbedding import FlagReranker
        # local_files_only=True forces use of HF cache (no online HEAD requests)
        # per plan.md R-1 risk: dev environment may be offline.
        _cached_reranker = FlagReranker(
            "BAAI/bge-reranker-v2-m3",
            use_fp16=False,
            local_files_only=True,
        )
        _loaded_models.append("bge-reranker-v2-m3")
        return _cached_reranker
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"reranker unavailable: {e}")


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "models_loaded": list(_loaded_models),
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@router.post("/embed")
async def embed(request: Request) -> dict:
    body = await request.json()
    texts = body.get("texts") or []
    model_name = body.get("model", "bge-small-zh-v1.5")
    if not texts:
        raise HTTPException(status_code=422, detail="texts is required")
    t0 = time.time()
    try:
        model = _get_embedder()
        # BGEM3FlagModel.encode returns numpy array of shape (n, dim).
        embeddings = model.encode(texts).tolist()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"embed failed: {e}")
    return {
        "embeddings": embeddings,
        "model": model_name,
        "duration_ms": round((time.time() - t0) * 1000, 1),
    }


@router.post("/rerank")
async def rerank(request: Request) -> dict:
    body = await request.json()
    query = body.get("query") or ""
    documents = body.get("documents") or []
    if not query or not documents:
        raise HTTPException(status_code=422, detail="query and documents are required")
    t0 = time.time()
    try:
        model = _get_reranker()
        pairs = [(query, d["text"]) for d in documents]
        scores = model.compute_score(pairs)
        ranked = sorted(
            [{"id": d["id"], "score": float(s)} for d, s in zip(documents, scores)],
            key=lambda x: x["score"],
            reverse=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"rerank failed: {e}")
    return {
        "ranked": ranked,
        "model": "bge-reranker-v2-m3",
        "duration_ms": round((time.time() - t0) * 1000, 1),
    }


def build_app() -> FastAPI:
    app = FastAPI(title="intercraft-embedding", version="0.1.0")
    app.include_router(router)
    return app


__all__ = ["build_app", "router"]