"""Integration tests for ability dimensions history (US5)."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestAbilitiesHistory:
    async def test_history_returns_empty_for_new_user(self, client, user_a_headers) -> None:
        resp = await client.get(
            "/api/v1/ability-dimensions/history?aggregate=month", headers=user_a_headers
        )
        assert resp.status_code == 200
        data = resp.json().get("data", [])
        assert isinstance(data, list)

    async def test_history_with_dimension_filter(self, client, user_a_headers) -> None:
        resp = await client.get(
            "/api/v1/ability-dimensions/history?dimension_key=tech_depth&aggregate=month",
            headers=user_a_headers,
        )
        assert resp.status_code == 200
        data = resp.json().get("data", [])
        assert isinstance(data, list)
        for item in data:
            assert item["dimension_key"] == "tech_depth"

    async def test_history_invalid_aggregate_422(self, client, user_a_headers) -> None:
        resp = await client.get(
            "/api/v1/ability-dimensions/history?aggregate=year",
            headers=user_a_headers,
        )
        assert resp.status_code == 422


@pytest.mark.integration
class TestAbilitiesPatch:
    async def test_patch_actual_score(self, client, user_a_headers) -> None:
        resp = await client.patch(
            "/api/v1/ability-dimensions/tech_depth",
            headers=user_a_headers,
            json={"actual_score": 7.5},
        )
        assert resp.status_code == 200
        dim = resp.json()
        assert float(dim["actual_score"]) == 7.5

    async def test_patch_sub_scores(self, client, user_a_headers) -> None:
        resp = await client.patch(
            "/api/v1/ability-dimensions/architecture",
            headers=user_a_headers,
            json={
                "sub_scores": {
                    "decomposition": {"actual": 6.0, "ideal": 10.0},
                    "tradeoffs": {"actual": 5.0, "ideal": 10.0},
                    "scalability": {"actual": 4.0, "ideal": 10.0},
                }
            },
        )
        assert resp.status_code == 200
        dim = resp.json()
        assert dim["sub_scores"]["decomposition"]["actual"] == 6.0

    async def test_patch_invalid_score_422(self, client, user_a_headers) -> None:
        resp = await client.patch(
            "/api/v1/ability-dimensions/tech_depth",
            headers=user_a_headers,
            json={"actual_score": 15.0},
        )
        assert resp.status_code == 422

    async def test_patch_invalid_sub_key_422(self, client, user_a_headers) -> None:
        resp = await client.patch(
            "/api/v1/ability-dimensions/tech_depth",
            headers=user_a_headers,
            json={"sub_scores": {"not_a_valid_key": {"actual": 5, "ideal": 10}}},
        )
        assert resp.status_code == 422
