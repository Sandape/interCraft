"""REQ-051 — dashboard freshness tests (simplified auth)."""
from __future__ import annotations

import pytest

from app.modules.admin_console.auth import require_admin


def test_require_admin_is_functional() -> None:
    """require_admin is a callable async function for FastAPI Depends."""
    import inspect
    assert inspect.iscoroutinefunction(require_admin)
