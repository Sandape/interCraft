"""Shared fixtures for app/agents/tests/.

Provides an in-process async HTTP client pointed at the FastAPI app so
unit tests can assert HTTP-boundary contracts (e.g. ``response.json()``
shape) without spinning up uvicorn. Mirrors ``backend/tests/conftest.py``
``client`` fixture but scoped to the agents tests directory.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client pointed at the in-process FastAPI app."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c