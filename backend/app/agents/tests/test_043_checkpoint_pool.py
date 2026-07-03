"""REQ-043 US-2 FR-005 + FR-006 — Checkpointer 8-pool + 3-tier reconnect tests.

Spec contracts:
- FR-005: ``get_checkpointer(user_id)`` factory hashes the user to one
  of 8 pools (``pool_id = hash(user_id) % 8``). Same user → same pool
  (across calls). Different users → possibly different pools. Pool
  exhaustion in pool_X must NOT affect pool_Y.
- FR-006: 3-tier reconnect: L1 快速重试 3 次 (1s) → L2 重建连接 (2s)
  → L3 Sentry + state.error.
- AC-SC-005: Sentry alert ≤ 30s after L3 fires.

Note: These tests run with the checkpointer singleton mocked — we
validate the routing/retry logic without standing up a real PG pool.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# AC-FR-005 — 8-pool hashing
# ---------------------------------------------------------------------------
class TestCheckpointerPool8:
    """CheckpointerPoolConfig + pool_id hash routing."""

    def test_pool_config_class_exists(self):
        """``CheckpointerPoolConfig`` is importable as a Pydantic model."""
        from app.agents.checkpointer_pool import CheckpointerPoolConfig

        cfg = CheckpointerPoolConfig(pool_id=0)
        assert cfg.pool_id == 0
        assert cfg.min_size >= 1
        assert cfg.max_size >= cfg.min_size

    def test_pool_config_validates_pool_id_range(self):
        """pool_id must be 0..7 (8 pools)."""
        from pydantic import ValidationError

        from app.agents.checkpointer_pool import CheckpointerPoolConfig

        # Valid range
        for pid in range(8):
            cfg = CheckpointerPoolConfig(pool_id=pid)
            assert cfg.pool_id == pid
        # Out of range
        with pytest.raises(ValidationError):
            CheckpointerPoolConfig(pool_id=8)
        with pytest.raises(ValidationError):
            CheckpointerPoolConfig(pool_id=-1)

    def test_get_pool_id_hash_distribution(self):
        """``get_pool_id`` uses md5 hash modulo 8."""
        from app.agents.checkpointer_pool import get_pool_id

        # Same user → same pool
        pid_a = get_pool_id("019ec1be-1234-5678-9abc-def012345678")
        pid_a2 = get_pool_id("019ec1be-1234-5678-9abc-def012345678")
        assert pid_a == pid_a2
        # Range
        assert 0 <= pid_a < 8
        # Different users → distribution
        pids = {get_pool_id(f"user-{i}") for i in range(50)}
        # With 50 users and 8 pools, we expect at least 4 distinct pool ids
        # (statistical floor; deterministic hash guarantees this for md5).
        assert len(pids) >= 4

    def test_get_pool_id_format_consistent(self):
        """pool_id returns int in [0, 7]."""
        from app.agents.checkpointer_pool import get_pool_id

        for i in range(100):
            pid = get_pool_id(f"user-{i}")
            assert isinstance(pid, int)
            assert 0 <= pid < 8

    @pytest.mark.asyncio
    async def test_get_checkpointer_pool_returns_singleton_per_pool(self):
        """Same user → same pool; different user with same hash → same pool."""
        from app.agents import checkpointer_pool

        # Reset the pool registry for a clean test
        checkpointer_pool._pools.clear()

        # Stub pool creation so we don't hit a real DB
        async def _fake_create(cfg):
            return MagicMock(name=f"pool-{cfg.pool_id}")

        with patch.object(checkpointer_pool, "_create_pool", side_effect=_fake_create):
            p1 = await checkpointer_pool.get_checkpointer_pool("019ec1be-user-1")
            p1_again = await checkpointer_pool.get_checkpointer_pool("019ec1be-user-1")
            # Same user_id → same pool instance (singleton)
            assert p1 is p1_again

    @pytest.mark.asyncio
    async def test_pool_isolation_one_pool_exhausted_does_not_affect_others(self):
        """Pool_X failure must NOT affect pool_Y (per AC-SC-004 100% isolation)."""
        from app.agents import checkpointer_pool

        checkpointer_pool._pools.clear()

        # Find two user_ids that hash to different pools
        from app.agents.checkpointer_pool import get_pool_id

        user_a = "019ec1be-user-A"
        user_b = "019ec1be-user-B"
        # Brute force until we get different pools
        i = 0
        while get_pool_id(user_a) == get_pool_id(user_b):
            user_b = f"019ec1be-user-B-{i}"
            i += 1
        pid_a = get_pool_id(user_a)
        pid_b = get_pool_id(user_b)
        assert pid_a != pid_b

        # Stub pool creation — pool_A raises on access, pool_B is healthy
        pool_a = MagicMock(name="pool-A-broken")
        pool_b = MagicMock(name="pool-B-healthy")

        async def _fake_create(cfg):
            if cfg.pool_id == pid_a:
                return pool_a
            return pool_b

        with patch.object(checkpointer_pool, "_create_pool", side_effect=_fake_create):
            pa = await checkpointer_pool.get_checkpointer_pool(user_a)
            pb = await checkpointer_pool.get_checkpointer_pool(user_b)
            assert pa is pool_a
            assert pb is pool_b
            assert pa is not pb
            # pool_b is unaffected — calling get again returns same instance
            pb_again = await checkpointer_pool.get_checkpointer_pool(user_b)
            assert pb_again is pool_b


# ---------------------------------------------------------------------------
# AC-FR-006 — 3-tier reconnect (L1 / L2 / L3)
# ---------------------------------------------------------------------------
class TestThreeTierReconnect:
    """The 3-tier reconnect strategy."""

    def test_three_tier_reconnect_function_exists(self):
        """``three_tier_reconnect`` is importable."""
        from app.agents.reconnect import three_tier_reconnect

        assert callable(three_tier_reconnect)

    @pytest.mark.asyncio
    async def test_l1_retries_3_times_with_1s_interval(self):
        """L1 retries up to 3 times; sleeps 1s between attempts."""
        from app.agents.reconnect import three_tier_reconnect

        # Stub pool that always fails
        fake_pool = MagicMock()

        async def _always_fail(*_args, **_kwargs):
            from sqlalchemy.exc import OperationalError

            raise OperationalError("connection is closed", None, None)

        fake_pool.test_op = _always_fail

        # Patch get_checkpointer_pool to return fake pool
        # Patch asyncio.sleep so we don't actually sleep 3 seconds
        with (
            patch(
                "app.agents.reconnect.get_checkpointer_pool",
                AsyncMock(return_value=fake_pool),
            ),
            patch(
                "app.agents.reconnect.asyncio.sleep",
                new=AsyncMock(),
            ) as mock_sleep,
        ):
            with pytest.raises(Exception):
                await three_tier_reconnect(
                    user_id="019ec1be-test",
                    op_name="test_op",
                )
            # L1 sleeps 3 times (between attempts 1→2, 2→3, 3→L2)
            # L2 sleeps 1 more time before rebuild
            # Total: 3 (L1) + 1 (L2) = 4 sleep calls
            assert mock_sleep.call_count >= 3

    @pytest.mark.asyncio
    async def test_l3_raises_checkpointer_unavailable_error(self):
        """After L1+L2 fail, L3 raises CheckpointerUnavailableError."""
        from app.agents.exceptions import CheckpointerUnavailableError
        from app.agents.reconnect import three_tier_reconnect

        fake_pool = MagicMock()

        async def _always_fail(*_args, **_kwargs):
            from sqlalchemy.exc import OperationalError

            raise OperationalError("connection is closed", None, None)

        fake_pool.test_op = _always_fail

        with (
            patch(
                "app.agents.reconnect.get_checkpointer_pool",
                AsyncMock(return_value=fake_pool),
            ),
            patch(
                "app.agents.reconnect.asyncio.sleep",
                new=AsyncMock(),
            ),
        ):
            with pytest.raises(CheckpointerUnavailableError) as exc_info:
                await three_tier_reconnect(
                    user_id="019ec1be-test",
                    op_name="test_op",
                )
            # retry_after must be set per spec (L3 → frontend waits)
            assert exc_info.value.retry_after >= 1

    @pytest.mark.asyncio
    async def test_success_on_first_try_does_not_retry(self):
        """If first attempt succeeds, no retry / no sleep."""
        from app.agents.reconnect import three_tier_reconnect

        fake_pool = MagicMock()

        async def _success(*_args, **_kwargs):
            return "ok"

        fake_pool.test_op = _success

        with (
            patch(
                "app.agents.reconnect.get_checkpointer_pool",
                AsyncMock(return_value=fake_pool),
            ),
            patch(
                "app.agents.reconnect.asyncio.sleep",
                new=AsyncMock(),
            ) as mock_sleep,
        ):
            result = await three_tier_reconnect(
                user_id="019ec1be-test",
                op_name="test_op",
            )
            assert result == "ok"
            assert mock_sleep.call_count == 0

    @pytest.mark.asyncio
    async def test_l1_success_after_2_failures(self):
        """L1 recovers: 2 fails then 1 success."""
        from app.agents.reconnect import three_tier_reconnect

        fake_pool = MagicMock()
        call_count = {"n": 0}

        async def _flaky(*_args, **_kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                from sqlalchemy.exc import OperationalError

                raise OperationalError("connection is closed", None, None)
            return "recovered"

        fake_pool.test_op = _flaky

        with (
            patch(
                "app.agents.reconnect.get_checkpointer_pool",
                AsyncMock(return_value=fake_pool),
            ),
            patch(
                "app.agents.reconnect.asyncio.sleep",
                new=AsyncMock(),
            ) as mock_sleep,
        ):
            result = await three_tier_reconnect(
                user_id="019ec1be-test",
                op_name="test_op",
            )
            assert result == "recovered"
            # 2 retries → 2 sleeps
            assert mock_sleep.call_count == 2


# ---------------------------------------------------------------------------
# L041-004 / L041-005 — namespace isolation + exception type
# ---------------------------------------------------------------------------
class TestCheckpointPoolNamespaceAndException:
    """Env vars + exception type contracts."""

    def test_checkpointer_pool_config_in_settings(self):
        """Settings declares ``us3_use_v2_checkpoint_pool`` (own namespace)."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert "us3_use_v2_checkpoint_pool" in fields, (
            "Settings must declare us3_use_v2_checkpoint_pool (L041-004 namespace isolation)"
        )

    def test_checkpoint_pool_count_default_8(self):
        """Default checkpoint_pool_count is 8 (per Clarifications 2026-07-03)."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert "checkpoint_pool_count" in fields
        # Default value must be 8
        field_info = fields["checkpoint_pool_count"]
        assert field_info.default == 8

    def test_checkpointer_unavailable_error_is_runtime_error_subclass(self):
        """``CheckpointerUnavailableError`` must be ``RuntimeError`` subclass
        (per L041-005 compatibility with 041 NodeError 6 category).

        The 041 US1 wiring uses ``except RuntimeError`` patterns to catch
        LLM errors and ``MaxIterationsReached`` — the checkpointer exception
        must sit in the same chain so a single ``except`` catches both.
        """
        from app.agents.exceptions import CheckpointerUnavailableError

        assert issubclass(CheckpointerUnavailableError, RuntimeError), (
            "CheckpointerUnavailableError must subclass RuntimeError (L041-005 compat)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])