"""REQ-052 QR code URL contract tests."""

from __future__ import annotations

from datetime import datetime, timezone


def test_qrcode_response_uses_direct_image_url() -> None:
    from app.modules.agent.schemas import QrcodeResponse

    response = QrcodeResponse(
        qrcode_token="a46fb64431ed99597887d23b442c987c",
        qrcode_url=(
            "https://liteapp.weixin.qq.com/q/7GiQu1"
            "?qrcode=a46fb64431ed99597887d23b442c987c&bot_type=3"
        ),
        qrcode_image_url=(
            "/api/v1/agent/wechat/qrcode/image"
            "?qrcode_token=a46fb64431ed99597887d23b442c987c"
        ),
        expires_at=datetime(2026, 7, 8, 12, 5, tzinfo=timezone.utc),
        expires_in_sec=300,
    )

    payload = response.model_dump()

    assert payload["qrcode_url"].startswith("https://liteapp.weixin.qq.com/q/")
    assert payload["qrcode_image_url"].startswith("/api/v1/agent/wechat/qrcode/image")
    assert "qrcode_img_base64" not in payload


def test_ilink_qrcode_url_prefers_ilink_direct_url() -> None:
    from app.modules.agent.api import _ilink_qrcode_url

    url = "https://liteapp.weixin.qq.com/q/7GiQu1?qrcode=abc&bot_type=3"

    assert _ilink_qrcode_url({"qrcode": "abc", "qrcode_img_content": url}) == url


def test_ilink_qrcode_url_builds_liteapp_url_from_token() -> None:
    from app.modules.agent.api import _ilink_qrcode_url

    assert _ilink_qrcode_url({"qrcode": "abc 123", "qrcode_img_content": ""}) == (
        "https://liteapp.weixin.qq.com/q/7GiQu1?qrcode=abc%20123&bot_type=3"
    )


def test_render_qr_png_bytes_returns_png() -> None:
    from app.modules.agent.api import _render_qr_png_bytes

    payload = _render_qr_png_bytes("https://liteapp.weixin.qq.com/q/7GiQu1?qrcode=abc&bot_type=3")

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
