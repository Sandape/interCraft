"""Integration tests for Supervisor routing (T025, REQ-06).

Tests:
- plan→interviewer state propagation (_planner_complete_node)
- skip Tavily when plan is already cached (planner_search_node T021)
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_tavily(monkeypatch):
    """Prevent real network calls to Tavily API."""

    async def _empty_search(query, **kwargs):
        return ""

    monkeypatch.setattr(
        "app.agents.interview.nodes.planner_search.tavily_search",
        _empty_search,
    )


# ---------------------------------------------------------------------------
# T025 — Supervisor routing tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_planner_complete_propagates_plan():
    """After planner subgraph completes, _planner_complete_node forwards
    interview_plan and web_research to shared state so the interviewer
    (question_gen) can read them.

    Acceptance Scenario 2 (partial): plan → interviewer state propagation.
    """
    from app.agents.interview.graph import _planner_complete_node

    plan = {
        "target_company": "TestCorp",
        "target_position": "后端工程师",
        "focus_areas": [
            {"area": "技术深度", "weight": 0.8, "reason": "JD 要求"},
        ],
        "suggested_questions": ["问题1"],
        "tips": [],
        "tech_stack": ["Python"],
        "interview_difficulty": "hard",
    }
    web_research = {
        "interview_experience": [{"title": "面经", "content": "内容", "url": "https://example.com"}],
        "company_tech_stack": [],
        "common_questions": [],
    }

    state = {
        "interview_plan": plan,
        "web_research": web_research,
    }

    result = _planner_complete_node(state)

    assert result["interview_plan"] == plan
    assert result["web_research"] == web_research

    # Verify the forwarded data is structurally intact (dict, not serialized string)
    assert isinstance(result["interview_plan"], dict)
    assert result["interview_plan"]["target_company"] == "TestCorp"
    assert len(result["interview_plan"]["focus_areas"]) == 1
    assert isinstance(result["web_research"], dict)
    assert len(result["web_research"]["interview_experience"]) == 1


@pytest.mark.asyncio
async def test_planner_complete_handles_null_plan():
    """_planner_complete_node gracefully handles null/missing plan data."""
    from app.agents.interview.graph import _planner_complete_node

    # No plan / no web_research in state
    state: dict = {}
    result = _planner_complete_node(state)

    assert result["interview_plan"] is None
    assert result["web_research"] is None


@pytest.mark.asyncio
async def test_planner_search_skips_when_plan_cached():
    """When interview_plan already exists in state (T021), planner_search_node
    skips Tavily search and returns the existing web_research unchanged.

    Acceptance Scenario 2 (partial): skip Tavily when cached.
    """
    from app.agents.interview.nodes.planner_search import planner_search_node

    existing_web_research = {
        "interview_experience": [{"title": "已有面经", "content": "已有内容", "url": "https://example.com"}],
        "company_tech_stack": [],
        "common_questions": [],
    }

    state = {
        "interview_plan": {"target_company": "CachedCorp"},  # Non-None → skip
        "web_research": existing_web_research,
        "company": "CachedCorp",
        "position": "工程师",
    }

    result = await planner_search_node(state)

    assert "web_research" in result
    # Web research should be the original, not a new search
    wr = result["web_research"]
    assert len(wr["interview_experience"]) == 1
    assert wr["interview_experience"][0]["title"] == "已有面经"


@pytest.mark.asyncio
async def test_planner_search_skips_and_creates_empty_when_no_existing():
    """When interview_plan is cached but web_research is missing,
    planner_search_node returns an empty WebResearch instead of crashing."""
    from app.agents.interview.nodes.planner_search import planner_search_node
    from app.agents.interview.schemas import WebResearch

    state = {
        "interview_plan": {"target_company": "CachedCorp"},
        # No web_research in state
        "company": "CachedCorp",
        "position": "工程师",
    }

    result = await planner_search_node(state)

    assert "web_research" in result
    wr = result["web_research"]
    # Should be an empty WebResearch dict
    expected_empty = WebResearch().model_dump()
    assert wr == expected_empty


@pytest.mark.asyncio
async def test_planner_search_does_not_skip_when_no_plan():
    """When interview_plan is None, planner_search_node performs the search."""
    from app.agents.interview.nodes.planner_search import planner_search_node

    state = {
        "interview_plan": None,  # Not cached → run search
        "company": "FreshCorp",
        "position": "工程师",
        "web_research": None,
    }

    result = await planner_search_node(state)

    assert "web_research" in result
    wr = result["web_research"]
    # Search ran — web_research should be a non-None dict with all 3 keys
    assert isinstance(wr, dict)
    assert "interview_experience" in wr
    assert "company_tech_stack" in wr
    assert "common_questions" in wr
