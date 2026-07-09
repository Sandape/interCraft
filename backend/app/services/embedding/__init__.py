"""Embedding + Rerank service (REQ-048).

Single-process FastAPI sub-service exposing ``/embed`` + ``/rerank`` +
``/health`` endpoints, called by the parent FastAPI app over internal HTTP.

Local development: ``python -m app.services.embedding.cli health``.
Production: deployable as a separate worker; see ``app/workers/embedding_worker.py``
for the arq-side task that drives writes to ``error_questions.embedding``.

This module is currently a skeleton — the body of embedder / reranker /
server / cli is filled in during Phase 4 / US2 (T013-T017).
"""

__all__: list[str] = []