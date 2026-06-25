"""029 US1 — Unit tests: tracing library init + fail-open (FR-017).

Tests per spec FR-017 (fail-open) and FR-012 (local dev trace viewer).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.observability import (
    TracingConfig,
    get_in_memory_exporter,
    init_tracing,
    shutdown_tracing,
)
from app.observability.tracing import _reset_tracing_for_test


@pytest.fixture(autouse=True)
def _reset_tracing():
    """Reset tracing state before + after each test for isolation."""
    _reset_tracing_for_test()
    yield
    _reset_tracing_for_test()


def test_init_tracing_with_noop_exporter_does_not_raise():
    """exporter='none' → no processor added, no spans emitted."""
    init_tracing(TracingConfig(exporter="none"))
    # No in-memory exporter configured.
    assert get_in_memory_exporter() is None


def test_init_tracing_with_console_exporter_does_not_raise(capsys):
    """exporter='console' → ConsoleSpanExporter registered (writes to stderr)."""
    init_tracing(TracingConfig(exporter="console"))
    # No in-memory exporter.
    assert get_in_memory_exporter() is None
    # Emit a span; console exporter writes to stderr.
    from app.observability import span

    with span("test.console_span"):
        pass
    # Console exporter prints to stderr; not asserting on format to keep
    # the test stable across OTel SDK versions.


def test_init_tracing_with_in_memory_exporter_collects_spans():
    """exporter='in_memory' → InMemorySpanExporter collects spans."""
    init_tracing(TracingConfig(exporter="in_memory"))
    exporter = get_in_memory_exporter()
    assert exporter is not None

    from app.observability import span

    with span("test.in_memory_span", attr1="val1"):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.in_memory_span"
    assert spans[0].attributes.get("attr1") == "val1"


def test_init_tracing_with_otlp_exporter_endpoint_configured():
    """exporter='otlp' + endpoint → OTLPSpanExporter configured (no exception)."""
    # Patch OTLPSpanExporter so we don't actually try to send.
    with patch(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
    ) as mock_cls:
        init_tracing(
            TracingConfig(
                exporter="otlp",
                otlp_endpoint="http://localhost:4318/v1/traces",
                otlp_headers={"x-api-key": "test"},
            )
        )
        # OTLPSpanExporter was instantiated with the endpoint.
        mock_cls.assert_called_once()
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["endpoint"] == "http://localhost:4318/v1/traces"
        assert kwargs["headers"] == {"x-api-key": "test"}


def test_init_tracing_with_otlp_exporter_no_endpoint_falls_back_to_console():
    """exporter='otlp' + no endpoint → fallback to console (dev mode)."""
    init_tracing(TracingConfig(exporter="otlp", otlp_endpoint=None))
    # No OTLP exporter instantiated; console exporter used instead.
    # Verify by emitting a span and checking it doesn't fail.
    from app.observability import span

    with span("test.otlp_fallback_span"):
        pass
    # No in-memory exporter; console exporter is the fallback.
    assert get_in_memory_exporter() is None


def test_init_tracing_fail_open_on_exception():
    """Mock OTel SDK to raise during init → init_tracing catches + log warning + noop tracer.

    Verifies FR-017 fail-open: trace init failure never blocks agent.
    """
    # Force TracerProvider to raise.
    with patch(
        "opentelemetry.sdk.trace.TracerProvider",
        side_effect=RuntimeError("simulated OTel SDK failure"),
    ):
        # Must not raise.
        init_tracing(TracingConfig(exporter="in_memory"))

    # Tracing is in fail-open mode: spans are no-op.
    from app.observability import span

    with span("test.after_failure") as s:
        # set_attribute must be a no-op (not raise).
        s.set_attribute("k", "v")

    # No spans collected (no exporter registered).
    assert get_in_memory_exporter() is None


def test_init_tracing_idempotent():
    """Calling init_tracing twice does not re-register provider."""
    init_tracing(TracingConfig(exporter="in_memory"))
    exporter1 = get_in_memory_exporter()

    # Second call should be a no-op.
    init_tracing(TracingConfig(exporter="in_memory"))
    exporter2 = get_in_memory_exporter()

    # Same exporter instance (idempotent).
    assert exporter1 is exporter2


def test_shutdown_tracing_flushes_spans():
    """shutdown_tracing() flushes pending spans and clears in-memory exporter."""
    init_tracing(TracingConfig(exporter="in_memory"))
    exporter = get_in_memory_exporter()
    assert exporter is not None

    from app.observability import span

    with span("test.shutdown_flush"):
        pass

    # Span is collected before shutdown.
    assert len(exporter.get_finished_spans()) == 1

    shutdown_tracing()

    # After shutdown, in-memory exporter reference is cleared.
    assert get_in_memory_exporter() is None


def test_shutdown_tracing_when_not_initialized_is_noop():
    """shutdown_tracing() before init_tracing is a no-op."""
    # Should not raise.
    shutdown_tracing()
