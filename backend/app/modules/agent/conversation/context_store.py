"""Redis ConversationContext store (REQ-054).

Key: ``wechat:conversation:{user_id}``
TTL: 24h, refreshed on every read/write.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

KEY_PREFIX = "wechat:conversation:"
TTL_SECONDS = 86_400  # 24h

VALID_STATES = frozenset({"idle", "awaiting_confirmation", "in_interview"})


class RedisUnavailableError(Exception):
    """Raised when Redis cannot be reached for conversation context."""


def _key(user_id: UUID | str) -> str:
    return f"{KEY_PREFIX}{user_id}"


def default_context() -> dict[str, Any]:
    """Fresh idle context."""
    return {
        "state": "idle",
        "pending_action": None,
        "queued_after_confirm": [],
        "interview_session_id": None,
        "interview_round": None,
        "unknown_streak": 0,
        "last_active_at": datetime.now(timezone.utc).isoformat(),
        "channel_hint": "wechat",
    }


def _touch(ctx: dict[str, Any]) -> dict[str, Any]:
    ctx = dict(ctx)
    ctx["last_active_at"] = datetime.now(timezone.utc).isoformat()
    if "queued_after_confirm" not in ctx:
        ctx["queued_after_confirm"] = []
    if "unknown_streak" not in ctx:
        ctx["unknown_streak"] = 0
    if ctx.get("state") not in VALID_STATES:
        ctx["state"] = "idle"
    return ctx


async def get_context(user_id: UUID | str) -> dict[str, Any]:
    """Load conversation context; miss → idle default. Refreshes TTL on hit."""
    try:
        r = get_redis()
        raw = await r.get(_key(user_id))
        if not raw:
            return default_context()
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            return default_context()
        ctx = _touch(data)
        await r.set(_key(user_id), json.dumps(ctx, ensure_ascii=False), ex=TTL_SECONDS)
        return ctx
    except RedisUnavailableError:
        raise
    except Exception as exc:
        logger.warning(
            "conversation_context_get_failed",
            extra={"user_id": str(user_id), "error": type(exc).__name__},
        )
        raise RedisUnavailableError(str(exc)) from exc


async def set_context(user_id: UUID | str, ctx: dict[str, Any]) -> None:
    """Persist context and refresh TTL."""
    try:
        r = get_redis()
        payload = _touch(ctx)
        await r.set(
            _key(user_id),
            json.dumps(payload, ensure_ascii=False),
            ex=TTL_SECONDS,
        )
    except RedisUnavailableError:
        raise
    except Exception as exc:
        logger.warning(
            "conversation_context_set_failed",
            extra={"user_id": str(user_id), "error": type(exc).__name__},
        )
        raise RedisUnavailableError(str(exc)) from exc


async def clear_context(user_id: UUID | str) -> None:
    """Delete conversation context key."""
    try:
        r = get_redis()
        await r.delete(_key(user_id))
    except Exception as exc:
        logger.warning(
            "conversation_context_clear_failed",
            extra={"user_id": str(user_id), "error": type(exc).__name__},
        )
        raise RedisUnavailableError(str(exc)) from exc


__all__ = [
    "KEY_PREFIX",
    "TTL_SECONDS",
    "RedisUnavailableError",
    "default_context",
    "get_context",
    "set_context",
    "clear_context",
]
