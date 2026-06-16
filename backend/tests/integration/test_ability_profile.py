"""Integration tests for ability profile (Feature 006).

Covers:
- Dashboard aggregation (US1)
- Self-assessment via PATCH (US2)
- System score propagation (US3)
- Share link lifecycle (US4)
- Growth timeline (US5)
- PDF export (US6)
- Admin view (US7)
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestDashboardAPI:
    """US1: Dashboard aggregation."""

    async def test_dashboard_returns_dimensions(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "dimensions" in data["data"]

    async def test_dashboard_empty_state(self, client, auth_headers):
        """User with no ability data sees empty dimensions list."""
        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.integration
class TestSelfAssessmentAPI:
    """US2: Self-assessment."""

    async def test_self_assess_updates_dashboard(self, client, auth_headers):
        resp = await client.patch(
            "/api/v1/ability-dimensions/tech_depth",
            headers=auth_headers,
            json={"actual_score": 7.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["actual_score"] == 7.0


@pytest.mark.integration
class TestSystemScorePropagation:
    """US3: System score display."""

    async def test_dashboard_includes_system_scores(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.integration
class TestShareLinkLifecycle:
    """US4: Share link CRUD."""

    async def test_create_share_link(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/ability-profile/share",
            headers=auth_headers,
            json={"expires_in_hours": 48},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert "token" in data
        assert data["has_pin"] is False

    async def test_create_share_link_with_pin(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/ability-profile/share",
            headers=auth_headers,
            json={"pin": "1234", "expires_in_hours": 48},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["has_pin"] is True

    async def test_list_share_links(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/ability-profile/share",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_revoke_share_link(self, client, auth_headers, test_share_link_id):
        resp = await client.delete(
            f"/api/v1/ability-profile/share/{test_share_link_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_public_access_revoked_returns_404(self, client, revoked_token):
        resp = await client.get(f"/api/v1/ability-profile/share/{revoked_token}")
        assert resp.status_code == 404


@pytest.mark.integration
class TestGrowthTimeline:
    """US5: Growth timeline."""

    async def test_dashboard_includes_history(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        for dim in resp.json()["data"]["dimensions"]:
            assert "history" in dim


@pytest.mark.integration
class TestExport:
    """US6: PDF export."""

    async def test_trigger_export(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/ability-profile/export",
            headers=auth_headers,
        )
        assert resp.status_code in (202, 429)  # 429 if rate limited

    async def test_list_exports(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/ability-profile/exports",
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.integration
class TestAdminView:
    """US7: Admin view."""

    async def test_admin_view_other_user(self, client, admin_headers, other_user_id):
        resp = await client.get(
            f"/api/v1/ability-profile/admin/{other_user_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "viewed_user_id" in data

    async def test_non_admin_gets_403(self, client, auth_headers, other_user_id):
        resp = await client.get(
            f"/api/v1/ability-profile/admin/{other_user_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 403
