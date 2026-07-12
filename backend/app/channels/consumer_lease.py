"""PostgreSQL-backed single-active lease for the existing iLink consumer."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.core.db import get_session_context
from app.core.logging import get_logger
from app.modules.agent.runtime.telemetry import emit_event, record_metric

log = get_logger("wechat.consumer")


@dataclass(frozen=True, slots=True)
class LeaseResult:
    acquired: bool
    fencing_token: int | None = None
    lease_until: datetime | None = None


class ConsumerLeaseManager:
    """Acquire, renew and fence one logical channel consumer group."""

    def __init__(self, *, consumer_key: str = "wechat-agent-ilink", ttl_seconds: int = 30) -> None:
        if not consumer_key.strip():
            raise ValueError("consumer_key is required")
        if ttl_seconds < 10:
            raise ValueError("ttl_seconds must be at least 10")
        self.consumer_key = consumer_key
        self.ttl_seconds = ttl_seconds

    async def try_acquire_or_renew(
        self,
        owner_id: UUID,
        expected_fencing_token: int | None = None,
    ) -> LeaseResult:
        statement = text(
            """
            INSERT INTO wechat_consumer_leases (
                consumer_key, owner_id, fencing_token, lease_until,
                heartbeat_at, acquired_at, metadata_json
            ) VALUES (
                :consumer_key, :owner_id, 1,
                now() + make_interval(secs => :ttl_seconds),
                now(), now(), '{}'::jsonb
            )
            ON CONFLICT (consumer_key) DO UPDATE SET
                owner_id = EXCLUDED.owner_id,
                fencing_token = CASE
                    WHEN wechat_consumer_leases.owner_id = EXCLUDED.owner_id
                     AND CAST(:expected_fencing_token AS bigint) IS NOT NULL
                     AND wechat_consumer_leases.fencing_token = CAST(:expected_fencing_token AS bigint)
                     AND wechat_consumer_leases.lease_until > now()
                    THEN wechat_consumer_leases.fencing_token
                    ELSE wechat_consumer_leases.fencing_token + 1
                END,
                lease_until = now() + make_interval(secs => :ttl_seconds),
                heartbeat_at = now(),
                acquired_at = CASE
                    WHEN wechat_consumer_leases.owner_id = EXCLUDED.owner_id
                     AND CAST(:expected_fencing_token AS bigint) IS NOT NULL
                     AND wechat_consumer_leases.fencing_token = CAST(:expected_fencing_token AS bigint)
                     AND wechat_consumer_leases.lease_until > now()
                    THEN wechat_consumer_leases.acquired_at
                    ELSE now()
                END
            WHERE (
                wechat_consumer_leases.owner_id = EXCLUDED.owner_id
                AND CAST(:expected_fencing_token AS bigint) IS NOT NULL
                AND wechat_consumer_leases.fencing_token = CAST(:expected_fencing_token AS bigint)
                AND wechat_consumer_leases.lease_until > now()
            ) OR wechat_consumer_leases.owner_id IS NULL
              OR wechat_consumer_leases.lease_until IS NULL
              OR wechat_consumer_leases.lease_until <= now()
            RETURNING fencing_token, lease_until
            """
        )
        async with get_session_context() as session:
            row = (
                await session.execute(
                    statement,
                    {
                        "consumer_key": self.consumer_key,
                        "owner_id": owner_id,
                        "ttl_seconds": self.ttl_seconds,
                        "expected_fencing_token": expected_fencing_token,
                    },
                )
            ).first()
        if row is None:
            record_metric(
                "wechat_consumer_lease_acquire_total",
                outcome="renew_failed" if expected_fencing_token is not None else "standby",
            )
            return LeaseResult(acquired=False)
        fencing_token = int(row[0])
        outcome = "renewed" if expected_fencing_token is not None else "acquired"
        record_metric("wechat_consumer_lease_acquire_total", outcome=outcome)
        if expected_fencing_token is None and fencing_token > 1:
            record_metric("wechat_consumer_takeover_total", outcome="acquired")
        return LeaseResult(
            acquired=True,
            fencing_token=fencing_token,
            lease_until=row[1],
        )

    async def validate_fence(self, owner_id: UUID, fencing_token: int) -> bool:
        async with get_session_context() as session:
            value = await session.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM wechat_consumer_leases "
                    "WHERE consumer_key=:consumer_key AND owner_id=:owner_id "
                    "AND fencing_token=:fencing_token AND lease_until > now())"
                ),
                {
                    "consumer_key": self.consumer_key,
                    "owner_id": owner_id,
                    "fencing_token": fencing_token,
                },
            )
        return bool(value)

    async def release(self, owner_id: UUID, fencing_token: int) -> bool:
        async with get_session_context() as session:
            result = await session.execute(
                text(
                    "UPDATE wechat_consumer_leases SET owner_id=NULL, "
                    "lease_until=now(), heartbeat_at=now() "
                    "WHERE consumer_key=:consumer_key AND owner_id=:owner_id "
                    "AND fencing_token=:fencing_token"
                ),
                {
                    "consumer_key": self.consumer_key,
                    "owner_id": owner_id,
                    "fencing_token": fencing_token,
                },
            )
            changed = result.rowcount == 1
        return changed


class ActiveConsumerLease:
    """Own the pool only while its PostgreSQL lease can be renewed."""

    def __init__(
        self,
        *,
        manager: ConsumerLeaseManager,
        owner_id: UUID,
        fencing_token: int,
        renew_seconds: int,
        pool: Any,
    ) -> None:
        self.manager = manager
        self.owner_id = owner_id
        self.fencing_token = fencing_token
        self.renew_seconds = renew_seconds
        self.pool = pool
        self._stop_event = asyncio.Event()
        self._renew_task: asyncio.Task[None] | None = None
        self._pool_started = True

    def start_renewal(self) -> None:
        if self._renew_task is None:
            self._renew_task = asyncio.create_task(
                self._renew_loop(), name="wechat-agent-consumer-lease"
            )

    async def _renew_loop(self) -> None:
        consecutive_failures = 0
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.renew_seconds)
                break
            except TimeoutError:
                pass

            try:
                result = await self.manager.try_acquire_or_renew(
                    self.owner_id,
                    expected_fencing_token=self.fencing_token,
                )
            except Exception:
                result = LeaseResult(acquired=False)

            if result.acquired and result.fencing_token == self.fencing_token:
                consecutive_failures = 0
                continue

            consecutive_failures += 1
            log.warning(
                "wechat.consumer.renewal_failed",
                failure_count=consecutive_failures,
            )
            if consecutive_failures < 2:
                continue

            emit_event(
                log,
                "wechat.consumer.status",
                state="degraded",
                enabled=True,
                reason="lease_lost",
                fencing_token=self.fencing_token,
            )
            record_metric("wechat_consumer_state", value=1, state="degraded")
            if self._pool_started:
                await self.pool.shutdown()
                self._pool_started = False
            break

    async def stop(self) -> None:
        self._stop_event.set()
        if self._renew_task is not None:
            await self._renew_task
            self._renew_task = None
        if self._pool_started:
            await self.pool.shutdown()
            self._pool_started = False
        await self.manager.release(self.owner_id, self.fencing_token)


class ConsumerLeaseSupervisor:
    """Keep a consumer-capable instance in standby and acquire after failover."""

    def __init__(
        self,
        *,
        manager: ConsumerLeaseManager,
        owner_id: UUID,
        renew_seconds: int,
        pool: Any,
    ) -> None:
        self.manager = manager
        self.owner_id = owner_id
        self.renew_seconds = renew_seconds
        self.pool = pool
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._active: ActiveConsumerLease | None = None

    async def start(self) -> None:
        await self._try_activate()
        self._task = asyncio.create_task(self._supervise(), name="wechat-agent-consumer-supervisor")

    async def _try_activate(self) -> bool:
        try:
            lease = await self.manager.try_acquire_or_renew(self.owner_id)
        except Exception:
            lease = LeaseResult(acquired=False)
        if not lease.acquired or lease.fencing_token is None:
            emit_event(log, "wechat.consumer.status", state="standby", enabled=True)
            record_metric("wechat_consumer_state", value=1, state="standby")
            return False

        self.pool.configure_consumer_fence(
            consumer_key=self.manager.consumer_key,
            owner_id=self.owner_id,
            fencing_token=lease.fencing_token,
        )
        try:
            await self.pool.startup()
        except Exception as exc:
            try:
                await self.pool.shutdown()
            except Exception:
                pass
            await self.manager.release(self.owner_id, lease.fencing_token)
            emit_event(
                log,
                "wechat.consumer.status",
                state="degraded",
                enabled=True,
                fencing_token=lease.fencing_token,
                reason="startup_failed",
            )
            log.error(
                "wechat.consumer.startup_failed",
                error_type=type(exc).__name__,
            )
            record_metric("wechat_consumer_state", value=1, state="degraded")
            return False

        self._active = ActiveConsumerLease(
            manager=self.manager,
            owner_id=self.owner_id,
            fencing_token=lease.fencing_token,
            renew_seconds=self.renew_seconds,
            pool=self.pool,
        )
        self._active.start_renewal()
        emit_event(
            log,
            "wechat.consumer.status",
            state="active",
            enabled=True,
            fencing_token=lease.fencing_token,
            lease_until=lease.lease_until.isoformat() if lease.lease_until else None,
        )
        record_metric("wechat_consumer_state", value=1, state="active")
        return True

    async def _supervise(self) -> None:
        while not self._stop_event.is_set():
            if self._active is not None:
                previous = self._active
                renewal = previous._renew_task
                if renewal is not None:
                    await renewal
                if self._stop_event.is_set():
                    break
                await previous.stop()
                if self._active is previous:
                    self._active = None
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.renew_seconds)
                break
            except TimeoutError:
                await self._try_activate()

    async def stop(self) -> None:
        self._stop_event.set()
        active = self._active
        if active is not None:
            await active.stop()
            self._active = None
        if self._task is not None:
            await self._task
            self._task = None


__all__ = [
    "ActiveConsumerLease",
    "ConsumerLeaseManager",
    "ConsumerLeaseSupervisor",
    "LeaseResult",
]
