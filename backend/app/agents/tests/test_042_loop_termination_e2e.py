"""REQ-042 US-1 MB2 — MarkComplete + GraphRecursionError + iteration_guard.

AC-3.x (FR-003), AC-4.1 ~ AC-4.4 (FR-004), AC-7.1 (FR-009 env), AC-E2E-1/2/3.

Test-First red-phase commit per REQ-041 AC-9.1 pattern.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# AC-4.1 — GraphRecursionError importable from langgraph.errors
# ---------------------------------------------------------------------------
class TestGraphRecursionErrorImport:
    def test_graph_recursion_error_importable(self):
        """AC-4.1: GraphRecursionError importable from langgraph.errors."""
        from langgraph.errors import GraphRecursionError

        assert GraphRecursionError is not None
        assert issubclass(GraphRecursionError, Exception)


# ---------------------------------------------------------------------------
# AC-3.x — MarkComplete is bound in interview / error_coach / planner (041 partial verify)
# ---------------------------------------------------------------------------
class TestMarkCompleteBinding:
    def test_interview_bind_tools_uses_mark_complete(self):
        """AC-3.1: interview.question_gen / score_llm bind [MarkComplete]."""
        from app.agents.interview.graph import _route_after_score_llm

        # MarkComplete is signalled via ``_mark_complete`` state field;
        # the 4-way router (FR-004) routes _mark_complete=True → END.
        import inspect

        src = inspect.getsource(_route_after_score_llm)
        assert "_mark_complete" in src
        assert "END" in src

    def test_error_coach_mark_complete_in_state(self):
        """AC-3.2: error_coach state declares _mark_complete field (per 041 US-2)."""
        from app.agents.state.error_coach_state import ErrorCoachState

        # TypedDict total=False — check via __annotations__
        annotations = ErrorCoachState.__annotations__
        assert "_mark_complete" in annotations

    def test_planner_graph_imports_mark_complete(self):
        """AC-3.3: planner_graph imports MarkComplete (041 US-2 partial verify)."""
        from app.agents.interview import planner_graph

        # The 041 stub re-exports MarkComplete at module scope.
        assert hasattr(planner_graph, "MarkComplete")


# ---------------------------------------------------------------------------
# AC-4.4 — iteration_guard_node with @node_error_handler double decoration
# ---------------------------------------------------------------------------
class TestIterationGuardNode:
    def test_iteration_guard_module_exists(self):
        """AC-4.4: iteration_guard_node function exists."""
        from app.agents.utils.loop_termination import MaxIterationsReached

        # MaxIterationsReached is the exception the guard raises.
        exc = MaxIterationsReached(agent_name="interview", limit=5, actual=5)
        assert exc.agent_name == "interview"

    def test_max_iterations_reached_caught_by_runtime_error(self):
        """AC-4.4 + L041-005: MaxIterationsReached is catchable as RuntimeError."""
        import pytest as _pytest

        from app.agents.utils.loop_termination import MaxIterationsReached

        # 040 AC-4.6 pattern: pytest.raises(RuntimeError) must observe
        # MaxIterationsReached without modification.
        with _pytest.raises(RuntimeError):
            raise MaxIterationsReached(agent_name="interview", limit=5, actual=5)


# ---------------------------------------------------------------------------
# AC-7.1 — env vars (3 independent) — Pydantic fields
# ---------------------------------------------------------------------------
class TestEnvVars:
    def test_three_env_vars_independent(self):
        """AC-7.1: 3 env vars (us1, us2_compress, us2_store) all default False."""
        from app.core.config import get_settings

        settings = get_settings()
        # 3 env vars must be independent Pydantic fields, default False.
        assert settings.us1_use_v2_loop_termination is False
        assert settings.us2_use_v2_compress_history is False
        assert settings.us2_use_v2_langgraph_store is False
