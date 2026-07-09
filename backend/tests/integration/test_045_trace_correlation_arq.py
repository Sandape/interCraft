from __future__ import annotations

from app.core.redis import build_arq_trace_metadata
from app.observability.tracing import TraceContext
from app.workers.main import bind_arq_trace_context


def test_arq_enqueue_metadata_contains_traceparent_and_run_id() -> None:
    meta = build_arq_trace_metadata(TraceContext(run_id="run-arq", trace_id="3" * 32, span_id="4" * 16))

    assert meta["run_id"] == "run-arq"
    assert meta["trace_id"] == "3" * 32
    assert meta["traceparent"] == f"00-{'3' * 32}-{'4' * 16}-01"


def test_arq_worker_binds_trace_context_from_metadata() -> None:
    ctx = bind_arq_trace_context(
        {
            "job_id": "job-1",
            "trace_ctx": {
                "run_id": "run-arq",
                "trace_id": "3" * 32,
                "span_id": "4" * 16,
            },
        }
    )

    assert ctx.run_id == "run-arq"
    assert ctx.trace_id == "3" * 32
