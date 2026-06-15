"""Contract test — resume branches API.

Originally a T-task TDD stub. Superseded by tests/integration/test_e2e_phase1.py
which exercises branch COW cloning end-to-end (§3.3).
"""
import pytest

pytestmark = [pytest.mark.contract, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_create_branch_with_parent_clones_blocks() -> None:
    pass
