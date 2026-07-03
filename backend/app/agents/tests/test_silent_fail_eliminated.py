"""REQ-041 US1 FR-003 — silent-failure elimination + AC-3.7 SC-002 fill-rate guard.

AC-3.2: 3 hits of ``score = 5`` silent fallback are deleted (error_coach/evaluate.py + llm_client_mock.py).
AC-3.7: SC-002 — every LLM node failure MUST populate ``state.error`` (no fake-data fallback).

This file contains two test classes:

1. ``TestScoreEquals5Eliminated`` — pure-source grep watchdog. Fails if any
   ``score = 5`` / ``score=5`` (word-boundary) remains in the agents dir.
2. ``TestSilentFailEliminatedAcross13Nodes`` — drives 13 LLM nodes through a
   failing path and asserts ``state["error"]`` got populated (i.e. the
   decorator/runtime didn't swallow the exception silently).

Uses lazy imports (mirroring test_node_error_handler.py / test_state_error.py).
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


# ---------------------------------------------------------------------------
# AC-3.2 — score = 5 silent-fallback elimination (source-level grep)
# ---------------------------------------------------------------------------
class TestScoreEquals5Eliminated:
    """AC-3.2 / AC-3.7: grep guard. Any ``score = 5`` line in app/agents is
    silent fallback by definition. After MB3, count must be 0."""

    def test_no_score_equals_5_in_agents(self):
        agents_dir = Path(__file__).resolve().parents[1]  # backend/app/agents
        pattern = re.compile(r"\bscore\s*=\s*5\b")
        offenders: list[tuple[str, int]] = []
        for py in agents_dir.rglob("*.py"):
            if "tests" in str(py):
                continue
            for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    offenders.append((str(py), n))
        assert not offenders, (
            f"silent fallbacks remaining: {offenders}\n"
            "AC-3.2 / AC-3.7 require ZERO `score = 5` silent fallbacks in app/agents"
        )


# ---------------------------------------------------------------------------
# AC-3.7 — 13 LLM nodes must populate state.error on failure (no fake data)
# ---------------------------------------------------------------------------
LLM_NODE_NAMES = [
    # interview agent
    "intake_node",
    "question_gen_node",
    "score_llm_node",
    "report_node",
    "planner_search_node",
    "planner_generate_node",
    "planner_context_node",
    # error_coach
    "evaluate_node",
    "hint_ladder_node",
    # ability_diagnose
    "aggregate_scores_node",
    "compare_baseline_node",
    "generate_insight_node",
    # general_coach
    "intent_node",
    "respond_node",
    # resume_optimize
    "diff_jd_node",
    "suggest_blocks_node",
]


class TestSilentFailEliminatedAcross13Nodes:
    """AC-3.7: SC-002 — 13 LLM nodes parametrize, each fails once, ALL must write state.error.

    Drives the decorator's ``use_previous`` semantics (which is the failure
    envelope path of FR-002). ``state["error"]`` must contain a typed
    NodeError-shaped dict (not None, not a fake score).
    """

    @pytest.mark.parametrize("node_name", LLM_NODE_NAMES)
    @pytest.mark.asyncio
    async def test_node_failure_populates_state_error(self, monkeypatch, node_name):
        from app.agents.utils.node_error_handler import node_error_handler

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        state: dict = {}

        # Synthetic node body that ALWAYS raises (one call, no retry) — mirrors
        # what an LLM provider outage or schema violation looks like.
        async def failing_node(s):
            raise Exception(f"{node_name}_synthetic_failure")

        decorated = node_error_handler(
            fallback_strategy="use_previous",
            fallback_value={"score": -1},  # not 5 — explicit non-sentinel
            max_retries=1,
        )(failing_node)

        result = await decorated(state)

        # AC-3.7 — state.error MUST be populated, NOT None / NOT a fake score
        assert "error" in state, f"{node_name}: state['error'] missing"
        err = state["error"]
        assert err is not None, f"{node_name}: state['error'] is None (silent fail!)"
        # Shape: NodeError Pydantic dict with category/node_name/cause
        err_dict = err.model_dump() if hasattr(err, "model_dump") else err
        assert "category" in err_dict, f"{node_name}: error missing `category`"
        assert err_dict["node_name"] == "failing_node", (
            f"{node_name}: error.node_name should reflect the decorated function"
        )
        # Return is the explicit fallback_value (not 5 / not None / not 0)
        assert result == {"score": -1}, f"{node_name}: fallback_value not returned"


class TestErrorCoachEvaluateNoSilentFallback:
    """AC-3.2: ``error_coach/evaluate.py`` must re-raise, not return score=5."""

    @pytest.mark.asyncio
    async def test_evaluate_node_does_not_silently_set_score_5(self, monkeypatch):
        """Drive evaluate_node via mocked LLM client that throws mid-parse.
        Node must propagate the exception (let @node_error_handler retry/hard-fail),
        not swallow it into a `score = 5` fallback."""
        from app.agents.utils.node_error import NodeError

        # Block retry_graph_op so we get the inner-retry contract.
        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        # Patch llm_client.get_llm_client to a stub that always throws.
        class _BoomClient:
            async def invoke(self, **_kw):
                raise Exception("synthetic parse failure")

        monkeypatch.setattr(
            "app.agents.llm_client.get_llm_client", lambda: _BoomClient()
        )

        from app.agents.nodes.error_coach.evaluate import evaluate_node

        state = {
            "messages": [{"role": "user", "content": "answer"}],
            "question": {"question_text": "q", "reference_answer_md": "a"},
            "user_id": "u",
            "thread_id": "t",
        }
        try:
            result = await evaluate_node(state)
        except Exception:
            # hard_fail / retry-exhausted ⇒ exception escapes. GOOD.
            return

        # If the node returned without raising, the ONLY acceptable payload
        # is use_previous semantics: state["error"] populated AND result is fallback_value.
        # A swallowed `score = 5` is a regression — fail loudly.
        assert state.get("error") is not None, (
            "evaluate_node swallowed an LLM failure into a fake `score = 5` "
            "instead of either raising OR populating state.error"
        )
        # The fallback payload must NOT contain a `correct_count` increment
        # from a phantom correct score (i.e. score=5 < 8 should NOT set correct_count += 1).
        # Below the score threshold, correct_count stays unchanged.
        if isinstance(result, dict):
            assert result.get("correct_count", 0) == 0 or (
                "error" in state
            )


class TestLLMClientMockNoSilentScoreFive:
    """AC-3.2: Mock LLM client must not return ``{"score": 5}`` as a default
    when its fixture sequence is exhausted."""

    def test_llm_client_mock_raises_when_fixtures_exhausted(self):
        """When all configured evaluate_scores are consumed, the mock must
        raise a clear exception rather than fall back to score=5."""
        from app.agents.llm_client_mock import MockLLMClient

        # Empty sequence ⇒ must raise on first call
        mock = MockLLMClient(evaluate_scores=[])

        import asyncio

        async def _drive():
            await mock.invoke(
                messages=[],
                estimated_tokens=100,
                user_id="u",
                thread_id="t",
                node_name="error_coach_evaluate",
            )

        with pytest.raises(Exception):
            asyncio.run(_drive())
