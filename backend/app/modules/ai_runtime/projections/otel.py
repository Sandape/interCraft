"""OTel projection destination helpers (REQ-061 T159).

Re-projects durable runtime facts into OTel destination records.
Never calls providers/tools/metering; never re-executes AI work.
Parent propagation: HTTP → worker → engine → attempt via correlation ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

# Bounded metric label keys — cardinality must stay finite.
BOUNDED_METRIC_LABELS: frozenset[str] = frozenset(
    {
        "capability",
        "action",
        "status",
        "service_tier",
        "failure_category",
        "destination",
    }
)


@dataclass(frozen=True)
class OTelDestinationStatus:
    destination: str = "otel"
    backlog_count: int = 0
    last_success_at: datetime | None = None
    last_confirmed_sequence: str | None = None
    blocked_count: int = 0
    available: bool = True


@dataclass(frozen=True)
class PropagatedContext:
    root_task_id: str
    execution_id: str | None
    attempt_id: str | None
    correlation_id: str
    parent_span_id: str | None = None


def build_propagated_context(
    *,
    root_task_id: UUID | str,
    correlation_id: str,
    execution_id: UUID | str | None = None,
    attempt_id: UUID | str | None = None,
    parent_span_id: str | None = None,
) -> PropagatedContext:
    return PropagatedContext(
        root_task_id=str(root_task_id),
        execution_id=str(execution_id) if execution_id else None,
        attempt_id=str(attempt_id) if attempt_id else None,
        correlation_id=correlation_id,
        parent_span_id=parent_span_id,
    )


def filter_metric_labels(labels: dict[str, Any]) -> dict[str, str]:
    """Drop unbounded labels; coerce remaining values to short strings."""
    out: dict[str, str] = {}
    for key, value in labels.items():
        if key not in BOUNDED_METRIC_LABELS:
            continue
        text = str(value)[:64]
        out[key] = text
    return out


def project_event_representation(
    *,
    source_event_id: str,
    root_task_id: str,
    sequence: int,
    event_type: str,
    context: PropagatedContext | None = None,
) -> dict[str, Any]:
    """Build a persisted OTel projection representation (metadata only)."""
    return {
        "destination": "otel",
        "source_event_id": source_event_id,
        "root_task_id": root_task_id,
        "sequence": sequence,
        "event_type": event_type,
        "representation": "metadata",
        "context": {
            "correlation_id": context.correlation_id if context else None,
            "execution_id": context.execution_id if context else None,
            "attempt_id": context.attempt_id if context else None,
            "parent_span_id": context.parent_span_id if context else None,
        },
        "projected_at": datetime.now(UTC).isoformat(),
        "provider_calls_created": 0,
        "tool_calls_created": 0,
    }


def destination_status_from_counts(
    *,
    backlog: int,
    blocked: int,
    last_success_at: datetime | None,
    last_confirmed_sequence: str | None,
) -> OTelDestinationStatus:
    return OTelDestinationStatus(
        backlog_count=backlog,
        blocked_count=blocked,
        last_success_at=last_success_at,
        last_confirmed_sequence=last_confirmed_sequence,
        available=True,
    )


__all__ = [
    "BOUNDED_METRIC_LABELS",
    "OTelDestinationStatus",
    "PropagatedContext",
    "build_propagated_context",
    "destination_status_from_counts",
    "filter_metric_labels",
    "project_event_representation",
]
