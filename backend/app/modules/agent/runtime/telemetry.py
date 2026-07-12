"""Allowlisted Agent events, bounded metric labels and safe trace attributes."""

from __future__ import annotations

import hashlib
import hmac
import re
from contextlib import contextmanager
from typing import Any, Iterator

from app.observability.tracing import span


class TelemetryContractError(ValueError):
    pass


COMMON_FIELDS = frozenset(
    {
        "event",
        "correlation_id",
        "trace_id",
        "message_id",
        "task_id",
        "tool_call_id",
        "delivery_id",
        "user_ref",
        "consumer_owner_ref",
        "fencing_token",
        "binding_epoch",
        "claim_generation",
    }
)

_EVENT_SPEC: dict[str, frozenset[str]] = {
    "wechat.consumer.status": frozenset({"state", "enabled", "owner_ref", "lease_until", "reason"}),
    "wechat.poll.persisted": frozenset({"batch_id", "item_count", "quarantined_count"}),
    "wechat.message.received": frozenset({"external_id_hash", "duplicate"}),
    "wechat.identity.resolved": frozenset({"binding_status"}),
    "agent.task.transition": frozenset({"from_status", "to_status", "stage", "reason"}),
    "agent.llm.completed": frozenset(
        {"model", "prompt_version", "latency_ms", "tokens", "status", "retry_count"}
    ),
    "agent.tool.proposed": frozenset({"tool", "version", "args_hash", "confirmation"}),
    "agent.tool.completed": frozenset(
        {"tool", "status", "committed", "resource_type", "latency_ms", "error_category"}
    ),
    "agent.db.committed": frozenset({"operation", "resource_type", "resource_id", "duration_ms"}),
    "wechat.delivery.completed": frozenset({"segment", "attempt", "status", "provider_code"}),
    "wechat.delivery.unknown": frozenset({"segment", "attempt", "reconciliation_mode"}),
    "agent.run.completed": frozenset({"status", "duration_ms", "terminal_reason"}),
    "agent.dev.message.received": frozenset({"channel"}),
    "agent.dev.message.completed": frozenset({"channel"}),
}

EVENT_FIELDS: dict[str, frozenset[str]] = {
    name: COMMON_FIELDS | fields for name, fields in _EVENT_SPEC.items()
}

EVENT_SEQUENCE = (
    "wechat.message.received",
    "wechat.identity.resolved",
    "agent.llm.completed",
    "agent.tool.proposed",
    "agent.tool.completed",
    "agent.db.committed",
    "agent.run.completed",
    "wechat.delivery.completed",
)

AGENT_METRIC_LABELS: dict[str, tuple[str, ...]] = {
    "wechat_consumer_state": ("state",),
    "wechat_consumer_lease_acquire_total": ("outcome",),
    "wechat_consumer_takeover_total": ("outcome",),
    "wechat_inbound_total": ("outcome",),
    "wechat_inbound_processing_seconds": (),
    "wechat_inbound_duplicate_total": (),
    "wechat_inbound_quarantined_total": ("reason",),
    "wechat_queue_depth": ("direction", "state"),
    "agent_task_total": ("kind", "outcome"),
    "agent_task_duration_seconds": ("kind", "outcome"),
    "agent_tool_calls_total": ("tool", "outcome"),
    "agent_tool_duration_seconds": ("tool",),
    "agent_retry_total": ("layer", "category"),
    "wechat_delivery_total": ("outcome",),
    "agent_stale_claim_rejected_total": ("layer",),
    "agent_binding_epoch_rejected_total": ("layer",),
}

_GAUGE_METRICS = frozenset({"wechat_consumer_state", "wechat_queue_depth"})
_HISTOGRAM_METRICS = frozenset(
    {
        "wechat_inbound_processing_seconds",
        "agent_task_duration_seconds",
        "agent_tool_duration_seconds",
    }
)

_FORBIDDEN_KEYS = frozenset(
    {
        "password",
        "token",
        "cookie",
        "authorization",
        "raw_message",
        "message_content",
        "prompt",
        "system_prompt",
        "reasoning_content",
        "tool_args",
        "tool_result",
        "resume_body",
        "jd_text",
        "provider_body",
    }
)
_SECRET_VALUE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|\bsk-[a-z0-9_-]+|password\s*=|cookie\s*=|api[_-]?key\s*=)"
)

_METRICS: dict[str, Any] = {}
try:
    from prometheus_client import Counter, Gauge, Histogram

    for _metric_name, _label_names in AGENT_METRIC_LABELS.items():
        if _metric_name in _GAUGE_METRICS:
            _factory = Gauge
        elif _metric_name in _HISTOGRAM_METRICS:
            _factory = Histogram
        else:
            _factory = Counter
        _METRICS[_metric_name] = _factory(
            _metric_name,
            f"REQ-060 {_metric_name}",
            _label_names,
        )
except (ImportError, ValueError):
    # Import remains safe in stripped test/runtime environments and when a
    # process reloads modules under an existing Prometheus registry.
    _METRICS = {}


def privacy_ref(value: str, *, salt: str) -> str:
    return hmac.new(salt.encode(), value.encode(), hashlib.sha256).hexdigest()[:24]


def _safe_value(value: Any) -> Any:
    if isinstance(value, str):
        if _SECRET_VALUE.search(value):
            return "[REDACTED]"
        return value[:500]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)[:200]


def build_event(event: str, **fields: Any) -> dict[str, Any]:
    allowed = EVENT_FIELDS.get(event)
    if allowed is None:
        raise TelemetryContractError(f"unknown Agent event: {event}")
    result: dict[str, Any] = {"event": event}
    for key, value in fields.items():
        normalized = key.strip().lower()
        if normalized in _FORBIDDEN_KEYS or key not in allowed:
            continue
        result[key] = _safe_value(value)
    return result


def emit_event(logger: Any, event: str, **fields: Any) -> dict[str, Any]:
    payload = build_event(event, **fields)
    if hasattr(logger, "bind"):
        logger.info(event, **{key: value for key, value in payload.items() if key != "event"})
    else:
        logger.info(event, extra=payload)
    return payload


def record_metric(name: str, *, value: float = 1.0, **labels: str) -> None:
    if not isinstance(value, (int, float)) or value < 0:
        raise TelemetryContractError("metric value must be a non-negative number")
    expected = AGENT_METRIC_LABELS.get(name)
    if expected is None:
        raise TelemetryContractError(f"unknown Agent metric: {name}")
    if set(labels) != set(expected):
        raise TelemetryContractError(f"invalid labels for {name}")
    safe_labels = {key: _safe_value(value) for key, value in labels.items()}
    if any(value == "[REDACTED]" for value in safe_labels.values()):
        raise TelemetryContractError("secret-like metric label rejected")
    metric = _METRICS.get(name)
    if metric is None:
        return
    bound = metric.labels(**safe_labels) if safe_labels else metric
    if name in _HISTOGRAM_METRICS:
        bound.observe(value)
    elif name in _GAUGE_METRICS:
        bound.set(value)
    else:
        bound.inc(value)


def _correlation_link(fields: dict[str, Any]) -> list[Any]:
    """Create a metadata-only link anchor for work crossing queue boundaries."""
    trace_ref = str(fields.get("trace_id") or "")
    correlation_ref = str(fields.get("correlation_id") or "")
    if not trace_ref or trace_ref == "unavailable" or not correlation_ref:
        return []
    try:
        from opentelemetry.trace import Link, SpanContext, TraceFlags

        trace_id = int(hashlib.sha256(trace_ref.encode()).hexdigest()[:32], 16)
        span_id = int(hashlib.sha256(correlation_ref.encode()).hexdigest()[:16], 16)
        context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        return [Link(context, attributes={"link.kind": "durable_correlation"})]
    except Exception:
        return []


@contextmanager
def agent_span(name: str, **fields: Any) -> Iterator[Any]:
    safe = {
        key: _safe_value(value)
        for key, value in fields.items()
        if key.strip().lower() not in _FORBIDDEN_KEYS and key in COMMON_FIELDS
    }
    with span(name, _links=_correlation_link(fields), **safe) as current:
        yield current


__all__ = [
    "AGENT_METRIC_LABELS",
    "EVENT_SEQUENCE",
    "EVENT_FIELDS",
    "TelemetryContractError",
    "agent_span",
    "build_event",
    "emit_event",
    "privacy_ref",
    "record_metric",
]
