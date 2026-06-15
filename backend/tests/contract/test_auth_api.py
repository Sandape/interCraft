"""Contract test — auth API.

Originally a T-task TDD stub. Superseded by tests/integration/test_e2e_phase1.py
which exercises register/login/refresh end-to-end against the real DB.
"""
import pytest

pytestmark = [pytest.mark.contract, pytest.mark.skip(reason="superseded by test_e2e_phase1.py")]


@pytest.mark.asyncio
async def test_register_201_and_token_pair() -> None:
    pass


@pytest.mark.asyncio
async def test_register_duplicate_email_409() -> None:
    pass


@pytest.mark.asyncio
async def test_register_weak_password_422() -> None:
    pass
