"""Temporary stub conftest for REQ-036 review.

The file app/agents/interview/nodes/planner_context.py (added 2026-06-24)
references ``get_session_context`` from ``app.core.db`` — a name that
no longer exists. This is a pre-existing breakage unrelated to REQ-036.

This stub injects a no-op shim so the export tests can collect. DO NOT
keep this file past the REQ-036 review.
"""
import app.core.db as _db
if not hasattr(_db, "get_session_context"):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def _stub():
        yield None
    _db.get_session_context = _stub
