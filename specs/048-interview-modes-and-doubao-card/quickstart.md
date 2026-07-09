# Quickstart — REQ-048

**Date**: 2026-07-07
**Purpose**: End-to-end validation scenarios for Interview Mode Split + Doubao Card Export

---

## QS-1. Prerequisites

### Environment
- Python 3.11+
- Node.js 22+ (for card renderer sub-service)
- PostgreSQL 15+ with pgvector extension
- Redis 6+ (existing infrastructure)

### Models
- ✅ `bge-reranker-v2-m3` — **already downloaded** at `C:\Users\30803\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3\` (2.27 GB)
- ❌ `bge-small-zh-v1.5` — **need to download** (~93 MB) at first run

### Migration
```bash
cd backend
uv run alembic upgrade head  # applies 0028 / 0029 / 0030
```

### Embedding Service Startup
```bash
# Terminal 1: Embedding + Rerank Service
cd backend
EMBEDDING_MODEL_NAME=bge-small-zh-v1.5 \
RERANKER_MODEL_NAME=bge-reranker-v2-m3 \
uv run python -m app.services.embedding.server \
    --port 8765 \
    --host 127.0.0.1
```

### Card Renderer Startup
```bash
# Terminal 2: Card Renderer
cd backend
uv run python -m app.services.card_renderer.server \
    --port 8766 \
    --host 127.0.0.1
```

### Backend + Frontend (existing)
```bash
# Terminal 3: FastAPI
cd backend
uv run uvicorn app.main:app --reload --port 8000

# Terminal 4: Frontend
npm run dev
```

---

## QS-2. E2E Validation Scenarios

### Scenario A — Quick Drill with Hybrid Retrieval

**Setup**: Seed demo account `019ec1be-1234-5678-9abc-def012345678` with 50 error questions across 5 dimensions.

```bash
# Run seed
cd backend
uv run python -m scripts.seed_demo_errors --user-id 019ec1be-1234-5678-9abc-def012345678 --count 50
```

**Steps**:
1. Login as demo user (existing e2e setup)
2. Navigate to 「新建面试」
3. Select job: "字节跳动 / 高级前端工程师"
4. Click 「下一步：选择面试方式」
5. Click 「在线 AI 面试」→ Click 「快速补漏」

**Expected outcomes**:
- 5 questions loaded within ≤3s
- Each question's dimension aligns with JD (≥3 of 5 hit "tech_depth" or "architecture")
- POST `/api/v1/interviews/quick-drill/preview` returns same source_question_ids
- Within 5 min, repeat → same questions returned (cache hit)
- analytics_events has row `event_type='drill_degraded_*'` if any degradation occurred

**Verification**:
```bash
# Check embedding was computed
PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER intercraft -c \
  "SELECT COUNT(*) FROM error_questions WHERE embedding IS NOT NULL;"

# Should return 50 after ~1 minute (async embedding jobs)
```

---

### Scenario B — Full Interview 10-15 Questions

**Steps**:
1. Login as demo user
2. 「新建面试」→ Select job
3. Click 「在线 AI 面试」→ Click 「完整面试」
4. Select 「中等（10 题）」
5. Complete interview

**Expected outcomes**:
- Exactly 9-11 questions generated (SC-020)
- If 3 consecutive scores ≥ 8.0 reached at question 7, can early-terminate
- report.per_question_score length matches actual answered questions (7-11)
- At least 3 different dimensions covered

---

### Scenario C — Doubao Card Generation

**Steps**:
1. Login as demo user
2. 「新建面试」→ Select job
3. Click 「豆包面试」
4. Wait for Planner to complete (~10-30s)

**Expected outcomes**:
- Card preview shown within ≤5s (SC-030)
- Default 4:3 (1080×810) JPG ≤300KB
- Click 「切换为 9:16」→ renders 1080×1920 portrait
- Click 「下载 JPG」→ file downloads
- Click 「复制大纲文本」→ clipboard contains Markdown
- analytics_events has row `event_type='doubao_card_rendered'`
- No interview_sessions row created (only planner output)

---

### Scenario D — Degradation Path

**Setup**: Stop embedding service temporarily

```bash
# Kill embedding service
lsof -ti:8765 | xargs kill -9
```

**Steps**:
1. Trigger quick drill
2. Observe response time + UI toast

**Expected outcomes**:
- Top-of-screen toast: "错题匹配精度下降"
- Returns BM25 top-5 (no embedding cosine, no reranker)
- analytics_events has row `event_type='drill_degraded_to_bm25'`

---

### Scenario E — Variant Re-take

**Steps**:
1. Trigger quick drill
2. Before interview starts, click 「换种问法」 toggle
3. Start interview

**Expected outcomes**:
- Question text differs from original error_questions.question_text
- Same expected_points retained
- Same dimension retained
- analytics_events has row `event_type='variant_mode_enabled'`

---

## QS-3. CLI Verification

```bash
# Verify embedding service health
$ python -m app.services.embedding.cli health
{"status": "ok", "models_loaded": ["bge-small-zh-v1.5", "bge-reranker-v2-m3"]}

# Verify single embedding
$ python -m app.services.embedding.cli embed --text "分布式事务"
[0.012, -0.034, ...]  # 512 floats

# Verify card renderer
$ python -m app.services.card_renderer.cli render \
    --plan specs/048-interview-modes-and-doubao-card/fixtures/sample-plan.json \
    --size 4_3 --output /tmp/test-card.jpg
Rendered 234567 bytes in 1245ms

# Verify migration applied
$ python -m app.cli.migrate verify --target 0029_error_questions_embedding
✓ pgvector extension enabled
✓ error_questions.embedding column exists
✓ HNSW index exists
✓ GIN tsvector index exists

# Verify drill selector (no-cache)
$ python -m app.agents.interview.cli select_drill \
    --user-id 019ec1be-1234-5678-9abc-def012345678 \
    --job-id abc-def-123 --no-cache
```

---

## QS-4. Performance Acceptance Tests

```bash
# SC-010: Drill selection p95 ≤3s
$ python -m scripts.perf_test_drill --users 20 --iterations 5
p50: 1.2s, p95: 2.8s, p99: 3.5s  # p95 must be ≤3s

# SC-013: Cache hit rate ≥80%
$ python -m scripts.measure_drill_cache_hit --window 1h --users 100
cache_hit_rate: 0.84  # must be ≥0.80
```

---

## QS-5. Regression Suite

```bash
# Backend unit tests
cd backend
uv run pytest -q app/agents/interview/ app/modules/errors/ app/services/embedding/ app/services/card_renderer/

# Backend integration tests
uv run pytest -q tests/integration/test_drill_e2e.py tests/integration/test_card_render.py

# Frontend tests
npm run test
npm run typecheck

# E2E (Playwright)
npm run e2e -- --grep "quick-drill|full-interview|doubao-card"
```

---

## QS-6. Smoke Test (5 min)

```bash
# One-shot smoke test for CI
cd backend
uv run pytest -q tests/smoke/test_048_smoke.py

# Expected:
# - embedding_service /health → 200
# - card_renderer /health → 200
# - GET /api/v1/interviews/mode-recommendation → 200
# - demo user has error_count ≥ 5 (from seed)
# - migration 0028/0029/0030 applied
```