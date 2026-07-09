"""[REQ-048 US2 T051] BM25 retrieval via Postgres tsvector @@ plainto_tsquery.

Returns top-N error_questions ranked by full-text search relevance against the
job description (JD) keywords. Uses the GIN index ``idx_error_questions_tsvector``
(created in migration 0029_error_questions_embedding.py) on
``to_tsvector('simple', question_text || ' ' || coalesce(answer_text, ''))``.

The query is a SQL builder helper (returns ``sqlalchemy.text`` + params dict)
so the caller can use whatever session is available. RLS is the caller's
responsibility — apply ``SET LOCAL app.user_id = ...`` before invoking.
"""
from __future__ import annotations

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import ClauseElement


def build_bm25_query(
    jd_text: str,
    *,
    user_id: str | None = None,
    limit: int = 30,
) -> tuple[ClauseElement, dict[str, object]]:
    """Build a tsvector @@ plainto_tsquery SQL builder for BM25-style retrieval.

    Parameters
    ----------
    jd_text:
        The job description / role keywords to search against.
    user_id:
        Optional RLS-style filter; if provided the query additionally
        constrains ``user_id = :uid`` for explicit isolation (defence in
        depth on top of the row-level security policy).
    limit:
        Maximum number of rows to return (default 30 per data-model.md §5).

    Returns
    -------
    (ClauseElement, dict)
        ``(sqlalchemy.text(stmt), params)`` ready for ``session.execute``.

    Notes
    -----
    - Uses ``to_tsquery`` with the **simple** text search configuration so
      CJK characters pass through as tokens. ``simple`` is the right choice
      for Chinese without jieba; the production search-time tokenizer
      (FlagEmbedding / bm25 transformer) is separate from the tsvector
      column which is used for coarse pre-filtering.
    - Filters out ``status='mastered'`` per the data-model.md backfill
      policy so the user never sees "我已经会了" questions in drill.
    - Returns rows ordered by ``ts_rank`` descending (the BM25 proxy in
      Postgres). True BM25 ranking requires ``pg_trgm`` + an external
      scorer; the tsvector @@ plainto_tsquery path is the lightweight
      in-database fallback (US2 spec R-3 "BM25 + cosine + cross-encoder
      Hybrid" — R-3 spec text calls it "BM25", the in-Postgres mapping is
      tsvector full-text search).
    """
    user_filter = "AND user_id = :uid" if user_id else ""
    stmt = text(
        f"""
        SELECT
            id,
            source_session_id,
            source_question_id,
            dimension,
            question_text,
            ts_rank(
                to_tsvector('simple', coalesce(question_text, '') || ' ' || coalesce(answer_text, '')),
                plainto_tsquery('simple', :jd_text)
            ) AS bm25_score
        FROM error_questions
        WHERE
            deleted_at IS NULL
            AND status != 'mastered'
            AND to_tsvector('simple', coalesce(question_text, '') || ' ' || coalesce(answer_text, ''))
                @@ plainto_tsquery('simple', :jd_text)
            {user_filter}
        ORDER BY bm25_score DESC, updated_at DESC
        LIMIT :limit
        """
    )
    params: dict[str, object] = {"jd_text": jd_text or "", "limit": int(limit)}
    if user_id:
        params["uid"] = user_id
    return stmt, params


# Re-export JSONB / bindparam for callers that want to compose with jsonb binds.
__all__ = ["build_bm25_query", "JSONB", "bindparam"]