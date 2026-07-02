"""REQ-039 B2 r2 review fix — nodes must be sorted by name ascending.

Reviewer found that ``service.list_trace_nodes`` returned nodes in dict
insertion order, which depends on the order LangGraph serialized
``node_payloads`` — not a logical ordering. The AC matrix explicitly
requires ``node_name`` ordering.

These tests guard the contract: nodes returned to the frontend must be
sorted by ``name`` ascending, regardless of insertion order. They also
protect the follow-up production fix: ``list_trace_nodes`` must project
only node metadata in SQL instead of fetching the whole ``node_payloads``
JSONB value into Python; a large failed interview trace previously timed
out on ``GET /traces/{id}/nodes``.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.admin_console import service


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _payload(name: str, **extra):
    base = {"name": name, "status": "success"}
    base.update(extra)
    return base


def _metadata_rows(payloads, *, status="success"):
    if isinstance(payloads, list):
        items = []
        for idx, item in enumerate(payloads):
            if not isinstance(item, dict):
                continue
            nid = str(item.get("name") or item.get("node_id") or f"node_{idx}")
            items.append((nid, item))
    else:
        items = [(str(k), v) for k, v in (payloads or {}).items() if isinstance(v, dict)]

    rows = [
        {
            "node_id": nid,
            "name": str(payload.get("name") or nid),
            "status": str(payload.get("status") or status or "unknown"),
            "parent": payload.get("parent"),
            "started_at": payload.get("started_at"),
            "ended_at": payload.get("ended_at"),
            "has_input": "input" in payload,
            "has_output": "output" in payload,
        }
        for nid, payload in items
    ]
    return sorted(rows, key=lambda r: r["name"])


class _FakeMappingResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappingResult(self._rows)


class _FakeSession:
    def __init__(self, *, status="success", node_payloads=None):
        self.status = status
        self.node_payloads = {} if node_payloads is None else node_payloads
        self.executed_sql = None
        self.executed_params = None

    async def execute(self, sql, params):  # noqa: ANN001 - matches AsyncSession enough for test
        self.executed_sql = str(sql)
        self.executed_params = params
        return _FakeResult(_metadata_rows(self.node_payloads, status=self.status))


@pytest.mark.asyncio
async def test_list_trace_nodes_sorts_by_name_ascending():
    """Nodes returned by service.list_trace_nodes must be sorted by `name` ascending."""
    trace_id = uuid4()
    # Deliberately reverse-alphabetical insertion order. Without the sort
    # fix this would come back as c, b, a.
    session = _FakeSession(
        node_payloads={
            "node_c": _payload("c_node"),
            "node_a": _payload("a_node"),
            "node_b": _payload("b_node"),
        }
    )

    nodes = await service.list_trace_nodes(session, trace_id=trace_id)

    names = [n["name"] for n in nodes]
    assert names == ["a_node", "b_node", "c_node"], (
        f"nodes must be sorted by name ascending; got {names}"
    )
    assert "FROM traces" in session.executed_sql
    assert "jsonb_each" in session.executed_sql
    assert "jsonb_array_elements" in session.executed_sql
    assert "ORDER BY name ASC" in session.executed_sql
    assert session.executed_params == {"trace_id": trace_id}


@pytest.mark.asyncio
async def test_list_trace_nodes_stable_order_with_mixed_keys():
    """When payloads include parent / input / output variants, sort still wins."""
    trace_id = uuid4()
    # Note: service derives has_input / has_output from presence of
    # the `input` / `output` keys in the payload, not from explicit
    # flags. Build payloads accordingly.
    session = _FakeSession(
        node_payloads={
            "z_id": _payload("z_node", output={"result": 1}),
            "m_id": _payload("m_node", input={"x": 1}),
            "a_id": _payload("a_node", input={"a": 1}, output={"b": 2}),
            "b_id": _payload("b_node", parent="a_node"),
        }
    )

    nodes = await service.list_trace_nodes(session, trace_id=trace_id)

    names = [n["name"] for n in nodes]
    assert names == sorted(names), f"nodes must be in ascending name order; got {names}"
    # Flags survived the sort round-trip:
    by_name = {n["name"]: n for n in nodes}
    assert by_name["a_node"]["has_input"] is True
    assert by_name["a_node"]["has_output"] is True
    assert by_name["m_node"]["has_input"] is True
    assert by_name["m_node"]["has_output"] is False
    assert by_name["b_node"]["parent"] == "a_node"
    assert by_name["z_node"]["has_output"] is True


@pytest.mark.asyncio
async def test_list_trace_nodes_sorts_when_payloads_is_list():
    """Sort applies even when node_payloads is a list (normalized to dict)."""
    trace_id = uuid4()
    session = _FakeSession(
        node_payloads=[
            _payload("zebra"),
            _payload("alpha"),
            _payload("mango"),
        ]
    )

    nodes = await service.list_trace_nodes(session, trace_id=trace_id)
    names = [n["name"] for n in nodes]
    assert names == ["alpha", "mango", "zebra"], (
        f"list-shaped payloads must also be sorted; got {names}"
    )


@pytest.mark.asyncio
async def test_list_trace_nodes_empty_returns_empty():
    """Empty payloads → empty sorted (== []) list, no exception."""
    trace_id = uuid4()
    session = _FakeSession(node_payloads={})

    nodes = await service.list_trace_nodes(session, trace_id=trace_id)
    assert nodes == []
