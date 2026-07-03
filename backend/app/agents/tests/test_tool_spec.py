"""REQ-041 US-2 FR-006 ACs — ToolSpec Pydantic model + extract_tool_spec + SIDE_EFFECT_RULES.

- AC-6.1: class ToolSpec exists in app.agents.tools.spec with the 4 fields
- AC-6.2: extract_tool_spec(tool_func) returns ToolSpec
- AC-6.3 + AC-6.4 + AC-6.5: parametrize all 6 tools with exact side_effects matches
- AC-6.3a: SIDE_EFFECT_RULES is a module-level dict literal with >= 5 rules
"""
from __future__ import annotations

import pytest


def test_tool_spec_pydantic_schema() -> None:
    """AC-6.1: ToolSpec(name, schema, side_effects, requires_approval=False) Pydantic model."""
    from app.agents.tools.spec import ToolSpec

    # Construct a ToolSpec and verify all 4 fields are present.
    ts = ToolSpec(
        name="x",
        schema={"queries": "list[str]"},
        side_effects=["read"],
        requires_approval=False,
    )
    assert ts.name == "x"
    assert ts.schema == {"queries": "list[str]"}
    assert ts.side_effects == ["read"]
    assert ts.requires_approval is False


def test_side_effect_rules_explicit() -> None:
    """AC-6.3a: backend/app/agents/tools/spec.py contains a module-level
    SIDE_EFFECT_RULES dict literal with >= 5 rules covering all 6 tool categories."""
    from app.agents.tools import spec as spec_module

    rules = getattr(spec_module, "SIDE_EFFECT_RULES", None)
    assert isinstance(rules, dict), (
        f"SIDE_EFFECT_RULES must be a module-level dict, got {type(rules).__name__}"
    )
    assert len(rules) >= 5, (
        f"SIDE_EFFECT_RULES must have >= 5 entries, got {len(rules)}: {sorted(rules.keys())}"
    )
    # Verify coverage of the 6 tool categories via prefix matching.
    expected_prefixes = {"tavily", "query_", "think_tool", "MarkComplete"}
    assert expected_prefixes.issubset(set(rules.keys())), (
        f"Missing prefixes in SIDE_EFFECT_RULES: {expected_prefixes - set(rules.keys())}. "
        f"Present: {sorted(rules.keys())}"
    )


# ---------------------------------------------------------------------------
# AC-6.3 + AC-6.4 + AC-6.5 — parametrize all 6 tools with exact side_effects.
# ---------------------------------------------------------------------------

def _spec_for(tool_func):
    from app.agents.tools.spec import extract_tool_spec
    return extract_tool_spec(tool_func)


def test_extract_tool_spec_tavily() -> None:
    """AC-6.3 (a): tavily_search -> ['read', 'external_api'], requires_approval=False."""
    from app.agents.tools import tavily_search
    from app.agents.tools.spec import ToolSpec

    spec = _spec_for(tavily_search)
    assert isinstance(spec, ToolSpec)
    assert spec.name == "tavily_search"
    assert spec.side_effects == ["read", "external_api"], (
        f"tavily_search.side_effects must equal ['read', 'external_api'], got {spec.side_effects}"
    )
    assert spec.requires_approval is False


def test_extract_tool_spec_query_readonly() -> None:
    """AC-6.4: query_error_question / query_resume_blocks / query_interview_report -> ['read']."""
    from app.agents.tools import (
        query_error_question_by_id,
        query_resume_blocks,
        query_interview_report,
    )

    expected = ["read"]
    for tool in (query_error_question_by_id, query_resume_blocks, query_interview_report):
        spec = _spec_for(tool)
        assert spec.side_effects == expected, (
            f"{tool.name}.side_effects must equal {expected}, got {spec.side_effects}"
        )
        assert spec.requires_approval is False, (
            f"{tool.name}.requires_approval must be False, got {spec.requires_approval}"
        )


def test_extract_tool_spec_think_tool() -> None:
    """AC-6.3 (c): think_tool -> ['read'], requires_approval=False."""
    from app.agents.tools import think_tool

    spec = _spec_for(think_tool)
    assert spec.name == "think_tool"
    assert spec.side_effects == ["read"], (
        f"think_tool.side_effects must equal ['read'], got {spec.side_effects}"
    )
    assert spec.requires_approval is False


def test_extract_tool_spec_mark_complete() -> None:
    """AC-6.3 (d) + AC-6.5: MarkComplete -> ['ws_push'], requires_approval=True."""
    from app.agents.tools import MarkComplete

    spec = _spec_for(MarkComplete)
    assert spec.name == "MarkComplete"
    assert spec.side_effects == ["ws_push"], (
        f"MarkComplete.side_effects must equal ['ws_push'], got {spec.side_effects}"
    )
    assert spec.requires_approval is True, (
        f"MarkComplete.requires_approval must be True (ws_push), got {spec.requires_approval}"
    )
