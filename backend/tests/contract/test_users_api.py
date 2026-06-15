"""Contract test — users API.

Originally a T-task TDD stub. Superseded by tests/integration/test_e2e_phase1.py
which exercises /users/me end-to-end (SC-001).
"""
import pytest

pytestmark = [pytest.mark.contract, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_me_returns_user() -> None:
    pass
