"""Contract test — blocks API.

Originally a T-task TDD stub. Superseded by tests/integration/test_e2e_phase1.py
which exercises block reorder end-to-end (§3.5).
"""
import pytest

pytestmark = [pytest.mark.contract, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_reorder_updates_index_atomically() -> None:
    pass
