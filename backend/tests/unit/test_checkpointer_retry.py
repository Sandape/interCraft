"""023 — Unit tests: checkpointer retry wrapper.

Covers ``_is_reconnectable`` pattern matching (FR-008) and the
``retry_graph_op`` wrapper which is the single production retry path
for all 5 graphs. The legacy ``with_checkpointer_retry`` was removed
(dead code — see 023 round-1 review), so its unit tests are gone too.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.checkpointer import _CHECKPOINTER_RECONNECT_PATTERNS, _is_reconnectable
from app.agents.exceptions import CheckpointerUnavailableError


class TestIsReconnectable:
    def test_matches_connection_is_closed(self):
        err = RuntimeError("connection is closed")
        assert _is_reconnectable(err) is True

    def test_matches_admin_shutdown(self):
        err = RuntimeError("admin shutdown")
        assert _is_reconnectable(err) is True

    def test_matches_server_closed_unexpectedly(self):
        err = RuntimeError("server closed the connection unexpectedly")
        assert _is_reconnectable(err) is True

    def test_rejects_syntax_error(self):
        err = RuntimeError("syntax error at or near")
        assert _is_reconnectable(err) is False

    def test_rejects_auth_failure(self):
        err = RuntimeError("password authentication failed")
        assert _is_reconnectable(err) is False

    def test_case_insensitive_matching(self):
        err = RuntimeError("Connection Is Closed")
        assert _is_reconnectable(err) is True

    def test_patterns_constant_has_four_substrings(self):
        """FR-008 — exactly the 4 spec-mandated substrings."""
        assert _CHECKPOINTER_RECONNECT_PATTERNS == (
            "connection is closed",
            "the connection",
            "admin shutdown",
            "server closed the connection unexpectedly",
        )


class _FakeGraph:
    """Minimal fake graph with configurable aget_state / aupdate_state / ainvoke."""

    def __init__(self) -> None:
        self.aget_state = AsyncMock()
        self.aupdate_state = AsyncMock()
        self.ainvoke = AsyncMock()


async def _build_fake_graph(_fake: _FakeGraph) -> _FakeGraph:
    """Async factory returning ``_fake`` (matches ``build_graph_fn`` contract)."""
    return _fake


class TestRetryGraphOpAgetState:
    """``state_first=False`` (default) — ``op(config, *args)``."""

    @pytest.mark.asyncio
    async def test_aget_state_success_no_retry(self):
        fake = _FakeGraph()
        fake.aget_state.return_value = {"values": {"current_question": 1}}
        config = {"configurable": {"thread_id": "t1"}}

        result = await retry_graph_op_helper(
            lambda: _build_fake_graph(fake), config, "aget_state"
        )

        assert result == {"values": {"current_question": 1}}
        assert fake.aget_state.await_count == 1

    @pytest.mark.asyncio
    async def test_aget_state_retries_on_reconnectable_error(self):
        fake = _FakeGraph()
        fake.aget_state.side_effect = [
            RuntimeError("connection is closed"),
            {"values": {"current_question": 2}},
        ]
        config = {"configurable": {"thread_id": "t1"}}

        result = await retry_graph_op_helper(
            lambda: _build_fake_graph(fake), config, "aget_state"
        )

        assert result == {"values": {"current_question": 2}}
        assert fake.aget_state.await_count == 2

    @pytest.mark.asyncio
    async def test_aget_state_raises_unavailable_after_max_retries(self):
        fake = _FakeGraph()
        fake.aget_state.side_effect = RuntimeError("connection is closed")
        config = {"configurable": {"thread_id": "t1"}}

        with pytest.raises(CheckpointerUnavailableError) as exc_info:
            await retry_graph_op_helper(
                lambda: _build_fake_graph(fake), config, "aget_state", max_retries=2
            )

        assert exc_info.value.retry_after == 30
        assert fake.aget_state.await_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_aget_state_propagates_non_reconnectable_error(self):
        fake = _FakeGraph()
        fake.aget_state.side_effect = ValueError("syntax error at or near")
        config = {"configurable": {"thread_id": "t1"}}

        with pytest.raises(ValueError, match="syntax error"):
            await retry_graph_op_helper(
                lambda: _build_fake_graph(fake), config, "aget_state"
            )

        assert fake.aget_state.await_count == 1  # no retry


class TestRetryGraphOpAupdateState:
    """``state_first=False`` with extra positional args (values)."""

    @pytest.mark.asyncio
    async def test_aupdate_state_passes_values_positionally(self):
        fake = _FakeGraph()
        fake.aupdate_state.return_value = None
        config = {"configurable": {"thread_id": "t1"}}
        values = {"messages": [{"role": "user", "content": "hi"}]}

        await retry_graph_op_helper(
            lambda: _build_fake_graph(fake), config, "aupdate_state", values
        )

        fake.aupdate_state.assert_awaited_once_with(config, values)

    @pytest.mark.asyncio
    async def test_aupdate_state_retries_on_connection_loss(self):
        fake = _FakeGraph()
        fake.aupdate_state.side_effect = [
            RuntimeError("the connection was lost"),
            None,
        ]
        config = {"configurable": {"thread_id": "t1"}}

        await retry_graph_op_helper(
            lambda: _build_fake_graph(fake), config, "aupdate_state", {"k": "v"}
        )

        assert fake.aupdate_state.await_count == 2


class TestRetryGraphOpAinvokeStateFirst:
    """``state_first=True`` — ``op(*args, config)`` (matches ``ainvoke(state, config)``)."""

    @pytest.mark.asyncio
    async def test_ainvoke_state_first_passes_state_then_config(self):
        fake = _FakeGraph()
        fake.ainvoke.return_value = {"result": "ok"}
        config = {"configurable": {"thread_id": "t1"}}
        state = {"messages": []}

        result = await retry_graph_op_helper(
            lambda: _build_fake_graph(fake),
            config,
            "ainvoke",
            state,
            state_first=True,
        )

        fake.ainvoke.assert_awaited_once_with(state, config)
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_ainvoke_state_first_retries_on_reconnectable_error(self):
        fake = _FakeGraph()
        fake.ainvoke.side_effect = [
            RuntimeError("admin shutdown"),
            {"final": "result"},
        ]
        config = {"configurable": {"thread_id": "t1"}}

        result = await retry_graph_op_helper(
            lambda: _build_fake_graph(fake),
            config,
            "ainvoke",
            {"messages": []},
            state_first=True,
        )

        assert result == {"final": "result"}
        assert fake.ainvoke.await_count == 2

    @pytest.mark.asyncio
    async def test_ainvoke_state_first_raises_unavailable_after_max_retries(self):
        fake = _FakeGraph()
        fake.ainvoke.side_effect = RuntimeError("server closed the connection unexpectedly")
        config = {"configurable": {"thread_id": "t1"}}

        with pytest.raises(CheckpointerUnavailableError):
            await retry_graph_op_helper(
                lambda: _build_fake_graph(fake),
                config,
                "ainvoke",
                {"messages": []},
                state_first=True,
                max_retries=2,
            )

        assert fake.ainvoke.await_count == 3


# ---------------------------------------------------------------------------
# Helper — patches ``_force_rebuild`` so retry loop doesn't close the real
# pool (which doesn't exist in unit tests anyway).
# ---------------------------------------------------------------------------


def retry_graph_op_helper(build_fn, config, op_name, *args, **kwargs):
    """Thin wrapper around the real ``retry_graph_op`` that stubs ``_force_rebuild``."""
    from app.agents.checkpointer import retry_graph_op

    with patch("app.agents.checkpointer._force_rebuild", new=AsyncMock()):
        return retry_graph_op(build_fn, config, op_name, *args, **kwargs)
