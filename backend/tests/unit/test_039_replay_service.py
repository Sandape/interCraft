"""REQ-039 US2 — replay service unit tests (FR-006/007/008/010).

Pure unit tests for the service layer's :func:`trigger_replay` logic.
These tests use the in-memory ``AsyncSession`` substitute pattern:
since the service calls ``repository.get_trace`` and
``repository.insert_trace`` directly, we monkey-patch those
helpers to avoid DB I/O for fast feedback.

Coverage:

- Happy path: replay copies prompt_version + model + input_payload
  snapshot (FR-007).
- Replay writes ``replay_of`` pointer (FR-006).
- Audit row is written with the canonical fields (FR-008 / IC-5).
- Missing trace → :class:`TraceNotFoundError` (HTTP 404).
- Retired model → :class:`ModelRetiredError` (HTTP 410, FR-010).
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.modules.admin_console import service
from app.modules.admin_console.service import (
    ModelRetiredError,
    TraceNotFoundError,
)


class _FakeAuditRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def log_replay(self, session, user_id, **kwargs):
        self.calls.append(("replay", {"user_id": user_id, **kwargs}))

    async def log_diff(self, session, user_id, **kwargs):
        self.calls.append(("diff", {"user_id": user_id, **kwargs}))

    async def log_tag_added(self, session, user_id, **kwargs):
        self.calls.append(("tag_added", {"user_id": user_id, **kwargs}))

    async def log_tag_removed(self, session, user_id, **kwargs):
        self.calls.append(("tag_removed", {"user_id": user_id, **kwargs}))


@pytest.fixture
def fake_session(monkeypatch):
    """Patch the service's repository + audit calls so they don't touch the DB."""
    audit = _FakeAuditRecorder()
    monkeypatch.setattr(service, "audit", audit)
    monkeypatch.setattr(service, "repository", service.repository)  # keep import
    return SimpleNamespace(audit=audit)


@pytest.fixture(autouse=True)
def _reset_retired_models():
    service.reset_retired_models()
    yield
    service.reset_retired_models()


def _trace_row(**overrides):
    base = {
        "id": uuid4(),
        "task_id": uuid4(),
        "user_id": uuid4(),
        "task_type": "interview",
        "prompt_version": "v1.2.3",
        "model": "deepseek-v4-pro",
        "input_payload": {"messages": [{"role": "user", "content": "hi"}]},
        "status": "failed",
        "replay_of": None,
        "node_payloads": {"plan": {"status": "ok"}},
        "created_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestTriggerReplayHappyPath:
    async def test_replay_creates_new_trace_with_replay_of_pointer(
        self, monkeypatch, fake_session
    ) -> None:
        from app.modules.admin_console import service as svc

        orig = _trace_row()
        new_id = uuid4()

        async def fake_get_trace(session, trace_id):
            assert trace_id == orig.id
            return orig

        captured = {}

        async def fake_insert_trace(session, **kwargs):
            captured.update(kwargs)
            captured["id"] = kwargs.get("trace_id") or uuid4()
            row = SimpleNamespace(
                id=captured["id"],
                task_id=kwargs.get("task_id"),
                prompt_version=kwargs.get("prompt_version"),
                model=kwargs.get("model"),
                status=kwargs.get("status"),
                created_at=datetime.now(timezone.utc),
            )
            return row

        monkeypatch.setattr(svc.repository, "get_trace", fake_get_trace)
        monkeypatch.setattr(svc.repository, "insert_trace", fake_insert_trace)

        user_id = uuid4()
        result = await svc.trigger_replay(
            SimpleNamespace(), orig_trace_id=orig.id, user_id=user_id
        )

        # Replay copies prompt_version + model + input_payload verbatim (FR-007).
        assert captured["prompt_version"] == orig.prompt_version
        assert captured["model"] == orig.model
        assert captured["input_payload"] == orig.input_payload
        assert captured["replay_of"] == orig.id
        assert captured["status"] == "pending"
        # New trace has a fresh UUID (not the original).
        assert result.new_trace_id != orig.id
        assert result.replay_of == orig.id
        assert result.prompt_version == orig.prompt_version
        assert result.model == orig.model

        # Audit row written.
        assert any(c[0] == "replay" for c in fake_session.audit.calls)
        replay_call = next(c for c in fake_session.audit.calls if c[0] == "replay")
        assert replay_call[1]["user_id"] == user_id
        assert replay_call[1]["orig_trace_id"] == orig.id
        assert replay_call[1]["new_trace_id"] == result.new_trace_id


class TestTriggerReplayErrors:
    async def test_missing_trace_raises_not_found(self, monkeypatch) -> None:
        from app.modules.admin_console import service as svc

        async def fake_get_trace(session, trace_id):
            return None

        monkeypatch.setattr(svc.repository, "get_trace", fake_get_trace)
        with pytest.raises(TraceNotFoundError):
            await svc.trigger_replay(
                SimpleNamespace(), orig_trace_id=uuid4(), user_id=uuid4()
            )

    async def test_retired_model_raises_410(self, monkeypatch) -> None:
        from app.modules.admin_console import service as svc

        orig = _trace_row(model="legacy-gpt-3.5")
        service.set_retired_models({"legacy-gpt-3.5"})

        async def fake_get_trace(session, trace_id):
            return orig

        monkeypatch.setattr(svc.repository, "get_trace", fake_get_trace)
        with pytest.raises(ModelRetiredError) as exc:
            await svc.trigger_replay(
                SimpleNamespace(), orig_trace_id=orig.id, user_id=uuid4()
            )
        assert exc.value.status_code == 410
        assert "retired" in exc.value.message.lower()