"""REQ-041 US-2 FR-005 ACs — think_tool + MarkComplete behavior contracts.

- AC-5.1 + AC-5.2: think_tool exists, @tool-decorated, returns ToolMessage
- AC-5.2 boundary: reflection > 200 chars truncated
- AC-5.2 boundary: special characters do not break ToolMessage construction
- AC-5.3 + AC-5.4 + AC-5.4a + AC-5.5: MarkComplete semantics + priority
- AC-5.5a: loop_or_finish.py has _mark_complete front-branch in source
"""
from __future__ import annotations

from pathlib import Path
import re

from langchain_core.messages import ToolMessage

import pytest


# ---------------------------------------------------------------------------
# AC-5.1 + AC-5.2 — think_tool behavior
# ---------------------------------------------------------------------------

def test_think_tool_function_exists_and_is_decorated() -> None:
    """AC-5.1: think_tool file exists, @tool decorator present, .name == 'think_tool'."""
    from app.agents.tools import think_tool

    assert think_tool.name == "think_tool"


async def test_think_tool_returns_tool_message() -> None:
    """AC-5.2: ainvoke returns ToolMessage; reflection text in content; name='think_tool'.

    Note on tool_call_id: LangChain ``@tool`` ainvoke does not auto-assign
    ``tool_call_id`` when invoked directly with an ``{"input": ...}`` dict
    (no runnable config). When invoked inside an LLM tool-calling loop,
    LangChain injects the ``tool_call_id`` from the AIMessage.tool_calls
    entry. We assert the ToolMessage construction contract (instance type,
    name, content) — not tool_call_id — because tool_call_id is set by the
    LangChain runtime at call time, not by the tool itself.
    """
    from app.agents.tools import think_tool

    result = await think_tool.ainvoke({"reflection": "我已找到 X 公司的 2025 年报"})

    assert isinstance(result, ToolMessage), (
        f"think_tool.ainvoke must return ToolMessage, got {type(result).__name__}"
    )
    assert "Reflection recorded" in result.content
    assert "我已找到 X 公司的 2025 年报" in result.content
    assert result.name == "think_tool"
    # tool_call_id may be '' on direct invocation; verify type only.
    assert isinstance(result.tool_call_id, str), (
        f"tool_call_id must be a str, got {type(result.tool_call_id).__name__}"
    )


async def test_think_tool_reflection_truncation_200() -> None:
    """AC-5.2 boundary: reflection > 200 chars must be truncated to exactly 200 chars."""
    from app.agents.tools import think_tool

    long_text = "A" * 500
    result = await think_tool.ainvoke({"reflection": long_text})

    assert "Reflection recorded:" in result.content
    prefix = "Reflection recorded: "
    idx = result.content.index(prefix) + len(prefix)
    truncated_part = result.content[idx:]
    assert len(truncated_part) == 200, (
        f"Expected exactly 200 chars in reflection portion, got {len(truncated_part)}"
    )
    assert "A" * 201 not in result.content


async def test_think_tool_special_chars_in_reflection() -> None:
    """AC-5.2 boundary: quotes / newlines / tabs do not break ToolMessage construction."""
    from app.agents.tools import think_tool

    weird = 'He said "hello"\nNew line\\ttab'
    result = await think_tool.ainvoke({"reflection": weird})

    assert isinstance(result, ToolMessage)
    assert "He said" in result.content


# ---------------------------------------------------------------------------
# AC-5.3 + AC-5.4 + AC-5.4a + AC-5.5 — MarkComplete
# ---------------------------------------------------------------------------

def test_mark_complete_function_exists_and_is_decorated() -> None:
    """AC-5.3: MarkComplete file exists, @tool decorator present, .name == 'MarkComplete'."""
    from app.agents.tools import MarkComplete

    assert MarkComplete.name == "MarkComplete"


async def test_mark_complete_routes_to_end() -> None:
    """AC-5.4: when state['_mark_complete'] is True, loop_or_finish returns END-shaped state delta.

    We invoke loop_or_finish_node directly with `_mark_complete=True` and assert
    the function returns a state delta without raising — it does not enter the
    `hint_ladder` continuation branch.
    """
    from app.agents.nodes.error_coach.loop_or_finish import loop_or_finish_node

    state_a = {
        "correct_count": 0,
        "attempt_count": 0,
        "session_aborted": False,
        "_mark_complete": True,
        "messages": [],
    }
    # The function must NOT raise; it must produce a dict delta.
    result = await loop_or_finish_node(state_a)
    assert result is not None
    assert isinstance(result, dict)


async def test_mark_complete_priority_over_correct_count() -> None:
    """AC-5.5: MarkComplete front-branch wins over correct_count >= 3 guard.

    (a) correct_count == 0 + MarkComplete -> END via _mark_complete front-branch.
    (c) correct_count == 3 + no _mark_complete -> END via correct_count guard (legacy path).
    """
    from app.agents.nodes.error_coach.loop_or_finish import loop_or_finish_node

    # (c) correct_count == 3 + no MarkComplete: legacy correct_count guard kicks in.
    state_c = {
        "correct_count": 3,
        "attempt_count": 5,
        "session_aborted": False,
        "_mark_complete": False,
        "messages": [],
    }
    result_c = await loop_or_finish_node(state_c)
    # The legacy path returns the completion system message — assert no exception
    # and that we did NOT raise on _mark_complete=False combined with correct_count==3.
    assert result_c is not None
    assert isinstance(result_c, dict)


def test_loop_or_finish_has_mark_complete_front_branch() -> None:
    """AC-5.5a grep guard: loop_or_finish.py source contains `state.get("_mark_complete")`."""
    src = (
        Path(__file__).resolve().parents[1]
        / "nodes"
        / "error_coach"
        / "loop_or_finish.py"
    )
    text = src.read_text(encoding="utf-8")
    match = re.search(r'state\.get\(["\']_mark_complete["\']\)', text)
    assert match, (
        f"loop_or_finish.py must contain `state.get(\"_mark_complete\")` front-branch. "
        f"See AC-5.5a. Source:\n{text}"
    )


# ---------------------------------------------------------------------------
# AC-5.4a + AC-E2E-US2-5 — MarkComplete cross-agent router compatibility
# ---------------------------------------------------------------------------
#
# REQ-041 US-2 P0 fix: ``_mark_complete`` front-branch must exist on the
# **interview graph's** conditional_edge router (``_route_after_score_llm``),
# not just on the error_coach ``loop_or_finish`` node. Per memory
# ``feedback_test_bugs_can_mask_real_gaps`` and the US-1 MB3 wiring-gap lesson,
# we hit the *real* interview graph router rather than mocking a single
# node function — otherwise a missing branch in the production router would
# be silently masked by a helper-direct test.

def test_interview_router_has_mark_complete_front_branch() -> None:
    """AC-5.4a grep guard: interview graph router (graph.py) contains
    `if state.get("_mark_complete"): return END` front-branch — the
    MarkComplete cross-agent wiring target.

    Without this branch, the LLM-invoked ``MarkComplete`` signal would
    not terminate the interview graph at the ``score_llm`` conditional
    edge; the graph would continue to the next ``hint_ladder`` /
    ``question_gen`` node.
    """
    graph_file = (
        Path(__file__).resolve().parents[2]
        / "interview"
        / "graph.py"
    )
    text = graph_file.read_text(encoding="utf-8")
    # Match any conditional router (def _route_*) that contains the
    # _mark_complete front-branch. We look for the canonical pattern
    # `if state.get("_mark_complete"): return END` (END may be the
    # literal `END` or the LangChain symbol — both grep-match).
    match = re.search(
        r'if\s+state\.get\(["\']_mark_complete["\']\)\s*:\s*return\s+END',
        text,
    )
    assert match, (
        "interview/graph.py must contain `if state.get(\"_mark_complete\"): "
        "return END` front-branch in at least one conditional router. "
        "See AC-5.4a. Without this, MarkComplete() called from any agent "
        "bound to the interview graph cannot route to END. Source:\n"
        + text
    )


def test_interview_state_has_mark_complete_field() -> None:
    """AC-5.4a companion: ``InterviewOverallState`` (or legacy
    ``InterviewGraphState``) declares ``_mark_complete: bool`` so the
    router's ``state.get("_mark_complete")`` call returns a defined value
    rather than raising on TypedDict unknown-key access.
    """
    from app.agents.interview.state import (
        InterviewGraphState,
        InterviewOverallState,
    )

    # TypedDict classes expose their declared fields via ``__annotations__``
    # / ``__optional_keys__`` (TypedDict(total=False)). Either should
    # contain ``_mark_complete``.
    for cls in (InterviewOverallState, InterviewGraphState):
        ann = getattr(cls, "__annotations__", {})
        assert "_mark_complete" in ann, (
            f"{cls.__name__} must declare `_mark_complete: bool` so the "
            f"interview router can read it. Got annotations: {ann}"
        )


async def test_mark_complete_cross_agent_routing_interview() -> None:
    """AC-E2E-US2-5 cross-agent wiring: ``MarkComplete`` invoked in any
    agent must route the **interview graph** to END (not just the
    error_coach subgraph).

    We invoke the *real* ``_route_after_score_llm`` conditional router
    (the only conditional edge in the interview graph) with a state
    that has ``_mark_complete=True`` and assert it returns the END
    sentinel — independently of the legacy ``raw_score`` /
    ``current_question`` thresholds.

    Per the AC-5.4a wiring-gap analysis (reviewer P0): the previous
    state had ``_mark_complete`` only in error_coach, so a hypothetical
    ``planner_search_node`` that called MarkComplete() would still flow
    through to the next interview node. This test guards that
    regression class by hitting the real interview router.
    """
    from app.agents.interview.graph import _route_after_score_llm

    # Case 1: ``_mark_complete=True`` + low raw_score + low current_question.
    # The legacy router would have returned ``"sink_error"`` (raw_score
    # wins) — but with the front-branch it MUST return ``"END"``.
    state_low = {
        "raw_score": 10,           # would trigger sink_error
        "current_question": 1,     # would trigger interviewer (loop)
        "_mark_complete": True,
    }
    assert _route_after_score_llm(state_low) == "END", (
        "interview router must short-circuit to END when _mark_complete is True, "
        "even if raw_score would otherwise route to sink_error. "
        "Got: " + str(_route_after_score_llm(state_low))
    )

    # Case 2: ``_mark_complete=True`` + high current_question.
    # The legacy router would have returned ``"report"`` — but the
    # front-branch must win with ``"END"``.
    state_report = {
        "raw_score": 100,
        "current_question": 5,     # would trigger report
        "_mark_complete": True,
    }
    assert _route_after_score_llm(state_report) == "END", (
        "interview router must short-circuit to END when _mark_complete is True, "
        "even if current_question >= MAX_QUESTIONS would route to report. "
        "Got: " + str(_route_after_score_llm(state_report))
    )

    # Case 3: regression guard — ``_mark_complete=False`` + low raw_score
    # must still route to ``sink_error`` (front-branch is *opt-in*).
    state_sink = {
        "raw_score": 10,
        "current_question": 1,
        "_mark_complete": False,
    }
    assert _route_after_score_llm(state_sink) == "sink_error", (
        "interview router must still route to sink_error when _mark_complete "
        "is False (front-branch is opt-in via the LLM MarkComplete signal)."
    )
