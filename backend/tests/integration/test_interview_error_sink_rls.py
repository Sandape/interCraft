from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import text

from app.agents.interview.nodes.sink_error import derive_source_qid, _sink_to_error_book

pytestmark = [pytest.mark.integration]


async def test_sink_error_binds_rls_user_before_writing_error_question(
    client,
    db_session,
    user_a_headers,
) -> None:
    me = await client.get("/api/v1/users/me", headers=user_a_headers)
    assert me.status_code == 200, me.text
    user_id = UUID(me.json()["id"])

    created = await client.post(
        "/api/v1/interview-sessions",
        json={"position": "Frontend Engineer", "company": "RLS Probe", "mode": "text"},
        headers=user_a_headers,
    )
    assert created.status_code == 201, created.text
    session_id = UUID(created.json()["data"]["id"])

    await _sink_to_error_book(
        {"thread_id": str(session_id), "user_id": str(user_id)},
        "What causes stale closures in React?",
        "A stale closure captures old render state.",
        "tech_depth",
        3,
        1,
    )

    source_question_id = derive_source_qid(str(session_id), 1)
    await db_session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    row = (
        await db_session.execute(
            text(
                """SELECT user_id, source_session_id, source_question_id, score
                   FROM error_questions
                   WHERE source_question_id = :qid"""
            ),
            {"qid": source_question_id},
        )
    ).mappings().one()

    assert row["user_id"] == user_id
    assert row["source_session_id"] == session_id
    assert row["source_question_id"] == source_question_id
    assert row["score"] == 3
