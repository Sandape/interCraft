from __future__ import annotations

import pytest

from app.agents.base import BaseAgent
from app.agents.checkpointer import retry_graph_op
from app.agents.llm_client import _build_ai_invocation_summary
from app.observability.tracing import (
    TRACE_UNAVAILABLE,
    TracingConfig,
    _reset_tracing_for_test,
    init_tracing,
    record_req035_capture_event,
    span,
)


class _GraphWithLLMSummary:
    async def ainvoke(self, state, config=None):
        summary = _build_ai_invocation_summary(
            invocation_id="invoke_req_035",
            graph="integration_graph",
            node="score",
            model="deepseek-v4-pro",
            system_prompt="",
            tool_defs=None,
            messages=[{"role": "user", "content": "redacted"}],
            prompt_tokens=11,
            completion_tokens=7,
            latency_ms=42,
            retry_count=0,
            status="SUCCESS",
        )
        return {"summary_trace_id": summary.trace_id, "thread_id": state["thread_id"]}


class _AgentWithLLMSummary(BaseAgent):
    def build_graph(self):
        return _GraphWithLLMSummary()


@pytest.fixture(autouse=True)
def _fresh_tracing():
    _reset_tracing_for_test()
    init_tracing(TracingConfig(exporter="in_memory", service_name="req035-test"))
    yield
    _reset_tracing_for_test()


@pytest.mark.asyncio
async def test_agent_capture_chain_inherits_active_trace_context(monkeypatch: pytest.MonkeyPatch) -> None:
    records: list[dict[str, object]] = []

    def capture(**kwargs):
        record = record_req035_capture_event(**kwargs)
        records.append(record)
        return record

    monkeypatch.setattr("app.agents.base.record_req035_capture_event", capture)

    result = await _AgentWithLLMSummary().ainvoke(
        {"thread_id": "thread_req_035", "user_id": "user_req_035"}
    )

    assert result["summary_trace_id"] != TRACE_UNAVAILABLE
    assert records[0]["target_type"] == "agent_run"
    assert records[0]["target_id"] == "thread_req_035"
    assert records[0]["status"] == "success"
    assert records[0]["trace_id"] == result["summary_trace_id"]
    assert records[0]["span_id"] != TRACE_UNAVAILABLE


@pytest.mark.asyncio
async def test_checkpointer_capture_chain_inherits_resume_trace_context(monkeypatch: pytest.MonkeyPatch) -> None:
    records: list[dict[str, object]] = []

    class Graph:
        async def aget_state(self, config):
            return {"ok": True, "thread_id": config["configurable"]["thread_id"]}

    async def build_graph():
        return Graph()

    def capture(**kwargs):
        record = record_req035_capture_event(**kwargs)
        records.append(record)
        return record

    monkeypatch.setattr("app.agents.checkpointer.record_req035_capture_event", capture)

    with span("checkpointer.resume", **{"thread_id": "thread_req_035"}):
        result = await retry_graph_op(
            build_graph,
            {"configurable": {"thread_id": "thread_req_035"}},
            "aget_state",
            max_retries=0,
        )

    assert result == {"ok": True, "thread_id": "thread_req_035"}
    assert records[0]["target_type"] == "checkpointer_graph_op"
    assert records[0]["target_id"] == "thread_req_035"
    assert records[0]["status"] == "success"
    assert records[0]["trace_id"] != TRACE_UNAVAILABLE
    assert records[0]["span_id"] != TRACE_UNAVAILABLE
