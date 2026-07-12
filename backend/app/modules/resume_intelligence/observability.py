"""Redacted logging and low-cardinality metric helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prometheus_client import Counter, Histogram

_TEXT_KEYS = {
    "resume",
    "resume_text",
    "jd",
    "jd_text",
    "prompt",
    "raw_prompt",
    "raw_model_output",
    "comment",
    "text",
    "markdown",
}

resume_intelligence_events_total = Counter(
    "resume_intelligence_events_total",
    "REQ-059 metadata-only events.",
    ["operation", "status", "category"],
)
resume_intelligence_duration_seconds = Histogram(
    "resume_intelligence_duration_seconds",
    "REQ-059 operation duration.",
    ["operation", "status"],
)


@dataclass(frozen=True)
class CorrelationIds:
    request_id: str | None = None
    run_id: str | None = None
    analysis_id: str | None = None
    trace_id: str | None = None

    def as_log_fields(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "request_id": self.request_id,
                "run_id": self.run_id,
                "analysis_id": self.analysis_id,
                "trace_id": self.trace_id,
            }.items()
            if value
        }


def redact_value(key: str, value: Any) -> Any:
    if key.casefold() in _TEXT_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return redacted_fields(value)
    if isinstance(value, list):
        return [redact_value(key, item) for item in value[:20]]
    return value


def redacted_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: redact_value(key, value) for key, value in fields.items()}


def log_event(logger: Any, event: str, *, ids: CorrelationIds | None = None, **fields: Any) -> None:
    payload = redacted_fields(fields)
    if ids:
        payload.update(ids.as_log_fields())
    logger.info(event, **payload)


def record_event_metric(*, operation: str, status: str, category: str = "none") -> None:
    resume_intelligence_events_total.labels(
        operation=_low_cardinality(operation),
        status=_low_cardinality(status),
        category=_low_cardinality(category),
    ).inc()


def observe_duration(*, operation: str, status: str, seconds: float) -> None:
    resume_intelligence_duration_seconds.labels(
        operation=_low_cardinality(operation),
        status=_low_cardinality(status),
    ).observe(max(0.0, float(seconds)))


def _low_cardinality(value: str) -> str:
    value = str(value or "unknown")
    allowed = {
        "derive",
        "analyze",
        "suggestions",
        "feedback",
        "queued",
        "running",
        "complete",
        "succeeded",
        "partial",
        "partial_success",
        "failed",
        "cancelled",
        "none",
        "validation",
        "provider",
        "idempotency",
        "conflict",
    }
    return value if value in allowed else "other"


__all__ = [
    "CorrelationIds",
    "log_event",
    "observe_duration",
    "record_event_metric",
    "redacted_fields",
]
