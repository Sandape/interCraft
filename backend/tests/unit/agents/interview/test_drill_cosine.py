"""[REQ-048 US2 T045] Unit test for cosine retrieval via pgvector <=>.

Verifies the SQL builder produces a syntactically valid query that uses
pgvector's ``<=>`` cosine distance operator.

AC coverage:
- AC-04: cosine returns top-30 by similarity
- AC-10: NULL embedding fallback handled (separate test)

This is a unit test — no DB connection required.
"""
from __future__ import annotations

from app.agents.interview.drill_helpers.cosine_query import (
    _format_vector,
    build_cosine_query,
)


def _fake_embedding(dim: int = 512) -> list[float]:
    return [0.01 * i for i in range(dim)]


def _render_sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def test_cosine_query_uses_pgvector_distance_operator() -> None:
    stmt, params = build_cosine_query(_fake_embedding(), limit=30)
    text_str = _render_sql(stmt)
    assert "<=>" in text_str
    assert "CAST(" in text_str
    assert "AS vector" in text_str
    assert "ORDER BY embedding <=>" in text_str
    assert params["limit"] == 30


def test_cosine_query_vector_literal_format() -> None:
    """The vector literal must be '[v1,v2,...]' format accepted by pgvector."""
    literal = _format_vector([0.1, -0.2, 0.3])
    assert literal.startswith("[")
    assert literal.endswith("]")
    assert "0.100000" in literal
    assert "-0.200000" in literal


def test_cosine_query_with_user_id_filter() -> None:
    stmt, params = build_cosine_query(
        _fake_embedding(),
        user_id="019ebc56-fb4f-7978-bf91-29abc5c13d93",
        limit=20,
    )
    assert params["uid"] == "019ebc56-fb4f-7978-bf91-29abc5c13d93"
    assert params["limit"] == 20
    # :uid is referenced in the SQL template when user_id is provided.
    assert ":uid" in str(stmt)


def test_cosine_query_excludes_null_embedding() -> None:
    """data-model.md §1.2 — embedding NULL rows must be filtered."""
    stmt, _ = build_cosine_query(_fake_embedding())
    text_str = _render_sql(stmt)
    assert "embedding IS NOT NULL" in text_str


def test_cosine_query_filters_mastered_status() -> None:
    stmt, _ = build_cosine_query(_fake_embedding())
    text_str = _render_sql(stmt)
    assert "status != 'mastered'" in text_str


def test_cosine_query_limit_default_is_30() -> None:
    stmt, params = build_cosine_query(_fake_embedding())
    assert params["limit"] == 30


def test_format_vector_handles_empty_list() -> None:
    assert _format_vector([]) == "[]"


def test_cosine_query_vector_param_contains_formatted_list() -> None:
    """The :qv bind param is the formatted vector literal (pgvector format)."""
    emb = [0.5, -0.5, 0.25]
    _, params = build_cosine_query(emb)
    assert "[0.500000,-0.500000,0.250000]" == params["qv"]