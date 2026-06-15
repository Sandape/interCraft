"""Integration tests for interview sessions (US4 partial, M11)."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestInterviewSessionsRead:
    async def test_list_returns_200(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/interview-sessions", headers=user_a_headers)
        assert r.status_code == 200
        assert "data" in r.json()

    async def test_get_nonexistent_404(self, client, user_a_headers) -> None:
        r = await client.get(
            "/api/v1/interview-sessions/ffffffff-ffff-7fff-8000-000000000000",
            headers=user_a_headers,
        )
        assert r.status_code == 404


@pytest.mark.integration
class TestInterviewSessions405:
    async def test_patch_returns_405(self, client, user_a_headers) -> None:
        r = await client.patch(
            "/api/v1/interview-sessions/ffffffff-ffff-7fff-8000-000000000000",
            headers=user_a_headers, json={"status": "completed"},
        )
        assert r.status_code == 405


@pytest.mark.integration
class TestInterviewSessionsRLS:
    async def test_cross_user_404(self, client, user_a_headers, user_b_headers) -> None:
        r = await client.get("/api/v1/interview-sessions", headers=user_b_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        if data:
            sid = data[0]["id"]
            r = await client.get(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
            assert r.status_code == 404


# ---- soft delete (新增) ----

@pytest.mark.integration
class TestInterviewSessionsDelete:
    async def _create_session(self, client, headers, position="Backend Eng", company="ACME") -> str:
        r = await client.post(
            "/api/v1/interview-sessions",
            json={"position": position, "company": company, "mode": "text"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        return r.json()["data"]["id"]

    async def test_delete_nonexistent_404(self, client, user_a_headers) -> None:
        r = await client.delete(
            "/api/v1/interview-sessions/ffffffff-ffff-7fff-8000-000000000000",
            headers=user_a_headers,
        )
        assert r.status_code == 404

    async def test_delete_in_progress_returns_204_and_hides(self, client, user_a_headers) -> None:
        sid = await self._create_session(client, user_a_headers)

        # 删除
        r = await client.delete(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
        assert r.status_code == 204

        # 再次查询应返回 404 (软删除后不可见)
        r = await client.get(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
        assert r.status_code == 404

        # 列表也不应包含该 session
        r = await client.get("/api/v1/interview-sessions", headers=user_a_headers)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()["data"]]
        assert sid not in ids

    async def test_delete_idempotent_returns_404(self, client, user_a_headers) -> None:
        sid = await self._create_session(client, user_a_headers)
        r1 = await client.delete(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
        assert r1.status_code == 204
        r2 = await client.delete(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
        assert r2.status_code == 404

    async def test_cross_user_delete_404(self, client, user_a_headers, user_b_headers) -> None:
        sid = await self._create_session(client, user_a_headers)
        # user B 试图删除 user A 的 session 应 404
        r = await client.delete(f"/api/v1/interview-sessions/{sid}", headers=user_b_headers)
        assert r.status_code == 404
        # user A 仍能看到
        r = await client.get(f"/api/v1/interview-sessions/{sid}", headers=user_a_headers)
        assert r.status_code == 200

