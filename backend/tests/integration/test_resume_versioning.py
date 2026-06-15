"""Integration test — version rollback.

Originally a T-task TDD stub. Superseded by
tests/integration/test_e2e_phase1.py::test_3_4_rollback_creates_new_branch.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_rollback_creates_new_branch() -> None:
    pass


@pytest.mark.asyncio
async def test_initial_version_created_on_branch_create() -> None:
    pass
