"""Shared fixtures for resumes_v2 tests (T016-T018).

Provides:
- A minimal valid ResumeDataV2 dict (parses the Pydantic schema)
- A registered user + JWT access token via the auth endpoints
- An async session with the RLS `app.user_id` GUC pre-bound for that user
- A helper that builds a raw INSERT (service-role bypass) so models tests
  can pre-seed rows for constraint checks

We rely on the existing root `backend/tests/conftest.py` for `client`,
`db_session`, and `user_a_headers` / `user_b_headers`.
"""
from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import sqlalchemy as sa
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import _session_cm, dispose_engine
from app.main import app


@pytest.fixture(autouse=True)
async def _reset_engine_between_tests() -> AsyncGenerator[None, None]:
    """Reset the SQLAlchemy engine between tests.

    The root ``backend/tests/conftest.py`` defines an ``event_loop``
    fixture that creates a new asyncio loop per test, but the cached
    engine keeps a connection bound to the first loop. With NullPool
    that connection is created fresh each session, but the
    sessionmaker's internals retain a loop reference that causes
    "got Future ... attached to a different loop" on the 2nd test.

    Disposing the engine before/after each test side-steps this.
    """
    await dispose_engine()
    try:
        yield
    finally:
        await dispose_engine()
        # Also close the checkpointer singleton to free its loop-bound state.
        try:
            from app.agents.checkpointer import _force_rebuild

            await _force_rebuild()
        except Exception:
            pass


# ── minimal valid ResumeDataV2 ──────────────────────────────────────────────

def minimal_resume_data_v2() -> dict[str, Any]:
    """A minimal ResumeDataV2 that passes both Pydantic + Zod validation.

    Mirrors the contract from specs/032-resume-renderer-v2/contracts/02-resume-data-schema.md §4.1.
    """
    rgba = "rgba(0,0,0,1)"
    return {
        "picture": {
            "hidden": True,
            "url": "",
            "size": 80,
            "rotation": 0,
            "aspectRatio": 1,
            "borderRadius": 0,
            "borderColor": rgba,
            "borderWidth": 0,
            "shadowColor": rgba,
            "shadowWidth": 0,
        },
        "basics": {
            "name": "Test User",
            "headline": "Engineer",
            "email": "test@example.com",
            "phone": "",
            "location": "",
            "website": {"url": "", "label": ""},
            "customFields": [],
        },
        "summary": {
            "title": "Summary",
            "icon": "file-text",
            "columns": 1,
            "hidden": False,
            "content": "<p>Hello world.</p>",
        },
        "sections": {
            "profiles": {
                "title": "Profiles", "icon": "link", "columns": 1, "hidden": False, "items": []
            },
            "experience": {
                "title": "Experience", "icon": "briefcase", "columns": 1, "hidden": False, "items": []
            },
            "education": {
                "title": "Education", "icon": "graduation-cap", "columns": 1, "hidden": False, "items": []
            },
            "projects": {
                "title": "Projects", "icon": "code", "columns": 1, "hidden": False, "items": []
            },
            "skills": {
                "title": "Skills", "icon": "wrench", "columns": 1, "hidden": False, "items": []
            },
            "languages": {
                "title": "Languages", "icon": "languages", "columns": 1, "hidden": False, "items": []
            },
            "interests": {
                "title": "Interests", "icon": "heart", "columns": 1, "hidden": False, "items": []
            },
            "awards": {
                "title": "Awards", "icon": "trophy", "columns": 1, "hidden": False, "items": []
            },
            "certifications": {
                "title": "Certifications", "icon": "award", "columns": 1, "hidden": False, "items": []
            },
            "publications": {
                "title": "Publications", "icon": "book-open", "columns": 1, "hidden": False, "items": []
            },
            "volunteer": {
                "title": "Volunteer", "icon": "hand-heart", "columns": 1, "hidden": False, "items": []
            },
            "references": {
                "title": "References", "icon": "phone", "columns": 1, "hidden": False, "items": []
            },
        },
        "customSections": [],
        "metadata": {
            "template": "pikachu",
            "layout": {
                "sidebarWidth": 35,
                "pages": [{"fullWidth": False, "main": ["summary", "experience"], "sidebar": ["skills"]}],
            },
            "page": {
                "gapX": 4, "gapY": 6, "marginX": 14, "marginY": 12,
                "format": "a4", "locale": "en-US",
                "hideLinkUnderline": False, "hideIcons": False, "hideSectionIcons": True,
            },
            "design": {
                "colors": {
                    "primary": "rgba(0,132,209,1)",
                    "text": "rgba(0,0,0,1)",
                    "background": "rgba(255,255,255,1)",
                },
                "level": {"icon": "star", "type": "circle"},
            },
            "typography": {
                "body": {"fontFamily": "IBM Plex Sans", "fontWeights": ["400"], "fontSize": 10, "lineHeight": 1.5},
                "heading": {"fontFamily": "IBM Plex Sans", "fontWeights": ["600"], "fontSize": 14, "lineHeight": 1.5},
            },
            "notes": "",
            "styleRules": [],
        },
    }


@pytest.fixture
def minimal_data() -> dict[str, Any]:
    """Alias fixture for clarity in test bodies."""
    return minimal_resume_data_v2()


# ── auth helpers ────────────────────────────────────────────────────────────

def _hdrs(access: str | None = None, fp: str = "fp-v2") -> dict[str, str]:
    h = {"X-Device-Fingerprint": fp, "X-Request-ID": f"req-{secrets.token_hex(8)}"}
    if access:
        h["Authorization"] = f"Bearer {access}"
    return h


async def _register_user(c: httpx.AsyncClient, email: str, fp: str) -> dict[str, str]:
    r = await c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": email.split("@")[0],
            "device_fingerprint": fp,
        },
        headers=_hdrs(fp=fp),
    )
    body = r.json()
    return {"user_id": body["user"]["id"], "access": body["tokens"]["access_token"]}


@pytest.fixture
async def v2_user() -> dict[str, str]:
    """Register a fresh user via the public auth endpoint. Returns {user_id, access}."""
    suffix = secrets.token_hex(8)
    email = f"v2_{suffix}@intercraft.io"
    fp = f"fp-v2-{suffix}"
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await _register_user(c, email, fp)


@pytest.fixture
async def v2_user_b() -> dict[str, str]:
    """A second fresh user — for cross-user 403 / RLS tests."""
    suffix = secrets.token_hex(8)
    email = f"v2b_{suffix}@intercraft.io"
    fp = f"fp-v2b-{suffix}"
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await _register_user(c, email, fp)


# ── raw DB insert helper (service-role bypass, no RLS) ─────────────────────

@pytest.fixture
async def raw_db() -> AsyncGenerator[AsyncSession, None]:
    """AsyncSession without RLS context — for raw SQL constraint tests.

    Use sparingly. Most tests should use `db_session` from the root
    conftest, which respects RLS via the bound `app.user_id` GUC.
    """
    async with _session_cm() as session:
        yield session


async def insert_resume_v2_raw(
    session: AsyncSession,
    *,
    user_id: UUID,
    name: str = "Raw Resume",
    slug: str | None = None,
    is_public: bool = False,
    is_locked: bool = False,
    password_hash: str | None = None,
    data: dict[str, Any] | None = None,
    version: int = 0,
) -> UUID:
    """Insert a resumes_v2 row. Binds RLS to ``user_id`` first since
    the table is FORCE'd to RLS even for the table owner.
    """
    from app.core.db import set_rls_user_id
    from app.modules.resumes_v2.models import ResumeV2

    await set_rls_user_id(session, user_id)
    rid = uuid4()
    row = ResumeV2(
        id=rid,
        user_id=user_id,
        name=name,
        slug=slug or f"raw-{secrets.token_hex(4)}",
        tags=[],
        is_public=is_public,
        is_locked=is_locked,
        password_hash=password_hash,
        data=data or minimal_resume_data_v2(),
        version=version,
    )
    session.add(row)
    await session.flush()
    return rid


async def insert_stats_raw(session: AsyncSession, resume_id: UUID) -> None:
    from app.modules.resumes_v2.models import ResumeStatisticsV2

    session.add(ResumeStatisticsV2(resume_id=resume_id, views=0, downloads=0))
    await session.flush()


async def insert_analysis_raw(session: AsyncSession, resume_id: UUID) -> None:
    from app.modules.resumes_v2.models import ResumeAnalysisV2

    session.add(
        ResumeAnalysisV2(
            resume_id=resume_id,
            analysis={"overallScore": 80, "dimensions": [], "strengths": [], "suggestions": []},
            status="success",
        )
    )
    await session.flush()


async def create_real_user(
    session: AsyncSession,
    *,
    email: str | None = None,
    display_name: str | None = None,
) -> UUID:
    """Insert a real ``users`` row so resumes_v2's FK can be satisfied.

    Returns the user_id. Cleans up after itself on rollback (caller
    is responsible for committing or rolling back).
    """
    import hashlib

    from app.core.db import set_rls_user_id
    from app.core.ids import new_uuid_v7
    from app.core.security import hash_password
    from app.modules.auth.models import User

    uid = new_uuid_v7()
    actual_email = email or f"raw_{secrets.token_hex(8)}@test.local"
    # Pre-bind RLS so the INSERT passes (chicken-and-egg, same as the
    # auth.register flow).
    await set_rls_user_id(session, uid)
    user = User(
        id=uid,
        email=actual_email,
        email_sha256=hashlib.sha256(actual_email.encode()).digest(),
        display_name=display_name or "raw",
        password_hash=hash_password("Demo1234"),
    )
    session.add(user)
    await session.flush()
    return uid
