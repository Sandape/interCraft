"""Shared pytest fixtures + skip guards for integration tests.

Integration tests that hit a real Postgres skip when DATABASE_URL is the
placeholder. Unit tests run regardless.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

# Force NullPool so RLS context can't leak across requests.
os.environ.setdefault("DB_USE_NULL_POOL", "1")
os.environ.setdefault("RATE_LIMIT_AUTH_PER_MIN", "10000")
os.environ.setdefault("RATE_LIMIT_BUSINESS_PER_MIN", "10000")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.db import _session_cm  # noqa: E402
from app.main import app  # noqa: E402


def _is_placeholder_db() -> bool:
    return "PLACEHOLDER" in get_settings().database_url


def pytest_collection_modifyitems(config, items):
    skip_db = pytest.mark.skip(
        reason="DATABASE_URL not configured (T008b pending — user must provide a real URL)"
    )
    for item in items:
        if "integration" in item.keywords and _is_placeholder_db():
            item.add_marker(skip_db)


# ---- base fixtures ----

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client pointed at the in-process FastAPI app."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Direct DB session for test setup/verification (no RLS)."""
    async with _session_cm() as session:
        yield session


# ---- auth helpers ----

def _hdrs(access: str | None = None, fp: str = "fp-test") -> dict[str, str]:
    h = {"X-Device-Fingerprint": fp, "X-Request-ID": f"req-{secrets.token_hex(8)}"}
    if access:
        h["Authorization"] = f"Bearer {access}"
    return h


async def _register(
    c: httpx.AsyncClient, email: str, password: str = "Demo1234", fp: str = "fp-1"
) -> dict:
    r = await c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": email.split("@")[0],
            "device_fingerprint": fp,
        },
        headers=_hdrs(fp=fp),
    )
    return r.json()


async def _login(
    c: httpx.AsyncClient, email: str, password: str = "Demo1234", fp: str = "fp-1"
) -> dict:
    r = await c.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "device_fingerprint": fp},
        headers=_hdrs(fp=fp),
    )
    return r.json()


# ---- user fixtures ----

async def _create_user_and_get_headers() -> dict[str, str]:
    """Register a new test user, login, and return auth headers."""
    suffix = secrets.token_hex(8)
    email = f"test_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Register (ignore conflict if user somehow exists)
        reg = await _register(c, email, fp=fp)
        access = reg["tokens"]["access_token"]
        return _hdrs(access, fp)


@pytest.fixture
async def user_a_headers():
    """Auth headers for test user A (fresh per test)."""
    return await _create_user_and_get_headers()


@pytest.fixture
async def user_b_headers():
    """Auth headers for test user B (fresh per test)."""
    return await _create_user_and_get_headers()


@pytest.fixture
async def fresh_user_headers():
    """Auth headers for a brand-new user (same as user_a but semantic name)."""
    return await _create_user_and_get_headers()
