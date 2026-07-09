"""[REQ-048 US2 T053] Cross-encoder rerank call wrapper.

Calls the embedding service's ``POST /rerank`` endpoint (bge-reranker-v2-m3
cross-encoder) and returns the reranked candidates ordered by score.

Implements the failure-mode contract from AC-07 + AC-08:

- Returns the *unranked* candidate order with ``degraded=True`` when the
  rerank endpoint returns 5xx (after one retry) so the caller can choose
  to escalate to LLM listwise rerank (AC-07 fallback path).
- Raises ``RerankUnavailableError`` when the embedding service itself is
  unreachable — callers should fall back to BM25-only (AC-08).
- Returns ``degraded=False, items=[...]`` on the happy path.

The ``items`` shape mirrors what the cross-encoder endpoint returns:
``[{"id": <uuid>, "score": <float>}, ...]`` ordered by descending score.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RerankUnavailableError(RuntimeError):
    """Raised when the rerank endpoint is unreachable (network / 5xx after retries)."""


@dataclass
class RerankResult:
    items: list[dict[str, Any]]
    degraded: bool

    def __bool__(self) -> bool:  # pragma: no cover - convenience only
        return bool(self.items)


async def call_rerank(
    jd_text: str,
    candidates: list[dict[str, Any]],
    *,
    base_url: str,
    timeout_seconds: float = 30.0,
    model: str = "bge-reranker-v2-m3",
    retry_once: bool = True,
    client: httpx.AsyncClient | None = None,
) -> RerankResult:
    """POST /rerank with (JD, candidates) and return reranked top-N.

    Parameters
    ----------
    jd_text:
        The query side of the cross-encoder (the JD or role keywords).
    candidates:
        Up to 50 dicts each with at least ``{"id": <str>, "text": <str>}``.
        ``text`` is the question text used as the document side of the
        cross-encoder; ``id`` is opaque and is returned as-is.
    base_url:
        The embedding service base URL (``Settings.reranker_service_url``).
    timeout_seconds:
        Hard timeout per HTTP attempt (default 30s, matches
        ``Settings.reranker_timeout_seconds``).
    model:
        Cross-encoder model name (default bge-reranker-v2-m3 per
        data-model.md §2.2).
    retry_once:
        If ``True`` (default), retry once on 5xx before giving up.
    client:
        Optional pre-built ``httpx.AsyncClient`` (used by tests with
        ``httpx.MockTransport``). When ``None`` a fresh client is
        constructed per call.

    Returns
    -------
    RerankResult
        ``items`` are ordered by descending reranker score. ``degraded=True``
        indicates we fell back to the original candidate order (no rerank
        applied) — AC-07 path. ``degraded=False`` means the cross-encoder
        succeeded.

    Raises
    ------
    RerankUnavailableError
        When the embedding service is unreachable (network error / 5xx
        after retry). Caller should fall back to BM25-only (AC-08 path).
    """
    if not candidates:
        return RerankResult(items=[], degraded=False)

    payload = {
        "model": model,
        "query": jd_text,
        "documents": [
            {"id": str(c.get("id", "")), "text": str(c.get("text", ""))}
            for c in candidates
        ],
    }

    last_exc: Exception | None = None
    max_attempts = 2 if retry_once else 1
    for attempt in range(1, max_attempts + 1):
        try:
            if client is not None:
                r = await client.post(
                    f"{base_url.rstrip('/')}/rerank",
                    json=payload,
                )
            else:
                async with httpx.AsyncClient(timeout=timeout_seconds) as c:
                    r = await c.post(
                        f"{base_url.rstrip('/')}/rerank",
                        json=payload,
                    )
            if r.status_code >= 500:
                # Server-side failure → retry once if allowed.
                if retry_once and attempt == 1:
                    logger.warning(
                        "drill.rerank.5xx_retry",
                        status=r.status_code,
                        body=r.text[:200],
                    )
                    continue
                raise RerankUnavailableError(
                    f"rerank returned {r.status_code}: {r.text[:200]}"
                )
            r.raise_for_status()
            data = r.json()
            items = data.get("items") or data.get("results") or []
            # Normalise: each item must have id + score.
            normalised = [
                {"id": str(it.get("id", "")), "score": float(it.get("score", 0.0))}
                for it in items
            ]
            normalised.sort(key=lambda x: x["score"], reverse=True)
            return RerankResult(items=normalised, degraded=False)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            last_exc = exc
            if retry_once and attempt == 1:
                logger.warning(
                    "drill.rerank.network_retry",
                    exc=str(exc),
                )
                continue
            raise RerankUnavailableError(f"rerank unreachable: {exc}") from exc

    # Should not reach here, but guard for safety.
    raise RerankUnavailableError(f"rerank unreachable: {last_exc}")


def fallback_to_input_order(candidates: list[dict[str, Any]]) -> RerankResult:
    """Return the candidates unchanged with degraded=True.

    Used when rerank is unavailable but the caller wants to continue with
    the BM25/cosine order rather than failing the entire drill (AC-07 path).
    """
    items = [
        {"id": str(c.get("id", "")), "score": 0.0}
        for c in candidates
    ]
    return RerankResult(items=items, degraded=True)


__all__ = ["RerankResult", "RerankUnavailableError", "call_rerank", "fallback_to_input_order"]