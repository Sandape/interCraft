"""M12 — LockService: orchestrate lock acquire/release/heartbeat (T018)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog

from app.core.exceptions import AppError
from app.core.ids import new_uuid_v7
from app.core.metrics import lock_acquire_attempts_total
from app.modules.locks.redis_store import (
    LOCK_PREFIX,
    _key,
    acquire as redis_acquire,
    get as redis_get,
    heartbeat as redis_heartbeat,
    publish_event,
    release as redis_release,
    scan_stale,
)
from app.modules.locks.schemas import (
    AcquireInput,
    LockEvent,
    LockStatus,
    ReleaseResponse,
)
from app.core.ws import connection_manager
from app.workers.tasks.lock_audit import write_lock_audit

logger = structlog.get_logger("locks")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock_key_from_id(lock_id: str, resource_type: str, resource_id: str) -> str:
    return _key(resource_type, resource_id)


class LockService:
    """Pessimistic lock service backed by Redis + WS events + audit log."""

    async def acquire(
        self,
        user_id: str,
        device_id: str,
        session_id: str,
        input: AcquireInput,
        user_name: str = "",
    ) -> LockStatus:
        resource_type = input.resource_type
        resource_id = str(input.resource_id)
        key = _key(resource_type, resource_id)

        # Check if already locked
        existing = await redis_get(key)
        if existing:
            if existing.get("user_id") == user_id:
                lock_acquire_attempts_total.labels(result="conflict").inc()
                raise AppError(
                    code="lock.already_held_by_you",
                    message="你已在另一设备上编辑该资源",
                    http_status=409,
                    details={
                        "lock_id": existing.get("lock_id"),
                        "device_id": existing.get("device_id"),
                        "acquired_at": existing.get("acquired_at"),
                    },
                )
            lock_acquire_attempts_total.labels(result="conflict").inc()
            raise AppError(
                code="lock.resource_locked",
                message="该资源正被其他用户编辑中",
                http_status=409,
                details={
                    "locked_by": {
                        "user_id": existing.get("user_id"),
                        "user_name": existing.get("user_name", ""),
                        "acquired_at": existing.get("acquired_at"),
                    }
                },
            )

        now = _now()
        lock_id = str(new_uuid_v7())
        lock_data = {
            "lock_id": lock_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_id,
            "user_name": user_name,
            "device_id": device_id,
            "session_id": session_id,
            "acquired_at": now.isoformat(),
            "heartbeat_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
        }

        ok = await redis_acquire(resource_type, resource_id, lock_data)
        if not ok:
            lock_acquire_attempts_total.labels(result="conflict").inc()
            raise AppError(
                code="lock.resource_locked",
                message="该资源正被其他用户编辑中",
                http_status=409,
            )

        lock_acquire_attempts_total.labels(result="ok").inc()

        # Fire-and-forget audit
        asyncio.create_task(
            _audit(user_id, device_id, session_id, resource_type, resource_id, "acquired")
        )

        # WS broadcast
        event = {
            "type": "lock.acquired",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_id,
            "user_name": user_name,
            "device_id": device_id,
            "acquired_at": now.isoformat(),
        }
        asyncio.create_task(publish_event(resource_id, event))
        asyncio.create_task(connection_manager.broadcast_to_resource(resource_id, event))

        logger.info(
            "lock.acquired",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            lock_id=lock_id,
        )

        return LockStatus(
            locked=True,
            lock_id=lock_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            user_name=user_name,
            device_id=device_id,
            acquired_at=now,
            expires_at=now + timedelta(minutes=5),
        )

    async def release(self, lock_id: str, user_id: str) -> ReleaseResponse:
        """Release a lock by lock_id. Verifies ownership before releasing."""
        # We need to find the key by lock_id. Scan for it.
        from app.core.redis import get_redis

        r = get_redis()
        cursor = 0
        found_key = None
        found_data = None
        while True:
            cursor, keys = await r.scan(cursor, match=f"{LOCK_PREFIX}:*", count=100)
            for key in keys:
                data = await redis_get(key)
                if data and data.get("lock_id") == lock_id:
                    found_key = key
                    found_data = data
                    break
            if found_key or cursor == 0:
                break

        if not found_key or not found_data:
            raise AppError(
                code="lock.not_found",
                message="锁不存在或已过期",
                http_status=404,
            )

        if found_data.get("user_id") != user_id:
            raise AppError(
                code="lock.not_yours",
                message="无权释放他人持有的锁",
                http_status=403,
            )

        await redis_release(found_key)
        now = _now()

        resource_type = found_data.get("resource_type", "")
        resource_id = found_data.get("resource_id", "")

        # Audit
        asyncio.create_task(
            _audit(
                found_data.get("user_id", user_id),
                found_data.get("device_id", ""),
                found_data.get("session_id", ""),
                resource_type,
                resource_id,
                "released",
            )
        )

        # WS broadcast
        event = {
            "type": "lock.released",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "released_at": now.isoformat(),
            "reason": "manual",
        }
        asyncio.create_task(publish_event(resource_id, event))
        asyncio.create_task(connection_manager.broadcast_to_resource(resource_id, event))

        logger.info(
            "lock.released",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            lock_id=lock_id,
        )

        return ReleaseResponse(
            lock_id=lock_id,
            resource_type=resource_type,
            resource_id=resource_id,
            released_at=now,
        )

    async def heartbeat(self, lock_id: str, user_id: str) -> bool:
        """Renew lock TTL. Returns True on success."""
        from app.core.redis import get_redis

        r = get_redis()
        cursor = 0
        found_key = None
        found_data = None
        while True:
            cursor, keys = await r.scan(cursor, match=f"{LOCK_PREFIX}:*", count=100)
            for key in keys:
                data = await redis_get(key)
                if data and data.get("lock_id") == lock_id:
                    found_key = key
                    found_data = data
                    break
            if found_key or cursor == 0:
                break

        if not found_key or not found_data:
            raise AppError(
                code="lock.not_found",
                message="锁不存在或已过期",
                http_status=404,
            )

        if found_data.get("user_id") != user_id:
            raise AppError(
                code="lock.not_yours",
                message="无权操作他人持有的锁",
                http_status=403,
            )

        ok = await redis_heartbeat(found_key)
        if ok:
            # Update heartbeat_at in the stored JSON
            now = _now()
            found_data["heartbeat_at"] = now.isoformat()
            import json as _json

            await r.set(found_key, _json.dumps(found_data, ensure_ascii=False), ex=300)

            resource_type = found_data.get("resource_type", "")
            resource_id = found_data.get("resource_id", "")

            asyncio.create_task(
                _audit(
                    user_id,
                    found_data.get("device_id", ""),
                    found_data.get("session_id", ""),
                    resource_type,
                    resource_id,
                    "heartbeat",
                )
            )

        return ok

    async def get_status(
        self, resource_type: str, resource_id: str
    ) -> LockStatus:
        """Query lock status for a resource."""
        key = _key(resource_type, resource_id)
        data = await redis_get(key)
        if data is None:
            return LockStatus(
                locked=False,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        return LockStatus(
            locked=True,
            lock_id=data.get("lock_id"),
            resource_type=data.get("resource_type"),
            resource_id=data.get("resource_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            device_id=data.get("device_id"),
            acquired_at=datetime.fromisoformat(data["acquired_at"])
            if data.get("acquired_at")
            else None,
            expires_at=datetime.fromisoformat(data["expires_at"])
            if data.get("expires_at")
            else None,
        )

    async def auto_release_stale(self) -> list[dict]:
        """Scan and release stale locks (no heartbeat for >90s).

        Called by ARQ cron every 30s.
        Returns list of released lock data.
        """
        stale_locks = await scan_stale()
        released = []
        for lock_data in stale_locks:
            key = lock_data.pop("_key", None)
            if not key:
                continue
            await redis_release(key)

            resource_id = lock_data.get("resource_id", "")
            user_id = lock_data.get("user_id", "")

            # WS: notify original holder that lock was lost
            lost_event = {
                "type": "lock.lost",
                "resource_type": lock_data.get("resource_type", ""),
                "resource_id": resource_id,
                "reason": "heartbeat_timeout",
                "message": "锁已被释放:心跳超时。请保存本地更改后重新获取锁。",
            }
            if user_id and connection_manager.is_online(user_id):
                asyncio.create_task(connection_manager.send_to_user(user_id, lost_event))

            # WS: broadcast lock.released
            release_event = {
                "type": "lock.released",
                "resource_type": lock_data.get("resource_type", ""),
                "resource_id": resource_id,
                "released_at": _now().isoformat(),
                "reason": "heartbeat_lost",
            }
            asyncio.create_task(publish_event(resource_id, release_event))
            asyncio.create_task(
                connection_manager.broadcast_to_resource(resource_id, release_event)
            )

            # Audit
            asyncio.create_task(
                _audit(
                    user_id,
                    lock_data.get("device_id", ""),
                    lock_data.get("session_id", ""),
                    lock_data.get("resource_type", ""),
                    resource_id,
                    "expired",
                )
            )

            released.append(lock_data)
            logger.info(
                "lock.expired",
                user_id=user_id,
                resource_id=resource_id,
                lock_id=lock_data.get("lock_id"),
            )

        return released


async def _audit(
    user_id: str,
    device_id: str,
    session_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
) -> None:
    try:
        await write_lock_audit(
            ctx={},
            record={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "user_id": user_id,
                "device_id": device_id,
                "session_id": session_id,
                "action": action,
                "metadata_json": {},
            },
        )
    except Exception:
        logger.warning(
            "lock.audit_failed",
            action=action,
            resource_id=resource_id,
        )
