"""Metric definition catalog for REQ-033 PM Dashboard V1.

A metric definition is the *contract* a metric snapshot row must satisfy:
``metric_id``, display ``name``, ``unit``, ``aggregation`` strategy
(``sum`` / ``avg`` / ``p50`` / ``p95`` / ``p99``), and the source
``ProductEvent.name`` (or ``AIInvocationSummary`` model+graph) that
feeds it.

The ``MetricCatalog`` is an in-memory registry — PM dashboard panels
look up the definition by id to render metadata + unit + source link,
and to know which aggregation to apply when computing a fresh snapshot.

Six metrics are pre-registered because they back the **Overview panel**
(US1). Sub-batch 2+ will add the rest as PM dashboard panels are built.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Aggregation = Literal["sum", "avg", "p50", "p95", "p99"]


@dataclass(frozen=True)
class MetricDefinition:
    """Contract for one metric snapshot row.

    US9 (T041): adds ``dimensions`` — a list of approved version-aware
    dimension names (e.g. ``["model", "graph", "node", "prompt_fingerprint"]``).
    Optional and defaults to empty tuple so existing callers keep working.
    """

    metric_id: str
    name: str
    description: str
    unit: str
    aggregation: Aggregation
    source_event: str  # ProductEvent.name OR AIInvocationSummary graph_name
    # US9: version-aware dimension list. Empty tuple = no dimensions
    # (rolled up across all data). When set, dashboard panels apply
    # the same filter semantics across all metric_ids that share a
    # dimension name.
    dimensions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.metric_id:
            raise ValueError("metric_id must be non-empty")
        if not self.source_event:
            raise ValueError("source_event must be non-empty")
        if self.unit not in {"count", "percent", "score", "tokens", "ms", "currency"} and not self.unit:
            # soft warning — kept loose so future units can be added without
            # changing this module's signature. Hard-fail only on empty.
            raise ValueError("unit must be non-empty")


@dataclass
class MetricCatalog:
    """In-memory registry of ``MetricDefinition`` rows.

    Thread-unsafe (intentional — registration happens at module import
    time, lookup is read-only thereafter). The catalog is intentionally
    *not* a singleton — tests can construct their own catalog to verify
    registration + lookup without global state.
    """

    _definitions: dict[str, MetricDefinition] = field(default_factory=dict)

    def register(self, definition: MetricDefinition) -> None:
        """Add (or overwrite) a definition. Duplicate ids raise."""
        if definition.metric_id in self._definitions:
            raise ValueError(f"metric_id already registered: {definition.metric_id}")
        self._definitions[definition.metric_id] = definition

    def get(self, metric_id: str) -> MetricDefinition:
        """Return the definition for ``metric_id``. Raises KeyError if missing."""
        return self._definitions[metric_id]

    def try_get(self, metric_id: str) -> MetricDefinition | None:
        """Return the definition or ``None`` if not registered."""
        return self._definitions.get(metric_id)

    def list_all(self) -> list[MetricDefinition]:
        """Return all registered definitions, sorted by ``metric_id`` for stable test assertions."""
        return sorted(self._definitions.values(), key=lambda d: d.metric_id)

    def list_by_source(self, event_name: str) -> list[MetricDefinition]:
        """Return definitions whose ``source_event`` equals ``event_name``."""
        return [d for d in self._definitions.values() if d.source_event == event_name]

    def metric_by_id_with_dimensions(
        self,
        metric_id: str,
        dimensions_filter: dict[str, str] | None = None,
    ) -> MetricDefinition | None:
        """US9 (T041): dimension-aware lookup.

        Returns the ``MetricDefinition`` for ``metric_id`` if all
        ``dimensions_filter`` keys are present in the definition's
        ``dimensions`` tuple. If any required dimension is missing
        from the definition, returns ``None`` — caller is expected
        to fall back to the unfiltered metric.

        The intent is to keep the dashboard filter semantics uniform:
        if a user filters by ``model=deepseek-v4-pro`` and the metric
        has no ``model`` dimension, we don't apply the filter (and
        don't pretend to).

        Returns ``None`` for missing ``metric_id`` (use ``try_get``
        for that, but this method composes the two checks).
        """
        d = self.try_get(metric_id)
        if d is None:
            return None
        if not dimensions_filter:
            return d
        for k in dimensions_filter:
            if k not in d.dimensions:
                return None
        return d


# ---------------------------------------------------------------------------
# Built-in metric definitions (PM Dashboard V1 Overview panel)
# ---------------------------------------------------------------------------


_BUILTIN_DEFINITIONS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        metric_id="pm.resume.created",
        name="Resumes Created",
        description="Count of resume.v2.created_or_uploaded events in the period.",
        unit="count",
        aggregation="sum",
        source_event="resume.created_or_uploaded",
        dimensions=("environment", "app_version", "release_stage"),
    ),
    MetricDefinition(
        metric_id="pm.resume.exported",
        name="Resumes Exported",
        description="Count of resume.v2.exported events (PDF + DOCX combined).",
        unit="count",
        aggregation="sum",
        source_event="resume.exported",
        dimensions=("environment", "app_version", "model"),
    ),
    MetricDefinition(
        metric_id="pm.interview.completed",
        name="Mock Interviews Completed",
        description="Count of interview.completed events in the period.",
        unit="count",
        aggregation="sum",
        source_event="interview.completed",
        dimensions=(
            "environment",
            "app_version",
            "prompt_fingerprint",
            "rubric_version",
            "model",
        ),
    ),
    MetricDefinition(
        metric_id="pm.interview.avg_score",
        name="Average Interview Score",
        description="Average overall_score across interview.completed events with non-null score.",
        unit="score",
        aggregation="avg",
        source_event="interview.completed",
        dimensions=(
            "environment",
            "app_version",
            "prompt_fingerprint",
            "rubric_version",
            "model",
        ),
    ),
    MetricDefinition(
        metric_id="pm.ai.token_consumed",
        name="LLM Tokens Consumed",
        description="Sum of tokens_in + tokens_out across all AI invocation summaries.",
        unit="tokens",
        aggregation="sum",
        source_event="ai.call_completed",
        dimensions=("environment", "model", "graph", "node", "prompt_fingerprint"),
    ),
    MetricDefinition(
        metric_id="pm.ai.cache_hit_rate",
        name="AI Cache Hit Rate",
        description="Fraction of AI invocations with cached=True (0..1).",
        unit="percent",
        aggregation="avg",
        source_event="ai.call_completed",
        dimensions=("environment", "model", "graph", "node", "prompt_fingerprint"),
    ),
)


def build_default_catalog() -> MetricCatalog:
    """Return a fresh catalog populated with the six built-in metrics.

    Always returns a new instance so tests are isolated from each other
    (no module-level singleton state).
    """
    cat = MetricCatalog()
    for d in _BUILTIN_DEFINITIONS:
        cat.register(d)
    return cat


__all__ = [
    "Aggregation",
    "MetricCatalog",
    "MetricDefinition",
    "build_default_catalog",
]
