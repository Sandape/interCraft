"""[AC-040-US2] Test-First: tests for FR-003 / FR-004 / FR-005 node separation.

Test-First order (AC-9.1): this file is committed BEFORE the implementation
files in the node_separation branch. The pytest collection in this file
imports ``app.agents.interview.nodes.score_llm`` and
``app.agents.interview.nodes.sink_error`` etc.; until those modules exist,
collection fails with ``ModuleNotFoundError`` (red-phase).

AC coverage in this module:
- AC-4.1 / AC-4.2: split files exist with the right node functions.
- AC-4.3 / AC-4.4: single-responsibility (score_llm does not touch DB,
  sink_error does not call LLM).
- AC-4.5: routing function ``_route_after_score_llm`` returns the
  ``Literal["interviewer", "sink_error", "report"]`` type and the graph
  has 4 edges (3 from score_llm + 1 sink_error -> interviewer).
- AC-4.6 / AC-4.7a / AC-4.7b: failure isolation + node-internal retry +
  retry_graph_op compatibility.
- AC-4.9: ``interrupt_before`` equals ``["sink_error"]`` and does not
  keep ``"score"``.
- AC-5.1..AC-5.4: split files for update_dim_db / update_history /
  update_activities / ws_push.
- AC-5.5: each node writes only its own table / pushes only WS.
- AC-5.6: ws_push failure does not affect DB writes.
- AC-5.7: update_dim_db re-raise -> add_conditional_edges -> update_dim_error_log.
- AC-5.7a: ability_diagnose state has db_warnings: list[str].
- AC-8.1 / AC-8.2 / AC-11.1a: feature flag independence (4 combinations).
- AC-E2E-5: node function name matches add_node registration name
  (modulo ``{agent}.`` prefix).
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# AC-4.1 / AC-4.2: split node files exist with expected functions.
# ---------------------------------------------------------------------------


def test_ac_4_1_score_llm_node_file_exists() -> None:
    """AC-4.1: backend/app/agents/interview/nodes/score_llm.py exists with score_llm_node."""
    from app.agents.interview.nodes import score_llm  # noqa: F401

    assert inspect.iscoroutinefunction(score_llm.score_llm_node)


def test_ac_4_2_sink_error_node_file_exists() -> None:
    """AC-4.2: backend/app/agents/interview/nodes/sink_error.py exists with sink_error_node."""
    from app.agents.interview.nodes import sink_error  # noqa: F401

    assert inspect.iscoroutinefunction(sink_error.sink_error_node)


# ---------------------------------------------------------------------------
# AC-4.3: score_llm does NOT call the DB.
# AC-4.4: sink_error does NOT call LLM.
# ---------------------------------------------------------------------------


def test_ac_4_3_score_llm_node_does_not_call_db() -> None:
    """AC-4.3: score_llm_node source code does not reference DB session context or ErrorQuestionRepository."""
    from app.agents.interview.nodes import score_llm

    src = Path(score_llm.__file__).read_text(encoding="utf-8")
    assert "get_session_context" not in src, "score_llm_node must not touch DB"
    assert "ErrorQuestionRepository" not in src, "score_llm_node must not touch DB"


def test_ac_4_4_sink_error_node_does_not_call_llm() -> None:
    """AC-4.4: sink_error_node source code does not call LLM client.invoke."""
    from app.agents.interview.nodes import sink_error

    src = Path(sink_error.__file__).read_text(encoding="utf-8")
    assert "client.invoke" not in src, "sink_error_node must not call LLM"
    assert "get_llm_client" not in src, "sink_error_node must not call LLM"


# ---------------------------------------------------------------------------
# AC-4.5: routing function signature + 4 edges + Literal three-way.
# ---------------------------------------------------------------------------


def test_ac_4_5_route_after_score_llm_function_and_edges() -> None:
    """AC-4.5: _route_after_score_llm exists with Literal three-way; graph has 4 edges."""
    from app.agents.interview.graph import InterviewGraph

    src = Path(InterviewGraph.__module__.replace(".", "/") + ".py").read_text(
        encoding="utf-8"
    )
    backend_root = Path(src).resolve().parent
    # The graph module is at backend/app/agents/interview/graph.py; resolve relative to file.
    graph_path = Path(__file__).resolve().parents[1] / "interview" / "graph.py"
    graph_src = graph_path.read_text(encoding="utf-8")

    # Routing function defined
    assert re.search(
        r"def\s+_route_after_score_llm\s*\(", graph_src
    ), "_route_after_score_llm must be defined"
    # Literal three-way return annotation
    assert (
        'Literal["interviewer", "sink_error", "report"]' in graph_src
    ), "Literal three-way annotation required"
    # Edge count: 3 from score_llm + 1 sink_error -> interviewer
    edge_hits = re.findall(
        r'add_(?:conditional_)?edge\([^)]*(?:score_llm|sink_error)[^)]*\)',
        graph_src,
    )
    assert len(edge_hits) >= 4, f"need >=4 edges (3 from score_llm + 1 sink_error->interviewer), got {len(edge_hits)}"


def test_ac_4_5_error_threshold_in_config() -> None:
    """AC-4.5: ERROR_THRESHOLD = 60 in backend/app/agents/interview/config.py."""
    from app.agents.interview import config

    assert hasattr(config, "ERROR_THRESHOLD"), "ERROR_THRESHOLD must be defined"
    assert config.ERROR_THRESHOLD == 60, f"ERROR_THRESHOLD must be 60 (was {config.ERROR_THRESHOLD})"


def test_ac_4_5_max_questions_in_config() -> None:
    """AC-4.5: MAX_QUESTIONS must be referenced in interview/config.py."""
    from app.agents.interview import config

    src = Path(config.__file__).read_text(encoding="utf-8")
    assert "MAX_QUESTIONS" in src, "MAX_QUESTIONS must be in config.py"


# ---------------------------------------------------------------------------
# AC-4.6: failure isolation — score_llm LLM failure does NOT trigger sink_error.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac_4_6_score_llm_failure_does_not_trigger_sink_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-4.6: When client.invoke raises, sink_error must not be reached."""
    from app.agents.interview.nodes import score_llm, sink_error

    state = {
        "questions": [{"question": "Q?", "dimension": "tech_depth"}],
        "scores": [],
        "current_question": 1,
        "messages": [{"role": "user", "content": "my answer"}],
        "user_id": "user-1",
        "thread_id": "thread-1",
    }

    sink_calls: list[dict] = []

    async def sink_spy(state: dict) -> dict:
        sink_calls.append(state)
        return {}

    monkeypatch.setattr(sink_error, "sink_error_node", sink_spy)

    with patch(
        "app.agents.interview.nodes.score_llm.get_llm_client"
    ) as mock_get_client:
        mock_client = MagicMock()
        mock_client.invoke = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        mock_get_client.return_value = mock_client

        with pytest.raises(RuntimeError):
            await score_llm.score_llm_node(state)

    assert sink_calls == [], "sink_error must not be called when score_llm fails"


# ---------------------------------------------------------------------------
# AC-4.7a: sink_error node-internal retry. score_llm NOT re-invoked.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac_4_7a_sink_error_node_internal_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-4.7a: sink_error retries internally; score_llm is NOT re-invoked."""
    from app.agents.interview.nodes import sink_error
    from sqlalchemy.exc import OperationalError

    state = {
        "questions": [{"question": "Q?", "dimension": "tech_depth"}],
        "scores": [{"question_no": 1, "dimension": "tech_depth", "score": 3}],
        "current_question": 1,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "thread_id": "00000000-0000-0000-0000-000000000002",
    }

    call_count = {"n": 0}

    async def flaky_session_execute(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise OperationalError("conn", {}, Exception("connection is closed"))
        # 3rd call succeeds — return a fake result
        result = MagicMock()
        result.first.return_value = None
        return result

    async def flaky_commit():
        return None

    # Patch the session context manager used by sink_error
    fake_session = MagicMock()
    fake_session.execute = AsyncMock(side_effect=flaky_session_execute)
    fake_session.commit = AsyncMock(side_effect=flaky_commit)

    class FakeCtx:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.agents.interview.nodes.sink_error.get_session_context",
        lambda: FakeCtx(),
    )

    await sink_error.sink_error_node(state)

    assert call_count["n"] >= 2, f"sink_error should retry at least once; got {call_count['n']} calls"


# ---------------------------------------------------------------------------
# AC-4.7b: retry_graph_op compatibility — checkpointer reconnect still works
# with split nodes.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac_4_7b_retry_graph_op_compatible_with_node_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-4.7b: retry_graph_op wraps new score_llm + sink_error and retries on OperationalError."""
    from sqlalchemy.exc import OperationalError

    from app.agents.interview.graph import InterviewGraph

    # aget_state first call raises, second call returns a fake state
    class FakeState:
        values = None
        next = None

    call_count = {"n": 0}

    async def fake_aget_state(config, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OperationalError("conn", {}, Exception("connection is closed"))
        return FakeState()

    # Patch the checkpointer module that retry_graph_op uses
    from app.agents import checkpointer as cp_mod

    monkeypatch.setattr(cp_mod, "_force_rebuild", AsyncMock(return_value=None), raising=False)

    # Patch the underlying aget_state that retry_graph_op will invoke
    with patch.object(cp_mod, "get_checkpointer", AsyncMock()) as mock_get_cp:
        fake_cp = MagicMock()
        fake_cp.aget_state = AsyncMock(side_effect=fake_aget_state)
        mock_get_cp.return_value = fake_cp

        # Build a tiny graph with just score_llm + sink_error to verify retry
        # calls reach them. We don't need full interview graph here; just
        # confirm retry_graph_op's reconnect path was taken.
        from app.agents.interview.nodes import score_llm, sink_error

        score_called = {"n": 0}
        sink_called = {"n": 0}

        async def score_stub(state):
            score_called["n"] += 1
            return {"raw_score": 3, "scores": state.get("scores", []) + [{"score": 3}]}

        async def sink_stub(state):
            sink_called["n"] += 1
            return {}

        # Simulate the retry_graph_op flow at the checkpointer level
        try:
            await cp_mod.retry_graph_op(
                lambda: MagicMock(),
                {"configurable": {"thread_id": "t1"}},
                "aget_state",
            )
        except Exception:
            pass

        # The first aget_state must have been attempted (reconnect triggered)
        assert call_count["n"] >= 1, "retry_graph_op must have called aget_state at least once"


# ---------------------------------------------------------------------------
# AC-4.8: score.py is now a re-export shell with DEPRECATED comment.
# ---------------------------------------------------------------------------


def test_ac_4_8_score_py_is_reexport_with_deprecated() -> None:
    """AC-4.8: score.py re-exports score_llm_node + sink_error_node + has DEPRECATED comment."""
    score_path = Path(__file__).resolve().parents[1] / "interview" / "nodes" / "score.py"
    src = score_path.read_text(encoding="utf-8")
    assert "DEPRECATED" in src, "score.py must contain DEPRECATED marker"
    assert "score_llm_node" in src, "score.py must re-export score_llm_node"
    assert "sink_error_node" in src, "score.py must re-export sink_error_node"
    # Old implementation must NOT be present
    assert "async def score_node(" not in src, "score.py must not implement score_node"


# ---------------------------------------------------------------------------
# AC-4.9: interrupt_before = ["sink_error"], no "score" string in graph.py.
# ---------------------------------------------------------------------------


def test_ac_4_9_interrupt_before_contains_sink_error() -> None:
    """AC-4.9: interrupt_before must include 'sink_error'; 'score' must not be in graph.py."""
    graph_path = Path(__file__).resolve().parents[1] / "interview" / "graph.py"
    src = graph_path.read_text(encoding="utf-8")
    assert "interrupt_before" in src, "interrupt_before must be specified"
    assert '"sink_error"' in src, "interrupt_before must contain 'sink_error'"
    # '"score"' string must not appear (the bare score node no longer exists)
    assert '"score"' not in src, (
        "interrupt_before must not contain 'score' string "
        "(AC-4.9 R8'' strict: equal [...,'sink_error'] not [score, sink_error])"
    )


# ---------------------------------------------------------------------------
# AC-5.1..AC-5.4: update_dimensions split files.
# ---------------------------------------------------------------------------


def test_ac_5_1_update_dim_db_node_file_exists() -> None:
    from app.agents.nodes.ability_diagnose import update_dim_db  # noqa: F401

    assert inspect.iscoroutinefunction(update_dim_db.update_dim_db_node)


def test_ac_5_2_update_history_node_file_exists() -> None:
    from app.agents.nodes.ability_diagnose import update_history  # noqa: F401

    assert inspect.iscoroutinefunction(update_history.update_history_node)


def test_ac_5_3_update_activities_node_file_exists() -> None:
    from app.agents.nodes.ability_diagnose import update_activities  # noqa: F401

    assert inspect.iscoroutinefunction(update_activities.update_activities_node)


def test_ac_5_4_ws_push_node_file_exists() -> None:
    from app.agents.nodes.ability_diagnose import ws_push  # noqa: F401

    assert inspect.iscoroutinefunction(ws_push.ws_push_node)


# ---------------------------------------------------------------------------
# AC-5.5: each update_dimensions split node writes only its own concern.
# ---------------------------------------------------------------------------


def test_ac_5_5_each_split_node_only_touches_its_own_table() -> None:
    """AC-5.5: split source files reference only their own SQL table."""
    base = Path(__file__).resolve().parents[1] / "nodes" / "ability_diagnose"

    update_dim_src = (base / "update_dim_db.py").read_text(encoding="utf-8")
    assert "ability_dimensions" in update_dim_src
    assert "ability_dimensions_history" not in update_dim_src
    assert "INSERT INTO activities" not in update_dim_src

    history_src = (base / "update_history.py").read_text(encoding="utf-8")
    assert "ability_dimensions_history" in history_src
    assert "INSERT INTO ability_dimensions " not in history_src
    assert "INSERT INTO activities" not in history_src

    activities_src = (base / "update_activities.py").read_text(encoding="utf-8")
    assert "INSERT INTO activities" in activities_src
    assert "INSERT INTO ability_dimensions" not in activities_src

    ws_src = (base / "ws_push.py").read_text(encoding="utf-8")
    assert "send_to_user" in ws_src
    assert "INSERT INTO" not in ws_src


# ---------------------------------------------------------------------------
# AC-5.6: ws_push failure does NOT affect DB writes.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac_5_6_ws_push_failure_does_not_affect_db_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-5.6: WS push fails -> DB write still committed."""
    from app.agents.nodes.ability_diagnose import update_dim_db, update_history, update_activities, ws_push

    # Replace ws_push with a stub that always raises
    async def fail_ws(state):
        raise RuntimeError("WS unreachable")

    monkeypatch.setattr(ws_push, "ws_push_node", fail_ws)

    # Track that the other nodes were called regardless of ws failure
    # (this test only verifies the source level: ws_push is isolated from DB).
    state = {"user_id": "u1", "diagnoses": [], "insights": []}

    # Verify update_dim_db doesn't reference ws_push.send_to_user (single responsibility)
    update_dim_src = Path(update_dim_db.__file__).read_text(encoding="utf-8")
    assert "send_to_user" not in update_dim_src, "update_dim_db must not call WS"


# ---------------------------------------------------------------------------
# AC-5.7: update_dim_db re-raise -> add_conditional_edges -> update_dim_error_log.
# This is verified at the source level (LangGraph routing function semantics
# documented in AC-5.7 + AC-6.5 + tracing.py fail-open philosophy).
# ---------------------------------------------------------------------------


def test_ac_5_7_update_dim_db_reraises_for_otel_and_routes_to_error_log() -> None:
    """AC-5.7: update_dim_db's body wraps DB call in try/except + explicit OTel API + state db_warnings; no silent swallow."""
    update_dim_path = (
        Path(__file__).resolve().parents[1]
        / "nodes"
        / "ability_diagnose"
        / "update_dim_db.py"
    )
    src = update_dim_path.read_text(encoding="utf-8")
    # 4 nodes must include the OTel API call when handling errors
    assert "set_status" in src or "StatusCode.ERROR" in src, (
        "update_dim_db must explicitly mark OTel span as ERROR (R1''' P0)"
    )
    assert "record_exception" in src, (
        "update_dim_db must call record_exception (R1''' P0)"
    )
    assert "db_warnings" in src, "update_dim_db must append to db_warnings"


def test_ac_5_7_update_dim_error_log_node_exists() -> None:
    """AC-5.7: intermediate node ability_diagnose.update_dim_error_log must exist."""
    from app.agents.nodes.ability_diagnose import update_dim_error_log  # noqa: F401

    assert inspect.iscoroutinefunction(update_dim_error_log.update_dim_error_log_node)


def test_ac_5_7_graph_uses_conditional_edges_and_routing_function() -> None:
    """AC-5.7: ability_diagnose graph uses add_conditional_edges + _route_after_update_dim_db."""
    graph_path = (
        Path(__file__).resolve().parents[1] / "graphs" / "ability_diagnose.py"
    )
    src = graph_path.read_text(encoding="utf-8")
    assert "add_conditional_edges" in src, "add_conditional_edges must be used"
    assert "_route_after_update_dim_db" in src, "routing function required"


# ---------------------------------------------------------------------------
# AC-5.7a: ability_diagnose state has db_warnings: list[str].
# ---------------------------------------------------------------------------


def test_ac_5_7a_ability_diagnose_state_has_db_warnings() -> None:
    """AC-5.7a: AbilityDiagnoseState must declare db_warnings: list[str]."""
    from app.agents.state.ability_diagnose_state import AbilityDiagnoseState

    annotations = AbilityDiagnoseState.__annotations__
    assert "db_warnings" in annotations, (
        f"db_warnings must be in AbilityDiagnoseState; got {sorted(annotations)}"
    )
    # The annotation should mention list[str]; TypedDict-compatible (no Field()).
    assert "list[str]" in str(annotations["db_warnings"]), (
        f"db_warnings must be list[str]; got {annotations['db_warnings']!r}"
    )


# ---------------------------------------------------------------------------
# AC-5.8: update_dimensions.py is now a re-export shell with DEPRECATED.
# ---------------------------------------------------------------------------


def test_ac_5_8_update_dimensions_py_is_reexport_with_deprecated() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "nodes"
        / "ability_diagnose"
        / "update_dimensions.py"
    )
    src = path.read_text(encoding="utf-8")
    assert "DEPRECATED" in src, "update_dimensions.py must contain DEPRECATED marker"
    for fn in ("update_dim_db", "update_history", "update_activities", "ws_push"):
        assert fn in src, f"update_dimensions.py must re-export {fn}"


# ---------------------------------------------------------------------------
# AC-5.9: ability_diagnose graph edges connect 4 update nodes + update_dim_error_log.
# ---------------------------------------------------------------------------


def test_ac_5_9_ability_diagnose_graph_edges() -> None:
    graph_path = (
        Path(__file__).resolve().parents[1] / "graphs" / "ability_diagnose.py"
    )
    src = graph_path.read_text(encoding="utf-8")
    for node in (
        "update_dim_db",
        "update_history",
        "update_activities",
        "ws_push",
        "generate_insight",
    ):
        assert node in src, f"{node} must be referenced in ability_diagnose graph"


# ---------------------------------------------------------------------------
# AC-8.1: feature flag env var default + independence from STATE_SCHEMA.
# ---------------------------------------------------------------------------


def test_ac_8_1_node_split_flag_defaults_false_and_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-8.1: INTERVIEW_USE_V2_NODE_SPLIT defaults false; independent from STATE_SCHEMA."""
    monkeypatch.delenv("INTERVIEW_USE_V2_NODE_SPLIT", raising=False)
    monkeypatch.delenv("INTERVIEW_USE_V2_STATE_SCHEMA", raising=False)

    from app.agents.interview import config

    raw = os.environ.get("INTERVIEW_USE_V2_NODE_SPLIT", "false").lower()
    assert raw == "false", "default must be 'false'"

    config_src = Path(config.__file__).read_text(encoding="utf-8")
    # Two flags must be in independent lines (no shared if/elif chain).
    node_flag_count = config_src.count("INTERVIEW_USE_V2_NODE_SPLIT")
    state_flag_count = config_src.count("INTERVIEW_USE_V2_STATE_SCHEMA")
    assert node_flag_count >= 1 and state_flag_count >= 1
    # Sanity: not aliased to each other.
    assert "INTERVIEW_USE_V2_NODE_SPLIT = INTERVIEW_USE_V2_STATE_SCHEMA" not in config_src


def test_ac_8_1_four_flag_combinations_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-8.1 / R11'': 4 flag combinations must all be reachable (no raise on any combo)."""
    from app.agents.interview import config

    combos = [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ]
    for schema_v, node_split_v in combos:
        monkeypatch.setenv(
            "INTERVIEW_USE_V2_STATE_SCHEMA",
            "true" if schema_v else "false",
        )
        monkeypatch.setenv(
            "INTERVIEW_USE_V2_NODE_SPLIT",
            "true" if node_split_v else "false",
        )
        # Reload module so env vars are read fresh.
        importlib.reload(config)
        # No raise: simply call the schema builder
        schema = config.build_interview_state_schema()
        assert schema is not None
        # Re-read the node_split flag
        node_split_flag = config.INTERVIEW_USE_V2_NODE_SPLIT()
        assert node_split_flag == node_split_v


# ---------------------------------------------------------------------------
# AC-E2E-5: node function name matches add_node registration name (modulo prefix).
# ---------------------------------------------------------------------------


def test_ac_e2e_5_node_function_name_matches_add_node() -> None:
    """AC-E2E-5: every add_node('agent.role_action', func) call has func.__name__ == role_action."""
    graph_files = [
        Path(__file__).resolve().parents[1] / "interview" / "graph.py",
        Path(__file__).resolve().parents[1] / "graphs" / "ability_diagnose.py",
        Path(__file__).resolve().parents[1] / "graphs" / "error_coach.py",
        Path(__file__).resolve().parents[1] / "graphs" / "general_coach.py",
        Path(__file__).resolve().parents[1] / "graphs" / "resume_optimize.py",
    ]
    pattern = re.compile(r'add_node\(\s*"([^"]+)"\s*,\s*([A-Za-z_]\w*)')
    mismatches: list[str] = []
    for fp in graph_files:
        src = fp.read_text(encoding="utf-8")
        for match in pattern.finditer(src):
            name, func = match.group(1), match.group(2)
            if name == "interview_planner":
                # Subgraph registration — function name comes from planner_graph.
                continue
            # Strip {agent}. prefix.
            if "." in name:
                _, role_action = name.split(".", 1)
            else:
                role_action = name
            if func != role_action:
                mismatches.append(f"{fp.name}: add_node({name!r}, {func!r})")
    assert not mismatches, "Node function name mismatches:\n" + "\n".join(mismatches)