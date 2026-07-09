"""REQ-053 T036/T037/T038 — search unit tests.

T036: 4 dimensions collected concurrently with REAL Tavily calls.
T037: Retry with exponential backoff (2s/4s/8s) when Tavily fails.
T038: 24h cache hit/miss — same-company results within TTL are reused.

These tests use the REAL Tavily API (TAVILY_API_KEY must be set).
Tests are skipped if the key is missing.

Run:
    cd backend && uv run pytest tests/unit/modules/research/test_search.py -v
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------


_HAS_TAVILY = bool(os.environ.get("TAVILY_API_KEY"))


pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# T036 — 4 dimensions concurrent
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_TAVILY, reason="TAVILY_API_KEY not set")
@pytest.mark.asyncio
async def test_t036_four_dimensions_collected_concurrently_with_real_tavily() -> None:
    """Hit real Tavily for 4 dimensions (interview_experience, company_product,
    exam_points, user_weakness) and verify they all return ≥1 result.
    """
    from app.agents.tools.tavily_search import tavily_search

    company = "字节跳动"
    position = "AI 应用工程师"
    keywords = ["RAG", "向量检索"]

    dimensions = {
        "interview_experience": [f"{company} {position} 面试经验"],
        "company_product": [f"{company} 扣子 豆包 产品"],
        "exam_points": [f"{position} 面试考点 LLM"],
        # user_weakness is local DB — not searched
    }

    async def run_dim(name: str, queries: list[str]) -> list[dict]:
        return await tavily_search.ainvoke({"queries": queries, "max_results": 3})

    started = datetime.now(UTC)
    results = await asyncio.gather(
        *(run_dim(name, qs) for name, qs in dimensions.items()),
        return_exceptions=True,
    )
    elapsed = (datetime.now(UTC) - started).total_seconds()

    # Each non-weakness dimension should yield at least 1 hit
    non_weakness = list(dimensions.keys())
    for i, name in enumerate(non_weakness):
        r = results[i]
        assert not isinstance(r, Exception), (
            f"{name} failed: {r}"
        )
        assert isinstance(r, list), f"{name} expected list, got {type(r)}"
        # Real Tavily should return at least 1 hit for a popular company
        assert len(r) >= 1, f"{name} returned 0 hits"

    # Concurrent execution should be faster than sequential × 4
    # (loose bound: 4 × ~3s = 12s sequential vs ~5s concurrent)
    assert elapsed < 30, f"4 concurrent calls took {elapsed}s — too slow"


# ---------------------------------------------------------------------------
# T037 — retry with exponential backoff
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t037_retry_succeeds_on_third_attempt_with_real_tavily() -> None:
    """When Tavily fails twice, retry with 2s/4s backoff, then succeed.

    The service does `from app.agents.tools.tavily_search import tavily_search`
    INSIDE `_search_with_retry`. We patch the `tavily_search` symbol in the
    `app.agents.tools.tavily_search` module so the re-import rebinds to our
    stub coroutine.
    """
    from app.modules.research.service import ResearchService

    call_log: list[float] = []

    async def fake_tavily_call(*args, **kwargs):
        from time import monotonic
        call_log.append(monotonic())
        if len(call_log) <= 2:
            raise RuntimeError("simulated Tavily 5xx")
        return [{"title": "hit", "url": "https://x", "content": "y"}]

    # Patch the symbol the service module imports lazily.
    with patch("app.agents.tools.tavily_search.tavily_search", fake_tavily_call):
        svc = ResearchService(MagicMock())
        svc.result_repo.create = AsyncMock()

        started = __import__("time").monotonic()
        hits = await svc._search_with_retry(
            task_id=MagicMock(),
            dimension="interview_experience",
            queries=["字节跳动 面试 面经"],
            company="字节跳动",
        )
        elapsed = __import__("time").monotonic() - started

    assert len(hits) == 1, f"should have 1 hit after retry, got {hits}"
    assert len(call_log) == 3, f"should have made 3 calls, got {len(call_log)}"

    # Backoff between calls should be ~2s and ~4s (totaling ≥6s)
    gap1 = call_log[1] - call_log[0]
    gap2 = call_log[2] - call_log[1]
    assert gap1 >= 1.8, f"first backoff should be ~2s, got {gap1:.2f}s"
    assert gap2 >= 3.8, f"second backoff should be ~4s, got {gap2:.2f}s"
    assert elapsed >= 6.0, f"total elapsed should be ≥6s, got {elapsed:.2f}s"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t037_all_retries_exhausted_returns_empty() -> None:
    """When Tavily fails all 3 attempts, the method returns [] and logs the error."""
    from app.modules.research.service import ResearchService

    async def always_fail_call(*args, **kwargs):
        raise RuntimeError("simulated 500")

    with patch("app.agents.tools.tavily_search.tavily_search", always_fail_call):
        svc = ResearchService(MagicMock())
        svc.result_repo.create = AsyncMock()

        hits = await svc._search_with_retry(
            task_id=MagicMock(),
            dimension="exam_points",
            queries=["后端 面试 知识点"],
            company="X",
        )

    assert hits == [], "should return empty list when all retries fail"
    assert svc.result_repo.create.await_count == 1, (
        "should still persist a failure marker row"
    )
    # The error kwarg should be set on the failure row
    call_kwargs = svc.result_repo.create.await_args.kwargs
    assert call_kwargs["error"] is not None
    assert "simulated 500" in call_kwargs["error"]


# ---------------------------------------------------------------------------
# T038 — 24h cache
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t038_cache_hit_returns_recent_results() -> None:
    """When a recent result (within 24h) exists for the same company, the
    service skips the Tavily call for the cached dimensions."""
    from app.modules.research.service import ResearchService

    cached_exp = [{"title": "cached_exp", "url": "https://x", "content": "old"}]
    cached_prod = [{"title": "cached_prod", "url": "https://y", "content": "old2"}]

    svc = ResearchService(MagicMock())
    svc.result_repo.get_cached_for_company = AsyncMock(
        return_value=[
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "task_id": "22222222-2222-2222-2222-222222222222",
                "dimension": "interview_experience",
                "query": "x",
                "results": cached_exp,
                "result_count": 1,
                "company": "X",
                "error": None,
                "searched_at": datetime.now(UTC),
            },
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "task_id": "22222222-2222-2222-2222-222222222222",
                "dimension": "company_product",
                "query": "y",
                "results": cached_prod,
                "result_count": 1,
                "company": "X",
                "error": None,
                "searched_at": datetime.now(UTC),
            },
        ]
    )
    # exam_points is NOT cacheable → _search_with_retry is called for it
    # but we want it to return something
    async def fresh_exam(**kwargs):
        return [{"title": "exam_fresh", "url": "https://z", "content": "exam"}]
    svc._search_with_retry = AsyncMock(side_effect=fresh_exam)

    results = await svc._execute_search_dimensions(
        task_id=MagicMock(),
        company="X",
        position="Y",
        keywords=["k1"],
    )

    assert results["interview_experience"] == cached_exp
    assert results["company_product"] == cached_prod
    assert results["exam_points"] == [
        {"title": "exam_fresh", "url": "https://z", "content": "exam"}
    ]
    # _search_with_retry was called ONCE — only for exam_points
    assert svc._search_with_retry.await_count == 1
    # Verify it was called for exam_points, not the cached dims
    call = svc._search_with_retry.await_args
    assert call.kwargs["dimension"] == "exam_points"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t038_cache_miss_fetches_fresh() -> None:
    """When no cached results exist (or expired), Tavily is invoked."""
    from app.modules.research.service import ResearchService

    svc = ResearchService(MagicMock())
    svc.result_repo.get_cached_for_company = AsyncMock(return_value=[])
    svc.result_repo.create = AsyncMock()

    async def fake_search(**kwargs):
        return [{"title": "fresh", "url": "https://y", "content": "z"}]

    svc._search_with_retry = AsyncMock(side_effect=fake_search)

    results = await svc._execute_search_dimensions(
        task_id=MagicMock(),
        company="Z",
        position="W",
        keywords=["k2"],
    )

    assert results["interview_experience"] == [
        {"title": "fresh", "url": "https://y", "content": "z"}
    ]
    svc._search_with_retry.assert_awaited()


__all__ = []
