# Implementation Plan: Long-Term Memory Layer for Agents

**Branch**: `028-long-term-memory` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/028-long-term-memory/spec.md`

## Summary

Add a cross-session long-term memory layer (semantic / episodic / procedural)
so the 5 LangGraph agents can recall user facts, past interactions, and
learned interaction patterns. **This plan covers US1 only** — semantic
memory storage + extraction + retrieval, integrated into the interview
graph's planner_context. US2/US3/US4 and pgvector embedding retrieval are
scoped out (see Scope below).

The pre-existing `AsyncPostgresSaver` continues to handle thread-level
short-term state. This feature adds a separate cross-session memory layer
that is queried before the LLM is invoked and updated after a session
completes.

## Technical Context

**Language/Version**: Python 3.12 (backend only — frontend UI is out of scope for this feature).

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async), Alembic, LangGraph, ARQ + Redis, structlog, prometheus_client. No new dependencies required — pgvector is not used in US1 (exact-match retrieval only).

**Storage**: PostgreSQL — new table `semantic_memories` (+ `memory_retrieval_logs` for observability). RLS enforced per `app.user_id`, mirroring the pattern in `migrations/versions/0001_initial.py::_enable_rls`.

**Testing**: pytest + pytest-asyncio. Unit tests under `backend/app/modules/agent_memory/tests/`. Integration test under `backend/tests/integration/test_agent_memory.py`. Mock LLM via existing `MockLLMClient` (no real DeepSeek calls).

**Target Platform**: Linux server (production), Windows 11 + bash (local dev per project memory).

**Performance Goals**: SC-003 retrieval p95 ≤100ms (US1 trivially meets this — single-table SELECT with index, no embedding computation). SC-002 token budget ≤500 tokens/call enforced at retrieval layer.

**Constraints**: Memory extraction MUST NOT block agent response (FR-006) — extraction runs via ARQ after interview completion. Memory retrieval MUST degrade gracefully (FR-013) — failures are logged and the agent proceeds with no memories.

**Scale/Scope**: Per-user rows. Estimate ~10-50 active semantic memories per user after 10 interviews. Index on `(user_id, fact_key, status)` for upsert lookup.

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I — Library-First | PASS | New self-contained module `backend/app/modules/agent_memory/` with its own README. No edits to existing modules except where wiring is required (interview service enqueues extraction; planner_context calls retriever). |
| III — Test-First | PASS | Repository / extractor / retriever unit tests written alongside implementation. Integration test covers planner_context memory injection. |
| V — Observability | PASS | Structured logs at extract/retrieve boundaries (`memory.extract.complete`, `memory.retrieve.complete`). `memory_retrieval_logs` table records graph + node + retrieved memory ids + token budget + latency. |
| Security & Privacy | PASS | RLS on both tables. PII redaction in extractor (email/phone regex). Encryption-at-rest (FR-016) deferred to US4 — explicit ⏳ in tasks.md. |

## Project Structure

### Documentation (this feature)

```text
specs/028-long-term-memory/
├── spec.md              # Already exists (Draft)
├── plan.md              # This file
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   └── agent_memory/                # NEW — self-contained memory module
│   │       ├── README.md                # Module purpose, API, examples
│   │       ├── __init__.py
│   │       ├── models.py                # SemanticMemory, MemoryRetrievalLog
│   │       ├── schemas.py               # Pydantic I/O schemas
│   │       ├── repository.py            # CRUD + conflict resolution (latest-wins)
│   │       ├── extractor.py             # Extract semantic facts from interview state
│   │       ├── retriever.py             # Retrieve active memories for a user
│   │       ├── redactor.py              # PII redaction (email/phone regex)
│   │       └── tests/
│   │           ├── __init__.py
│   │           ├── test_models.py        # Model instantiation + CHECK constraint fixtures
│   │           ├── test_repository.py   # CRUD + latest-wins + RLS
│   │           ├── test_extractor.py    # Fact extraction from mock interview state
│   │           └── test_retriever.py    # Token budget + ranking + graceful failure
│   ├── agents/
│   │   └── interview/
│   │       └── nodes/
│   │           ├── planner_context.py   # MODIFIED — call memory retriever
│   │           └── planner_generate.py  # MODIFIED — render memory block in prompt
│   └── workers/
│       ├── main.py                       # MODIFIED — register extract_memories task
│       └── tasks/
│           └── extract_memories.py       # NEW — ARQ task wrapping extractor
├── migrations/
│   └── versions/
│       └── 0018_agent_memory.py          # NEW — semantic_memories + memory_retrieval_logs
└── tests/
    └── integration/
        └── test_agent_memory.py          # NEW — planner_context memory injection + extraction
```

**Structure Decision**: New module under `backend/app/modules/agent_memory/` (mirrors existing
module layout — `ability_profile/`, `interviews/`). The ARQ task lives under
`backend/app/workers/tasks/` to match the existing ARQ registration pattern in
`workers/main.py`. Interview graph integration is via minimal edits to two
existing nodes (`planner_context.py` + `planner_generate.py`).

## Scope

**US1 (implemented this plan)**:
- Semantic memory storage with RLS
- Rule-based extractor (target_position / target_company / identified_weakness)
- Retriever with token budget cap
- PII redaction (email/phone regex)
- Interview graph integration: planner_context retrieves + planner_generate renders
- ARQ task for post-interview extraction
- MemoryRetrievalLog observability

**⏳ Deferred to future work**:
- US2 — Episodic memory (past interactions, embedding-based retrieval)
- US3 — Procedural memory (interaction patterns)
- US4 — User control API (list / search / delete / forget-me) — storage layer already isolates by `user_id` so US4 is a thin addition
- pgvector embedding column + semantic similarity ranking (US1 uses exact `fact_key` match + created_at desc; no embedding model calls in US1)
- LangMem / Mem0 framework evaluation — US1 is a self-built lightweight layer; framework swap is a future planning decision
- Encryption at rest (FR-016) — depends on US4 user-control API scope
- Eval suite golden cases for memory injection (FR-019) — depends on US2/US3 to have meaningful memory types to eval

## Complexity Tracking

No Constitution violations. The partial implementation is justified by
L004 (api-quota-risk) — implementing all 4 US in one dev cycle has
historically caused 429 interruptions. US1 is closed-ended (storage +
extraction + retrieval + one graph integration), letting US2/US3/US4 be
scheduled as separate dev cycles.
