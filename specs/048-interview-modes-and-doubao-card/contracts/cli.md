# CLI Contracts — REQ-048

**Date**: 2026-07-07
**Purpose**: CLI surfaces for embedding service + card renderer (per Constitution Principle II: CLI Interface)

---

## CLI-1. Embedding Service CLI

**Module**: `app.services.embedding.cli`

### `python -m app.services.embedding.cli embed --text "..."`

Embed a single text and print 512-dim vector as JSON.

```bash
$ python -m app.services.embedding.cli embed --text "分布式事务如何解决一致性"
[0.012, -0.034, 0.089, ...]  # 512 floats
```

### `python -m app.services.embedding.cli embed-batch --input file.txt --output embeddings.jsonl`

Batch embed from a newline-delimited text file.

```bash
$ python -m app.services.embedding.cli embed-batch \
    --input questions.txt \
    --output embeddings.jsonl \
    --model bge-small-zh-v1.5
```

### `python -m app.services.embedding.cli health`

Check service health and loaded models.

```bash
$ python -m app.services.embedding.cli health
{"status": "ok", "models_loaded": ["bge-small-zh-v1.5", "bge-reranker-v2-m3"], "uptime_seconds": 12345}
```

---

## CLI-2. Card Renderer CLI

**Module**: `app.services.card_renderer.cli`

### `python -m app.services.card_renderer.cli render --plan plan.json --size 4_3 --output card.jpg`

Render a card from InterviewPlan JSON.

```bash
$ python -m app.services.card_renderer.cli render \
    --plan specs/048-interview-modes-and-doubao-card/fixtures/sample-plan.json \
    --size 4_3 \
    --output /tmp/card.jpg
Rendered 234567 bytes in 1245ms → /tmp/card.jpg
```

### `python -m app.services.card_renderer.cli render --plan plan.json --size 9_16 --output card-portrait.jpg`

Render 9:16 portrait version.

---

## CLI-3. Quick Drill Selector CLI

**Module**: `app.agents.interview.cli.select_drill`

> For ops to manually verify / regenerate drill cache without UI.

### `python -m app.agents.interview.cli.select_drill --user-id <uuid> --job-id <uuid> --limit 5`

```bash
$ python -m app.agents.interview.cli select_drill \
    --user-id 019ec1be-1234-5678-9abc-def012345678 \
    --job-id abc-def-123 \
    --limit 5

{
  "candidates": [
    {"source_question_id": "...", "dimension": "tech_depth", "score": 4, "jd_alignment": 0.87},
    ...
  ],
  "dimension_distribution": {"tech_depth": 2, "architecture": 2, "engineering_practice": 1},
  "duration_ms": 2345,
  "cache_hit": false
}
```

### `python -m app.agents.interview.cli select_drill --user-id <uuid> --job-id <uuid> --no-cache`

Force re-run without cache.

---

## CLI-4. Migration Verification

### `python -m app.cli.migrate verify --target 0028_interview_mode_split`

Verify migrations 0028/0029/0030 applied correctly.

```bash
$ python -m app.cli.migrate verify --target 0029_error_questions_embedding
✓ pgvector extension enabled
✓ error_questions.embedding column exists (vector(512))
✓ HNSW index idx_error_questions_embedding exists
✓ error_questions.embedding_v2 column exists (vector(1024))
✓ GIN index idx_error_questions_tsvector exists
```

---

## CLI-5. Card Cache Management

### `python -m app.services.card_renderer.cli cache stats`

```bash
$ python -m app.services.card_renderer.cli cache stats
{
  "total_cached_cards": 142,
  "total_size_bytes": 34567890,
  "hit_rate_24h": 0.42,
  "avg_render_duration_ms": 1245
}
```

### `python -m app.services.card_renderer.cli cache purge --older-than 7d`

Purge expired cards.