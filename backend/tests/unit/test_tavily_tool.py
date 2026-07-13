"""T010: Unit tests for TavilySearchTool (tavily_search).

Tests per REQ-041 StructuredTool contract:
  1. Normal search via ainvoke returns structured list[dict] results
  2. Empty results return empty list
  3. Per-query client exceptions are logged and propagated to the caller/retry boundary
  4. Missing API key raises TavilyAPIKeyMissingError
  5. max_results forwarded to TavilyClient
  6. Schema-invalid ainvoke input raises validation error
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from pydantic import ValidationError

from app.agents.tools._clients import TavilyAPIError, TavilyAPIKeyMissingError
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


@pytest.fixture(autouse=True)
def _clear_tavily_env(monkeypatch):
    """Ensure TAVILY_* env vars don't leak between tests."""
    monkeypatch.delenv("TAVILY_MOCK_MODE", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_MOCK_SCENARIO_PATH", raising=False)


@pytest.fixture
def mock_tavily_client():
    """Patch TavilyClient in tavily_search module with a controllable fake.

    Yields a mutable state dict. Tests set ``results`` (list[dict] returned by
    each ``search()`` call), ``side_effect`` (exception to raise per call), and
    can inspect ``calls`` (list of {query, max_results} dicts per invocation).
    """
    state: dict = {"results": [], "side_effect": None, "calls": []}

    class _FakeClient:
        def __init__(self, api_key: str, **kwargs: object) -> None:
            self.api_key = api_key

        async def search(self, query: str, max_results: int = 5) -> list[dict]:
            state["calls"].append({"query": query, "max_results": max_results})
            if state["side_effect"] is not None:
                raise state["side_effect"]
            return list(state["results"])

    with patch("app.agents.tools.tavily_search.TavilyClient", _FakeClient):
        yield state


# ===================================================================
# Acceptance scenario 1 + 2: normal search returns structured list[dict]
# ===================================================================


class TestTavilySearchSuccess:
    """StructuredTool .ainvoke returns raw list[dict] (REQ-053)."""

    @pytest.mark.asyncio
    async def test_returns_structured_results(self, mock_tavily_client: dict) -> None:
        """Given valid API key and results, returns list[dict] with all fields."""
        mock_tavily_client["results"] = [
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
        ]

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            result = await tavily_search.ainvoke(
                {"queries": ["Python programming"], "max_results": 5}
            )

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {
            "title": "Python Programming Guide",
            "content": "A comprehensive guide to Python programming.",
            "url": "https://python.example.com/guide",
            "score": 0.95,
        }
        assert result[1]["title"] == "Advanced Python Tips"
        assert result[1]["url"] == "https://python.example.com/tips"
        assert result[1]["score"] == 0.87

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(
        self, mock_tavily_client: dict
    ) -> None:
        """Search returning no results yields empty list."""
        mock_tavily_client["results"] = []

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            result = await tavily_search.ainvoke(
                {"queries": ["nothing"], "max_results": 5}
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_missing_fields_does_not_crash(
        self, mock_tavily_client: dict
    ) -> None:
        """Results with missing optional fields still produce valid output."""
        mock_tavily_client["results"] = [
            {"title": "Minimal Result", "url": "https://example.com/minimal"}
        ]

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            result = await tavily_search.ainvoke(
                {"queries": ["minimal"], "max_results": 5}
            )

        assert len(result) == 1
        assert result[0]["title"] == "Minimal Result"
        assert result[0]["url"] == "https://example.com/minimal"

    @pytest.mark.asyncio
    async def test_max_results_passed_to_client(
        self, mock_tavily_client: dict
    ) -> None:
        """max_results from ainvoke input is forwarded to TavilyClient.search."""
        mock_tavily_client["results"] = [_make_result(title="MR")]

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            await tavily_search.ainvoke(
                {"queries": ["test"], "max_results": 3}
            )

        assert mock_tavily_client["calls"][0]["max_results"] == 3

    @pytest.mark.asyncio
    async def test_multiple_queries_aggregated(
        self, mock_tavily_client: dict
    ) -> None:
        """Results from multiple queries are aggregated in call order."""
        mock_tavily_client["results"] = [_make_result(title="R", url="https://x.com")]

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            result = await tavily_search.ainvoke(
                {"queries": ["q1", "q2"], "max_results": 5}
            )

        # One result per query → two total
        assert len(result) == 2
        assert len(mock_tavily_client["calls"]) == 2
        assert mock_tavily_client["calls"][0]["query"] == "q1"
        assert mock_tavily_client["calls"][1]["query"] == "q2"


# ===================================================================
# Acceptance scenario 3: API errors degrade gracefully → empty list
# ===================================================================


class TestTavilySearchGracefulDegradation:
    """Per-query client exceptions are logged and propagated to the caller/retry boundary,
    not degraded to an empty aggregate."""

    @pytest.mark.asyncio
    async def test_timeout_propagates(self, mock_tavily_client: dict) -> None:
        """TimeoutError per query is propagated to the caller."""
        mock_tavily_client["side_effect"] = TimeoutError("request timed out")

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(TimeoutError, match="request timed out"):
                await tavily_search.ainvoke(
                    {"queries": ["test"], "max_results": 5}
                )

        assert mock_tavily_client['calls'] == [{'query': 'test', 'max_results': 5}]

    @pytest.mark.asyncio
    async def test_http_400_propagates(self, mock_tavily_client: dict) -> None:
        """TavilyAPIError (4xx) per query is propagated to the caller."""
        mock_tavily_client["side_effect"] = TavilyAPIError(
            "HTTP 400: Bad Request for query='test'"
        )

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(TavilyAPIError, match="HTTP 400"):
                await tavily_search.ainvoke(
                    {"queries": ["test"], "max_results": 5}
                )

        assert mock_tavily_client['calls'] == [{'query': 'test', 'max_results': 5}]

    @pytest.mark.asyncio
    async def test_http_500_propagates(self, mock_tavily_client: dict) -> None:
        """TavilyAPIError (5xx) per query is propagated to the caller."""
        mock_tavily_client["side_effect"] = TavilyAPIError(
            "HTTP 500: Internal Server Error for query='test'"
        )

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(TavilyAPIError, match="HTTP 500"):
                await tavily_search.ainvoke(
                    {"queries": ["test"], "max_results": 5}
                )

        assert mock_tavily_client['calls'] == [{'query': 'test', 'max_results': 5}]

    @pytest.mark.asyncio
    async def test_connection_error_propagates(
        self, mock_tavily_client: dict
    ) -> None:
        """ConnectionError per query is propagated to the caller."""
        mock_tavily_client["side_effect"] = ConnectionError("connection refused")

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(ConnectionError, match="connection refused"):
                await tavily_search.ainvoke(
                    {"queries": ["test"], "max_results": 5}
                )

        assert mock_tavily_client['calls'] == [{'query': 'test', 'max_results': 5}]

    @pytest.mark.asyncio
    async def test_rate_limit_propagates(self, mock_tavily_client: dict) -> None:
        """Rate limit (429) per query is propagated to the caller."""
        mock_tavily_client["side_effect"] = TavilyAPIError(
            "HTTP 429: Too Many Requests for query='test'"
        )

        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(TavilyAPIError, match="HTTP 429"):
                await tavily_search.ainvoke(
                    {"queries": ["test"], "max_results": 5}
                )

        assert mock_tavily_client['calls'] == [{'query': 'test', 'max_results': 5}]


# ===================================================================
# Missing API key → TavilyAPIKeyMissingError (REQ-041 AC-4.1a)
# ===================================================================


class TestTavilySearchMissingApiKey:
    """No API key configured raises TavilyAPIKeyMissingError."""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_typed_error(self) -> None:
        """When TAVILY_API_KEY is empty, raises TavilyAPIKeyMissingError."""
        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(api_key=""),
        ):
            with patch(
                "app.agents.tools.tavily_search.TavilyClient"
            ) as mock_client:
                with pytest.raises(TavilyAPIKeyMissingError):
                    await tavily_search.ainvoke(
                        {"queries": ["test"], "max_results": 5}
                    )
                mock_client.assert_not_called()


# ===================================================================
# Schema-invalid input to ainvoke
# ===================================================================


class TestTavilySearchInvalidInput:
    """Schema-invalid input to ainvoke raises validation error."""

    @pytest.mark.asyncio
    async def test_missing_required_queries_key_raises(self) -> None:
        """ainvoke input dict missing 'queries' key raises."""
        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(ValidationError):
                await tavily_search.ainvoke({"max_results": 5})

    @pytest.mark.asyncio
    async def test_non_list_queries_raises(self) -> None:
        """ainvoke input with non-list 'queries' raises."""
        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(ValidationError):
                await tavily_search.ainvoke(
                    {"queries": "not_a_list", "max_results": 5}
                )

    @pytest.mark.asyncio
    async def test_empty_queries_list_raises(self) -> None:
        """Empty queries list is rejected (list min_length=1)."""
        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(ValidationError):
                await tavily_search.ainvoke({"queries": [], "max_results": 5})

    @pytest.mark.asyncio
    async def test_whitespace_only_query_raises(self) -> None:
        """Whitespace-only query is rejected after stripping (str min_length=1)."""
        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(ValidationError):
                await tavily_search.ainvoke({"queries": ["   "], "max_results": 5})

    @pytest.mark.asyncio
    async def test_max_results_zero_raises(self) -> None:
        """max_results=0 is rejected (ge=1)."""
        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(ValidationError):
                await tavily_search.ainvoke({"queries": ["valid"], "max_results": 0})

    @pytest.mark.asyncio
    async def test_max_results_exceeds_five_raises(self) -> None:
        """max_results=6 is rejected (le=5)."""
        with patch(
            "app.agents.tools.tavily_search.get_settings",
            return_value=_settings_with(),
        ):
            with pytest.raises(ValidationError):
                await tavily_search.ainvoke({"queries": ["valid"], "max_results": 6})
