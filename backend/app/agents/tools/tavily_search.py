"""REQ-041 US-2 FR-004 — ``tavily_search`` @tool (web search wrapper around Tavily).

The tool invokes :class:`app.agents.tools._clients.TavilyClient` for each
query in ``queries`` and aggregates the result dicts. API key absence surfaces
as the typed :class:`TavilyAPIKeyMissingError` per AC-4.1a.
"""
from __future__ import annotations

import os

from langchain_core.tools import tool

from app.agents.tools._clients import (
    TavilyAPIKeyMissingError,
    TavilyClient,
)


def _resolve_tavily_api_key() -> str | None:
    """Look up TAVILY_API_KEY via Settings with safe fallback to env / empty.

    Wrapped in try/except so importing ``tavily_search`` never breaks Settings
    initialisation in test environments that have no DB / Redis wired up
    (e.g. ``pytest --collect-only``).
    """
    try:
        from app.core.config import get_settings

        value = get_settings().tavily_api_key
        if value:
            return value
    except Exception:
        pass
    return os.environ.get("TAVILY_API_KEY") or None


@tool
async def tavily_search(
    queries: list[str],
    max_results: int = 5,
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
    """
    import structlog

    logger = structlog.get_logger("agents.tools.tavily_search")

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
        except Exception as exc:  # surface as runtime error for @node_error_handler
            logger.warning("tavily_search.query_failed", query=query, error=str(exc))
            continue
        aggregated.extend(results)
    return aggregated


__all__ = ["tavily_search", "TavilyAPIKeyMissingError"]
