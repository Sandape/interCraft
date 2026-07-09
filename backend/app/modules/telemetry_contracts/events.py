"""Event and metric snapshot schema definitions for REQ-033.

Self-contained dataclasses (no Pydantic, no LangSmith client) that represent
the canonical shape of:

- ``ProductEvent`` — a single product funnel / lifecycle event
  (e.g. ``resume.diagnosis_completed``).
- ``AIInvocationSummary`` — the summary of one logical AI call (graph,
  node, model, tokens, latency, cache hit, error).
- ``MetricSnapshot`` — a dashboard-ready metric row (numerator / denominator
  / value / dimensions / freshness).

These are the *contract* used by REQ-033 Sub-batch 2+ when events are emitted
from product code. The contract is intentionally JSON-safe (no ORM, no async
clients) so it can be exercised in pure unit tests without DB / Redis.

The shape is informed by ``specs/033-eval-pm-dashboard/contracts/event-metric-schema.md``
but uses Python dataclass idioms (snake_case fields) instead of the JSON
schema's camelCase keys. ``event_to_dict`` / ``dict_to_event`` translate
between them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

# ---------------------------------------------------------------------------
# ProductEvent
# ---------------------------------------------------------------------------


@dataclass
class ProductEvent:
    """A product lifecycle event (e.g. ``resume.created``).

    ``event_id`` is auto-generated on construction so callers cannot
    accidentally forget to set it. ``properties`` is a free-form dict
    for event-specific payload — keys are conventionally dotted
    (e.g. ``template.id``) but no schema is enforced here; that is the
    caller's responsibility.
    """

    name: str
    occurred_at: datetime
    properties: dict[str, Any] = field(default_factory=dict)
    event_id: UUID = field(default_factory=uuid4)
    user_id: UUID | None = None
    environment: str = "unknown"
    release_stage: str = "UNKNOWN"
    app_version: str = "unknown"
    feature_area: str = "unknown"
    privacy_class: str = "PUBLIC_METADATA"
    redaction_status: str = "NOT_REQUIRED"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict representation.

        ``UUID`` -> str, ``datetime`` -> ISO 8601 string.
        """
        d = asdict(self)
        d["event_id"] = str(self.event_id)
        d["user_id"] = str(self.user_id) if self.user_id is not None else None
        d["occurred_at"] = self.occurred_at.isoformat()
        return d


def event_to_dict(event: ProductEvent) -> dict[str, Any]:
    """Module-level alias for ``ProductEvent.to_dict()``."""
    return event.to_dict()


def dict_to_event(data: dict[str, Any]) -> ProductEvent:
    """Re-hydrate a ``ProductEvent`` from its dict form.

    Inverse of ``event_to_dict``. Unknown keys in ``properties`` are
    preserved as-is.
    """
    return ProductEvent(
        name=data["name"],
        occurred_at=datetime.fromisoformat(data["occurred_at"]),
        properties=dict(data.get("properties") or {}),
        event_id=UUID(data["event_id"]) if data.get("event_id") else uuid4(),
        user_id=UUID(data["user_id"]) if data.get("user_id") else None,
        environment=data.get("environment", "unknown"),
        release_stage=data.get("release_stage", "UNKNOWN"),
        app_version=data.get("app_version", "unknown"),
        feature_area=data.get("feature_area", "unknown"),
        privacy_class=data.get("privacy_class", "PUBLIC_METADATA"),
        redaction_status=data.get("redaction_status", "NOT_REQUIRED"),
    )


# ---------------------------------------------------------------------------
# AIInvocationSummary
# ---------------------------------------------------------------------------


@dataclass
class AIInvocationSummary:
    """Summary of one logical AI call.

    One LLM HTTP round-trip or one graph node invocation maps to one
    ``AIInvocationSummary``. Token counts and latency are required so
    PM dashboard panels (cost / latency / cache hit rate) can aggregate
    directly without going back to OTel.
    """

    invocation_id: UUID
    graph_name: str
    run_id: UUID | None
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cached: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["invocation_id"] = str(self.invocation_id)
        d["run_id"] = str(self.run_id) if self.run_id is not None else None
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AIInvocationSummary:
        return cls(
            invocation_id=UUID(data["invocation_id"]),
            graph_name=data["graph_name"],
            run_id=UUID(data["run_id"]) if data.get("run_id") else None,
            model=data["model"],
            tokens_in=int(data["tokens_in"]),
            tokens_out=int(data["tokens_out"]),
            latency_ms=int(data["latency_ms"]),
            cached=bool(data.get("cached", False)),
            error=data.get("error"),
        )


# ---------------------------------------------------------------------------
# MetricSnapshot
# ---------------------------------------------------------------------------


@dataclass
class MetricSnapshot:
    """A dashboard-ready metric row.

    ``value`` is the precomputed metric value for the period (numerator /
    denominator already applied). ``dimensions`` carries filter dimensions
    (environment, app_version, model, graph, node) — empty dict means
    aggregate (no filter).
    """

    metric_id: str
    name: str
    value: float
    captured_at: datetime
    unit: str = "count"
    dimensions: dict[str, str] = field(default_factory=dict)
    numerator: float | None = None
    denominator: float | None = None
    snapshot_id: UUID = field(default_factory=uuid4)
    source_of_truth: str = "unknown"
    freshness_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["snapshot_id"] = str(self.snapshot_id)
        d["captured_at"] = self.captured_at.isoformat()
        d["freshness_at"] = (
            self.freshness_at.isoformat() if self.freshness_at else None
        )
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricSnapshot:
        return cls(
            metric_id=data["metric_id"],
            name=data["name"],
            value=float(data["value"]),
            captured_at=datetime.fromisoformat(data["captured_at"]),
            unit=data.get("unit", "count"),
            dimensions=dict(data.get("dimensions") or {}),
            numerator=data.get("numerator"),
            denominator=data.get("denominator"),
            snapshot_id=UUID(data["snapshot_id"]) if data.get("snapshot_id") else uuid4(),
            source_of_truth=data.get("source_of_truth", "unknown"),
            freshness_at=(
                datetime.fromisoformat(data["freshness_at"])
                if data.get("freshness_at")
                else None
            ),
        )


__all__ = [
    "AIInvocationSummary",
    "MetricSnapshot",
    "ProductEvent",
    "dict_to_event",
    "event_to_dict",
]
