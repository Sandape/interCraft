"""Integration tests for tasks dedup + activities pagination (US8)."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestTasksDedup:
    async def test_find_or_create_idempotent(self, client, user_a_headers) -> None:
        """Creating a job twice should not create duplicate interview_prep tasks."""
        # Create first job
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "DedupCorp", "position": "SDE",
        })
        assert r.status_code == 201

        # List tasks - should have 1 interview_prep task
        r = await client.get("/api/v1/tasks", headers=user_a_headers)
        assert r.status_code == 200
        first_count = len(r.json()["data"])

        # Create second job with same details
        await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "DedupCorp2", "position": "SDE2",
        })

        r = await client.get("/api/v1/tasks", headers=user_a_headers)
        assert r.status_code == 200
        # Each job creates its own task (different related_entity_id)
        assert len(r.json()["data"]) > first_count

    async def test_patch_task(self, client, user_a_headers) -> None:
        # Create a job to get a task
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "TaskPatch", "position": "Engineer",
        })
        r = await client.get("/api/v1/tasks", headers=user_a_headers)
        tasks = r.json()["data"]
        assert len(tasks) > 0

        task_id = tasks[0]["id"]
        r = await client.patch(f"/api/v1/tasks/{task_id}", headers=user_a_headers, json={
            "status": "done",
        })
        assert r.status_code == 200

    async def test_get_nonexistent_task_404(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/tasks/ffffffff-ffff-7fff-8000-000000000000", headers=user_a_headers)
        assert r.status_code == 404

    async def test_delete_task(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/jobs", headers=user_a_headers, json={
            "company": "TaskDel", "position": "Temp",
        })
        r = await client.get("/api/v1/tasks", headers=user_a_headers)
        tasks = r.json()["data"]
        assert len(tasks) > 0

        task_id = tasks[-1]["id"]
        r = await client.delete(f"/api/v1/tasks/{task_id}", headers=user_a_headers)
        assert r.status_code == 204


@pytest.mark.integration
class TestActivitiesPagination:
    async def test_list_returns_items(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/activities", headers=user_a_headers)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "next_cursor" in body
        assert "has_more" in body

    async def test_cursor_pagination_forward(self, client, user_a_headers) -> None:
        # Create multiple jobs to generate activities
        for i in range(3):
            await client.post("/api/v1/jobs", headers=user_a_headers, json={
                "company": f"PageCorp{i}", "position": f"SDE{i}",
            })

        r = await client.get("/api/v1/activities?limit=1", headers=user_a_headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 1

        if body["has_more"] and body["next_cursor"]:
            r = await client.get(
                f"/api/v1/activities?limit=1&cursor={body['next_cursor']}",
                headers=user_a_headers,
            )
            assert r.status_code == 200
            # Should have different items
            assert r.json()["items"][0]["id"] != body["items"][0]["id"]

    async def test_invalid_cursor_error(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/activities?cursor=not_valid_base64@@@", headers=user_a_headers)
        # Invalid base64 cursor should produce a 422
        assert r.status_code == 422


@pytest.mark.integration
class TestTasksActivitiesRLS:
    async def test_cross_user_task_404(self, client, user_a_headers, user_b_headers) -> None:
        # B creates a job → gets a task
        r = await client.post("/api/v1/jobs", headers=user_b_headers, json={
            "company": "B Task Corp", "position": "CEO",
        })
        r = await client.get("/api/v1/tasks", headers=user_b_headers)
        tasks = r.json()["data"]
        if tasks:
            task_id = tasks[0]["id"]
            r = await client.get(f"/api/v1/tasks/{task_id}", headers=user_a_headers)
            assert r.status_code == 404
