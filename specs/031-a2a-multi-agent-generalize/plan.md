# Implementation Plan: REQ-031 A2A Multi-Agent Generalization

**Branch**: `[031-a2a-multi-agent-generalize]` | **Date**: 2026-06-25 | **Spec**: [./spec.md](./spec.md)

## Summary

Extract the Supervisor + subgraph orchestration pattern from feature 025
(interview planner + interviewer) into a reusable library, then apply it to
the `error_coach` graph by splitting the existing hint flow into a
`HintLadderAgent` and a new `RecommendationAgent` that proposes similar
questions when the user is stuck. This plan covers **US1 (reusable A2A
framework)** and **US2 (error_coach split)**. US3 (resume_optimize split),
US4 (standardized A2A message protocol + interview graph migration),
LangGraph `Command` API full utilization, full fallback chain
(retry + circuit breaker + user-facing error), and cross-graph agent
interop are explicitly deferred.

The framework is a self-contained library (`backend/app/agents/a2a/`) with:

- `AgentDefinition` (name, role, input/output schema, routing rule)
- `A2AMessage` (from / to / task / context / expected output / status / trace)
- `Supervisor` (compiles `StateGraph` from agent list + routing fn)
- `DelegationRecord` persistence via a new `a2a_messages` table
- Built-in timeout (configurable, default 30 s)
- Delegation depth cap (default 3) + cycle detection
- Failure handling: retry once → fallback → user-facing error
- A CLI that takes agent declarations (yaml/json) and emits graph
  visualization + compile status

`error_coach` is refactored to use the framework: `HintLadderAgent` keeps
the existing `hint_ladder_node` logic; `RecommendationAgent` queries the
error question repository for similar questions when the user is stuck
(attempt_count ≥ 3). The existing 3-correct flow remains unchanged for
backward compat with the existing E2E suite.

## Technical Context

- **Language/Version**: Python 3.11 (project baseline; matches `pyproject.toml`).
- **Primary Dependencies**: LangGraph (StateGraph, Command, add_conditional_edges),
  Pydantic v2, SQLAlchemy 2.0 async, structlog, OTel (existing 029 layer).
  **No new package dependencies** — the framework is built on LangGraph's
  primitives and the existing DB / observability stack.
- **Storage**: One new table `a2a_messages` (delegation audit log) — RLS
  disabled because messages are scoped by thread_id and trace_id, not by
  user. `a2a_messages` carries `parent_agent`, `child_agent`, `task`,
  `context_jsonb`, `expected_output_jsonb`, `status`, `result_jsonb`,
  `error_reason`, `duration_ms`, `retry_count`, `trace_id`, `thread_id`,
  `created_at`. Existing tables untouched.
- **Testing**: pytest (asyncio_mode=auto). Unit tests for the framework's
  routing function, cycle detection, and timeout. Integration test for
  `error_coach` showing both `HintLadderAgent` and `RecommendationAgent`
  are invoked when the user is stuck (3 failed attempts). MockLLMClient
  drives the LLM path so the test is deterministic and quota-free.
- **Target Platform**: Linux server (production), Windows 11 + bash (dev).
- **Project Type**: backend library + small CLI + DB migration + one graph refactor.
- **Performance Goals**:
  - Routing decision: O(agents) per hop, < 1 ms.
  - Timeout enforcement: asyncio.wait_for around the agent node call.
  - A2AMessage insert: single INSERT per delegation, indexed on (trace_id, created_at).
- **Constraints**:
  - Must NOT break 023's `retry_graph_op` pattern for the checkpointer —
    `error_coach` continues to use `retry_graph_op` for `ainvoke` /
    `aget_state` / `aupdate_state`.
  - Must NOT touch the 025 interview graph in this iteration (US4
    deferred — working tree carries 025 changes that conflict if we
    refactor now).
  - The framework coexists with feature 029's OTel tracing — agent
    nodes can still carry `@traced_node` decorators, and the
    Supervisor's delegation decision emits a parent span.

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | ✅ Pass | `backend/app/agents/a2a/` is self-contained. Pure routing/state types have no DB / FastAPI dependency. DB-coupled `repository.py` is the only persistence surface. README documents AgentDefinition / Supervisor / routing / timeout / cycle detection. |
| II. CLI Interface | ✅ Pass | `python -m app.agents.a2a.cli --agents agents.json` prints graph nodes/edges + compile status. Returns exit 0 on success, exit 1 on cycle / missing agent. |
| III. Test-First | ✅ Pass | Routing function, cycle detection, and timeout tests written **before** implementation. error_coach integration test written before the graph refactor. |
| IV. Integration Tests | ✅ Pass | `test_error_coach_a2a_split` runs the full graph with MockLLMClient and asserts both `HintLadderAgent` and `RecommendationAgent` are called in the stuck path. |
| V. Observability | ✅ Pass | structlog events: `a2a.routing_decision` (parent, child, reason), `a2a.delegation_started` / `a2a.delegation_succeeded` / `a2a.delegation_failed` / `a2a.delegation_timeout` / `a2a.cycle_detected` / `a2a.depth_exceeded`. No PII in log attrs. |
| VI. Versioning | ✅ Pass | Schema migration is forward-only. Status enum (`pending` / `success` / `failed` / `timeout`) lives in CHECK constraint. |
| VII. Documentation | ✅ Pass | `backend/app/agents/a2a/README.md` describes AgentDefinition / Supervisor / A2AMessage / DelegationRecord / timeout / cycle detection / CLI usage / error_coach example. |

## Project Structure

### Documentation (this feature)

```text
specs/031-a2a-multi-agent-generalize/
├── plan.md              # This file
├── tasks.md             # Phase 2 tasks (US1 + US2 only; US3/US4 ⏳)
├── spec.md              # Source of truth (4 US, 1-2 implemented this cycle)
└── contracts/
    └── a2a-api.md       # Public framework API (function signatures, types)
```

### Source Code

```text
backend/app/agents/a2a/
├── README.md            # Constitution VII — usage, examples, error_coach sample
├── __init__.py          # Re-exports: AgentDefinition, Supervisor, A2AMessage, etc.
├── schemas.py           # Pydantic: AgentDefinition, A2AMessage, DelegationRecord
├── supervisor.py        # Supervisor class — compile_state_graph(agents, routing_fn)
├── routing.py           # Routing decision helpers (cycle detection, depth cap)
├── delegation.py        # Async delegation runner (timeout + retry + fallback)
├── repository.py        # A2AMessageRepository — persistence helper
├── models.py            # SQLAlchemy model for a2a_messages table
├── cli.py               # typer CLI: declare agents → print graph + compile status
└── tests/
    ├── __init__.py
    ├── test_schemas.py          # Pydantic validation (input/output schema, status enum)
    ├── test_routing.py          # cycle detection + depth cap
    ├── test_delegation.py       # timeout + retry + fallback
    └── test_supervisor.py       # compile_state_graph builds expected edges

backend/app/agents/graphs/
└── error_coach.py       # UPDATED — uses a2a.Supervisor to route hint_ladder vs recommendation

backend/app/agents/nodes/error_coach/
├── recommendation.py    # NEW — RecommendationAgent: query_error_question similar-question lookup
└── (existing 4 nodes: fetch_question, hint_ladder, evaluate, loop_or_finish)

backend/migrations/versions/
└── 0021_a2a_messages.py # a2a_messages table (no RLS, indexed on trace_id)

backend/tests/
├── unit/
│   ├── test_a2a_schemas.py
│   ├── test_a2a_routing.py
│   ├── test_a2a_delegation.py
│   └── test_a2a_supervisor.py
└── integration/
    └── test_error_coach_a2a_split.py   # MockLLMClient, assert both agents called
```

**Structure Decision**: Single new self-contained library at
`backend/app/agents/a2a/`, mirroring the `agent_memory` 028 / `irt` 030
"library-first" pattern. One additive change to `error_coach.py` (route
between the existing `hint_ladder` node and a new `recommendation` node
via the Supervisor). All routing math lives in `routing.py` and
`delegation.py` (no DB / LangGraph-direct imports in the schema layer)
so the routing layer is unit-testable without infrastructure.

## A2A Framework — API Sketch

```python
# Pure types (no DB, no LangGraph)
from app.agents.a2a import (
    AgentDefinition,    # name, role, input_schema, output_schema, timeout
    A2AMessage,         # from, to, task, context, expected_output, status, trace_id
    DelegationRecord,   # parent, child, task, result, duration, status, retry_count
    RoutingDecision,    # next_agent: str | None, reason: str, depth: int
)

# Supervisor — the load-bearing builder
from app.agents.a2a import Supervisor, SupervisorConfig

config = SupervisorConfig(
    agents=[
        AgentDefinition(
            name="hint_ladder",
            role="提供渐进式提示",
            input_schema=HintLadderInput,
            output_schema=HintLadderOutput,
            timeout_seconds=10.0,
        ),
        AgentDefinition(
            name="recommendation",
            role="推荐类似题目",
            input_schema=RecommendationInput,
            output_schema=RecommendationOutput,
            timeout_seconds=15.0,
        ),
    ],
    routing_fn=_route_after_hint,           # Callable[[State], RoutingDecision]
    default_timeout_seconds=30.0,
    max_delegation_depth=3,
    enable_cycle_detection=True,
)

supervisor = Supervisor(config)
graph = await supervisor.compile_state_graph(ErrorCoachState)
```

The `Supervisor.compile_state_graph(state_cls)` returns a compiled
`StateGraph` with one node per `AgentDefinition` plus a hidden
`__supervisor_router__` node that owns the `add_conditional_edges`
mapping. The router calls `routing_fn(state)` to decide which agent to
visit next, with cycle detection + depth enforcement applied before
the agent is invoked. Timeouts are enforced via `asyncio.wait_for`
around the agent's node call.

## Data Model

### `a2a_messages`

| Column | Type | Notes |
|---|---|---|
| id | UUID v7 | PK |
| trace_id | TEXT | OTel trace_id (or request_id fallback) for cross-graph correlation |
| thread_id | TEXT | LangGraph thread_id (so per-session filter is possible) |
| parent_agent | TEXT | Source agent name (or `"__supervisor__"`) |
| child_agent | TEXT | Target agent name |
| task | TEXT | Short description of the delegated subtask |
| context_jsonb | JSONB | Frozen snapshot of the relevant state slice at delegation time |
| expected_output_jsonb | JSONB | Pydantic schema name + sample for output validation |
| status | TEXT | `pending` / `success` / `failed` / `timeout` |
| result_jsonb | JSONB | Agent output on success (NULL until completion) |
| error_reason | TEXT | Error message on `failed` / `timeout` |
| retry_count | INT | Number of retries before final status (0–1 in US1) |
| duration_ms | INT | Wall-clock from delegation start to terminal status |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

Constraints:
- CHECK `status IN ('pending','success','failed','timeout')`
- CHECK `retry_count >= 0 AND retry_count <= 5`
- CHECK `duration_ms >= 0`
- RLS: **disabled** — messages are scoped by `trace_id` + `thread_id`,
  not by user; debugging requires querying across users within one
  trace. Mirrors 025 `interview_plan` JSONB precedent.
- Indexes: `idx_a2a_messages_trace_id` (trace_id), `idx_a2a_messages_thread_id` (thread_id),
  `idx_a2a_messages_status_created_at` (status, created_at).

No FK to `users` because debug cross-user queries are required; the
service layer is responsible for sanitizing any user-derived text.

## API Contracts

See `contracts/a2a-api.md` for full signatures. Public surface:

```python
# Pure types
from app.agents.a2a import (
    AgentDefinition, A2AMessage, DelegationRecord,
    RoutingDecision, SupervisorConfig,
)

# Supervisor + delegation runner
from app.agents.a2a import Supervisor, DelegationRunner

# Repository (DB-coupled, used by graph + scripts)
from app.agents.a2a.repository import A2AMessageRepository
```

## Scope Decision — Why US1 + US2 Only

The full 4-US implementation requires:

- US3: resume_optimize split (JD-analysis + rewrite agents) — touches
  resume_optimize graph and the recommendation_rewrite prompt surface
  (L004 quota risk).
- US4: 025 interview graph migration to the new framework + standard
  message protocol — **025 is in the dirty working tree** (per the
  REQ-MERGE-02 cycle), refactoring it now would create merge conflicts
  with the 025 work that hasn't been committed. Defer to US4.
- Full Command API utilization: a `Command(goto=..., update=...)`
  routing variant — useful but additive; the supervisor uses
  `add_conditional_edges` for US1 to avoid the LangGraph Command
  signature drift risk.
- Full fallback chain (retry + circuit breaker + user-facing error) —
  US1 ships retry-once + log-on-failure. Circuit breaker + user-facing
  error are ⏳ until US3 demonstrates real failure modes.

US1 + US2 deliver:

1. Reusable A2A framework (the load-bearing foundation).
2. error_coach split (the first real application, validates
   generalizability per SC-001).

US3 + US4 plug into the framework without modifying its core.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected |
|---|---|---|
| New `a2a/` library at `backend/app/agents/a2a/` | US1 establishes the foundation; US3/US4 need a stable library surface | Putting A2A under `interview/` couples it to the interview agent; US2/US3 need library access from error_coach + resume_optimize. |
| `a2a_messages` table without RLS | Debug queries must span users within one trace | RLS would force debuggers to know which user started the trace; spec FR-017 implies cross-user debug visibility. |
| Retry-once only (no circuit breaker) in US1 | L004 quota risk — full circuit breaker risks burning tokens on dev runs | Retry-once + structured log is the smallest defensible default. Circuit breaker ⏳. |

## Migration Plan

`0021_a2a_messages.py` (depends on `0020_irt_item_bank`):

- Creates `a2a_messages` table with CHECK constraints on status /
  retry_count / duration_ms.
- Indexes on `trace_id`, `thread_id`, and `(status, created_at)`.
- Downgrade drops the table.
- Forward-only; safe to merge behind a feature flag.

## Open Questions / Decisions Deferred

1. **Command API vs. add_conditional_edges**: US1 uses
   `add_conditional_edges`. Migrating to `Command(goto, update)`
   happens in US4 alongside the 025 interview graph migration.
2. **Cross-graph agent interop (e.g. error_coach invoking an interview
   agent)**: Deferred. US2 ships single-graph delegation only.
3. **Circuit breaker + user-facing error fallback**: Deferred to US3.
4. **Agent input/output schema enforcement**: US1 declares the schema
   in `AgentDefinition` and validates at the delegation boundary
   (Pydantic `model_validate`). The full schema validator
   (deep equality, recursive type check) is ⏳.