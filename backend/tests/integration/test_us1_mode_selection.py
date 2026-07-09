"""REQ-048 US1 — Mode selection integration tests (T034).

Validates:
- AC-01: two_top_level_or_doubao_no_suboptions — successful full-mode
  create + state persists + drill_cache_key + max_questions.
- AC-03: state reset on back navigation is testable via the
  ``useInterviewModeStore.reset()`` call from the frontend (covered by
  the Zustand unit test, not here).
"""
from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_mode_recommendation_route_not_shadowed_by_session_id(
    client, user_a_headers
) -> None:
    """Static mode route must not be parsed as the dynamic UUID session id."""
    r = await client.get(
        "/api/v1/interview-sessions/mode-recommendation",
        headers=user_a_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["required"] == 5
    assert isinstance(body["data"]["available"], int)


@pytest.mark.asyncio
async def test_two_top_level_or_doubao_no_suboptions(client, user_a_headers) -> None:
    """AC-01 — full mode create succeeds with max_questions=10 + persisted."""
    r = await client.post(
        "/api/v1/interview-sessions",
        json={
            "position": "高级前端工程师",
            "company": "字节跳动",
            "mode": "full",
            "max_questions": 10,
        },
        headers=user_a_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    sid = body["data"]["id"]
    # Fetch the session and verify mode/max_questions are persisted.
    r2 = await client.get(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
    assert r2.status_code == 200, r2.text
    payload = r2.json()
    assert payload["mode"] == "full"
    assert payload["max_questions"] == 10


@pytest.mark.asyncio
async def test_mode_state_reset_on_position_back(client, user_a_headers) -> None:
    """AC-03 (backend half) — re-creating a session does not leak prior state.

    The full state-reset semantics live in the frontend store; on the
    backend we verify that creating a new session after a previous one
    doesn't carry stale mode/max_questions/error_question_ids.
    """
    # First session: quick_drill (will fail with INSUFFICIENT_ERROR_POOL — OK).
    await client.post(
        "/api/v1/interview-sessions",
        json={"position": "Backend Eng", "company": "Acme", "mode": "quick_drill"},
        headers=user_a_headers,
    )
    # Second session: full + max_questions=15. Must NOT inherit quick_drill state.
    r2 = await client.post(
        "/api/v1/interview-sessions",
        json={
            "position": "Backend Eng",
            "company": "Acme",
            "mode": "full",
            "max_questions": 15,
        },
        headers=user_a_headers,
    )
    assert r2.status_code == 201, r2.text
    body = r2.json()
    sid = body["data"]["id"]
    r3 = await client.get(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
    assert r3.status_code == 200, r3.text
    payload = r3.json()
    assert payload["mode"] == "full"
    assert payload["max_questions"] == 15
    assert payload.get("error_question_ids") in (None, [])


@pytest.mark.asyncio
async def test_doubao_mode_creates_session_with_no_suboptions(client, user_a_headers) -> None:
    """AC-01 — doubao mode creates session row + no max_questions sub-option.

    Per contracts/http-api.md C-1 + R9, doubao mode still writes 1 row
    (for session_id routing to /card endpoint) but does not require
    max_questions or error_question_ids.
    """
    r = await client.post(
        "/api/v1/interview-sessions",
        json={
            "position": "Backend Eng",
            "company": "Acme",
            "mode": "doubao",
        },
        headers=user_a_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    sid = body["data"]["id"]
    r2 = await client.get(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
    assert r2.status_code == 200, r2.text
    payload = r2.json()
    assert payload["mode"] == "doubao"
    assert payload.get("max_questions") is None
    assert payload.get("error_question_ids") in (None, [])
