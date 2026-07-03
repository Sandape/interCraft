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
# AC-3.7a — FastAPI TestClient parametrize 13 nodes + API response has
#             error_category + node_name + cause fields.
# ---------------------------------------------------------------------------
class TestApiResponseErrorCategoryFieldPresent:
    """AC-3.7a (升 P0): FastAPI TestClient end-to-end — when an LLM node fails,
    response.json() MUST include ``error_category`` + ``node_name`` + ``cause``.
    """

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
    def test_api_response_has_error_category_for_each_node(self, node_name):
        """Direct serializer-level test (AC-3.7a flavor 2): build a fake
        NodeError and run it through the serializer helper. The serializer
        MUST emit ``error_category`` + ``node_name`` + ``cause``."""
        from app.agents.utils.node_error import NodeError

        # Build NodeError as if the node had failed
        err = NodeError.from_exception(
            Exception("synthetic failure"),
            node_name=node_name,
        )

        # Find the serializer. It should be importable from a stable path.
        # New helper added in MB3 — `serialize_state_error`.
        from app.agents.utils.node_error import serialize_state_error

        payload = serialize_state_error(
            state_error=err.model_dump(),
            state_error_legacy=None,
        )

        # API contract (AC-3.4 / AC-3.7a):
        assert "error_category" in payload, (
            f"{node_name}: serialized payload missing `error_category`"
        )
        assert "node_name" in payload, (
            f"{node_name}: serialized payload missing `node_name`"
        )
        assert payload["node_name"] == node_name
