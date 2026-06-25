# A2A Multi-Agent Orchestration Library

**REQ-031 US1** — extracts the Supervisor + subgraph pattern from feature
025 (interview planner + interviewer) into a reusable library, then
applies it to `error_coach` (US2) so new multi-agent flows can be
added by declaration only — no Supervisor core changes.

## Quickstart

```python
from app.agents.a2a import (
    AgentDefinition,
    Supervisor,
    SupervisorConfig,
    RoutingDecision,
)


def hint_ladder_handler(ctx: dict, state: dict) -> dict:
    # Call existing hint_ladder node logic here.
    return {"hint": "..."}


def recommendation_handler(ctx: dict, state: dict) -> dict:
    # Call new RecommendationAgent logic.
    return {"recommendations": [...]}


def route_after_hint(state: dict) -> RoutingDecision:
    if state.get("attempt_count", 0) >= 3 and state.get("correct_count", 0) == 0:
        return RoutingDecision(next_agent="recommendation", reason="stuck")
    return RoutingDecision(next_agent=None, reason="continue")


config = SupervisorConfig(
    agents=[
        AgentDefinition(name="hint_ladder", role="提供渐进式提示"),
        AgentDefinition(name="recommendation", role="推荐类似题目"),
    ],
    routing_fn=route_after_hint,
    default_timeout_seconds=30.0,
    max_delegation_depth=3,
)

supervisor = Supervisor(config)
supervisor.register_handler("hint_ladder", hint_ladder_handler)
supervisor.register_handler("recommendation", recommendation_handler)

graph = supervisor.compile_state_graph(ErrorCoachState)
# Use graph.ainvoke(state, config) per standard LangGraph conventions.
```

## API Surface

| Symbol | Purpose |
|---|---|
| `AgentDefinition` | One agent's name, role, schema, timeout. |
| `A2AMessage` | Standardized inter-agent message envelope. |
| `DelegationRecord` | In-memory record returned by `DelegationRunner`. |
| `RoutingDecision` | Output of a routing function (`next_agent=None` → END). |
| `SupervisorConfig` | Full configuration: agents + routing fn + global knobs. |
| `Supervisor` | Compiles a `StateGraph` from the config + handlers. |
| `DelegationRunner` | Runs one delegation: timeout + retry + persistence. |
| `A2AMessageRepository` | DB persistence helper (audit log). |
| `CycleDetectedError` | Raised when an agent re-enters its ancestor path. |
| `DepthExceededError` | Raised when depth ≥ `max_delegation_depth`. |
| `AgentTimeoutError` | Raised by the runner on timeout (internal). |

## A2AMessage schema

```python
A2AMessage(
    trace_id="...",            # OTel trace_id (or request_id fallback)
    thread_id="...",           # LangGraph thread_id
    parent_agent="...",        # delegating agent name (or "__supervisor__")
    child_agent="...",         # target agent name
    task="...",                # short description of the subtask
    context={...},             # state slice passed to the agent
    expected_output={...},     # schema hint (used by US4 validator)
    status="pending|success|failed|timeout",
    result={...},              # agent output on success
    error_reason="...",        # error message on failed/timeout
    retry_count=0,             # 0..5
    duration_ms=123,           # wall-clock duration
)
```

Persisted to `a2a_messages` table (migration `0021_a2a_messages`).
RLS disabled — debug queries span users within one trace (FR-018).

## Timeout + Cycle + Depth

- **Timeout**: each agent has a per-agent `timeout_seconds`; the
  `DelegationRunner` uses `asyncio.wait_for(agent_fn(context),
  timeout=...)` so a hanging agent never blocks the graph.
- **Cycle detection**: enabled by default. The router tracks
  `a2a_visited: list[str]` in state; visiting an ancestor raises
  `CycleDetectedError` and the graph ends.
- **Depth cap**: `max_delegation_depth=3` by default. The router
  raises `DepthExceededError` when the next hop would exceed the cap.

## Failure handling

US1 ships retry-once for non-timeout failures:

1. First call → exception → retry once.
2. Retry → success → `status="success"`, `retry_count=1`.
3. Retry → timeout → `status="timeout"`, `error_reason="Timeout after
   retry: ..."`.
4. Retry → exception → `status="failed"`, `error_reason="<ExcType>: ..."`.

Timeouts are not retried (FR-008 rationale: same load probably
persists). Circuit breaker + user-facing error are ⏳ deferred to US3.

## CLI

```bash
python -m app.agents.a2a.cli --agents agents.json
python -m app.agents.a2a.cli --agents agents.json --check-only
```

`agents.json` schema:

```json
{
  "agents": [
    {"name": "hint_ladder", "role": "提供渐进式提示", "timeout_seconds": 10.0},
    {"name": "recommendation", "role": "推荐类似题目", "timeout_seconds": 15.0}
  ],
  "routing_rules": [
    {"from": "hint_ladder", "to": "recommendation", "when": "stuck"}
  ],
  "default_timeout_seconds": 30.0,
  "max_delegation_depth": 3
}
```

Exit codes: `0` = ok, `1` = validation error, `2` = usage error.

## error_coach example

The `error_coach` graph is the first consumer (US2). Its routing
function returns `"recommendation"` when `attempt_count >= 3 and
correct_count == 0`. The existing 3-correct flow is unchanged.

See `backend/app/agents/graphs/error_coach.py` for the production
wiring.