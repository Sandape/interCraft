"""REQ-039 B2 r2 review fix — `since` query param binding + SQL where contract.

Reviewer found that ``GET /traces?since=<ts>`` was silently ignored because
the FastAPI handler did not declare a ``since`` query param. These tests
guard the contract from both sides:

1. ``list_traces`` service binds ``since`` into the SQL params so the
   ``WHERE created_at >= :since`` predicate actually filters rows.
2. The FastAPI route accepts ``?since=...`` and forwards it to the
   service layer.

The reviewer explicitly flagged FastAPI's silent-ignore behaviour as the
real bug; the unit test below is the regression guard.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.modules.admin_console import service
from app.modules.admin_console.api import get_caller_user_id, router


# ---------------------------------------------------------------------------
# Fake session helpers — reuse the pattern from test_039_trace_listing
# ---------------------------------------------------------------------------


class _Row:
    def __init__(self, data: dict):
        self._mapping = data


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    """Records the SQL text + bound params so the test can assert on them."""

    def __init__(self, rows):
        self._rows = rows
        self.executed: list = []

    async def execute(self, stmt):  # noqa: ANN001 - signature matches AsyncSession
        self.executed.append(stmt)
        params = getattr(stmt, "_bindparams", {}) or {}
        try:
            params_dict = dict(params.items())  # type: ignore[union-attr]
        except Exception:
            params_dict = {}
        extracted: dict[str, object] = {}
        for k, v in params_dict.items():
            extracted[k] = getattr(v, "value", v)
        return _FakeResult(self._rows)


def _row(ts: str = "2026-07-01T00:00:00"):
    return _Row(
        {
            "id": uuid4(),
            "task_id": uuid4(),
            "task_type": "interview",
            "prompt_version": "v1",
            "model": "deepseek-v4-pro",
            "status": "success",
            "error_message": None,
            "replay_of": None,
            "created_at": SimpleNamespace(isoformat=lambda: ts),
            "updated_at": SimpleNamespace(isoformat=lambda: ts),
        }
    )


# ---------------------------------------------------------------------------
# 1. service.list_traces binds `since` into SQL params (FR-001 contract)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_list_traces_binds_since_into_sql_params():
    """`since` must be passed to ``bindparams`` so SQLAlchemy emits the WHERE clause."""
    fake = _FakeSession([_row()])
    since_ts = datetime(2026, 6, 1, tzinfo=timezone.utc)
    await service.list_traces(fake, limit=50, since=since_ts)

    assert len(fake.executed) == 1, "session.execute must be called exactly once"
    stmt = fake.executed[0]
    text = str(stmt)
    # The WHERE clause must include the since predicate.
    assert "created_at >= :since" in text, (
        f"service.list_traces must include `created_at >= :since` predicate; got: {text}"
    )
    # And the params dict must carry the since value (under _bindparams).
    params = getattr(stmt, "_bindparams", {}) or {}
    try:
        params_dict = dict(params.items())  # type: ignore[union-attr]
    except Exception:
        params_dict = {}
    assert "since" in params_dict, (
        f"`since` must be bound into the statement params; got keys: {list(params_dict)}"
    )
    bound_value = getattr(params_dict["since"], "value", params_dict["since"])
    assert bound_value == since_ts


@pytest.mark.asyncio
async def test_service_list_traces_omits_since_clause_when_none():
    """When since=None, the WHERE clause must not include the since predicate."""
    fake = _FakeSession([_row(), _row()])
    await service.list_traces(fake, limit=100)
    text = str(fake.executed[0])
    assert "created_at >= :since" not in text, (
        f"when since=None the predicate must be omitted; got: {text}"
    )


# ---------------------------------------------------------------------------
# 2. FastAPI route accepts ?since=<ts> and forwards it to the service.
# ---------------------------------------------------------------------------


def _build_test_app():
    """Build a minimal FastAPI app with the admin_console router mounted.

    We monkey-patch `service.list_traces` (the symbol imported into the
    api module) with a spy that records the kwargs it was called with
    but does NOT recursively call the real implementation (which would
    infinite-loop because the spy lives on the same attribute).
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin-console/observability")

    async def _fake_session():
        yield _FakeSession([_row()])

    captured: dict = {}

    async def _spy_list_traces(session, **kwargs):
        captured["kwargs"] = kwargs
        return []

    from app.modules.admin_console import api as api_module

    app.dependency_overrides[api_module._db_session_with_rls] = _fake_session
    app.dependency_overrides[api_module.get_caller_user_id] = lambda: uuid4()
    app.dependency_overrides[get_caller_user_id] = lambda: uuid4()

    # Patch the `service` symbol as imported by the api module.
    original = api_module.service.list_traces
    api_module.service.list_traces = _spy_list_traces  # type: ignore[assignment]
    return app, captured, api_module, original


@pytest.mark.asyncio
async def test_route_accepts_since_and_forwards_to_service():
    """The FastAPI route must accept `?since=<iso ts>` and pass it through."""
    app, captured, api_module, original = _build_test_app()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/admin-console/observability/traces",
                params={"limit": 50, "since": "2026-06-01T00:00:00Z"},
            )
        assert r.status_code == 200, (
            f"route must accept `?since=` without 422; got {r.status_code} body={r.text}"
        )
        # FastAPI parses `2026-06-01T00:00:00Z` to a tz-aware datetime.
        kwargs = captured["kwargs"]
        assert "since" in kwargs, f"`since` must be forwarded as a kwarg; got {list(kwargs)}"
        since_val = kwargs["since"]
        assert isinstance(since_val, datetime), (
            f"`since` must be parsed as datetime; got {type(since_val).__name__}"
        )
        # Also assert other expected kwargs are forwarded unchanged.
        assert kwargs["limit"] == 50
        assert kwargs["task_type"] is None
        assert kwargs["status_filter"] is None
    finally:
        api_module.service.list_traces = original  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_route_rejects_unknown_query_param_consistent():
    """Sanity check: FastAPI does NOT 422 on unknown query params (silent ignore).

    This documents the very behavior the reviewer flagged — that's why
    the contract test above (route_accepts_since) exists: we need a
    *positive* test that the known param is wired, not a 422 contract.
    """
    app, _, api_module, original = _build_test_app()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/admin-console/observability/traces",
                params={"limit": 10, "made_up_param": "x"},
            )
        # FastAPI silently ignores `made_up_param` — no 422. This is the
        # bug behavior; document it so future readers understand why we
        # need a positive integration assertion for `since`.
        assert r.status_code == 200
    finally:
        api_module.service.list_traces = original  # type: ignore[assignment]