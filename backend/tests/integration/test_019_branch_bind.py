"""019 — Integration tests for binding a resume branch to a job (FR-007~FR-008).

Job.branch_id is set via PATCH /jobs/{id}; the validation must:
- accept a valid branch_id the user owns
- reject a non-UUID branch_id with 422
- reject a branch_id that belongs to another user with 404
"""
from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


class TestJobBranchBind:
    async def test_create_branch_then_patch_job_branch_id_succeeds(
        self, client, user_a_headers
    ) -> None:
        # 1. create branch
        r = await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "字节 · 前端", "company": "字节", "position": "前端"},
        )
        assert r.status_code in (200, 201), r.text
        branch_id = r.json()["branch"]["id"]

        # 2. create job
        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={"company": "字节", "position": "前端"},
        )
        job_id = r.json()["id"]

        # 3. PATCH /jobs/{id} with branch_id
        r = await client.patch(
            f"/api/v1/jobs/{job_id}",
            headers=user_a_headers,
            json={"branch_id": branch_id},
        )
        assert r.status_code == 200, r.text
        assert r.json()["branch_id"] == branch_id

    async def test_create_resume_v2_then_patch_job_branch_id_succeeds(
        self, client, user_a_headers
    ) -> None:
        # REQ-055 derived resumes live in resumes_v2, but Job.branch_id is
        # still the cross-module binding field used by interview launch.
        slug = f"bind-v2-{uuid4().hex[:8]}"
        r = await client.post(
            "/api/v1/v2/resumes",
            headers=user_a_headers,
            json={"name": "V2 resume for job binding", "slug": slug, "template": "onyx"},
        )
        assert r.status_code == 201, r.text
        branch_id = r.json()["id"]

        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={"company": "V2Co", "position": "AI App Engineer"},
        )
        assert r.status_code == 201, r.text
        job_id = r.json()["id"]

        r = await client.patch(
            f"/api/v1/jobs/{job_id}",
            headers=user_a_headers,
            json={"branch_id": branch_id},
        )
        assert r.status_code == 200, r.text
        assert r.json()["branch_id"] == branch_id

    async def test_patch_job_branch_id_to_invalid_uuid_rejected(
        self, client, user_a_headers
    ) -> None:
        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={"company": "X", "position": "Y"},
        )
        job_id = r.json()["id"]
        r = await client.patch(
            f"/api/v1/jobs/{job_id}",
            headers=user_a_headers,
            json={"branch_id": "not-a-uuid"},
        )
        assert r.status_code == 422, r.text

    async def test_patch_job_branch_id_to_other_users_branch_rejected(
        self, client, user_a_headers, user_b_headers
    ) -> None:
        # user B creates a branch
        r = await client.post(
            "/api/v1/resume-branches",
            headers=user_b_headers,
            json={"name": "B-branch", "company": "B", "position": "B"},
        )
        assert r.status_code in (200, 201), r.text
        b_branch_id = r.json()["branch"]["id"]

        # user A creates a job and tries to bind to B's branch
        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={"company": "A", "position": "A"},
        )
        job_id = r.json()["id"]
        r = await client.patch(
            f"/api/v1/jobs/{job_id}",
            headers=user_a_headers,
            json={"branch_id": b_branch_id},
        )
        # The PATCH filters on user_id, so this becomes 404 (no such job/branch pair)
        assert r.status_code in (404, 422), r.text
