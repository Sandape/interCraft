"""REQ-039 B2 r2 review fix — nodes must be sorted by name ascending.

Reviewer found that ``service.list_trace_nodes`` returned nodes in dict
insertion order, which depends on the order LangGraph serialized
``node_payloads`` — not a logical ordering. The AC matrix explicitly
requires ``node_name`` ordering.

These tests guard the contract: nodes returned to the frontend must be
sorted by ``name`` ascending, regardless of insertion order.
"""
from __future__ import annotations

from types import SimpleNamespace
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


class _FakeRepository:
    """Stand-in for ``app.modules.admin_console.repository`` returning a fixed trace."""

    def __init__(self, trace: SimpleNamespace) -> None:
        self._trace = trace

    async def get_trace(self, session, trace_id):  # noqa: ANN001 - signature matches repo
        return self._trace


def _patch_repo(monkeypatch, trace: SimpleNamespace) -> None:
    """Patch ``service.repository`` with a ``_FakeRepository`` bound to ``trace``."""
    monkeypatch.setattr(service, "repository", _FakeRepository(trace))


@pytest.mark.asyncio
async def test_list_trace_nodes_sorts_by_name_ascending(monkeypatch):
    """Nodes returned by service.list_trace_nodes must be sorted by `name` ascending."""
    trace_id = uuid4()
    # Deliberately reverse-alphabetical insertion order. Without the sort
    # fix this would come back as c, b, a.
    fake_trace = SimpleNamespace(
        id=trace_id,
        status="success",
        node_payloads={
            "node_c": _payload("c_node"),
            "node_a": _payload("a_node"),
            "node_b": _payload("b_node"),
        },
    )

    _patch_repo(monkeypatch, fake_trace)
    nodes = await service.list_trace_nodes(SimpleNamespace(), trace_id=trace_id)

    names = [n["name"] for n in nodes]
    assert names == ["a_node", "b_node", "c_node"], (
        f"nodes must be sorted by name ascending; got {names}"
    )


@pytest.mark.asyncio
async def test_list_trace_nodes_stable_order_with_mixed_keys(monkeypatch):
    """When payloads include parent / input / output variants, sort still wins."""
    trace_id = uuid4()
    # Note: service derives has_input / has_output from presence of
    # the `input` / `output` keys in the payload, not from explicit
    # flags. Build payloads accordingly.
    fake_trace = SimpleNamespace(
        id=trace_id,
        status="success",
        node_payloads={
            "z_id": _payload("z_node", output={"result": 1}),
            "m_id": _payload("m_node", input={"x": 1}),
            "a_id": _payload("a_node", input={"a": 1}, output={"b": 2}),
            "b_id": _payload("b_node", parent="a_node"),
        },
    )

    _patch_repo(monkeypatch, fake_trace)
    nodes = await service.list_trace_nodes(SimpleNamespace(), trace_id=trace_id)

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
async def test_list_trace_nodes_sorts_when_payloads_is_list(monkeypatch):
    """Sort applies even when node_payloads is a list (normalized to dict)."""
    trace_id = uuid4()
    fake_trace = SimpleNamespace(
        id=trace_id,
        status="success",
        node_payloads=[
            _payload("zebra"),
            _payload("alpha"),
            _payload("mango"),
        ],
    )

    _patch_repo(monkeypatch, fake_trace)
    nodes = await service.list_trace_nodes(SimpleNamespace(), trace_id=trace_id)
    names = [n["name"] for n in nodes]
    assert names == ["alpha", "mango", "zebra"], (
        f"list-shaped payloads must also be sorted; got {names}"
    )


@pytest.mark.asyncio
async def test_list_trace_nodes_empty_returns_empty(monkeypatch):
    """Empty payloads → empty sorted (== []) list, no exception."""
    trace_id = uuid4()
    fake_trace = SimpleNamespace(id=trace_id, status="success", node_payloads={})

    _patch_repo(monkeypatch, fake_trace)
    nodes = await service.list_trace_nodes(SimpleNamespace(), trace_id=trace_id)
    assert nodes == []