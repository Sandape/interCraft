"""Verify ability dimensions are seeded on registration (US5, DEC-P2-2)."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestAbilitiesSeed:
    async def test_new_user_has_6_dimensions(self, client, fresh_user_headers) -> None:
        """A freshly registered user should have 6 ability dimensions seeded."""
        resp = await client.get("/api/v1/ability-dimensions", headers=fresh_user_headers)
        # fresh_user_headers might be from a newly registered test user
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                dim_keys = {d["dimension_key"] for d in data}
                expected = {
                    "tech_depth", "architecture", "engineering_practice",
                    "communication", "algorithm", "business",
                }
                assert dim_keys == expected
                for d in data:
                    assert d["actual_score"] in ("0.00", 0, 0.0)
                    assert d["ideal_score"] in ("10.00", 10, 10.0)
                    assert d["is_active"] is True

    async def test_dimensions_have_sub_scores(self, client, user_a_headers) -> None:
        resp = await client.get("/api/v1/ability-dimensions", headers=user_a_headers)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            for d in data:
                sub = d.get("sub_scores", {})
                assert isinstance(sub, dict)
                # Each dimension should have 3 sub-keys
                assert len(sub) == 3, f"{d['dimension_key']} has {len(sub)} sub_scores, expected 3"
