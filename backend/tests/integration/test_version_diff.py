"""Integration tests for the version diff endpoint (spec 027 US7 FR-049/050).

Exercises the full HTTP path:
  GET /api/v1/resume-branches/{branch_id}/versions/{v1}/diff/{v2}

Covers:
  - 200 + correct diff payload when both versions exist
  - 404 when either version is missing
  - 404 when the branch belongs to a different user (RLS isolation)
  - 422 when v1 == v2
"""
from __future__ import annotations

import asyncio
import secrets
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


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


async def _create_branch(c, access, fp, **payload) -> dict:
    r = await c.post("/api/v1/resume-branches", json=payload, headers=_hdrs(access, fp))
    assert r.status_code in (200, 201), r.text
    return r.json()["branch"]


async def _create_block(c, access, fp, branch_id, **payload) -> dict:
    r = await c.post(
        f"/api/v1/resume-branches/{branch_id}/blocks",
        json=payload,
        headers=_hdrs(access, fp),
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["block"]


async def _patch_block(c, access, fp, block_id, **payload) -> dict:
    r = await c.patch(
        f"/api/v1/resume-blocks/{block_id}",
        json=payload,
        headers=_hdrs(access, fp),
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["block"]


async def _save_version(c, access, fp, branch_id, label: str = "snap") -> int:
    r = await c.post(
        f"/api/v1/resume-branches/{branch_id}/versions",
        json={"label": label},
        headers=_hdrs(access, fp),
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["version"]["version_no"]


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_diff_returns_classified_blocks(client: httpx.AsyncClient) -> None:
    """v1 → modify + add blocks → v2; assert add/modified/unchanged classification."""
    suffix = secrets.token_hex(4)
    email = f"diff-{suffix}@intercraft.io"
    fp = f"fp-diff-{suffix}"
    reg = await _register(client, email, fp=fp)
    access = reg["tokens"]["access_token"]

    branch = await _create_branch(client, access, fp, name="diff 主简历", is_main=True)
    branch_id = branch["id"]

    # Initial 2 blocks (heading + experience)
    heading = await _create_block(
        client, access, fp, branch_id, type="heading", title="姓名", content_md="张三"
    )
    exp = await _create_block(
        client, access, fp, branch_id,
        type="experience", title="字节前端", content_md="抖音创作者平台",
    )

    # v1 — initial snapshot
    v1 = await _save_version(client, access, fp, branch_id, "v1")

    # Modify experience content, add a new skill block
    await _patch_block(client, access, fp, exp["id"], content_md="抖音 + TikTok 创作者平台")
    await _create_block(
        client, access, fp, branch_id,
        type="skill", title="技能", content_md="TypeScript / React",
    )

    # v2 — second snapshot
    v2 = await _save_version(client, access, fp, branch_id, "v2")

    r = await client.get(
        f"/api/v1/resume-branches/{branch_id}/versions/{v1}/diff/{v2}",
        headers=_hdrs(access, fp),
    )
    assert r.status_code == 200, r.text
    diff = r.json()["diff"]
    assert diff["old_version_no"] == v1
    assert diff["new_version_no"] == v2

    blocks_by_op = {b["op"]: b for b in diff["blocks"]}
    assert "added" in blocks_by_op, f"missing 'added' op in {[b['op'] for b in diff['blocks']]}"
    assert "modified" in blocks_by_op
    assert "unchanged" in blocks_by_op
    # The experience block was modified
    modified = blocks_by_op["modified"]
    assert modified["old_block"]["content_md"] == "抖音创作者平台"
    assert modified["new_block"]["content_md"] == "抖音 + TikTok 创作者平台"
    # line_diff has at least one removed + one added entry
    kinds = {e["kind"] for e in modified["line_diff"]}
    assert "removed" in kinds
    assert "added" in kinds

    # added block has no old_block, no line_diff
    added = blocks_by_op["added"]
    assert added["old_block"] is None
    assert added["line_diff"] is None

    # Summary counts match the block list
    summary = diff["summary"]
    assert summary["added"] >= 1
    assert summary["modified"] >= 1
    assert summary["unchanged"] >= 1


@pytest.mark.asyncio
async def test_diff_404_when_version_missing(client: httpx.AsyncClient) -> None:
    suffix = secrets.token_hex(4)
    email = f"miss-{suffix}@intercraft.io"
    fp = f"fp-miss-{suffix}"
    reg = await _register(client, email, fp=fp)
    access = reg["tokens"]["access_token"]

    branch = await _create_branch(client, access, fp, name="miss", is_main=True)
    branch_id = branch["id"]
    v1 = await _save_version(client, access, fp, branch_id, "v1")

    # v2 doesn't exist
    r = await client.get(
        f"/api/v1/resume-branches/{branch_id}/versions/{v1}/diff/9999",
        headers=_hdrs(access, fp),
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_diff_404_across_users(client: httpx.AsyncClient) -> None:
    """User B must not be able to diff user A's branch versions (RLS)."""
    suffix = secrets.token_hex(4)
    user_a = await _register(client, f"a-{suffix}@x.io", fp=f"fp-a-{suffix}")
    user_b = await _register(client, f"b-{suffix}@x.io", fp=f"fp-b-{suffix}")
    access_a = user_a["tokens"]["access_token"]
    access_b = user_b["tokens"]["access_token"]

    a_branch = await _create_branch(client, access_a, f"fp-a-{suffix}", name="A", is_main=True)
    a_branch_id = a_branch["id"]
    await _save_version(client, access_a, f"fp-a-{suffix}", a_branch_id, "v1")
    await _save_version(client, access_a, f"fp-a-{suffix}", a_branch_id, "v2")

    r = await client.get(
        f"/api/v1/resume-branches/{a_branch_id}/versions/1/diff/2",
        headers=_hdrs(access_b, f"fp-b-{suffix}"),
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_diff_422_when_versions_equal(client: httpx.AsyncClient) -> None:
    suffix = secrets.token_hex(4)
    email = f"eq-{suffix}@intercraft.io"
    fp = f"fp-eq-{suffix}"
    reg = await _register(client, email, fp=fp)
    access = reg["tokens"]["access_token"]

    branch = await _create_branch(client, access, fp, name="eq", is_main=True)
    branch_id = branch["id"]
    v1 = await _save_version(client, access, fp, branch_id, "v1")

    r = await client.get(
        f"/api/v1/resume-branches/{branch_id}/versions/{v1}/diff/{v1}",
        headers=_hdrs(access, fp),
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_diff_branch_attributes(client: httpx.AsyncClient) -> None:
    """Renaming the branch between versions shows up in branch_diff."""
    suffix = secrets.token_hex(4)
    email = f"bd-{suffix}@intercraft.io"
    fp = f"fp-bd-{suffix}"
    reg = await _register(client, email, fp=fp)
    access = reg["tokens"]["access_token"]

    branch = await _create_branch(client, access, fp, name="原名", is_main=True)
    branch_id = branch["id"]
    v1 = await _save_version(client, access, fp, branch_id, "v1")

    r = await client.patch(
        f"/api/v1/resume-branches/{branch_id}",
        json={"name": "新名"},
        headers=_hdrs(access, fp),
    )
    assert r.status_code == 200, r.text

    v2 = await _save_version(client, access, fp, branch_id, "v2")

    r = await client.get(
        f"/api/v1/resume-branches/{branch_id}/versions/{v1}/diff/{v2}",
        headers=_hdrs(access, fp),
    )
    assert r.status_code == 200, r.text
    diff = r.json()["diff"]
    assert diff["branch_diff"]["name"] is not None
    assert "原名" in diff["branch_diff"]["name"]
    assert "新名" in diff["branch_diff"]["name"]