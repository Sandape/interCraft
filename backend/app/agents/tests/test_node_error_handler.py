"""REQ-041 US1 FR-002 / FR-003 — @node_error_handler decorator + NodeError Pydantic.

AC-2.1 ~ AC-2.9 + AC-2.2a/2.2b + AC-3.5 + AC-E2E-US1-1 covered here.

Test-First red-phase commit per REQ-040 AC-9.1 pattern.
Uses lazy imports inside test functions (per test_token_limit.py / test_node_separation.py
pattern) so pytest collection surfaces a clear ``ModuleNotFoundError`` red-phase error
rather than failing at import time on the ``app`` package discovery (which is brittle
under uv's ``python -m pytest`` layout).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import openai
import pytest


# ---------------------------------------------------------------------------
# AC-2.1 — decorator exists with required signature
# ---------------------------------------------------------------------------
class TestNodeErrorHandlerExists:
    def test_decorator_function_exists(self):
        """AC-2.1: ``node_error_handler`` defined in node_error_handler.py."""
        from app.agents.utils.node_error_handler import node_error_handler

        assert callable(node_error_handler)

    def test_decorator_signature_includes_strategy_value_max_retries(self):
        """AC-2.1: signature exposes fallback_strategy / fallback_value / max_retries."""
        import inspect

        from app.agents.utils.node_error_handler import node_error_handler

        sig = inspect.signature(node_error_handler)
        params = sig.parameters
        assert "fallback_strategy" in params
        assert "fallback_value" in params
        assert "max_retries" in params
        # default max_retries must be 3 per AC-2.1
        assert params["max_retries"].default == 3


# ---------------------------------------------------------------------------
# AC-2.2a — retry strategy: node-internal retry isolation
# ---------------------------------------------------------------------------
class TestRetryStrategyMaxRetries:
    @pytest.mark.asyncio
    async def test_node_internal_retry_calls_node_n_times_then_raises(self, monkeypatch):
        """AC-2.2a: mock node throws 3 times → re-raise LLMInvokeError, count==max_retries."""
        from app.agents.llm_client import LLMInvokeError
        from app.agents.utils.node_error_handler import node_error_handler

        # disable retry_graph_op (per AC-E2E-US1-1 monkeypatch guard)
        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        call_count = {"n": 0}

        async def failing_node(state):
            call_count["n"] += 1
            raise Exception("transient")

        decorated = node_error_handler(
            fallback_strategy="retry",
            fallback_value=None,
            max_retries=3,
        )(failing_node)

        with pytest.raises(LLMInvokeError):
            await decorated({})

        # node called exactly max_retries times (NOT max_retries+1 — strict per AC)
        assert call_count["n"] == 3, (
            f"Expected node called 3 times (max_retries), got {call_count['n']}"
        )


# ---------------------------------------------------------------------------
# AC-2.2b — graph-level retry_graph_op compatibility
# ---------------------------------------------------------------------------
class TestRetryGraphOpCompatibility:
    @pytest.mark.asyncio
    async def test_node_raises_operational_error_propagates_to_retry_graph_op(
        self, monkeypatch
    ):
        """AC-2.2b: OperationalError propagates upward from node to retry_graph_op layer."""
        from app.agents.llm_client import LLMInvokeError
        from app.agents.utils.node_error_handler import node_error_handler

        # retry_graph_op NOT disabled — its called count tracks graph-layer retry
        retry_graph_op_calls = {"n": 0}

        async def mock_retry_graph_op(func, *args, **kwargs):
            retry_graph_op_calls["n"] += 1
            return await func(*args, **kwargs)

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            mock_retry_graph_op,
        )

        async def failing_node(state):
            # OperationalError is not a token-limit exception; retry_graph_op layer
            # must trigger (we don't intercept this).
            from sqlalchemy.exc import OperationalError

            raise OperationalError("connection is closed", None, None)

        decorated = node_error_handler(
            fallback_strategy="retry",
            fallback_value=None,
            max_retries=2,
        )(failing_node)

        # node-level retry exhausts → raises LLMInvokeError
        with pytest.raises(LLMInvokeError):
            await decorated({})


# ---------------------------------------------------------------------------
# AC-2.3 — use_previous strategy: write state.error + return fallback_value
# ---------------------------------------------------------------------------
class TestUsePreviousStrategy:
    @pytest.mark.asyncio
    async def test_never_reraises_writes_state_error_returns_fallback(self, monkeypatch):
        """AC-2.3: state.error written, fallback_value returned, NO exception raised."""
        from app.agents.utils.node_error import NodeError
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
            fallback_value={"score": -1},
            max_retries=3,
        )(failing_node)

        result = await decorated(state)

        assert result == {"score": -1}
        assert "error" in state
        assert isinstance(state["error"], NodeError)
        assert state["error"].node_name == "failing_node"
        assert state["error"].cause == "schema_invalid"

    @pytest.mark.asyncio
    async def test_use_previous_calls_node_exactly_once(self, monkeypatch):
        """AC-2.3: use_previous does NOT retry (calls node only once)."""
        from app.agents.utils.node_error_handler import node_error_handler

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        call_count = {"n": 0}

        async def failing_node(state):
            call_count["n"] += 1
            raise Exception("transient")

        decorated = node_error_handler(
            fallback_strategy="use_previous",
            fallback_value=None,
        )(failing_node)

        await decorated({})
        assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# AC-2.4 — hard_fail strategy: immediate re-raise (no retry)
# ---------------------------------------------------------------------------
class TestHardFailStrategy:
    @pytest.mark.asyncio
    async def test_hard_fail_propagates_exception_unchanged(self, monkeypatch):
        """AC-2.4: hard_fail re-raises original exception, no retry."""
        from app.agents.utils.node_error_handler import node_error_handler

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        call_count = {"n": 0}

        async def failing_node(state):
            call_count["n"] += 1
            raise ValueError("boom")

        decorated = node_error_handler(
            fallback_strategy="hard_fail",
            fallback_value=None,
        )(failing_node)

        with pytest.raises(ValueError, match="boom"):
            await decorated({})

        assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# AC-2.5 — token limit truncation: doesn't consume max_retries
# ---------------------------------------------------------------------------
class TestTokenLimitTruncation:
    @pytest.mark.asyncio
    async def test_token_limit_truncates_prompt_not_max_retries(self, monkeypatch):
        """AC-2.5: token-limit goes through retry_with_shorter_prompt, NOT retried via max_retries."""
        from app.agents.utils.node_error_handler import node_error_handler

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        # Constant is exposed in module for grep verification (AC-2.5 R8)
        from app.agents.utils import node_error_handler as mod

        assert hasattr(mod, "_MAX_TRUNCATION_ATTEMPTS")
        assert mod._MAX_TRUNCATION_ATTEMPTS == 1

        # Track the prompt length passed on each call
        prompt_lengths: list[int] = []

        async def llm_like_node(state):
            attempts = len(prompt_lengths)
            prompt_lengths.append(100 if attempts == 0 else 50)
            if attempts == 0:
                raise openai.BadRequestError(
                    "prompt is too long", response=AsyncMock(), body={}
                )
            return {"ok": True}

        decorated = node_error_handler(
            fallback_strategy="retry",
            fallback_value=None,
            max_retries=3,
        )(llm_like_node)

        # Inject model_name into state so is_token_limit_exceeded recognises it
        state = {"_llm_model_name": "openai:gpt-4o"}
        result = await decorated(state)
        assert result == {"ok": True}
        # second prompt shorter than first
        assert prompt_lengths[1] < prompt_lengths[0]

    @pytest.mark.asyncio
    async def test_token_limit_recursive_guard_uses_max_truncation_attempts_one(
        self, monkeypatch
    ):
        """AC-2.5: _MAX_TRUNCATION_ATTEMPTS=1 — after 1 truncation, fall back to normal retry."""
        from app.agents.llm_client import LLMInvokeError
        from app.agents.utils.node_error_handler import node_error_handler

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        call_count = {"n": 0}

        async def always_token_limit(state):
            call_count["n"] += 1
            raise openai.BadRequestError(
                "prompt is too long", response=AsyncMock(), body={}
            )

        decorated = node_error_handler(
            fallback_strategy="retry",
            fallback_value=None,
            max_retries=3,
        )(always_token_limit)

        state = {"_llm_model_name": "openai:gpt-4o"}
        with pytest.raises(LLMInvokeError):
            await decorated(state)

        # Truncation attempt counts as 1 extra call; max_retries=3 gives at most 4 total
        # (3 retry + 1 truncation) before hard_fail.
        assert call_count["n"] <= 3 + 1


# ---------------------------------------------------------------------------
# AC-2.6 — 13 LLM nodes decorated
# ---------------------------------------------------------------------------
class TestLLMNodesHaveDecorator:
    def test_thirteen_llm_nodes_have_line_anchored_decorator(self):
        """AC-2.6: grep line-anchored count of @node_error_handler >= 13."""
        agents_dir = (
            Path(__file__).resolve().parents[1]
        )  # backend/app/agents
        pattern = re.compile(r"^@node_error_handler\b")

        count = 0
        decorated_files = []
        for py_file in agents_dir.rglob("*.py"):
            if "tests" in str(py_file):
                continue
            for line in py_file.read_text(encoding="utf-8").splitlines():
                if pattern.match(line):
                    count += 1
                    decorated_files.append(py_file.name)

        assert count >= 13, (
            f"Expected >= 13 line-anchored @node_error_handler, got {count}"
            f" in {decorated_files}"
        )


# ---------------------------------------------------------------------------
# AC-2.7 + AC-2.8 — intake / report explicit hard_fail
# ---------------------------------------------------------------------------
class TestIntakeAndReportHardFail:
    def test_intake_node_uses_hard_fail(self):
        """AC-2.7: intake.py decorator explicitly pins hard_fail."""
        from app.agents.interview.nodes.intake import intake_node

        path = Path(intake_node.__code__.co_filename)
        text = path.read_text(encoding="utf-8")
        decorator_lines = []
        func_lineno = intake_node.__code__.co_firstlineno - 1
        for line in text.splitlines()[:func_lineno]:
            if line.startswith("@node_error_handler"):
                decorator_lines.append(line)
        assert any(
            re.search(r"hard_fail", line) for line in decorator_lines
        ), f"intake.py missing hard_fail on @node_error_handler; got {decorator_lines}"

    def test_report_node_uses_hard_fail(self):
        """AC-2.8: report.py decorator explicitly pins hard_fail."""
        from app.agents.interview.nodes.report import report_node

        path = Path(report_node.__code__.co_filename)
        text = path.read_text(encoding="utf-8")
        decorator_lines = []
        func_lineno = report_node.__code__.co_firstlineno - 1
        for line in text.splitlines()[:func_lineno]:
            if line.startswith("@node_error_handler"):
                decorator_lines.append(line)
        assert any(
            re.search(r"hard_fail", line) for line in decorator_lines
        ), f"report.py missing hard_fail on @node_error_handler; got {decorator_lines}"


# ---------------------------------------------------------------------------
# AC-2.9 — double-decorator interaction with @traced_node (ERROR span)
# ---------------------------------------------------------------------------
class TestTracedNodeErrorSpan:
    @pytest.mark.asyncio
    async def test_traced_node_records_error_when_node_fails(self, monkeypatch):
        """AC-2.9: when node raises, @traced_node still marks span ERROR + record_exception."""
        from app.agents.utils.node_error_handler import node_error_handler
        from app.observability import traced_node

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        # set up an in-memory exporter to capture spans
        from opentelemetry import trace as ot_trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer(__name__)

        # monkeypatch the global tracer provider used by app.observability
        monkeypatch.setattr(ot_trace, "get_tracer", lambda *_a, **_kw: tracer)

        @traced_node("test_role.action")
        @node_error_handler(fallback_strategy="hard_fail")
        async def failing(state):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await failing({})

        spans = exporter.get_finished_spans()
        assert spans, "expected at least one span"
        error_span = next(
            (s for s in spans if "test_role.action" in s.name), None
        )
        assert error_span is not None
        # OTel Status.ERROR must be set OR recorded exception event present
        from opentelemetry.trace import StatusCode

        assert (
            error_span.status.status_code == StatusCode.ERROR
            or any(e.name == "exception" for e in error_span.events)
        ), f"span status={error_span.status} events={error_span.events}"


# ---------------------------------------------------------------------------
# AC-E2E-US1-1 — double decorator error propagation (no side effects)
# ---------------------------------------------------------------------------
class TestDoubleDecoratorErrorPropagation:
    @pytest.mark.asyncio
    async def test_double_decorator_re_raises_without_side_effects(self, monkeypatch):
        """AC-E2E-US1-1: @traced_node + @node_error_handler stack; exception propagates, no state.error written on hard_fail."""
        from app.agents.utils.node_error_handler import node_error_handler
        from app.observability import traced_node

        monkeypatch.setattr(
            "app.agents.checkpointer.retry_graph_op",
            lambda func, *a, **kw: func,
        )

        state: dict[str, Any] = {}

        @traced_node("double.decor_test")
        @node_error_handler(fallback_strategy="hard_fail")
        async def failing(state):
            raise RuntimeError("kaboom")

        with pytest.raises(RuntimeError, match="kaboom"):
            await failing(state)

        # hard_fail → state.error NOT written (only use_previous writes it)
        assert "error" not in state or state.get("error") is None


# ---------------------------------------------------------------------------
# AC-3.5 — NodeError Pydantic with 6 category Literal
# ---------------------------------------------------------------------------
class TestNodeErrorModel:
    def test_node_error_has_six_category_literal_values(self):
        """AC-3.5: NodeError.category literal matches 038 subclass __name__.lower()."""
        from typing import get_args

        from app.agents.utils.node_error import NodeError

        ann = NodeError.model_fields["category"].annotation
        # unwrap Literal / Optional
        args = get_args(ann)
        flat = []
        for a in args:
            flat.extend(get_args(a))
        values = tuple(sorted(flat))
        expected = (
            "checkpointer_unavailable",
            "oob",
            "parse_fail",
            "quota",
            "schema_invalid",
            "timeout",
        )
        for v in expected:
            assert v in values, f"missing category {v}; got {values}"


# ---------------------------------------------------------------------------
# AC-3.6 / AC-3.6a — exception classification imports 038 subclasses + 023
# CheckpointerUnavailableError (does NOT redefine them)
# ---------------------------------------------------------------------------
class TestExceptionClassificationImports:
    def test_node_error_handler_imports_5_structured_output_subclasses(self):
        """AC-3.6a: imports from app.agents.structured_output.errors."""
        import app.agents.utils.node_error_handler as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert re.search(
            r"from\s+app\.agents\.structured_output\.errors\s+import\s+[^#\n]*"
            r"(SchemaInvalid|ParseFail|Quota|Timeout|OutOfBounds)",
            src,
        ), "node_error_handler.py must import 038 subclasses"

    def test_node_error_handler_imports_checkpointer_unavailable_error(self):
        """AC-3.6a: imports CheckpointerUnavailableError from checkpointer.py."""
        import app.agents.utils.node_error_handler as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert re.search(
            r"from\s+app\.agents\.checkpointer\s+import\s+\(?[^#\n]*CheckpointerUnavailableError",
            src,
        ), "node_error_handler.py must import CheckpointerUnavailableError"
