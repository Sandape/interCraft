"""Redis token-bucket rate limit (per-IP for /auth/*; per-user for business)."""
from __future__ import annotations

import time

from fastapi import HTTPException, Request, status
from starlette.responses import Response

from app.core.config import get_settings
from app.core.redis import get_redis

# Lua script: atomic token bucket refill + decrement.
# KEYS[1] = bucket key (str)
# ARGV[1] = capacity (int)
# ARGV[2] = refill_rate (tokens/sec, float)
# ARGV[3] = now (sec, int)
# Returns: { allowed (0|1), remaining, retry_after_sec }
_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
    tokens = capacity
    ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * rate)
local allowed = 0
local retry_after = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry_after = math.ceil((1 - tokens) / rate)
end

redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, 60)

return { allowed, math.floor(tokens), retry_after }
"""


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host or "0.0.0.0"
    return "0.0.0.0"


def _rate_key(scope: str, ident: str) -> str:
    bucket = int(time.time() // 60)  # 1-min window key
    return f"rl:{scope}:{ident}:{bucket}"


async def enforce_rate_limit(
    request: Request,
    *,
    scope: str = "auth",
    capacity: int | None = None,
    per_minute: int | None = None,
) -> Response:
    """Apply rate limit. Mutates `request.state` and raises HTTPException(429) when blocked.

    Capacity / per_minute default to config-driven values. Returns the
    `Response` only as a convenience to chain inside middlewares.
    """
    settings = get_settings()
    cap = capacity or (settings.rate_limit_auth_per_min if scope == "auth" else settings.rate_limit_business_per_min)
    rpm = per_minute or cap
    rate_per_sec = rpm / 60.0

    if scope == "auth":
        ident = _client_ip(request)
    else:
        ident = (
            getattr(request.state, "user_id", None)
            or _client_ip(request)
        )
    key = _rate_key(scope, ident)
    now = int(time.time())

    redis = get_redis()
    try:
        allowed, remaining, retry_after = await redis.eval(
            _SCRIPT, 1, key, cap, rate_per_sec, now
        )
    except Exception:
        # Fail-open: never block the request because Redis is sick.
        return Response()

    request.state.rate_limit_remaining = int(remaining)
    request.state.rate_limit_limit = cap
    request.state.rate_limit_reset = now + 60

    if not int(allowed):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit.exceeded",
            headers={
                "Retry-After": str(int(retry_after) or 1),
                "X-RateLimit-Limit": str(cap),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(now + int(retry_after or 1)),
            },
        )

    return Response()


__all__ = ["enforce_rate_limit"]
