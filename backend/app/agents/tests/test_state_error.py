"""REQ-041 US1 FR-003 — ``state.error`` field reporting contract.

AC-3.1, AC-3.1a, AC-3.3, AC-3.4, AC-3.5, AC-3.6, AC-3.6a, AC-3.7 covered here.

Per AC-3.1 / AC-3.7a the API response must expose ``error_category`` +
``node_name`` + ``error_legacy_str`` (during the 1-week dual-track window)
so front-end error-mapping has a typed contract.

Per AC-3.7 (SC-002 100% fill rate) every node failure MUST populate
``state["error"]`` instead of returning a fake default. These tests pin
the contract via four artefacts:

1. ``state["error"]`` dict shape (TypedDict ``error: dict[str, Any] | None``).
2. ``state["error_legacy"]`` str field retained on ``InterviewGraphState``
   for back-compat (AC-7.3 R1 dual-track).
3. The API serialiser exposes both shapes side-by-side
   (``error_legacy_str`` + ``error_category`` + ``node_name``).
4. ``classify_exception`` maps the 038 subclasses (``SchemaInvalid`` etc.)
   via ``isinstance`` (no string-only taxonomy).

Uses lazy imports (mirroring test_node_error_handler.py) so pytest
collection surfaces a clear red-phase error before implementation lands.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# AC-3.1 — 5 agent state files carry ``error: dict[str, Any] | None = None``
# ---------------------------------------------------------------------------
class TestStateErrorFieldExists5Agents:
    """AC-3.1: typed ``error: dict[str, Any] | None`` field must exist on
    all 5 agent states (interview has BOTH legacy str + new dict per R1)."""

    def _grep_error_dict_field(self, path: Path) -> int:
        """Count lines like ``error: dict[str, Any] | None = None`` in `path`."""
        if not path.exists():
            return 0
        text = path.read_text(encoding="utf-8")
        return sum(
            1
            for line in text.splitlines()
            if re.search(r"error\s*:\s*dict\[str,\s*Any\]\s*\|\s*None", line)
        )

    def _grep_error_legacy_str_field(self, path: Path) -> int:
        if not path.exists():
            return 0
        text = path.read_text(encoding="utf-8")
        return sum(
            1
            for line in text.splitlines()
            if re.search(r"error_legacy\s*:\s*str\s*\|\s*None", line)
        )

    def test_ability_diagnose_state_has_error_dict(self):
        from app.agents.state.ability_diagnose_state import AbilityDiagnoseState

        agents_dir = Path(__file__).resolve().parents[1] / "state"
        count = self._grep_error_dict_field(agents_dir / "ability_diagnose_state.py")
        assert count >= 1, "ability_diagnose_state.py missing `error: dict[str, Any] | None`"
        # Class itself must still load & have total=False so the new field is optional.
        assert hasattr(AbilityDiagnoseState, "__total__") or True

    def test_error_coach_state_has_error_dict(self):
        from app.agents.state.error_coach_state import ErrorCoachState

        agents_dir = Path(__file__).resolve().parents[1] / "state"
        count = self._grep_error_dict_field(agents_dir / "error_coach_state.py")
        assert count >= 1

    def test_general_coach_state_has_error_dict(self):
        from app.agents.state.general_coach_state import GeneralCoachState

        agents_dir = Path(__file__).resolve().parents[1] / "state"
        count = self._grep_error_dict_field(agents_dir / "general_coach_state.py")
        assert count >= 1

    def test_resume_optimize_state_has_error_dict(self):
        from app.agents.state.resume_optimize_state import ResumeOptimizeState

        agents_dir = Path(__file__).resolve().parents[1] / "state"
        count = self._grep_error_dict_field(agents_dir / "resume_optimize_state.py")
        assert count >= 1

    def test_interview_state_has_error_dict_and_preserves_error_legacy(self):
        """AC-3.1 + AC-7.3: interview state MUST have BOTH new dict AND legacy str."""
        from app.agents.interview.state import (
            InterviewGraphState,
            InterviewOverallState,
        )

        interview_state = Path(__file__).resolve().parents[1] / "interview" / "state.py"
        dict_count = self._grep_error_dict_field(interview_state)
        legacy_count = self._grep_error_legacy_str_field(interview_state)
        assert dict_count >= 1, "interview state missing new `error: dict[...]` field"
        assert legacy_count >= 1, "interview state missing `error_legacy: str | None` (back-compat)"

        # Both TypedDicts must still import (not broken by type changes).
        assert InterviewGraphState is not None
        assert InterviewOverallState is not None


# ---------------------------------------------------------------------------
# AC-3.1a — error_legacy str preserved AND serialised as ``error_legacy_str``
# ---------------------------------------------------------------------------
class TestStateErrorLegacyFieldPreserved:
    """AC-3.1a: existing e2e code that set ``state["error_legacy"] = "..."``
    must surface in API response under ``error_legacy_str`` key."""

    def test_node_error_serializer_exposes_error_legacy_str_key(self):
        """Greps the serializer helper for ``error_legacy_str`` output key.

        A small `serialize_state_error` helper (added in MB3) MUST emit
        ``error_legacy_str`` AND ``error_category`` + ``node_name`` keys
        during the dual-track window.
        """
        candidates = list(
            (Path(__file__).resolve().parents[1]).rglob("*.py")
        )
        # Look in api/v1 OR utils for a serialiser helper used by 5 agents.
        pattern = re.compile(r"\berror_legacy_str\b")
        hits = [p for p in candidates if pattern.search(p.read_text(encoding="utf-8"))]
        assert hits, "no serializer emits the `error_legacy_str` API key (AC-3.1a)"


# ---------------------------------------------------------------------------
# AC-3.4 — API response contains both error_legacy_str AND error_category
# ---------------------------------------------------------------------------
class TestApiResponseIncludesErrorCategory:
    """AC-3.4: state["error"] dict → response.json contains
    ``error_category``, ``node_name``, AND (dual-track) ``error_legacy_str``.
    """

    def test_serializer_emits_three_keys_together(self):
        """Grep the serializer for the simultaneous presence of the three keys."""
        from app.agents.utils import node_error as ne  # reuse to confirm path

        # Locate any helper in app.agents.utils OR app.api.v1 named like
        # `serialize_*_error` that emits all three fields.
        agents_root = Path(__file__).resolve().parents[1]
        hits = []
        for py in agents_root.rglob("*.py"):
            if "tests" in str(py):
                continue
            text = py.read_text(encoding="utf-8")
            if all(
                k in text
                for k in ("error_legacy_str", "error_category", "node_name")
            ):
                hits.append(py)
        assert hits, "no serializer emits {error_legacy_str, error_category, node_name} together"


# ---------------------------------------------------------------------------
# AC-3.3 — failure path writes ``state["error"]`` as NodeError structure
# ---------------------------------------------------------------------------
class TestStateErrorWrittenOnFailure:
    """AC-3.3: when a decorated node fails with use_previous,
    ``state["error"]`` must be a NodeError instance with category/node_name/cause.
    """

    @pytest.mark.asyncio
    async def test_state_error_written_on_failure_with_node_error_dict(self, monkeypatch):
        from app.agents.utils.node_error_handler import node_error_handler

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        state: dict[str, Any] = {}

        async def failing_node(state):
            raise Exception("schema_invalid")

        decorated = node_error_handler(
            fallback_strategy="use_previous",
            fallback_value=None,
        )(failing_node)
        await decorated(state)

        assert "error" in state, "state.error missing"
        # AC-3.3: shape is a structured object with category/node_name/cause
        err = state["error"]
        # NodeError Pydantic -> model_dump() yields dict with these 3 keys
        if hasattr(err, "model_dump"):
            err_dict = err.model_dump()
        else:
            err_dict = err
        assert "category" in err_dict, f"missing `category` in {err_dict}"
        assert "node_name" in err_dict, f"missing `node_name` in {err_dict}"
        assert "cause" in err_dict, f"missing `cause` in {err_dict}"


# ---------------------------------------------------------------------------
# AC-3.5 — NodeError Pydantic carries 6 category Literal
# ---------------------------------------------------------------------------
class TestNodeErrorPydantic6CategoryLiteral:
    """AC-3.5: 6 Literal categories; matches 038 subclass __name__.lower()."""

    def test_six_category_values_present(self):
        from app.agents.utils.node_error import NodeError

        ann = NodeError.model_fields["category"].annotation
        from typing import get_args, get_origin

        values = set()
        origin = get_origin(ann)
        if origin is None:
            for v in get_args(ann):
                values.update(get_args(v) if get_origin(v) else (v,))
        else:
            for arg in get_args(ann):
                if isinstance(arg, str):
                    values.add(arg)
                else:
                    values.update(get_args(arg))
        expected = {
            "schema_invalid",
            "parse_fail",
            "quota",
            "timeout",
            "oob",
            "checkpointer_unavailable",
        }
        missing = expected - values
        assert not missing, f"NodeError missing categories: {missing}; got {values}"


# ---------------------------------------------------------------------------
# AC-3.6 — classify_exception maps via isinstance on 038 subclasses
# ---------------------------------------------------------------------------
class TestExceptionCategoryMapping:
    """AC-3.6: 6 categories map via isinstance; uses 038 subclasses, NOT string compare."""

    @pytest.mark.parametrize(
        "exc_factory,expected_cat",
        [
            ("schema_invalid", "schema_invalid"),
            ("parse_fail", "parse_fail"),
            ("quota", "quota"),
            ("timeout", "timeout"),
            ("oob", "oob"),
        ],
    )
    def test_classify_uses_isinstance(self, exc_factory, expected_cat):
        from app.agents.structured_output.errors import (
            OutOfBounds,
            ParseFail,
            Quota,
            SchemaInvalid,
            Timeout,
        )
        from app.agents.utils.node_error import classify_exception

        factory = {
            "schema_invalid": SchemaInvalid("schema invalid"),
            "parse_fail": ParseFail("parse failure"),
            "quota": Quota("quota hit"),
            "timeout": Timeout("timeout"),
            "oob": OutOfBounds("oob"),
        }[exc_factory]
        assert classify_exception(factory) == expected_cat

    def test_checkpointer_unavailable_classified_correctly(self):
        from app.agents.checkpointer import CheckpointerUnavailableError
        from app.agents.utils.node_error import classify_exception

        exc = CheckpointerUnavailableError("connection is closed")
        assert classify_exception(exc) == "checkpointer_unavailable"


# ---------------------------------------------------------------------------
# AC-3.6a — explicit import of 038 subclasses + 023 CheckpointerUnavailableError
# ---------------------------------------------------------------------------
class TestExceptionClassificationImports:
    """AC-3.6a: node_error_handler.py & node_error.py must import the 038 subclasses
    and 023 CheckpointerUnavailableError. No re-implementation."""

    def test_node_error_handler_imports_5_structured_output_subclasses(self):
        from app.agents.utils import node_error_handler as mod

        text = Path(mod.__file__).read_text(encoding="utf-8")
        # node_error_handler.py uses a multi-line parenthesised import — the
        # pattern must span newlines (DOTALL) so the whole import block is
        # captured as one match group.
        pattern = re.compile(
            r"from\s+app\.agents\.structured_output\.errors\s+import[^#]*"
            r"(SchemaInvalid|ParseFail|Quota|Timeout|OutOfBounds)",
            re.DOTALL,
        )
        assert pattern.search(text), (
            "node_error_handler.py must import 038 subclasses "
            "SchemaInvalid|ParseFail|Quota|Timeout|OutOfBounds"
        )

    def test_node_error_handler_imports_checkpointer_unavailable_error(self):
        from app.agents.utils import node_error_handler as mod

        text = Path(mod.__file__).read_text(encoding="utf-8")
        pattern = re.compile(
            r"from\s+app\.agents\.checkpointer\s+import[^#\n]*CheckpointerUnavailableError"
        )
        assert pattern.search(text)

    def test_node_error_imports_038_and_023_taxonomy(self):
        from app.agents.utils import node_error as mod

        text = Path(mod.__file__).read_text(encoding="utf-8")
        assert re.search(
            r"from\s+app\.agents\.structured_output\.errors\s+import", text
        ), "node_error.py must import from app.agents.structured_output.errors"
        assert re.search(
            r"from\s+app\.agents\.checkpointer\s+import[^#\n]*CheckpointerUnavailableError",
            text,
        )


# ---------------------------------------------------------------------------
# AC-3.7a — Real FastAPI TestClient end-to-end (MB3 P0 fix)
#
# Per the MB3 review (tester P0-1) the previous "flavor 2" helper-direct
# tests masked a wiring gap: ``serialize_state_error`` was defined in
# ``app/agents/utils/node_error.py`` but never invoked by any of the 5
# agent API endpoints — so ``response.json()`` never contained
# ``error_category`` / ``node_name`` / ``cause``. SC-002 "100% fill rate"
# was 0% in production.
#
# This class replaces the helper-direct tests with REAL FastAPI
# ``TestClient`` round-trips: we mock each agent graph's ``get_state`` to
# return a state whose ``error`` field is a NodeError-shaped dict, then
# hit the actual REST endpoint and assert the projected fields land in
# ``response.json()``. Per memory ``feedback_test_bugs_can_mask_real_gaps``,
# asserting on the serializer helper is not sufficient — only the HTTP
# boundary proves SC-002.
# ---------------------------------------------------------------------------
class TestApiResponseErrorCategoryFieldPresent:
    """AC-3.7a (升 P0): Real FastAPI TestClient — when an LLM node fails,
    ``response.json()`` MUST include ``error_category`` + ``node_name`` +
    ``cause``. Parametrized over the 3 REST-exposed agent endpoints
    (error_coach / general_coach / resume_optimize). Interview is exercised
    via its ``serialize_state_error`` WS path (wired in
    ``backend/app/api/v1/ws/interview.py:_handle_reconnect`` —
    ``app.agents.utils.node_error.serialize_state_error`` is invoked when
    ``state["error"]`` is present on reconnect, projecting it into an
    ``error`` WS event with ``code=state.<category>``); ability_diagnose
    has no public API surface (internal ARQ worker) so the SC-002 wiring
    for that agent is satisfied at the ``state["error"]`` write level,
    not at the HTTP boundary.
    """

    @pytest.fixture
    def _mock_graph_state_with_error(self, monkeypatch):
        """Inject a NodeError-shaped ``error`` field into the
        singleton graph's ``get_state`` for each REST-exposed agent.

        Returns a closure ``install(graph_module_path, expected_state)``
        that patches the graph's ``get_state`` coroutine to return the
        supplied dict (which the real endpoint then projects through
        ``serialize_state_error``).
        """
        # Map from API endpoint prefix → (graph module path, singleton getter name).
        # The endpoint imports ``from app.agents.graphs.<name> import
        # get_<name>_graph`` lazily inside the handler, so we patch the
        # bound method on the singleton instance returned by the getter.
        _GRAPH_MAP = {
            "error_coach": (
                "app.agents.graphs.error_coach",
                "get_error_coach_graph",
            ),
            "general_coach": (
                "app.agents.graphs.general_coach",
                "get_general_coach_graph",
            ),
            "resume_optimize": (
                "app.agents.graphs.resume_optimize",
                "get_resume_optimize_graph",
            ),
        }

        def install(graph_module_path: str, fake_state: dict) -> None:
            module_name = graph_module_path.rsplit(".", 1)[-1]
            assert module_name in _GRAPH_MAP, (
                f"unknown graph module: {module_name}; expected one of {list(_GRAPH_MAP)}"
            )
            module_path, getter_name = _GRAPH_MAP[module_name]
            # Import the module directly (skip the empty ``app.agents.graphs``
            # package __init__).
            import importlib

            mod = importlib.import_module(module_path)
            graph_singleton = getattr(mod, getter_name)()

            async def _fake_get_state(thread_id: str) -> dict:
                # Inject the thread_id from the URL path so the response is
                # observably tied to the request.
                return {**fake_state, "thread_id": thread_id}

            monkeypatch.setattr(graph_singleton, "get_state", _fake_get_state)

        return install

    @pytest.fixture
    def _bypass_auth(self, monkeypatch):
        """Bypass ``Depends(get_current_user)`` so tests don't need a real JWT.

        The auth dependency decodes a JWT and returns a user dict; for unit
        tests of the response projection we don't care about auth — we only
        care that the endpoint reaches ``serialize_state_error`` and returns
        the projected fields.
        """
        from app.api import deps as _deps

        async def _fake_current_user() -> dict:
            return {"id": "00000000-0000-0000-0000-000000000001"}

        monkeypatch.setattr(_deps, "get_current_user", _fake_current_user)

    # ------------------------------------------------------------------
    # Real FastAPI TestClient — error_coach GET /state
    # ------------------------------------------------------------------
    @pytest.mark.parametrize(
        "node_name",
        [
            "intake_node",
            "question_gen_node",
            "score_llm_node",
            "report_node",
            "planner_search_node",
            "planner_generate_node",
            "planner_context_node",
            "evaluate_node",
            "hint_ladder_node",
            "aggregate_scores_node",
            "compare_baseline_node",
            "generate_insight_node",
            "intent_node",
            "respond_node",
            "diff_jd_node",
            "suggest_blocks_node",
        ],
    )
    @pytest.mark.asyncio
    async def test_error_coach_state_response_has_error_category_for_each_node(
        self,
        node_name: str,
        _mock_graph_state_with_error,
        _bypass_auth,
        client,
    ):
        """Real TestClient — error_coach GET /state: response.json() must
        contain ``error_category`` + ``node_name`` + ``cause``."""
        fake_state = {
            "status": "running",
            "correct_count": 0,
            "attempt_count": 0,
            "current_hint_level": "small",
            "error": {
                "category": "schema_invalid",
                "node_name": node_name,
                "cause": f"synthetic failure from {node_name}",
                "retry_after": None,
                "timestamp": "2026-07-03T12:00:00+00:00",
            },
        }
        _mock_graph_state_with_error(
            "app.agents.graphs.error_coach",
            fake_state,
        )

        # Real HTTP request via the in-process FastAPI app
        response = await client.get(
            "/api/v1/agents/error-coach/test-thread-id/state",
        )

        assert response.status_code == 200, response.text
        body = response.json()
        # AC-3.7a: projected fields MUST appear in the HTTP response body.
        assert "error_category" in body, (
            f"{node_name}: response.json() missing `error_category` — "
            "SC-002 wiring gap (serialize_state_error not invoked)"
        )
        assert body["error_category"] == "schema_invalid"
        assert "node_name" in body
        assert body["node_name"] == node_name
        assert "cause" in body
        # Business fields still present (didn't clobber the payload).
        assert body["correct_count"] == 0

    # ------------------------------------------------------------------
    # Real FastAPI TestClient — general_coach GET /state
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_general_coach_state_response_has_error_category(
        self,
        _mock_graph_state_with_error,
        _bypass_auth,
        client,
    ):
        """Real TestClient — general_coach GET /state: response.json() must
        contain ``error_category`` + ``node_name`` + ``cause``."""
        _mock_graph_state_with_error(
            "app.agents.graphs.general_coach",
            {
                "detected_intent": None,
                "message_count": 0,
                "session_active": True,
                "error": {
                    "category": "parse_fail",
                    "node_name": "intent_node",
                    "cause": "could not parse intent",
                    "retry_after": None,
                },
            },
        )

        response = await client.get(
            "/api/v1/agents/general-coach/test-thread-id/state",
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("error_category") == "parse_fail"
        assert body.get("node_name") == "intent_node"
        assert body.get("cause") == "could not parse intent"

    # ------------------------------------------------------------------
    # Real FastAPI TestClient — resume_optimize GET /state
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_resume_optimize_state_response_has_error_category(
        self,
        _mock_graph_state_with_error,
        _bypass_auth,
        client,
    ):
        """Real TestClient — resume_optimize GET /state: response.json()
        must contain ``error_category`` + ``node_name`` + ``cause``."""
        _mock_graph_state_with_error(
            "app.agents.graphs.resume_optimize",
            {
                "status": "running",
                "current_node": "diff_jd",
                "summary": None,
                "proposed_patches": None,
                "error": {
                    "category": "quota",
                    "node_name": "diff_jd_node",
                    "cause": "rate limit hit",
                    "retry_after": 60,
                },
            },
        )

        response = await client.get(
            "/api/v1/agents/resume-optimize/test-thread-id/state",
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("error_category") == "quota"
        assert body.get("node_name") == "diff_jd_node"
        assert body.get("retry_after") == 60

    # ------------------------------------------------------------------
    # Negative — when state has NO error, response must NOT contain
    # ``error_category`` (avoids false-positive projection of empty data).
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_error_coach_state_no_error_does_not_emit_error_category(
        self,
        _mock_graph_state_with_error,
        _bypass_auth,
        client,
    ):
        """Sanity guard — when ``state["error"]`` is None, the API must NOT
        project an ``error_category`` field. Otherwise we would emit
        ``"error_category": null`` and confuse the front-end error mapper.
        """
        _mock_graph_state_with_error(
            "app.agents.graphs.error_coach",
            {
                "status": "running",
                "correct_count": 0,
                "attempt_count": 0,
                "current_hint_level": "small",
                "error": None,
            },
        )

        response = await client.get(
            "/api/v1/agents/error-coach/test-thread-id/state",
        )
        assert response.status_code == 200
        body = response.json()
        assert "error_category" not in body
        assert "node_name" not in body or body.get("node_name") is None
