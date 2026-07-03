"""REQ-042 US-1 MB1 — Configuration.max_iterations + recursion_limit.

AC-1.1 ~ AC-1.5 (FR-001) + AC-2.1 ~ AC-2.3 (FR-002) + AC-4.3 (MaxIterationsReached inherits RuntimeError).

Test-First red-phase commit per REQ-041 AC-9.1 pattern.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# AC-1.1 — Configuration.max_iterations field
# ---------------------------------------------------------------------------
class TestConfigurationMaxIterations:
    def test_configuration_module_exists(self):
        """AC-1.1: ``loop_termination`` module exists with ``Configuration`` class."""
        from app.agents.utils.loop_termination import Configuration

        assert Configuration is not None

    def test_max_iterations_field_default(self):
        """AC-1.1: ``Configuration.max_iterations: int`` with default >= 10."""
        from app.agents.utils.loop_termination import Configuration

        config = Configuration()
        assert isinstance(config.max_iterations, int)
        assert config.max_iterations >= 10


# ---------------------------------------------------------------------------
# AC-1.2 — 5 agent-specific default values
# ---------------------------------------------------------------------------
class TestPerAgentDefaults:
    def test_interview_default_is_5(self):
        """AC-1.2: interview agent has max_iterations=5."""
        from app.agents.utils.loop_termination import InterviewStateConfiguration

        assert InterviewStateConfiguration().max_iterations == 5

    def test_error_coach_default_is_10(self):
        """AC-1.2: error_coach has max_iterations=10."""
        from app.agents.utils.loop_termination import ErrorCoachStateConfiguration

        assert ErrorCoachStateConfiguration().max_iterations == 10

    def test_planner_default_is_6(self):
        """AC-1.2: planner has max_iterations=6."""
        from app.agents.utils.loop_termination import PlannerStateConfiguration

        assert PlannerStateConfiguration().max_iterations == 6

    def test_researcher_default_is_10(self):
        """AC-1.2: researcher has max_iterations=10."""
        from app.agents.utils.loop_termination import ResearcherStateConfiguration

        assert ResearcherStateConfiguration().max_iterations == 10

    def test_general_coach_default_is_10(self):
        """AC-1.2: general_coach has max_iterations=10."""
        from app.agents.utils.loop_termination import GeneralCoachStateConfiguration

        assert GeneralCoachStateConfiguration().max_iterations == 10

    def test_all_five_defaults_match(self):
        """AC-1.2: tuple of 5 agent defaults is (5, 10, 6, 10, 10)."""
        from app.agents.utils.loop_termination import (
            ErrorCoachStateConfiguration,
            GeneralCoachStateConfiguration,
            InterviewStateConfiguration,
            PlannerStateConfiguration,
            ResearcherStateConfiguration,
        )

        defaults = (
            InterviewStateConfiguration().max_iterations,
            ErrorCoachStateConfiguration().max_iterations,
            PlannerStateConfiguration().max_iterations,
            ResearcherStateConfiguration().max_iterations,
            GeneralCoachStateConfiguration().max_iterations,
        )
        assert defaults == (5, 10, 6, 10, 10)


# ---------------------------------------------------------------------------
# AC-1.4 — iteration_count reducer (add)
# ---------------------------------------------------------------------------
class TestIterationCountReducer:
    def test_iteration_count_reducer_adds(self):
        """AC-1.4: iteration_count reducer adds two values."""
        from app.agents.utils.loop_termination import iteration_count_reducer

        result = iteration_count_reducer({"iteration_count": 1}, {"iteration_count": 2})
        assert result == {"iteration_count": 3}

    def test_iteration_count_reducer_handles_missing(self):
        """AC-1.4: reducer treats missing key as 0."""
        from app.agents.utils.loop_termination import iteration_count_reducer

        result = iteration_count_reducer({}, {"iteration_count": 5})
        assert result == {"iteration_count": 5}


# ---------------------------------------------------------------------------
# AC-2.1 + AC-2.2 — recursion_limit per agent
# ---------------------------------------------------------------------------
class TestRecursionLimit:
    def test_recursion_limit_field_exists(self):
        """AC-2.1: ``Configuration.recursion_limit: int`` exists."""
        from app.agents.utils.loop_termination import Configuration

        config = Configuration()
        assert isinstance(config.recursion_limit, int)
        assert config.recursion_limit > 0

    def test_interview_recursion_limit_is_30(self):
        """AC-2.2: interview recursion_limit=30."""
        from app.agents.utils.loop_termination import InterviewStateConfiguration

        assert InterviewStateConfiguration().recursion_limit == 30

    def test_error_coach_recursion_limit_is_20(self):
        """AC-2.2: error_coach recursion_limit=20."""
        from app.agents.utils.loop_termination import ErrorCoachStateConfiguration

        assert ErrorCoachStateConfiguration().recursion_limit == 20

    def test_researcher_recursion_limit_is_25(self):
        """AC-2.2: researcher recursion_limit=25."""
        from app.agents.utils.loop_termination import ResearcherStateConfiguration

        assert ResearcherStateConfiguration().recursion_limit == 25

    def test_planner_recursion_limit_is_25(self):
        """AC-2.2: planner recursion_limit=25."""
        from app.agents.utils.loop_termination import PlannerStateConfiguration

        assert PlannerStateConfiguration().recursion_limit == 25

    def test_general_coach_recursion_limit_is_25(self):
        """AC-2.2: general_coach recursion_limit=25."""
        from app.agents.utils.loop_termination import GeneralCoachStateConfiguration

        assert GeneralCoachStateConfiguration().recursion_limit == 25


# ---------------------------------------------------------------------------
# AC-4.3 — MaxIterationsReached inherits RuntimeError (L041-005)
# ---------------------------------------------------------------------------
class TestMaxIterationsReachedInheritance:
    def test_max_iterations_reached_is_runtime_error(self):
        """AC-4.3 / L041-005: MaxIterationsReached must inherit RuntimeError.

        Critical for 040 AC-4.6 ``pytest.raises(RuntimeError)`` compatibility
        in retry_graph_op wrapper.
        """
        from app.agents.utils.loop_termination import MaxIterationsReached

        assert issubclass(MaxIterationsReached, RuntimeError)

    def test_max_iterations_reached_attributes(self):
        """AC-4.3: stores agent_name, limit, actual on instance."""
        from app.agents.utils.loop_termination import MaxIterationsReached

        exc = MaxIterationsReached(agent_name="interview", limit=5, actual=7)
        assert exc.agent_name == "interview"
        assert exc.limit == 5
        assert exc.actual == 7
        assert "interview" in str(exc)
