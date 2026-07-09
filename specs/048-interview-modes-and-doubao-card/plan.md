# Implementation Plan: Interview Mode Split + Doubao Card Export (REQ-048)

**Branch**: `048-interview-modes-and-doubao-card` | **Date**: 2026-07-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/048-interview-modes-and-doubao-card/spec.md`

## Summary

REQ-048 splits the Interview flow into three modes selectable before starting: 「在线 AI 面试」(sub-modes 「快速补漏」 + 「完整面试」) and 「豆包面试」 (renders a JD + InterviewPlan card for screenshot to 豆包 app). Core technical innovation is the Hybrid retrieval pipeline (BM25 + BGE embedding + bge-reranker-v2-m3 cross-encoder) replacing the current single-LLM planner for quick-drill question selection. The Doubao card sub-feature introduces a Node.js satori-based renderer with 4:3 + 9:16 variants.

## Technical Context

**Language/Version**:
- Backend: Python 3.11+ (existing FastAPI)
- Card renderer: Node.js 22+ (new sub-service)
- Frontend: TypeScript strict + React 18 (existing)

**Primary Dependencies**:
- Backend: `FlagEmbedding>=1.2` (new), `transformers>=4.38` (new), `pgvector` (PostgreSQL extension), arq (existing), FastAPI (existing), LangGraph (existing)
- Card renderer: `@vercel/og` (satori + resvg), `sharp` (mozjpeg), `Noto Sans SC` (subset)
- Frontend: React 18, TanStack Query, Zustand (existing); no new deps

**Storage**:
- PostgreSQL 15+ with `pgvector` extension (NEW dependency)
- Redis 6+ for `drill_cache` (5min) + `card_cache` (7d) — existing
- HuggingFace local cache: `bge-reranker-v2-m3` (already downloaded 2.27 GB), `bge-small-zh-v1.5` (need to download 93 MB)

**Testing**:
- Backend: `uv run pytest -q` (existing) + new tests for drill selector / card renderer / embedding service
- Frontend: `npm run test` + `npm run typecheck` (existing)
- E2E: Playwright `tests/e2e/quick-drill.spec.ts` + `tests/e2e/full-interview-15.spec.ts` + `tests/e2e/doubao-card.spec.ts` (NEW)

**Target Platform**: Linux server (production) + Windows 11 (existing dev)

**Project Type**: Web application (frontend + backend + 2 new sub-services: embedding service + card renderer)

**Performance Goals**:
- Drill selection p95 ≤3s (SC-010)
- Card render p95 ≤5s (SC-030)
- Embedding compute (offline) p95 ≤500ms per error_question
- Rerank top-50 p95 ≤2.5s on CPU

**Constraints**:
- CPU-only inference for both bge-small (embedding) + bge-reranker-v2-m3 (no GPU)
- Card file size ≤300KB (4:3 + 9:16)
- Embedding service single-process, no horizontal scaling in v1
- Existing DeepSeek 500K/month quota must not be eroded by LLM rerank (cross-encoder replaces LLM listwise rerank)

**Scale/Scope**:
- Per-user error_question growth: <100/day, <500/year (A-006)
- Drill sessions/day: estimated 1000-5000 across all users in steady state
- Card renders/day: estimated 200-1000
- embedding + reranker services single-process, ~50 RPS combined

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Phase 0 Check (against constitution v1.0.0)

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | ✅ PASS | embedding_service + card_renderer each isolated library with own CLI + README |
| II. CLI Interface | ✅ PASS | CLI-1/2/3 in contracts/cli.md cover all 3 sub-services |
| III. Test-First (NON-NEGOTIABLE) | ✅ PASS | tasks.md will put unit/integration/E2E tests before impl |
| IV. Integration & Synchronization | ✅ PASS | Playwright E2E + Postgres RLS contract tests required |
| V. Observability | ✅ PASS | `@traced_node` decorator reuse + analytics_events table + OTel spans |

### Post-Phase 1 Check (re-evaluated after design)

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | ✅ PASS | embedding + card_renderer + drill_selector each in own folder; no shared internals |
| II. CLI Interface | ✅ PASS | CLI surfaces allow local dev without Docker stack |
| III. Test-First | ✅ PASS | Per tasks.md template: T1 unit test → T2 impl → T3 integration → T4 E2E |
| IV. Integration | ✅ PASS | Quick drill E2E spec covers BM25+embedding+rerank full pipeline with real PG/Redis |
| V. Observability | ✅ PASS | analytics_events table + OTel spans on all 3 sub-services + LangSmith traces for parent graph |

**No violations.** Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/048-interview-modes-and-doubao-card/
├── plan.md              # This file
├── research.md          # Phase 0 output (resolved 11 NEEDS CLARIFICATION)
├── data-model.md        # Phase 1 output (3 migrations + 1 new table)
├── quickstart.md        # Phase 1 output (5 E2E scenarios + CLI verification)
├── contracts/
│   ├── http-api.md      # Phase 1 output (8 new/modified HTTP endpoints)
│   └── cli.md           # Phase 1 output (5 CLI surfaces)
├── checklists/
│   └── requirements.md  # 16/16 PASS
└── tasks.md             # Phase 2 output (next command, NOT yet created)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── agents/interview/                    # MODIFY (existing)
│   │   ├── nodes/
│   │   │   ├── mode_guard.py                # NEW (豆包早停条件)
│   │   │   ├── drill_selector.py            # NEW (Hybrid retrieval)
│   │   │   ├── variant_generator.py         # NEW (变体重考)
│   │   │   ├── question_gen.py              # MODIFY (accept error_question_ids)
│   │   │   └── sink_error.py                # MODIFY (UPSERT + state machine)
│   │   └── graph.py                         # MODIFY (wire mode_guard + 3 sub-modes)
│   ├── modules/interviews/
│   │   ├── models.py                        # MODIFY (+mode, +max_questions, +error_question_ids)
│   │   └── service.py                       # MODIFY (mode-aware start)
│   ├── modules/errors/
│   │   └── service.py                       # REVIEW (regression path support)
│   ├── services/
│   │   ├── embedding/                       # NEW library
│   │   │   ├── __init__.py
│   │   │   ├── server.py                    # FastAPI HTTP server
│   │   │   ├── cli.py                       # Click/typer CLI
│   │   │   ├── embedder.py                  # bge-small-zh-v1.5 wrapper
│   │   │   ├── reranker.py                  # bge-reranker-v2-m3 wrapper
│   │   │   ├── client.py                    # HTTP client (called by FastAPI)
│   │   │   └── README.md                    # Library-first README
│   │   └── card_renderer/                   # NEW library
│   │       ├── __init__.py
│   │       ├── server.py                    # FastAPI HTTP server (Node alternative)
│   │       ├── cli.py                       # CLI for local render
│   │       ├── renderer.py                  # satori + resvg + sharp wrapper
│   │       ├── templates/
│   │       │   ├── card_4x3.tsx             # JSX template
│   │       │   └── card_9x16.tsx            # JSX template
│   │       ├── fonts/
│   │       │   └── NotoSansSC-subset.woff2  # git LFS
│   │       └── README.md                    # Library-first README
│   └── workers/
│       └── embedding_worker.py              # NEW (arq task: compute embedding)
├── migrations/
│   ├── versions/
│   │   ├── 0028_interview_mode_split.py     # NEW
│   │   ├── 0029_error_questions_embedding.py # NEW
│   │   └── 0030_analytics_events.py         # NEW
└── tests/
    ├── unit/
    │   ├── services/embedding/              # NEW (test embedder + reranker with real models)
    │   ├── services/card_renderer/          # NEW (test satori templates)
    │   └── agents/interview/test_drill_selector.py  # NEW
    └── integration/
        ├── test_drill_e2e.py                # NEW (Hybrid retrieval full pipeline)
        ├── test_card_render.py              # NEW (Doubao card full render)
        └── test_embedding_pipeline.py       # NEW (write → enqueue → compute → read)

frontend/src/
├── pages/
│   ├── InterviewModeSelect.tsx              # NEW (mode entry page)
│   ├── InterviewList.tsx                    # MODIFY (+mode column)
│   └── InterviewLive.tsx                    # MODIFY (variant toggle)
├── components/interview/
│   ├── ModeCard.tsx                         # NEW (在线 AI 面试 / 豆包面试 入口卡)
│   ├── DrillCandidatesPreview.tsx           # NEW (5 题预览)
│   ├── VariantToggle.tsx                    # NEW (原题/变体 toggle)
│   └── DoubaoCardPreview.tsx                # NEW (卡片预览 + 下载)
├── api/
│   └── interviews.ts                        # MODIFY (mode-aware + card endpoint)
└── stores/
    └── useInterviewModeStore.ts             # NEW (mode selection state)

tests/e2e/
├── quick-drill.spec.ts                      # NEW (full E2E)
├── full-interview-15.spec.ts                # NEW (10-15 题 + adaptive termination)
├── doubao-card.spec.ts                      # NEW (card render + download)
└── mode-recommendation.spec.ts              # NEW (intelligent recommendation)

docs/evidence/048-interview-modes-and-doubao-card/
├── architecture-decision.md                 # WHY cross-encoder over LLM rerank
├── sample-cards/
│   ├── card-4x3-sample.jpg
│   └── card-9x16-sample.jpg
└── drill-eval-set.md                        # 20 hand-labeled drill test cases
```

**Structure Decision**: Option 2 (web application) — frontend + backend + 2 new isolated backend sub-services (embedding + card_renderer). Each sub-service is its own library per Constitution I.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| (none) | All Constitution principles satisfied | n/a |

## Phase Status

| Phase | Status | Output |
|---|---|---|
| 0: Outline & Research | ✅ COMPLETE | [research.md](research.md) — 14 decisions + risk register |
| 1: Design & Contracts | ✅ COMPLETE | [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md) |
| 2: Tasks (NOT created by /speckit-plan) | ⏳ PENDING | Run `/speckit-tasks` next |

---

## Key Implementation Decisions (summary from research.md)

| ID | Decision | Rationale |
|---|---|---|
| R-1 | bge-small-zh-v1.5 (512 维) embedding | CPU 可跑，~93MB，精度足够 |
| R-2 | bge-reranker-v2-m3 cross-encoder | 本机已下载，省 LLM 配额 |
| R-3 | BM25 + cosine + cross-encoder Hybrid | Anthropic Contextual Retrieval 同款 |
| R-4 | @vercel/og (satori + resvg) + sharp | warm 80-250ms, 完美 CJK |
| R-5 | Redis 5min drill_cache | 同用户短时复用 |
| R-6 | effective_max = max(7, min(user, planner)) | 硬下限 7 保证报告样本 |
| R-7 | 默认原题 + UI toggle 切变体 | 节省 LLM + 防背题 |
| R-8 | UPSERT + 错题状态机 service 复用 | 闭环 + 不污染错题本 |
| R-9 | MODE_GUARD 节点早停 Planner | 复用 LangGraph 子图编排 |
| R-10 | Noto Sans SC 子集化 | 9MB → 200KB |
| R-11 | arq worker async compute | 复用现有 arq 0.25+ |

## Dependency Injection (to add)

```python
# app/core/config.py — ADD fields
embedding_service_url: str = "http://127.0.0.1:8765"
embedding_model_name: str = "bge-small-zh-v1.5"
embedding_timeout_seconds: int = 10
reranker_service_url: str = "http://127.0.0.1:8765"  # same as embedding (combined service)
reranker_model_name: str = "bge-reranker-v2-m3"
reranker_timeout_seconds: int = 30
card_renderer_url: str = "http://127.0.0.1:8766"
card_render_timeout_seconds: int = 10
drill_cache_ttl_seconds: int = 300
card_cache_ttl_days: int = 7
min_questions_full: int = 7
max_questions_full: int = 15
adaptive_termination_threshold: float = 8.0
adaptive_termination_window: int = 3
```

## Migration Sequence

```
0028_interview_mode_split.py  (interview_sessions +mode, +max_questions, +error_question_ids)
   ↓
0029_error_questions_embedding.py  (pgvector + embedding + tsvector GIN)
   ↓
0030_analytics_events.py  (埋点表 + RLS)
```

## Risk Mitigation (deferred to tasks.md)

| Risk | Owner Task | Mitigation |
|---|---|---|
| pgvector 扩展未启用 | T-M01 | 显式 `CREATE EXTENSION IF NOT EXISTS vector` |
| mastered → reviewing 反向迁移不支持 | T-R01 | review existing service code; ~20 line PR if needed |
| bge-small 首次下载失败 | T-E01 | HF 镜像 + retry 3 + timeout 60s |
| 卡片渲染 OOM | T-C01 | 字体子集化 + 渲染超时 5s + max 1 concurrent |
| embedding + reranker 单进程 SPOF | (deferred to v2) | 暂不水平扩展（v1 单用户量不足） |