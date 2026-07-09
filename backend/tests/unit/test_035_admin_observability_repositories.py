"""REQ-051 — admin console repository tests (simplified)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.agent_observability import repository as obs_repo
from app.modules.agent_observability.models import (
    LLMCallRecord,
    ObservabilityPayload,
    ObservabilitySpan,
    ObservabilityTrace,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_observability_repository_searches_trace_rows_with_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    trace = SimpleNamespace(
        trace_id="trace_search_1",
        business_event_id="business_1",
        environment="local",
        feature_area="interview",
        agent_name="interview_supervisor",
        status="error",
        started_at=now,
        ended_at=now + timedelta(milliseconds=250),
        version_context={"source_revision": "rev-1"},
    )
    spans = [
        SimpleNamespace(
            span_id="span_root",
            parent_span_id=None,
            span_kind="agent_run",
            node_name="interview_supervisor",
            status="error",
        ),
        SimpleNamespace(
            span_id="span_score",
            parent_span_id="span_root",
            span_kind="node",
            node_name="score",
            status="error",
        ),
    ]
    llm_calls = [
        SimpleNamespace(
            llm_call_id="llm_1",
            prompt_tokens=100,
            completion_tokens=25,
            estimated_cost=Decimal("0.0125"),
        )
    ]
    eval_case = SimpleNamespace(
        case_result_id="case_1",
        case_id="golden_1",
        verdict="failed",
        badcase_id="badcase_1",
    )

    async def fake_list_traces(_session, *, user_id=None, status=None, limit=50):
        assert status == "error"
        return [trace]

    async def fake_spans(_session, *, trace_id: str):
        assert trace_id == trace.trace_id
        return spans

    async def fake_llm_calls(_session, *, trace_id: str):
        assert trace_id == trace.trace_id
        return llm_calls

    async def fake_eval_case(_session, *, trace_id: str):
        assert trace_id == trace.trace_id
        return eval_case

    monkeypatch.setattr(obs_repo, "list_traces", fake_list_traces)
    monkeypatch.setattr(obs_repo, "list_spans_for_trace", fake_spans)
    monkeypatch.setattr(obs_repo, "list_llm_calls_for_trace", fake_llm_calls)
    monkeypatch.setattr(obs_repo, "get_eval_case_for_trace", fake_eval_case)

    rows, next_cursor = await obs_repo.search_trace_rows(
        object(),
        q="score",
        status="error",
        eval_status="failed",
        badcase_status="OPEN",
        limit=10,
    )

    assert next_cursor is None
    assert rows[0]["trace_id"] == "trace_search_1"
    assert rows[0]["total_tokens"] == 125
    assert rows[0]["estimated_cost"] == 0.0125
    assert rows[0]["eval_status"] == "failed"
    assert rows[0]["badcase_status"] == "OPEN"
    assert rows[0]["next_node"] == "score"


@pytest.mark.asyncio
async def test_observability_repository_builds_trace_hierarchy(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    trace = SimpleNamespace(
        trace_id="trace_hierarchy_1",
        business_event_id="business_1",
        environment="local",
        feature_area="resume",
        agent_name="resume_agent",
        status="success",
        started_at=now,
        ended_at=now + timedelta(milliseconds=300),
        version_context={},
    )
    spans = [
        SimpleNamespace(
            span_id="span_root",
            parent_span_id=None,
            span_kind="agent_run",
            node_name="resume_agent",
            status="success",
        ),
        SimpleNamespace(
            span_id="span_node",
            parent_span_id="span_root",
            span_kind="node",
            node_name="diagnose",
            status="success",
        ),
    ]
    eval_case = SimpleNamespace(
        case_result_id="case_1",
        case_id="golden_1",
        verdict="passed",
        badcase_id=None,
    )

    async def fake_get_trace(_session, *, trace_id: str):
        assert trace_id == trace.trace_id
        return trace

    async def fake_spans(_session, *, trace_id: str):
        assert trace_id == trace.trace_id
        return spans

    async def fake_llm_calls(_session, *, trace_id: str):
        assert trace_id == trace.trace_id
        return []

    async def fake_eval_case(_session, *, trace_id: str):
        assert trace_id == trace.trace_id
        return eval_case

    monkeypatch.setattr(obs_repo, "get_trace", fake_get_trace)
    monkeypatch.setattr(obs_repo, "list_spans_for_trace", fake_spans)
    monkeypatch.setattr(obs_repo, "list_llm_calls_for_trace", fake_llm_calls)
    monkeypatch.setattr(obs_repo, "get_eval_case_for_trace", fake_eval_case)

    hierarchy = await obs_repo.get_trace_hierarchy(object(), trace_id=trace.trace_id)

    assert hierarchy is not None
    assert hierarchy["trace"]["trace_id"] == trace.trace_id
    assert hierarchy["hierarchy"]["root_span_id"] == "span_root"
    assert hierarchy["hierarchy"]["node_path"] == ["diagnose"]
    assert hierarchy["links"]["eval_case_ids"] == ["case_1"]
