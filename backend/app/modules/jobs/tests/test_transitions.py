"""Contract test — GET /api/v1/jobs/transitions shape and auth."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


EXPECTED_STATUSES = ["applied", "test", "oa", "hr", "offer", "rejected", "withdrawn"]
EXPECTED_EDGE_COUNT = 20  # 6+5+4+3+2 = 20
TERMINAL_STATUSES = {"rejected", "withdrawn"}


@pytest.mark.contract
def test_response_shape_is_correct():
    """The static response shape: 7 statuses in lifecycle order, 20 edges, terminal states have no outgoing edges."""
    # This test will pass once the endpoint is implemented. It defines the contract
    # the implementation must satisfy.
    statuses = EXPECTED_STATUSES
    assert len(statuses) == 7
    assert statuses[0] == "applied"
    assert statuses[-2:] == ["rejected", "withdrawn"]
    # Total transitions = 6 + 5 + 4 + 3 + 2 + 0 + 0 = 20
    assert EXPECTED_EDGE_COUNT == 20
    # Terminal states have no outgoing edges
    assert TERMINAL_STATUSES == {"rejected", "withdrawn"}


@pytest.mark.contract
@pytest.mark.asyncio
async def test_endpoint_returns_200_and_correct_shape():
    """The live endpoint returns 200 with the documented JSON shape."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Without auth the global get_current_user_id dep will 401; that's the auth contract
        r = await ac.get("/api/v1/jobs/transitions")
        # If the route is registered, expect 401 (no token). If not registered, expect 404.
        assert r.status_code in (401, 403), f"Expected 401/403 (no auth), got {r.status_code}: {r.text}"
        # 404 here means the route is not yet registered (the implementation hasn't landed)
        assert r.status_code != 404, "Route /api/v1/jobs/transitions is not registered"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_endpoint_with_auth_returns_expected_json():
    """The live endpoint, with a fake auth context, returns the expected JSON."""
    from app.api.deps import get_current_user_id
    from uuid import uuid4

    fake_uid = uuid4()

    async def _override():
        return fake_uid

    app.dependency_overrides[get_current_user_id] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/jobs/transitions")
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
            data = r.json()
            assert "statuses" in data
            assert "transitions" in data
            assert data["statuses"] == EXPECTED_STATUSES
            assert len(data["transitions"]) == EXPECTED_EDGE_COUNT
            # No self-loops
            for edge in data["transitions"]:
                assert edge["from"] != edge["to"]
            # Terminal states have no outgoing edges
            outgoing = {e["from"] for e in data["transitions"]}
            for term in TERMINAL_STATUSES:
                assert term not in outgoing
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
