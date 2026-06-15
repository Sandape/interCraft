"""M12 — Redis lock store (T017).

Key format: lock:{resource_type}:{resource_id}
Value: JSON string with lock metadata.
TTL: 300s hard cap (extended on heartbeat).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from uuid import UUID

from app.core.redis import get_redis, publish


LOCK_PREFIX = "lock"
LOCK_TTL = 300  # 5 min hard cap
HEARTBEAT_TIMEOUT = 90  # 1.5x heartbeat interval


def _key(resource_type: str, resource_id: str | UUID) -> str:
    return f"{LOCK_PREFIX}:{resource_type}:{resource_id}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def acquire(
    resource_type: str,
    resource_id: str | UUID,
    lock_data: dict,
) -> bool:
    """Try to SET NX with TTL. Returns True if acquired, False if already held."""
    r = get_redis()
    key = _key(resource_type, resource_id)
    payload = json.dumps(lock_data, ensure_ascii=False)
    result = await r.set(key, payload, nx=True, ex=LOCK_TTL)
    return result is True


async def release(lock_key: str) -> int:
    """Delete the lock key. Returns number of keys deleted."""
    r = get_redis()
    return await r.delete(lock_key)


async def heartbeat(lock_key: str) -> bool:
    """Renew TTL via EXPIRE. Returns True if key exists, False otherwise."""
    r = get_redis()
    result = await r.expire(lock_key, LOCK_TTL)
    return result == 1


async def get(lock_key: str) -> dict | None:
    """Get lock data as dict, or None if not found."""
    r = get_redis()
    raw = await r.get(lock_key)
    if raw is None:
        return None
    return json.loads(raw) if isinstance(raw, str) else raw


async def publish_event(resource_id: str, event: dict) -> int:
    """Publish a lock event to the resource's Redis channel."""
    channel = f"lock:{resource_id}"
    return await publish(channel, event)


async def scan_stale() -> list[dict]:
    """Scan for stale locks (heartbeat_at > 90s ago). Returns list of lock data dicts."""
    r = get_redis()
    stale = []
    now_ts = time.time()
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor, match=f"{LOCK_PREFIX}:*", count=100)
        for key in keys:
            raw = await r.get(key)
            if raw is None:
                continue
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                hb_at = data.get("heartbeat_at")
                if hb_at:
                    hb_ts = datetime.fromisoformat(hb_at).timestamp()
                    if now_ts - hb_ts > HEARTBEAT_TIMEOUT:
                        data["_key"] = key
                        stale.append(data)
            except Exception:
                continue
        if cursor == 0:
            break
    return stale
