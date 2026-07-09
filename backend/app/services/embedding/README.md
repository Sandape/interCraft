# Embedding + Rerank Service (REQ-048)

Standalone Python sub-service that exposes:

- `POST /embed` — bge-small-zh-v1.5 (512-dim, CPU)
- `POST /rerank` — bge-reranker-v2-m3 (cross-encoder, CPU)
- `GET /health`

Run locally:

```bash
cd backend
EMBEDDING_MODEL_NAME=bge-small-zh-v1.5 \
RERANKER_MODEL_NAME=bge-reranker-v2-m3 \
uv run python -m app.services.embedding.cli health
```

Phase 4 / US2 fills in `embedder.py` / `reranker.py` / `server.py` bodies
(T013-T017).