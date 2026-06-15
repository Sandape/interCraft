"""Monthly quota reset test — DEC-P2-4.

Verifies that calling monthly_quota_reset() resets monthly_token_used=0
and quota_reset_at=now() for active users.
"""
from __future__ import annotations

import secrets

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text

from app.main import app
from app.workers.tasks.monthly_quota_reset import monthly_quota_reset


async def _register_user() -> tuple[str, str]:
    """Create a fresh user and return (email, user_id)."""
    suffix = secrets.token_hex(8)
    email = f"quota_test_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/v1/auth/register", json={
            "email": email, "password": "Demo1234",
            "display_name": email.split("@")[0],
            "device_fingerprint": fp,
        })
        user_id = r.json()["user"]["id"]
    return email, user_id


@pytest.mark.integration
class TestMonthlyQuotaReset:
    async def test_reset_zeroes_used_tokens(self, db_session) -> None:
        """After calling reset, monthly_token_used should be 0."""
        email, user_id = await _register_user()

        # Set some token usage
        await db_session.execute(
            text("UPDATE users SET monthly_token_used = 50000 WHERE id = :uid"),
            {"uid": user_id},
        )
        await db_session.commit()

        result = await monthly_quota_reset({})
        assert result["status"] == "ok"
        assert result["rows_updated"] >= 1

        row = await db_session.execute(
            text("SELECT monthly_token_used FROM users WHERE id = :uid"),
            {"uid": user_id},
        )
        assert row.scalar() == 0

    async def test_reset_updates_quota_reset_at(self, db_session) -> None:
        """quota_reset_at should be updated to current time."""
        from datetime import datetime, timezone

        email, user_id = await _register_user()

        # Set old date
        await db_session.execute(
            text("UPDATE users SET monthly_token_used = 100, quota_reset_at = '2026-05-01' WHERE id = :uid"),
            {"uid": user_id},
        )
        await db_session.commit()

        before = datetime.now(timezone.utc)
        await monthly_quota_reset({})
        after = datetime.now(timezone.utc)

        row = await db_session.execute(
            text("SELECT quota_reset_at FROM users WHERE id = :uid"),
            {"uid": user_id},
        )
        new_ts = row.scalar()
        assert new_ts is not None
        assert before <= new_ts <= after
