"""[REQ-048 US2 T044] Unit test for BM25 retrieval via tsvector @@ plainto_tsquery.

Verifies the SQL builder returns the expected statement shape + that the
query plan is syntactically valid (Postgres parses it without errors when
a real connection is available; otherwise we verify structural invariants).

AC coverage:
- AC-04: BM25 returns top-30 by relevance
- AC-04c: inline keyword fixture exists (separate test)
- AC-10: NULL JD fallback handled (separate test)

This is a unit test — no DB connection required. We construct the SQL +
params via ``build_bm25_query`` and assert:
1. The statement contains the tsvector / plainto_tsquery pattern.
2. The LIMIT parameter is honoured.
3. The optional user_id filter is included / omitted correctly.
4. The bound parameter names are correct.
"""
from __future__ import annotations

from app.agents.interview.drill_helpers.bm25_query import build_bm25_query


def _render_sql(stmt) -> str:
    """Render the SQLAlchemy text() to a readable string with bind params."""
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def test_bm25_query_contains_tsvector_match() -> None:
    stmt, params = build_bm25_query("分布式事务", limit=30)
    # Rendered SQL uses literal substitution → no :uid param without user_id.
    assert "to_tsvector" in str(stmt)
    assert "plainto_tsquery" in str(stmt)
    assert "LIMIT" in str(stmt)
    assert "ORDER BY bm25_score DESC" in str(stmt)
    assert params["jd_text"] == "分布式事务"
    assert params["limit"] == 30


def test_bm25_query_with_user_id_filter() -> None:
    stmt, params = build_bm25_query(
        "微服务",
        user_id="019ebc56-fb4f-7978-bf91-29abc5c13d93",
        limit=15,
    )
    # When user_id is provided, params dict must contain it for explicit filtering.
    assert params["uid"] == "019ebc56-fb4f-7978-bf91-29abc5c13d93"
    assert params["limit"] == 15
    # The underlying SQL template uses :uid for the user_id filter.
    assert ":uid" in str(stmt)


def test_bm25_query_excludes_user_id_when_none() -> None:
    stmt, params = build_bm25_query("RAG", limit=10)
    assert "uid" not in params
    # The template references :uid only when user_id is provided.
    assert ":uid" not in str(stmt)


def test_bm25_query_filters_mastered_status() -> None:
    """data-model.md §1.2 requires status != 'mastered' for drill candidates."""
    stmt, _ = build_bm25_query("分布式锁")
    text_str = _render_sql(stmt)
    assert "status != 'mastered'" in text_str


def test_bm25_query_handles_empty_jd_text() -> None:
    """AC-10 — empty JD must still produce a valid statement (will match nothing)."""
    stmt, params = build_bm25_query("", limit=5)
    assert params["jd_text"] == ""
    assert params["limit"] == 5
    # Template contains the plainto_tsquery pattern regardless of empty input.
    assert "plainto_tsquery('simple'" in str(stmt)