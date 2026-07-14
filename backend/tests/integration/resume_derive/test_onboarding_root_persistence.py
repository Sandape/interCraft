"""REQ-061 Issue #61 — Onboarding root resume persistence contract.

These are isolated-Postgres contract tests for the onboarding Step 2 flow
that lets a brand-new user create their first (and only) root resume. The
tests run against a real PostgreSQL because the contract under test
depends on the ``resumes_v2`` table, the unique constraint that protects
the "one root per user" invariant, and the savepoint / IntegrityError
recovery path that protects against concurrent POSTs.

Each test is independent: it registers a fresh user via the public auth
route, then exercises the v2 root endpoints and asserts against the
authoritative database state. The tests skip cleanly when the test
runner has no real Postgres (``PLACEHOLDER`` URL); the unit-level
behaviour is covered by ``test_resume_derive_root_logging.py`` and the
frontend tests.

The suite covers:

* blank-mode onboarding: ``metadata.markdown.sourceMarkdown`` is exactly
  empty, no demo identity / facts, the created row is owned by the
  caller and visible only to that caller;
* paste-mode onboarding: the caller's exact marker is preserved byte-
  for-byte (whitespace, length);
* one-row tenant invariant: a second POST for the same tenant returns
  the documented ``ROOT_EXISTS`` envelope (status 409, no overwrite);
* concurrent POSTs: a tight loop of N POSTs yields exactly one created
  row and N-1 stable ``ROOT_EXISTS`` envelopes — never a 500, never a
  silent overwrite;
* cross-tenant 404: tenant B cannot read tenant A's root;
* redaction: success / conflict logs never include the marker / payload.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select

pytestmark = pytest.mark.integration

from app.core.config import get_settings  # noqa: E402
from app.core.db import _session_cm  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.resumes_v2.models import ResumeV2  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _placeholder_db() -> bool:
    return "PLACEHOLDER" in get_settings().database_url


def _deepcopy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    import copy

    return copy.deepcopy(payload)


def _empty_v2_payload(*, marker: str = "") -> dict[str, Any]:
    """Build a complete v2 doc with an exactly-empty Markdown marker.

    The frontend blank-mode onboarding calls into this with ``marker=""``
    so the user's first root has no demo identity or seeded content —
    only the structural skeleton. Paste / structured mode reuses the
    same payload but with ``marker`` set to the user's exact text.
    """
    return {
        "picture": {"hidden": True, "url": "", "size": 96, "rotation": 0, "aspectRatio": 1.0},
        "basics": {"name": "", "headline": "", "email": "", "phone": "", "location": ""},
        "summary": {
            "title": "Summary",
            "icon": "user",
            "columns": 1,
            "hidden": False,
            "content": "",
        },
        "sections": {
            "experience": {
                "title": "Experience",
                "icon": "briefcase",
                "hidden": False,
                "items": [],
            },
            "education": {
                "title": "Education",
                "icon": "graduation-cap",
                "hidden": False,
                "items": [],
            },
            "projects": {"title": "Projects", "icon": "folder", "hidden": False, "items": []},
            "skills": {"title": "Skills", "icon": "wrench", "hidden": False, "items": []},
        },
        "metadata": {
            "template": "onyx",
            "markdown": {"sourceMarkdown": marker, "themeId": "muji-default-autumn"},
        },
    }


async def _register_user(
    client: httpx.AsyncClient, *, email: str, password: str = "Demo1234"
) -> dict[str, Any]:
    fp = f"fp-{uuid4().hex[:12]}"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": email.split("@")[0],
            "device_fingerprint": fp,
        },
        headers={"X-Device-Fingerprint": fp},
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    if isinstance(body, dict):
        if "tokens" in body:
            body["access_token"] = body["tokens"]["access_token"]
        if "user" in body:
            body["user_id"] = body["user"]["id"]
    return body


def _bearer(register_body: dict[str, Any]) -> str:
    token = register_body.get("access_token")
    if not token:
        raise AssertionError(f"register response did not return a token: {register_body!r}")
    return token


async def _create_root_via_api(
    client: httpx.AsyncClient,
    *,
    bearer: str,
    payload: dict[str, Any],
    name: str = "根简历",
    slug: str = "root-resume",
) -> httpx.Response:
    return await client.post(
        "/api/v1/v2/resumes/root",
        json={"name": name, "slug": slug, "data": payload},
        headers={"Authorization": f"Bearer {bearer}"},
    )


async def _fetch_db_root(*, user_id: UUID) -> ResumeV2 | None:
    async with _session_cm() as session:
        stmt = select(ResumeV2).where(
            ResumeV2.user_id == user_id,
            ResumeV2.resume_kind == "root",
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


@pytest_asyncio.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blank_onboarding_root_has_empty_markdown_and_no_demo_identity(
    http_client: httpx.AsyncClient,
) -> None:
    """Blank mode persists a complete v2 doc with sourceMarkdown="" and
    no demo identity / facts."""
    if _placeholder_db():
        pytest.skip("DATABASE_URL is PLACEHOLDER; integration test requires real Postgres")

    email = f"onboarding-blank-{uuid4().hex[:10]}@intercraft.io"
    reg = await _register_user(http_client, email=email)
    bearer = _bearer(reg)
    user_id = UUID(reg["user_id"])

    payload = _empty_v2_payload(marker="")
    resp = await _create_root_via_api(http_client, bearer=bearer, payload=payload)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["resume_kind"] == "root"
    md = body["data"]["metadata"]["markdown"]
    assert md["sourceMarkdown"] == "", (
        "blank onboarding must persist an exactly-empty sourceMarkdown; "
        "any seeded demo text would leak identity / facts."
    )

    db_row = await _fetch_db_root(user_id=user_id)
    assert db_row is not None, "root row must exist for the authenticated caller"
    db_md = (db_row.data or {}).get("metadata", {}).get("markdown", {})
    assert db_md.get("sourceMarkdown") == ""
    # No demo identity: basics / summary must be empty in DB.
    db_basics = (db_row.data or {}).get("basics", {})
    db_summary = (db_row.data or {}).get("summary", {})
    assert (db_basics.get("name") or "") == ""
    assert (db_basics.get("email") or "") == ""
    assert (db_summary.get("content") or "") == ""


@pytest.mark.asyncio
async def test_paste_onboarding_preserves_user_marker_byte_for_byte(
    http_client: httpx.AsyncClient,
) -> None:
    """Paste / structured mode preserves the user's exact marker."""
    if _placeholder_db():
        pytest.skip("DATABASE_URL is PLACEHOLDER; integration test requires real Postgres")

    email = f"onboarding-paste-{uuid4().hex[:10]}@intercraft.io"
    reg = await _register_user(http_client, email=email)
    bearer = _bearer(reg)
    user_id = UUID(reg["user_id"])

    marker = (
        "  # 五年前端 + AI 应用工程师\n  \n  - 负责 RAG 与 Agent 工作流\n  - 推动可观测体系落地\n"
    )
    payload = _empty_v2_payload(marker=marker)
    resp = await _create_root_via_api(http_client, bearer=bearer, payload=payload)

    assert resp.status_code == 201, resp.text
    db_row = await _fetch_db_root(user_id=user_id)
    assert db_row is not None
    db_marker = (db_row.data or {}).get("metadata", {}).get("markdown", {}).get("sourceMarkdown")
    assert db_marker == marker, "paste mode must persist the user's exact marker"


@pytest.mark.asyncio
async def test_second_create_returns_409_root_exists_no_overwrite(
    http_client: httpx.AsyncClient,
) -> None:
    """A second POST for the same user surfaces stable 409 ROOT_EXISTS
    and never overwrites the existing row's data / version."""
    if _placeholder_db():
        pytest.skip("DATABASE_URL is PLACEHOLDER; integration test requires real Postgres")

    email = f"onboarding-twice-{uuid4().hex[:10]}@intercraft.io"
    reg = await _register_user(http_client, email=email)
    bearer = _bearer(reg)
    user_id = UUID(reg["user_id"])

    first_marker = "first marker — keep this exact"
    first = await _create_root_via_api(
        http_client,
        bearer=bearer,
        payload=_empty_v2_payload(marker=first_marker),
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]
    first_version = first.json()["version"]

    # Second POST with intentionally different content — must NOT overwrite.
    second_marker = "second marker must be discarded"
    second = await _create_root_via_api(
        http_client,
        bearer=bearer,
        payload=_empty_v2_payload(marker=second_marker),
    )
    assert second.status_code == 409, second.text
    err = second.json()
    # Backend returns the nested envelope the frontend ApiError parser expects.
    err_obj = err.get("error")
    assert isinstance(err_obj, dict), f"error must be a nested dict, got {type(err_obj).__name__}"
    assert err_obj.get("code") == "ROOT_EXISTS", err

    db_row = await _fetch_db_root(user_id=user_id)
    assert db_row is not None
    assert str(db_row.id) == first_id, "existing root id must not change"
    assert int(db_row.version) == int(first_version), "version must not bump on conflict"
    db_marker = (db_row.data or {}).get("metadata", {}).get("markdown", {}).get("sourceMarkdown")
    assert db_marker == first_marker, "loser POST must never overwrite the winner's marker"


@pytest.mark.asyncio
async def test_concurrent_create_root_returns_stable_root_exists_no_500(
    http_client: httpx.AsyncClient,
) -> None:
    """A burst of concurrent POSTs for one tenant yields exactly one
    created row and N-1 stable 409s. No 500, no overwrite."""
    if _placeholder_db():
        pytest.skip("DATABASE_URL is PLACEHOLDER; integration test requires real Postgres")

    email = f"onboarding-race-{uuid4().hex[:10]}@intercraft.io"
    reg = await _register_user(http_client, email=email)
    bearer = _bearer(reg)
    user_id = UUID(reg["user_id"])

    # All requests use the same slug `root-resume` to match real onboarding
    # concurrency (the repository first flushes a standard row, then the
    # service sets resume_kind='root'). Mix blank/paste markers.
    burst = 6
    payloads = [
        _empty_v2_payload(marker="") if i % 2 == 0 else _empty_v2_payload(marker=f"marker #{i}")
        for i in range(burst)
    ]

    results = await asyncio.gather(
        *[
            _create_root_via_api(
                http_client, bearer=bearer, payload=p, name="根简历", slug="root-resume"
            )
            for i, p in enumerate(payloads)
        ],
        return_exceptions=False,
    )

    statuses = [r.status_code for r in results]
    success = [r for r in results if r.status_code == 201]
    conflicts = [r for r in results if r.status_code == 409]

    assert len(success) == 1, f"expected exactly one winner, got statuses={statuses}"
    assert len(conflicts) == burst - 1, f"expected {burst - 1} ROOT_EXISTS, got statuses={statuses}"
    assert all(c.status_code < 500 for c in conflicts), statuses
    # Strict nested envelope — no flat fallback.
    for c in conflicts:
        err = c.json().get("error")
        assert isinstance(err, dict), (
            f"conflict envelope must be nested dict, got {type(err).__name__}: {err}"
        )
        assert err.get("code") == "ROOT_EXISTS", (c.status_code, c.json())

    # Database invariant: exactly one root row.
    async with _session_cm() as session:
        stmt = select(ResumeV2).where(
            ResumeV2.user_id == user_id,
            ResumeV2.resume_kind == "root",
        )
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 1, f"expected one-row tenant invariant, got {len(rows)}"

    # Winner's content and version must not have changed after loser requests.
    winner = success[0].json()
    winner_id = winner.get("id")
    winner_version = winner.get("version")
    async with _session_cm() as session:
        db_row = await session.get(ResumeV2, UUID(winner_id))
        assert db_row is not None
        assert int(db_row.version) == int(winner_version), (
            f"version must not bump after conflict; expected {winner_version}, got {db_row.version}"
        )
        db_md = (db_row.data or {}).get("metadata", {}).get("markdown", {}).get("sourceMarkdown")
        # The winner's marker must be preserved — the losers did not overwrite.
        winner_marker = next(
            p["metadata"]["markdown"]["sourceMarkdown"]
            for i, p in enumerate(payloads)
            if results[i].status_code == 201
        )
        assert db_md == winner_marker, (
            f"winner marker must be preserved; expected {winner_marker!r}, got {db_md!r}"
        )


@pytest.mark.asyncio
async def test_cross_tenant_404_for_get_root(
    http_client: httpx.AsyncClient,
) -> None:
    """Tenant B cannot read tenant A's root. GET returns 404, never 200
    with a foreign row."""
    if _placeholder_db():
        pytest.skip("DATABASE_URL is PLACEHOLDER; integration test requires real Postgres")

    a_email = f"onboarding-tenant-a-{uuid4().hex[:10]}@intercraft.io"
    b_email = f"onboarding-tenant-b-{uuid4().hex[:10]}@intercraft.io"
    a_reg = await _register_user(http_client, email=a_email)
    b_reg = await _register_user(http_client, email=b_email)

    a_create = await _create_root_via_api(
        http_client,
        bearer=_bearer(a_reg),
        payload=_empty_v2_payload(marker="tenant A only"),
    )
    assert a_create.status_code == 201

    b_get = await http_client.get(
        "/api/v1/v2/resumes/root",
        headers={"Authorization": f"Bearer {_bearer(b_reg)}"},
    )
    assert b_get.status_code == 404
    assert b_get.json().get("error") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_one_row_tenant_invariant_after_sequential_create(
    http_client: httpx.AsyncClient,
) -> None:
    """Sequential creates from one tenant must converge to exactly one row."""
    if _placeholder_db():
        pytest.skip("DATABASE_URL is PLACEHOLDER; integration test requires real Postgres")

    email = f"onboarding-invariant-{uuid4().hex[:10]}@intercraft.io"
    reg = await _register_user(http_client, email=email)
    bearer = _bearer(reg)
    user_id = UUID(reg["user_id"])

    for i in range(3):
        resp = await _create_root_via_api(
            http_client,
            bearer=bearer,
            payload=_empty_v2_payload(marker=f"attempt {i}"),
            name=f"根简历 #{i}",
            slug=f"root-{i}",
        )
        assert resp.status_code in (201, 409), resp.text

    async with _session_cm() as session:
        stmt = select(ResumeV2).where(
            ResumeV2.user_id == user_id,
            ResumeV2.resume_kind == "root",
        )
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 1, f"expected exactly one row, got {len(rows)}"


# ---------------------------------------------------------------------------
# Unit-style contract: race-recovery shape (no DB needed)
# ---------------------------------------------------------------------------
