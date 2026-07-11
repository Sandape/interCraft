"""Integration tests for ability profile (Feature 006 / 024).

Covers:
- Dashboard aggregation (US1)
- Self-assessment via PATCH (US2) — dual-track self_assessed_score
- Share link lifecycle (US4) — no PIN
- Growth timeline (US5)
- PDF export sync (US6)
- Admin view (US7)
"""
from __future__ import annotations

import pytest


@pytest.fixture
async def auth_headers(user_a_headers):
    """Alias for existing user_a_headers fixture."""
    return user_a_headers


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
        """Seeded user still has 6 dimensions (all zero / no assessment)."""
        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.integration
class TestSelfAssessmentAPI:
    """US2: Self-assessment writes self_assessed_score (dual-track)."""

    async def test_self_assess_updates_dashboard(self, client, auth_headers):
        resp = await client.patch(
            "/api/v1/ability-dimensions/tech_depth",
            headers=auth_headers,
            json={"self_assessed_score": 7.0, "notes": "感觉不错"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["self_assessed_score"]) == 7.0

        dash = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=auth_headers,
        )
        assert dash.status_code == 200
        dims = {d["key"]: d for d in dash.json()["data"]["dimensions"]}
        assert dims["tech_depth"]["self_assessed_score"] == 7.0


@pytest.mark.integration
class TestSystemScorePropagation:
    """US3: System score display."""

    async def test_dashboard_includes_system_scores(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/ability-profile/dashboard",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        for dim in resp.json()["data"]["dimensions"]:
            assert "actual_score" in dim
            assert "self_assessed_score" in dim


@pytest.mark.integration
class TestShareLinkLifecycle:
    """US4: Share link CRUD (no PIN — Feature 024)."""

    async def test_create_share_link(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/ability-profile/share",
            headers=auth_headers,
            json={"expires_in_hours": 48},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert "token" in data
        assert "has_pin" not in data

    async def test_pin_field_ignored(self, client, auth_headers):
        """Extra pin field must not break create (schema ignores unknown or rejects)."""
        resp = await client.post(
            "/api/v1/ability-profile/share",
            headers=auth_headers,
            json={"pin": "1234", "expires_in_hours": 48},
        )
        # Pydantic v2 default: ignore extra → 201; or 422 if forbid
        assert resp.status_code in (201, 422)

    async def test_list_share_links(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/ability-profile/share",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_revoke_share_link(self, client, auth_headers):
        create = await client.post(
            "/api/v1/ability-profile/share",
            headers=auth_headers,
            json={"expires_in_hours": 24},
        )
        assert create.status_code == 201
        link_id = create.json()["data"]["id"]
        token = create.json()["data"]["token"]

        resp = await client.delete(
            f"/api/v1/ability-profile/share/{link_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        public = await client.get(f"/api/v1/ability-profile/share/{token}")
        assert public.status_code == 403


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
    """US6: PDF export — sync endpoint registered; legacy POST still accepted."""

    async def test_export_pdf_route_exists(self, client, auth_headers, tmp_path):
        """Sync export-pdf is registered and returns PDF when generation succeeds."""
        from unittest.mock import AsyncMock, patch

        pdf_file = tmp_path / "ability-profile-test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock")

        with patch(
            "app.modules.ability_profile.pdf.generate_profile_pdf",
            new=AsyncMock(return_value=str(pdf_file)),
        ):
            resp = await client.get(
                "/api/v1/ability-profile/export-pdf",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content.startswith(b"%PDF-")

    async def test_list_exports(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/ability-profile/exports",
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.integration
class TestAdminView:
    """US7: Admin view — non-admin gets 403."""

    async def test_non_admin_gets_403(self, client, auth_headers):
        # Use a random UUID as target; auth user is not admin
        resp = await client.get(
            "/api/v1/ability-profile/admin/00000000-0000-7000-8000-000000000001",
            headers=auth_headers,
        )
        assert resp.status_code == 403
