"""[REQ-048 US2 T052] Cosine retrieval via pgvector ``<=>`` distance.

Returns top-N error_questions ranked by cosine distance against the JD
embedding (bge-small-zh-v1.5, 512-dimensional ``vector(512)`` column on
``error_questions.embedding`` created in migration
``0029_error_questions_embedding.py``).

The query uses ``pgvector``'s ``<=>`` cosine distance operator. The HNSW
index on the embedding column is ``idx_error_questions_embedding`` (US2
data-model.md §1.2).

Behaviour
---------
- Filters out rows where ``embedding IS NULL`` so the index hits cleanly.
- Filters out ``status='mastered'`` per the data-model.md backfill policy.
- Optionally accepts ``user_id`` for explicit RLS-style isolation (defence
  in depth on top of the row-level security policy).
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy.sql import ClauseElement
from sqlalchemy.sql import text


def build_cosine_query(
    jd_embedding: Sequence[float],
    *,
    user_id: str | None = None,
    limit: int = 30,
) -> tuple[ClauseElement, dict[str, object]]:
    """Build a pgvector cosine-distance SQL builder.

    Parameters
    ----------
    jd_embedding:
        The 512-dim embedding of the JD text (from
        ``EmbeddingServiceClient.embed([jd_text])``). Must have length
        matching the column's ``vector(N)`` dimensionality; the caller is
        responsible for asserting length 512 (bge-small-zh-v1.5).
    user_id:
        Optional explicit user_id filter (defence in depth).
    limit:
        Maximum rows (default 30 per data-model.md §5).

    Returns
    -------
    (ClauseElement, dict)
        ``(sqlalchemy.text(stmt), params)``. The embedding is bound as a
        PostgreSQL ``vector`` literal — pgvector accepts the
        ``'[v1,v2,...]'`` literal form which we construct at SQL-build
        time. No JSONB-binds caveat applies here; the dimension list is
        a constant string parameterised by the caller.

    Notes
    -----
    - Cosine distance in pgvector is ``1 - cosine_similarity``. Smaller
      distance == more similar. ORDER BY ascending ``embedding <=> :qv``.
    - The embedding list must be coerced to a PostgreSQL ``vector`` literal.
      We render it inline (not parameterised) because pgvector's adapter
      doesn't accept Python lists as bind params — see ``_format_vector``.
    """
    user_filter = "AND user_id = :uid" if user_id else ""
    vector_literal = _format_vector(jd_embedding)
    stmt = text(
        f"""
        SELECT
            id,
            source_session_id,
            source_question_id,
            dimension,
            question_text,
            (embedding <=> CAST(:qv AS vector)) AS cosine_distance
        FROM error_questions
        WHERE
            deleted_at IS NULL
            AND status != 'mastered'
            AND embedding IS NOT NULL
            {user_filter}
        ORDER BY embedding <=> CAST(:qv AS vector)
        LIMIT :limit
        """
    )
    params: dict[str, object] = {
        "qv": vector_literal,
        "limit": int(limit),
    }
    if user_id:
        params["uid"] = user_id
    return stmt, params


def _format_vector(values: Sequence[float]) -> str:
    """Render a Python sequence of floats as a pgvector literal string.

    Example: ``[0.1, -0.2, 0.3]`` -> ``'[0.1,-0.2,0.3]'``.

    Why inline rather than bind: pgvector's asyncpg dialect does not
    natively accept Python ``list[float]`` as a bind parameter. The
    canonical workaround is to render the literal at SQL-build time and
    cast to ``vector`` in SQL. The values are caller-controlled (no SQL
    injection vector), so this is safe.
    """
    return "[" + ",".join(f"{float(v):.6f}" for v in values) + "]"


__all__ = ["build_cosine_query", "_format_vector"]