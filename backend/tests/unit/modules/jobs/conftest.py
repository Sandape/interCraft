"""Local conftest for backend/tests/unit/modules/jobs/ — provides a stub
db_session fixture so migration tests can be collected without the full
test suite's conftest (which requires app.main to be importable).

The integration-level tests (which actually hit a real Postgres) use the
top-level `tests/conftest.py` fixture. For pure unit-level checks
(e.g. verifying migration module shape), we don't need a real session.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
async def db_session() -> MagicMock:
    """A mock AsyncSession for unit-level migration tests.

    This fixture mimics the contract of the integration `db_session` fixture
    enough that schema-inspection tests can be written and collected without
    requiring a real database connection. Tests that need real DB behavior
    should be marked `@pytest.mark.integration` and run via the full suite.
    """
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    return session
