"""REQ-041-P0-APPROVAL — Test-First red phase for the run-time approval gate.

Covers 8 paths required by AC-6.1 / AC-6.2 (and AC-1.2 / AC-1.3 / AC-1.3a /
AC-2.1 / AC-2.2 / AC-3.1 / AC-4.1 / AC-4.2):

(a) test_approve_readonly — tavily_search approved without state consult
(b) test_deny_mark_complete — MarkComplete denied when no approval context
(c) test_approve_mark_complete_with_state — MarkComplete approved when approved_tools present
(d) test_runtime_blocks_mark_complete — _approval_runtime raises ToolApprovalDenied,
    underlying MarkComplete.func never called (AC-3.1)
(e) test_node_error_category_round_trip — NodeError(category='tool_approval_denied')
    round-trips through serialize_state_error
(f) test_enforce_false_backcompat — bind_tools_with_approval(..., enforce=False)
    is byte-equivalent to llm.bind_tools
(g) test_enforce_approval_deterministic — same input => same output over 10 calls
(h) test_bind_tools_with_approval_callable — wraps a MockLLMClient without raising

Plus 2 wiring tests:
(i) test_cross_agent_wiring — 5 graph files all import bind_tools_with_approval
(j) test_classify_exception_approval_missing — classify_exception maps
    RuntimeError('approval_missing:MarkComplete') -> 'tool_approval_denied'
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# (a) AC-1.2: read-only tools approved without consulting state
# ---------------------------------------------------------------------------
def test_approve_readonly() -> None:
    """AC-1.2: tavily_search (read-only, no approval) is approved on empty state,
    deterministically (10 successive calls return identical tuples)."""
    from app.agents.tools.approval import _enforce_approval
    from app.agents.tools.spec import ToolSpec

    spec = ToolSpec(
        name="tavily_search",
        args_schema={"queries": "list[str]"},
        side_effects=["read", "external_api"],
        requires_approval=False,
    )
    tool_call = {"id": "tc-1", "name": "tavily_search", "args": {"queries": ["q"]}}
    state: dict[str, Any] = {}

    # Deterministic: 10 successive calls return identical tuples.
    results = [_enforce_approval(tool_call, spec, state) for _ in range(10)]
    assert results[0] == (True, "no_approval_required")
    assert all(r == (True, "no_approval_required") for r in results)


# ---------------------------------------------------------------------------
# (b) AC-1.3: MarkComplete denied without approval context
# ---------------------------------------------------------------------------
def test_deny_mark_complete() -> None:
    """AC-1.3: MarkComplete denied when state has no approval token / approved_tools.
    Deny reason MUST be 'approval_missing:MarkComplete' (prefix format locked)."""
    from app.agents.tools.approval import _enforce_approval
    from app.agents.tools.spec import ToolSpec

    spec = ToolSpec(
        name="MarkComplete",
        args_schema={"reason": "str"},
        side_effects=["ws_push"],
        requires_approval=True,
    )
    tool_call = {"id": "tc-mc", "name": "MarkComplete", "args": {"reason": "done"}}

    denied, reason = _enforce_approval(tool_call, spec, {})
    assert denied is False
    assert reason == "approval_missing:MarkComplete"
    assert reason.startswith("approval_missing:")


# ---------------------------------------------------------------------------
# (c) MarkComplete approved when state contains approved_tools
# ---------------------------------------------------------------------------
def test_approve_mark_complete_with_state() -> None:
    """MarkComplete approved when state['approved_tools'] is a list containing it."""
    from app.agents.tools.approval import _enforce_approval
    from app.agents.tools.spec import ToolSpec

    spec = ToolSpec(
        name="MarkComplete",
        args_schema={"reason": "str"},
        side_effects=["ws_push"],
        requires_approval=True,
    )
    tool_call = {"id": "tc-mc-2", "name": "MarkComplete", "args": {"reason": "ok"}}

    state = {"approved_tools": ["MarkComplete"]}
    approved, reason = _enforce_approval(tool_call, spec, state)
    assert approved is True
    assert reason == "approved_via_state"


# ---------------------------------------------------------------------------
# (d) AC-3.1: _approval_runtime blocks MarkComplete, underlying func NOT called
# ---------------------------------------------------------------------------
def test_runtime_blocks_mark_complete() -> None:
    """AC-3.1: _approval_runtime raises ToolApprovalDenied before MarkComplete runs.
    Verified by spy on MarkComplete.coroutine asserting it was never called."""
    from langchain_core.messages import ToolMessage

    from app.agents.tools.approval import (
        ToolApprovalDenied,
        _approval_runtime,
    )
    from app.agents.tools import TOOL_REGISTRY, MarkComplete

    # Spy on the underlying async callable. For ``@tool``-decorated async
    # functions, LangChain exposes the coroutine via ``StructuredTool.coroutine``
    # (not ``.func``).
    original_coroutine = MarkComplete.coroutine
    invocations: list[tuple] = []

    async def spy_func(*args: Any, **kwargs: Any) -> str:
        invocations.append((args, kwargs))
        return "INVOKED"

    MarkComplete.coroutine = spy_func  # type: ignore[assignment]
    try:
        tool_calls = [
            {"id": "tc-block-1", "name": "MarkComplete", "args": {"reason": "done"}},
        ]
        state: dict[str, Any] = {}  # no approval token

        with pytest.raises(ToolApprovalDenied):
            _approval_runtime(
                tool_calls,
                state,
                TOOL_REGISTRY,
                node_name="<test>",
            )

        # Underlying callable SHALL NOT execute.
        assert invocations == [], (
            f"MarkComplete.coroutine was invoked: {invocations}; the gate must "
            "block before reaching the underlying callable."
        )
    finally:
        MarkComplete.coroutine = original_coroutine  # type: ignore[assignment]

    # Returned ToolMessage (when approved) ties tool_call_id to callable result.
    state_approved = {"approved_tools": ["MarkComplete"]}
    msg = _approval_runtime(
        [{"id": "tc-approve-1", "name": "MarkComplete", "args": {"reason": "ok"}}],
        state_approved,
        TOOL_REGISTRY,
        node_name="<test>",
    )
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "tc-approve-1"
    assert "complete" in msg.content


# ---------------------------------------------------------------------------
# (e) AC-4.1: NodeError(category='tool_approval_denied') round-trips via
#     serialize_state_error
# ---------------------------------------------------------------------------
def test_node_error_category_round_trip() -> None:
    """AC-4.1: NodeError with category='tool_approval_denied' serializes to API
    payload with error_category='tool_approval_denied'."""
    from app.agents.utils.node_error import NodeError, serialize_state_error

    err = NodeError(
        category="tool_approval_denied",
        node_name="evaluate",
        cause="approval_missing:MarkComplete",
        retry_after=None,
        timestamp="2026-07-05T00:00:00+00:00",
    )

    payload = serialize_state_error(err)
    assert payload["error_category"] == "tool_approval_denied"
    assert payload["node_name"] == "evaluate"
    assert payload["cause"] == "approval_missing:MarkComplete"


# ---------------------------------------------------------------------------
# (f) AC-2.2: enforce=False must be byte-equivalent to plain llm.bind_tools
# ---------------------------------------------------------------------------
def test_enforce_false_backcompat() -> None:
    """AC-2.2: bind_tools_with_approval(llm, tools, enforce=False) MUST return the
    same object that llm.bind_tools(tools) returns. tools list MUST NOT be mutated."""
    from app.agents.tools.approval import bind_tools_with_approval

    sentinel = object()

    class FakeLLM:
        def bind_tools(self, tool_list):
            # Return a sentinel for identity verification.
            return sentinel

    tools = [MagicMock(name="tavily"), MagicMock(name="think")]
    tools_before = list(tools)
    out = bind_tools_with_approval(FakeLLM(), tools, enforce=False)  # type: ignore[arg-type]
    assert out is sentinel, "enforce=False MUST delegate verbatim to llm.bind_tools"

    # No mutation of the input list (NAC-3).
    assert tools == tools_before, "tools list was mutated by bind_tools_with_approval"


# ---------------------------------------------------------------------------
# (g) AC-1.2 determinism: 10 successive calls return identical tuples
# ---------------------------------------------------------------------------
def test_enforce_approval_deterministic() -> None:
    """AC-1.2 / AC-6.1(g): _enforce_approval is deterministic — 10 successive calls
    on the same input return identical tuples."""
    from app.agents.tools.approval import _enforce_approval
    from app.agents.tools.spec import ToolSpec

    spec = ToolSpec(
        name="tavily_search",
        args_schema={"queries": "list[str]"},
        side_effects=["read", "external_api"],
        requires_approval=False,
    )
    tool_call = {"id": "x", "name": "tavily_search", "args": {}}
    results = [_enforce_approval(tool_call, spec, {}) for _ in range(10)]
    # All identical
    assert len({tuple(r) for r in results}) == 1


# ---------------------------------------------------------------------------
# (h) AC-2.1 + AC-6.1(h): bind_tools_with_approval callable against llm_client_mock
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bind_tools_with_approval_callable() -> None:
    """AC-2.1: bind_tools_with_approval(llm, tools) returns an object whose
    .ainvoke and .invoke both succeed against a frontier-LLM-shaped binding."""
    from langchain_core.messages import AIMessage

    from app.agents.tools.approval import bind_tools_with_approval
    from app.agents.tools import MarkComplete, tavily_search

    class _FrontierShapedMock:
        """Mock LLM exposing both ``bind_tools`` (returns ``self``) and
        ``ainvoke`` (returns an AIMessage with planned tool calls). Mirrors
        ``llm_client_mock.MockLLMClient`` so the gate's wrapping is verified
        end-to-end without touching the production client.
        """

        def __init__(self) -> None:
            self.tool_calls: list[dict[str, Any]] = []
            self.invocations: list[str] = []

        def bind_tools(self, tools):
            self.invocations.append("bind_tools")
            self._bound_tools = list(tools)
            return self

        async def ainvoke(self, *args, **kwargs):
            self.invocations.append("ainvoke")
            return AIMessage(
                content="",
                tool_calls=list(self.tool_calls),
            )

    mock = _FrontierShapedMock()
    mock.tool_calls = [
        {"id": "tc-1", "name": "tavily_search", "args": {"queries": ["q"]}},
    ]
    wrapped = bind_tools_with_approval(mock, [tavily_search, MarkComplete])

    # bind_tools_with_approval delegates to llm.bind_tools — verify by record.
    assert "bind_tools" in mock.invocations
    assert wrapped is mock, (
        "bind_tools_with_approval should delegate to llm.bind_tools and return "
        "the same object the LLM surfaced (AC-2.1)."
    )

    # .ainvoke succeeds and returns an AIMessage with the planned tool call.
    msg = await wrapped.ainvoke(
        messages=[],
        user_id="u",
        thread_id="t",
        node_name="planner_search",
    )
    assert isinstance(msg, AIMessage)
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0]["name"] == "tavily_search"
    assert msg.tool_calls[0]["id"] == "tc-1"


# ---------------------------------------------------------------------------
# (i) AC-5.1 + AC-5.2: cross-agent wiring covers all 5 agent graphs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "wiring_file",
    [
        "backend/app/agents/interview/planner_graph.py",
        "backend/app/agents/nodes/error_coach/evaluate.py",
        "backend/app/agents/nodes/resume_optimize/diff_jd.py",
        "backend/app/agents/nodes/ability_diagnose/generate_insight.py",
        "backend/app/agents/nodes/general_coach/intent.py",
    ],
)
def test_cross_agent_wiring(wiring_file: str) -> None:
    """AC-5.1 / AC-5.2: each of the 5 wiring target files MUST contain both an
    import of bind_tools_with_approval AND at least one bind_tools_with_approval(
    invocation. Static + parametrised check."""
    from pathlib import Path

    repo_root = Path(_REPO_ROOT)
    fpath = repo_root / wiring_file
    assert fpath.exists(), f"wiring target missing: {fpath}"

    # import presence: at least 1 match for the symbol
    text = fpath.read_text(encoding="utf-8")
    assert "bind_tools_with_approval" in text, (
        f"{wiring_file} must import bind_tools_with_approval"
    )
    # at least 1 invocation site (not just import)
    invocations = text.count("bind_tools_with_approval(")
    assert invocations >= 1, (
        f"{wiring_file} must have a bind_tools_with_approval() call site "
        f"(found {invocations})"
    )


# Wiring test reads fixture files relative to repo root, which is 4 parents
# above this module: <repo>/backend/app/agents/tests/test_approval_gate.py
_REPO_ROOT = str(Path(__file__).resolve().parents[4])


# ---------------------------------------------------------------------------
# (j) AC-1.3a: classify_exception maps approval_missing:ToolName -> tool_approval_denied
# ---------------------------------------------------------------------------
def test_classify_exception_approval_missing() -> None:
    """AC-1.3a: classify_exception(RuntimeError('approval_missing:MarkComplete'))
    MUST map to NodeErrorCategory bucket 'tool_approval_denied'."""
    from app.agents.utils.node_error import (
        NodeError,
        classify_exception,
    )

    cat = classify_exception(RuntimeError("approval_missing:MarkComplete"))
    assert cat == "tool_approval_denied"

    # NodeError.from_exception round-trip
    err = NodeError.from_exception(
        RuntimeError("approval_missing:MarkComplete"),
        node_name="<test>",
    )
    assert err.category == "tool_approval_denied"
    assert "approval_missing:MarkComplete" in err.cause
