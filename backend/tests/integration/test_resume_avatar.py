"""Integration tests for US9 resume branch avatar endpoints.

Covers:
- POST /avatar: happy path (200), oversize (413), bad MIME (415)
- GET /avatar: served bytes match what was uploaded (compressed)
- DELETE /avatar: 200 + GET → 404
- POST /avatar/inherit: copy parent avatar fields
- PATCH branch: avatar_size / position / shape field validation
"""
from __future__ import annotations

import io
from uuid import UUID, uuid4

import httpx
import pytest
from PIL import Image

pytestmark = [pytest.mark.integration]


# ---- fixtures: tiny PNG/JPEG generated on the fly ----


def _png_bytes(width: int = 64, height: int = 64, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width: int = 64, height: int = 64, color: tuple[int, int, int] = (0, 255, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _webp_bytes(width: int = 64, height: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (0, 0, 255)).save(buf, format="WEBP", quality=80)
    return buf.getvalue()


def _oversize_bytes() -> bytes:
    """Generate a JPEG slightly over the 2 MB cap (settings.avatar_max_bytes)."""
    # 2 MB cap is 2_097_152 bytes. We pad via quality iteration.
    img = Image.new("RGB", (2000, 2000), (123, 45, 67))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=98)
    data = buf.getvalue()
    if len(data) >= 2_097_152:
        return data
    # Append a comment-style header so size exceeds the cap.
    return data + b"\x00" * (2_097_152 - len(data) + 1)


def _files_payload(name: str, raw: bytes, content_type: str) -> list[tuple]:
    return [("file", (name, raw, content_type))]


# ---- helpers: branch lifecycle ----


async def _create_branch(client: httpx.AsyncClient, headers: dict, *, name: str = "测试简历") -> str:
    resp = await client.post(
        "/api/v1/resume-branches",
        headers=headers,
        json={"name": name, "theme_id": "default", "accent_color": "#39393a"},
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    return body["branch"]["id"]


# ---- tests ----


@pytest.mark.asyncio
async def test_avatar_upload_png_happy_path(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)

    resp = await client.post(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
        files=_files_payload("avatar.png", _png_bytes(), "image/png"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["branch_id"] == branch_id
    assert body["url"].startswith(f"/api/v1/resume-branches/{branch_id}/avatar")

    # GET back the bytes
    get_resp = await client.get(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
    )
    assert get_resp.status_code == 200, get_resp.text
    # Backend may Pillow-compress; we only assert it's a valid JPEG/PNG image.
    img = Image.open(io.BytesIO(get_resp.content))
    img.verify()


@pytest.mark.asyncio
async def test_avatar_upload_jpeg_happy_path(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    resp = await client.post(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
        files=_files_payload("avatar.jpg", _jpeg_bytes(), "image/jpeg"),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_avatar_upload_webp_happy_path(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    resp = await client.post(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
        files=_files_payload("avatar.webp", _webp_bytes(), "image/webp"),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_avatar_upload_oversize_rejected_413(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    resp = await client.post(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
        files=_files_payload("big.jpg", _oversize_bytes(), "image/jpeg"),
    )
    assert resp.status_code == 413, resp.text


@pytest.mark.asyncio
async def test_avatar_upload_unsupported_format_rejected_415(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    resp = await client.post(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
        files=_files_payload("doc.gif", b"GIF89a" + b"\x00" * 64, "image/gif"),
    )
    assert resp.status_code == 415, resp.text


@pytest.mark.asyncio
async def test_avatar_delete_and_reget_404(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    upload = await client.post(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
        files=_files_payload("a.png", _png_bytes(), "image/png"),
    )
    assert upload.status_code == 200

    delete = await client.delete(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
    )
    assert delete.status_code == 200

    again = await client.get(
        f"/api/v1/resume-branches/{branch_id}/avatar",
        headers=user_a_headers,
    )
    assert again.status_code == 404


@pytest.mark.asyncio
async def test_avatar_inherit_copies_from_parent(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    parent_id = await _create_branch(client, user_a_headers, name="父级简历")
    # Upload parent avatar
    resp = await client.post(
        f"/api/v1/resume-branches/{parent_id}/avatar",
        headers=user_a_headers,
        files=_files_payload("p.png", _png_bytes(), "image/png"),
    )
    assert resp.status_code == 200

    # Create derived branch
    derived = await client.post(
        "/api/v1/resume-branches",
        headers=user_a_headers,
        json={
            "name": "派生简历",
            "parent_id": parent_id,
            "theme_id": "default",
            "accent_color": "#39393a",
        },
    )
    assert derived.status_code in (200, 201), derived.text
    child_id = derived.json()["branch"]["id"]

    inherit = await client.post(
        f"/api/v1/resume-branches/{child_id}/avatar/inherit",
        headers=user_a_headers,
    )
    assert inherit.status_code == 200, inherit.text

    # GET child avatar should now succeed.
    child_get = await client.get(
        f"/api/v1/resume-branches/{child_id}/avatar",
        headers=user_a_headers,
    )
    assert child_get.status_code == 200


@pytest.mark.asyncio
async def test_avatar_inherit_no_parent_returns_422(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers, name="主简历")
    resp = await client.post(
        f"/api/v1/resume-branches/{branch_id}/avatar/inherit",
        headers=user_a_headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_avatar_upload_branch_not_found_returns_404(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    fake = uuid4()
    resp = await client.post(
        f"/api/v1/resume-branches/{fake}/avatar",
        headers=user_a_headers,
        files=_files_payload("a.png", _png_bytes(), "image/png"),
    )
    assert resp.status_code == 404, resp.text


# ---- PATCH field validation ----


@pytest.mark.asyncio
async def test_patch_avatar_size_out_of_range_422(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    resp = await client.patch(
        f"/api/v1/resume-branches/{branch_id}",
        headers=user_a_headers,
        json={"avatar_size": 10},
    )
    assert resp.status_code == 422, resp.text

    resp2 = await client.patch(
        f"/api/v1/resume-branches/{branch_id}",
        headers=user_a_headers,
        json={"avatar_size": 300},
    )
    assert resp2.status_code == 422, resp2.text


@pytest.mark.asyncio
async def test_patch_avatar_position_invalid_422(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    resp = await client.patch(
        f"/api/v1/resume-branches/{branch_id}",
        headers=user_a_headers,
        json={"avatar_position": "nowhere"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_patch_avatar_shape_invalid_422(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    resp = await client.patch(
        f"/api/v1/resume-branches/{branch_id}",
        headers=user_a_headers,
        json={"avatar_shape": "star"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_patch_avatar_fields_persists(
    client: httpx.AsyncClient, user_a_headers
) -> None:
    branch_id = await _create_branch(client, user_a_headers)
    resp = await client.patch(
        f"/api/v1/resume-branches/{branch_id}",
        headers=user_a_headers,
        json={"avatar_size": 120, "avatar_position": "top", "avatar_shape": "rounded"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    branch = body.get("branch") or body
    assert branch["avatar_size"] == 120
    assert branch["avatar_position"] == "top"
    assert branch["avatar_shape"] == "rounded"
