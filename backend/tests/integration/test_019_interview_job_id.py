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
    async def test_create_interview_with_job_id_derives_position_and_company(
        self, client, user_a_headers
    ) -> None:
        r = await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "Acme PM Resume", "company": "Acme AI", "position": "AI PM"},
        )
        assert r.status_code in (200, 201), r.text
        branch_id = r.json()["branch"]["id"]

        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={
                "company": "Acme AI",
                "position": "AI Product Manager",
                "requirements_md": "Original JD: own roadmap, prompt design, and AI product metrics.",
            },
        )
        assert r.status_code in (200, 201), r.text
        job_id = r.json()["id"]

        r = await client.post(
            "/api/v1/interview-sessions",
            headers=user_a_headers,
            json={
                "job_id": job_id,
                "branch_id": branch_id,
                "mode": "full",
                "max_questions": 10,
            },
        )
        assert r.status_code in (200, 201), r.text
        session_id = r.json()["data"]["id"]

        r = await client.get(
            f"/api/v1/interview-sessions/{session_id}",
            headers=user_a_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["job_id"] == job_id
        assert body["branch_id"] == branch_id
        assert body["company"] == "Acme AI"
        assert body["position"] == "AI Product Manager"

    async def test_create_interview_accepts_v2_resume_id_as_branch_context(
        self, client, user_a_headers
    ) -> None:
        r = await client.post(
            "/api/v1/v2/resumes",
            headers=user_a_headers,
            json={"name": "V2 PM Resume", "slug": "v2-pm-resume", "template": "onyx"},
        )
        assert r.status_code in (200, 201), r.text
        resume_id = (r.json().get("resume") or r.json())["id"]

        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={
                "company": "Acme AI",
                "position": "AI Product Manager",
                "requirements_md": "Original JD: prompt design and AI product metrics.",
            },
        )
        assert r.status_code in (200, 201), r.text
        job_id = r.json()["id"]

        r = await client.post(
            "/api/v1/interview-sessions",
            headers=user_a_headers,
            json={"job_id": job_id, "branch_id": resume_id, "mode": "doubao"},
        )
        assert r.status_code in (200, 201), r.text
        session_id = r.json()["data"]["id"]

        r = await client.get(
            f"/api/v1/interview-sessions/{session_id}",
            headers=user_a_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["branch_id"] == resume_id
        assert body["job_id"] == job_id
        assert body["company"] == "Acme AI"
        assert body["position"] == "AI Product Manager"

    async def test_generate_plan_endpoint_persists_plan_without_starting_qa(
        self, client, user_a_headers, monkeypatch
    ) -> None:
        async def fake_context(state):
            return {
                "planner_context": {
                    "resume": {"has_resume": True, "name": "Acme PM Resume"},
                    "job": {
                        "has_job": True,
                        "company": state["company"],
                        "position": state["position"],
                        "requirements_md": "Original JD must stay intact.",
                    },
                }
            }

        async def fake_search(_state):
            return {"web_research": {"interview_experience": [], "company_tech_stack": [], "common_questions": []}}

        async def fake_generate(state):
            return {
                "interview_plan": {
                    "target_company": state["company"],
                    "target_position": state["position"],
                    "job_requirements": "Use the original JD.",
                    "tech_stack": ["LLM", "Prompt"],
                    "interview_difficulty": "medium",
                    "focus_areas": [{"area": "Prompt design", "weight": 0.7, "reason": "Core job duty"}],
                    "suggested_questions": ["How would you design the Doubao interview prompt?"],
                    "web_research_summary": None,
                    "tips": ["Ask one question at a time."],
                }
            }

        monkeypatch.setattr(
            "app.agents.interview.nodes.planner_context.planner_context_node",
            fake_context,
        )
        monkeypatch.setattr(
            "app.agents.interview.nodes.planner_search.planner_search_node",
            fake_search,
        )
        monkeypatch.setattr(
            "app.agents.interview.nodes.planner_generate.planner_generate_node",
            fake_generate,
        )

        r = await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "Acme PM Resume", "company": "Acme AI", "position": "AI PM"},
        )
        assert r.status_code in (200, 201), r.text
        branch_id = r.json()["branch"]["id"]

        r = await client.post(
            "/api/v1/jobs",
            headers=user_a_headers,
            json={
                "company": "Acme AI",
                "position": "AI Product Manager",
                "requirements_md": "Original JD must stay intact.",
            },
        )
        assert r.status_code in (200, 201), r.text
        job_id = r.json()["id"]

        r = await client.post(
            "/api/v1/interview-sessions",
            headers=user_a_headers,
            json={"job_id": job_id, "branch_id": branch_id, "mode": "doubao"},
        )
        assert r.status_code in (200, 201), r.text
        session_id = r.json()["data"]["id"]

        r = await client.post(
            f"/api/v1/interview-sessions/{session_id}/plan",
            headers=user_a_headers,
        )
        assert r.status_code == 200, r.text
        plan = r.json()["data"]["interview_plan"]
        assert plan["target_company"] == "Acme AI"
        assert plan["target_position"] == "AI Product Manager"
        assert plan["focus_areas"][0]["area"] == "Prompt design"

        r = await client.get(
            f"/api/v1/interview-sessions/{session_id}",
            headers=user_a_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["interview_plan"]["suggested_questions"][0].startswith("How would")
        assert body["overall_score"] is None

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
