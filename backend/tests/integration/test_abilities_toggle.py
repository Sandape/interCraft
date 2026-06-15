"""Integration tests for ability dimension toggle (US5)."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestAbilitiesToggle:
    async def test_toggle_disables_dimension(self, client, user_a_headers) -> None:
        resp = await client.post(
            "/api/v1/ability-dimensions/tech_depth/toggle",
            headers=user_a_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 200
        dim = resp.json()
        assert dim["is_active"] is False
        assert dim["dimension_key"] == "tech_depth"

    async def test_toggle_reenables_dimension(self, client, user_a_headers) -> None:
        # First disable
        await client.post(
            "/api/v1/ability-dimensions/algorithm/toggle",
            headers=user_a_headers,
            json={"is_active": False},
        )
        # Then re-enable
        resp = await client.post(
            "/api/v1/ability-dimensions/algorithm/toggle",
            headers=user_a_headers,
            json={"is_active": True},
        )
        assert resp.status_code == 200
        dim = resp.json()
        assert dim["is_active"] is True

    async def test_toggle_no_body_defaults(self, client, user_a_headers) -> None:
        resp = await client.post(
            "/api/v1/ability-dimensions/business/toggle",
            headers=user_a_headers,
            json={},
        )
        # No is_active in body should be treated as toggle (default to current opposite)
        assert resp.status_code in (200, 422)
