"""Integration test — silent refresh.

Originally a T-task TDD stub. Superseded by
tests/integration/test_e2e_phase1.py::test_3_6_refresh_rotates_invalidates_old.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_refresh_rotates_and_invalidates_old() -> None:
    pass
