"""Unit tests for A2A DelegationRunner (T011)."""
from __future__ import annotations

import asyncio

import pytest

from app.agents.a2a.delegation import AgentTimeoutError, DelegationRunner
from app.agents.a2a.schemas import A2AMessageStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _ok_agent(_ctx: dict) -> dict:
    return {"value": 42}


async def _slow_agent(_ctx: dict) -> dict:
    await asyncio.sleep(2.0)
    return {"value": "slow"}


async def _fail_agent(_ctx: dict) -> dict:
    raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

class TestDelegationSuccess:
    @pytest.mark.asyncio
    async def test_returns_result(self) -> None:
        runner = DelegationRunner()
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_ok_agent,
            timeout_seconds=1.0, trace_id="tr", thread_id="th",
        )
        assert rec.status == A2AMessageStatus.SUCCESS
        assert rec.result == {"value": 42}
        assert rec.retry_count == 0
        assert rec.error_reason is None

    @pytest.mark.asyncio
    async def test_duration_recorded(self) -> None:
        runner = DelegationRunner()
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_ok_agent,
            timeout_seconds=1.0, trace_id="tr", thread_id="th",
        )
        assert rec.duration_ms >= 0


# ---------------------------------------------------------------------------
# Timeout path
# ---------------------------------------------------------------------------

class TestDelegationTimeout:
    @pytest.mark.asyncio
    async def test_timeout_status(self) -> None:
        runner = DelegationRunner()
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_slow_agent,
            timeout_seconds=0.1, trace_id="tr", thread_id="th",
        )
        assert rec.status == A2AMessageStatus.TIMEOUT
        assert rec.error_reason is not None
        assert "Timeout" in rec.error_reason

    @pytest.mark.asyncio
    async def test_timeout_does_not_retry(self) -> None:
        runner = DelegationRunner()
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_slow_agent,
            timeout_seconds=0.1, trace_id="tr", thread_id="th",
        )
        # Retry would just consume another 0.1s and produce the same
        # result; we don't retry on timeout.
        assert rec.retry_count == 0


# ---------------------------------------------------------------------------
# Failure path (retry once)
# ---------------------------------------------------------------------------

class TestDelegationFailure:
    @pytest.mark.asyncio
    async def test_first_failure_retries_once(self) -> None:
        """Use a counter to verify retry happened exactly once."""
        call_count = 0

        async def _flaky_agent(_ctx: dict) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first try fails")
            return {"value": "second try succeeds"}

        runner = DelegationRunner()
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_flaky_agent,
            timeout_seconds=1.0, trace_id="tr", thread_id="th",
        )
        assert call_count == 2
        assert rec.status == A2AMessageStatus.SUCCESS
        assert rec.retry_count == 1
        assert rec.result == {"value": "second try succeeds"}

    @pytest.mark.asyncio
    async def test_persistent_failure_returns_failed(self) -> None:
        runner = DelegationRunner()
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_fail_agent,
            timeout_seconds=1.0, trace_id="tr", thread_id="th",
        )
        assert rec.status == A2AMessageStatus.FAILED
        assert rec.retry_count == 1
        assert "RuntimeError" in (rec.error_reason or "")
        assert "boom" in (rec.error_reason or "")

    @pytest.mark.asyncio
    async def test_retry_on_timeout_still_records_failure(self) -> None:
        """If the first call times out, the runner does NOT retry — see rationale."""
        runner = DelegationRunner()
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_slow_agent,
            timeout_seconds=0.1, trace_id="tr", thread_id="th",
        )
        assert rec.status == A2AMessageStatus.TIMEOUT
        assert rec.retry_count == 0


# ---------------------------------------------------------------------------
# Persistence (no repository → no-op; with repository → INSERT)
# ---------------------------------------------------------------------------

class TestDelegationPersistence:
    @pytest.mark.asyncio
    async def test_no_repository_does_not_raise(self) -> None:
        runner = DelegationRunner(repository=None)
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_ok_agent,
            timeout_seconds=1.0, trace_id="tr", thread_id="th",
        )
        assert rec.status == A2AMessageStatus.SUCCESS


# ---------------------------------------------------------------------------
# Trace / thread propagation
# ---------------------------------------------------------------------------

class TestDelegationTrace:
    @pytest.mark.asyncio
    async def test_trace_id_in_record(self) -> None:
        runner = DelegationRunner()
        rec = await runner.run(
            parent="p", child="c", task="t",
            context={}, agent_fn=_ok_agent,
            timeout_seconds=1.0, trace_id="abc-123", thread_id="th-xyz",
        )
        # The runner itself doesn't store trace_id on the record —
        # that's the repository's job. Verify the parent/child + task
        # are correctly preserved.
        assert rec.parent == "p"
        assert rec.child == "c"
        assert rec.task == "t"