"""Regression tests for quick-drill selector fallback behavior."""
from __future__ import annotations

from types import SimpleNamespace


async def test_select_drill_candidates_ignores_empty_cache_and_uses_fallback(monkeypatch) -> None:
    from app.agents.interview.nodes import drill_selector

    calls: dict[str, int] = {"fallback": 0, "pipeline": 0}

    class EmptyCache:
        cache_key = "drill_cache:user:empty"
        source_question_ids: list[str] = []

    async def fake_fetch_error_pool_ids(user_id: str) -> list[str]:
        return ["source-1", "source-2", "source-3", "source-4", "source-5"]

    async def fake_get_cached(*args, **kwargs) -> EmptyCache:
        return EmptyCache()

    async def fake_materialise_cached_candidates(*args, **kwargs) -> list[dict]:
        return []

    async def fake_run_hybrid_pipeline(*args, **kwargs) -> list[dict]:
        calls["pipeline"] += 1
        return []

    async def fake_select_no_jd_fallback(user_id: str) -> list[dict]:
        calls["fallback"] += 1
        return [
            {
                "id": "error-1",
                "source_question_id": "source-1",
                "dimension": "tech_depth",
                "question_text": "Explain your RAG evaluation loop.",
            }
        ]

    async def fake_set_cached(*args, **kwargs) -> bool:
        return True

    async def fake_record_analytics(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(drill_selector, "get_redis", lambda: object())
    monkeypatch.setattr(drill_selector, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(drill_selector, "_fetch_error_pool_ids", fake_fetch_error_pool_ids)
    monkeypatch.setattr(drill_selector, "get_cached", fake_get_cached)
    monkeypatch.setattr(
        drill_selector,
        "_materialise_cached_candidates",
        fake_materialise_cached_candidates,
    )
    monkeypatch.setattr(drill_selector, "_run_hybrid_pipeline", fake_run_hybrid_pipeline)
    monkeypatch.setattr(drill_selector, "select_no_jd_fallback", fake_select_no_jd_fallback)
    monkeypatch.setattr(drill_selector, "set_cached", fake_set_cached)
    monkeypatch.setattr(drill_selector, "_record_analytics", fake_record_analytics)

    candidates = await drill_selector.select_drill_candidates(
        user_id="019f4b81-3712-7baa-b3fd-29df4a8488dc",
        jd_text="Agent workflow JD",
        top_k=5,
    )

    assert calls == {"fallback": 1, "pipeline": 1}
    assert candidates == [
        {
            "id": "error-1",
            "source_question_id": "source-1",
            "dimension": "tech_depth",
            "question_text": "Explain your RAG evaluation loop.",
        }
    ]
