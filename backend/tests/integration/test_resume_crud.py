"""Integration test — resume CRUD.

Originally a T-task TDD stub. Superseded by tests/integration/test_e2e_phase1.py
(§3.3 COW clone + §3.5 reorder).
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_create_branch_with_parent_clones_blocks() -> None:
    pass


@pytest.mark.asyncio
async def test_reorder_does_not_rewrite_other_indexes() -> None:
    pass


@pytest.mark.asyncio
async def test_soft_delete_cascades_to_blocks_and_versions() -> None:
    pass
