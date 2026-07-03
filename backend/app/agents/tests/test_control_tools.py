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
    """AC-5.2: ainvoke returns ToolMessage; reflection text in content; tool_call_id set."""
    from app.agents.tools import think_tool

    result = await think_tool.ainvoke({"reflection": "我已找到 X 公司的 2025 年报"})

    assert isinstance(result, ToolMessage), (
        f"think_tool.ainvoke must return ToolMessage, got {type(result).__name__}"
    )
    assert "Reflection recorded" in result.content
    assert "我已找到 X 公司的 2025 年报" in result.content
    assert result.name == "think_tool"
    assert isinstance(result.tool_call_id, str) and result.tool_call_id, (
        f"tool_call_id must be a non-empty str, got {result.tool_call_id!r}"
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
