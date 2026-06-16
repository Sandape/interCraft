"""Integration test: interview completion -> ability_dimensions sync (Feature 018, defect #9).

Per Constitution III: tests must FAIL before implementation.

The interview report's `dimension_scores` must be reflected in the user's
`ability_dimensions` table synchronously when the interview completes — not
only via the async ARQ `ability_diagnose` worker. This avoids the race
condition where `/ability-profile` returns all-zero dimensions moments after
interview completion.

Scope of this test: the `_sync_ability_dimensions` private method on
`InterviewSessionService`. End-to-end through LangGraph submit_answer is
covered by E2E specs in `e2e/` and by the manual demo in
`specs/018-fix-product-defects/quickstart.md`.
"""
from __future__ import annotations

import json
import uuid
from uuid import UUID

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration]


_DIMENSION_KEYS = (
    "tech_depth", "architecture", "engineering_practice",
    "communication", "algorithm", "business",
)


async def _get_user_id(db_session, email: str) -> UUID | None:
    result = await db_session.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": email}
    )
    row = result.fetchone()
    return row[0] if row else None


async def _seed_via_register(client, suffix: str) -> tuple[dict, UUID]:
    """Register a fresh user via API → ability_dimensions are auto-seeded.

    Returns (headers, user_id). Reads user_id back via the API (RLS-safe).
    """
    email = f"sync_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": f"sync-{suffix}",
            "device_fingerprint": fp,
        },
        headers={"X-Device-Fingerprint": fp},
    )
    assert reg.status_code in (200, 201), reg.text
    access = reg.json()["tokens"]["access_token"]
    headers = {
        "Authorization": f"Bearer {access}",
        "X-Device-Fingerprint": fp,
    }
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, UUID(me.json()["id"])


async def _insert_completed_session_with_report(
    db_session, user_id: UUID, dimension_scores: dict[str, float]
) -> UUID:
    """Insert an interview_session + interview_report directly.

    Sets the RLS `app.user_id` GUC before each INSERT so the policy check
    `user_id = current_setting('app.user_id')::uuid` passes.
    """
    from sqlalchemy import bindparam
    from sqlalchemy.dialects.postgresql import JSONB

    session_id = uuid.uuid4()
    avg = sum(dimension_scores.values()) / max(len(dimension_scores), 1)

    await db_session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    await db_session.execute(
        text(
            """INSERT INTO interview_sessions
               (id, user_id, position, company, mode, status, thread_id,
                started_at, ended_at)
               VALUES (:id, :uid, 'Backend', 'ACME', 'text', 'completed',
                       :tid, now() - interval '30 minutes', now())"""
        ),
        {"id": session_id, "uid": user_id, "tid": str(session_id)},
    )
    await db_session.commit()

    await db_session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    insert_report = text(
        """INSERT INTO interview_reports
           (id, session_id, overall_score, per_question_score,
            dimension_scores, strengths, improvements, summary_md)
           VALUES (:id, :sid, :os, '[]'::jsonb, :ds,
                   '[]'::jsonb, '[]'::jsonb, 'sync test')"""
    ).bindparams(bindparam("ds", type_=JSONB))
    await db_session.execute(
        insert_report,
        {
            "id": uuid.uuid4(),
            "sid": session_id,
            "os": avg,
            "ds": dimension_scores,
        },
    )
    await db_session.commit()
    return session_id


async def _fetch_dimensions(db_session, user_id: UUID) -> dict[str, tuple[float, str]]:
    """Read dimensions as the owning user (RLS-scoped)."""
    await db_session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    result = await db_session.execute(
        text(
            """SELECT dimension_key, actual_score, source
               FROM ability_dimensions
               WHERE user_id = :uid
               ORDER BY dimension_key"""
        ),
        {"uid": user_id},
    )
    return {row[0]: (float(row[1]), row[2]) for row in result.fetchall()}


@pytest.mark.asyncio
async def test_sync_upserts_interview_dimensions_with_interview_source(client, db_session):
    """Defect #9: per-dimension scores from the report land in ability_dimensions
    synchronously, with source='interview'."""
    from app.core.db import _session_cm
    from app.modules.interviews.service import InterviewSessionService

    suffix = uuid.uuid4().hex[:8]
    _headers, user_id = await _seed_via_register(client, suffix)
    dimension_scores = {"tech_depth": 7.5, "communication": 6.0}
    session_id = await _insert_completed_session_with_report(
        db_session, user_id, dimension_scores
    )

    async with _session_cm() as sync_session:
        await sync_session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )
        svc = InterviewSessionService(sync_session)
        await svc._sync_ability_dimensions(session_id, user_id)
        await sync_session.commit()

    dims = await _fetch_dimensions(db_session, user_id)

    assert dims["tech_depth"][0] == pytest.approx(7.5, abs=0.01), (
        f"tech_depth: expected 7.5, got {dims['tech_depth'][0]}"
    )
    assert dims["tech_depth"][1] == "interview", (
        f"tech_depth source: expected 'interview', got {dims['tech_depth'][1]}"
    )
    assert dims["communication"][0] == pytest.approx(6.0, abs=0.01)
    assert dims["communication"][1] == "interview"

    assert dims["algorithm"][0] == 0.0
    assert dims["algorithm"][1] == "manual"
    assert dims["architecture"][0] == 0.0
    assert dims["architecture"][1] == "manual"


@pytest.mark.asyncio
async def test_sync_is_noop_when_no_report_exists(client, db_session):
    """Defensive: if no interview_report row exists, sync must not raise."""
    from app.core.db import _session_cm
    from app.modules.interviews.service import InterviewSessionService

    suffix = uuid.uuid4().hex[:8]
    _headers, user_id = await _seed_via_register(client, suffix)
    session_id = uuid.uuid4()

    await db_session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    await db_session.execute(
        text(
            """INSERT INTO interview_sessions
               (id, user_id, position, company, mode, status, thread_id)
               VALUES (:id, :uid, 'Backend', 'ACME', 'text', 'completed', :tid)"""
        ),
        {"id": session_id, "uid": user_id, "tid": str(session_id)},
    )
    await db_session.commit()

    async with _session_cm() as sync_session:
        await sync_session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )
        svc = InterviewSessionService(sync_session)
        # Must not raise
        await svc._sync_ability_dimensions(session_id, user_id)
        await sync_session.commit()

    dims = await _fetch_dimensions(db_session, user_id)
    for dim_key in _DIMENSION_KEYS:
        assert dims[dim_key][0] == 0.0
        assert dims[dim_key][1] == "manual"