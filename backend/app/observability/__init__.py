"""OpenTelemetry tracing library (feature 029 US1).

Self-contained library (Constitution Principle I: Library-First). No FastAPI /
DB direct dependency — only `opentelemetry-*` and stdlib. FastAPI lifespan
calls `init_tracing()`; tests can use `TracingConfig(exporter="in_memory")` to
collect spans via `InMemorySpanExporter`.

US1 scope:
- Single distributed trace per agent invocation
- Graph node spans (entry/exit) with state delta summary
- LLM call child spans (model, tokens, latency, cache status)
- Tool call child spans (tool name, args summary, duration)
- OTLP HTTP exporter (configurable endpoint)
- Fail-open: export failure never blocks agent execution (FR-017)
- Local dev: console exporter when no OTLP endpoint configured (FR-012)
- Backward compat: existing request_id ContextVar retained (FR-008)
- structlog processor adds trace_id + span_id to log events (FR-013)

⏳ Deferred to US2/US3/US4:
- US2 cross-process propagation (HTTP→WS→ARQ) — needs middleware + WS handler + ARQ worker changes
- US3 sampling (default 100%, configurable later)
- US4 prometheus exemplars — structlog trace_id is the foundation
- PII redaction — basic args_summary truncation in `@traced_tool`; complete redaction ⏳
- Local trace viewer UI — console exporter suffices for dev
- 026 trace integration — 029 OTel is an independent layer
- 5 graph full integration — interview + error_coach done; resume_optimize / ability_diagnose / general_coach ⏳
"""
from app.observability.tracing import (
    TracingConfig,
    finish_span_with_exception,
    get_in_memory_exporter,
    get_tracer,
    init_tracing,
    record_llm_span_attributes,
    shutdown_tracing,
    span,
    traced_node,
    traced_tool,
)

__all__ = [
    "TracingConfig",
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
