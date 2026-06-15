"""Integration test — 5-device eviction.

Originally a T-task TDD stub. Superseded by
tests/integration/test_e2e_phase1.py::test_3_1_sixth_login_evicts_oldest.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_sixth_login_evicts_oldest() -> None:
    pass
