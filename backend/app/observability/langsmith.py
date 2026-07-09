"""REQ-043 US-1 FR-002 — LangSmith trace exporter.

Runs **in parallel** with the existing OTel exporter (``tracing.py``) —
LangSmith is opt-in via ``LANGSMITH_API_KEY``. When the key is empty,
the exporter is a no-op (no network calls, no error logs).

OpenDeepResearch reference: ``deep_researcher.py:85`` uses
``tags=["langsmith:nostream"]``. We follow the same pattern — emit
spans as LangSmith ``chain`` runs with ``langsmith:nostream`` tag.

Design contract (per L041-001):
- Independent module (no coupling to ``tracing.py``).
- Uses langsmith-sdk ``Client``; if the SDK is not installed, the
  exporter falls back to a no-op (FR-017 fail-open pattern).
- The ``export(spans)`` entry point takes a list of OTel span-like
  objects with ``.name`` and ``.attributes`` — callers (notably
  ``init_tracing``) hand over the in-memory exporter's spans.
"""
from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger("observability.langsmith")


def _metadata_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (tuple, list)):
        return [_metadata_value(item) for item in value]
    return str(value)


class LangSmithExporter:
    """Send OTel spans to LangSmith alongside the local OTel pipeline.

    Args:
        api_key: LangSmith API key. Empty string ⇒ no-op exporter.
        project: LangSmith project name. Defaults to ``intercraft-prod``.

    The exporter never raises on the network path: any HTTP / SDK error
    is logged and the span is silently dropped. This matches the
    fail-open philosophy used by ``tracing.py``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        project: str = "intercraft-prod",
    ) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        # Prefer explicit constructor args, then env, then settings.
        self.api_key: str = (
            api_key
            if api_key is not None
            else settings.langsmith_api_key
            or os.environ.get("LANGSMITH_API_KEY", "")
        )
        self.project: str = project or settings.langsmith_project or "intercraft-prod"
        self._client: Any | None = None
        # Lazy init — only build the langsmith Client on first export, so
        # test code can construct the exporter without hitting the network.
        if self.api_key:
            try:
                from langsmith import Client  # type: ignore[import-not-found]

                self._client = Client(api_key=self.api_key)
                logger.info(
                    "langsmith.exporter.initialized",
                    project=self.project,
                )
            except Exception:
                # LangSmith SDK missing / auth error → no-op
                logger.warning(
                    "langsmith.exporter.init_failed_fail_open",
                    exc_info=True,
                )
                self._client = None

    def export(self, spans: list[Any]) -> None:
        """Send ``spans`` to LangSmith. Each span has ``.name`` + ``.attributes``.

        If ``api_key`` is empty (or the SDK init failed), this is a
        no-op — spans are dropped silently. Each per-span error is
        logged but does not abort the batch.
        """
        self.export_with_policy(spans)

    def export_with_policy(
        self,
        spans: list[Any],
        *,
        export_policy_decision: Any | None = None,
        environment: str = "LOCAL",
        representation_level: str = "REDACTED",
    ) -> None:
        """Send spans to LangSmith after optional destination-policy checks."""

        env = str(environment).upper()
        level = str(representation_level).upper()
        if env == "PRODUCTION" and level == "FULL_CONTENT":
            if export_policy_decision is None:
                logger.warning(
                    "langsmith.exporter.blocked_missing_policy",
                    environment=env,
                    representation_level=level,
                )
                return
            policy_level = str(
                getattr(
                    getattr(export_policy_decision, "representation_level", None),
                    "value",
                    getattr(export_policy_decision, "representation_level", ""),
                )
            ).upper()
            destination = str(
                getattr(
                    getattr(export_policy_decision, "destination", None),
                    "value",
                    getattr(export_policy_decision, "destination", ""),
                )
            ).upper()
            if destination != "LANGSMITH" or policy_level == "BLOCKED":
                logger.warning(
                    "langsmith.exporter.blocked_by_policy",
                    destination=destination,
                    representation_level=policy_level,
                )
                return
        if not self.api_key or self._client is None:
            return  # no-op

        for span in spans:
            try:
                attrs = getattr(span, "attributes", {}) or {}
                inputs = attrs.get("input", {})
                outputs = attrs.get("output", {})
                agent = attrs.get("agent.name", "unknown")
                trace_id = attrs.get("trace.id")
                run_id = attrs.get("run.id")
                metadata = {
                    str(key): _metadata_value(value)
                    for key, value in attrs.items()
                    if value is not None
                }
                metadata["span.name"] = getattr(span, "name", "node.unknown")
                tags = [
                    "langsmith:nostream",
                    f"agent:{agent}",
                ]
                if trace_id:
                    tags.append(f"trace:{trace_id}")
                if run_id:
                    tags.append(f"run:{run_id}")
                self._client.create_run(
                    project_name=self.project,
                    name=getattr(span, "name", "node.unknown"),
                    run_type=(
                        "llm"
                        if str(getattr(span, "name", "")).startswith("llm.")
                        else "chain"
                    ),
                    inputs=inputs if isinstance(inputs, dict) else {"value": inputs},
                    outputs=outputs if isinstance(outputs, dict) else {"value": outputs},
                    tags=tags,
                    extra={"metadata": metadata},
                )
            except Exception:
                # Per-span error: log + continue. Never abort the batch.
                logger.warning(
                    "langsmith.exporter.span_failed",
                    span_name=getattr(span, "name", "unknown"),
                    exc_info=True,
                )


__all__ = ["LangSmithExporter"]
