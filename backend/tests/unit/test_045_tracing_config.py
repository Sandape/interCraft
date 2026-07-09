from __future__ import annotations

from app.observability import tracing


def test_tracing_config_clamps_sample_ratio() -> None:
    assert tracing.TracingConfig(sample_ratio=-1).sample_ratio == 0.0
    assert tracing.TracingConfig(sample_ratio=2).sample_ratio == 1.0


def test_run_context_round_trips_and_clears() -> None:
    tracing.clear_trace_context()
    tracing.bind_trace_context(run_id="run-123", trace_id="0" * 32, span_id="a" * 16)

    ctx = tracing.get_trace_context()
    assert ctx.run_id == "run-123"
    assert ctx.trace_id == "0" * 32
    assert ctx.span_id == "a" * 16

    tracing.clear_trace_context()
    assert tracing.get_trace_context().run_id is None


def test_traceparent_round_trip() -> None:
    ctx = tracing.TraceContext(run_id="run-1", trace_id="1" * 32, span_id="2" * 16)
    headers = tracing.inject_trace_context(ctx)

    restored = tracing.extract_trace_context(headers)
    assert restored.run_id == "run-1"
    assert restored.trace_id == "1" * 32
    assert restored.span_id == "2" * 16
    assert headers["traceparent"].startswith("00-")
