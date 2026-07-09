"""Planner search node — Tavily web search for interview prep info (T013, REQ-04).

Searches across 3 dimensions using ``tavily_search``:
1. Interview experience / 面经 for the target company + position
2. Company tech stack and engineering culture
3. Common interview questions

Parses each dimension's results into structured ``SearchResult`` objects,
bundles them into a ``WebResearch`` model, and returns the state update.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import structlog

from app.agents.interview.schemas import SearchResult, WebResearch
from app.agents.interview.state import InterviewGraphState
from app.agents.tools.tavily_search import tavily_search

logger = structlog.get_logger(__name__)

_MAX_RESULTS_PER_DIM = 5


async def _run_tavily_query(query: str, *, max_results: int) -> Any:
    """Invoke the LangChain Tavily tool through its stable async surface."""
    return await tavily_search.ainvoke(
        {"queries": [query], "max_results": max_results}
    )


def _parse_tavily_output(raw: Any) -> list[SearchResult]:
    """Parse Tavily's formatted text output into ``SearchResult`` objects.

    The ``tavily_search`` tool returns a plain-text block per result::

        1. <Title>
        <snippet>
           Source: <url>
           Relevance: <score>

    This function extracts title, content/snippet, and URL from that format.
    Returns an empty list when the input is empty or contains no parseable
    results.
    """
    if isinstance(raw, list):
        results: list[SearchResult] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            content = str(item.get("content") or item.get("snippet") or "")
            url = str(item.get("url") or "")
            if title or content:
                results.append(SearchResult(title=title, content=content, url=url))
        return results

    if not isinstance(raw, str) or not raw.strip():
        return []

    results: list[SearchResult] = []
    # Result blocks are separated by one or more blank lines
    for block in re.split(r"\n\n+", raw.strip()):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")

        title = ""
        content_parts: list[str] = []
        url = ""

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("Source:"):
                url = stripped[len("Source:") :].strip()
            elif stripped.startswith("Relevance:"):
                continue
            elif i == 0:
                # First non-meta line is the title; strip heading number (e.g. "1. ")
                title = re.sub(r"^\d+\.\s*", "", stripped)
            else:
                if stripped:
                    content_parts.append(stripped)

        content = " ".join(content_parts).strip()
        if title or content:
            results.append(SearchResult(title=title, content=content, url=url))

    return results


_SUMMARY_DIMENSIONS: list[tuple[str, str]] = [
    ("interview_experience", "面经"),
    ("company_tech_stack", "技术栈"),
    ("common_questions", "常见问题"),
]


def _build_summary(web_research: WebResearch) -> str:
    """Build a concise summary (<=500 chars) from WebResearch results.

    For each non-empty dimension, appends a short sentence noting source URLs.
    The calling node's LLM call (planner_generate / T014) will later refine
    this into ``InterviewPlan.web_research_summary``.
    """
    parts: list[str] = []

    for dim, label in _SUMMARY_DIMENSIONS:
        items: list[SearchResult] = getattr(web_research, dim)
        if not items:
            continue
        urls = [r.url for r in items if r.url]
        part = (
            f"{label}方面查到 {len(items)} 条结果"
            + (f"，参考来源：{'; '.join(urls)}" if urls else "")
        )
        parts.append(part)

    summary = "；".join(parts)
    if len(summary) > 500:
        summary = summary[:497] + "..."

    return summary or "未搜索到相关结果"


async def planner_search_node(state: InterviewGraphState) -> dict[str, Any]:
    """Search the web for interview preparation information.

    Reads the target **company** and **position** from graph state, performs
    3 parallel Tavily searches across the defined dimensions, and returns
    structured ``WebResearch`` data for downstream plan generation.

    Gracefully handles missing company/position (returns empty ``WebResearch``)
    and per-dimension search failures (returns empty list for that dimension).

    T021 (REQ-06): Skips Tavily search when ``interview_plan`` already exists
    in state (cached plan from a previous run).
    """
    # T021 — skip Tavily search when plan already cached
    if state.get("interview_plan") is not None:
        logger.info("planner_search.skip", reason="plan_already_cached")
        existing = state.get("web_research")
        return {"web_research": existing or WebResearch().model_dump()}

    company = (state.get("company") or "").strip()
    position = (state.get("position") or "").strip()

    if not company and not position:
        logger.warning("planner_search.skip", reason="no_company_or_position")
        return {"web_research": WebResearch().model_dump()}

    # --- Build 3 search queries -------------------------------------------
    queries = {
        "interview_experience": (
            f"{company} {position} interview experience 面经"
        ).strip(),
        "company_tech_stack": (
            f"{company} tech stack engineering culture"
        ).strip(),
        "common_questions": (
            f"{company} {position} interview common questions"
        ).strip(),
    }

    # --- Execute all 3 searches in parallel --------------------------------
    raw_results = await asyncio.gather(
        _run_tavily_query(
            queries["interview_experience"],
            max_results=_MAX_RESULTS_PER_DIM,
        ),
        _run_tavily_query(
            queries["company_tech_stack"],
            max_results=_MAX_RESULTS_PER_DIM,
        ),
        _run_tavily_query(
            queries["common_questions"],
            max_results=_MAX_RESULTS_PER_DIM,
        ),
        return_exceptions=True,
    )

    # --- Parse results -----------------------------------------------------
    dimension_keys = [
        "interview_experience",
        "company_tech_stack",
        "common_questions",
    ]

    web_research_kwargs: dict[str, list[SearchResult]] = {}
    for idx, dim_name in enumerate(dimension_keys):
        raw = raw_results[idx]
        if isinstance(raw, Exception):
            logger.warning(
                "planner_search.dim_failed",
                dimension=dim_name,
                error=str(raw),
            )
            web_research_kwargs[dim_name] = []
        else:
            parsed = _parse_tavily_output(raw)
            web_research_kwargs[dim_name] = parsed

    web_research = WebResearch(**web_research_kwargs)

    # --- Log results -------------------------------------------------------
    total_results = (
        len(web_research.interview_experience)
        + len(web_research.company_tech_stack)
        + len(web_research.common_questions)
    )
    summary = _build_summary(web_research)
    logger.info(
        "planner_search.complete",
        total_results=total_results,
        interview_experience_count=len(web_research.interview_experience),
        company_tech_stack_count=len(web_research.company_tech_stack),
        common_questions_count=len(web_research.common_questions),
        summary=summary,
    )

    return {"web_research": web_research.model_dump()}


__all__ = ["planner_search_node"]
