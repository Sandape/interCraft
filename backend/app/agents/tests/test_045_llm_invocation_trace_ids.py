from __future__ import annotations

import pytest

from app.agents.llm_client import _build_ai_invocation_summary
from app.agents.llm_client_mock import MockLLMClient
from app.observability.tracing import (
    TracingConfig,
    bind_trace_context,
    clear_trace_context,
    get_in_memory_exporter,
    init_tracing,
)
from app.observability.tracing import _reset_tracing_for_test


def test_ai_invocation_summary_preserves_trace_and_run_ids() -> None:
    summary = _build_ai_invocation_summary(
        invocation_id="00000000-0000-0000-0000-000000000045",
        graph="interview",
        node="score",
        model="mock",
        system_prompt="system",
        tool_defs=[],
        messages=[{"role": "user", "content": "hello"}],
        prompt_tokens=1,
        completion_tokens=2,
        latency_ms=30,
        retry_count=0,
        status="SUCCESS",
        run_id="00000000-0000-0000-0000-000000000046",
        trace_id="5" * 32,
    )

    assert str(summary.run_id) == "00000000-0000-0000-0000-000000000046"
    assert summary.trace_id == "5" * 32


@pytest.mark.asyncio
async def test_mock_llm_emits_testable_span_without_network() -> None:
    _reset_tracing_for_test()
    init_tracing(TracingConfig(exporter="in_memory", service_name="req045-test"))
    bind_trace_context(
        run_id="00000000-0000-0000-0000-000000000047",
        trace_id="6" * 32,
        span_id="7" * 16,
    )

    client = MockLLMClient(hint_contents={"small": "hint"})
    response = await client.invoke(
        messages=[{"role": "user", "content": "Hint level: small"}],
        user_id="user",
        thread_id="thread",
        node_name="error_coach_hint",
    )

    exporter = get_in_memory_exporter()
    assert exporter is not None
    spans = exporter.get_finished_spans()
    assert response["content"] == "hint"
    assert [item.name for item in spans] == ["llm.mock.error_coach_hint"]
    attrs = spans[0].attributes
    assert attrs["llm.mock"] is True
    assert attrs["llm.model"] == "mock-llm"
    assert attrs["llm.node"] == "error_coach_hint"
    assert attrs["run.id"] == "00000000-0000-0000-0000-000000000047"
    assert attrs["trace.id"] == "6" * 32

    clear_trace_context()
    _reset_tracing_for_test()
