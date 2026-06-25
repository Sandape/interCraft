"""029 US1 — Unit tests: span attributes + decorators + structlog processor.

Tests per spec FR-001/002/003/004/005 (span emission + hierarchy +
attributes) and FR-013 (logs join to traces via trace_id).
"""
from __future__ import annotations

import structlog
import pytest

from app.observability import (
    TracingConfig,
    finish_span_with_exception,
    get_in_memory_exporter,
    init_tracing,
    record_llm_span_attributes,
    span,
    traced_node,
    traced_tool,
)
from app.observability.tracing import _inject_otel_context, _reset_tracing_for_test


@pytest.fixture(autouse=True)
def _reset_tracing():
    """Init in-memory tracing before each test; reset after."""
    _reset_tracing_for_test()
    init_tracing(TracingConfig(exporter="in_memory"))
    yield
    _reset_tracing_for_test()


def _spans():
    """Return collected spans from the in-memory exporter."""
    return get_in_memory_exporter().get_finished_spans()


def test_span_creates_with_correct_name():
    with span("test.span_name"):
        pass
    spans = _spans()
    assert len(spans) == 1
    assert spans[0].name == "test.span_name"


def test_span_attributes_set_correctly():
    with span("test.span", node_name="intake", model="deepseek", tokens=100):
        pass
    spans = _spans()
    assert spans[0].attributes.get("node_name") == "intake"
    assert spans[0].attributes.get("model") == "deepseek"
    assert spans[0].attributes.get("tokens") == 100


def test_span_records_exception_on_error():
    with pytest.raises(ValueError, match="boom"):
        with span("test.error_span"):
            raise ValueError("boom")
    spans = _spans()
    assert len(spans) == 1
    # Status should be ERROR.
    from opentelemetry.trace import StatusCode

    assert spans[0].status.status_code == StatusCode.ERROR
    # Exception should be recorded as an event.
    exc_events = [
        e for e in spans[0].events if e.name == "exception"
    ]
    assert len(exc_events) == 1


def test_span_no_error_on_success():
    with span("test.ok_span"):
        pass
    spans = _spans()
    from opentelemetry.trace import StatusCode

    # UNSET means the span completed without error.
    assert spans[0].status.status_code == StatusCode.UNSET


def test_traced_node_decorator_async_emits_span():
    @traced_node("intake")
    async def fake_node(state):
        return {"result": "ok"}

    import asyncio

    result = asyncio.run(fake_node({"k": "v"}))
    assert result == {"result": "ok"}
    spans = _spans()
    assert len(spans) == 1
    assert spans[0].name == "node.intake"
    assert spans[0].attributes.get("node.name") == "intake"


def test_traced_node_decorator_sync_emits_span():
    @traced_node("planner_complete")
    def fake_sync_node(state):
        return {"forwarded": True}

    result = fake_sync_node({"k": "v"})
    assert result == {"forwarded": True}
    spans = _spans()
    assert len(spans) == 1
    assert spans[0].name == "node.planner_complete"


def test_traced_node_decorator_propagates_exception():
    @traced_node("boom_node")
    async def fake_failing_node(state):
        raise RuntimeError("intentional")

    import asyncio

    with pytest.raises(RuntimeError, match="intentional"):
        asyncio.run(fake_failing_node({}))

    spans = _spans()
    assert len(spans) == 1
    from opentelemetry.trace import StatusCode

    assert spans[0].status.status_code == StatusCode.ERROR


def test_traced_tool_decorator_emits_span_with_args_summary():
    @traced_tool("tavily_search")
    async def fake_tool(query, *, max_results=5):
        return "result-text"

    import asyncio

    result = asyncio.run(fake_tool("hello world", max_results=3))
    assert result == "result-text"

    spans = _spans()
    assert len(spans) == 1
    assert spans[0].name == "tool.tavily_search"
    assert spans[0].attributes.get("tool.name") == "tavily_search"
    # args_summary should include the positional + keyword args.
    args_summary = spans[0].attributes.get("args_summary", "")
    assert "'hello world'" in args_summary
    assert "max_results=3" in args_summary
    # result_summary should be set.
    assert spans[0].attributes.get("result_summary") == "result-text"


def test_traced_tool_truncates_long_args():
    @traced_tool("big_tool")
    async def fake_tool(big_arg):
        return "ok"

    import asyncio

    long_arg = "x" * 500
    asyncio.run(fake_tool(long_arg))

    spans = _spans()
    args_summary = spans[0].attributes.get("args_summary", "")
    # Truncated to 100 chars.
    assert len(args_summary) <= 100


def test_record_llm_span_attributes_sets_model_and_tokens():
    with span("llm.invoke", node_name="intake") as s:
        record_llm_span_attributes(
            s,
            model="deepseek-v4-flash",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=1234,
            cache_status="miss",
            retry_count=0,
        )
    spans = _spans()
    attrs = spans[0].attributes
    assert attrs.get("model") == "deepseek-v4-flash"
    assert attrs.get("prompt_tokens") == 100
    assert attrs.get("completion_tokens") == 50
    assert attrs.get("duration_ms") == 1234
    assert attrs.get("cache_status") == "miss"
    assert attrs.get("retry_count") == 0


def test_record_llm_span_attributes_ignores_none_values():
    with span("llm.invoke") as s:
        record_llm_span_attributes(s, model="X", prompt_tokens=None, completion_tokens=50)
    spans = _spans()
    attrs = spans[0].attributes
    assert attrs.get("model") == "X"
    assert attrs.get("completion_tokens") == 50
    # prompt_tokens=None should not appear as an attribute.
    assert "prompt_tokens" not in attrs


def test_finish_span_with_exception_marks_error():
    with span("llm.invoke") as s:
        finish_span_with_exception(s, RuntimeError("oops"))
    spans = _spans()
    from opentelemetry.trace import StatusCode

    assert spans[0].status.status_code == StatusCode.ERROR


def test_structlog_processor_injects_trace_id_when_span_active():
    """Active span → event_dict has trace_id + span_id matching the span."""
    with span("test.span_for_log") as s:
        ctx = s.get_span_context()
        expected_trace = f"{ctx.trace_id:032x}"
        expected_span = f"{ctx.span_id:016x}"

        event = _inject_otel_context(None, "info", {"event": "test"})
        assert event["trace_id"] == expected_trace
        assert event["span_id"] == expected_span


def test_structlog_processor_no_trace_id_when_no_span():
    """No active span → event_dict has no trace_id field."""
    event = _inject_otel_context(None, "info", {"event": "test"})
    assert "trace_id" not in event
    assert "span_id" not in event


def test_structlog_processor_injects_trace_id_during_node_span():
    """Integration: structlog + traced_node → log inside node carries trace_id."""
    captured: list[dict] = []

    def _capture_processor(_logger, _method_name, event_dict):
        # Apply our processor then capture.
        event_dict = _inject_otel_context(_logger, _method_name, event_dict)
        captured.append(dict(event_dict))
        # Drop the event so structlog doesn't try to render to PrintLogger
        # (which doesn't accept arbitrary kwargs).
        raise structlog.DropEvent

    structlog.configure(
        processors=[_capture_processor],
        logger_factory=structlog.PrintLoggerFactory(),
    )
    log = structlog.get_logger("test")

    @traced_node("logged_node")
    async def node_with_log(state):
        log.info("inside_node")
        return {}

    import asyncio

    asyncio.run(node_with_log({}))

    # The captured log should have trace_id + span_id.
    assert len(captured) == 1
    assert "trace_id" in captured[0]
    assert "span_id" in captured[0]
    assert len(captured[0]["trace_id"]) == 32  # 16 bytes hex = 32 chars
    assert len(captured[0]["span_id"]) == 16  # 8 bytes hex = 16 chars


def test_structlog_processor_clears_when_span_exits():
    """After span exits, subsequent logs have no trace_id."""
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

    with span("test.span"):
        log.info("inside_span")

    log.info("outside_span")

    assert len(captured) == 2
    assert "trace_id" in captured[0]  # inside
    assert "trace_id" not in captured[1]  # outside
