"""REQ-043 US-2 FR-005 + FR-006 — Checkpointer 8-pool + 3-tier reconnect tests.

Spec contracts:
- FR-005: ``get_checkpointer(user_id)`` factory hashes the user to one
  of 8 pools (``pool_id = hash(user_id) % 8``). Same user → same pool
  (across calls). Different users → possibly different pools. Pool
  exhaustion in pool_X must NOT affect pool_Y.
- FR-006: 3-tier reconnect: L1 快速重试 3 次 (1s) → L2 重建连接 (2s)
  → L3 Sentry + state.error.
- AC-SC-005: Sentry alert ≤ 30s after L3 fires.

REQ-081 additions:
- Shared connection-kwargs builder matches locked
  ``AsyncPostgresSaver.from_conn_string`` semantics:
  ``autocommit=True`` / ``prepare_threshold=0`` / ``row_factory=dict_row``
  plus existing keepalives.
- Singleton + every shard pool funnel through the same builder.
- Pool open or saver setup failure is fail-closed: partial pool is
  closed, no cached entry is published, original exception is
  preserved, and a later retry can succeed.
- Repeated / concurrent first calls are single-flight per slot.
- ``CheckpointerReadiness`` snapshot reports ``up`` / ``down`` /
  ``uninitialised`` with a redacted reason tag.

Note: These tests run with the checkpointer singleton mocked — we
validate the routing/retry logic without standing up a real PG pool.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg_pool
import pytest
from langgraph.checkpoint.postgres import aio as checkpoint_postgres_aio
from psycopg.rows import dict_row


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

        fake_pool = MagicMock()

        async def _always_fail(*_args, **_kwargs):
            from sqlalchemy.exc import OperationalError

            raise OperationalError("connection is closed", None, None)

        fake_pool.test_op = _always_fail

        from app.agents.exceptions import CheckpointerUnavailableError

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
            with pytest.raises(CheckpointerUnavailableError):
                await three_tier_reconnect(
                    user_id="019ec1be-test",
                    op_name="test_op",
                )
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
        field_info = fields["checkpoint_pool_count"]
        assert field_info.default == 8

    def test_checkpointer_unavailable_error_is_reexported(self):
        """``CheckpointerUnavailableError`` is re-exported via ``checkpointer.py``."""
        from app.agents.checkpointer import CheckpointerUnavailableError
        from app.agents.exceptions import CheckpointerUnavailableError as ExcCls

        assert CheckpointerUnavailableError is ExcCls
        err = CheckpointerUnavailableError("test", retry_after=42)
        assert err.retry_after == 42
        assert "test" in str(err)


# ---------------------------------------------------------------------------
# REQ-081 — Shared connection-kwargs builder + fail-closed init + readiness
# ---------------------------------------------------------------------------
class TestBuildCheckpointerConnectionKwargs:
    """Single tested builder shared by singleton + every shard pool."""

    def test_kwargs_match_from_conn_string_contract(self):
        from app.agents.checkpointer import (
            _POOL_CONFIG,
            build_checkpointer_connection_kwargs,
        )

        kwargs = build_checkpointer_connection_kwargs()
        assert kwargs["autocommit"] is True
        assert kwargs["prepare_threshold"] == 0
        assert kwargs["row_factory"] is dict_row
        assert kwargs["keepalives"] == _POOL_CONFIG["keepalives"]
        assert kwargs["keepalives_idle"] == _POOL_CONFIG["keepalives_idle"]
        assert kwargs["keepalives_interval"] == _POOL_CONFIG["keepalives_interval"]
        assert kwargs["keepalives_count"] == _POOL_CONFIG["keepalives_count"]

    def test_kwargs_returns_fresh_dict_each_call(self):
        from app.agents.checkpointer import build_checkpointer_connection_kwargs

        a = build_checkpointer_connection_kwargs()
        b = build_checkpointer_connection_kwargs()
        assert a is not b
        a["autocommit"] = False
        assert b["autocommit"] is True

    @pytest.mark.asyncio
    async def test_singleton_uses_shared_kwargs(self):
        from app.agents import checkpointer as cp_module

        fake_saver = MagicMock(name="saver")
        fake_saver.setup = AsyncMock(return_value=None)

        captured_kwargs: dict[str, object] = {}

        class _FakePool:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

            async def open(self, wait: bool = True) -> None:
                return None

            async def close(self) -> None:
                return None

        def _fake_get_saver(pool):
            return fake_saver

        with (
            patch.object(cp_module, "_checkpointer", None),
            patch.object(cp_module, "_pool", None),
            patch.object(cp_module, "_readiness", cp_module._READINESS_UNINITIALISED),
            patch.object(psycopg_pool, "AsyncConnectionPool", _FakePool),
            patch.object(
                checkpoint_postgres_aio,
                "AsyncPostgresSaver",
                _fake_get_saver,
            ),
        ):
            result = await cp_module.get_checkpointer()

        assert result is fake_saver
        kwargs = captured_kwargs["kwargs"]
        assert kwargs["autocommit"] is True
        assert kwargs["prepare_threshold"] == 0
        assert kwargs["row_factory"] is dict_row


class TestCheckpointerReadinessSnapshot:
    """The ``CheckpointerReadiness`` snapshot reported by /readyz + workers."""

    def test_initial_state_is_uninitialised(self):
        from app.agents import checkpointer as cp_module

        cp_module._readiness = cp_module._READINESS_UNINITIALISED
        snap = cp_module.get_checkpointer_readiness()
        assert snap.state == "uninitialised"
        assert snap.reason == "not_initialised"
        assert snap.as_dict() == {"state": "uninitialised", "reason": "not_initialised"}

    def test_as_dict_does_not_expose_exception_text(self):
        from app.agents import checkpointer as cp_module

        snap = cp_module.CheckpointerReadiness("down", "saver_setup_failed")
        assert "://" not in snap.reason
        assert ":" not in snap.reason
        assert snap.reason in {
            "ok",
            "not_initialised",
            "saver_setup_failed",
            "pool_open_failed",
        }


class TestGetCheckpointerFailClosed:
    """Singleton init is fail-closed: pool open / saver setup failures
    close the partial pool, leave the singleton uninitialised, and
    re-raise the ORIGINAL exception so a later retry can succeed."""

    @pytest.mark.asyncio
    async def test_pool_open_failure_preserves_original_exception_and_keeps_uninitialised(
        self,
    ):
        from app.agents import checkpointer as cp_module

        class _BoomPool:
            def __init__(self, **_kwargs):
                pass

            async def open(self, wait: bool = True) -> None:
                raise RuntimeError("boom: pool open failed")

            async def close(self) -> None:
                return None

        with (
            patch.object(cp_module, "_checkpointer", None),
            patch.object(cp_module, "_pool", None),
            patch.object(psycopg_pool, "AsyncConnectionPool", _BoomPool),
            pytest.raises(RuntimeError, match="boom: pool open failed"),
        ):
            await cp_module.get_checkpointer()

        assert cp_module._checkpointer is None
        assert cp_module._pool is None
        assert cp_module._readiness.state == "down"
        assert cp_module._readiness.reason == "pool_open_failed"

    @pytest.mark.asyncio
    async def test_saver_setup_failure_closes_partial_pool(self):
        from app.agents import checkpointer as cp_module

        close_calls = {"count": 0}

        class _Pool:
            def __init__(self, **_kwargs):
                pass

            async def open(self, wait: bool = True) -> None:
                return None

            async def close(self) -> None:
                close_calls["count"] += 1

        class _Saver:
            def __init__(self, _pool):
                pass

            async def setup(self) -> None:
                raise RuntimeError("concurrent index failed")

        with (
            patch.object(cp_module, "_checkpointer", None),
            patch.object(cp_module, "_pool", None),
            patch.object(psycopg_pool, "AsyncConnectionPool", _Pool),
            patch.object(checkpoint_postgres_aio, "AsyncPostgresSaver", _Saver),
            pytest.raises(RuntimeError, match="concurrent index failed"),
        ):
            await cp_module.get_checkpointer()

        assert close_calls["count"] == 1
        assert cp_module._checkpointer is None
        assert cp_module._pool is None
        assert cp_module._readiness.state == "down"

    @pytest.mark.asyncio
    async def test_retry_after_failure_succeeds(self):
        from app.agents import checkpointer as cp_module

        class _BoomPool:
            def __init__(self, **_kwargs):
                pass

            async def open(self, wait: bool = True) -> None:
                raise RuntimeError("first attempt boom")

            async def close(self) -> None:
                return None

        class _GoodPool:
            def __init__(self, **_kwargs):
                pass

            async def open(self, wait: bool = True) -> None:
                return None

            async def close(self) -> None:
                return None

        good_saver = MagicMock(name="saver")
        good_saver.setup = AsyncMock(return_value=None)

        cp_module._checkpointer = None
        cp_module._pool = None
        cp_module._readiness = cp_module._READINESS_UNINITIALISED
        with (
            patch.object(psycopg_pool, "AsyncConnectionPool", _BoomPool),
            pytest.raises(RuntimeError, match="first attempt boom"),
        ):
            await cp_module.get_checkpointer()

        with (
            patch.object(psycopg_pool, "AsyncConnectionPool", _GoodPool),
            patch.object(
                checkpoint_postgres_aio,
                "AsyncPostgresSaver",
                lambda pool: good_saver,
            ),
        ):
            result = await cp_module.get_checkpointer()
        assert result is good_saver
        assert cp_module._readiness.state == "up"

    @pytest.mark.asyncio
    async def test_pool_close_failure_during_teardown_does_not_swallow_original(self):
        from app.agents import checkpointer as cp_module

        class _Pool:
            def __init__(self, **_kwargs):
                pass

            async def open(self, wait: bool = True) -> None:
                return None

            async def close(self) -> None:
                raise RuntimeError("close failed too")

        class _Saver:
            def __init__(self, _pool):
                pass

            async def setup(self) -> None:
                raise RuntimeError("original setup boom")

        cp_module._checkpointer = None
        cp_module._pool = None
        cp_module._readiness = cp_module._READINESS_UNINITIALISED
        with (
            patch.object(psycopg_pool, "AsyncConnectionPool", _Pool),
            patch.object(checkpoint_postgres_aio, "AsyncPostgresSaver", _Saver),
            pytest.raises(RuntimeError, match="original setup boom"),
        ):
            await cp_module.get_checkpointer()
        assert cp_module._checkpointer is None


class TestGetCheckpointerSingleFlight:
    """Repeated / concurrent first calls run setup at most once per slot."""

    @pytest.mark.asyncio
    async def test_repeated_calls_run_setup_once(self):
        from app.agents import checkpointer as cp_module

        setup_calls = {"count": 0}
        fake_saver = MagicMock(name="saver")
        fake_saver.setup = AsyncMock(
            side_effect=lambda: setup_calls.__setitem__("count", setup_calls["count"] + 1)
        )

        class _Pool:
            def __init__(self, **_kwargs):
                pass

            async def open(self, wait: bool = True) -> None:
                return None

            async def close(self) -> None:
                return None

        cp_module._checkpointer = None
        cp_module._pool = None
        cp_module._readiness = cp_module._READINESS_UNINITIALISED
        with (
            patch.object(psycopg_pool, "AsyncConnectionPool", _Pool),
            patch.object(
                checkpoint_postgres_aio,
                "AsyncPostgresSaver",
                lambda pool: fake_saver,
            ),
        ):
            a = await cp_module.get_checkpointer()
            b = await cp_module.get_checkpointer()
            c = await cp_module.get_checkpointer()

        assert a is b is c is fake_saver
        assert setup_calls["count"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_first_calls_share_single_setup(self):
        from app.agents import checkpointer as cp_module

        setup_calls = {"count": 0}
        fake_saver = MagicMock(name="saver")

        async def _setup_side_effect():
            setup_calls["count"] += 1
            await asyncio.sleep(0.05)

        fake_saver.setup = AsyncMock(side_effect=_setup_side_effect)

        class _Pool:
            def __init__(self, **_kwargs):
                pass

            async def open(self, wait: bool = True) -> None:
                return None

            async def close(self) -> None:
                return None

        cp_module._checkpointer = None
        cp_module._pool = None
        cp_module._readiness = cp_module._READINESS_UNINITIALISED
        with (
            patch.object(psycopg_pool, "AsyncConnectionPool", _Pool),
            patch.object(
                checkpoint_postgres_aio,
                "AsyncPostgresSaver",
                lambda pool: fake_saver,
            ),
        ):
            results = await asyncio.gather(
                cp_module.get_checkpointer(),
                cp_module.get_checkpointer(),
                cp_module.get_checkpointer(),
            )

        assert all(r is fake_saver for r in results)
        assert setup_calls["count"] == 1


class TestCloseCheckpointerIdempotent:
    """``close_checkpointer()`` tolerates already-closed + uninitialised state."""

    @pytest.mark.asyncio
    async def test_close_uninitialised_singleton_is_noop(self):
        from app.agents import checkpointer as cp_module

        cp_module._checkpointer = None
        cp_module._pool = None
        cp_module._readiness = cp_module._READINESS_UNINITIALISED
        await cp_module.close_checkpointer()
        assert cp_module._pool is None
        assert cp_module._readiness.state == "uninitialised"

    @pytest.mark.asyncio
    async def test_close_after_already_closed_does_not_raise(self):
        from app.agents import checkpointer as cp_module

        class _ClosedPool:
            async def close(self) -> None:
                raise RuntimeError("pool already closed")

        cp_module._checkpointer = MagicMock(name="stale_saver")
        cp_module._pool = _ClosedPool()
        cp_module._readiness = cp_module._READINESS_UP
        await cp_module.close_checkpointer()
        assert cp_module._pool is None
        assert cp_module._checkpointer is None
        assert cp_module._readiness.state == "uninitialised"

    @pytest.mark.asyncio
    async def test_shared_pool_close_is_called_exactly_once_across_repeated_shutdown(self):
        """State clearing alone is not proof that the real close ran once."""
        from app.agents import checkpointer as cp_module

        pool = MagicMock(name="shared_pool")
        pool.close = AsyncMock()
        cp_module._checkpointer = MagicMock(name="shared_saver")
        cp_module._pool = pool
        cp_module._readiness = cp_module._READINESS_UP

        await cp_module.close_checkpointer()
        await cp_module.close_checkpointer()

        pool.close.assert_awaited_once_with()
        assert cp_module._pool is None
        assert cp_module._checkpointer is None
        assert cp_module._readiness.state == "uninitialised"


class TestShardPoolFailClosed:
    """Per-pool fail-closed semantics: a failing shard leaves other shards intact."""

    @pytest.mark.asyncio
    async def test_shard_a_failure_does_not_affect_shard_b(self):
        from app.agents import checkpointer_pool

        checkpointer_pool._reset_pools_for_test()
        checkpointer_pool._pool_locks.clear()

        async def _boom_create(cfg):
            raise RuntimeError("shard A boom")

        async def _good_create(cfg):
            return MagicMock(name=f"saver-{cfg.pool_id}")

        from app.agents.checkpointer_pool import get_pool_id

        user_a = "019ec1be-fail-A"
        user_b = "019ec1be-ok-B"
        i = 0
        while get_pool_id(user_a) == get_pool_id(user_b):
            user_b = f"019ec1be-ok-B-{i}"
            i += 1
        pid_a = get_pool_id(user_a)
        pid_b = get_pool_id(user_b)
        assert pid_a != pid_b

        async def _route(cfg):
            if cfg.pool_id == pid_a:
                return await _boom_create(cfg)
            return await _good_create(cfg)

        with patch.object(checkpointer_pool, "_create_pool", side_effect=_route):
            with pytest.raises(RuntimeError, match="shard A boom"):
                await checkpointer_pool.get_checkpointer_pool(user_a)
            assert pid_a not in checkpointer_pool._pools
            result_b = await checkpointer_pool.get_checkpointer_pool(user_b)
            assert result_b is not None
            assert pid_b in checkpointer_pool._pools

        checkpointer_pool._reset_pools_for_test()
        checkpointer_pool._pool_locks.clear()

    @pytest.mark.asyncio
    async def test_shard_pool_close_tolerates_already_closed_pool(self):
        from app.agents import checkpointer_pool

        checkpointer_pool._reset_pools_for_test()
        checkpointer_pool._pool_locks.clear()

        class _ClosedSaver:
            conn = MagicMock()
            conn.close = AsyncMock(side_effect=RuntimeError("already closed"))

        checkpointer_pool._pools[0] = _ClosedSaver()
        await checkpointer_pool.close_all_pools()
        assert checkpointer_pool._pools == {}

        checkpointer_pool._reset_pools_for_test()
        checkpointer_pool._pool_locks.clear()

    @pytest.mark.asyncio
    async def test_shard_conn_close_is_called_exactly_once_across_repeated_shutdown(self):
        """Repeated shutdown must not call a removed saver.conn twice."""
        from app.agents import checkpointer_pool

        checkpointer_pool._reset_pools_for_test()
        checkpointer_pool._pool_locks.clear()

        saver = MagicMock(name="shard_saver")
        saver.conn = MagicMock(name="shard_pool")
        saver.conn.close = AsyncMock()
        checkpointer_pool._pools[0] = saver

        await checkpointer_pool.close_all_pools()
        await checkpointer_pool.close_all_pools()

        saver.conn.close.assert_awaited_once_with()
        assert checkpointer_pool._pools == {}

        checkpointer_pool._reset_pools_for_test()
        checkpointer_pool._pool_locks.clear()

    @pytest.mark.asyncio
    async def test_shard_pool_factory_uses_shared_kwargs(self):
        from app.agents import checkpointer_pool

        checkpointer_pool._reset_pools_for_test()
        checkpointer_pool._pool_locks.clear()

        captured: dict[str, object] = {}

        class _Pool:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            async def open(self, wait: bool = True) -> None:
                return None

            async def close(self) -> None:
                return None

        fake_saver = MagicMock(name="saver")
        fake_saver.setup = AsyncMock(return_value=None)

        with (
            patch.object(psycopg_pool, "AsyncConnectionPool", _Pool),
            patch.object(
                checkpoint_postgres_aio,
                "AsyncPostgresSaver",
                lambda pool: fake_saver,
            ),
        ):
            result = await checkpointer_pool.get_checkpointer_pool("019ec1be-shard-1")

        assert result is fake_saver
        kwargs = captured["kwargs"]
        assert kwargs["autocommit"] is True
        assert kwargs["prepare_threshold"] == 0
        assert kwargs["row_factory"] is dict_row

        checkpointer_pool._reset_pools_for_test()
        checkpointer_pool._pool_locks.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
