"""Integration tests for avatar upload/remove (Feature 013).

Covers the contract in specs/013-user-avatar/contracts/avatar-api.md:
- happy path upload (200) + 后续 GET 可读
- 错误 MIME (415)
- 超过 2MB (413)
- 超过 2048 像素 (422)
- 跨用户读别人头像 (404)
- 移除后 DELETE → 200 / GET 自身头像 → 404
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

pytest_plugins = ("tests.conftest",)

# Reuse the E2E fixtures so the same image bytes work end-to-end.
FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "e2e" / "_fixtures"
SAMPLE_PNG = FIXTURES / "sample-avatar.png"
TOO_LARGE_PNG = FIXTURES / "avatar-too-large.png"
TOO_WIDE_PNG = FIXTURES / "avatar-too-wide.png"


def _file_payload(path: Path, content_type: str = "image/png") -> tuple[str, tuple[str, bytes, str]]:
    """Return httpx `files` entry: (field_name, (filename, bytes, content_type))."""
    return ("file", (path.name, path.read_bytes(), content_type))


def _files_payload(path: Path) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [_file_payload(path)]


@pytest.mark.integration
class TestAvatarUpload:
    async def test_upload_happy_path(self, client: httpx.AsyncClient, user_a_headers) -> None:  # type: ignore[no-untyped-def]
        # sanity: fixtures exist
        assert SAMPLE_PNG.exists(), f"missing fixture {SAMPLE_PNG}"

        resp = await client.post(
            "/api/v1/users/me/avatar",
            headers=user_a_headers,
            files=_files_payload(SAMPLE_PNG),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["content_type"] == "image/png"
        assert body["byte_size"] == SAMPLE_PNG.stat().st_size
        assert body["url"].startswith("/api/v1/users/me/avatar/")
        avatar_id = body["avatar_id"]

        # GET the avatar back as the same user → 200 + body bytes match
        get_resp = await client.get(
            f"/api/v1/users/me/avatar/{avatar_id}",
            headers=user_a_headers,
        )
        assert get_resp.status_code == 200, get_resp.text
        assert get_resp.content == SAMPLE_PNG.read_bytes()

    async def test_upload_wrong_mime(self, client: httpx.AsyncClient, user_a_headers) -> None:  # type: ignore[no-untyped-def]
        # Send a GIF file — should fail sniff as JPG/PNG
        gif_bytes = b"GIF89a" + b"\x00" * 100
        resp = await client.post(
            "/api/v1/users/me/avatar",
            headers=user_a_headers,
            files=[("file", ("avatar.gif", gif_bytes, "image/gif"))],
        )
        assert resp.status_code == 415, resp.text
        body = resp.json()
        # Global error envelope shape: {"error": {"code": "http.415", "message": "..."}}
        assert body["error"]["code"] == "http.415"
        # The inner service code is preserved in the message string
        assert "UNSUPPORTED_FORMAT" in body["error"]["message"]

    async def test_upload_oversize(self, client: httpx.AsyncClient, user_a_headers) -> None:  # type: ignore[no-untyped-def]
        assert TOO_LARGE_PNG.exists()
        # Limit is 2 MB; this fixture is ~6.8 MB.
        resp = await client.post(
            "/api/v1/users/me/avatar",
            headers=user_a_headers,
            files=_files_payload(TOO_LARGE_PNG),
        )
        # May be 413 (router pre-check) or 400 (body parse limit). The router
        # pre-check returns 413 with our envelope.
        assert resp.status_code in (413, 400), resp.text

    async def test_upload_over_dimension(self, client: httpx.AsyncClient, user_a_headers) -> None:  # type: ignore[no-untyped-def]
        assert TOO_WIDE_PNG.exists()
        resp = await client.post(
            "/api/v1/users/me/avatar",
            headers=user_a_headers,
            files=_files_payload(TOO_WIDE_PNG),
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert body["error"]["code"] == "http.422"
        assert "DIMENSION_TOO_LARGE" in body["error"]["message"]

    async def test_cross_tenant_fetch_returns_404(  # type: ignore[no-untyped-def]
        self, client: httpx.AsyncClient, user_a_headers, user_b_headers
    ) -> None:
        # user A uploads
        up = await client.post(
            "/api/v1/users/me/avatar",
            headers=user_a_headers,
            files=_files_payload(SAMPLE_PNG),
        )
        assert up.status_code == 200, up.text
        avatar_id = up.json()["avatar_id"]

        # user B tries to read it — must not be reachable
        other = await client.get(
            f"/api/v1/users/me/avatar/{avatar_id}",
            headers=user_b_headers,
        )
        assert other.status_code == 404, other.text

    async def test_remove_avatar(self, client: httpx.AsyncClient, user_a_headers) -> None:  # type: ignore[no-untyped-def]
        # Upload first
        up = await client.post(
            "/api/v1/users/me/avatar",
            headers=user_a_headers,
            files=_files_payload(SAMPLE_PNG),
        )
        assert up.status_code == 200, up.text
        _avatar_id = up.json()["avatar_id"]  # only need upload success

        # Confirm the avatar is the active one in /me
        me_before = await client.get("/api/v1/users/me", headers=user_a_headers)
        assert me_before.json()["avatar_url"] is not None

        # Delete → 200
        rm = await client.delete(
            "/api/v1/users/me/avatar",
            headers=user_a_headers,
        )
        assert rm.status_code == 200, rm.text
        body = rm.json()
        assert body["status"] == "removed"

        # /me now reports no avatar
        me_after = await client.get("/api/v1/users/me", headers=user_a_headers)
        assert me_after.json()["avatar_url"] is None

        # The file is intentionally kept on disk (spec T022) so a stale GET
        # to the old avatar_id will still 200; what changes is that the user
        # no longer points at it. We assert that explicitly: another DELETE
        # is a no-op → 404 NO_AVATAR.
        rm2 = await client.delete(
            "/api/v1/users/me/avatar",
            headers=user_a_headers,
        )
        assert rm2.status_code == 404, rm2.text

    async def test_remove_when_no_avatar_returns_404(  # type: ignore[no-untyped-def]
        self, client: httpx.AsyncClient, fresh_user_headers
    ) -> None:
        rm = await client.delete(
            "/api/v1/users/me/avatar",
            headers=fresh_user_headers,
        )
        assert rm.status_code == 404, rm.text
