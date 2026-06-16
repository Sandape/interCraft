"""Contract tests for the global search endpoint."""
from __future__ import annotations

import pytest

pytest_plugins = ("tests.conftest",)


@pytest.mark.integration
class TestGlobalSearchEndpoint:
    async def _create_resume(
        self,
        client,
        headers: dict[str, str],
        *,
        name: str = "Bytedance Senior Frontend",
        company: str = "Bytedance",
        position: str = "Senior Frontend Engineer",
    ) -> str:
        resp = await client.post(
            "/api/v1/resume-branches",
            headers=headers,
            json={
                "name": name,
                "company": company,
                "position": position,
                "is_main": False,
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["branch"]["id"]

    async def _create_interview(
        self,
        client,
        headers: dict[str, str],
        *,
        company: str = "Bytedance",
        position: str = "Senior Frontend Engineer",
    ) -> str:
        resp = await client.post(
            "/api/v1/interview-sessions",
            headers=headers,
            json={"company": company, "position": position, "mode": "text"},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]["id"]

    async def test_search_returns_grouped_user_results(self, client, user_a_headers) -> None:
        resume_id = await self._create_resume(client, user_a_headers)
        interview_id = await self._create_interview(client, user_a_headers)
        ability_resp = await client.patch(
            "/api/v1/ability-dimensions/architecture",
            headers=user_a_headers,
            json={"actual_score": 7},
        )
        assert ability_resp.status_code == 200, ability_resp.text

        resp = await client.get(
            "/api/v1/search",
            headers=user_a_headers,
            params={"q": "byte", "limit": 5},
        )

        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["query"] == "byte"
        assert payload["took_ms"] >= 0

        groups = {group["type"]: group for group in payload["groups"]}
        assert groups["resume"]["items"][0]["id"] == resume_id
        assert groups["resume"]["items"][0]["destination"] == f"/resume/{resume_id}"
        assert groups["interview"]["items"][0]["id"] == interview_id
        assert groups["interview"]["items"][0]["destination"] == (
            f"/interview/{interview_id}/report"
        )

        ability = await client.get(
            "/api/v1/search",
            headers=user_a_headers,
            params={"q": "architecture", "limit": 5},
        )
        assert ability.status_code == 200, ability.text
        ability_groups = {group["type"]: group for group in ability.json()["groups"]}
        assert ability_groups["ability"]["items"][0]["id"] == "ability::architecture"
        assert ability_groups["ability"]["items"][0]["destination"] == (
            "/ability-profile/architecture"
        )

    async def test_search_enforces_validation_and_caps(self, client, user_a_headers) -> None:
        empty_resp = await client.get(
            "/api/v1/search",
            headers=user_a_headers,
            params={"q": ""},
        )
        assert empty_resp.status_code == 422

        for index in range(7):
            await self._create_resume(
                client,
                user_a_headers,
                name=f"Cap Test Resume {index}",
                company="CapCo",
                position="Engineer",
            )

        resp = await client.get(
            "/api/v1/search",
            headers=user_a_headers,
            params={"q": "Cap Test", "limit": 5},
        )
        assert resp.status_code == 200, resp.text
        groups = {group["type"]: group for group in resp.json()["groups"]}
        assert len(groups["resume"]["items"]) == 5
        assert groups["resume"]["total"] >= 7
        assert sum(len(group["items"]) for group in resp.json()["groups"]) <= 25

    async def test_search_respects_user_isolation(
        self,
        client,
        user_a_headers,
        user_b_headers,
    ) -> None:
        own_id = await self._create_resume(
            client,
            user_a_headers,
            name="Private Search Target",
            company="IsolationCo",
            position="Frontend",
        )

        own_resp = await client.get(
            "/api/v1/search",
            headers=user_a_headers,
            params={"q": "Private Search", "limit": 5},
        )
        assert own_resp.status_code == 200, own_resp.text
        assert any(
            item["id"] == own_id
            for group in own_resp.json()["groups"]
            for item in group["items"]
        )

        other_resp = await client.get(
            "/api/v1/search",
            headers=user_b_headers,
            params={"q": "Private Search", "limit": 5},
        )
        assert other_resp.status_code == 200, other_resp.text
        assert all(
            item["id"] != own_id
            for group in other_resp.json()["groups"]
            for item in group["items"]
        )
