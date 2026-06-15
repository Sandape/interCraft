"""Backfill `question_text` and `user_answer` into existing interview_reports rows.

Why: `score.py` and `report.py` were updated to write these fields into the
`per_question_score` JSONB column, but reports generated before that change
don't have them. The original question text and the user's answer are still
recoverable from the LangGraph checkpointer (state["questions"] + state["messages"]).

Idempotent: skips rows that already have `question_text` populated.
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine

from app.agents.checkpointer import close_checkpointer, get_checkpointer, get_graph_config
from app.agents.interview.graph import get_interview_graph
from app.core.config import get_settings


async def _collect_user_answers(messages: list) -> list[str]:
    """Return the content of every HumanMessage/user dict in `messages`, in order."""
    out: list[str] = []
    for m in messages:
        if isinstance(m, dict):
            if m.get("role") == "user":
                out.append(m.get("content", "") or "")
        else:
            if getattr(m, "type", "") == "human":
                out.append(getattr(m, "content", "") or "")
    return out


async def _fetch_state(thread_id: str) -> tuple[list[dict], list[str]]:
    """Read the LangGraph state for a thread. Returns (questions, user_answers)."""
    graph = await get_interview_graph().build_graph()
    config = await get_graph_config(thread_id)
    state = await graph.aget_state(config)
    values = state.values if state.values else {}
    questions = values.get("questions", []) or []
    messages = values.get("messages", []) or []
    user_answers = await _collect_user_answers(messages)
    return questions, user_answers


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")

    backfilled = 0
    skipped = 0
    no_state = 0
    errored = 0

    async with engine.begin() as conn:
        # Set the demo user's GUC so RLS lets us see the rows.
        demo = (await conn.execute(text("SELECT id FROM users WHERE email = 'demo@intercraft.io'"))).scalar()
        if demo:
            await conn.execute(text(f"SET app.user_id = '{demo}'"))

        rows = (await conn.execute(text(
            """
            SELECT s.id, s.thread_id, r.per_question_score
            FROM interview_sessions s
            JOIN interview_reports r ON r.session_id = s.id
            WHERE s.status = 'completed'
            ORDER BY s.created_at DESC
            """
        ))).fetchall()

        print(f"Found {len(rows)} completed sessions with reports.")
        cp = await get_checkpointer()

        for session_id, thread_id, per_q in rows:
            # Historical bug: checkpoints are stored under `session_id`,
            # not the recorded `thread_id`. Try both keys; the second
            # is just a safety net for any future migration.
            lookup_keys = [str(session_id)]
            if thread_id and str(thread_id) != str(session_id):
                lookup_keys.append(str(thread_id))

            try:
                # Idempotency: skip if first entry already has question_text
                if per_q and isinstance(per_q, list) and per_q[0].get("question_text"):
                    skipped += 1
                    continue

                questions = None
                user_answers = None
                used_key = None
                for key in lookup_keys:
                    try:
                        qs, ua = await _fetch_state(key)
                    except Exception:
                        continue
                    if qs:
                        questions, user_answers, used_key = qs, ua, key
                        break

                if not questions:
                    no_state += 1
                    print(f"  [no-state] {session_id} keys={lookup_keys}")
                    continue

                # user_answers[0] is the self-intro at the intake step. Skip it.
                answers_for_questions = user_answers[1:1 + len(questions)]

                updated = []
                for i, q in enumerate(per_q):
                    new_q = dict(q)
                    if not new_q.get("question_text"):
                        new_q["question_text"] = questions[i].get("question", "")
                    if not new_q.get("user_answer"):
                        new_q["user_answer"] = (
                            answers_for_questions[i] if i < len(answers_for_questions) else ""
                        )
                    updated.append(new_q)

                await conn.execute(
                    text(
                        "UPDATE interview_reports SET per_question_score = :pqs "
                        "WHERE session_id = :sid"
                    ).bindparams(bindparam("pqs", type_=JSONB)),
                    {"pqs": updated, "sid": session_id},
                )
                backfilled += 1
                print(
                    f"  [backfilled] {session_id} via={used_key[:8]}… "
                    f"q[0]={updated[0].get('question_text', '')[:40]!r} "
                    f"a[0]={updated[0].get('user_answer', '')[:40]!r}"
                )
            except Exception as exc:
                errored += 1
                print(f"  [error] {session_id}: {exc}")

    await engine.dispose()
    await close_checkpointer()

    print()
    print(f"Summary: backfilled={backfilled} skipped={skipped} no_state={no_state} errored={errored}")
    return 0 if errored == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
