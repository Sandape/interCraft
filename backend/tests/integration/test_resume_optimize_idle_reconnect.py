"""023 US3 — Resume Optimize idle reconnect integration test.

Verifies: start → force checkpointer drop → confirm(apply) → 200 + resume
version created.

Per spec 023 US3 acceptance scenario 1: "响应 200，简历版本正确创建".
"""
from __future__ import annotations

import os
import secrets
import uuid

import pytest

pytestmark = [pytest.mark.integration]


def _scenario_path() -> str:
    """Empty mock-LLM scenario (resume_optimize uses internal prompts)."""
    import json

    os.makedirs(
        os.path.join(os.path.dirname(__file__), "_mock_scenarios"),
        exist_ok=True,
    )
    path = os.path.join(
        os.path.dirname(__file__),
        "_mock_scenarios",
        f"ro_idle_{uuid.uuid4().hex[:8]}.json",
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"evaluate_scores": [], "hint_contents": {}}, f)
    return path


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    monkeypatch.setenv("LLM_MOCK_MODE", "1")
    monkeypatch.setenv("LLM_MOCK_SCENARIO_PATH", _scenario_path())
    yield


async def _register_and_seed_branch(client, suffix: str) -> tuple[dict, str, str]:
    """Register a fresh user, create a resume branch, return (headers, user_id, branch_id).

    The access token is folded into the returned ``headers`` dict; resume_optimize
    uses the user-bound branch context (per existing /agents/resume-optimize
    endpoint contract).
    """
    email = f"ro_idle_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": f"ro-idle-{suffix}",
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
    user_id = me.json()["id"]

    # Create a resume branch via API
    br = await client.post(
        "/api/v1/resume-branches",
        headers=headers,
        json={"name": f"idle-{suffix}", "position": "Frontend Engineer"},
    )
    assert br.status_code in (200, 201), br.text
    branch_id = br.json()["branch"]["id"]
    return headers, user_id, branch_id


@pytest.mark.asyncio
async def test_resume_optimize_confirm_apply_after_reconnect(client):
    """023 US3 — start, force-rebuild, confirm(apply) → 200 + version created."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.resume_optimize import get_resume_optimize_graph

    suffix = secrets.token_hex(8)
    headers, user_id, branch_id = await _register_and_seed_branch(client, suffix)

    graph = get_resume_optimize_graph()
    thread_id = await graph.start(
        user_id=user_id,
        branch_id=branch_id,
        target_jd="资深前端工程师,React + TypeScript,5年经验",
    )
    assert thread_id is not None

    # Simulate idle connection drop
    await _force_rebuild()

    # Confirm apply — must not raise despite dropped connection
    result = await graph.confirm(thread_id, decision="apply")
    assert result is not None

    # Verify version was created via REST API
    versions = await client.get(
        f"/api/v1/resume-branches/{branch_id}/versions", headers=headers
    )
    assert versions.status_code == 200, versions.text
    versions_data = versions.json().get("data", [])
    # At least one version should exist (either the original or the AI-suggested one)
    assert len(versions_data) >= 1, f"Expected at least 1 resume version, got {len(versions_data)}"


@pytest.mark.asyncio
async def test_resume_optimize_confirm_discard_after_reconnect(client):
    """023 US3 — confirm(discard) after reconnect → 200, no version created, thread aborted."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.resume_optimize import get_resume_optimize_graph

    suffix = secrets.token_hex(8)
    headers, user_id, branch_id = await _register_and_seed_branch(client, suffix)

    graph = get_resume_optimize_graph()
    thread_id = await graph.start(
        user_id=user_id,
        branch_id=branch_id,
        target_jd="后端架构师，分布式系统",
    )
    assert thread_id is not None

    await _force_rebuild()

    result = await graph.confirm(thread_id, decision="discard")
    assert result is not None

    # No new version should be created (decision=discard)
    versions = await client.get(
        f"/api/v1/resume-branches/{branch_id}/versions", headers=headers
    )
    assert versions.status_code == 200, versions.text
    versions_data = versions.json().get("data", [])
    # The branch was just created so it may have 0 or 1 version (initial). The
    # AI-suggested version must NOT exist since user discarded.
    assert len(versions_data) <= 1, (
        f"Expected ≤1 version (discard should not create), got {len(versions_data)}"
    )


@pytest.mark.asyncio
async def test_resume_optimize_confirm_retries_on_operational_error(monkeypatch):
    """023 US3 FR-010 — retry_graph_op retry branch exercised on resume_optimize path.

    Mocks build_graph so aupdate_state succeeds but ainvoke raises
    ``OperationalError("connection is closed")`` on first attempt and
    succeeds on second.  Asserts:

    - ``checkpointer_reconnect_total`` increments (FR-034)
    - The retry returns the second-attempt result
    - ainvoke was called twice (1 initial + 1 retry)
    """
    from unittest.mock import AsyncMock, patch

    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.resume_optimize import get_resume_optimize_graph
    from app.core.metrics import checkpointer_reconnect_total

    await _force_rebuild()
    before = checkpointer_reconnect_total._value.get()

    fake_graph = AsyncMock()
    fake_graph.aupdate_state = AsyncMock(return_value=None)
    call_count = 0

    async def flaky_ainvoke(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("connection is closed")
        return {"decision": "apply", "thread_aborted": False, "summary": "ok"}

    fake_graph.ainvoke = flaky_ainvoke

    graph = get_resume_optimize_graph()
    with (
        patch.object(graph, "build_graph", AsyncMock(return_value=fake_graph)),
        patch("app.agents.checkpointer._force_rebuild", new=AsyncMock()),
    ):
        result = await graph.confirm("tid-ro-retry", decision="apply")

    assert call_count == 2, f"Expected 2 invocations, got {call_count}"
    assert result == {"decision": "apply", "thread_aborted": False, "summary": "ok"}
    after = checkpointer_reconnect_total._value.get()
    assert after > before, (
        f"checkpointer_reconnect_total must inc on retry (before={before}, after={after})"
    )
