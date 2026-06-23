"""023 US2 — Error Coach idle reconnect integration test.

Verifies: start → force checkpointer drop → submit 3 correct answers →
frequency decremented (3 → 2) and correct_count=3 in final state.

Per spec 023 US2 acceptance scenario 2: "frequency 正确从 3 减为 2".
"""
from __future__ import annotations

import json
import os
import secrets
import uuid

import pytest

pytestmark = [pytest.mark.integration]


def _scenario_path(scores: list[int]) -> str:
    """Write a mock-LLM scenario and return its path."""
    os.makedirs(
        os.path.join(os.path.dirname(__file__), "_mock_scenarios"),
        exist_ok=True,
    )
    path = os.path.join(
        os.path.dirname(__file__),
        "_mock_scenarios",
        f"ec_idle_{uuid.uuid4().hex[:8]}.json",
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "evaluate_scores": scores,
                "hint_contents": {
                    "small": "小提示",
                    "medium": "中等提示",
                    "detailed": "详细提示",
                },
            },
            f,
            ensure_ascii=False,
        )
    return path


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    """Enable mock LLM with three correct-answer scores."""
    monkeypatch.setenv("LLM_MOCK_MODE", "1")
    monkeypatch.setenv("LLM_MOCK_SCENARIO_PATH", _scenario_path([10, 10, 10]))
    yield


async def _register_user(client, suffix: str) -> tuple[dict, str]:
    """Register a fresh test user."""
    email = f"ec_idle_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": f"ec-idle-{suffix}",
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
    return headers, me.json()["id"]


async def _create_error_question(client, headers: dict, frequency: int = 3) -> str:
    """Create an error question with given frequency."""
    r = await client.post(
        "/api/v1/error-questions",
        headers=headers,
        json={
            "question_text": "023 idle test: 解释 useMemo 用法",
            "answer_text": "useMemo 缓存计算值。",
            "reference_answer_md": "useMemo 缓存计算值。",
            "dimension": "tech_depth",
            "score": 4,
        },
    )
    assert r.status_code == 201, r.text
    eq_id = r.json()["id"]

    # Manually bump frequency to 3 via PATCH (default is 1)
    patch = await client.patch(
        f"/api/v1/error-questions/{eq_id}",
        headers=headers,
        json={"frequency": frequency},
    )
    assert patch.status_code == 200, patch.text
    return eq_id


@pytest.mark.asyncio
async def test_error_coach_idle_reconnect_3_correct_decrements_frequency(client):
    """023 US2 — start, force-rebuild (simulate idle drop), submit 3 correct → freq 3→2."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.error_coach import get_error_coach_graph

    suffix = secrets.token_hex(8)
    headers, user_id = await _register_user(client, suffix)
    error_question_id = await _create_error_question(client, headers, frequency=3)

    graph = get_error_coach_graph()
    thread_id = await graph.start(
        user_id=user_id,
        error_question_id=error_question_id,
    )

    # First correct answer
    r1 = await graph.submit_answer(thread_id, "useMemo 缓存计算值。")
    assert r1 is not None

    # Simulate idle connection drop between round 1 and round 2.
    await _force_rebuild()

    # Second correct answer (after forced reconnect)
    r2 = await graph.submit_answer(thread_id, "useMemo 缓存计算值，避免重复执行。")
    assert r2 is not None

    # Force another drop between round 2 and round 3
    await _force_rebuild()

    # Third correct answer — completes the session
    r3 = await graph.submit_answer(thread_id, "useMemo 用于缓存昂贵的计算结果。")
    assert r3 is not None

    # Verify state
    state = await graph.get_state(thread_id)
    assert state["correct_count"] >= 3
    assert state["status"] == "completed"

    # Verify frequency was decremented from 3 to 2
    resp = await client.get(f"/api/v1/error-questions/{error_question_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    eq = resp.json()
    assert eq["frequency"] == 2, f"Expected frequency=2, got {eq['frequency']}"


@pytest.mark.asyncio
async def test_error_coach_abort_after_reconnect(client):
    """023 US2 — abort() must also survive a forced checkpointer drop."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.error_coach import get_error_coach_graph

    suffix = secrets.token_hex(8)
    headers, user_id = await _register_user(client, suffix)
    error_question_id = await _create_error_question(client, headers, frequency=3)

    graph = get_error_coach_graph()
    thread_id = await graph.start(user_id=user_id, error_question_id=error_question_id)

    await _force_rebuild()

    result = await graph.abort(thread_id)
    assert result is not None

    # frequency decremented (3 → 2) due to abort
    resp = await client.get(f"/api/v1/error-questions/{error_question_id}", headers=headers)
    assert resp.status_code == 200
    eq = resp.json()
    assert eq["frequency"] == 2, f"Expected frequency=2 after abort, got {eq['frequency']}"


@pytest.mark.asyncio
async def test_error_coach_submit_answer_retries_on_operational_error(monkeypatch):
    """023 US2 FR-007 — retry_graph_op retry branch exercised on error_coach path.

    Mocks build_graph so aget_state succeeds, aupdate_state succeeds, but
    ainvoke raises ``OperationalError("connection is closed")`` on first
    attempt and succeeds on second.  Asserts:

    - ``checkpointer_reconnect_total`` increments (FR-034)
    - The retry returns the second-attempt result
    - ainvoke was called twice (1 initial + 1 retry)
    """
    from unittest.mock import AsyncMock, patch

    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.error_coach import get_error_coach_graph
    from app.core.metrics import checkpointer_reconnect_total

    await _force_rebuild()
    before = checkpointer_reconnect_total._value.get()

    fake_state = AsyncMock()
    fake_state.values = {"user_id": "u1", "error_question_id": "eq1", "correct_count": 0}
    fake_state.next = ["evaluate"]

    fake_graph = AsyncMock()
    fake_graph.aget_state = AsyncMock(return_value=fake_state)
    fake_graph.aupdate_state = AsyncMock(return_value=None)
    call_count = 0

    async def flaky_ainvoke(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("connection is closed")
        # second attempt — correct_count still < 3 so no frequency decrement
        return {"correct_count": 1, "session_aborted": False}

    fake_graph.ainvoke = flaky_ainvoke

    graph = get_error_coach_graph()
    with (
        patch.object(graph, "build_graph", AsyncMock(return_value=fake_graph)),
        patch("app.agents.checkpointer._force_rebuild", new=AsyncMock()),
    ):
        result = await graph.submit_answer("tid-ec-retry", "test answer")

    assert call_count == 2, f"Expected 2 invocations, got {call_count}"
    assert result == {"correct_count": 1, "session_aborted": False}
    after = checkpointer_reconnect_total._value.get()
    assert after > before, (
        f"checkpointer_reconnect_total must inc on retry (before={before}, after={after})"
    )
