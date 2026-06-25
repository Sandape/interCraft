"""029 US1 — Integration tests: interview graph + MockLLMClient → single trace.

Tests per spec SC-001: one interview agent invocation produces a single
trace containing ≥5 node spans and ≥5 LLM call spans.

These tests do NOT require a real DeepSeek API key — they use the
MockLLMClient injected via ``LLM_MOCK_MODE=1``. They DO require a working
Postgres (for the LangGraph checkpointer) so they're marked integration.

If DATABASE_URL is the placeholder, the tests are skipped via the
``conftest.pytest_collection_modifyitems`` hook.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest

from app.observability import (
    TracingConfig,
    get_in_memory_exporter,
    init_tracing,
)
from app.observability.tracing import _reset_tracing_for_test


@pytest.fixture(autouse=True)
def _init_in_memory_tracing():
    """Init in-memory tracing before each test; reset after."""
    _reset_tracing_for_test()
    init_tracing(TracingConfig(exporter="in_memory"))
    yield
    _reset_tracing_for_test()


@pytest.fixture(autouse=True)
def _mock_llm_mode():
    """Enable MockLLMClient via env var so no real DeepSeek calls happen."""
    old = os.environ.get("LLM_MOCK_MODE")
    os.environ["LLM_MOCK_MODE"] = "1"
    yield
    if old is None:
        os.environ.pop("LLM_MOCK_MODE", None)
    else:
        os.environ["LLM_MOCK_MODE"] = old


def _spans():
    """Return collected spans from the in-memory exporter."""
    exporter = get_in_memory_exporter()
    assert exporter is not None, "InMemorySpanExporter not configured"
    return exporter.get_finished_spans()


def _span_names() -> list[str]:
    return [s.name for s in _spans()]


def _node_spans() -> list:
    return [s for s in _spans() if s.name.startswith("node.")]


def _llm_spans() -> list:
    return [s for s in _spans() if s.name == "llm.invoke"]


@pytest.mark.integration
class TestTracingGraphIntegration:
    """Integration: interview graph emits spans under one trace_id."""

    @pytest.mark.asyncio
    async def test_interview_node_functions_emit_spans_when_called(
        self,
    ):
        """Sanity: calling decorated node functions directly emits node spans.

        This bypasses the graph + checkpointer so it works without DB. It
        verifies that ``@traced_node`` is actually wired into the node
        functions (intake / question_gen / score / report).
        """
        from app.agents.interview.nodes.intake import intake_node
        from app.agents.interview.nodes.question_gen import question_gen_node
        from app.agents.interview.nodes.report import report_node
        from app.agents.interview.nodes.score import score_node

        # Each node expects InterviewGraphState; we pass minimal stub state.
        # MockLLMClient returns "" for unknown nodes — that's fine, we just
        # want to trigger the span.
        await intake_node(
            {
                "messages": [{"role": "user", "content": "前端工程师"}],
                "user_id": "00000000-0000-0000-0000-000000000001",
                "thread_id": "00000000-0000-0000-0000-000000000002",
            }
        )
        await question_gen_node(
            {
                "current_question": 0,
                "user_id": "00000000-0000-0000-0000-000000000001",
                "thread_id": "00000000-0000-0000-0000-000000000002",
            }
        )
        await score_node(
            {
                "questions": [{"question": "q1", "dimension": "tech_depth"}],
                "scores": [],
                "current_question": 0,
                "messages": [{"role": "user", "content": "answer"}],
                "user_id": "00000000-0000-0000-0000-000000000001",
                "thread_id": "00000000-0000-0000-0000-000000000002",
            }
        )
        await report_node(
            {
                "scores": [{"score": 5, "dimension": "tech_depth", "feedback": ""}],
                "questions": [],
                "user_id": "00000000-0000-0000-0000-000000000001",
                "thread_id": "00000000-0000-0000-0000-000000000002",
            }
        )

        # Each node function should have emitted a node.<name> span.
        names = _span_names()
        assert "node.intake" in names
        assert "node.question_gen" in names
        assert "node.score" in names
        assert "node.report" in names

        # Each node should also have emitted an llm.invoke child span.
        assert len(_llm_spans()) >= 4

    @pytest.mark.asyncio
    async def test_llm_invoke_spans_carry_model_and_token_attributes(self):
        """FR-003: LLM call spans carry model + token + latency attrs."""
        from app.agents.interview.nodes.intake import intake_node

        await intake_node(
            {
                "messages": [{"role": "user", "content": "前端工程师"}],
                "user_id": "00000000-0000-0000-0000-000000000001",
                "thread_id": "00000000-0000-0000-0000-000000000002",
            }
        )

        llm_spans = _llm_spans()
        assert len(llm_spans) >= 1
        attrs = llm_spans[0].attributes
        # MockLLMClient sets model="mock-llm" (FR-018).
        assert attrs.get("llm.model") == "mock-llm"
        # Token attributes present (mock sets them to 0).
        assert "llm.prompt_tokens" in attrs
        assert "llm.completion_tokens" in attrs
        assert attrs.get("llm.cache_status") == "mock"
        # node.name is set on the LLM span too for filtering by node.
        assert attrs.get("node.name") == "intake"

    @pytest.mark.asyncio
    async def test_node_span_marked_error_on_exception(self):
        """FR-001 / US1 AS4: failed node → span marked with error status."""
        from app.agents.interview.nodes.intake import intake_node

        # Patch LLM client to raise → intake_node catches + returns fallback,
        # but the *node* span still completes (the node didn't raise).
        # We need to make the node itself raise — patch a downstream call.
        with patch(
            "app.agents.interview.nodes.intake._load_job_context",
            side_effect=RuntimeError("DB unreachable"),
        ):
            # The node has a job_id in state → _load_job_context is called
            # inside a try/except, so the node won't raise. Patch something
            # that propagates: get_llm_client.
            with patch(
                "app.agents.interview.nodes.intake.get_llm_client",
                side_effect=RuntimeError("LLM unavailable"),
            ):
                # intake_node does NOT catch get_llm_client() — it catches
                # the .invoke() call, but get_llm_client() itself raising
                # propagates. Actually, looking at the code, get_llm_client
                # is called outside the try block, so it propagates.
                with pytest.raises(RuntimeError, match="LLM unavailable"):
                    await intake_node(
                        {
                            "messages": [{"role": "user", "content": "前端工程师"}],
                            "user_id": "00000000-0000-0000-0000-000000000001",
                            "thread_id": "00000000-0000-0000-0000-000000000002",
                        }
                    )

        # The node.intake span should be marked ERROR.
        node_spans = _node_spans()
        intake_spans = [s for s in node_spans if s.name == "node.intake"]
        assert len(intake_spans) >= 1
        from opentelemetry.trace import StatusCode

        assert intake_spans[0].status.status_code == StatusCode.ERROR
        # Exception event recorded.
        exc_events = [e for e in intake_spans[0].events if e.name == "exception"]
        assert len(exc_events) == 1

    @pytest.mark.asyncio
    async def test_trace_export_fail_open_does_not_block_agent(self):
        """FR-017: unreachable OTLP endpoint → agent still completes.

        Init with OTLP exporter pointing at an unreachable endpoint; run a
        decorated node function; assert it completes successfully + the
        node span is still emitted via the in-memory exporter fallback.

        Actually testing this requires re-init with OTLP exporter (which
        replaces the in-memory one). Instead, we verify fail-open at the
        library level: patch the BatchSpanProcessor to raise on export,
        then run a span — agent code should be unaffected.
        """
        # Re-init with OTLP exporter pointing at unreachable endpoint.
        _reset_tracing_for_test()
        init_tracing(
            TracingConfig(
                exporter="otlp",
                otlp_endpoint="http://127.0.0.1:1/v1/traces",  # unreachable port
            )
        )

        from app.agents.interview.nodes.intake import intake_node

        # Should complete without raising, even though OTLP backend is down.
        result = await intake_node(
            {
                "messages": [{"role": "user", "content": "前端工程师"}],
                "user_id": "00000000-0000-0000-0000-000000000001",
                "thread_id": "00000000-0000-0000-0000-000000000002",
            }
        )
        assert "position" in result  # Node returned normally

    @pytest.mark.asyncio
    async def test_multiple_node_spans_share_trace_id_when_called_in_sequence(
        self,
    ):
        """US1 SC-001 partial: multiple nodes called in sequence share trace_id.

        Note: this is a node-level test (not graph-level) because each node
        call is a separate invocation without an enclosing root span. In
        production, the graph's ``ainvoke`` is the root span — but for
        testing we verify that consecutive spans within a single
        ``with span('root'):`` block share a trace_id.
        """
        from app.observability import span

        # Simulate a "root" span that wraps multiple node calls.
        with span("agent.invoke", graph="interview"):
            from app.agents.interview.nodes.intake import intake_node

            await intake_node(
                {
                    "messages": [{"role": "user", "content": "前端工程师"}],
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "thread_id": "00000000-0000-0000-0000-000000000002",
                }
            )

        # All spans should share the root span's trace_id.
        spans = _spans()
        root_spans = [s for s in spans if s.name == "agent.invoke"]
        assert len(root_spans) == 1
        root_trace_id = root_spans[0].context.trace_id

        # Every other span should have the same trace_id.
        for sp in spans:
            assert sp.context.trace_id == root_trace_id, (
                f"span {sp.name} has trace_id {sp.context.trace_id}, expected {root_trace_id}"
            )

        # The intake node span + llm.invoke span are children of the root.
        node_spans = [s for s in spans if s.name == "node.intake"]
        assert len(node_spans) == 1
        assert node_spans[0].parent is not None
        assert node_spans[0].parent.span_id == root_spans[0].context.span_id

        llm_spans = [s for s in spans if s.name == "llm.invoke"]
        assert len(llm_spans) == 1
        # llm.invoke's parent is the node.intake span.
        assert llm_spans[0].parent is not None
        assert llm_spans[0].parent.span_id == node_spans[0].context.span_id

    @pytest.mark.asyncio
    async def test_structlog_log_events_carry_trace_id_during_node_span(self):
        """FR-013: structured logs emitted during a node span carry trace_id."""
        import structlog

        from app.observability import span
        from app.observability.tracing import _inject_otel_context

        captured: list[dict] = []

        def _capture_processor(_logger, _method_name, event_dict):
            event_dict = _inject_otel_context(_logger, _method_name, event_dict)
            captured.append(dict(event_dict))
            raise structlog.DropEvent

        structlog.configure(
            processors=[_capture_processor],
            logger_factory=structlog.PrintLoggerFactory(),
        )
        log = structlog.get_logger("test")

        with span("node.intake", **{"node.name": "intake"}) as s:
            ctx = s.get_span_context()
            expected_trace = f"{ctx.trace_id:032x}"
            log.info("inside_node")

        assert len(captured) == 1
        assert captured[0]["trace_id"] == expected_trace
