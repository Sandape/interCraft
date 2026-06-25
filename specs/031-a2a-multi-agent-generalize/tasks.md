# Tasks: REQ-031 A2A Multi-Agent Generalization

**Input**: Design documents from `specs/031-a2a-multi-agent-generalize/`
(plan.md, spec.md, contracts/a2a-api.md).

**Scope**: US1 (reusable A2A framework) + US2 (error_coach split into
HintLadderAgent + RecommendationAgent). US3 (resume_optimize split),
US4 (025 interview migration + standard message protocol), full LangGraph
Command API utilization, full fallback chain (retry + circuit breaker +
user-facing error), and cross-graph agent interop are listed but **⏳
deferred** — see "Phase N+ Deferrals" at the end.

**Constitution gates**: Library-First (self-contained `app/agents/a2a/`),
Test-First (routing/cycle/timeout tests before implementation),
CLI Interface (`python -m app.agents.a2a.cli`), Observability
(structlog events: routing decision, delegation started/succeeded/failed/
timeout/cycle_detected/depth_exceeded).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2)
- File paths absolute from `D:\Project\eGGG\`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Library skeleton + test scaffolding.

- [ ] T001 [US1] Create A2A library directory + `__init__.py` at `D:\Project\eGGG\backend\app\agents\a2a\__init__.py` with re-exports of `AgentDefinition`, `A2AMessage`, `Supervisor`, `SupervisorConfig`, `RoutingDecision`, `DelegationRecord`, `DelegationRunner`, `A2AMessageRepository`
- [ ] T002 [P] [US1] Create A2A `tests/` package + `__init__.py` at `D:\Project\eGGG\backend\app\agents\a2a\tests\__init__.py`
- [ ] T003 [US1] Create empty stub files for: `schemas.py`, `routing.py`, `supervisor.py`, `delegation.py`, `repository.py`, `models.py`, `cli.py`, `README.md` — at the paths listed in plan.md Project Structure

**Checkpoint**: Library skeleton present; public API surface declared in `__init__.py`.

## Phase 2: Foundational (Framework Core + Storage)

**Purpose**: Core framework (schemas + routing + supervisor + delegation +
persistence) and storage layer (Alembic migration + SQLAlchemy model).
**Blocks all US1 implementation.**

**⚠️ CRITICAL**: No US1 task can start until Phase 2 is complete.

- [ ] T004 [US1] Implement Pydantic schemas at `D:\Project\eGGG\backend\app\agents\a2a\schemas.py`:
  - `AgentDefinition` (name, role, input_schema, output_schema, timeout_seconds)
  - `A2AMessage` (id, trace_id, thread_id, parent_agent, child_agent, task, context, expected_output, status, result, error_reason, retry_count, duration_ms, created_at, updated_at)
  - `DelegationRecord` (parent, child, task, result, duration_ms, status, retry_count)
  - `RoutingDecision` (next_agent: str | None, reason: str, depth: int)
  - `SupervisorConfig` (agents: list[AgentDefinition], routing_fn, default_timeout_seconds=30.0, max_delegation_depth=3, enable_cycle_detection=True)
  - Status enum: `pending` / `success` / `failed` / `timeout`
- [ ] T005 [P] [US1] Create Alembic migration `0021_a2a_messages.py` at `D:\Project\eGGG\backend\migrations\versions\0021_a2a_messages.py`:
  - `a2a_messages` table (no RLS — debug cross-user)
  - CHECK constraints on status / retry_count / duration_ms
  - Indexes: `idx_a2a_messages_trace_id`, `idx_a2a_messages_thread_id`, `idx_a2a_messages_status_created_at`
  - Forward + downgrade migrations
- [ ] T006 [US1] Implement SQLAlchemy model at `D:\Project\eGGG\backend\app\agents\a2a\models.py`:
  - `A2AMessage` ORM mapping the migration columns (mirror `agent_memory` 028 pattern)
- [ ] T007 [US1] Implement `repository.py` at `D:\Project\eGGG\backend\app\agents\a2a\repository.py`:
  - `A2AMessageRepository(session)` with `create(message)`, `update_status(id, status, result=None, error=None, duration_ms=None)`, `list_for_thread(thread_id, limit=50)`, `list_for_trace(trace_id, limit=200)`
  - Uses existing `get_session_factory()` + `set_user_context` (no RLS, but session is still bound)
- [ ] T008 [US1] Implement `routing.py` at `D:\Project\eGGG\backend\app\agents\a2a\routing.py`:
  - `check_cycle(visited: list[str], next_agent: str) -> bool` — raises `CycleDetectedError` on repeat
  - `enforce_depth(depth: int, max_depth: int) -> None` — raises `DepthExceededError` when `depth >= max_depth`
  - `decide(state, agents, visited, depth, routing_fn, config) -> RoutingDecision` — applies cycle + depth checks before returning the routing function's decision
  - Errors are typed and carry context (parent_agent, child_agent, depth) for log attrs

**Checkpoint**: Migration applies cleanly; ORM model importable; routing math unit-testable (no infrastructure).

## Phase 3: User Story 1 - Reusable A2A Orchestration Framework (Priority: P1) 🎯 MVP

**Goal**: Self-contained library that compiles a LangGraph `StateGraph`
from a list of `AgentDefinition` + a routing function, with timeout,
depth cap, cycle detection, and `A2AMessage` persistence.

**Independent Test**: Given a Supervisor with 3 agents (A, B, C), the
compiled `StateGraph` has 3 nodes + 1 hidden router node; a routing
function that returns A → B → C → END produces the expected execution
order; visiting A twice raises `CycleDetectedError`; depth > 3 raises
`DepthExceededError`.

### Tests for User Story 1 (Test-First per Constitution III)

> **NOTE: Written FIRST, verified FAIL before implementation**

- [ ] T009 [P] [US1] Unit tests for schemas at `D:\Project\eGGG\backend\tests\unit\test_a2a_schemas.py`:
  - `test_agent_definition_requires_name` — empty name rejected
  - `test_a2a_message_status_enum_validated` — invalid status string rejected
  - `test_supervisor_config_defaults` — default_timeout_seconds=30, max_delegation_depth=3
  - `test_routing_decision_next_agent_optional` — `next_agent=None` means END
  - `test_delegation_record_status_enum` — same as A2AMessage
- [ ] T010 [P] [US1] Unit tests for routing at `D:\Project\eGGG\backend\tests\unit\test_a2a_routing.py`:
  - `test_check_cycle_detects_repeat` — visited=[A,B,A] raises CycleDetectedError
  - `test_check_cycle_allows_unique` — visited=[A,B,C] does not raise
  - `test_enforce_depth_under_max_ok` — depth=2, max=3 → no raise
  - `test_enforce_depth_at_max_raises` — depth=3, max=3 → raises DepthExceededError
  - `test_decide_invokes_routing_fn` — routing_fn returns "B" → RoutingDecision(next_agent="B", depth=1)
  - `test_decide_passes_cycle_and_depth_checks` — repeat in visited raises before fn result is consumed
- [ ] T011 [P] [US1] Unit tests for delegation runner at `D:\Project\eGGG\backend\tests\unit\test_a2a_delegation.py`:
  - `test_delegation_success_persists_message` — async fn returns dict → status=success
  - `test_delegation_timeout_raises_timeout_error` — async fn sleeps > timeout → TimeoutError, status=timeout
  - `test_delegation_failure_persists_error` — async fn raises → status=failed, error_reason set
  - `test_delegation_retry_once_on_failure` — first call raises, second call succeeds → retry_count=1
  - `test_delegation_no_retry_on_timeout` — TimeoutError → retry_count=0 (retrying won't help)
  - `test_delegation_passes_trace_id` — DelegationRecord carries the supplied trace_id

### Implementation for User Story 1

- [ ] T012 [US1] Implement `delegation.py` at `D:\Project\eGGG\backend\app\agents\a2a\delegation.py`:
  - `DelegationRunner` class with `run(parent, child, task, context, expected_output, agent_fn, *, timeout_seconds, trace_id, thread_id, repository=None) -> DelegationRecord`
  - Uses `asyncio.wait_for(agent_fn(context), timeout=timeout_seconds)` for timeout
  - Retry once on non-timeout exception, then escalate to `status="failed"` with `error_reason`
  - Persists via `A2AMessageRepository` when supplied (no-op when `repository=None` for pure unit tests)
  - structlog events: `a2a.delegation_started`, `a2a.delegation_succeeded`, `a2a.delegation_failed`, `a2a.delegation_timeout`
- [ ] T013 [US1] Implement `supervisor.py` at `D:\Project\eGGG\backend\app\agents\a2a\supervisor.py`:
  - `Supervisor` class wrapping `SupervisorConfig`
  - `compile_state_graph(state_cls) -> StateGraph` — adds one node per agent, plus a hidden `__supervisor_router__` node that owns `add_conditional_edges`
  - `__supervisor_router__` reads routing decision from state, applies cycle + depth checks, then returns the next agent name (or `END`)
  - Each agent node is wrapped to call the agent's underlying async fn via `DelegationRunner` so timeouts and persistence apply uniformly
- [ ] T014 [US1] Implement `cli.py` at `D:\Project\eGGG\backend\app\agents\a2a\cli.py`:
  - `python -m app.agents.a2a.cli --agents agents.json` reads JSON list of `{name, role, timeout_seconds}` declarations
  - Outputs the graph node + edge list to stdout, exits 0 on success
  - `--check-only` validates routing function + cycle detection without compiling the graph
  - Missing agent / unknown routing target → exit 1 with structured error
- [ ] T015 [US1] Add README at `D:\Project\eGGG\backend\app\agents\a2a\README.md`:
  - Section 1: Quickstart — declare 3 agents + routing fn, compile graph, run ainvoke
  - Section 2: A2AMessage schema + status enum + persistence
  - Section 3: Timeout + cycle detection + depth cap semantics
  - Section 4: error_coach example (US2 reference)
  - Section 5: CLI usage examples
- [ ] T016 [US1] Run schema + routing + delegation unit tests; verify all pass at `D:\Project\eGGG\backend\tests\unit\test_a2a_*.py`

**Checkpoint**: Library is self-contained, has a public API, unit tests
pass. The CLI accepts a JSON agent declaration and prints graph info.

## Phase 4: User Story 2 - Error Coach Splits Into Hint-Ladder + Recommendation Agents (Priority: P2)

**Goal**: Refactor `error_coach` graph to use the new framework with two
agents: `HintLadderAgent` (existing hint_ladder logic) and
`RecommendationAgent` (new — propose similar questions when the user is
stuck). The 3-correct flow remains unchanged for backward compat.

**Independent Test**: A user stuck on Q1 (3 failed attempts) running
through `error_coach` triggers `RecommendationAgent` and surfaces ≥1
similar question alongside the hint output. The existing
`test_error_coach_three_correct_flow` continues to pass without
modification.

### Tests for User Story 2 (Test-First)

> **NOTE: Written FIRST, verified FAIL before refactor**

- [ ] T017 [P] [US2] Unit tests for RecommendationAgent at `D:\Project\eGGG\backend\tests\unit\test_a2a_recommendation_agent.py`:
  - `test_recommendation_filters_already_solved` — input includes an already-solved question_id; output excludes it
  - `test_recommendation_returns_empty_when_no_matches` — no similar questions in DB; output is empty list
  - `test_recommendation_handles_empty_question_text` — gracefully handles missing question_text
  - `test_recommendation_respects_max_items` — request ≥3, repository returns 5, output ≤ 3
- [ ] T018 [US2] Integration test at `D:\Project\eGGG\backend\tests\integration\test_error_coach_a2a_split.py`:
  - Scenario: 3 failed attempts → recommendation node invoked
  - Setup: register user, create 3 error questions (Q1 + 2 similar), use MockLLMClient with scenario file returning `evaluate_scores=[3, 3, 3]` (all incorrect)
  - Assert: `recommendation_agent` was called ≥1 time (via `a2a_messages.status='success'` filter on trace_id)
  - Assert: state contains `recommendations: list[dict]` with ≥1 entry
  - Assert: existing `test_error_coach_three_correct_flow` continues to pass with the new graph (run it as a sub-test)

### Implementation for User Story 2

- [ ] T019 [US2] Implement `RecommendationAgent` at `D:\Project\eGGG\backend\app\agents\nodes\error_coach\recommendation.py`:
  - `recommendation_node(state: ErrorCoachState) -> dict` — wraps the existing `query_error_question_by_id` to find the source question, then queries `error_questions` for other questions with the same `dimension` (excluding the current one and any with `status='mastered'`)
  - Limit to 3 recommendations; ordered by `frequency DESC, created_at DESC`
  - Returns `{"recommendations": [{"id": ..., "question_text": ..., "dimension": ...}, ...]}`
  - On empty result: returns `{"recommendations": []}` — never raises
- [ ] T020 [US2] Refactor `error_coach.py` at `D:\Project\eGGG\backend\app\agents\graphs\error_coach.py`:
  - Build `AgentDefinition` list: `hint_ladder` (existing logic) + `recommendation` (new node)
  - Routing function: `_route_after_hint_ladder(state)` returns `recommendation` when `attempt_count >= 3` and `correct_count == 0`, else `END`
  - Compile via `Supervisor(...).compile_state_graph(ErrorCoachState)`
  - **Preserve existing `retry_graph_op` calls** for `ainvoke` / `aget_state` / `aupdate_state` (L001 checkpointer pattern)
  - **Preserve `interrupt_after=["hint_ladder"]`** so the existing pause-resume flow continues to work
  - **Preserve existing `submit_answer` / `abort` / `get_state` / `start` public API** so existing E2E tests pass without changes
- [ ] T021 [US2] Update `ErrorCoachState` at `D:\Project\eGGG\backend\app\agents\state\error_coach_state.py`:
  - Add `recommendations: list[dict[str, Any]]` field (default `[]`)
- [ ] T022 [US2] Run integration test suite for error_coach at `D:\Project\eGGG\backend\tests\integration\test_error_coach.py` + `test_error_coach_a2a_split.py`:
  - Existing `test_error_coach_three_correct_flow` passes without modification (US2 SC-002: 5-correct flow regression-free)
  - `test_recommendation_invoked_after_three_failed_attempts` passes (US2 SC-003: recommendation agent called when stuck)

**Checkpoint**: error_coach uses the new framework; HintLadderAgent +
RecommendationAgent both exercised; existing 5-correct flow continues
to work.

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, lint cleanup, and end-to-end smoke.

- [ ] T023 [P] [US1] Run `mypy backend/app/agents/a2a/ --strict` and resolve any new errors (existing pre-existing errors in adjacent modules ⏳ deferred)
- [ ] T024 [P] [US1] Run `ruff check --fix backend/app/agents/a2a/ backend/app/agents/nodes/error_coach/recommendation.py backend/tests/unit/test_a2a_*.py backend/tests/integration/test_error_coach_a2a_split.py`
- [ ] T025 [US1] Update `specs/README.md` to mark 031 as `in_progress` with US1+US2 done, US3+US4 ⏳
- [ ] T026 [US1] Run full backend test suite `cd backend && uv run pytest -q` and confirm no regression (baseline: 637 passing)

---

## Phase N+ Deferrals (⏳ Future Iterations)

The following are **listed in spec.md but NOT implemented in this cycle**:

### US3 — Resume Optimize Splits Into JD-Analysis + Rewrite Agents (Priority: P2) ⏳

- [ ] ⏳ T101 [US3] Refactor `backend/app/agents/graphs/resume_optimize.py` to use the new framework
- [ ] ⏳ T102 [US3] Implement `JDAnalysisAgent` — extract requirements/themes/keywords from JD
- [ ] ⏳ T103 [US3] Implement `RewriteAgent` — produce block suggestions referencing JD analysis
- [ ] ⏳ T104 [US3] Integration test: rewrite suggestions reference JD analysis in trace

### US4 — Standardized A2A Message Protocol + 025 Interview Migration (Priority: P3) ⏳

- [ ] ⏳ T201 [US4] Migrate `backend/app/agents/interview/graph.py` to use the new framework (deferred — 025 is in the dirty working tree per the REQ-MERGE-02 cycle)
- [ ] ⏳ T202 [US4] Adopt `Command(goto=..., update=...)` API instead of `add_conditional_edges` (L004 Command signature drift risk)
- [ ] ⏳ T203 [US4] Implement full fallback chain: retry + circuit breaker + user-facing error
- [ ] ⏳ T204 [US4] Cross-graph agent interop (e.g. error_coach calling into an interview agent)
- [ ] ⏳ T205 [US4] Schema validator: deep equality + recursive type check for `AgentDefinition.input_schema` / `output_schema`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS US1.
- **US1 (Phase 3)**: Depends on Foundational completion.
- **US2 (Phase 4)**: Depends on US1 completion (the framework must exist before error_coach can use it).
- **Polish (Phase 5)**: Depends on US1 + US2 completion.

### Within Each User Story

- Tests (T009–T011, T017–T018) written FIRST, verified FAIL before implementation.
- Schemas (T004) before routing (T008) before supervisor (T013).
- Migration (T005) before model (T006) before repository (T007).
- Recommendation agent (T019) before error_coach refactor (T020).

### Parallel Opportunities

- Phase 1 tasks T002 + T003 can run in parallel with T001.
- Phase 3 test tasks T009 + T010 + T011 can run in parallel.
- Phase 4 test tasks T017 + T018 can run in parallel.
- Phase 5 lint tasks T023 + T024 can run in parallel.

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: US1 — framework + tests + CLI + README.
4. **STOP and VALIDATE**: Run US1 unit tests independently.
5. (Optional) Deploy/demo the framework.

### Incremental Delivery

1. Setup + Foundational → Library skeleton + migration + repository.
2. US1 → Reusable framework + CLI + README.
3. US2 → error_coach split, validates generalizability.
4. Polish → Lint, type check, full regression run.

### Scope Discipline (L004 mitigation)

- US3 + US4 are **explicitly listed but ⏳ deferred**. Resist scope creep.
- If framework implementation stalls, drop US2 to keep US1 as the deliverable.
- If US2 stalls after US1 ships, ship US1 + tasks.md + ⏳ markers.