"""REQ-043 US-1 FR-004 — ``X-Trace-Id`` HTTP middleware.

Reads (or generates) a trace id from the ``X-Trace-Id`` request header,
attaches it to ``request.state.trace_id`` for downstream handlers, and
echoes it back on the response. Composes with the existing
``RequestIDMiddleware`` (``X-Request-ID``) — both headers coexist during
the dual-track window.

Design (per L041-004 namespace isolation):
- Module path ``app.middleware.trace_id`` — distinct from
  ``app.core.middleware.RequestIDMiddleware``. We don't modify the
  legacy middleware because removing it would break the 040
  trace-context wiring that 042 depends on.
- Trace id format: 32-char lowercase hex (OTel ``trace_id`` convention)
  if no header is provided. Falls back to ``uuid4().hex`` to ensure
  the header is always populated.
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# 32-char lowercase hex (OTel trace_id convention).
_TRACE_ID_PATTERN = r"[0-9a-f]{32}"


def _is_valid_trace_id(value: str) -> bool:
    """Accept 32-char lowercase hex; reject anything else."""
    import re

    return bool(re.fullmatch(_TRACE_ID_PATTERN, value))


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Inject / propagate ``X-Trace-Id`` on every request/response pair.

    Behaviour:
    - If the request supplies a valid ``X-Trace-Id`` header, reuse it.
    - Otherwise, generate a fresh ``uuid4().hex`` (32-char lowercase hex).
    - Store on ``request.state.trace_id`` for handlers.
    - Echo on the response header so clients can correlate.
    """

    HEADER = "X-Trace-Id"

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(self.HEADER, "")
        if incoming and _is_valid_trace_id(incoming):
            trace_id = incoming
        else:
            trace_id = uuid.uuid4().hex
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers[self.HEADER] = trace_id
        return response


__all__ = ["TraceIDMiddleware"]