# agent_memory — Cross-Session Long-Term Memory Layer (REQ-028 US1)

Self-contained module for storing and retrieving agent memories across sessions.

US1 scope: **semantic memory only** — user facts (target position, identified
weakness, stated preference). Episodic / procedural / user-control API are
deferred (see `specs/028-long-term-memory/tasks.md`).

## Architecture

```
interview graph
    │
    ├── planner_context_node
    │       │
    │       └── retrieve_active_memories(user_id, graph="interview",
    │                                        node="planner_context")
    │           │
    │           └── AgentMemoryRepository.list_active_memories
    │               (RLS-scoped SELECT on semantic_memories)
    │
    └── report_node (after interview completes)
            │
            └── ARQ enqueue "extract_memories"
                    │
                    └── extract_and_store(user_id, session_id, state)
                        │
                        ├── extract_facts(state) — rule-based
                        ├── redact(fact_value) — email/phone PII
                        └── AgentMemoryRepository.upsert_semantic_memory
                            (latest-wins: old row → status='superseded',
                                            new row → status='active')
```

## Tables

### `semantic_memories`

| Column | Type | Notes |
|---|---|---|
| id | UUID v7 | PK |
| user_id | UUID | FK → users.id, RLS-scoped |
| fact_key | TEXT | e.g. `target_position`, `identified_weakness` |
| fact_value | TEXT | PII-redacted before storage |
| confidence | NUMERIC(3,2) | 0.0–1.0 |
| source | TEXT | `extracted_from_llm_output` / `user_asserted` / `system_inferred` |
| version | INT | Per-fact revision counter (1, 2, 3, …) |
| status | TEXT | `active` / `superseded` |
| schema_version | INT | Extraction-logic version (FR-004) |
| meta | JSONB | `{session_id, dimension, score, ...}` |
| superseded_at | TIMESTAMPTZ | NULL when status=active |
| superseded_by | UUID | FK → semantic_memories.id (self-ref) |
| created_at, updated_at | TIMESTAMPTZ | |

**Partial unique index** `uq_semantic_memories_active_user_key` on
`(user_id, fact_key) WHERE status = 'active'` enforces one active fact per
key per user at the DB level.

### `memory_retrieval_logs`

Observability table (FR-012). One row per `retrieve_active_memories()` call.

## API

### Extractor

```python
from app.modules.agent_memory.extractor import extract_and_store
from app.modules.agent_memory.repository import AgentMemoryRepository

async with get_session_context() as session:
    await session.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})
    repo = AgentMemoryRepository(session)
    summary = await extract_and_store(
        user_id=user_id,
        session_id=session_id,
        state={"position": "前端", "company": "字节", "interview_report": {...}},
        repo=repo,
    )
    # summary: {"extracted": 3, "stored": 3, "blocked": 0, "details": [...]}
```

### Retriever

```python
from app.modules.agent_memory.retriever import retrieve_active_memories

async with get_session_context() as session:
    await session.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})
    result = await retrieve_active_memories(
        user_id=user_id,
        graph="interview",
        node="planner_context",
        session=session,
        token_budget=500,
    )
    # result.memories: list[SemanticMemoryOut]
    # result.degraded: bool (True if DB error → empty list returned)
```

### Repository

```python
repo = AgentMemoryRepository(session)
row = await repo.upsert_semantic_memory(
    user_id=user_id, fact_key="target_position", fact_value="前端",
    confidence=1.0, source="user_asserted",
)
memories = await repo.list_active_memories(user_id, limit=50)
await repo.purge_user_memories(user_id)  # US4 forget-me
```

## Conflict Resolution (Latest-Wins)

When `upsert_semantic_memory` is called with a `fact_key` that already has an
`active` row:

1. If `fact_value` is **identical** → no-op (idempotent).
2. If `fact_value` **differs** → old row gets `status='superseded'`,
   `superseded_at=now()`, `superseded_by=<new_id>`. New row inserted with
   `version=old.version+1`, `status='active'`.

The old row is **never deleted** (spec SC-006). This preserves history for
audit / US4 user-facing "memory history" view.

## RLS

Both tables have `FORCE ROW LEVEL SECURITY` with policy
`<table>_user_isolation`:
```sql
USING (user_id = current_setting('app.user_id', true)::uuid)
WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
```

The caller must `SET LOCAL app.user_id = <user_id>` before any operation.
The repository does not set the GUC itself — keeps it composable with the
caller's transaction boundary.

## PII Redaction (FR-009)

`redactor.redact(value)` returns `(redacted_value, blocked)`:
- Email addresses and phone numbers (CN mobile + US) replaced with `[REDACTED]`.
- If the value is essentially only PII (redaction removed most of it), `blocked=True`
  and the fact is dropped.

US4 will add LLM-based PII classification. US1 uses regex — sufficient for
the 3 fact types extracted (target_position / target_company /
identified_weakness), which rarely contain incidental PII.

## Graceful Degrade (FR-013)

`retrieve_active_memories` catches **all** exceptions. On error:
1. Logs `memory.retrieve.failed` with full traceback.
2. Writes a `MemoryRetrievalLog` row with empty `retrieved_memory_ids` (best-effort).
3. Returns `MemoryRetrieveOut(memories=[], degraded=True)`.

The caller (planner_context_node) treats this as "no memories" and proceeds
with the interview. The user sees no error.

## Testing

- `tests/test_models.py` — model instantiation + CHECK constraints
- `tests/test_repository.py` — upsert + latest-wins + idempotent + RLS
- `tests/test_extractor.py` — fact extraction from mock state
- `tests/test_retriever.py` — token budget + graceful failure
- `backend/tests/integration/test_agent_memory.py` — end-to-end (planner_context injection)

All tests use `MockLLMClient` — no real DeepSeek calls.
