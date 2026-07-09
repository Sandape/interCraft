"""[AC-040-US2 FR-004 + REQ-048 US6 T109] sink_error node — DB-only persistence
of low-scoring answers with frequency state machine integration.

Splits the legacy ``score_node`` into two responsibilities (US2 AC-4.4):

- ``score_llm`` (``score_llm.py``): LLM call only.
- ``sink_error`` (this file): conditional DB write to ``error_questions``
  when ``raw_score < ERROR_THRESHOLD``. **No LLM calls.**

REQ-048 US6 T109 — state machine integration:

- After UPSERT, calls ``app.modules.errors.service.reduce_status`` to
  determine the new (status, frequency) pair based on the existing row
  state. Detects ``mastered → practicing`` regressions (AC-27).
- Emits ``drill_resink_completed`` analytics event with the migration
  payload (regression_detected flag).
- **AC-29 hard constraint**: ``source_session_id`` is NEVER updated.
  The UPSERT path uses INSERT-with-original-session for new rows and
  ``score + answer_text + last_practiced_at`` UPDATE only for existing
  rows. No UPDATE statement touches ``source_session_id``.

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
import json
from uuid import UUID, uuid4, uuid5

import structlog
from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.agents.interview.config import SINK_ERROR_MAX_RETRIES
from app.agents.interview.state import InterviewGraphState
from app.core.db import get_session_context
from app.observability import traced_node

# Stable namespace for source_question_id derivation (UUID v5).
_SOURCE_NS = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
logger = structlog.get_logger(__name__)


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


# ---------------------------------------------------------------------------
# REQ-048 US6 T110 — analytics INSERT for drill_resink_completed.
# Best-effort: never raises (matches the production ``_record_analytics``
# pattern from drill_selector).
# ---------------------------------------------------------------------------


async def _write_analytics(
    *,
    user_id: str,
    event_type: str,
    payload: dict,
) -> None:
    blacklist = {"question_text", "score", "answer", "expected_points"}
    leaked = blacklist & set(payload.keys())
    if leaked:
        for k in leaked:
            payload.pop(k, None)
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        return
    try:
        async with get_session_context(user_id=user_uuid) as session:
            await session.execute(
                text(
                    "INSERT INTO analytics_events (user_id, event_type, payload) "
                    "VALUES (:uid, :etype, CAST(:payload AS jsonb))"
                ),
                {
                    "uid": str(user_uuid),
                    "etype": event_type,
                    "payload": json.dumps(payload, ensure_ascii=False),
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sink_error.analytics.insert_failed",
            event_type=event_type,
            exc=str(exc),
        )


# ---------------------------------------------------------------------------
# REQ-048 US6 T109 — state machine migration helpers.
# ---------------------------------------------------------------------------


def _next_status_and_frequency(
    *,
    current_status: str,
    current_frequency: int,
) -> tuple[str, int]:
    """Return (new_status, new_frequency) for a low-score re-sink.

    Mirrors the production app.modules.errors.service.reduce_status
    transitions. Returns the same status if the row was already mastered
    (no transition possible — caller logs a warning).

    Spec mapping (spec.md uses "reviewing" / production uses "practicing"
    in app.modules.errors.service.VALID_TRANSITIONS — these are the same
    concept; the user is back in the practice cycle after a fail).
    """
    # Local import to avoid circular deps at module-load time.
    from app.modules.errors.service import reduce_status

    if current_status == "mastered":
        # Regression: mastered → practicing (AC-27, requires the transition
        # supported by REQ-048 T032b + T109 VALID_TRANSITIONS update).
        try:
            return reduce_status(
                current_status="mastered",
                target_status="practicing",
                current_frequency=current_frequency,
                target_frequency=1,
            )
        except Exception:
            return current_status, current_frequency
    if current_status == "fresh":
        try:
            return reduce_status(
                current_status="fresh",
                target_status="practicing",
                current_frequency=current_frequency,
                target_frequency=2,
            )
        except Exception:
            return current_status, current_frequency
    if current_status == "practicing":
        # Direct frequency decrease (mirror of repo.recall()).
        return current_status, max(current_frequency - 1, 1)
    # archived or unknown — no-op.
    return current_status, current_frequency


async def _sink_to_error_book(
    state: InterviewGraphState,
    question_text: str,
    answer: str,
    dimension: str,
    score: int,
    current_q: int,
) -> None:
    """Persist a low-scoring question to error_questions (UPSERT) +
    REQ-048 US6 T109 state machine migration.

    Uses raw SQL (rather than the ``ErrorQuestionRepository`` wrapper) so
    the write path only depends on ``session.execute`` + ``session.commit``
    — both of which are easily mocked in tests, and the SQL is auditable
    without indirection through the repository ORM session.

    AC-29 hard constraint: source_session_id is NEVER updated. The UPDATE
    statement below targets only ``score`` / ``answer_text`` /
    ``last_practiced_at`` / ``status`` / ``frequency`` — never the
    ``source_session_id`` column. The INSERT path uses the current
    session_id as the original.

    Raises the underlying ``OperationalError`` on connection loss so the
    caller (this node) can decide how to retry / record.
    """
    thread_id = state.get("thread_id", "")
    user_id = state.get("user_id", "")
    if not thread_id or not user_id or not question_text:
        return

    source_session_id = UUID(thread_id)
    source_question_id = derive_source_qid(thread_id, current_q)

    find_sql = text(
        """SELECT id, status, frequency FROM error_questions
        WHERE user_id = :uid AND source_question_id = :qid
        LIMIT 1"""
    )
    insert_sql = text(
        """INSERT INTO error_questions
        (id, user_id, source_session_id, source_question_id, dimension,
         question_text, answer_text, score, status, frequency,
         last_practiced_at, created_at, updated_at)
        VALUES (:id, :uid, :sid, :qid, :dim, :qtext, :atext, :score,
                'fresh', 3, now(), now(), now())"""
    )
    # NOTE: this UPDATE statement intentionally does NOT touch
    # source_session_id. AC-29 / FR-042 hard constraint.
    update_sql = text(
        """UPDATE error_questions
        SET score = :score,
            answer_text = :atext,
            last_practiced_at = now(),
            updated_at = now()
        WHERE id = :id"""
    )
    # State machine UPDATE — separate statement so the column whitelist is
    # explicit (status + frequency only).
    update_state_sql = text(
        """UPDATE error_questions
        SET status = :status,
            frequency = :frequency,
            updated_at = now()
        WHERE id = :id"""
    )

    user_uuid = UUID(user_id)
    async with get_session_context(user_id=user_uuid) as session:
        existing_row = (
            await session.execute(
                find_sql,
                {
                    "uid": user_uuid,
                    "qid": source_question_id,
                },
            )
        ).first()

        if existing_row is not None:
            existing_id = existing_row[0]
            existing_status = existing_row[1] or "fresh"
            existing_frequency = int(existing_row[2] or 3)
            await session.execute(
                update_sql,
                {
                    "id": existing_id,
                    "atext": answer,
                    "score": score,
                },
            )
            # State machine migration (REQ-048 T109 + AC-27 regression).
            new_status, new_frequency = _next_status_and_frequency(
                current_status=existing_status,
                current_frequency=existing_frequency,
            )
            if (new_status, new_frequency) != (existing_status, existing_frequency):
                await session.execute(
                    update_state_sql,
                    {
                        "id": existing_id,
                        "status": new_status,
                        "frequency": new_frequency,
                    },
                )
            regression_detected = existing_status == "mastered" and new_status == "practicing"
            try:
                await _write_analytics(
                    user_id=user_id,
                    event_type="drill_resink_completed",
                    payload={
                        "source_question_id": str(source_question_id),
                        "old_status": existing_status,
                        "new_status": new_status,
                        "new_frequency": new_frequency,
                        "regression_detected": regression_detected,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("sink_error.analytics.emit_failed", exc=str(exc))
        else:
            await session.execute(
                insert_sql,
                {
                    "id": uuid4(),
                    "uid": user_uuid,
                    "sid": source_session_id,
                    "qid": source_question_id,
                    "dim": dimension,
                    "qtext": question_text[:2000],
                    "atext": answer,
                    "score": score,
                },
            )
            # First-time write — also emit analytics so the close-loop
            # dashboard surfaces the new error_questions row.
            try:
                await _write_analytics(
                    user_id=user_id,
                    event_type="drill_resink_completed",
                    payload={
                        "source_question_id": str(source_question_id),
                        "old_status": None,
                        "new_status": "fresh",
                        "new_frequency": 3,
                        "regression_detected": False,
                        "first_sink": True,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("sink_error.analytics.emit_failed", exc=str(exc))

        await session.commit()


@traced_node("interview.sink_error")
async def sink_error_node(state: InterviewGraphState) -> dict:
    """Persist the low-scoring answer to ``error_questions``.

    Reads ``raw_score`` and the latest score entry from state (set by
    ``score_llm``). Returns an empty state delta on success — the
    routing edge to ``interviewer`` runs next.

    REQ-048 US6 T109: the UPSERT is followed by a frequency state-machine
    migration (see ``_next_status_and_frequency``). Regression events
    (mastered → practicing) are recorded with ``regression_detected=true``.
    """
    scores = state.get("scores", [])
    latest = scores[-1] if scores else {}
    question_text = latest.get("question_text", "")
    if not question_text:
        question_no = int(latest.get("question_no", state.get("current_question", 0)) or 0)
        questions = state.get("questions", [])
        question_index = question_no - 1
        if 0 <= question_index < len(questions):
            question_text = questions[question_index].get("question", "")
        elif questions:
            question_text = questions[-1].get("question", "")
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
            # Error-book persistence is a side effect; do not block the
            # interview when schema drift or RLS/memory test data makes it fail.
            span = trace.get_current_span()
            span.set_status(StatusCode.ERROR, f"sink_error non-recoverable: {e}")
            span.record_exception(e)
            logger.warning("interview.sink_error.skipped", error=str(e), exc_info=True)
            last_exc = e
            break

    # On success the node returns an empty delta; routing edge → interviewer.
    return {"scores": scores}


__all__ = ["sink_error_node"]
