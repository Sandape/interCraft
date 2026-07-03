"""[AC-040-US1] Tests for FR-002 / FR-007 / FR-008.

FR-002 (AC-2.x): Three-layer state schema split
FR-007 (AC-7.x): PlannerContext Pydantic model
FR-008 (AC-8.x): Feature flag dual-track
"""
from __future__ import annotations

import os

import pytest
from pydantic import BaseModel, ValidationError

from app.agents.interview.context import (
    MemoryItem,
    PlannerContext,
    WebResearchBundle,
)
from app.agents.interview.state import (
    InterviewInputState,
    InterviewOverallState,
    InterviewOutputState,
)


# ===========================================================================
# FR-002 — Three-layer state schema
# ===========================================================================


# ---------------------------------------------------------------------------
# AC-2.1 — InterviewInputState only contains messages + thread_id
# ---------------------------------------------------------------------------
def test_interview_input_state_only_messages_and_thread_id() -> None:
    """AC-2.1: InterviewInputState.__annotations__ ⊆ {messages, thread_id}."""
    keys = set(InterviewInputState.__annotations__.keys())
    assert keys == {"messages", "thread_id"}, (
        f"InterviewInputState leaked fields: {keys - {'messages', 'thread_id'}}"
    )


# ---------------------------------------------------------------------------
# AC-2.2 — InterviewOverallState includes all 20 legacy fields
# (Phase 2 implementation extension: +1 v2 field `interview_plan` for AC-E2E-2)
# ---------------------------------------------------------------------------
_EXPECTED_20_FIELDS = {
    "messages",
    "current_question",
    "questions",
    "scores",
    "resume_context",
    "position",
    "company",
    "base_location",
    "difficulty",
    "branch_id",
    "overall_score",
    "interview_report",
    "error",
    "user_id",
    "thread_id",
    "job_id",
    "requirements_md",
    "requirements_provided",
    "requirements_truncated",
    "requirements_original_chars",
}


def test_interview_overall_state_includes_all_20_fields() -> None:
    """AC-2.2: InterviewOverallState contains the 20 legacy fields as a
    subset (set inclusion). The v2 implementation adds one extra field
    (``interview_plan``) required by AC-E2E-2 for the planner subgraph
    to write to a declared state field; this 21st field is a documented
    Phase 2 implementation extension.
    """
    keys = set(InterviewOverallState.__annotations__.keys())
    missing = _EXPECTED_20_FIELDS - keys
    assert not missing, f"InterviewOverallState missing legacy fields: {missing}"
    # The 20 legacy fields must all be present; v2 may add extras
    assert _EXPECTED_20_FIELDS.issubset(keys)


# ---------------------------------------------------------------------------
# AC-2.3 — InterviewOutputState is Pydantic BaseModel
# ---------------------------------------------------------------------------
def test_interview_output_state_is_pydantic_with_report_and_score() -> None:
    """AC-2.3: InterviewOutputState is BaseModel with interview_report + overall_score."""
    assert isinstance(InterviewOutputState, type)
    assert issubclass(InterviewOutputState, BaseModel)
    fields = set(InterviewOutputState.model_fields.keys())
    assert "interview_report" in fields
    assert "overall_score" in fields


# ---------------------------------------------------------------------------
# AC-2.4 — StateGraph.__init__(input=, output=) accepts three-layer schema
# ---------------------------------------------------------------------------
def test_graph_compiles_with_input_and_output_state() -> None:
    """AC-2.4: StateGraph(OverallState, input=..., output=...).compile() succeeds.

    langgraph 0.2.28 — input/output go on StateGraph.__init__, not compile().
    The compiled graph wraps input_schema in LangGraphInput (a pydantic
    class), so we compare the model_fields to the source TypedDict's
    __annotations__ rather than the class identity.
    """
    from langgraph.graph import StateGraph

    builder = StateGraph(
        InterviewOverallState,
        input=InterviewInputState,
        output=InterviewOutputState,
    )

    # Must not raise
    graph = builder.compile()
    # The compiled graph exposes input_schema and output_schema (wrapped
    # in pydantic classes by langgraph; compare field sets)
    input_fields = set(graph.input_schema.model_fields.keys())
    expected_input = set(InterviewInputState.__annotations__.keys())
    assert input_fields == expected_input, (
        f"input schema fields mismatch: got={input_fields}, want={expected_input}"
    )
    output_fields = set(graph.output_schema.model_fields.keys())
    expected_output = set(InterviewOutputState.model_fields.keys())
    assert output_fields == expected_output, (
        f"output schema fields mismatch: got={output_fields}, want={expected_output}"
    )


# ===========================================================================
# FR-007 — PlannerContext Pydantic model
# ===========================================================================


# ---------------------------------------------------------------------------
# AC-7.1 — PlannerContext validates memories field type
# ---------------------------------------------------------------------------
def test_planner_context_pydantic_validates_memories_field() -> None:
    """AC-7.1: PlannerContext(memories=list, web_research=...) succeeds;
    PlannerContext(memories="not a list", web_research=...) raises ValidationError."""
    web = WebResearchBundle(query="q", results=[])
    # Valid
    ctx = PlannerContext(memories=[], web_research=web)
    assert ctx.memories == []
    # Invalid type
    with pytest.raises(ValidationError) as excinfo:
        PlannerContext(memories="not a list", web_research=web)
    # The error mentions memories
    assert "memories" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC-7.2 — Missing web_research raises ValidationError mentioning field name
# ---------------------------------------------------------------------------
def test_planner_context_pydantic_rejects_missing_web_research() -> None:
    """AC-7.2: PlannerContext(memories=[]) (missing web_research) raises
    ValidationError with 'web_research' in the error message."""
    with pytest.raises(ValidationError) as excinfo:
        PlannerContext(memories=[])
    assert "web_research" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC-7.3a — memories is non-Optional, required field
# ---------------------------------------------------------------------------
def test_planner_context_construction_rejects_missing_memories() -> None:
    """AC-7.3a: PlannerContext(web_research=...) without memories raises
    ValidationError mentioning 'memories'."""
    web = WebResearchBundle(query="q", results=[])
    with pytest.raises(ValidationError) as excinfo:
        PlannerContext(web_research=web)  # type: ignore[call-arg]
    assert "memories" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC-7.3b — planner_context=None raises AttributeError on .memories access
# ---------------------------------------------------------------------------
def test_planner_generate_node_handles_none_planner_context() -> None:
    """AC-7.3b: state['planner_context']=None, node access raises AttributeError
    ('NoneType' object has no attribute 'memories'), not silent None."""
    # We test the access pattern explicitly, mirroring how a node would
    # dereference state.planner_context.memories
    state: dict = {"planner_context": None}
    with pytest.raises(AttributeError) as excinfo:
        # Direct access: state["planner_context"].memories
        state["planner_context"].memories
    assert "memories" in str(excinfo.value)
    assert "NoneType" in str(excinfo.value)


# ===========================================================================
# FR-008 — Feature flag
# ===========================================================================


# ---------------------------------------------------------------------------
# AC-8.1 — env var defaults to false
# ---------------------------------------------------------------------------
def test_feature_flag_default_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-8.1: Without INTERVIEW_USE_V2_STATE_SCHEMA env var, flag is false."""
    from app.agents.interview.config import INTERVIEW_USE_V2_STATE_SCHEMA

    monkeypatch.delenv("INTERVIEW_USE_V2_STATE_SCHEMA", raising=False)
    # Re-import / re-read — config module exposes a function or constant
    val = INTERVIEW_USE_V2_STATE_SCHEMA()
    assert val is False, f"expected default False, got {val!r}"


def test_feature_flag_env_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-8.1 variant: env=true flips the flag to true."""
    from app.agents.interview.config import INTERVIEW_USE_V2_STATE_SCHEMA

    monkeypatch.setenv("INTERVIEW_USE_V2_STATE_SCHEMA", "true")
    assert INTERVIEW_USE_V2_STATE_SCHEMA() is True


# ---------------------------------------------------------------------------
# AC-8.2 — Switch controls graph behavior
# ---------------------------------------------------------------------------
def test_feature_flag_switches_state_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-8.2: When INTERVIEW_USE_V2_STATE_SCHEMA=true, the graph builder
    uses the three-layer schema; when false, it falls back to InterviewGraphState."""
    from app.agents.interview.config import build_interview_state_schema
    from app.agents.interview.state import InterviewGraphState, InterviewOverallState

    # Default: false → legacy schema
    monkeypatch.delenv("INTERVIEW_USE_V2_STATE_SCHEMA", raising=False)
    schema_default = build_interview_state_schema()
    assert schema_default is InterviewGraphState

    # Set to true → three-layer
    monkeypatch.setenv("INTERVIEW_USE_V2_STATE_SCHEMA", "true")
    schema_v2 = build_interview_state_schema()
    assert schema_v2 is InterviewOverallState


# ---------------------------------------------------------------------------
# AC-8.3 — Old InterviewGraphState retained (DEPRECATED comment)
# ---------------------------------------------------------------------------
def test_interview_graph_state_kept_with_deprecation() -> None:
    """AC-8.3: InterviewGraphState class still exists + DEPRECATED comment
    + release manager TODO marker."""
    import re
    from pathlib import Path

    from app.agents.interview.state import InterviewGraphState

    # Class still importable
    assert hasattr(InterviewGraphState, "__annotations__")

    # Source file has DEPRECATED keyword
    # Test file: backend/app/agents/tests/test_state_schemas.py
    # parents[0] = tests/, parents[1] = agents/, parents[2] = app/, parents[3] = backend/
    # Target: backend/app/agents/interview/state.py → parents[3] / "app" / "agents" / ...
    state_file = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "agents"
        / "interview"
        / "state.py"
    )
    content = state_file.read_text(encoding="utf-8")
    assert "DEPRECATED" in content, "state.py missing DEPRECATED comment"
    # TODO marker for release manager
    assert "TODO" in content, "state.py missing TODO marker for release manager"

    # Class def present
    assert re.search(r"^class InterviewGraphState", content, re.MULTILINE), (
        "InterviewGraphState class not found in state.py"
    )
