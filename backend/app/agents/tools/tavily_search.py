"""REQ-041 US-2 FR-004 — ``tavily_search`` @tool (web search wrapper around Tavily).

The tool invokes :class:`app.agents.tools._clients.TavilyClient` for each
query in ``queries`` and aggregates the result dicts. API key absence surfaces
as the typed :class:`TavilyAPIKeyMissingError` per AC-4.1a.
"""
from __future__ import annotations

import os
from typing import Annotated

from langchain_core.tools import tool
from pydantic import Field, StringConstraints

from app.agents.tools._clients import (
    TavilyAPIKeyMissingError,
    TavilyClient,
)
from app.core.config import get_settings

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
QueryList = Annotated[list[NonBlankStr], Field(min_length=1)]
MaxResults = Annotated[int, Field(ge=1, le=5)]


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _settings_value(name: str, default: object = None) -> object:
    try:
        return getattr(get_settings(), name)
    except Exception:
        return default


def _resolve_tavily_api_key() -> str | None:
    """Look up TAVILY_API_KEY via Settings with safe fallback to env / empty.

    Wrapped in try/except so importing ``tavily_search`` never breaks Settings
    initialisation in test environments that have no DB / Redis wired up
    (e.g. ``pytest --collect-only``).
    """
    try:
        value = str(_settings_value("tavily_api_key", "") or "")
        if value:
            return value
    except Exception:
        pass
    return os.environ.get("TAVILY_API_KEY") or None


def _resolve_mock_mode() -> bool:
    return bool(_settings_value("tavily_mock_mode", False)) or _truthy(
        os.environ.get("TAVILY_MOCK_MODE")
    )


@tool
async def tavily_search(
    queries: QueryList,
    max_results: MaxResults = 5,
) -> list[dict]:
    """Search the web for company / product / research data via Tavily.

    Use this when the user asks about external facts that may live on the
    public web, such as product roadmaps, financial results, or recent news.

    Args:
        queries: one or more search queries to issue (independent calls).
        max_results: maximum number of results per query (default 5).

    Returns:
        A list of result dicts ``{"title": str, "url": str, "content": str, "score": float}``
        across all queries. May be empty if Tavily returned zero hits.

    Raises:
        TavilyAPIKeyMissingError: when TAVILY_API_KEY is not configured.
        Exception: client search exceptions are logged then re-raised unchanged
            for caller retry handling.
    """
    import structlog

    logger = structlog.get_logger("agents.tools.tavily_search")

    if _resolve_mock_mode():
        from app.agents.tools.tavily_client_mock import MockTavilyClient

        scenario_path = os.environ.get("TAVILY_MOCK_SCENARIO_PATH", "")
        client = MockTavilyClient.from_scenario_file(scenario_path)
        aggregated: list[dict] = []
        for query in queries:
            response = client.search(query=query, max_results=max_results)
            aggregated.extend(response.get("results", []))
        return aggregated

    api_key = _resolve_tavily_api_key()
    if not api_key:
        raise TavilyAPIKeyMissingError(
            "TAVILY_API_KEY is not configured; cannot call Tavily search. "
            "Set TAVILY_API_KEY in environment or app/.env.local."
        )

    client = TavilyClient(api_key=api_key)
    aggregated: list[dict] = []
    for query in queries:
        try:
            results = await client.search(query, max_results=max_results)
        except Exception as exc:
            logger.warning("tavily_search.query_failed", query=query, error=str(exc))
            raise
        aggregated.extend(results)
    return aggregated


__all__ = ["tavily_search", "TavilyAPIKeyMissingError"]
