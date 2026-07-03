"""Tavily API HTTP client.

Uses :mod:`httpx` for async POST to ``https://api.tavily.com/search`` with
the auth headers Tavily documents for the v1 search endpoint. The client
is intentionally minimal — single ``search`` method, surface HTTP errors as
``TavilyAPIError`` (not raw :class:`httpx.HTTPStatusError`), so tool wrappers
can catch the typed exception.

Per REQ-041 US-2 AC-4.1a — API key absence surfaces as ``TavilyAPIKeyMissingError``,
distinct from KeyError / generic exception. Real HTTP / network errors use
``TavilyAPIError``.
"""
from __future__ import annotations

import os

import httpx


class TavilyAPIKeyMissingError(RuntimeError):
    """Raised when ``TAVILY_API_KEY`` is not configured.

    Per AC-4.1a: this is a dedicated exception type, NOT a KeyError. Catch
    sites that pre-validate the key get an unambiguous type for matching.
    """


class TavilyAPIError(RuntimeError):
    """Raised on a non-2xx response from the Tavily API."""


class TavilyClient:
    """Async HTTP wrapper around the Tavily search endpoint.

    Usage::

        client = TavilyClient(api_key="tvly-...")
        results = await client.search(["company 2025 annual report"], max_results=5)
    """

    BASE_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str, *, timeout_s: float = 15.0) -> None:
        if not api_key:
            raise TavilyAPIKeyMissingError(
                "TAVILY_API_KEY is empty; configure the env var before invoking Tavily."
            )
        self.api_key = api_key
        self._timeout = timeout_s

    async def search(self, query: str, *, max_results: int = 5) -> list[dict]:
        """Issue a single search request for ``query`` and return a list of
        result dicts (``title`` / ``url`` / ``content`` / ``score``).

        Reference: https://docs.tavily.com/docs/rest-api/api-reference#endpoint-search
        """
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self.BASE_URL, json=payload)
        if response.status_code >= 400:
            raise TavilyAPIError(
                f"Tavily API returned HTTP {response.status_code} for query={query!r}: "
                f"{response.text[:300]}"
            )
        data = response.json()
        return list(data.get("results", []))


__all__ = [
    "TavilyAPIKeyMissingError",
    "TavilyAPIError",
    "TavilyClient",
]
