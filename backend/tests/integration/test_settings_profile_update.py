"""Integration tests for settings profile update (US11)."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestSettingsProfileUpdate:
    async def test_patch_users_me_4_fields(self, client, user_a_headers) -> None:
        r = await client.patch("/api/v1/users/me", headers=user_a_headers, json={
            "display_name": "Updated Name",
        })
        assert r.status_code == 200
        assert r.json()["display_name"] == "Updated Name"

    async def test_patch_target_role(self, client, user_a_headers) -> None:
        r = await client.patch("/api/v1/users/me", headers=user_a_headers, json={
            "target_role": "Senior SWE",
        })
        assert r.status_code == 200
        assert r.json()["target_role"] == "Senior SWE"

    async def test_patch_years_of_experience(self, client, user_a_headers) -> None:
        r = await client.patch("/api/v1/users/me", headers=user_a_headers, json={
            "years_of_experience": 5,
        })
        assert r.status_code == 200
        assert r.json()["years_of_experience"] == 5

    async def test_patch_bio(self, client, user_a_headers) -> None:
        r = await client.patch("/api/v1/users/me", headers=user_a_headers, json={
            "bio": "E2E profile bio persists.",
        })
        assert r.status_code == 200
        assert r.json()["bio"] == "E2E profile bio persists."

    async def test_patch_email_blocked_422(self, client, user_a_headers) -> None:
        r = await client.patch("/api/v1/users/me", headers=user_a_headers, json={
            "email": "hacker@evil.com",
        })
        # email changes are silently ignored by the backend
        assert r.status_code == 200
        assert r.json()["email"] != "hacker@evil.com"

    async def test_patch_subscription_blocked_422(self, client, user_a_headers) -> None:
        r = await client.patch("/api/v1/users/me", headers=user_a_headers, json={
            "subscription_tier": "enterprise",
        })
        # subscription changes are silently ignored by the backend
        assert r.status_code == 200
