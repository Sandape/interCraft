"""T011: Unit tests for MockTavilyClient (REQ-10).

Tests per impl-plan.md REQ-10 acceptance scenarios:
  1. Scenario loading — ``from_scenario_file`` loads preset results from JSON
  2. Empty fallback — unknown query returns empty results without raising
  3. Environment toggle — ``TAVILY_MOCK_MODE=1`` activates mock in ``tavily_search``

Pattern follows ``test_tavily_tool.py`` and ``test_llm_client_mock.py``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents.tools.tavily_client_mock import MockTavilyClient
from app.agents.tools.tavily_search import tavily_search
from app.core.config import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    title: str = "Test Title",
    content: str = "Test content.",
    url: str = "https://example.com",
    score: float = 0.95,
) -> dict:
    return {"title": title, "content": content, "url": url, "score": score}


def _scenario_json(scenarios: list[dict]) -> str:
    return json.dumps({"scenarios": scenarios}, ensure_ascii=False, indent=2)


def _mock_settings(
    tavily_mock_mode: bool = False,
    tavily_api_key: str = "test-key",
) -> Settings:
    return Settings(
        tavily_mock_mode=tavily_mock_mode,
        tavily_api_key=tavily_api_key,
        deepseek_api_key="sk-dummy",
        database_url="sqlite+aiosqlite://",
    )


# ===================================================================
# Acceptance scenario 1: scenario loading
# ===================================================================

class TestScenarioLoading:
    """``from_scenario_file`` correctly loads preset results."""

    def test_loads_scenarios_from_file(self, tmp_path: Path):
        """Valid JSON file with scenarios loads correctly."""
        f = tmp_path / "scenarios.json"
        f.write_text(_scenario_json([
            {"query": "python", "results": [_make_result(title="Py")]},
            {"query": "java", "results": [_make_result(title="Java")]},
        ]))
        mock = MockTavilyClient.from_scenario_file(str(f))
        assert len(mock._scenarios) == 2
        assert mock._scenarios[0]["query"] == "python"

    def test_missing_file_returns_empty(self):
        """Non-existent path falls back to empty scenarios."""
        mock = MockTavilyClient.from_scenario_file("/nonexistent/path.json")
        assert mock._scenarios == []

    def test_empty_path_returns_empty(self):
        """Empty string path falls back to empty scenarios."""
        mock = MockTavilyClient.from_scenario_file("")
        assert mock._scenarios == []

    def test_invalid_json_returns_empty(self, tmp_path: Path):
        """Malformed JSON falls back to empty scenarios."""
        f = tmp_path / "bad.json"
        f.write_text("not valid json")
        mock = MockTavilyClient.from_scenario_file(str(f))
        assert mock._scenarios == []

    def test_missing_scenarios_key_returns_empty(self, tmp_path: Path):
        """JSON without 'scenarios' key returns empty scenarios."""
        f = tmp_path / "no_key.json"
        f.write_text(json.dumps({"other": []}))
        mock = MockTavilyClient.from_scenario_file(str(f))
        assert mock._scenarios == []


# ===================================================================
# Acceptance scenario 2: search returns results or empty
# ===================================================================

class TestSearchResults:
    """Search returns preset results or empty fallback."""

    def test_exact_query_match_returns_results(self):
        """Exact query match yields the preset results."""
        mock = MockTavilyClient(scenarios=[
            {"query": "python", "results": [_make_result(title="Python Guide")]},
        ])
        response = mock.search(query="python")
        assert len(response["results"]) == 1
        assert response["results"][0]["title"] == "Python Guide"

    def test_unknown_query_returns_empty(self):
        """Unknown query returns empty results — no exception."""
        mock = MockTavilyClient(scenarios=[
            {"query": "python", "results": [_make_result(title="Py")]},
        ])
        response = mock.search(query="unknown")
        assert response["results"] == []

    def test_default_scenario_catch_all(self):
        """'default' scenario acts as catch-all for unmatched queries."""
        mock = MockTavilyClient(scenarios=[
            {"query": "specific", "results": [_make_result(title="Specific")]},
            {"query": "default", "results": [_make_result(title="Default")]},
        ])
        response = mock.search(query="anything")
        assert len(response["results"]) == 1
        assert response["results"][0]["title"] == "Default"

    def test_default_not_used_when_exact_match_exists(self):
        """Exact match takes priority over default scenario."""
        mock = MockTavilyClient(scenarios=[
            {"query": "python", "results": [_make_result(title="Exact")]},
            {"query": "default", "results": [_make_result(title="Default")]},
        ])
        response = mock.search(query="python")
        assert response["results"][0]["title"] == "Exact"

    def test_max_results_limits_output(self):
        """max_results caps the number of returned results."""
        mock = MockTavilyClient(scenarios=[{
            "query": "many",
            "results": [_make_result(title=f"R{i}") for i in range(10)],
        }])
        response = mock.search(query="many", max_results=3)
        assert len(response["results"]) == 3

    def test_search_depth_is_accepted(self):
        """search_depth param is accepted but doesn't affect output."""
        mock = MockTavilyClient(scenarios=[{
            "query": "t", "results": [_make_result(title="T")],
        }])
        assert mock.search(query="t", search_depth="basic") == mock.search(
            query="t", search_depth="advanced"
        )

    def test_empty_constructor_returns_empty(self):
        """No scenarios means empty results for any query."""
        mock = MockTavilyClient()
        assert mock.search(query="anything")["results"] == []

    def test_search_is_idempotent(self):
        """Multiple calls with the same query return identical results."""
        mock = MockTavilyClient(scenarios=[{
            "query": "stable", "results": [_make_result(title="Stable")],
        }])
        assert mock.search(query="stable") == mock.search(query="stable")


# ===================================================================
# Acceptance scenario 3: environment variable toggle
# ===================================================================

class TestEnvToggle:
    """``TAVILY_MOCK_MODE=1`` activates mock in ``tavily_search``."""

    @pytest.mark.asyncio
    async def test_mock_mode_returns_formatted_results(self, tmp_path: Path):
        """Mock mode returns formatted results matching real Tavily output."""
        f = tmp_path / "s.json"
        f.write_text(_scenario_json([
            {"query": "python programming", "results": [
                _make_result(title="Mock Py", url="https://mock.dev/py"),
            ]},
        ]))
        settings = _mock_settings(tavily_mock_mode=True)
        with patch("app.agents.tools.tavily_search.get_settings", return_value=settings), \
             patch.dict(os.environ, {"TAVILY_MOCK_SCENARIO_PATH": str(f)}):
            result = await tavily_search(query="python programming")
        assert "1. Mock Py" in result
        assert "Source: https://mock.dev/py" in result

    @pytest.mark.asyncio
    async def test_mock_mode_unknown_query_returns_empty(self, tmp_path: Path):
        """Unknown query in mock mode returns empty string."""
        f = tmp_path / "s.json"
        f.write_text(_scenario_json([
            {"query": "known", "results": [_make_result(title="Known")]},
        ]))
        settings = _mock_settings(tavily_mock_mode=True)
        with patch("app.agents.tools.tavily_search.get_settings", return_value=settings), \
             patch.dict(os.environ, {"TAVILY_MOCK_SCENARIO_PATH": str(f)}):
            result = await tavily_search(query="unknown")
        assert result == ""

    @pytest.mark.asyncio
    async def test_mock_mode_no_api_key_still_works(self, tmp_path: Path):
        """Mock mode does NOT require TAVILY_API_KEY."""
        f = tmp_path / "s.json"
        f.write_text(_scenario_json([
            {"query": "test", "results": [_make_result(title="No Key OK")]},
        ]))
        settings = _mock_settings(tavily_mock_mode=True, tavily_api_key="")
        with patch("app.agents.tools.tavily_search.get_settings", return_value=settings), \
             patch.dict(os.environ, {"TAVILY_MOCK_SCENARIO_PATH": str(f)}):
            result = await tavily_search(query="test")
        assert "No Key OK" in result

    @pytest.mark.asyncio
    async def test_mock_mode_without_scenario_file_returns_empty(self):
        """Mock mode with no scenario file returns empty."""
        settings = _mock_settings(tavily_mock_mode=True)
        with patch("app.agents.tools.tavily_search.get_settings", return_value=settings), \
             patch.dict(os.environ, {"TAVILY_MOCK_SCENARIO_PATH": ""}):
            result = await tavily_search(query="anything")
        assert result == ""

    @pytest.mark.asyncio
    async def test_mock_mode_output_format_matches_real(self, tmp_path: Path):
        """Formatted mock output has same structure as real output."""
        f = tmp_path / "s.json"
        f.write_text(_scenario_json([
            {
                "query": "test topic",
                "results": [
                    _make_result(title="R1", content="C1", url="https://a.com", score=0.9),
                    _make_result(title="R2", content="C2", url="https://b.com", score=0.8),
                ],
            },
        ]))
        settings = _mock_settings(tavily_mock_mode=True)
        with patch("app.agents.tools.tavily_search.get_settings", return_value=settings), \
             patch.dict(os.environ, {"TAVILY_MOCK_SCENARIO_PATH": str(f)}):
            result = await tavily_search(query="test topic")

        assert "1. R1" in result
        assert "C1" in result
        assert "Source: https://a.com" in result
        assert "Relevance: 0.9" in result
        assert "2. R2" in result
        assert "C2" in result
        assert "Source: https://b.com" in result
        assert "Relevance: 0.8" in result

    @pytest.mark.asyncio
    async def test_mock_mode_false_uses_real_client(self):
        """tavily_mock_mode=False falls through to normal flow (no crash)."""
        settings = _mock_settings(tavily_mock_mode=False)
        with patch("app.agents.tools.tavily_search.get_settings", return_value=settings), \
             patch("tavily.TavilyClient") as mock_cls:
            result = await tavily_search(query="test")
            mock_cls.assert_called_once()
        # With no API key set above, this should return empty string
        assert result == ""
