"""Integration test — auth flow.

Originally a T-task TDD stub. Superseded by tests/integration/test_e2e_phase1.py
(SC-001 happy path + §3.1 + §3.6).
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_register_login_me_flow() -> None:
    pass


@pytest.mark.asyncio
async def test_5_device_eviction() -> None:
    pass


@pytest.mark.asyncio
async def test_refresh_reuse_revoke_all() -> None:
    pass
