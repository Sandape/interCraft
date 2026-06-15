"""Integration test — RLS isolation.

Originally a T-task TDD stub. Superseded by
tests/integration/test_e2e_phase1.py::test_3_2_rls_isolation.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_branch() -> None:
    pass
