"""MockTavilyClient for deterministic E2E testing (REQ-10).

Activated by ``TAVILY_MOCK_MODE=1`` env var. Reads a scenario JSON file
describing preset search results keyed by query string. Returns empty
results for unmatched queries — never raises.

Scenario JSON format::

    {
      "scenarios": [
        {
          "query": "python programming interview experience",
          "results": [
            {
              "title": "Python Interview Guide",
              "content": "Comprehensive Python interview preparation …",
              "url": "https://example.com/python-guide",
              "score": 0.95
            }
          ]
        }
      ]
    }

A scenario with ``"query": "default"`` acts as the catch-all when no
specific query matches.

Pattern follows ``MockLLMClient`` (see ``app/agents/llm_client_mock.py``).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("agents.tools.tavily_client_mock")


class MockTavilyClient:
    """Deterministic mock Tavily client for E2E / unit tests.

    Implements the same ``search()`` interface as ``tavily.TavilyClient``
    but returns preset results from a scenario file instead of calling the
    real Tavily API.
    """

    def __init__(self, scenarios: list[dict] | None = None) -> None:
        """Initialize with an optional list of scenario dicts.

        Each scenario should have:
            - ``query`` (str):  the search query string to match.
            - ``results`` (list[dict]):  preset search result dicts, each
              containing ``title``, ``content``, ``url``, and ``score``.
        """
        self._scenarios: list[dict] = list(scenarios or [])

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_scenario_file(cls, path: str) -> MockTavilyClient:
        """Load scenarios from a JSON file.  Falls back to empty on error."""
        if not path:
            logger.warning("tavily.mock_scenario_missing", path=path)
            return cls()
        p = Path(path)
        if not p.exists():
            logger.warning("tavily.mock_scenario_not_found", path=path)
            return cls()
        try:
            data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
            return cls(scenarios=data.get("scenarios"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("tavily.mock_scenario_parse_error", path=path, error=str(exc))
            return cls()

    # ------------------------------------------------------------------
    # Tavily-compatible API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Return preset results for a matching scenario, or empty results.

        Args:
            query: The search query string.
            search_depth: Ignored (kept for API compatibility).
            max_results: Maximum number of results to return.

        Returns:
            Dict with ``"results"`` (list[dict]) and ``"answer"`` (``None``).
            Empty results when no scenario matches the query.
        """
        # 1. Try exact query match
        for scenario in self._scenarios:
            if scenario.get("query", "") == query:
                results = scenario.get("results", [])
                return {"results": results[:max_results], "answer": None}

        # 2. Try catch-all default scenario
        for scenario in self._scenarios:
            if scenario.get("query", "") == "default":
                results = scenario.get("results", [])
                return {"results": results[:max_results], "answer": None}

        # 3. No match
        return {"results": [], "answer": None}


__all__ = ["MockTavilyClient"]
