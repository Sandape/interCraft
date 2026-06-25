# Tasks: Long-Term Memory Layer for Agents

**Input**: Design documents from `/specs/028-long-term-memory/`

**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: Tests are included for this feature (Constitution III — Test-First).

**Organization**: Tasks are grouped by user story. **US1 is implemented in this cycle; US2/US3/US4 are listed for traceability but marked ⏳.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Spec / plan / tasks scaffolding.

- [X] T001 [P] [US0] Create `specs/028-long-term-memory/plan.md` (this plan)
- [X] T002 [P] [US0] Create `specs/028-long-term-memory/tasks.md` (this file)

---

## Phase 2: Foundational — Storage Layer

**Purpose**: PostgreSQL schema + ORM models + RLS. MUST complete before any US1 logic.

- [X] T003 [US1] Create Alembic migration `backend/migrations/versions/0018_agent_memory.py` — `semantic_memories` + `memory_retrieval_logs` tables with RLS policies mirroring `_enable_rls` pattern.
- [X] T004 [US1] Create `backend/app/modules/agent_memory/__init__.py` (module init + exports).
- [X] T005 [US1] Create `backend/app/modules/agent_memory/models.py` — `SemanticMemory` (user_id, fact_key, fact_value, confidence, source, version, status, schema_version, timestamps, superseded_at) + `MemoryRetrievalLog` (trace_id, user_id, graph, node, query, retrieved_memory_ids, token_budget_used, retrieval_latency_ms, created_at).
- [X] T006 [US1] Create `backend/app/modules/agent_memory/schemas.py` — Pydantic I/O (`SemanticMemoryOut`, `MemoryRetrieveIn`, `MemoryRetrieveOut`, `MemoryExtractIn`).
- [X] T007 [US1] Create `backend/app/modules/agent_memory/redactor.py` — regex-based PII redaction for email + phone (CN/US). Returns `(redacted_value, blocked: bool)`.
- [X] T008 [US1] Create `backend/app/modules/agent_memory/repository.py` — CRUD with latest-wins conflict resolution (`upsert_semantic_memory` marks old row `superseded`, inserts new `active`).
- [X] T009 [US1] Create `backend/app/modules/agent_memory/README.md` — module purpose, API, example usage.

---

## Phase 3: User Story 1 — Semantic Memory Cross-Session Recall (Priority: P1) 🎯 MVP

**Goal**: After a user completes 3 interviews, the 4th interview's planner retrieves their target position, identified weaknesses, and stated preferences and injects them into the planner prompt — without re-asking.

**Independent Test**: Run 3 interview sessions for one user, then start a 4th. Confirm `planner_context_node` retrieves ≥3 active semantic memories and `planner_generate_node` injects them as a `## 长期记忆` section in the LLM prompt.

### Tests for User Story 1 ⚠️

> **NOTE**: Tests written alongside implementation. Repository/extractor/retriever unit tests use mock data; integration test uses real Postgres + MockLLMClient.

- [X] T010 [P] [US1] Unit test `backend/app/modules/agent_memory/tests/test_models.py` — model instantiation + CHECK constraints (status enum, confidence range, version monotonicity).
- [X] T011 [P] [US1] Unit test `backend/app/modules/agent_memory/tests/test_repository.py` — upsert + latest-wins + list_active + delete.
- [X] T012 [P] [US1] Unit test `backend/app/modules/agent_memory/tests/test_extractor.py` — extract target_position / target_company / identified_weakness from mock interview state.
- [X] T013 [P] [US1] Unit test `backend/app/modules/agent_memory/tests/test_retriever.py` — token budget cap + ranking + graceful failure on DB error.
- [X] T014 [US1] Integration test `backend/tests/integration/test_agent_memory.py` — end-to-end: extract memories → store → retrieve in planner_context → assert injected into prompt.

### Implementation for User Story 1

- [X] T015 [US1] Create `backend/app/modules/agent_memory/extractor.py` — rule-based fact extractor. Reads `state.position`, `state.company`, `state.interview_report.dimension_scores` and produces `(fact_key, fact_value, confidence, source)` tuples. Source is `extracted_from_llm_output` for weaknesses, `user_asserted` for position/company (the user entered them in the session create form).
- [X] T016 [US1] Create `backend/app/modules/agent_memory/retriever.py` — `retrieve_active_memories(user_id, *, graph, node, query=None, token_budget=500)`. Returns list of `SemanticMemoryOut` sorted by `created_at DESC`, capped by token budget. Logs `MemoryRetrievalLog` row. Catches all exceptions and returns `[]` on failure (FR-013 graceful degrade).
- [X] T017 [US1] Create `backend/app/workers/tasks/extract_memories.py` — ARQ task wrapping `extractor.extract_and_store(user_id, session_id, state)`. Best-effort: logs and swallows errors.
- [X] T018 [US1] Register `extract_memories` in `backend/app/workers/main.py::WorkerSettings.functions`.
- [X] T019 [US1] Modify `backend/app/agents/interview/nodes/planner_context.py` — after loading resume + job, call `retrieve_active_memories(user_id, graph="interview", node="planner_context")` and inject into `planner_context["memories"]`. Wrap in try/except; on failure, log warning and set `memories=[]`.
- [X] T020 [US1] Modify `backend/app/agents/interview/nodes/planner_generate.py` — add `_format_memory_section(memories)` and include it as `## 长期记忆` in `_format_user_content`. Empty memories produce no section (no log spam for new users — FR-013 edge case).
- [X] T021 [US1] Modify `backend/app/agents/interview/prompts/planner.md` — add a note that a `## 长期记忆` section may appear with prior-session facts; planner should leverage them.
- [X] T022 [US1] Modify `backend/app/modules/interviews/service.py::submit_answer` — after interview completes (5 scores + report written), enqueue `extract_memories` ARQ job (best-effort, log on enqueue failure).

**Checkpoint**: US1 fully functional — interview planner retrieves memories and injects them into the prompt. New users proceed with no memories (no error). Conflicting facts are resolved latest-wins.

---

## Phase 4: User Story 2 — Episodic Memory (Priority: P2) ⏳ DEFERRED

**Goal**: Error-coach retrieves past attempts at similar questions.

- [ ] T023 ⏳ [US2] Create `episodic_memories` table (pgvector embedding column).
- [ ] T024 ⏳ [US2] Create `EpisodicMemory` model + repository.
- [ ] T025 ⏳ [US2] Create extractor for error_coach episodes.
- [ ] T026 ⏳ [US2] Integrate retrieval into error_coach graph.
- [ ] T027 ⏳ [US2] Retention window enforcement (90-day default).

---

## Phase 5: User Story 3 — Procedural Memory (Priority: P3) ⏳ DEFERRED

**Goal**: Agent learns hint-style preferences.

- [ ] T028 ⏳ [US3] Create `procedural_memories` table.
- [ ] T029 ⏳ [US3] Pattern extractor (hint_style / rewrite_preference).
- [ ] T030 ⏳ [US3] Confidence threshold (≥3 samples) before applying.
- [ ] T031 ⏳ [US3] Integrate into error_coach + resume_optimize graphs.

---

## Phase 6: User Story 4 — User Control API (Priority: P2) ⏳ DEFERRED

**Goal**: User can list / search / delete / forget-me.

- [ ] T032 ⏳ [US4] `GET /api/v1/memory/semantic` — list user's semantic memories.
- [ ] T033 ⏳ [US4] `DELETE /api/v1/memory/semantic/{id}` — delete one.
- [ ] T034 ⏳ [US4] `POST /api/v1/memory/forget-me` — purge all (≤30s, SC-007).
- [ ] T035 ⏳ [US4] Encryption at rest (FR-016).
- [ ] T036 ⏳ [US4] Frontend memory management UI (out of original spec scope).

**Note**: Storage layer already enforces `user_id` RLS isolation (T003), so US4 is a thin API addition.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T037 [US1] Update `specs/README.md` — mark 028 as `in_progress (US1)`.
- [ ] T038 ⏳ [US0] pgvector embedding column + semantic similarity retrieval (replaces exact-match for US1 future iteration).
- [ ] T039 ⏳ [US0] Eval suite golden cases for memory injection (FR-019, depends on feature 026).
- [ ] T040 ⏳ [US0] LangMem / Mem0 framework evaluation spike.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Migration + models first; repository depends on models.
- **US1 (Phase 3)**: Tests + implementation interleaved. Repository/extractor/retriever unit tests run before integration test.
- **US2/US3/US4 (Phase 4-6)**: DEFERRED. Listed for traceability.

### Within US1

1. Migration T003 → models T005 → repository T008 (sequential — same conceptual layer).
2. Extractor T015 + Retriever T016 can run in parallel (different files, both depend only on T008).
3. ARQ task T017 + planner_context edit T019 depend on T015 + T016.
4. planner_generate edit T020 depends on T019 (state shape).
5. Integration test T014 runs last (exercises the full chain).

---

## Notes

- US1 is closed-ended: storage + extraction + retrieval + one graph integration. No pgvector, no LLM-driven extraction, no user-facing API.
- Tests use `MockLLMClient` (existing) — no real DeepSeek calls. Assertion is on the prompt content (the `## 长期记忆` section), not on LLM output.
- ARQ task registration follows the existing `ability_diagnose` pattern — best-effort enqueue, swallow errors.
- RLS pattern mirrors `migrations/versions/0001_initial.py::_enable_rls` — `FORCE ROW LEVEL SECURITY` + `CREATE POLICY ... USING (user_id = current_setting('app.user_id', true)::uuid)`.
