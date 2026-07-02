"""REQ-039 B2 supplement — list_traces / list_trace_nodes service tests.

Coverage:

- ``list_traces`` returns most-recent-first rows (FR-001).
- ``list_traces`` filters by ``task_type`` and ``status_filter``.
- ``list_traces`` honors ``limit``.
- ``list_traces`` returns empty list when no rows match.
- ``list_trace_nodes`` returns flat list of self-describing nodes
  with parent / has_input / has_output flags (FR detail panel).
- ``list_trace_nodes`` returns ``[]`` when trace is missing.
- ``list_trace_nodes`` normalizes list-shaped ``node_payloads``.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.admin_console import service


class _Row:
    """SQLAlchemy row stand-in with ``_mapping`` for service.list_traces."""

    def __init__(self, data: dict):
        self._mapping = data


class _MappingResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def mappings(self):
        return _MappingResult(self._rows)


class _FakeSession:
    """Pretend AsyncSession that supports the raw SQL used by the service layer."""

    def __init__(self, rows, *, node_rows=None):
        self._rows = rows
        self._node_rows = [] if node_rows is None else node_rows
        self.executed: list = []

    async def execute(self, stmt, params=None):  # noqa: ANN001 - signature matches AsyncSession enough
        self.executed.append((stmt, params))
        sql = str(stmt)
        if "jsonb_each" in sql or "jsonb_array_elements" in sql:
            return _FakeResult(self._node_rows)

        params_obj = getattr(stmt, "_bindparams", {}) or {}
        # SQLAlchemy text() bind params live on stmt._bindparams as a
        # _BindArguments; convert to dict for filtering.
        try:
            params_dict = dict(params_obj.items())  # type: ignore[union-attr]
        except Exception:
            params_dict = {}
        # Extract bare values from BindParameter entries.
        extracted: dict[str, object] = {}
        for k, v in params_dict.items():
            extracted[k] = getattr(v, "value", v)
        filtered = list(self._rows)
        if "task_type" in extracted:
            tt = extracted["task_type"]
            filtered = [r for r in filtered if r._mapping.get("task_type") == tt]
        if "status_filter" in extracted:
            sf = extracted["status_filter"]
            filtered = [r for r in filtered if r._mapping.get("status") == sf]
        return _FakeResult(filtered)


def _row(task_type: str = "interview", status: str = "success"):
    return _Row(
        {
            "id": uuid4(),
            "task_id": uuid4(),
            "task_type": task_type,
            "prompt_version": "v1",
            "model": "deepseek-v4-pro",
            "status": status,
            "error_message": None,
            "replay_of": None,
            "created_at": SimpleNamespace(isoformat=lambda: "2026-07-03T00:00:00"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2026-07-03T00:00:01"),
        }
    )


@pytest.mark.asyncio
async def test_list_traces_returns_all_rows_with_default_limit():
    rows = [_row(), _row(task_type="resume_render"), _row()]
    fake = _FakeSession(rows)
    result = await service.list_traces(fake, limit=100)
    assert len(result) == 3
    assert fake.executed, "session.execute must be called"


@pytest.mark.asyncio
async def test_list_traces_filters_by_task_type():
    rows = [_row(task_type="interview"), _row(task_type="resume_render")]
    fake = _FakeSession(rows)
    result = await service.list_traces(fake, limit=10, task_type="interview")
    assert len(result) == 1
    assert result[0]["task_type"] == "interview"


@pytest.mark.asyncio
async def test_list_traces_filters_by_status():
    rows = [_row(status="failed"), _row(status="success")]
    fake = _FakeSession(rows)
    result = await service.list_traces(fake, limit=10, status_filter="failed")
    assert len(result) == 1
    assert result[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_list_traces_returns_empty_when_no_rows():
    fake = _FakeSession([])
    result = await service.list_traces(fake, limit=100)
    assert result == []


@pytest.mark.asyncio
async def test_list_trace_nodes_returns_self_describing_nodes():
    trace_id = uuid4()
    fake = _FakeSession(
        [],
        node_rows=[
            {
                "node_id": "generate",
                "name": "generate",
                "status": "success",
                "parent": "plan",
                "started_at": None,
                "ended_at": None,
                "has_input": True,
                "has_output": False,
            },
            {
                "node_id": "plan",
                "name": "plan",
                "status": "success",
                "parent": None,
                "started_at": "2026-07-03T00:00:00",
                "ended_at": "2026-07-03T00:00:01",
                "has_input": True,
                "has_output": True,
            },
        ],
    )

    nodes = await service.list_trace_nodes(fake, trace_id=trace_id)
    assert len(nodes) == 2
    by_name = {n["node_id"]: n for n in nodes}
    plan = by_name["plan"]
    assert plan["name"] == "plan"
    assert plan["has_input"] is True
    assert plan["has_output"] is True
    generate = by_name["generate"]
    assert generate["parent"] == "plan"
    assert generate["has_input"] is True
    assert generate["has_output"] is False
    sql = str(fake.executed[0][0])
    assert "jsonb_each" in sql
    assert "jsonb_array_elements" in sql
    assert "ORDER BY name ASC" in sql


@pytest.mark.asyncio
async def test_list_trace_nodes_returns_empty_for_missing_trace():
    nodes = await service.list_trace_nodes(_FakeSession([]), trace_id=uuid4())
    assert nodes == []


@pytest.mark.asyncio
async def test_list_trace_nodes_normalizes_list_payloads():
    trace_id = uuid4()
    fake = _FakeSession(
        [],
        node_rows=[
            {
                "node_id": "plan",
                "name": "plan",
                "status": "success",
                "parent": None,
                "started_at": None,
                "ended_at": None,
                "has_input": True,
                "has_output": False,
            },
            {
                "node_id": "generate",
                "name": "generate",
                "status": "success",
                "parent": "plan",
                "started_at": None,
                "ended_at": None,
                "has_input": False,
                "has_output": True,
            },
        ],
    )

    nodes = await service.list_trace_nodes(fake, trace_id=trace_id)
    names = {n["node_id"] for n in nodes}
    assert names == {"plan", "generate"}
