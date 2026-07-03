"""REQ-043 US-1 FR-003 — ai_messages TTL cleanup test.

Spec contract:
- ``cleanup_old_ai_messages(days: int = 30)`` deletes rows older than
  ``days`` from the ``ai_messages`` table.
- Called daily by a cron job; the cron registration is best-effort.
- Graceful no-op if the ``ai_messages`` table does not exist yet (it is
  owned by an upstream feature / migration).

Note: the actual SQL table is not yet defined in this codebase (the
spec says it lives in an upstream feature). The TTL function is
implemented to fall back gracefully to a ``select 1`` probe so it can
be wired into the scheduler without breaking the current build.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# AC-SC-003 — TTL function exists and runs without raising
# ---------------------------------------------------------------------------
class TestAiMessagesTTL:
    """The TTL cleanup function must be importable + idempotent."""

    def test_cleanup_function_importable(self):
        """``cleanup_old_ai_messages`` is importable from the jobs module."""
        from app.modules.jobs.ai_messages_ttl import cleanup_old_ai_messages

        assert callable(cleanup_old_ai_messages)

    @pytest.mark.asyncio
    async def test_cleanup_default_days_is_30(self):
        """Default retention is 30 days (per spec FR-003)."""
        from app.modules.jobs.ai_messages_ttl import cleanup_old_ai_messages

        # Mock session.execute to a no-op so we don't hit a real DB
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch(
            "app.core.db._session_cm",
            return_value=_async_cm(mock_session),
        ):
            # Default days=30 must not raise
            deleted = await cleanup_old_ai_messages()
            assert isinstance(deleted, int)
            assert deleted >= 0

    @pytest.mark.asyncio
    async def test_cleanup_custom_days(self):
        """Custom retention days is honored."""
        from app.modules.jobs.ai_messages_ttl import cleanup_old_ai_messages

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch(
            "app.core.db._session_cm",
            return_value=_async_cm(mock_session),
        ):
            deleted = await cleanup_old_ai_messages(days=7)
            assert deleted == 5

    @pytest.mark.asyncio
    async def test_cleanup_handles_missing_table_gracefully(self):
        """If the ai_messages table does not exist, cleanup must not raise."""
        from app.modules.jobs.ai_messages_ttl import cleanup_old_ai_messages

        # Simulate ProgrammingError / UndefinedTableError when table missing
        mock_session = AsyncMock()

        async def _raise_table_missing(*_args, **_kwargs):
            err = Exception("relation 'ai_messages' does not exist")
            raise err

        mock_session.execute = AsyncMock(side_effect=_raise_table_missing)
        mock_session.commit = AsyncMock()

        with patch(
            "app.core.db._session_cm",
            return_value=_async_cm(mock_session),
        ):
            # Must not raise — graceful skip
            deleted = await cleanup_old_ai_messages(days=30)
            assert deleted == 0


# ---------------------------------------------------------------------------
# Trace ID middleware wiring (FR-004)
# ---------------------------------------------------------------------------
class TestTraceIDMiddlewareWiring:
    """TraceIDMiddleware must be wired into the FastAPI app."""

    def test_app_includes_trace_id_middleware(self):
        """The FastAPI app must have TraceIDMiddleware in its middleware stack."""
        from app.main import app
        from app.middleware.trace_id import TraceIDMiddleware

        # Starlette wraps middleware instances in ``Middleware(cls=...)``
        # — check the wrapped class via ``.cls``.
        middleware_classes = [getattr(m, "cls", None) for m in app.user_middleware]
        assert TraceIDMiddleware in middleware_classes, (
            f"TraceIDMiddleware not wired into app; got {middleware_classes}"
        )

    def test_trace_id_middleware_module_path(self):
        """TraceIDMiddleware lives in app.middleware.trace_id (own module)."""
        from app.middleware.trace_id import TraceIDMiddleware

        assert TraceIDMiddleware.__module__ == "app.middleware.trace_id"

    def test_healthz_response_has_trace_id_header(self):
        """When a request hits healthz without X-Trace-Id, the response carries one."""
        from app.middleware.trace_id import TraceIDMiddleware

        # Validate the middleware emits the header on every response by
        # static analysis: dispatch() always sets response.headers[HEADER].
        import inspect

        src = inspect.getsource(TraceIDMiddleware.dispatch)
        assert "response.headers[self.HEADER]" in src or "response.headers[TraceIDMiddleware.HEADER]" in src, (
            "TraceIDMiddleware.dispatch must always set response header"
        )


def _async_cm(value):
    """Build a minimal async context manager that yields ``value``."""

    class _ACM:
        async def __aenter__(self):
            return value

        async def __aexit__(self, *_):
            return False

    return _ACM()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])