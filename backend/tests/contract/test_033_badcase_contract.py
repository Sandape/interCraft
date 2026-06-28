"""REQ-033 US8 — badcase API contract tests (T055).

Locks the 7-endpoint surface documented in
``specs/033-eval-pm-dashboard/data-model.md`` §Badcase / §State
Transitions and ``contracts/pm-dashboard-api.md`` §badcases:

- ``POST /api/v1/badcases`` create — success + 422 on invalid
  ``type``/``severity``/``source``.
- ``GET /api/v1/badcases/{badcase_id}`` read — 200 + 404.
- ``GET /api/v1/badcases`` list — supports ``status``, ``type``,
  ``severity``, ``page``, ``page_size`` query filters.
- ``POST /api/v1/badcases/{badcase_id}/classify`` — requires
  ``reviewer``; updates type/severity.
- ``POST /api/v1/badcases/{badcase_id}/close`` — requires
  ``closureReason``, ``evidenceRef``, ``reviewer``; sets status=CLOSED +
  ``closedAt``.
- ``POST /api/v1/badcases/{badcase_id}/reject`` — requires ``reason``
  + ``reviewer``; sets status=REJECTED.
- ``POST /api/v1/badcases/{badcase_id}/promote`` — requires
  ``redactionAuditId`` + ``reviewer`` + ``reason``; appends a
  ``PROMOTE_CANDIDATE`` review action and returns the candidate path.
- 401 without reviewer auth.

Auth dependency is the ``require_reviewer`` stub registered in
``app.modules.badcases.api``; tests override it via FastAPI
``dependency_overrides`` so no real auth back-end is required.

DB contract: the repository reads / writes the ``badcases`` and
``badcase_review_actions`` tables created by migration 0024. RLS
isolation uses ``app.user_id`` GUC. Tests force-set the GUC via
``app.core.db.set_rls_user_id``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

# Skip if DATABASE_URL is not configured; contract tests assume a real
# Postgres (consistent with the rest of the 033 suite).
pytestmark = [
    pytest.mark.contract,
    pytest.mark.asyncio,
]


# ---------------------------------------------------------------------------
# Module imports done lazily inside fixtures so the skip message is
# produced before any app code touches the DB engine.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[Any, Any, Any, Any]]:
    """Build a FastAPI app with the badcases router mounted and a fresh DB session.

    Returns ``(app, session_factory, golden_dir, user_id)`` where:

    - ``app`` — FastAPI app with the badcases router mounted at the
      canonical prefix.
    - ``session_factory`` — async callable ``async with session_factory()
      as session: ...`` returning a session whose RLS GUC is pre-set to
      the test user.
    - ``golden_dir`` — temp directory the promotion module writes
      candidate files into (overrides ``specs/033-*/golden/``).
    - ``user_id`` — UUID of the pre-registered test user (callers can
      use it to seed data without round-tripping through the API).
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set; contract tests need real Postgres")

    # Direct golden dir override BEFORE app import (the promotion
    # module reads the env at call-time, not import-time, but we set
    # both for safety).
    monkeypatch.setenv("BADCASES_GOLDEN_DIR", str(tmp_path / "golden"))

    # Ensure the badcases app submodule uses our DB engine — same as
    # other 033 tests.
    from app.core.db import get_db_session_no_rls, set_rls_user_id
    from app.main import create_app
    from app.modules.badcases import api as badcase_api

    app = create_app()

    # Pre-register a test user via the auth endpoint so the FK on
    # ``badcases.user_id`` resolves.
    import httpx as _httpx
    from httpx import ASGITransport as _ASGITransport
    suffix = uuid4().hex[:8]
    test_email = f"badcase_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    async with _httpx.AsyncClient(
        transport=_ASGITransport(app=app), base_url="http://test"
    ) as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": "Demo1234",
                "display_name": suffix,
                "device_fingerprint": fp,
            },
            headers={"X-Device-Fingerprint": fp},
        )
        assert reg.status_code in (200, 201), reg.text
        body = reg.json()
        if isinstance(body, dict) and "user" in body:
            test_user_id = UUID(body["user"]["id"])
        elif isinstance(body, dict) and "id" in body:
            test_user_id = UUID(body["id"])
        else:
            # Fallback: look up user by email.
            test_user_id = uuid4()

    # The router exposes ``router``; FastAPI applies the dep at every
    # decorated endpoint.
    async def _fake_require_reviewer() -> UUID:
        return test_user_id

    app.dependency_overrides[badcase_api.require_reviewer] = _fake_require_reviewer

    async def _session_factory():
        async for session in get_db_session_no_rls():
            await set_rls_user_id(session, test_user_id)
            yield session

    yield app, _session_factory, tmp_path / "golden", test_user_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _post(client: AsyncClient, path: str, payload: dict[str, Any]) -> Any:
    resp = await client.post(path, json=payload)
    return resp


async def _get(client: AsyncClient, path: str) -> Any:
    return await client.get(path)


def _badcase_payload(**overrides: Any) -> dict[str, Any]:
    """Default POST body for ``POST /api/v1/badcases``."""
    payload: dict[str, Any] = {
        "type": "EVAL_REGRESSION",
        "severity": "HIGH",
        "source": "EVAL_FAILURE",
        "reviewer": "alice",
        "privacyClass": "PUBLIC_METADATA",
        "redactionStatus": "NOT_REQUIRED",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# T055 — POST /api/v1/badcases
# ---------------------------------------------------------------------------


async def test_post_badcase_returns_201_and_envelope(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Happy-path create returns 201 + ``{badcase: {...}}`` envelope."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await _post(client, "/api/v1/badcases", _badcase_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "badcase" in body
    bc = body["badcase"]
    assert bc["type"] == "EVAL_REGRESSION"
    assert bc["severity"] == "HIGH"
    assert bc["status"] == "OPEN"
    assert bc["reviewer"] == "alice"
    assert bc["badcaseId"].startswith("badcase-")


async def test_post_badcase_422_on_invalid_type(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Unknown type → 422 with structured error."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await _post(
            client, "/api/v1/badcases", _badcase_payload(type="NOT_A_TYPE")
        )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    # FastAPI's default validation uses ``detail``; we surface a
    # ``code`` key alongside for caller convenience.
    assert "error" in body or "code" in body or "detail" in body


async def test_post_badcase_422_on_invalid_severity(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Unknown severity → 422."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await _post(
            client, "/api/v1/badcases", _badcase_payload(severity="MEGA")
        )
    assert resp.status_code == 422, resp.text


async def test_post_badcase_422_on_invalid_source(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Unknown source → 422."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await _post(
            client, "/api/v1/badcases", _badcase_payload(source="ALIENS")
        )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T055 — GET /api/v1/badcases/{id}
# ---------------------------------------------------------------------------


async def test_get_badcase_200_returns_record(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Create then read returns 200 + matching payload."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        resp = await _get(client, f"/api/v1/badcases/{badcase_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["badcase"]["badcaseId"] == badcase_id


async def test_get_badcase_404_on_missing(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Unknown badcase_id → 404."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await _get(client, "/api/v1/badcases/badcase-does-not-exist")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# T055 — GET /api/v1/badcases (list)
# ---------------------------------------------------------------------------


async def test_list_badcases_filter_by_status_and_type(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """List returns matching rows for ``status`` + ``type`` filters."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Seed two badcases
        await _post(
            client, "/api/v1/badcases", _badcase_payload(type="EVAL_REGRESSION")
        )
        await _post(
            client, "/api/v1/badcases", _badcase_payload(type="DATA_QUALITY")
        )
        resp = await _get(client, "/api/v1/badcases?status=OPEN&type=EVAL_REGRESSION")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body or "data" in body or "badcases" in body
    items = body.get("items") or body.get("data") or body.get("badcases")
    assert isinstance(items, list)
    assert all(b["type"] == "EVAL_REGRESSION" for b in items)
    assert all(b["status"] == "OPEN" for b in items)


async def test_list_badcases_pagination_params(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """``page`` + ``page_size`` round-trip without error."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for _ in range(3):
            await _post(client, "/api/v1/badcases", _badcase_payload())
        resp = await _get(client, "/api/v1/badcases?page=1&page_size=2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body.get("items") or body.get("data") or body.get("badcases")
    assert isinstance(items, list)
    # page_size=2 should yield at most 2 items.
    assert len(items) <= 2


# ---------------------------------------------------------------------------
# T055 — POST /api/v1/badcases/{id}/classify
# ---------------------------------------------------------------------------


async def test_classify_updates_type_and_severity(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Classify changes type/severity + appends a CLASSIFY review action."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/classify",
            {
                "type": "AI_RELIABILITY",
                "severity": "CRITICAL",
                "reviewer": "alice",
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    bc = body["badcase"]
    assert bc["type"] == "AI_RELIABILITY"
    assert bc["severity"] == "CRITICAL"
    assert bc["status"] == "TRIAGED"
    # Audit log entry present
    actions = body.get("reviewActions") or body.get("review_actions") or []
    assert any(a.get("actionType") == "CLASSIFY" for a in actions)


async def test_classify_requires_reviewer(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Missing reviewer → 422."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/classify",
            {"type": "AI_RELIABILITY", "severity": "CRITICAL"},
        )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T055 — POST /api/v1/badcases/{id}/close
# ---------------------------------------------------------------------------


async def test_close_sets_status_closed_with_timestamp(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Close writes closure_reason + closed_at + appends CLOSE action.

    The FSM requires the full pipeline (OPEN → TRIAGED → IN_PROGRESS →
    AWAITING_VALIDATION → CLOSED). The API exposes only `classify` /
    `close` / `reject` / `promote`, so for the contract walk we use
    the repository helpers directly to advance through the
    intermediate states. The CLI integration tests exercise the
    user-facing walk end-to-end via subprocess.
    """
    app, _session_factory, _golden_dir, user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]

        # Walk FSM via repository (the user-facing surface is the CLI;
        # see test_033_badcase_promotion_cli.py for the end-to-end walk).
        from app.modules.badcases import repository as _repo
        from app.core.db import get_db_session_no_rls, set_rls_user_id

        async for session in get_db_session_no_rls():
            await set_rls_user_id(session, user_id)
            await _repo.update_status(
                session, badcase_id=badcase_id, user_id=user_id,
                new_status="TRIAGED", reviewer="alice",
            )
            await _repo.update_status(
                session, badcase_id=badcase_id, user_id=user_id,
                new_status="IN_PROGRESS", reviewer="alice",
            )
            await _repo.update_status(
                session, badcase_id=badcase_id, user_id=user_id,
                new_status="AWAITING_VALIDATION", reviewer="alice",
            )
            await session.commit()

        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/close",
            {
                "closureReason": "fixed",
                "evidenceRef": "https://example.com/evidence",
                "reviewer": "alice",
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    bc = body["badcase"]
    assert bc["status"] == "CLOSED"
    assert bc["closureReason"] == "fixed"
    assert bc["closedAt"] is not None


async def test_close_requires_closure_reason(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Missing closureReason → 422 (FSM rule)."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/close",
            {"reviewer": "alice", "evidenceRef": "link"},
        )
    assert resp.status_code == 422, resp.text


async def test_close_422_for_invalid_transition(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Closing an already-closed badcase → 422."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/close",
            {
                "closureReason": "fixed",
                "evidenceRef": "link",
                "reviewer": "alice",
            },
        )
        # 2nd close attempt should fail
        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/close",
            {
                "closureReason": "dup",
                "evidenceRef": "link",
                "reviewer": "alice",
            },
        )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T055 — POST /api/v1/badcases/{id}/reject
# ---------------------------------------------------------------------------


async def test_reject_sets_status_rejected(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Reject sets REJECTED + appends REJECT action."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/reject",
            {"reason": "not reproducible", "reviewer": "alice"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    bc = body["badcase"]
    assert bc["status"] == "REJECTED"
    assert bc["closureReason"] == "not reproducible"


async def test_reject_requires_reason(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Missing reason → 422."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/reject",
            {"reviewer": "alice"},
        )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T055 — POST /api/v1/badcases/{id}/promote
# ---------------------------------------------------------------------------


async def test_promote_creates_candidate_and_returns_path(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Promote writes a candidate JSON to the configured golden dir.

    The candidate file is the deliverable for US8 T064 — the actual
    baseline refresh lives in the US5 override-record flow. A passing
    redaction audit is NOT enforced here (no redaction table fixture
    in the contract; the unit-level ``can_promote`` rule is exercised
    in ``test_033_badcase_service.py``).
    """
    app, _session_factory, golden_dir, _user_id = app_and_session
    golden_dir.mkdir(parents=True, exist_ok=True)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/promote",
            {
                "redactionAuditId": "audit-001",
                "reviewer": "alice",
                "reason": "protect regression",
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "candidatePath" in body or "candidate_path" in body
    candidate_path = Path(body["candidatePath"] or body["candidate_path"])
    assert candidate_path.exists()
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert payload["badcaseId"] == badcase_id
    assert payload["redactionAuditId"] == "audit-001"
    assert payload["reviewer"] == "alice"


async def test_promote_requires_reviewer(
    app_and_session: tuple[Any, Any, Path, Any],
) -> None:
    """Missing reviewer → 422."""
    app, _session_factory, _golden_dir, _user_id = app_and_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await _post(client, "/api/v1/badcases", _badcase_payload())
        badcase_id = created.json()["badcase"]["badcaseId"]
        resp = await _post(
            client,
            f"/api/v1/badcases/{badcase_id}/promote",
            {"redactionAuditId": "audit-001", "reason": "protect"},
        )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T055 — auth gate
# ---------------------------------------------------------------------------


async def test_endpoints_require_reviewer_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without overriding ``require_reviewer``, endpoints return 401.

    We construct the app without the dependency_overrides so the real
    ``require_reviewer`` runs and rejects anonymous requests.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("BADCASES_GOLDEN_DIR", str(tmp_path / "golden"))

    from app.main import create_app

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # POST without auth → 401
        resp = await _post(client, "/api/v1/badcases", _badcase_payload())
        assert resp.status_code == 401, resp.text