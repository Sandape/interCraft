"""Integration tests for jobs lifecycle + status machine (US8)."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestJobsLifecycle:
    async def test_create_job_defaults_applied(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "TestCorp", "position": "Backend Engineer",
        })
        assert r.status_code == 201
        job = r.json()
        assert job["status"] == "applied"
        assert job["company"] == "TestCorp"
        assert "id" in job

    async def test_create_job_creates_task(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "TaskCorp", "position": "Frontend",
        })
        assert r.status_code == 201
        job_id = r.json()["id"]

        # A task should be auto-created
        r = await client.get("/api/v1/tasks", headers=user_a_headers)
        assert r.status_code == 200
        tasks = r.json()["data"]
        assert any(t["related_entity_id"] == job_id for t in tasks)

    async def test_create_job_logs_activity(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "LogCorp", "position": "DevOps",
        })
        assert r.status_code == 201

        r = await client.get("/api/v1/activities?limit=10", headers=user_a_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(i["type"] == "job_created" for i in items)

    async def test_list_jobs(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/jobs", headers=user_a_headers)
        assert r.status_code == 200
        assert "data" in r.json()

    async def test_get_job_by_id(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "GetMe", "position": "SDE",
        })
        job_id = r.json()["id"]
        r = await client.get(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
        assert r.status_code == 200
        assert r.json()["id"] == job_id

    async def test_get_nonexistent_job_404(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/jobs/ffffffff-ffff-7fff-8000-000000000000", headers=user_a_headers)
        assert r.status_code == 404

    async def test_patch_job(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "PatchMe", "position": "Intern",
        })
        job_id = r.json()["id"]
        r = await client.patch(f"/api/v1/jobs/{job_id}", headers=user_a_headers, json={
            "jd_url": "https://example.com/jd",
        })
        assert r.status_code == 200
        assert r.json()["jd_url"] == "https://example.com/jd"

    async def test_delete_job(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "DelMe", "position": "Temp",
        })
        job_id = r.json()["id"]
        r = await client.delete(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
        assert r.status_code == 204


@pytest.mark.integration
class TestJobsStatusMachine:
    async def test_valid_transition_applied_to_test(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "TransCorp", "position": "Engineer",
        })
        job_id = r.json()["id"]
        r = await client.patch(f"/api/v1/jobs/{job_id}/status", headers=user_a_headers, json={
            "to": "test",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "test"

    async def test_transition_applied_to_rejected(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "RejectCorp", "position": "SDE",
        })
        job_id = r.json()["id"]
        r = await client.patch(f"/api/v1/jobs/{job_id}/status", headers=user_a_headers, json={
            "to": "rejected",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

    async def test_invalid_transition_409(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "BadTrans", "position": "SDE",
        })
        job_id = r.json()["id"]
        r = await client.patch(f"/api/v1/jobs/{job_id}/status", headers=user_a_headers, json={
            "to": "applied",  # already applied
        })
        assert r.status_code in (409, 422)


@pytest.mark.integration
class TestJobsStats:
    async def test_stats_returns_counts(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/jobs/stats", headers=user_a_headers)
        assert r.status_code == 200
        body = r.json()
        assert "counts" in body
        assert "total" in body
        assert isinstance(body["counts"], dict)


@pytest.mark.integration
class TestJobsTimeline:
    async def test_timeline_has_status_history(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "TimeCorp", "position": "SDE",
        })
        job_id = r.json()["id"]
        r = await client.get(f"/api/v1/jobs/{job_id}/timeline", headers=user_a_headers)
        assert r.status_code == 200


@pytest.mark.integration
class TestJobsRLS:
    async def test_cross_user_access_404(self, client, user_a_headers, user_b_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_b_headers, json={
            "company": "B Corp", "position": "CTO",
        })
        job_id = r.json()["id"]
        r = await client.get(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
        assert r.status_code == 404
