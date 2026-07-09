"""Redis cache for dashboard summary (REQ-057)."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

CACHE_PREFIX = "dashboard_summary"
DEFAULT_TTL_SEC = 60


def build_cache_key(user_id: UUID | str, local_date: date | str) -> str:
    return f"{CACHE_PREFIX}:{user_id}:{local_date}"


def local_date_for_tz(tz_name: str, *, now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    try:
        zi = ZoneInfo(tz_name)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid tz: {tz_name}") from exc
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(zi).date()


async def cache_get(user_id: UUID, local_date: date) -> dict[str, Any] | None:
    try:
        client = get_redis()
        raw = await client.get(build_cache_key(user_id, local_date))
        if not raw:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        logger.warning("dashboard_summary_cache_get_failed", exc_info=True)
        return None


async def cache_set(
    user_id: UUID,
    local_date: date,
    payload: dict[str, Any],
    *,
    ttl_sec: int = DEFAULT_TTL_SEC,
) -> None:
    try:
        client = get_redis()
        await client.set(
            build_cache_key(user_id, local_date),
            json.dumps(payload, default=_json_default, ensure_ascii=False),
            ex=ttl_sec,
        )
    except Exception:  # noqa: BLE001
        logger.warning("dashboard_summary_cache_set_failed", exc_info=True)


async def cache_invalidate(user_id: UUID, *, tz_name: str = "Asia/Shanghai") -> None:
    """Delete today and yesterday keys for the user."""
    try:
        client = get_redis()
        today = local_date_for_tz(tz_name)
        yesterday = today - timedelta(days=1)
        await client.delete(
            build_cache_key(user_id, today),
            build_cache_key(user_id, yesterday),
        )
    except Exception:  # noqa: BLE001
        logger.warning("dashboard_summary_cache_invalidate_failed", exc_info=True)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)!r} is not JSON serializable")


__all__ = [
    "CACHE_PREFIX",
    "DEFAULT_TTL_SEC",
    "build_cache_key",
    "cache_get",
    "cache_invalidate",
    "cache_set",
    "local_date_for_tz",
]
