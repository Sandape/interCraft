"""Prometheus metrics for WeChat conversational agent (REQ-054 FR-019)."""

from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram

    intent_parse_total = Counter(
        "wechat_intent_parse_total",
        "Intent parse outcomes",
        labelnames=("intent", "outcome"),  # outcome: ok | low_confidence | error | rejected
    )

    intent_parse_latency_seconds = Histogram(
        "wechat_intent_parse_latency_seconds",
        "Intent parse latency including retries",
        buckets=(0.5, 1, 2, 5, 10, 15, 30),
    )

    tool_calls_total = Counter(
        "wechat_tool_calls_total",
        "Tool prepare/execute outcomes",
        labelnames=("tool", "phase", "outcome"),  # phase: prepare|execute
    )

    confirmation_total = Counter(
        "wechat_confirmation_total",
        "Write confirmation outcomes",
        labelnames=("action", "outcome"),  # confirm|cancel
    )

    interview_adapter_total = Counter(
        "wechat_interview_adapter_total",
        "Interview adapter actions",
        labelnames=("action", "outcome"),
    )

    orchestrator_handle_latency_seconds = Histogram(
        "wechat_orchestrator_handle_latency_seconds",
        "End-to-end ConversationOrchestrator.handle latency",
        buckets=(1, 2, 5, 10, 15, 30, 60),
    )

except Exception:  # pragma: no cover — prometheus unavailable
    class _NoOp:
        def labels(self, *args, **kwargs):  # noqa: ANN001, ANN003
            return self

        def inc(self, *args, **kwargs) -> None:  # noqa: ANN001, ANN003
            return None

        def observe(self, *args, **kwargs) -> None:  # noqa: ANN001, ANN003
            return None

    intent_parse_total = _NoOp()  # type: ignore[assignment]
    intent_parse_latency_seconds = _NoOp()  # type: ignore[assignment]
    tool_calls_total = _NoOp()  # type: ignore[assignment]
    confirmation_total = _NoOp()  # type: ignore[assignment]
    interview_adapter_total = _NoOp()  # type: ignore[assignment]
    orchestrator_handle_latency_seconds = _NoOp()  # type: ignore[assignment]


__all__ = [
    "intent_parse_total",
    "intent_parse_latency_seconds",
    "tool_calls_total",
    "confirmation_total",
    "interview_adapter_total",
    "orchestrator_handle_latency_seconds",
]
