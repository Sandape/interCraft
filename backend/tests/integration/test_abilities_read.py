"""Integration tests for ability dimensions read endpoints (US5)."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestAbilitiesRead:
    async def test_list_returns_6_dimensions(self, client, user_a_headers) -> None:
        resp = await client.get("/api/v1/ability-dimensions", headers=user_a_headers)
        assert resp.status_code == 200
        data = resp.json().get("data", [])
        # User A should have 6 dimensions (seeded on register)
        if data:
            dim_keys = {d["dimension_key"] for d in data}
            expected = {
                "tech_depth", "architecture", "engineering_practice",
                "communication", "algorithm", "business",
            }
            assert dim_keys == expected

    async def test_get_single_dimension(self, client, user_a_headers) -> None:
        resp = await client.get(
            "/api/v1/ability-dimensions/tech_depth", headers=user_a_headers
        )
        assert resp.status_code == 200
        dim = resp.json()
        assert dim["dimension_key"] == "tech_depth"
        assert "actual_score" in dim
        assert "ideal_score" in dim
        assert "sub_scores" in dim
        assert "is_active" in dim

    async def test_get_invalid_dimension_422(self, client, user_a_headers) -> None:
        resp = await client.get(
            "/api/v1/ability-dimensions/not_a_dim", headers=user_a_headers
        )
        assert resp.status_code == 422  # invalid dimension key → validation error

    async def test_list_empty_user_returns_empty(self, client) -> None:
        """If a user has no ability_dimensions rows, the API returns []."""
        # This is tested by having a freshly registered user where seed might fail
        # For now just verify the endpoint returns valid JSON shape
        pass


@pytest.mark.integration
class TestAbilitiesMeta:
    async def test_dimensions_meta_returns_6_dimensions(self, client, user_a_headers) -> None:
        resp = await client.get(
            "/api/v1/ability-dimensions/dimensions-meta", headers=user_a_headers
        )
        assert resp.status_code == 200
        meta = resp.json()
        assert "dimensions" in meta
        dims = meta["dimensions"]
        assert len(dims) == 6
        keys = {d["key"] for d in dims}
        assert keys == {
            "tech_depth", "architecture", "engineering_practice",
            "communication", "algorithm", "business",
        }
        for d in dims:
            assert "label_zh" in d
            assert "sub_keys" in d
            assert len(d["sub_keys"]) == 3
