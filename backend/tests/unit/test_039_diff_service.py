"""REQ-039 US3 — diff service unit tests (FR-011/012/013/014/015).

Coverage:

- Node alignment by ``node_name`` (FR-013).
- Field-level add/del/mod for nodes present in both traces.
- "Only in left" / "Only in right" sections for nodes unique to one trace.
- Cross-task-type rejection (FR-012 → :class:`CrossTaskTypeDiffError`).
- Audit row written with the canonical fields (FR-014 / IC-5).
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.modules.admin_console import service
from app.modules.admin_console.service import (
    CrossTaskTypeDiffError,
    TraceNotFoundError,
    _align_nodes,
    _diff_fields,
)


# ---------------------------------------------------------------------------
# _align_nodes + _diff_fields (pure functions)
# ---------------------------------------------------------------------------


class TestAlignNodes:
    def test_aligns_by_node_name(self) -> None:
        left = {"plan": {"status": "ok", "score": 9}, "unique_l": {"x": 1}}
        right = {"plan": {"status": "ok", "score": 7}, "unique_r": {"y": 2}}
        result = _align_nodes(left, right)
        names = [n["node_name"] for n in result]
        assert names == ["plan", "unique_l", "unique_r"]
        plan = next(n for n in result if n["node_name"] == "plan")
        assert plan["side"] == "both"
        assert any(f["op"] == "mod" and "score" in f["path"] for f in plan["fields"])

    def test_only_in_left_section(self) -> None:
        result = _align_nodes({"a": {"x": 1}}, {})
        assert len(result) == 1
        assert result[0]["node_name"] == "a"
        assert result[0]["side"] == "left"

    def test_only_in_right_section(self) -> None:
        result = _align_nodes({}, {"b": {"x": 1}})
        assert result[0]["node_name"] == "b"
        assert result[0]["side"] == "right"

    def test_empty_inputs(self) -> None:
        assert _align_nodes({}, {}) == []


class TestDiffFields:
    def test_mod_emitted(self) -> None:
        fields = _diff_fields({"a": 1}, {"a": 2}, prefix="p")
        assert fields == [{"path": "p.a", "op": "mod", "left": 1, "right": 2}]

    def test_add_emitted(self) -> None:
        fields = _diff_fields({"a": 1}, {"a": 1, "b": 2}, prefix="p")
        assert any(f["op"] == "add" and f["right"] == 2 for f in fields)

    def test_del_emitted(self) -> None:
        fields = _diff_fields({"a": 1, "b": 2}, {"a": 1}, prefix="p")
        assert any(f["op"] == "del" and f["left"] == 2 for f in fields)

    def test_equal_keys_omitted(self) -> None:
        fields = _diff_fields({"a": 1}, {"a": 1}, prefix="p")
        assert fields == []


# ---------------------------------------------------------------------------
# compute_diff (orchestration) — patches repository.get_traces_by_ids
# ---------------------------------------------------------------------------


def _trace_row(*, id: UUID, task_type: str, node_payloads: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        task_id=uuid4(),
        task_type=task_type,
        prompt_version="v1",
        model="m",
        input_payload={},
        status="ok",
        replay_of=None,
        node_payloads=node_payloads,
        created_at=None,
    )


@pytest.fixture
def fake_audit(monkeypatch):
    captured = []

    async def _log_diff(session, user_id, **kwargs):
        captured.append({"user_id": user_id, **kwargs})

    async def _log_replay(session, user_id, **kwargs):
        captured.append({"replay": True, **kwargs})

    fake = SimpleNamespace(
        log_diff=_log_diff,
        log_replay=_log_replay,
        log_tag_added=lambda *a, **kw: captured.append({"tag_added": True}),
        log_tag_removed=lambda *a, **kw: captured.append({"tag_removed": True}),
    )
    monkeypatch.setattr(service, "audit", fake)
    return captured


class TestComputeDiff:
    async def test_same_task_type_aligned(
        self, monkeypatch, fake_audit
    ) -> None:
        left_id, right_id = uuid4(), uuid4()
        left = _trace_row(
            id=left_id,
            task_type="interview",
            node_payloads={
                "plan": {"status": "ok", "score": 9},
                "only_left": {"x": 1},
            },
        )
        right = _trace_row(
            id=right_id,
            task_type="interview",
            node_payloads={
                "plan": {"status": "ok", "score": 7},
                "only_right": {"x": 2},
            },
        )

        async def fake_get(session, ids):
            return [left, right]

        monkeypatch.setattr(service.repository, "get_traces_by_ids", fake_get)

        result = await service.compute_diff(
            SimpleNamespace(),
            left_trace_id=left_id,
            right_trace_id=right_id,
            user_id=uuid4(),
        )

        assert result.task_type == "interview"
        assert result.node_count == 3
        names = [n["node_name"] for n in result.nodes]
        assert names == ["only_left", "only_right", "plan"]
        plan = next(n for n in result.nodes if n["node_name"] == "plan")
        assert plan["side"] == "both"
        assert any(f["op"] == "mod" for f in plan["fields"])

        # Audit row.
        assert any(c.get("left_trace_id") == left_id for c in fake_audit)

    async def test_cross_task_type_rejected(
        self, monkeypatch, fake_audit
    ) -> None:
        left_id, right_id = uuid4(), uuid4()
        left = _trace_row(id=left_id, task_type="interview", node_payloads={})
        right = _trace_row(id=right_id, task_type="resume", node_payloads={})

        async def fake_get(session, ids):
            return [left, right]

        monkeypatch.setattr(service.repository, "get_traces_by_ids", fake_get)

        with pytest.raises(CrossTaskTypeDiffError) as exc:
            await service.compute_diff(
                SimpleNamespace(),
                left_trace_id=left_id,
                right_trace_id=right_id,
                user_id=uuid4(),
            )
        assert exc.value.status_code == 400

    async def test_missing_trace_raises_not_found(
        self, monkeypatch, fake_audit
    ) -> None:
        async def fake_get(session, ids):
            return []

        monkeypatch.setattr(service.repository, "get_traces_by_ids", fake_get)
        with pytest.raises(TraceNotFoundError):
            await service.compute_diff(
                SimpleNamespace(),
                left_trace_id=uuid4(),
                right_trace_id=uuid4(),
                user_id=uuid4(),
            )

    async def test_same_id_rejected(
        self, monkeypatch, fake_audit
    ) -> None:
        tid = uuid4()
        with pytest.raises(CrossTaskTypeDiffError):
            await service.compute_diff(
                SimpleNamespace(),
                left_trace_id=tid,
                right_trace_id=tid,
                user_id=uuid4(),
            )