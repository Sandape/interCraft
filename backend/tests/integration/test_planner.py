"""Integration tests for Planner logic (T017, REQ-03/05).

Tests planner subgraph nodes across normal and fallback paths:
- resume+JD → plan with all required fields (serialization)
- missing resume fallback (no crash)
- no Tavily fallback (no crash)
"""
from __future__ import annotations

import json
import secrets
import uuid

import pytest

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register_user(client, suffix: str) -> tuple[dict, str]:
    """Register a test user and return (auth_headers, user_id)."""
    email = f"planner_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": f"planner-{suffix}",
            "device_fingerprint": fp,
        },
        headers={
            "X-Device-Fingerprint": fp,
            "X-Request-ID": f"req-{secrets.token_hex(8)}",
        },
    )
    assert reg.status_code in (200, 201), reg.text
    access = reg.json()["tokens"]["access_token"]
    headers = {
        "Authorization": f"Bearer {access}",
        "X-Device-Fingerprint": fp,
        "X-Request-ID": f"req-{secrets.token_hex(8)}",
    }
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, me.json()["id"]


async def _create_branch(client, headers: dict, **payload) -> dict:
    r = await client.post("/api/v1/resume-branches", json=payload, headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["branch"]


async def _create_block(client, headers: dict, branch_id: str, **payload) -> dict:
    r = await client.post(
        f"/api/v1/resume-branches/{branch_id}/blocks",
        json=payload,
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["block"]


async def _create_job(client, headers: dict, **payload) -> dict:
    r = await client.post("/api/v1/jobs", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _make_tavily_payload(query: str) -> list[dict]:
    """Map a single search query to a structured ``list[dict]`` payload.

    Production ``tavily_search`` returns structured result dicts; tests
    previously returned the legacy plain-text block format. After the tool
    migrated to a LangChain ``@tool`` returning ``list[dict]``,
    ``planner_search._parse_tavily_output`` now consumes the structured form
    directly, so the fixture mirrors that.
    """
    entries: list[dict] = []
    if "面经" in query:
        entries.append(
            {
                "title": "TestCorp 后端面经",
                "content": "主要询问了 Python 相关问题和系统设计",
                "url": "https://example.com/mianshi",
                "score": 0.95,
            }
        )
    if "tech stack" in query.lower():
        entries.append(
            {
                "title": "TestCorp 技术栈",
                "content": "Python, Go, PostgreSQL 是主要技术栈",
                "url": "https://example.com/techstack",
                "score": 0.90,
            }
        )
    if "common questions" in query.lower():
        entries.append(
            {
                "title": "TestCorp 常见问题",
                "content": "系统设计、Python 基础、数据库优化",
                "url": "https://example.com/questions",
                "score": 0.88,
            }
        )
    return entries


def _build_tavily_tool_stub(handler):
    """Wrap an async ``handler(payload) -> list[dict]`` as a LangChain-tool-like
    object exposing ``.ainvoke`` so production
    ``planner_search._run_tavily_query`` keeps working under monkeypatch.
    """

    class _TavilyStub:
        async def ainvoke(self, payload):
            queries = payload.get("queries") if isinstance(payload, dict) else None
            if not queries:
                return await handler("")
            merged: list[dict] = []
            for q in queries:
                merged.extend(await handler(q))
            return merged

    return _TavilyStub()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_tavily_default(monkeypatch):
    """Default: tavily_search returns empty results.

    Individual tests that need search results can override by calling
    ``monkeypatch.setattr`` on *the same target* in the test body.
    """
    async def _empty_search(query: str) -> list[dict]:
        return []

    monkeypatch.setattr(
        "app.agents.interview.nodes.planner_search.tavily_search",
        _build_tavily_tool_stub(_empty_search),
    )


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    """Mock LLM so planner_generate returns a valid InterviewPlan JSON.

    The mock returns the same fixed plan regardless of input — enough to
    verify serialization and fallback logic.
    """
    from app.agents.llm_client import LLMResponse

    # NOTE: target_company / target_position are intentionally omitted so
    # the validation code falls back to state.company / state.position,
    # making assertions predictable across tests with different companies.
    plan_payload = json.dumps({
        "focus_areas": [
            {
                "name": "技术深度",
                "weight": 0.8,
                "reason": "JD 要求深入掌握核心技能，候选人简历中有相关经验",
            },
            {
                "name": "系统设计",
                "weight": 0.6,
                "reason": "后端岗位需要良好的架构设计能力",
            },
        ],
        "difficulty": "hard",
        "suggested_questions": [
            "请描述你遇到的最复杂的技术挑战以及解决方案",
            "如何优化系统性能？请从原理层面说明",
        ],
        "interviewer_tips": [
            "重点关注候选人的实际决策过程",
            "可以通过追问了解技术深度",
        ],
        "tech_stack": ["Python", "PostgreSQL"],
    }, ensure_ascii=False)

    class _MockPlannerLLM:
        async def invoke(self, *, messages, node_name, **kwargs):
            return LLMResponse(
                content=plan_payload,
                model="mock",
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=0,
                checkpoint_id=None,
            )

    monkeypatch.setattr(
        "app.agents.interview.nodes.planner_generate.get_llm_client",
        lambda: _MockPlannerLLM(),
    )


# ---------------------------------------------------------------------------
# T017 — Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_planner_resume_jd_full_path(client, monkeypatch):
    """Resume + JD → plan contains all required fields (serialization).

    Acceptance Scenario 1: Planner receives resume + JD → generates plan
    with target_company, target_position, focus_areas, suggested_questions,
    interview_difficulty, tech_stack, and tips.
    """
    # -- Arrange -----------------------------------------------------------
    suffix = uuid.uuid4().hex[:8]
    headers, user_id = await _register_user(client, suffix)

    # Create resume (branch + blocks)
    branch = await _create_branch(
        client, headers, name="核心简历", is_main=True,
        company="TestCorp", position="后端工程师",
    )
    branch_id = branch["id"]

    await _create_block(
        client, headers, branch_id,
        type="skill", title=None, content_md="Python, PostgreSQL, Redis, Docker",
    )
    await _create_block(
        client, headers, branch_id,
        type="experience", title="TestCorp 后端开发",
        content_md="负责核心 API 开发和系统设计",
    )

    # Create job with JD
    job = await _create_job(
        client, headers,
        company="TestCorp", position="后端工程师",
        requirements_md="熟悉 Python, PostgreSQL, 有高并发系统经验",
        base_location="北京",
        employment_type="experienced",
    )
    job_id = job["id"]

    # Mock Tavily returning structured results for all 3 dimensions
    async def _mock_search(query: str) -> list[dict]:
        return _make_tavily_payload(query)

    monkeypatch.setattr(
        "app.agents.interview.nodes.planner_search.tavily_search",
        _build_tavily_tool_stub(_mock_search),
    )

    # -- Act ---------------------------------------------------------------
    from app.agents.interview.nodes.planner_context import planner_context_node
    from app.agents.interview.nodes.planner_generate import planner_generate_node
    from app.agents.interview.nodes.planner_search import planner_search_node

    state = {
        "branch_id": branch_id,
        "job_id": job_id,
        "user_id": user_id,
        "company": "TestCorp",
        "position": "后端工程师",
        "messages": [],
        "thread_id": f"test-planner-{suffix}",
    }

    # 1) Load context from DB
    ctx_result = await planner_context_node(state)
    assert "planner_context" in ctx_result
    pc = ctx_result["planner_context"]

    assert pc["resume"]["has_resume"] is True
    assert pc["resume"]["branch_company"] == "TestCorp"
    assert pc["resume"]["branch_position"] == "后端工程师"
    assert len(pc["resume"]["skills"]) > 0
    assert len(pc["resume"]["experiences"]) > 0
    assert pc["job"]["has_job"] is True
    assert pc["job"]["company"] == "TestCorp"
    assert pc["job"]["position"] == "后端工程师"
    assert "missing_fields" not in pc

    # 2) Run Tavily search
    state["planner_context"] = pc
    search_result = await planner_search_node(state)
    assert "web_research" in search_result

    wr = search_result["web_research"]
    assert len(wr.get("interview_experience", [])) > 0
    assert len(wr.get("company_tech_stack", [])) > 0
    assert len(wr.get("common_questions", [])) > 0

    # 3) Generate plan
    state["web_research"] = wr
    gen_result = await planner_generate_node(state)
    assert "interview_plan" in gen_result

    plan = gen_result["interview_plan"]

    # -- Assert ------------------------------------------------------------
    assert plan["target_company"] == "TestCorp"
    assert plan["target_position"] == "后端工程师"
    assert len(plan["focus_areas"]) >= 2
    for fa in plan["focus_areas"]:
        assert "area" in fa
        assert "weight" in fa
        assert "reason" in fa
        assert 0.0 <= fa["weight"] <= 1.0
    assert len(plan["suggested_questions"]) >= 2
    assert isinstance(plan["suggested_questions"], list)
    assert all(isinstance(q, str) for q in plan["suggested_questions"])
    assert plan["interview_difficulty"] in ("easy", "medium", "hard")
    assert isinstance(plan["tech_stack"], list)
    assert isinstance(plan["tips"], list)


@pytest.mark.asyncio
async def test_planner_missing_resume(client):
    """Missing resume → plan generated from JD + Tavily only, no crash.

    Acceptance Scenario 4: No resume data available — planner still produces
    a valid plan based solely on the job description and web research.
    """
    # -- Arrange -----------------------------------------------------------
    suffix = uuid.uuid4().hex[:8]
    headers, user_id = await _register_user(client, suffix)

    # Create job only — no resume branch
    job = await _create_job(
        client, headers,
        company="TestCorp2", position="运维工程师",
        requirements_md="熟悉 Linux, Kubernetes, CI/CD",
        base_location="上海",
        employment_type="experienced",
    )
    job_id = job["id"]

    # -- Act ---------------------------------------------------------------
    from app.agents.interview.nodes.planner_context import planner_context_node
    from app.agents.interview.nodes.planner_generate import planner_generate_node
    from app.agents.interview.nodes.planner_search import planner_search_node

    state = {
        "branch_id": None,  # No resume
        "job_id": job_id,
        "user_id": user_id,
        "company": "TestCorp2",
        "position": "运维工程师",
        "messages": [],
        "thread_id": f"test-planner-nr-{suffix}",
    }

    # 1) Load context — resume should be missing
    ctx_result = await planner_context_node(state)
    assert "planner_context" in ctx_result
    pc = ctx_result["planner_context"]

    assert pc["resume"]["has_resume"] is False
    assert pc["job"]["has_job"] is True
    # missing_fields should indicate resume_data is absent
    assert "missing_fields" in pc
    assert "resume_data" in pc["missing_fields"]

    # 2) Search — works from company+position
    state["planner_context"] = pc
    search_result = await planner_search_node(state)
    assert "web_research" in search_result

    # 3) Generate plan — succeeds without resume
    state["web_research"] = search_result["web_research"]
    gen_result = await planner_generate_node(state)
    assert "interview_plan" in gen_result

    plan = gen_result["interview_plan"]
    assert plan["target_company"] == "TestCorp2"
    assert plan["target_position"] == "运维工程师"
    # Must still produce a structurally valid plan
    assert isinstance(plan["focus_areas"], list)
    assert isinstance(plan["suggested_questions"], list)
    assert plan["interview_difficulty"] in ("easy", "medium", "hard")


@pytest.mark.asyncio
async def test_planner_no_tavily_fallback(client):
    """No Tavily results → plan generated from resume+JD only, no crash.

    Acceptance Scenario 3: Tavily API is unavailable / returns no results;
    planner must still produce a structurally valid plan from resume + JD.
    """
    # -- Arrange -----------------------------------------------------------
    suffix = uuid.uuid4().hex[:8]
    headers, user_id = await _register_user(client, suffix)

    # Create resume + job
    branch = await _create_branch(
        client, headers, name="核心简历", is_main=True,
        company="TestCorp3", position="前端工程师",
    )
    branch_id = branch["id"]
    await _create_block(
        client, headers, branch_id,
        type="skill", title=None, content_md="TypeScript, React, Vue",
    )
    await _create_block(
        client, headers, branch_id,
        type="experience", title="某公司前端",
        content_md="负责主站前端架构和性能优化",
    )

    job = await _create_job(
        client, headers,
        company="TestCorp3", position="前端工程师",
        requirements_md="精通 TypeScript, React, 有大型前端项目经验",
    )
    job_id = job["id"]

    # Tavily returns empty (no mock override needed — default mock returns "")

    # -- Act ---------------------------------------------------------------
    from app.agents.interview.nodes.planner_context import planner_context_node
    from app.agents.interview.nodes.planner_generate import planner_generate_node
    from app.agents.interview.nodes.planner_search import planner_search_node

    state = {
        "branch_id": branch_id,
        "job_id": job_id,
        "user_id": user_id,
        "company": "TestCorp3",
        "position": "前端工程师",
        "messages": [],
        "thread_id": f"test-planner-nt-{suffix}",
    }

    # 1) Load context
    ctx_result = await planner_context_node(state)
    assert "planner_context" in ctx_result
    pc = ctx_result["planner_context"]
    assert pc["resume"]["has_resume"] is True
    assert pc["job"]["has_job"] is True

    # 2) Search — returns empty (mocked)
    state["planner_context"] = pc
    search_result = await planner_search_node(state)
    assert "web_research" in search_result

    wr = search_result["web_research"]
    assert len(wr.get("interview_experience", [])) == 0
    assert len(wr.get("company_tech_stack", [])) == 0
    assert len(wr.get("common_questions", [])) == 0

    # 3) Generate plan — succeeds despite empty web research
    state["web_research"] = wr
    gen_result = await planner_generate_node(state)
    assert "interview_plan" in gen_result

    plan = gen_result["interview_plan"]
    assert plan["target_company"] == "TestCorp3"
    assert plan["target_position"] == "前端工程师"
    assert isinstance(plan["focus_areas"], list)
    assert isinstance(plan["suggested_questions"], list)
    assert plan["interview_difficulty"] in ("easy", "medium", "hard")
    assert isinstance(plan["tech_stack"], list)
