"""T010: Unit tests for TavilySearchTool (tavily_search).

Tests per impl-plan.md REQ-01 acceptance scenarios:
  1. Normal search returns formatted results (title/summary/source URL/relevance score)
  2. Search results formatted as text summary with source URLs
  3. Graceful degradation on timeout/4xx/5xx/missing-key — returns empty string
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agents.tools.tavily_search import tavily_search
from app.core.config import Settings


def _settings_with(api_key: str = "test-key-12345") -> Settings:
    """Return a Settings instance with the given tavily_api_key."""
    return Settings(
        tavily_api_key=api_key,
        deepseek_api_key="sk-dummy",
        database_url="sqlite+aiosqlite://",
        tavily_mock_mode=False,
    )


def _make_result(
    title: str = "Test Title",
    content: str = "Test content summary.",
    url: str = "https://example.com",
    score: float = 0.95,
) -> dict:
    return {"title": title, "content": content, "url": url, "score": score}


class MockTavilyClient:
    """Controllable mock that replaces tavily.TavilyClient."""

    def __init__(self, api_key: str = "", **kwargs) -> None:
        self.api_key = api_key
        self._results: list[dict] = []
        self._side_effect: Exception | None = None

    def set_results(self, results: list[dict]) -> None:
        self._results = results

    def set_side_effect(self, exc: Exception) -> None:
        self._side_effect = exc

    def search(self, **kwargs) -> dict:
        if self._side_effect:
            raise self._side_effect
        return {"results": self._results, "answer": None}


@pytest.fixture
def mock_tavily():
    """Replace tavily.TavilyClient with MockTavilyClient at the package level."""
    mc = MockTavilyClient()
    with patch("tavily.TavilyClient", return_value=mc):
        yield mc


class TestTavilySearchSuccess:
    """Acceptance scenario 1 + 2: normal search returns formatted results."""

    @pytest.mark.asyncio
    async def test_returns_formatted_results(self, mock_tavily: MockTavilyClient):
        """Given valid API key and results, returns formatted text with all fields."""
        mock_tavily.set_results([
            _make_result(
                title="Python Programming Guide",
                content="A comprehensive guide to Python programming.",
                url="https://python.example.com/guide",
                score=0.95,
            ),
            _make_result(
                title="Advanced Python Tips",
                content="Tips and tricks for advanced Python developers.",
                url="https://python.example.com/tips",
                score=0.87,
            ),
        ])

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="Python programming")

        assert "1. Python Programming Guide" in result
        assert "A comprehensive guide to Python programming." in result
        assert "Source: https://python.example.com/guide" in result
        assert "Relevance: 0.95" in result
        assert "2. Advanced Python Tips" in result
        assert "Source: https://python.example.com/tips" in result

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_string(
        self, mock_tavily: MockTavilyClient
    ):
        """Search returning no results yields empty string."""
        mock_tavily.set_results([])

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="nothing")

        assert result == ""

    @pytest.mark.asyncio
    async def test_missing_fields_does_not_crash(
        self, mock_tavily: MockTavilyClient
    ):
        """Results with missing optional fields still produce valid output."""
        mock_tavily.set_results([
            {"title": "Minimal Result", "url": "https://example.com/minimal"}
        ])

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="minimal")

        assert "1. Minimal Result" in result
        assert "Source: https://example.com/minimal" in result

    @pytest.mark.asyncio
    async def test_uses_basic_search_depth(self, mock_tavily: MockTavilyClient):
        """search_depth='basic' is accepted without error."""
        mock_tavily.set_results([
            _make_result(title="Basic Result", url="https://example.com/basic")
        ])

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="test", search_depth="basic")

        assert "Basic Result" in result


class TestTavilySearchGracefulDegradation:
    """Acceptance scenario 3: API errors return empty string."""

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(self, mock_tavily: MockTavilyClient):
        """Timeout error is caught and returns empty string."""
        mock_tavily.set_side_effect(TimeoutError("request timed out"))

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="test")

        assert result == ""

    @pytest.mark.asyncio
    async def test_http_400_returns_empty(self, mock_tavily: MockTavilyClient):
        """4xx error (e.g. bad request) returns empty string."""
        mock_tavily.set_side_effect(Exception("HTTP 400: Bad Request"))

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="test")

        assert result == ""

    @pytest.mark.asyncio
    async def test_http_500_returns_empty(self, mock_tavily: MockTavilyClient):
        """5xx error (e.g. server error) returns empty string."""
        mock_tavily.set_side_effect(Exception("HTTP 500: Internal Server Error"))

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="test")

        assert result == ""

    @pytest.mark.asyncio
    async def test_connection_error_returns_empty(self, mock_tavily: MockTavilyClient):
        """Connection-level failure returns empty string."""
        mock_tavily.set_side_effect(ConnectionError("connection refused"))

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="test")

        assert result == ""

    @pytest.mark.asyncio
    async def test_rate_limit_returns_empty(self, mock_tavily: MockTavilyClient):
        """Rate limit (429) returns empty string."""
        mock_tavily.set_side_effect(Exception("HTTP 429: Too Many Requests"))

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="test")

        assert result == ""


class TestTavilySearchMissingApiKey:
    """No API key configured."""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_empty(self):
        """When TAVILY_API_KEY is empty, skip search and return empty string."""
        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with(api_key="")), \
             patch("tavily.TavilyClient") as mock_cls:
            result = await tavily_search(query="test")
            mock_cls.assert_not_called()

        assert result == ""


class TestTavilySearchInvalidDepth:
    """Invalid search_depth should fall back."""

    @pytest.mark.asyncio
    async def test_invalid_search_depth_falls_back_to_advanced(
        self, mock_tavily: MockTavilyClient
    ):
        """When search_depth is invalid, defaults to 'advanced'."""
        mock_tavily.set_results([
            _make_result(title="Fallback", url="https://example.com/fallback")
        ])

        with patch("app.agents.tools.tavily_search.get_settings", return_value=_settings_with()):
            result = await tavily_search(query="test", search_depth="ultra")

        assert "Fallback" in result
