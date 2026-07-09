"""[REQ-048 US2 T046] Unit test for cross-encoder rerank call wrapper.

Tests the ``call_rerank`` function in isolation using ``httpx.MockTransport``
to mock the HTTP client. Validates:

- AC-04: top-50 -> top-5 by rerank score (we test the call shape + parse).
- AC-07: rerank 5xx → degraded fallback (``RerankResult.degraded=True``).
- AC-08: rerank unreachable → ``RerankUnavailableError`` raised.

Note: this is a unit test — the real cross-encoder is NOT started; we
exercise only the HTTP path. The model itself is exercised separately by
``tests/unit/services/embedding/test_reranker.py`` (REQ-048 T014).
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.agents.interview.drill_helpers.rerank_call import (
    RerankResult,
    RerankUnavailableError,
    call_rerank,
    fallback_to_input_order,
)


def _make_candidates(n: int = 50) -> list[dict[str, Any]]:
    return [
        {"id": f"q-{i}", "text": f"sample question {i}", "dimension": "tech_depth"}
        for i in range(n)
    ]


async def test_call_rerank_happy_path_orders_by_score() -> None:
    """Happy path: server returns 200 + items, we parse + sort by score desc."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json={
                "items": [
                    {"id": "q-3", "score": 0.95},
                    {"id": "q-7", "score": 0.50},
                    {"id": "q-1", "score": 0.10},
                ]
            },
        )
    )
    client = httpx.AsyncClient(transport=transport)
    try:
        result = await call_rerank(
            "分布式事务",
            _make_candidates(10),
            base_url="http://test.local",
            retry_once=False,
            client=client,
        )
    finally:
        await client.aclose()

    assert isinstance(result, RerankResult)
    assert result.degraded is False
    assert [it["id"] for it in result.items] == ["q-3", "q-7", "q-1"]


async def test_call_rerank_5xx_raises_unavailable_when_no_retry() -> None:
    """AC-07: /rerank returns 500; with retry disabled, raise immediately."""
    call_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, text="internal error")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    try:
        with pytest.raises(RerankUnavailableError):
            await call_rerank(
                "微服务",
                _make_candidates(5),
                base_url="http://test.local",
                retry_once=False,
                client=client,
            )
    finally:
        await client.aclose()
    assert call_count["n"] == 1


async def test_call_rerank_network_error_raises_unavailable() -> None:
    """AC-08: network unreachable → RerankUnavailableError raised."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    try:
        with pytest.raises(RerankUnavailableError):
            await call_rerank(
                "RAG",
                _make_candidates(3),
                base_url="http://test.local",
                retry_once=False,
                client=client,
            )
    finally:
        await client.aclose()


def test_fallback_to_input_order_marks_degraded() -> None:
    candidates = _make_candidates(5)
    result = fallback_to_input_order(candidates)
    assert result.degraded is True
    assert [it["id"] for it in result.items] == [c["id"] for c in candidates]


async def test_call_rerank_empty_candidates_returns_empty() -> None:
    """Edge case: no candidates → empty RerankResult, no HTTP call."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    try:
        result = await call_rerank(
            "anything",
            [],
            base_url="http://test.local",
            retry_once=False,
            client=client,
        )
    finally:
        await client.aclose()
    assert result.items == []
    assert result.degraded is False