"""Contract test — versions API.

Originally a T-task TDD stub. Superseded by tests/integration/test_e2e_phase1.py
which exercises save-version + rollback end-to-end (SC-001 + §3.4).
"""
import pytest

pytestmark = [pytest.mark.contract, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_save_version_201() -> None:
    pass


@pytest.mark.asyncio
async def test_rollback_creates_new_branch() -> None:
    pass
