"""Integration test for M18 Ability Diagnose complete flow.

Tests: ARQ task triggers → aggregate_scores → compare_baseline →
       generate_insight → update_dimensions → dimensions updated + activities written

Per Constitution III: these must FAIL before implementation.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]

_SESSION_ID = "019b5e6c-0000-7000-0000-000000000000"
_USER_ID = "019b5e6c-0000-7000-0000-000000000003"


@pytest.mark.asyncio
async def test_ability_diagnose_full_flow():
    """M18 full pipeline: run diagnose → verify dimensions + activities."""
    from app.agents.graphs.ability_diagnose import get_ability_diagnose_graph

    graph = get_ability_diagnose_graph()
    result = await graph.run(user_id=_USER_ID, session_id=_SESSION_ID)

    assert result is not None
    assert "diagnoses" in result
    assert "insights" in result

    # Verify dimensions were updated
    diagnoses = result.get("diagnoses", [])
    assert len(diagnoses) > 0

    for d in diagnoses:
        assert "dimension" in d
        assert "current_score" in d
        assert "delta" in d
        assert "trend" in d

    # Verify insights were generated
    insights = result.get("insights", [])
    assert len(insights) > 0

    for insight in insights:
        assert "dimension" in insight
        assert "suggestions" in insight
        assert len(insight["suggestions"]) > 0


@pytest.mark.asyncio
async def test_ability_diagnose_empty_session():
    """M18 handles missing session gracefully."""
    from app.agents.graphs.ability_diagnose import get_ability_diagnose_graph

    graph = get_ability_diagnose_graph()
    result = await graph.run(
        user_id="00000000-0000-0000-0000-000000000000",
        session_id="00000000-0000-0000-0000-000000000000",
    )

    # Should not crash, may return empty results
    assert result is not None
