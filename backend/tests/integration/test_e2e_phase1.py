"""Phase 1 E2E suite - exercises SC-001 + sections 3.1-3.7 of quickstart.md.

Hits the in-process FastAPI app via httpx.ASGITransport and the real
Postgres configured by `DATABASE_URL` + Redis at 127.0.0.1:6379.

Forces a NullPool engine so RLS `app.user_id` cannot leak across requests.

Run:
    cd backend && uv run pytest tests/integration/test_e2e_phase1.py -v
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import time
from collections.abc import AsyncGenerator

# Force NullPool before app imports happen.
os.environ.setdefault("DB_USE_NULL_POOL", "1")
# Raise rate limits so the test suite doesn't trip the per-IP cap.
os.environ.setdefault("RATE_LIMIT_AUTH_PER_MIN", "10000")
os.environ.setdefault("RATE_LIMIT_BUSINESS_PER_MIN", "10000")

import httpx
import pytest
from httpx import ASGITransport

from app.core.ids import new_uuid_v7
from app.main import app

# ---- helpers ----

def _device_id(fp: str) -> str:
    return hashlib.sha256(fp.encode()).hexdigest()


def _hdrs(access: str | None = None, fp: str = "fp-test") -> dict[str, str]:
    h = {
        "X-Device-Fingerprint": fp,
        "X-Request-ID": f"req-{new_uuid_v7()}",
    }
    if access:
        h["Authorization"] = f"Bearer {access}"
    return h


async def _register(c: httpx.AsyncClient, email: str, password: str = "Demo1234", fp: str = "fp-1") -> dict:
    r = await c.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "device_fingerprint": fp, "display_name": email.split("@")[0]},
        headers=_hdrs(fp=fp),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _login(c: httpx.AsyncClient, email: str, password: str = "Demo1234", fp: str = "fp-1") -> dict:
    r = await c.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "device_fingerprint": fp},
        headers=_hdrs(fp=fp),
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _create_branch(c: httpx.AsyncClient, access: str, fp: str, **payload) -> dict:
    r = await c.post("/api/v1/resume-branches", json=payload, headers=_hdrs(access, fp))
    assert r.status_code in (200, 201), r.text
    return r.json()["branch"]


async def _create_block(c: httpx.AsyncClient, access: str, fp: str, branch_id: str, **payload) -> dict:
    r = await c.post(
        f"/api/v1/resume-branches/{branch_id}/blocks",
        json=payload,
        headers=_hdrs(access, fp),
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["block"]


async def _list_blocks(c: httpx.AsyncClient, access: str, fp: str, branch_id: str) -> list[dict]:
    r = await c.get(f"/api/v1/resume-branches/{branch_id}/blocks", headers=_hdrs(access, fp))
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ---- fixture ----

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # ASGITransport doesn't run lifespan by default; trigger DB init.
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as _:
            pass
        yield c


# ---- §2 SC-001: 5-minute happy path ----

@pytest.mark.asyncio
async def test_sc001_happy_path(client: httpx.AsyncClient) -> None:
    """SC-001: register → login → me → create branch → 3 blocks → save version → list versions."""
    started = time.monotonic()
    suffix = secrets.token_hex(4)
    email = f"sc001-{suffix}@intercraft.io"
    fp = f"fp-sc001-{suffix}"

    # 1. Register
    reg = await _register(client, email, fp=fp)
    assert "user" in reg and "tokens" in reg
    access = reg["tokens"]["access_token"]
    user_id = reg["user"]["id"]

    # 2. Login (same device — re-login is allowed, prior session is replaced)
    login = await _login(client, email, fp=fp)
    assert login["user"]["id"] == user_id
    access = login["tokens"]["access_token"]

    # 3. /users/me
    r = await client.get("/api/v1/users/me", headers=_hdrs(access, fp))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == user_id

    # 4. Create main branch
    branch = await _create_branch(client, access, fp, name="核心简历", is_main=True)
    branch_id = branch["id"]

    # 5. Create 3 blocks
    created_block_ids: list[str] = []
    for type_, title, content in [
        ("heading", reg["user"]["display_name"], ""),
        ("summary", None, "3 年 React/TS 经验"),
        ("experience", "字节前端", "抖音创作者平台"),
    ]:
        block = await _create_block(
            client, access, fp, branch_id, type=type_, title=title, content_md=content, meta=None
        )
        created_block_ids.append(block["id"])

    # 6. Save version
    r = await client.post(
        f"/api/v1/resume-branches/{branch_id}/versions",
        json={"label": "v1"},
        headers=_hdrs(access, fp),
    )
    assert r.status_code in (200, 201), r.text
    v1 = r.json()["version"]
    assert v1["version_no"] >= 1

    # 7. List versions
    r = await client.get(
        f"/api/v1/resume-branches/{branch_id}/versions", headers=_hdrs(access, fp)
    )
    assert r.status_code == 200, r.text
    versions = r.json()["data"]
    assert any(v["version_no"] == v1["version_no"] for v in versions)

    elapsed = time.monotonic() - started
    assert elapsed < 60, f"SC-001 took {elapsed:.1f}s (target 5 min)"


# ---- §3.1 5-device eviction ----

@pytest.mark.asyncio
async def test_3_1_sixth_login_evicts_oldest(client: httpx.AsyncClient) -> None:
    suffix = secrets.token_hex(4)
    email = f"evict-{suffix}@intercraft.io"
    fp = f"fp-evict-{suffix}"
    await _register(client, email, fp=fp)
    fp_base = f"fp-evict-{suffix}-dev"

    # Login from 5 distinct devices — register already created session #1, so
    # logins 0..3 fill us to 5 active sessions.
    for i in range(5):
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Demo1234", "device_fingerprint": f"{fp_base}-{i}"},
            headers=_hdrs(fp=f"{fp_base}-{i}"),
        )
        assert r.status_code == 200, f"login #{i+1}: {r.text}"

    # 6th distinct device — must evict the oldest session
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Demo1234", "device_fingerprint": f"{fp_base}-5"},
        headers=_hdrs(fp=f"{fp_base}-5"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["evicted_session_id"] is not None

    # List sessions on a separate device (list itself creates a new session,
    # which evicts another oldest) — we expect at most 5 active.
    access = (await _login(client, email, fp=f"{fp_base}-list"))["tokens"]["access_token"]
    r = await client.get("/api/v1/users/me/sessions", headers=_hdrs(access, fp=f"{fp_base}-list"))
    assert r.status_code == 200, r.text
    sessions = r.json()["sessions"]
    assert len(sessions) <= 5, f"expected ≤5 active, got {len(sessions)}"


# ---- §3.2 RLS isolation ----

@pytest.mark.asyncio
async def test_3_2_rls_isolation(client: httpx.AsyncClient) -> None:
    suffix = secrets.token_hex(4)
    user_a = await _register(client, f"a-{suffix}@x.io", fp=f"fp-a-{suffix}")
    user_b = await _register(client, f"b-{suffix}@x.io", fp=f"fp-b-{suffix}")
    access_a = user_a["tokens"]["access_token"]
    access_b = user_b["tokens"]["access_token"]

    # A creates a branch
    branch = await _create_branch(client, access_a, f"fp-a-{suffix}", name="A 的简历", is_main=True)
    a_branch_id = branch["id"]

    # B lists branches — must not see A's
    r = await client.get(
        "/api/v1/resume-branches", headers=_hdrs(access_b, f"fp-b-{suffix}")
    )
    assert r.status_code == 200, r.text
    branch_ids = [b["id"] for b in r.json()["data"]]
    assert a_branch_id not in branch_ids, "RLS leak: B can see A's branch"

    # B tries to GET A's branch by id — must 404
    r = await client.get(
        f"/api/v1/resume-branches/{a_branch_id}",
        headers=_hdrs(access_b, f"fp-b-{suffix}"),
    )
    assert r.status_code == 404, f"RLS leak: B can GET A's branch — {r.status_code} {r.text}"


# ---- §3.3 COW: create branch from parent clones blocks ----

@pytest.mark.asyncio
async def test_3_3_cow_clones_blocks(client: httpx.AsyncClient) -> None:
    suffix = secrets.token_hex(4)
    user = await _register(client, f"cow-{suffix}@x.io", fp=f"fp-cow-{suffix}")
    access = user["tokens"]["access_token"]
    fp = f"fp-cow-{suffix}"

    # main branch + 2 blocks
    main = await _create_branch(client, access, fp, name="main", is_main=True)
    main_id = main["id"]
    for t, c in [("heading", "h"), ("summary", "s")]:
        await _create_block(client, access, fp, main_id, type=t, title=t, content_md=c, meta=None)

    # child branch with parent=main
    child = await _create_branch(
        client, access, fp, name="child", parent_id=main_id, is_main=False
    )
    child_id = child["id"]

    # child must have 2 cloned blocks
    blocks = await _list_blocks(client, access, fp, child_id)
    assert len(blocks) == 2


# ---- §3.4 Rollback creates new branch (does not mutate original) ----

@pytest.mark.asyncio
async def test_3_4_rollback_creates_new_branch(client: httpx.AsyncClient) -> None:
    suffix = secrets.token_hex(4)
    user = await _register(client, f"rb-{suffix}@x.io", fp=f"fp-rb-{suffix}")
    access = user["tokens"]["access_token"]
    fp = f"fp-rb-{suffix}"

    branch = await _create_branch(client, access, fp, name="main", is_main=True)
    branch_id = branch["id"]
    await _create_block(
        client, access, fp, branch_id, type="summary", title=None, content_md="v1 content", meta=None
    )
    # save v1
    r = await client.post(
        f"/api/v1/resume-branches/{branch_id}/versions", json={"label": "v1"}, headers=_hdrs(access, fp)
    )
    assert r.status_code in (200, 201), r.text
    v1 = r.json()["version"]
    v1_no = v1["version_no"]

    # mutate (add a block)
    await _create_block(
        client, access, fp, branch_id, type="experience", title="new", content_md="v2 content", meta=None
    )

    # rollback to v1
    r = await client.post(
        f"/api/v1/resume-branches/{branch_id}/versions/{v1_no}/rollback",
        json={"name": "rolled-back"},
        headers=_hdrs(access, fp),
    )
    assert r.status_code in (200, 201), r.text
    new_branch_id = r.json()["new_branch_id"]
    assert new_branch_id != branch_id

    # new branch has only the v1 blocks (1, not 2)
    new_blocks = await _list_blocks(client, access, fp, new_branch_id)
    assert len(new_blocks) == 1
    assert new_blocks[0]["content_md"] == "v1 content"

    # original branch untouched (still has 2 blocks)
    orig_blocks = await _list_blocks(client, access, fp, branch_id)
    assert len(orig_blocks) == 2


# ---- §3.5 Fractional indexing reorder ----

@pytest.mark.asyncio
async def test_3_5_reorder_preserves_others(client: httpx.AsyncClient) -> None:
    suffix = secrets.token_hex(4)
    user = await _register(client, f"reord-{suffix}@x.io", fp=f"fp-reord-{suffix}")
    access = user["tokens"]["access_token"]
    fp = f"fp-reord-{suffix}"

    branch = await _create_branch(client, access, fp, name="main", is_main=True)
    branch_id = branch["id"]
    ids: list[str] = []
    for t in ("a", "b", "c"):
        # 'a', 'b', 'c' are not valid block types — use 'custom' with title
        block = await _create_block(
            client, access, fp, branch_id, type="custom", title=t, content_md=t, meta=None
        )
        ids.append(block["id"])

    # Capture original order indices for b and c.
    before = {b["id"]: b["order_index"] for b in await _list_blocks(client, access, fp, branch_id)}

    # Move block[0] (a) to between b and c.
    r = await client.patch(
        f"/api/v1/resume-blocks/{ids[0]}/reorder",
        json={"block_id": ids[0], "prev_id": ids[1], "next_id": ids[2]},
        headers=_hdrs(access, fp),
    )
    assert r.status_code in (200, 201), r.text

    # Other blocks' order indices unchanged.
    after = {b["id"]: b["order_index"] for b in await _list_blocks(client, access, fp, branch_id)}
    assert after[ids[1]] == before[ids[1]], "b's index was rewritten"
    assert after[ids[2]] == before[ids[2]], "c's index was rewritten"


# ---- §3.6 Silent refresh ----

@pytest.mark.asyncio
async def test_3_6_refresh_rotates_invalidates_old(client: httpx.AsyncClient) -> None:
    suffix = secrets.token_hex(4)
    user = await _register(client, f"ref-{suffix}@x.io", fp=f"fp-ref-{suffix}")
    refresh = user["tokens"]["refresh_token"]
    fp = f"fp-ref-{suffix}"

    # First refresh — OK
    r = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
        headers=_hdrs(fp=fp),
    )
    assert r.status_code == 200, r.text

    # Reusing old refresh — reuse detection must reject (any non-2xx).
    r = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
        headers=_hdrs(fp=fp),
    )
    assert r.status_code >= 400, f"expected rejection on reuse, got {r.status_code} {r.text}"


# ---- §3.7 Health + metrics ----

@pytest.mark.asyncio
async def test_3_7_health_and_metrics(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code in (200, 503)  # 200 if DB is up; 503 if down
    body = r.json()
    assert "db" in body and "redis" in body

    r = await client.get("/metrics")
    assert r.status_code == 200, r.text
    assert b"http_requests_total" in r.content
    assert b"auth_login_attempts_total" in r.content
