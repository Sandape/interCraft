"""024 US1 — Integration tests: job offer field API.

Tests:
  1. List hides offer fields
  2. GET returns offer fields
  3. PATCH offer fields rejected when status != "offer"
  4. PATCH offer fields accepted when status == "offer"
  5. Past deadline rejected
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def _create_job(client, headers) -> dict:
    r = await client.post(
        "/api/v1/jobs",
        json={"company": "OfferCorp", "position": "Engineer"},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()


async def _update_status(client, headers, job_id: str, to: str):
    r = await client.patch(
        f"/api/v1/jobs/{job_id}/status",
        json={"to": to},
        headers=headers,
    )
    assert r.status_code == 200
    return r.json()


class TestOfferFieldsAPI:
    async def test_list_hides_offer_fields(self, client: AsyncClient, user_a_headers):
        """Job list endpoint does not return offer_* fields."""
        job = await _create_job(client, user_a_headers)
        r = await client.get("/api/v1/jobs", headers=user_a_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) >= 1
        item = next(j for j in data if j["id"] == job["id"])
        assert "offer_salary_text" not in item
        assert "offer_contact_name" not in item
        assert "offer_contact_info" not in item
        assert "offer_deadline_at" not in item

    async def test_get_returns_offer_fields(self, client: AsyncClient, user_a_headers):
        """Single job GET returns offer_* fields (as null)."""
        job = await _create_job(client, user_a_headers)
        r = await client.get(f"/api/v1/jobs/{job['id']}", headers=user_a_headers)
        assert r.status_code == 200
        assert "offer_salary_text" in r.json()
        assert r.json()["offer_salary_text"] is None

    async def test_patch_offer_fields_rejected_when_not_offer(
        self, client: AsyncClient, user_a_headers
    ):
        """PATCH with offer fields returns 409 when status != 'offer'."""
        job = await _create_job(client, user_a_headers)
        r = await client.patch(
            f"/api/v1/jobs/{job['id']}",
            json={"offer_salary_text": "100K"},
            headers=user_a_headers,
        )
        assert r.status_code == 409

    async def test_patch_offer_fields_accepted_when_offer(
        self, client: AsyncClient, user_a_headers
    ):
        """PATCH with offer fields succeeds when job status is 'offer'."""
        job = await _create_job(client, user_a_headers)
        await _update_status(client, user_a_headers, job["id"], "offer")

        future = (datetime.now(UTC) + timedelta(days=14)).isoformat()
        r = await client.patch(
            f"/api/v1/jobs/{job['id']}",
            json={
                "offer_salary_text": "120K-150K",
                "offer_contact_name": "Alice HR",
                "offer_contact_info": "alice@example.com",
                "offer_deadline_at": future,
            },
            headers=user_a_headers,
        )
        assert r.status_code == 200
        assert r.json()["offer_salary_text"] == "120K-150K"
        assert r.json()["offer_contact_name"] == "Alice HR"
        assert r.json()["offer_contact_info"] == "alice@example.com"
        assert r.json()["offer_deadline_at"] is not None

    async def test_rejects_past_deadline(
        self, client: AsyncClient, user_a_headers
    ):
        """Past offer_deadline_at returns 422."""
        job = await _create_job(client, user_a_headers)
        await _update_status(client, user_a_headers, job["id"], "offer")

        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        r = await client.patch(
            f"/api/v1/jobs/{job['id']}",
            json={"offer_deadline_at": past},
            headers=user_a_headers,
        )
        assert r.status_code == 422

    async def test_patch_non_offer_fields_still_works(
        self, client: AsyncClient, user_a_headers
    ):
        """Non-offer PATCH fields work regardless of status."""
        job = await _create_job(client, user_a_headers)
        r = await client.patch(
            f"/api/v1/jobs/{job['id']}",
            json={"company": "UpdatedCorp"},
            headers=user_a_headers,
        )
        assert r.status_code == 200
        assert r.json()["company"] == "UpdatedCorp"
