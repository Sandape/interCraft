"""Cross-cutting middleware: request-id, metrics, last-seen flushing, CORS helper."""
from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.logging import bind_request_context, clear_request_context
from app.core.metrics import http_request_duration_seconds, http_requests_total

log = structlog.get_logger("http")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject `X-Request-ID` and bind it into the log context for the request."""

    HEADER = "X-Request-ID"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get(self.HEADER) or str(uuid.uuid4())
        request.state.request_id = rid
        bind_request_context(request_id=rid)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers[self.HEADER] = rid
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Count requests + observe latency into Prometheus metrics."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        # Use the route's path template (e.g. /api/v1/users/me) not the raw URL.
        path_template = request.url.path
        method = request.method
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            http_requests_total.labels(method=method, path=path_template, status="500").inc()
            http_request_duration_seconds.labels(method=method, path=path_template).observe(duration)
            raise
        duration = time.perf_counter() - start
        status_code = str(response.status_code)
        http_requests_total.labels(method=method, path=path_template, status=status_code).inc()
        http_request_duration_seconds.labels(method=method, path=path_template).observe(duration)
        return response


class LastSeenTracker(BaseHTTPMiddleware):
    """Update `auth_sessions.last_seen_at` periodically (Redis buffer).

    The actual DB flush happens in the sessions service on critical paths.
    Here we just record the current session id in Redis for the next
    batch job. Phase 1 keeps this lightweight (no background flusher).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        sid = getattr(request.state, "session_id", None)
        if sid:
            try:
                from app.core.redis import get_redis

                redis = get_redis()
                await redis.sadd("last_seen:pending", sid)
                await redis.expire("last_seen:pending", 3600)
            except Exception:
                pass
        return await call_next(request)


def add_cors_headers(response: Response) -> Response:
    """No-op placeholder; CORS handled by FastAPI CORSMiddleware in main.py."""
    return response


class InternalIPMiddleware(BaseHTTPMiddleware):
    """Restrict /internal/* routes to localhost / Docker network IPs."""

    ALLOWED_PREFIX = "/api/v1/internal"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith(self.ALLOWED_PREFIX):
            client_host = request.client.host if request.client else None
            if client_host not in ("127.0.0.1", "::1", "localhost"):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "internal.forbidden",
                            "message": "Internal endpoints are not publicly accessible.",
                        }
                    },
                )
        return await call_next(request)


__all__ = ["InternalIPMiddleware", "LastSeenTracker", "MetricsMiddleware", "RequestIDMiddleware"]
