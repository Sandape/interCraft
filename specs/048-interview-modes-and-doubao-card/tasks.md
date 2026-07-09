---
description: "Task list for REQ-048 Interview Mode Split + Doubao Card Export"
---

# Tasks: Interview Mode Split + Doubao Card Export (REQ-048)

**Input**: Design documents from `/specs/048-interview-modes-and-doubao-card/`
- spec.md (6 user stories: 4× P1 + 2× P2)
- plan.md (technical context)
- research.md (14 decisions)
- data-model.md (3 migrations + 1 new table)
- contracts/ (8 HTTP endpoints + 5 CLI surfaces)
- quickstart.md (5 E2E scenarios)

**Tests**: Per Constitution Principle III (Test-First, NON-NEGOTIABLE), tests are **REQUIRED** for each user story. Test tasks MUST be written first and fail before implementation.

**Organization**: Tasks grouped by user story (US1-US6) to enable independent implementation + testing + delivery.

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3, US4, US5, US6 (from spec.md)
- Exact file paths included

## Path Conventions

- **Backend**: `backend/app/`, `backend/migrations/versions/`, `backend/tests/`
- **Frontend**: `src/` (NOT `frontend/src/`) — per AGENTS.md canonical rule
- **E2E**: `tests/e2e/`
- **Sub-services**: `backend/app/services/embedding/`, `backend/app/services/card_renderer/`
- **Interview API**: `backend/app/modules/interviews/api.py` (NOT `backend/app/api/v1/interviews.py`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization + new sub-service skeleton + dependency wiring

- [ ] T001 [P] Add dependencies to backend/pyproject.toml: FlagEmbedding>=1.2, transformers>=4.38, jieba, httpx (already present)
- [ ] T002 [P] Create embedding service skeleton at backend/app/services/embedding/{__init__.py, server.py, cli.py, embedder.py, reranker.py, client.py, README.md}
- [ ] T003 [P] Create card_renderer service skeleton at backend/app/services/card_renderer/{__init__.py, server.py, cli.py, renderer.py, templates/card_4x3.tsx, templates/card_9x16.tsx, fonts/.gitkeep, README.md}
- [ ] T004 [P] Add Settings fields to backend/app/core/config.py: embedding_service_url, embedding_model_name, embedding_timeout_seconds, reranker_service_url, reranker_model_name, reranker_timeout_seconds, card_renderer_url, card_render_timeout_seconds, drill_cache_ttl_seconds, card_cache_ttl_days, hard_min_questions_full, hard_max_questions_full, min_questions_full, max_questions_full, adaptive_termination_threshold, adaptive_termination_window
- [ ] T005 [P] Add env vars to backend/.env.example: EMBEDDING_SERVICE_URL, EMBEDDING_MODEL_NAME, RERANKER_SERVICE_URL, RERANKER_MODEL_NAME, CARD_RENDERER_URL, DRILL_CACHE_TTL_SECONDS, CARD_CACHE_TTL_DAYS, HARD_MIN_QUESTIONS_FULL, HARD_MAX_QUESTIONS_FULL, MIN_QUESTIONS_FULL, MAX_QUESTIONS_FULL, ADAPTIVE_TERMINATION_THRESHOLD, ADAPTIVE_TERMINATION_WINDOW
- [ ] T006 [P] Create backend/app/workers/embedding_worker.py — module containing `async def compute_embedding_task(ctx, error_question_id: str)` (task body only, no WorkerSettings; see T-NEW below)
- [ ] T007 [P] Create doc directory at docs/evidence/048-interview-modes-and-doubao-card/{sample-cards/, drill-eval-set.md, architecture-decision.md}

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST complete before ANY user story work

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 Create migration 0028_interview_mode_split.py in backend/migrations/versions/ — **note `interview_sessions.mode` column already exists (models.py:37)**; this migration ONLY ADD COLUMN max_questions/error_question_ids/drill_cache_key + add CHECK constraint `mode IN ('quick_drill','full','doubao')` + index on (user_id, mode)
- [ ] T009 Create migration 0029_error_questions_embedding.py in backend/migrations/versions/ — CREATE EXTENSION vector + ALTER TABLE error_questions ADD COLUMN embedding vector(512) + embedding_v2 vector(1024) + embedding_computed_at + embedding_model + HNSW index + GIN tsvector index
- [ ] T010 Create migration 0030_analytics_events.py in backend/migrations/versions/ — CREATE TABLE analytics_events + RLS + index
- [ ] T011 [P] Update backend/app/modules/interviews/models.py — **mode 字段已存在 (line 37)**; ONLY add max_questions / error_question_ids / drill_cache_key SQLAlchemy columns; ALSO update backend/app/modules/interviews/schemas.py with Pydantic validators + Literal['quick_drill','full','doubao'] enum
- [ ] T012 [P] Update backend/app/modules/errors/models.py — add ErrorQuestion.embedding / embedding_v2 / embedding_computed_at / embedding_model fields
- [ ] T013 [P] Create backend/app/services/embedding/embedder.py — FlagEmbedding-based embedder (bge-small-zh-v1.5, 512 维)
- [ ] T014 [P] Create backend/app/services/embedding/reranker.py — transformers-based reranker (bge-reranker-v2-m3, cross-encoder)
- [ ] T015 [P] Create backend/app/services/embedding/client.py — httpx async client wrapping /embed + /rerank + /health
- [ ] T016 [P] Create backend/app/services/embedding/server.py — FastAPI HTTP server exposing /embed /rerank /health endpoints
- [ ] T017 [P] Create backend/app/services/embedding/cli.py — typer-based CLI: embed / embed-batch / health
- [ ] T018 [P] Create backend/app/services/card_renderer/renderer.py — Python wrapper for satori + resvg + sharp (use pyogrio or python wrapper)
- [ ] T019 [P] Create backend/app/services/card_renderer/server.py — FastAPI HTTP server exposing /render /health endpoints
- [ ] T020 [P] Create backend/app/services/card_renderer/cli.py — typer-based CLI: render / cache stats / cache purge
- [ ] T021 Add Noto Sans SC subset font (150-200KB) to backend/app/services/card_renderer/fonts/ — git LFS
- [ ] T022 [P] Create backend/app/services/card_renderer/templates/card_4x3.tsx — JSX template (岗位标题 + 公司 + 难度 badge + 时长 + 大纲 5-8 条 + 品牌水印)
- [ ] T023 [P] Create backend/app/services/card_renderer/templates/card_9x16.tsx — JSX portrait template (same fields, vertical layout)
- [ ] T024 [P] Create backend/app/agents/interview/cli/select_drill.py — CLI for manual drill selection verification
- [ ] T025 [P] Create backend/app/agents/interview/nodes/mode_guard.py + wire into graph.py — LangGraph conditional edge that stops Planner sub-graph when state.mode='doubao' (creates node AND wires in same task, body ~30 lines)
- [ ] T026 [P] Create backend/app/agents/interview/nodes/drill_selector.py — Hybrid retrieval (BM25 + cosine + cross-encoder rerank) → top-5 (skeleton + imports only, body filled in T055)
- [ ] T027 [P] Create backend/app/agents/interview/nodes/variant_generator.py — LLM-based variant generation for 「快速补漏」变体模式 (skeleton + imports only, body filled in T099)
- [ ] T028 Update backend/app/agents/interview/state.py — extend InterviewOverallState with mode / max_questions / error_question_ids fields (preserve existing 20+1 schema)
- [ ] T029 Update backend/app/agents/interview/graph.py — wire mode_guard + 3 sub-modes (quick_drill/full/doubao) into existing LangGraph (depends on T025-T028, T030, T031)
- [ ] T030 Update backend/app/agents/interview/nodes/question_gen.py — accept error_question_ids in state and skip generation when present
- [ ] T031 Update backend/app/agents/interview/nodes/sink_error.py — UPSERT helper function + 状态机调用钩子 (skeleton; US6 T109 wires state machine service)
- [ ] T032a READ backend/app/modules/errors/service.py — verify mastered → reviewing 反向迁移 is natively supported (per A-007 risk); produce 1-page read note at docs/evidence/048-interview-modes-and-doubao-card/regression-readnote.md
- [ ] T032b [US6] IMPLEMENT mastered → reviewing regression path in backend/app/modules/errors/service.py if T032a finds gap (~20 lines PR; otherwise skip with note "no-op, already supported")

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 — Choose Interview Mode at Start (Priority: P1) 🎯 MVP

**Goal**: 「新建面试」入口加入「面试方式」选择页（在线 AI 面试 / 豆包面试两个并列入口；在线 AI 面试下二级选项「快速补漏」/「完整面试」；快速补漏在错题 < 5 时置灰）

**Independent Test**: demo 账号 → 「新建面试」 → 完成岗位参数 → 看到模式选择 → 错题 < 5 时「快速补漏」置灰 hover 提示

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T033 [P] [US1] Contract test for POST /api/v1/interviews in backend/tests/contract/test_interview_mode_contract.py — verify mode parameter validation (INSUFFICIENT_ERROR_POOL, INVALID_MAX_QUESTIONS, INVALID_COMBINATION error codes)
- [ ] T034 [P] [US1] Integration test for mode selection flow in backend/tests/integration/test_us1_mode_selection.py — login → start interview → mode selection → quick_drill disabled when <5 errors
- [ ] T035 [P] [US1] Playwright E2E test in tests/e2e/mode-selection.spec.ts — UI 流程：岗位 → 模式选择 → 错题置灰 hover 提示

### Implementation for User Story 1

- [ ] T036 [P] [US1] Create src/pages/InterviewModeSelect.tsx — mode selection page with 2 large cards (在线 AI 面试 / 豆包面试) [frontend root is `src/` per AGENTS.md]
- [ ] T037 [P] [US1] Create src/components/interview/ModeCard.tsx — 单个 mode card component with icon + title + description
- [ ] T038 [P] [US1] Create src/stores/useInterviewModeStore.ts — Zustand store for mode selection state
- [ ] T039 [P] [US1] Update src/api/interviews.ts — add mode / max_questions / use_variants params to start interview API
- [ ] T040 [US1] Update backend/app/modules/interviews/api.py — POST endpoint with mode-aware validation (depends on T033, T036). **Note**: actual API lives in `app/modules/interviews/api.py`, NOT `app/api/v1/interviews.py`
- [ ] T041 [US1] Update backend/app/modules/interviews/service.py — start_interview with mode branching (quick_drill → drill_selector; full → existing flow; doubao → mode_guard early stop)
- [ ] T042 [US1] Add analytics_events INSERT on mode selection (event_type='mode_selected') in backend/app/modules/interviews/service.py
- [ ] T043 [US1] Add frontend route for mode selection in src/App.tsx + router config

**Checkpoint**: User Story 1 should be fully functional and testable independently (MVP)

---

## Phase 4: User Story 2 — Quick Drill Mode: Hybrid Error-Question Selection (Priority: P1)

**Goal**: 「快速补漏」触发 Hybrid 检索 (BM25 + cosine + cross-encoder) → top-5 错题启动面试，5 分钟内复用缓存

**Independent Test**: demo 账号（≥50 错题）→ 选「快速补漏」 → ≤3s 返回 5 题，5 分钟内重复同岗位复用相同题

### Tests for User Story 2

- [ ] T044 [P] [US2] Unit test for BM25 retrieval in backend/tests/unit/test_drill_bm25.py — verify SQL tsvector query returns top-30 by relevance
- [ ] T045 [P] [US2] Unit test for cosine retrieval in backend/tests/unit/test_drill_cosine.py — verify pgvector <=> distance returns top-30 by similarity
- [ ] T046 [P] [US2] Unit test for cross-encoder rerank in backend/tests/unit/test_drill_rerank.py — verify top-50 → top-5 by bge-reranker score
- [ ] T047 [P] [US2] Unit test for cache logic in backend/tests/unit/test_drill_cache.py — verify 5min TTL + cache hit rate ≥80%
- [ ] T048 [P] [US2] Unit test for degradation path in backend/tests/unit/test_drill_degradation.py — verify BM25-only fallback when embedding/reranker down
- [ ] T049 [P] [US2] Integration test for full drill pipeline in backend/tests/integration/test_us2_drill_e2e.py — seed 50 errors → trigger drill → verify end-to-end
- [ ] T050 [P] [US2] Playwright E2E test in tests/e2e/quick-drill.spec.ts — UI flow: mode select → quick drill → 5 questions loaded → cache hit on repeat

### Implementation for User Story 2

- [ ] T051 [P] [US2] Create backend/app/agents/interview/drill_helpers/bm25_query.py — SQL builder for tsvector @@ plainto_tsquery
- [ ] T052 [P] [US2] Create backend/app/agents/interview/drill_helpers/cosine_query.py — SQL builder for pgvector <=> with embedding vector
- [ ] T053 [P] [US2] Create backend/app/agents/interview/drill_helpers/rerank_call.py — call embedding service /rerank with (JD, candidates)
- [ ] T054 [P] [US2] Create backend/app/agents/interview/drill_helpers/cache.py — Redis cache wrapper with 5min TTL
- [ ] T055 [US2] Implement backend/app/agents/interview/nodes/drill_selector.py — Hybrid pipeline orchestrator (depends on T051-T054, T013-T015)
- [ ] T056 [US2] Wire drill_selector into graph.py — quick_drill mode → drill_selector → question_gen
- [ ] T057 [US2] Add analytics_events INSERT on drill selection (event_type='drill_selected', payload={cache_hit, candidates, duration_ms})
- [ ] T058 [US2] Add analytics_events INSERT on degradation (event_type='drill_degraded_to_bm25' / 'drill_degraded_to_llm_rerank')
- [ ] T-NEW-1 [US2] Register `compute_embedding_task` (from T006) to `backend/app/workers/main.py:WorkerSettings.functions` list — without this the task is defined but never picked up by arq worker
- [ ] T-NEW-2 [US2] Backfill embedding for EXISTING error_questions where `embedding IS NULL` — create backend/scripts/backfill_embeddings.py using arq batch task; smoke test with 10 rows, then full backfill (estimated 1000 items × ~50ms = 50s wall-clock); verify with `SELECT COUNT(*) WHERE embedding IS NOT NULL` = total count after run
- [ ] T059 [P] [US2] Add GET /api/v1/interviews/quick-drill/preview endpoint in backend/app/modules/interviews/api.py (preview candidates before commit)
- [ ] T060 [P] [US2] Add GET /api/v1/interviews/mode-recommendation endpoint in backend/app/modules/interviews/api.py (recommend mode based on user history)
- [ ] T061 [P] [US2] Create src/components/interview/DrillCandidatesPreview.tsx — preview 5 candidates with dimension distribution + JD alignment
- [ ] T062 [US2] Wire DrillCandidatesPreview into src/pages/InterviewModeSelect.tsx — when quick_drill selected, show preview modal before commit

**Checkpoint**: US2 fully functional, error-driven drill selection works end-to-end

---

## Phase 5: User Story 3 — Full Interview Mode: 10-15 Questions with Agent-Controlled Depth (Priority: P1)

**Goal**: 「完整面试」支持 10 / 15 题软区间，Agent 根据分数自适应收尾

**Independent Test**: demo 账号 → 选「完整面试 + 中等（10 题）」 → 完成 9-11 题 → 报告 per_question_score 长度匹配

### Tests for User Story 3

- [ ] T063 [P] [US3] Unit test for effective_max calculation in backend/tests/unit/test_effective_max.py — verify effective_max = max(7, min(user, planner)) per FR-023; assert boundary values: user=10,planner=10 → 10; user=15,planner=15 → 15; user=10,planner=5 → 7 (hard min); user=15,planner=20 → 15 (hard max)
- [ ] T064 [P] [US3] Unit test for adaptive termination in backend/tests/unit/test_adaptive_termination.py — verify score ≥ 8.0 连续 3 题 + current ≥ effective_max - 3 triggers early report; **boundary assertions**: 中等 10 题最早 7 题收尾 (current=7 + 3 consecutive ≥8.0 → early terminate), 深入 15 题最早 12 题收尾 (current=12 + 3 consecutive ≥8.0 → early terminate); 硬下限 7 题即使条件满足也不提前 (current=6 → MUST NOT terminate even if all 3 scores ≥8.0)
- [ ] T065 [P] [US3] Integration test for full mode in backend/tests/integration/test_us3_full_interview.py — verify 10-15 题 range + dimension distribution
- [ ] T066 [P] [US3] Playwright E2E test in tests/e2e/full-interview-15.spec.ts — 完整 10 题 + adaptive termination scenario

### Implementation for User Story 3

- [ ] T067 [US3] Update backend/app/agents/interview/config.py — replace MAX_QUESTIONS constant with MIN_QUESTIONS_FULL=7, MAX_QUESTIONS_FULL=15, ADAPTIVE_TERMINATION_THRESHOLD=8.0, ADAPTIVE_TERMINATION_WINDOW=3 (depends on T063, T064)
- [ ] T068 [US3] Update backend/app/agents/interview/graph.py — wire effective_max computation into Planner prompt and question_gen termination logic
- [ ] T069 [US3] Update backend/app/agents/interview/nodes/question_gen.py — terminate at effective_max instead of fixed MAX_QUESTIONS
- [ ] T070 [US3] Update _route_after_score_llm in graph.py — add adaptive termination branch (score ≥ 8.0 连续 3 题 + current ≥ effective_max - 3)
- [ ] T071 [P] [US3] Update src/pages/InterviewLive.tsx — show progress bar with effective_max
- [ ] T072 [P] [US3] Add max_questions selector to src/components/interview/FullInterviewConfig.tsx (10 / 15 radio buttons)
- [ ] T073 [US3] Update planner.md prompt to consider effective_max + focus_areas count when generating interview plan

**Checkpoint**: US3 fully functional, 10-15 题 range + adaptive termination working

---

## Phase 6: User Story 4 — Doubao Card Generation & Export (Priority: P1)

**Goal**: 「豆包面试」模式只跑 Planner，渲染 4:3 + 9:16 双版本卡片供用户下载

**Independent Test**: demo 账号 → 选「豆包面试」 → Planner 完成 → ≤5s 看到 4:3 卡片 → 切到 9:16 → 下载 JPG ≤300KB

### Tests for User Story 4

- [ ] T074 [P] [US4] Unit test for card_renderer 4:3 in backend/tests/unit/test_card_renderer_4x3.py — verify satori produces 1080×810 image
- [ ] T075 [P] [US4] Unit test for card_renderer 9:16 in backend/tests/unit/test_card_renderer_9x16.py — verify satori produces 1080×1920 image
- [ ] T076 [P] [US4] Unit test for font subset in backend/tests/unit/test_card_font_subset.py — verify Noto Sans SC subset covers required characters
- [ ] T077 [P] [US4] Unit test for file size in backend/tests/unit/test_card_file_size.py — verify ≤300KB for both variants
- [ ] T078 [P] [US4] Integration test for Planner early stop in backend/tests/integration/test_us4_doubao_mode.py — verify mode='doubao' stops after planner_generate, no question_gen
- [ ] T079 [P] [US4] Integration test for card render end-to-end in backend/tests/integration/test_us4_card_render_e2e.py — verify InterviewPlan → image bytes
- [ ] T080 [P] [US4] Playwright E2E test in tests/e2e/doubao-card.spec.ts — UI flow: 豆包面试 → card preview → download → switch 9:16

### Implementation for User Story 4

- [ ] T081 [US4] Implement backend/app/services/card_renderer/renderer.py — satori + resvg + sharp mozjpeg pipeline (depends on T018, T021, T022, T023)
- [ ] T082 [US4] Implement backend/app/services/card_renderer/server.py — /render endpoint + /health endpoint (depends on T019)
- [ ] T083 [US4] Implement backend/app/services/card_renderer/cli.py — typer CLI for local render (depends on T020)
- [ ] T084 [US4] Add card cache logic (hash(JD+plan) → 7d TTL) in backend/app/services/card_renderer/cache.py
- [ ] T085 [US4] Update backend/app/agents/interview/planner_graph.py — Planner subgraph returns InterviewPlan as final state when mode='doubao'
- [ ] ~~T086 [US4] Wire mode_guard into graph.py~~ — **DONE via T025** (mode_guard creation + wire into graph.py merged into one Foundational task)
- [ ] T087 [US4] Add GET /api/v1/interviews/{session_id}/card endpoint in backend/app/modules/interviews/api.py (depends on T082)
- [ ] T088 [US4] Add analytics_events INSERT on card render (event_type='doubao_card_rendered', payload={size_variant, duration_ms, cache_hit, file_size_bytes})
- [ ] T089 [P] [US4] Create src/components/interview/DoubaoCardPreview.tsx — image preview + download + switch size variant
- [ ] T090 [P] [US4] Create src/components/interview/DoubaoCardActions.tsx — 「下载 JPG」 + 「复制大纲 Markdown」 + 「切换为 9:16」 buttons
- [ ] T091 [US4] Wire DoubaoCardPreview into mode selection flow — when doubao mode selected, show card preview after Planner completes
- [ ] T092 [P] [US4] Create src/lib/cardMarkdown.ts — generate Markdown from InterviewPlan for "复制大纲文本" CTA
- [ ] T093 [P] [US4] Generate sample card images to docs/evidence/048-interview-modes-and-doubao-card/sample-cards/ (4:3 + 9:16 variants)
- [ ] T094 [P] [US4] Generate hand-labeled drill eval set (20 test cases with ground truth) to docs/evidence/048-interview-modes-and-doubao-card/drill-eval-set.md

**Checkpoint**: US4 fully functional, doubao card downloadable in both variants

---

## Phase 7: User Story 5 — Drill Mode Question Variant Toggle (Priority: P2)

**Goal**: 「快速补漏」默认原题重考，UI 提供 toggle 切换变体重考

**Independent Test**: demo 账号 → 快速补漏 → toggle「换种问法」 → 题面变化但 dimension + expected_points 保留

### Tests for User Story 5

- [ ] T095 [P] [US5] Unit test for variant generation in backend/tests/unit/test_variant_generator.py — verify LLM generates new question_text while keeping dimension + expected_points
- [ ] T096 [P] [US5] Unit test for variant degradation in backend/tests/unit/test_variant_degradation.py — verify LLM failure → 原题重考 fallback
- [ ] T097 [P] [US5] Integration test for variant mode in backend/tests/integration/test_us5_variant_mode.py — verify end-to-end variant flow
- [ ] T098 [P] [US5] Playwright E2E test in tests/e2e/variant-toggle.spec.ts — UI flow: toggle「换种问法」 → start interview → verify variant questions

### Implementation for User Story 5

- [ ] T099 [US5] Implement backend/app/agents/interview/nodes/variant_generator.py body — LLM-based variant generation logic (skeleton already created in T027, depends on T095 contract)
- [ ] T100 [US5] Wire variant_generator into graph.py — when use_variants=true, run before question_gen
- [ ] T101 [US5] Add analytics_events INSERT on variant mode (event_type='variant_mode_enabled' / 'variant_generation_failed')
- [ ] T102 [P] [US5] Create src/components/interview/VariantToggle.tsx — toggle component with hover description
- [ ] T103 [US5] Wire VariantToggle into src/components/interview/DrillCandidatesPreview.tsx — show toggle before committing quick drill

**Checkpoint**: US5 fully functional, variant mode toggleable + degradable

---

## Phase 8: User Story 6 — Error Re-Sink on Low Score in Drill Mode (Priority: P2)

**Goal**: 「快速补漏」低分（<6）走 UPSERT + frequency 状态机迁移，保留 source_session_id

**Independent Test**: 5 道错题 → 快速补漏 → 答错 2 题 → 检查错题本：source_question_id 不变，last_practiced_at 更新，status 按状态机迁移

### Tests for User Story 6

- [ ] T104 [P] [US6] Unit test for frequency state machine in backend/tests/unit/test_error_state_machine.py — verify fresh→reviewing→mastered transitions
- [ ] T105 [P] [US6] Unit test for regression path in backend/tests/unit/test_error_regression.py — verify mastered→reviewing reverse migration
- [ ] T106 [P] [US6] Unit test for UPSERT in backend/tests/unit/test_sink_error_upsert.py — verify same source_question_id upsert behavior
- [ ] T107 [P] [US6] Integration test for re-sink in backend/tests/integration/test_us6_drill_resink.py — verify end-to-end low score → state machine
- [ ] T108 [P] [US6] Playwright E2E test in tests/e2e/drill-resink.spec.ts — UI flow: complete drill → verify error book updated

### Implementation for User Story 6

- [ ] T109 [US6] Implement backend/app/agents/interview/nodes/sink_error.py state machine integration — call `app.modules.errors.service.transition_state()` for frequency 状态机调整 + write UPSERT path (depends on T031 skeleton + T032a/T032b regression path; if T032b added regression code, T109 MUST cover mastered→reviewing trigger path; otherwise document "no-op")
- [ ] T110 [US6] Add analytics_events INSERT on re-sink (event_type='drill_resink_completed', payload={source_question_id, old_status, new_status, regression_detected})
- [ ] T111 [US6] Verify source_session_id NOT updated in sink_error_node — only last_practiced_at updated

**Checkpoint**: US6 fully functional, error book closed-loop with drill session

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories

- [ ] T112 [P] Update CLAUDE.md SPECKIT block to reference specs/048-interview-modes-and-doubao-card/plan.md (already done in plan workflow)
- [ ] T113 [P] Update specs/README.md with REQ-048 status (done / in_progress)
- [ ] T114 [P] Add architecture decision doc to docs/evidence/048-interview-modes-and-doubao-card/architecture-decision.md — WHY cross-encoder over LLM rerank
- [ ] T115 Run quickstart.md validation scripts:
  - backend smoke test: `uv run pytest -q tests/smoke/test_048_smoke.py`
  - CLI verification: `python -m app.services.embedding.cli health`
  - Card render: `python -m app.services.card_renderer.cli render --plan ...`
  - Migration verify: `python -m app.cli.migrate verify --target 0030_analytics_events`
- [ ] T116 [P] Run performance acceptance tests:
  - SC-010: drill selection p95 ≤3s (`python -m scripts.perf_test_drill`)
  - SC-013: cache hit rate ≥80% (`python -m scripts.measure_drill_cache_hit`)
  - SC-031: card file size ≤300KB (`python -m scripts.test_card_file_size`)
- [ ] T117 [P] Run full regression suite:
  - Backend: `cd backend && uv run pytest -q`
  - Frontend: `npm run test && npm run typecheck`
  - E2E: `npm run e2e -- --grep "quick-drill|full-interview|doubao-card|mode-selection|variant-toggle|drill-resink"`
- [ ] T118 Code review + cleanup: ensure no dead code, consistent naming, all `@traced_node` decorators carry `{agent}.{role}_{action}` prefix
- [ ] T119 [P] Security hardening: verify embeddings table RLS policy, verify analytics_events RLS, verify card render URL not exposed externally
- [ ] T120 Final deployment readiness check:
  - All 22 SC verified
  - All 8 Edge Cases handled
  - 13 assumptions validated
  - 11 Out of Scope items NOT touched

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Foundational)**: Depends on Setup completion - **BLOCKS all user stories**
- **Phases 3-8 (User Stories)**: All depend on Foundational phase completion
  - US1 (P1), US2 (P1), US3 (P1), US4 (P1) are independent — can run in parallel
  - US5 (P2) depends on US2 (variant mode is an extension of drill selection)
  - US6 (P2) depends on US2 (re-sink happens after drill selection completes)
- **Phase 9 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1) Mode Selection**: Depends on Foundational only
- **US2 (P1) Quick Drill Hybrid**: Depends on Foundational (embedding + reranker sub-services)
- **US3 (P1) Full Interview 10-15**: Depends on Foundational only
- **US4 (P1) Doubao Card**: Depends on Foundational (card_renderer sub-service)
- **US5 (P2) Variant Toggle**: Depends on US2 (drill selection complete + variant is optional layer)
- **US6 (P2) Error Re-Sink**: Depends on US2 (drill produces source_question_ids for re-sink)

### Within Each User Story

- Tests (TDD) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration

### Parallel Opportunities

- T001-T007 (Setup): all [P], can run in parallel
- T008-T032 (Foundational): T011/T012 (model updates) [P], T013-T017 (embedding service) [P], T018-T023 (card_renderer) [P], T024-T027 (interview nodes) [P]
- US1, US2, US3, US4 implementation: can be worked on in parallel by different team members
- Within each US: test tasks [P], model tasks [P], component tasks [P]

---

## Parallel Examples

### Setup (Phase 1)

```bash
# Launch all [P] Setup tasks together:
Task: "T001 Add FlagEmbedding + transformers + jieba to pyproject.toml"
Task: "T002 Create embedding service skeleton"
Task: "T003 Create card_renderer service skeleton"
Task: "T004 Add Settings fields to config.py"
Task: "T005 Add env vars to .env.example"
Task: "T006 Create arq worker module"
Task: "T007 Create docs/evidence dir"
```

### Foundational (Phase 2)

```bash
# After Setup complete, launch Foundational in waves:
Wave 1 (parallel):
Task: "T008 Create migration 0028_interview_mode_split.py"
Task: "T009 Create migration 0029_error_questions_embedding.py"
Task: "T010 Create migration 0030_analytics_events.py"
Task: "T011 Update interviews/models.py"
Task: "T012 Update errors/models.py"

Wave 2 (parallel):
Task: "T013-T017 Embedding service skeleton + impl"
Task: "T018-T023 Card renderer skeleton + impl"

Wave 3:
Task: "T024-T032 Interview nodes + state + graph wiring"
```

### User Story 1 (US1)

```bash
# Launch all tests first:
Task: "T033 Contract test for POST /api/v1/interviews"
Task: "T034 Integration test for mode selection flow"
Task: "T035 Playwright E2E test"

# After tests FAIL, launch impl in parallel:
Task: "T036 Create InterviewModeSelect.tsx"
Task: "T037 Create ModeCard.tsx"
Task: "T038 Create useInterviewModeStore.ts"
Task: "T039 Update interviews.ts API"
```

### Cross-US Parallelism (with 4 developers)

```text
After Foundational phase complete:
- Developer A: US1 (Mode Selection) — T033-T043
- Developer B: US2 (Quick Drill) — T044-T062
- Developer C: US3 (Full Interview 10-15) — T063-T073
- Developer D: US4 (Doubao Card) — T074-T094

Then US5 + US6 (P2 stories):
- Developer A: US5 (Variant Toggle) — T095-T103
- Developer B: US6 (Error Re-Sink) — T104-T111
```

---

## Implementation Strategy

### MVP First (User Story 1 + Minimal Foundation)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational CRITICAL parts only (T008-T032)
3. Complete Phase 3: User Story 1 (T033-T043)
4. **STOP and VALIDATE**: Test US1 independently (mode selection works)
5. Demo MVP: 用户能看到模式选择页（即使 drill/card/full 都还没实现）

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 → Mode selection page live
3. Add US2 → Quick drill works (MVP enhanced)
4. Add US3 → Full interview 10-15 题
5. Add US4 → Doubao card downloadable
6. Add US5 → Variant toggle (P2 enhancement)
7. Add US6 → Error book close-loop (P2 enhancement)
8. Each story adds value without breaking previous stories

### MVP Scope Recommendation

**MVP = US1 + US2 + US4** (all P1 with minimal cross-story dependency):
- US1: 用户入口可见
- US2: 「快速补漏」差异化价值
- US4: 「豆包面试」创新点
- US3 可以下一迭代再做（5→10 题改造相对独立）
- US5/US6 都是 P2 增强

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together (~2 days)
2. Once Foundational done:
   - Developer A: US1 (1 day)
   - Developer B: US2 (3 days — embedding pipeline is complex)
   - Developer C: US3 (1 day)
   - Developer D: US4 (2 days — card renderer is complex)
3. P2 stories (US5, US6) sequentially after P1 complete
4. Total estimate: 7-10 days for full MVP

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable + testable
- Verify tests FAIL before implementing (TDD per Constitution III)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All new code must carry `@traced_node("{agent}.{role}_{action}")` prefix per existing convention
- All migrations MUST include RLS policy for new tables (analytics_events)
- All Settings fields MUST be added to BOTH `config.py` AND `.env.example`
- Card render MUST keep file size ≤300KB (SC-031)
- Drill selection MUST keep p95 ≤3s (SC-010)

## Revision History (2026-07-07 复盘审计后)

**Original**: 120 tasks generated
**After revision**: 122 tasks (T032 split into T032a/T032b, +T-NEW-1 WorkerSettings registration, +T-NEW-2 backfill embedding, T086 merged into T025)

Key revisions applied:
1. ✅ Path corrections: API moved to `app/modules/interviews/api.py`; frontend paths now use `src/` (not `frontend/src/`)
2. ✅ Mode column noted as already existing (models.py:37)
3. ✅ T006 corrected: create worker module, not WorkerSettings (already exists at `app/workers/main.py:70`)
4. ✅ T025 + T086 merged: mode_guard creation + wire into graph.py in one Foundational task
5. ✅ T032 split: T032a = read existing service (verify regression path); T032b = implement if gap found
6. ✅ T064 + T067 + T004/T005: added `hard_min_questions_full` / `hard_max_questions_full` + boundary value assertions
7. ✅ Added T-NEW-1: register compute_embedding_task to WorkerSettings.functions (critical — without this task never runs)
8. ✅ Added T-NEW-2: backfill embedding for existing error_questions (critical — old questions would be invisible to drill selection)
9. ✅ T109 clarified: now depends on T032a/T032b outcome (no-op if regression already supported)
10. ✅ Phase 9 / Phase 3 / Path Conventions updated to reflect reality

After revision, tasks.md is ready for execution. **Confidence: 🟢 high.**