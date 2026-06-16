"""019 — Interview job_id validation (US3, FR-011).

POST /interview-sessions with job_id:
- happy path: own job + matching branch_id → 200/201
- happy path: own job + no branch_id → 200/201
- missing job: 404
- foreign job: 404
- branch mismatch: 409
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestInterviewJobId:
    async def test_create_interview_with_own_job_and_matching_branch_succeeds(
        self, client, user_a_headers
    ) -> None:
        # create branch + bind to job
        r = await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "字节 · 前端", "company": "字节", "position": "前端"},
        )
        assert r.status_code in (200, 201), r.text
        branch_id = r.json()["branch"]["id"]

        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={"company": "字节", "position": "前端"},
        )
        assert r.status_code in (200, 201), r.text
        job_id = r.json()["id"]

        r = await client.patch(
            f"/api/v1/jobs/{job_id}",
            headers=user_a_headers,
            json={"branch_id": branch_id},
        )
        assert r.status_code == 200, r.text

        # create interview session with job_id
        r = await client.post(
            "/api/v1/interview-sessions",
            headers=user_a_headers,
            json={
                "position": "前端",
                "company": "字节",
                "branch_id": branch_id,
                "job_id": job_id,
            },
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()["data"]
        assert body["job_id"] == job_id
        assert body["branch_id"] == branch_id

    async def test_create_interview_with_own_job_and_no_branch_succeeds(
        self, client, user_a_headers
    ) -> None:
        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={"company": "字节", "position": "前端"},
        )
        job_id = r.json()["id"]

        r = await client.post(
            "/api/v1/interview-sessions",
            headers=user_a_headers,
            json={"position": "前端", "company": "字节", "job_id": job_id},
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()["data"]
        assert body["job_id"] == job_id

    async def test_create_interview_with_missing_job_returns_404(
        self, client, user_a_headers
    ) -> None:
        import uuid
        fake_job_id = str(uuid.uuid4())
        r = await client.post(
            "/api/v1/interview-sessions",
            headers=user_a_headers,
            json={"position": "前端", "company": "字节", "job_id": fake_job_id},
        )
        assert r.status_code == 404, r.text

    async def test_create_interview_with_foreign_job_returns_404(
        self, client, user_a_headers, user_b_headers
    ) -> None:
        # user B creates a job
        r = await client.post(
            "/api/v1/jobs",
            headers=user_b_headers,
            json={"company": "B", "position": "B"},
        )
        b_job_id = r.json()["id"]

        # user A tries to create an interview with B's job
        r = await client.post(
            "/api/v1/interview-sessions",
            headers=user_a_headers,
            json={"position": "A", "company": "A", "job_id": b_job_id},
        )
        assert r.status_code == 404, r.text

    async def test_create_interview_with_branch_mismatch_returns_409(
        self, client, user_a_headers
    ) -> None:
        # create branch A
        r = await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "A 分支", "company": "A", "position": "A"},
        )
        branch_a = r.json()["branch"]["id"]

        # create branch B
        r = await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "B 分支", "company": "B", "position": "B"},
        )
        branch_b = r.json()["branch"]["id"]

        # create job bound to branch A
        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={"company": "A", "position": "A"},
        )
        job_id = r.json()["id"]
        r = await client.patch(
            f"/api/v1/jobs/{job_id}",
            headers=user_a_headers,
            json={"branch_id": branch_a},
        )
        assert r.status_code == 200, r.text

        # try to create interview with job but wrong branch → 409
        r = await client.post(
            "/api/v1/interview-sessions",
            headers=user_a_headers,
            json={
                "position": "A",
                "company": "A",
                "branch_id": branch_b,
                "job_id": job_id,
            },
        )
        assert r.status_code == 409, r.text
