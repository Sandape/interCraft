"""[AC-040-US2 FR-004] sink_error node — DB-only persistence of low-scoring answers.

Splits the legacy ``score_node`` into two responsibilities (US2 AC-4.4):

- ``score_llm`` (``score_llm.py``): LLM call only.
- ``sink_error`` (this file): conditional DB write to ``error_questions``
  when ``raw_score < ERROR_THRESHOLD``. **No LLM calls.**

Routing table (set in ``graph.py``):

- ``raw_score < ERROR_THRESHOLD`` → ``sink_error`` (this node).
- ``sink_error`` always returns to ``interviewer`` so the next question is
  asked (matches legacy behaviour: ``interrupt_before=["score"]`` was the
  HITL gate on DB-write side; we keep that gate here, AC-4.9).

US2 AC-4.7a (per-node retry):

- This function has its own ``for attempt in range(SINK_ERROR_MAX_RETRIES):``
  loop with explicit ``OperationalError`` handling.
- ``score_llm`` is **NOT** re-invoked on retry — the retry is local to the
  DB-write attempt only.
- On every failed attempt the OTel span records the exception via the
  explicit ``trace.get_current_span().record_exception(e)`` + ``set_status``
  call (R1''' P0 — bypasses ``traced_node`` fail-open swallowing so the
  span is marked ERROR even if the exception is re-raised outside the
  decorator context).
"""
from __future__ import annotations

import asyncio
from uuid import UUID, uuid4, uuid5

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy.exc import OperationalError

from app.agents.interview.config import SINK_ERROR_MAX_RETRIES
from app.agents.interview.state import InterviewGraphState
from app.core.db import get_session_context
from app.observability import traced_node

# Stable namespace for source_question_id derivation (UUID v5).
_SOURCE_NS = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def derive_source_qid(session_id: str, question_no: int) -> UUID:
    """Deterministic source_question_id = UUID5(session_id, str(question_no)).

    Public name (no underscore prefix) so callers / re-export shells can
    import it. Was previously ``_derive_source_qid`` in
    ``app.agents.interview.nodes.score`` (kept backward-compat alias).
    """
    return uuid5(UUID(session_id), str(question_no))


# Backward-compat alias for tests / external callers that imported the
# private name from the legacy ``score`` module.
_derive_source_qid = derive_source_qid


async def _sink_to_error_book(
    state: InterviewGraphState,
    question_text: str,
    answer: str,
    dimension: str,
    score: int,
    current_q: int,
) -> None:
    """Persist a low-scoring question to error_questions (UPSERT).

    Uses raw SQL (rather than the ``ErrorQuestionRepository`` wrapper) so
    the write path only depends on ``session.execute`` + ``session.commit``
    — both of which are easily mocked in tests, and the SQL is auditable
    without indirection through the repository ORM session.

    Raises the underlying ``OperationalError`` on connection loss so the
    caller (this node) can decide how to retry / record.
    """
    from sqlalchemy import text

    thread_id = state.get("thread_id", "")
    user_id = state.get("user_id", "")
    if not thread_id or not user_id:
        return

    source_session_id = UUID(thread_id)
    source_question_id = derive_source_qid(thread_id, current_q)

    upsert_sql = text(
        """INSERT INTO error_questions
        (id, user_id, source_session_id, source_question_id, dimension,
         question_text, answer_text, score, created_at, updated_at)
        VALUES (:id, :uid, :sid, :qid, :dim, :qtext, :atext, :score, now(), now())
        ON CONFLICT (user_id, source_question_id) DO UPDATE
        SET score = EXCLUDED.score,
            answer_text = EXCLUDED.answer_text,
            updated_at = now()"""
    )

    async with get_session_context() as session:
        await session.execute(
            upsert_sql,
            {
                "id": uuid4(),
                "uid": UUID(user_id),
                "sid": source_session_id,
                "qid": source_question_id,
                "dim": dimension,
                "qtext": question_text[:2000],
                "atext": answer,
                "score": score,
            },
        )
        await session.commit()


@traced_node("interview.sink_error")
async def sink_error_node(state: InterviewGraphState) -> dict:
    """Persist the low-scoring answer to ``error_questions``.

    Reads ``raw_score`` and the latest score entry from state (set by
    ``score_llm``). Returns an empty state delta on success — the
    routing edge to ``interviewer`` runs next.
    """
    scores = state.get("scores", [])
    latest = scores[-1] if scores else {}
    question_text = latest.get("question_text", "")
    answer = latest.get("user_answer", "")
    dimension = latest.get("dimension", "tech_depth")
    score = int(latest.get("score", 0))
    current_q = state.get("current_question", 0)

    last_exc: Exception | None = None
    for attempt in range(1, SINK_ERROR_MAX_RETRIES + 1):
        try:
            await _sink_to_error_book(
                state, question_text, answer, dimension, score, current_q,
            )
            last_exc = None
            break
        except OperationalError as e:
            # R1''' P0: explicit OTel API inside the node body (do not rely
            # on traced_node fail-open). The span context is the current
            # traced_node span — record the failure so it shows up in
            # LangSmith even if the retry succeeds on the next attempt.
            span = trace.get_current_span()
            span.set_status(StatusCode.ERROR, f"sink_error attempt {attempt} failed: {e}")
            span.record_exception(e)
            last_exc = e
            if attempt >= SINK_ERROR_MAX_RETRIES:
                # Out of retries: re-raise so @traced_node records ERROR on
                # the outer span AND graph state propagates the failure.
                raise
            # Exponential backoff (0.1s, 0.2s, ... capped at 1.0s).
            await asyncio.sleep(min(0.1 * (2 ** (attempt - 1)), 1.0))
        except Exception as e:
            # Non-reconnectable: record + re-raise immediately.
            span = trace.get_current_span()
            span.set_status(StatusCode.ERROR, f"sink_error non-recoverable: {e}")
            span.record_exception(e)
            raise

    # On success the node returns an empty delta; routing edge → interviewer.
    return {}


__all__ = ["sink_error_node"]