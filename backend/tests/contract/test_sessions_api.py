"""Contract test — sessions API.

Originally a T-task TDD stub. Superseded by tests/integration/test_e2e_phase1.py
which exercises sessions list + 5-device eviction (§3.1).
"""
import pytest

pytestmark = [pytest.mark.contract, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_list_sessions_marks_current() -> None:
    pass
