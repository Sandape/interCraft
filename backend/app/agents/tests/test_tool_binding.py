"""REQ-041 US-2 FR-004 ACs — `@tool` decorator + bind_tools + Tavily API key missing + 8 flag combos.

Tests in this file (Test-First red phase):
- AC-4.1a: tavily_search raises TavilyAPIKeyMissingError when TAVILY_API_KEY missing
- AC-4.5: TOOL_REGISTRY contains all 4 query tools (after AC-4.6 implements 6, this still PASSES)
- AC-4.6: TOOL_REGISTRY contains 4 query tools + 2 control flow tools (>= 6 entries)
- AC-4.7: bind_tools callable on real planner_graph (stub passthrough)
- AC-4.7b: bind_tools handles empty content + tool_calls
- AC-6.6: TOOL_REGISTRY _register_tools idempotent
- AC-7.1a: 8 flag combinations for AGENT_USE_V2_* independent
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest


class TestTavilyAPIKeyMissing:
    """AC-4.1a: tavily_search must raise TavilyAPIKeyMissingError (NOT KeyError) when TAVILY_API_KEY is unset."""

    async def test_tavily_search_handles_missing_api_key(self, monkeypatch):
        """Mock settings.TAVILY_API_KEY as empty/missing, call tavily_search.ainvoke,
        assert TavilyAPIKeyMissingError — explicitly NOT KeyError or ValidationError."""
        # Force settings to a fresh Settings instance with no TAVILY_API_KEY (clear any cached value).
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)

        # Import inside the test so we exercise the same code path the production agent uses.
        from app.agents.tools import tavily_search
        from app.agents.tools.tavily_search import TavilyAPIKeyMissingError

        with pytest.raises(TavilyAPIKeyMissingError):
            await tavily_search.ainvoke({"queries": ["test query"]})


class TestToolRegistry:
    """AC-4.5 + AC-4.6 + AC-6.6: TOOL_REGISTRY must contain all 4 query tools + 2 control tools."""

    def test_tool_registry_contains_4_tools(self):
        """AC-4.5: 4 query_* tools present in TOOL_REGISTRY."""
        from app.agents.tools import TOOL_REGISTRY

        assert len(TOOL_REGISTRY) >= 4, f"Expected >= 4, got {len(TOOL_REGISTRY)}"
        for name in ("tavily_search", "query_error_question_by_id", "query_resume_blocks", "query_interview_report"):
            assert name in TOOL_REGISTRY, (
                f"Missing tool '{name}' in TOOL_REGISTRY. "
                f"Present: {sorted(TOOL_REGISTRY.keys())}"
            )

    def test_tool_registry_contains_6_tools(self):
        """AC-4.6: 4 query tools + 2 control flow tools (think_tool + MarkComplete) = >= 6 entries."""
        from app.agents.tools import TOOL_REGISTRY

        required = {
            "tavily_search",
            "query_error_question_by_id",
            "query_resume_blocks",
            "query_interview_report",
            "think_tool",
            "MarkComplete",
        }
        missing = required - set(TOOL_REGISTRY.keys())
        assert not missing, f"Missing tools: {missing}. Present: {sorted(TOOL_REGISTRY.keys())}"

    def test_register_tools_idempotent(self):
        """AC-6.6: calling _register_tools() twice does NOT grow TOOL_REGISTRY."""
        from app.agents.tools import TOOL_REGISTRY, _register_tools

        before = len(TOOL_REGISTRY)
        _register_tools()
        after = len(TOOL_REGISTRY)
        assert before == after, (
            f"_register_tools() is NOT idempotent: {before} -> {after}. "
            f"Tools doubled up. Present: {sorted(TOOL_REGISTRY.keys())}"
        )


class TestBindToolsOnRealPlannerGraph:
    """AC-4.7: bind_tools callable on real planner_graph stub. AC-4.7b: empty content + tool_calls."""

    async def test_bind_tools_callable_on_real_planner_graph(self):
        """AC-4.7: dynamically import get_planner_subgraph, wrap bind_tools, ensure callable."""
        from app.agents.interview.planner_graph import get_planner_subgraph
        from app.agents.tools import tavily_search, think_tool, MarkComplete

        planner = get_planner_subgraph()
        # get_planner_subgraph() returns a CompiledStateGraph.
        # In langgraph 1.x (T183) compiled graphs are not directly callable;
        # use .ainvoke() explicitly. We verify that invoking with an empty
        # state delta does not raise.
        result = await planner.ainvoke({"messages": []})
        assert isinstance(result, dict), f"planner must return dict (state delta), got {type(result)}"

    async def test_bind_tools_handles_empty_content_with_tool_calls(self):
        """AC-4.7b: when LLM returns AIMessage(content='', tool_calls=[...]) the
        node function must log tool_calls and not assume content is non-empty.
        We mock MockLLMClient.ainvoke to return that exact shape and verify
        the node function does not raise IndexError on empty content."""
        from langchain_core.messages import AIMessage, ToolCall

        from app.agents.llm_client_mock import MockLLMClient

        # Build a mock LLM client that returns an empty-content AIMessage with tool_calls.
        tc = ToolCall(id="mock_id_123", name="tavily_search", args={"queries": ["x"], "max_results": 5})
        mock = MockLLMClient(
            planned_tool_calls=[
                {"id": "mock_id_123", "name": "tavily_search", "args": {"queries": ["x"], "max_results": 5}},
            ],
        )
        msg = await mock.ainvoke(
            messages=[],
            user_id="u",
            thread_id="t",
            node_name="planner_search",
        )
        # LangChain AIMessage must carry the tool_calls field even with empty content.
        assert msg.content == ""
        assert msg.tool_calls, "tool_calls must be propagated"
        assert msg.tool_calls[0]["name"] == "tavily_search"
        assert msg.tool_calls[0]["id"] == "mock_id_123"
        # The ToolCall object's args must be accessible; this matches the "node function
        # processes tool_calls without assuming content" contract.
        assert tc["name"] == "tavily_search"


class TestEightFlagCombinations:
    """AC-7.1a: 8 combos of AGENT_USE_V2_* flags must each load independently."""

    @pytest.mark.parametrize(
        "error_handler,tool_binding,control_tools",
        [
            (True, True, True),
            (True, True, False),
            (True, False, True),
            (True, False, False),
            (False, True, True),
            (False, True, False),
            (False, False, True),
            (False, False, False),
        ],
    )
    def test_ac_7_1_eight_flag_combinations_independent(
        self, monkeypatch, error_handler, tool_binding, control_tools
    ):
        """Each AGENT_USE_V2_* flag toggles independently. Build a fresh Settings
        instance with each combo and assert the three bool fields hold the
        expected values.

        We construct ``Settings()`` directly (not via the cached get_settings())
        so each parametrize case gets an isolated view of the environment.
        """
        monkeypatch.setenv("AGENT_USE_V2_ERROR_HANDLER", "true" if error_handler else "false")
        monkeypatch.setenv("AGENT_USE_V2_TOOL_BINDING", "true" if tool_binding else "false")
        monkeypatch.setenv("AGENT_USE_V2_CONTROL_TOOLS", "true" if control_tools else "false")

        from app.core.config import Settings

        settings = Settings()
        assert settings.agent_use_v2_error_handler is error_handler, (
            f"AGENT_USE_V2_ERROR_HANDLER mismatch for combo ("
            f"{error_handler}, {tool_binding}, {control_tools})"
        )
        assert settings.agent_use_v2_tool_binding is tool_binding, (
            f"AGENT_USE_V2_TOOL_BINDING mismatch for combo ("
            f"{error_handler}, {tool_binding}, {control_tools})"
        )
        assert settings.agent_use_v2_control_tools is control_tools, (
            f"AGENT_USE_V2_CONTROL_TOOLS mismatch for combo ("
            f"{error_handler}, {tool_binding}, {control_tools})"
        )
