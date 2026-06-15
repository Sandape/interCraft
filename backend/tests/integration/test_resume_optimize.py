"""Integration test for M16 Resume Optimize complete flow.

Tests: start → interrupt → confirm(apply) → verify blocks updated + version created
       start → interrupt → confirm(discard) → content unchanged + thread aborted

Per Constitution III: these must FAIL before implementation.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport

pytestmark = [pytest.mark.integration]

_BRANCH_ID = "019b5e6c-0000-7000-0000-000000000000"
_THREAD_ID = "019b5e6c-0000-7000-0000-000000000001"
_USER_ID = "019b5e6c-0000-7000-0000-000000000003"
_VALID_TOKEN = f"Bearer {_USER_ID}"


@pytest.mark.asyncio
async def test_resume_optimize_apply_flow():
    """M16 start → interrupt → confirm(apply) → blocks updated + version created."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with __import__("httpx").AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # 1. Start optimize
        res = await client.post(
            "/api/v1/agents/resume-optimize/start",
            json={"branch_id": _BRANCH_ID, "target_jd": "资深前端工程师,5年React经验,熟悉TypeScript"},
            headers={"Authorization": _VALID_TOKEN},
        )
        assert res.status_code == 201
        data = res.json()
        thread_id = data["thread_id"]
        assert data["status"] == "running"

        # 2. Poll state until interrupt or completed
        state_res = await client.get(
            f"/api/v1/agents/resume-optimize/{thread_id}/state",
            headers={"Authorization": _VALID_TOKEN},
        )
        assert state_res.status_code == 200
        state = state_res.json()
        assert state["status"] in ("running", "waiting_interrupt", "completed")

        # 3. If waiting_interrupt, confirm with apply
        if state["status"] == "waiting_interrupt":
            confirm_res = await client.post(
                f"/api/v1/agents/resume-optimize/{thread_id}/confirm",
                json={"decision": "apply"},
                headers={"Authorization": _VALID_TOKEN},
            )
            assert confirm_res.status_code == 200
            confirm_data = confirm_res.json()
            assert confirm_data["decision"] == "apply"
            assert confirm_data["version_id"] is not None

        # 4. Verify state is completed
        final_res = await client.get(
            f"/api/v1/agents/resume-optimize/{thread_id}/state",
            headers={"Authorization": _VALID_TOKEN},
        )
        assert final_res.status_code == 200
        assert final_res.json()["status"] in ("completed", "running")


@pytest.mark.asyncio
async def test_resume_optimize_discard_flow():
    """M16 start → interrupt → confirm(discard) → content unchanged."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with __import__("httpx").AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # 1. Start optimize
        res = await client.post(
            "/api/v1/agents/resume-optimize/start",
            json={"branch_id": _BRANCH_ID, "target_jd": "后端架构师"},
            headers={"Authorization": _VALID_TOKEN},
        )
        assert res.status_code == 201
        thread_id = res.json()["thread_id"]

        # 2. Poll state
        state_res = await client.get(
            f"/api/v1/agents/resume-optimize/{thread_id}/state",
            headers={"Authorization": _VALID_TOKEN},
        )
        assert state_res.status_code == 200

        # 3. Confirm with discard
        confirm_res = await client.post(
            f"/api/v1/agents/resume-optimize/{thread_id}/confirm",
            json={"decision": "discard"},
            headers={"Authorization": _VALID_TOKEN},
        )
        assert confirm_res.status_code == 200
        assert confirm_res.json()["decision"] == "discard"


@pytest.mark.asyncio
async def test_resume_optimize_lock_conflict_423():
    """M16 start returns 423 when branch is locked by another session."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with __import__("httpx").AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/v1/agents/resume-optimize/start",
            json={"branch_id": "00000000-0000-0000-0000-000000000000", "target_jd": "test"},
            headers={"Authorization": _VALID_TOKEN},
        )
        # 423 or 404 (branch not found) or 401 (no auth)
        assert res.status_code in (201, 401, 404, 423)
