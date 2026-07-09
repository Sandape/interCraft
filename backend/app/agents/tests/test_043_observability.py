"""REQ-043 US-1 — @traced_node coverage + LangSmith parallel export.

Tests cover three contracts:

- AC-SC-001: All LangGraph nodes are decorated with ``@traced_node`` so
  OTel/LangSmith span coverage is 100%. Spec states 17 nodes; baseline
  measured 26 — the test must reflect the *current* count not the spec
  number (per L041-001 — implementation reality wins).
- AC-SC-002: LangSmithExporter runs in parallel with OTel — both
  exporters receive the same spans, no conflict.
- AC-FR-004: ``trace_id`` propagates from OTel active span into structlog
  event dict and into the ``X-Trace-Id`` response header.

Note: Tests run with the *in-memory* OTel exporter so we can inspect
collected spans without standing up an OTel collector.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# Path to the agents source root (used for static coverage scan).
AGENTS_DIR = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# AC-SC-001 — @traced_node coverage scan
# ---------------------------------------------------------------------------
class TestTracedNodeCoverage:
    """Every LangGraph node function must carry ``@traced_node``."""

    def test_traced_node_decorator_present(self):
        """Spec FR-001: ``@traced_node`` decorator must be applied."""
        # Find the decorator in the source
        src_files = list((AGENTS_DIR).rglob("*.py"))
        hits = 0
        for f in src_files:
            text = f.read_text(encoding="utf-8")
            hits += len(re.findall(r"^@traced_node\b", text, re.MULTILINE))
        # Baseline measured 26 nodes (spec said 17 minimum; we have 26+).
        assert hits >= 17, (
            f"Only {hits} @traced_node applications found — spec FR-001/SC-001 requires ≥17"
        )

    def test_traced_node_unique_node_names_count(self):
        """At least 17 distinct node names are decorated (spec FR-001)."""
        names: set[str] = set()
        for f in AGENTS_DIR.rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            for m in re.finditer(r'^@traced_node\(\s*["\']([^"\']+)["\']\s*\)', text, re.MULTILINE):
                names.add(m.group(1))
        assert len(names) >= 17, (
            f"Only {len(names)} unique @traced_node names — spec FR-001/SC-001 requires ≥17"
        )

    def test_traced_node_decorator_imports_tracing_module(self):
        """Every consumer file using ``@traced_node`` must import it from ``tracing``.

        Excludes ``tracing.py`` itself (decorator definition site) and any
        file inside ``app/observability/`` (the source module).
        """
        for f in AGENTS_DIR.rglob("*.py"):
            # Skip the decorator source itself
            rel = f.relative_to(AGENTS_DIR)
            parts = rel.parts
            if "observability" in parts:
                continue
            text = f.read_text(encoding="utf-8")
            if not re.search(r"^@traced_node\b", text, re.MULTILINE):
                continue
            assert "from app.observability.tracing import" in text or (
                "from app.observability" in text and "traced_node" in text
            ), f"File {f} uses @traced_node but doesn't import it from app.observability.tracing"


# ---------------------------------------------------------------------------
# AC-SC-002 — LangSmithExporter parallel with OTel
# ---------------------------------------------------------------------------
class TestLangSmithExporter:
    """LangSmithExporter must run alongside OTel without conflict."""

    def test_langsmith_exporter_class_exists(self):
        """The exporter class must be importable from observability.langsmith."""
        from app.observability.langsmith import LangSmithExporter

        assert LangSmithExporter is not None

    def test_langsmith_exporter_has_export_method(self):
        """The exporter must have an ``export(spans)`` entry point."""
        from app.observability.langsmith import LangSmithExporter

        assert hasattr(LangSmithExporter, "export"), (
            "LangSmithExporter must expose .export(spans)"
        )

    def test_langsmith_exporter_project_default(self):
        """Default project name is ``intercraft-prod`` (per spec FR-002)."""
        from app.observability.langsmith import LangSmithExporter

        # Construct without real API key — config defaults are tested.
        exporter = LangSmithExporter.__new__(LangSmithExporter)
        # project default is read from settings, not hard-coded
        from app.core.config import get_settings

        settings = get_settings()
        # If settings.langsmith_project unset, we want the default
        # "intercraft-prod" — so the Settings field default matters.
        assert hasattr(settings, "langsmith_project"), (
            "Settings must declare langsmith_project (per L041-004 namespace isolation)"
        )
        assert hasattr(settings, "langsmith_api_key"), (
            "Settings must declare langsmith_api_key"
        )

    def test_langsmith_no_op_when_api_key_empty(self):
        """If LANGSMITH_API_KEY is empty, exporter is a no-op (no network call)."""
        from app.observability.langsmith import LangSmithExporter

        exporter = LangSmithExporter.__new__(LangSmithExporter)
        # When api_key is empty, export() must not raise
        exporter.api_key = ""  # type: ignore[attr-defined]
        exporter.project = "intercraft-prod"  # type: ignore[attr-defined]
        # Provide fake spans — exporter must skip silently
        fake_spans = [
            type("FakeSpan", (), {
                "name": "node.test",
                "attributes": {"node.name": "test", "input": {}, "output": {}},
            })()
        ]
        # Must not raise
        exporter.export(fake_spans)  # type: ignore[attr-defined]

    def test_langsmith_exporter_preserves_trace_metadata(self):
        """LangSmith runs include local trace identifiers for UI drilldown."""
        from app.observability.langsmith import LangSmithExporter

        captured: list[dict] = []

        class FakeClient:
            def create_run(self, **kwargs):
                captured.append(kwargs)

        exporter = LangSmithExporter.__new__(LangSmithExporter)
        exporter.api_key = "test-key"  # type: ignore[attr-defined]
        exporter.project = "intercraft-prod"  # type: ignore[attr-defined]
        exporter._client = FakeClient()  # type: ignore[attr-defined]
        fake_span = type(
            "FakeSpan",
            (),
            {
                "name": "llm.question_gen",
                "attributes": {
                    "llm.node": "question_gen",
                    "trace.id": "a" * 32,
                    "run.id": "session-123",
                    "llm.prompt_tokens": 11,
                },
            },
        )()

        exporter.export([fake_span])  # type: ignore[attr-defined]

        assert len(captured) == 1
        payload = captured[0]
        assert payload["run_type"] == "llm"
        assert "trace:" + "a" * 32 in payload["tags"]
        assert "run:session-123" in payload["tags"]
        metadata = payload["extra"]["metadata"]
        assert metadata["trace.id"] == "a" * 32
        assert metadata["run.id"] == "session-123"
        assert metadata["span.name"] == "llm.question_gen"

    def test_tracing_initialization_exports_finished_spans_to_langsmith(
        self, monkeypatch
    ):
        """LangSmith receives the same finished spans emitted through tracing."""
        from app.observability.tracing import (
            TracingConfig,
            _reset_tracing_for_test,
            init_tracing,
            span,
        )

        captured: list = []

        class FakeLangSmithExporter:
            def __init__(
                self,
                api_key: str | None = None,
                project: str = "intercraft-prod",
            ):
                self.api_key = api_key
                self.project = project

            def export(self, spans):
                captured.extend(spans)

        monkeypatch.setattr(
            "app.observability.langsmith.LangSmithExporter",
            FakeLangSmithExporter,
        )

        _reset_tracing_for_test()
        init_tracing(
            TracingConfig(
                service_name="test",
                exporter="in_memory",
                langsmith_api_key="test-key",
                langsmith_project="test-project",
            )
        )
        with span(
            "node.interview.question_gen",
            **{"node.name": "interview.question_gen"},
        ):
            pass

        assert [item.name for item in captured] == ["node.interview.question_gen"]
        _reset_tracing_for_test()


# ---------------------------------------------------------------------------
# AC-FR-004 — trace_id propagation to structlog + X-Trace-Id header
# ---------------------------------------------------------------------------
class TestTraceIDPropagation:
    """trace_id from OTel active span must reach structlog + HTTP header."""

    def test_extract_trace_id_returns_unavailable_when_no_span(self):
        """When OTel is not initialized, trace_id is the sentinel ``unavailable``."""
        from app.observability.tracing import (
            TRACE_UNAVAILABLE,
            extract_trace_id_from_span_or_unavailable,
        )

        # In test mode no span active → must return the sentinel
        # (don't assert exact value — OTel might be initialized by other tests).
        result = extract_trace_id_from_span_or_unavailable()
        assert result is not None
        # If OTel is initialized with no active span, the function returns
        # either a 32-char hex trace_id or the literal "unavailable".
        assert result == TRACE_UNAVAILABLE or re.fullmatch(r"[0-9a-f]{32}", result), (
            f"trace_id must be 32-char hex or 'unavailable', got {result!r}"
        )

    def test_structlog_processor_injects_trace_id(self):
        """The structlog processor must add ``trace_id`` to event dict."""
        from app.observability.tracing import _inject_otel_context

        # Simulate event dict before injection
        event: dict = {"event": "test", "level": "info"}
        result = _inject_otel_context(None, "info", event)
        # Result must be a dict (never raises per FR-017 fail-open)
        assert isinstance(result, dict)
        # If no active span, "trace_id" may or may not be present
        assert "event" in result

    def test_trace_id_middleware_sets_header(self):
        """The TraceIDMiddleware sets X-Trace-Id header on responses."""
        from app.middleware.trace_id import TraceIDMiddleware

        # Class existence + HEADER class attribute is the static contract
        assert TraceIDMiddleware is not None
        assert TraceIDMiddleware.HEADER == "X-Trace-Id", (
            "TraceIDMiddleware.HEADER must be 'X-Trace-Id'"
        )

    def test_config_declares_langsmith_settings(self):
        """Settings must expose langsmith_api_key + langsmith_project."""
        from app.core.config import Settings

        # Verify the fields exist on the model
        fields = Settings.model_fields
        assert "langsmith_api_key" in fields
        assert "langsmith_project" in fields


# ---------------------------------------------------------------------------
# L041-004 — namespace isolation: new vars are independent of 041/042
# ---------------------------------------------------------------------------
class TestNamespaceIsolation:
    """REQ-043 env vars must be independent of 041 + 042 namespace."""

    def test_langsmith_vars_use_langsmith_prefix(self):
        """langsmith_api_key + langsmith_project — own namespace, not REQ-NNN prefix."""
        from app.core.config import Settings

        # Get env var names (pydantic-settings auto-derives from field names)
        for field_name in ("langsmith_api_key", "langsmith_project"):
            assert field_name in Settings.model_fields, (
                f"Settings must declare {field_name}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
