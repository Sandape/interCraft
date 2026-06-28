"""OTel tracing init + decorators + structlog processor (US1).

Implements the public API documented in ``app.observability.__init__``.

Fail-open philosophy (FR-017):
- ``init_tracing`` catches all exceptions during OTel SDK setup. On failure,
  logs a warning and leaves the default no-op tracer in place. Agent code
  continues to run; spans are simply dropped.
- ``span`` / ``traced_node`` / ``traced_tool`` wrap all OTel calls in
  ``try/except`` so an OTel SDK bug can never raise into business code.
- The structlog processor never raises; if reading the active span fails,
  the event dict is returned untouched.

Backward compat (FR-008):
- The existing ``_request_id_var`` ContextVar in ``app.core.logging`` is
  untouched. OTel trace context is an additional correlation layer; both
  coexist during migration. Logs carry both ``request_id`` (legacy) and
  ``trace_id`` + ``span_id`` (new) when a span is active.

PII (FR-016, basic):
- ``@traced_tool`` truncates ``args_summary`` and ``result_summary`` to 100
  chars. User free-text answers are NOT put in span attributes by
  ``@traced_node`` or the LLM client wrapper. Complete PII redaction
  (regex-based scrubbing of email / phone / etc.) is ⏳ deferred.
"""
from __future__ import annotations

import contextlib
import functools
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal, ParamSpec, TypeVar

import structlog

logger = structlog.get_logger("observability.tracing")

T = TypeVar("T")
P = ParamSpec("P")

ExportMode = Literal["none", "console", "in_memory", "otlp"]

# Module-level holder for the in-memory exporter so tests can inspect
# collected spans without holding a reference on every call site.
_in_memory_exporter: Any | None = None

# Module-level holder for the TracerProvider. We keep this locally (rather
# than relying on ``trace.set_tracer_provider``) because OTel's global
# provider is a set-once API — once registered, it cannot be replaced in
# the same process. Tests need to re-init with different exporters, so we
# store the provider here and ``get_tracer`` reads it from this slot.
_provider: Any | None = None

# Last config used to init tracing. ``init_tracing`` is idempotent when the
# same config is passed twice (avoids re-init churn + preserves the in-memory
# exporter's collected spans across calls).
_last_config: TracingConfig | None = None

# Whether init_tracing has been called for this process. Idempotent —
# subsequent calls are a no-op (we don't re-register the global provider
# because OTel SDK only allows one provider per process).
_tracing_initialized: bool = False


@dataclass
class TracingConfig:
    """Configuration for OTel tracing initialization.

    Attributes
    ----------
    service_name:
        OTel resource attribute ``service.name``. Identifies the emitting
        service in the trace backend.
    exporter:
        - ``"none"`` — no-op tracer, no spans emitted (use in tests that
          don't care about traces)
        - ``"console"`` — emit spans to stderr via ``ConsoleSpanExporter``
          (dev default, no external backend needed, FR-012)
        - ``"in_memory"`` — collect spans in an ``InMemorySpanExporter``;
          retrieve via ``get_in_memory_exporter()`` (for tests)
        - ``"otlp"`` — emit spans via OTLP HTTP to ``otlp_endpoint``
    otlp_endpoint:
        OTLP HTTP endpoint URL, e.g. ``http://localhost:4318/v1/traces``.
        Ignored unless ``exporter == "otlp"``. If ``exporter == "otlp"``
        but endpoint is empty, falls back to ``console`` (dev mode).
    otlp_headers:
        Optional headers for OTLP exporter (e.g. auth tokens).
    sample_ratio:
        Trace sampling ratio 0.0–1.0. Default 1.0 = 100% sampling.
        US3 will make this configurable per graph / outcome. For now,
        every span is sampled.
    """

    service_name: str = "intercraft-backend"
    exporter: ExportMode = "console"
    otlp_endpoint: str | None = None
    otlp_headers: dict[str, str] | None = None
    sample_ratio: float = 1.0


def init_tracing(config: TracingConfig) -> None:
    """Initialize the OTel tracer provider.

    Idempotent: subsequent calls with the same config are no-ops. Different
    config = re-init (clears + rebuilds the provider). Fail-open (FR-017):
    any OTel SDK exception is caught, logged, and tracing is left in
    no-op mode.

    Note: we store the provider in a module global (``_provider``) rather
    than relying on ``trace.set_tracer_provider`` because OTel's global
    provider is a set-once API — once registered, it cannot be replaced
    in the same process. Tests need to re-init with different exporters,
    so we keep the provider locally and ``get_tracer`` reads from it.

    For production (FastAPI lifespan), the first init also registers the
    provider globally so any third-party library using
    ``trace.get_tracer_provider()`` sees our provider.
    """
    global _tracing_initialized, _in_memory_exporter, _provider, _last_config

    # Idempotent: skip if same config (avoid re-init churn).
    if _tracing_initialized and _last_config == config:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )

        # Tear down previous provider (for re-init scenarios / tests).
        if _provider is not None:
            with contextlib.suppress(Exception):
                _provider.force_flush(timeout_millis=5000)
                _provider.shutdown()
            _provider = None
            _in_memory_exporter = None

        resource = Resource.create({"service.name": config.service_name})
        provider = TracerProvider(resource=resource)

        # Resolve effective exporter. OTLP without endpoint falls back to
        # console so dev environments without a configured backend still
        # get visible spans (FR-012 local dev trace viewer).
        effective: ExportMode = config.exporter
        if effective == "otlp" and not config.otlp_endpoint:
            logger.warning(
                "tracing.otlp_no_endpoint_fallback_to_console",
                reason="OTLP_EXPORTER_OTLP_ENDPOINT not set",
            )
            effective = "console"

        if effective == "console":
            provider.add_span_processor(
                SimpleSpanProcessor(ConsoleSpanExporter())
            )
        elif effective == "in_memory":
            from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
                InMemorySpanExporter,
            )

            _in_memory_exporter = InMemorySpanExporter()
            provider.add_span_processor(
                SimpleSpanProcessor(_in_memory_exporter)
            )
        elif effective == "otlp":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            otlp_exporter = OTLPSpanExporter(
                endpoint=config.otlp_endpoint,
                headers=config.otlp_headers,
            )
            # BatchSpanProcessor is async — does not block the main path.
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        # effective == "none" → no processor, spans are dropped

        _provider = provider
        # Register globally — first call wins; subsequent calls log a
        # warning but we don't care because we read from _provider anyway.
        with contextlib.suppress(Exception):
            trace.set_tracer_provider(provider)
        _tracing_initialized = True
        _last_config = config
        logger.info(
            "tracing.initialized",
            exporter=effective,
            service_name=config.service_name,
            sample_ratio=config.sample_ratio,
        )
    except Exception:
        # FR-017 fail-open: log + leave no-op tracer in place.
        logger.warning("tracing.init_failed_fail_open", exc_info=True)
        _tracing_initialized = True  # Don't retry — fail-open permanently


def shutdown_tracing() -> None:
    """Flush + shutdown the tracer provider.

    Best-effort: never raises. Called from FastAPI lifespan shutdown.
    """
    global _tracing_initialized, _in_memory_exporter, _provider, _last_config

    if not _tracing_initialized:
        return

    if _provider is not None:
        with contextlib.suppress(Exception):
            _provider.force_flush(timeout_millis=5000)
        with contextlib.suppress(Exception):
            _provider.shutdown()

    _tracing_initialized = False
    _in_memory_exporter = None
    _provider = None
    _last_config = None


def get_tracer() -> Any:
    """Return the OTel tracer.

    Always returns a tracer — if ``init_tracing`` was never called or
    failed, OTel returns a no-op ``ProxyTracer`` that emits nothing.

    Reads from our local ``_provider`` slot so test re-init works (the
    global ``trace.set_tracer_provider`` is set-once).
    """
    from opentelemetry import trace

    if _provider is not None:
        return _provider.get_tracer("intercraft")
    # Fallback: global provider (may be no-op ProxyTracerProvider).
    return trace.get_tracer("intercraft")


def get_in_memory_exporter() -> Any | None:
    """Return the in-memory span exporter if configured, else None.

    For tests: ``init_tracing(TracingConfig(exporter="in_memory"))`` then
    call this to inspect collected spans.
    """
    return _in_memory_exporter


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[Any]:
    """Context manager that creates an OTel span.

    Sets initial attributes from ``attrs``. On exception, sets span status
    to ERROR + records the exception, then re-raises. On normal exit, the
    span is ended automatically.

    Fail-open: if OTel itself is broken (init failed, SDK bug, etc.), a
    no-op span is yielded so business code can still call
    ``record_llm_span_attributes`` / ``finish_span_with_exception`` on it
    without checking span type. Business exceptions are NOT swallowed —
    they propagate to the caller as-is.
    """
    noop = _NoopSpan()

    # Try to create the OTel span; if OTel is broken, fall back to noop.
    otel_span: Any = noop
    otel_cm: Any = None
    try:
        tracer = get_tracer()
        otel_cm = tracer.start_as_current_span(name)
        otel_span = otel_cm.__enter__()
        # Set initial attributes (best-effort).
        for k, v in attrs.items():
            with contextlib.suppress(Exception):
                otel_span.set_attribute(k, v)
    except Exception:
        # Fail-open: OTel itself is broken. Yield a noop span.
        logger.warning(
            "tracing.span_failed_fail_open", span_name=name, exc_info=True
        )
        otel_span = noop
        otel_cm = None

    # Run the body. Body exceptions are business logic; mark span + re-raise.
    try:
        yield otel_span
    except Exception as exc:
        # Mark the span as error (best-effort).
        with contextlib.suppress(Exception):
            from opentelemetry.trace import StatusCode, Status

            otel_span.set_status(Status(StatusCode.ERROR, str(exc)))
            otel_span.record_exception(exc)
        # Exit the OTel CM cleanly (we've already set the error status).
        if otel_cm is not None:
            with contextlib.suppress(Exception):
                otel_cm.__exit__(None, None, None)
        raise
    else:
        # Normal exit.
        if otel_cm is not None:
            with contextlib.suppress(Exception):
                otel_cm.__exit__(None, None, None)


def record_llm_span_attributes(otel_span: Any, **attrs: Any) -> None:
    """Set LLM-specific attributes on a span.

    Best-effort: any OTel exception is swallowed (FR-017 fail-open).
    Accepts a span (real OTel Span or ``_NoopSpan``) and any kwargs.
    """
    with contextlib.suppress(Exception):
        for k, v in attrs.items():
            if v is None:
                continue
            otel_span.set_attribute(k, v)


def finish_span_with_exception(
    otel_span: Any, exc: BaseException
) -> None:
    """Mark a span as ERROR + record the exception.

    Best-effort: any OTel exception is swallowed (FR-017 fail-open).
    """
    with contextlib.suppress(Exception):
        from opentelemetry.trace import StatusCode, Status

        otel_span.set_status(Status(StatusCode.ERROR, str(exc)))
        otel_span.record_exception(exc)


def traced_node(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that wraps a graph node function in a ``node.{name}`` span.

    Supports both async and sync functions (detected via
    ``inspect.iscoroutinefunction``). The wrapped function:
    - starts a ``node.{name}`` span
    - sets ``node.name`` attribute
    - on success: ends the span (via context manager)
    - on exception: marks span as ERROR + records exception + re-raises
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                with span(f"node.{name}", **{"node.name": name}):
                    return await fn(*args, **kwargs)  # type: ignore[no-any-return]

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                with span(f"node.{name}", **{"node.name": name}):
                    return fn(*args, **kwargs)

            return sync_wrapper

    return decorator


def traced_tool(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that wraps a tool function in a ``tool.{name}`` span.

    Sets ``tool.name`` + ``args_summary`` (truncated to 100 chars) +
    ``result_summary`` (truncated to 100 chars). PII redaction is basic
    (truncation only); complete redaction is ⏳ deferred (FR-016).
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                args_summary = _summarize_args(args, kwargs)
                with span(
                    f"tool.{name}",
                    **{"tool.name": name, "args_summary": args_summary},
                ) as s:
                    result: Any = await fn(*args, **kwargs)
                    record_llm_span_attributes(
                        s, result_summary=_truncate(str(result), 100)
                    )
                    return result  # type: ignore[no-any-return]

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                args_summary = _summarize_args(args, kwargs)
                with span(
                    f"tool.{name}",
                    **{"tool.name": name, "args_summary": args_summary},
                ) as s:
                    result = fn(*args, **kwargs)
                    record_llm_span_attributes(
                        s, result_summary=_truncate(str(result), 100)
                    )
                    return result

            return sync_wrapper

    return decorator


def _summarize_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Build a truncated summary of positional + keyword args."""
    parts: list[str] = []
    for a in args:
        parts.append(repr(a))
    for k, v in kwargs.items():
        parts.append(f"{k}={v!r}")
    return _truncate(", ".join(parts), 100)


def _truncate(s: str, max_len: int = 100) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _inject_otel_context(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor: inject trace_id + span_id from active span.

    Fail-open: never raises. When no span is active (or OTel is not
    initialized), the event dict is returned unchanged.
    """
    try:
        from opentelemetry import trace as otel_trace_api

        active = otel_trace_api.get_current_span()
        if active is None:
            return event_dict
        ctx = active.get_span_context()
        if ctx is None or not ctx.is_valid:
            return event_dict
        event_dict["trace_id"] = f"{ctx.trace_id:032x}"
        event_dict["span_id"] = f"{ctx.span_id:016x}"
    except Exception:
        # Fail-open: never break logging.
        pass
    return event_dict


class _NoopSpan:
    """Fallback span used when OTel itself is broken.

    Implements the subset of Span API used by ``record_llm_span_attributes``
    and ``finish_span_with_exception`` so business code can call them
    without checking span type.
    """

    def set_attribute(self, _key: str, _value: Any) -> None:
        pass

    def set_status(self, _status: Any) -> None:
        pass

    def record_exception(self, _exc: BaseException) -> None:
        pass

    def end(self) -> None:
        pass

    def get_span_context(self) -> Any:
        class _Ctx:
            is_valid = False
            trace_id = 0
            span_id = 0

        return _Ctx()


def _reset_tracing_for_test() -> None:
    """Reset module state for test isolation.

    Clears the in-memory exporter and the ``_tracing_initialized`` flag
    so the next ``init_tracing`` call re-registers a fresh provider.

    Note: the OTel global ``trace.set_tracer_provider`` is set-once; we
    cannot unset it. But ``get_tracer`` reads from our local ``_provider``
    slot, so resetting that slot is enough for tests.

    Test-only — do not call from production code.
    """
    global _tracing_initialized, _in_memory_exporter, _provider, _last_config
    if _provider is not None:
        with contextlib.suppress(Exception):
            _provider.force_flush(timeout_millis=5000)
            _provider.shutdown()
    _tracing_initialized = False
    _in_memory_exporter = None
    _provider = None
    _last_config = None


# ---------------------------------------------------------------------------
# T127 (US7) — extract_trace_id_from_span_or_unavailable
# ---------------------------------------------------------------------------


#: Literal sentinel returned when no OTel span is active or trace is
#: not initialized. Surfaced in eval-report / badcase fields so
#: downstream consumers can distinguish "no trace" from "real trace".
TRACE_UNAVAILABLE: str = "unavailable"


def extract_trace_id_from_span_or_unavailable() -> str:
    """Return the current OTel trace id (32-char hex) or ``"unavailable"``.

    REQ-033 US7 (T127) contract: callers (eval report, badcase
    promotion) need a stable way to grab the active trace id without
    caring whether OTel is initialized. When no span is active (or
    the SDK isn't loaded), this function returns the literal string
    ``"unavailable"`` — never ``None``, never empty, never crashes.

    Fail-open (FR-017): if reading the active span raises for any
    reason, return ``"unavailable"`` rather than propagating.

    The trace id format follows OTel's convention: 32 lowercase hex
    chars (128 bits). The OTel SDK exposes it via
    ``SpanContext.trace_id`` as an int; we format with ``:032x``.
    """
    try:
        from opentelemetry import trace as otel_trace_api

        active = otel_trace_api.get_current_span()
        if active is None:
            return TRACE_UNAVAILABLE
        ctx = active.get_span_context()
        if ctx is None or not ctx.is_valid:
            return TRACE_UNAVAILABLE
        return f"{ctx.trace_id:032x}"
    except Exception:
        # FR-017 fail-open: never break callers over OTel errors.
        return TRACE_UNAVAILABLE


__all__ = [
    "TRACE_UNAVAILABLE",
    "TracingConfig",
    "extract_trace_id_from_span_or_unavailable",
    "finish_span_with_exception",
    "get_in_memory_exporter",
    "get_tracer",
    "init_tracing",
    "record_llm_span_attributes",
    "shutdown_tracing",
    "span",
    "traced_node",
    "traced_tool",
]
