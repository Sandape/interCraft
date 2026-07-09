"""iLink Bot HTTP client — REQ-052 T010.

Adapted from CoPaw's ILinkClient:
  D:/Project/CoPaw/src/copaw/app/channels/weixin/client.py

All iLink API endpoints live under https://ilinkai.weixin.qq.com.
Protocol: HTTP/JSON, no third-party SDK required.

Authentication flow:
  1. GET /ilink/bot/get_bot_qrcode?bot_type=3  → qrcode + QR image URL
  2. Poll GET /ilink/bot/get_qrcode_status?qrcode=<qrcode> until confirmed
  3. Save bot_token + baseurl from the confirmed response
  4. Use bearer token for all subsequent requests

Key difference from CoPaw: This client is per-user (not per-bot).
Each ILinkClient instance carries its own bot_token.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx

from .ilink_utils import channel_version, make_headers

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
_GETUPDATES_TIMEOUT = 45.0   # getupdates: server holds up to 35s
_QRCODE_STATUS_TIMEOUT = 40.0  # get_qrcode_status: long-polls ~30s
_DEFAULT_TIMEOUT = 15.0      # quick calls: qrcode, sendmessage


class ILinkClient:
    """Async HTTP client for the WeChat iLink Bot API (per-user).

    Args:
        bot_token: Bearer token obtained after QR code login.
        base_url: iLink API base URL.
    """

    def __init__(
        self,
        bot_token: str = "",
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self.bot_token = bot_token
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        # True iff start() created a dedicated client (i.e. we own it and
        # stop() should aclose it). When start() was given a shared_client
        # this stays False — the pool manages the shared client's lifecycle.
        self._owns_client: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, shared_client: Optional[httpx.AsyncClient] = None) -> None:
        """Create the underlying httpx client.

        trust_env=False prevents httpx from picking up system proxy settings
        (HTTP_PROXY/HTTPS_PROXY). iLink API should be reached directly, not
        through a local proxy.

        Args:
            shared_client: Optional pre-built ``httpx.AsyncClient`` to reuse.
                When the iLink pool starts it spins up a single
                ``_shared_client`` (HTTP/2 multiplex) and passes it to every
                per-user ILinkClient, so 1000 bound users share 1 AsyncClient
                instead of 1000. Pass ``None`` to fall back to creating a
                dedicated client — used by short-lived callers (probe,
                outbound-drain cron) that don't belong to the pool.
        """
        if shared_client is not None:
            self._client = shared_client
            self._owns_client = False
            return
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(_GETUPDATES_TIMEOUT),
            http2=True,
            trust_env=False,
        )
        self._owns_client = True

    async def stop(self) -> None:
        """Close the underlying httpx client.

        Only closes the client if we own it (``start()`` was called without
        a shared_client). When a shared_client was passed in, the pool
        manages the shared client's lifecycle, and we must NOT aclose it
        here or we'd tear down the client for all other users.
        """
        if self._client and self._owns_client:
            await self._client.aclose()
        self._client = None
        self._owns_client = False

    @property
    def is_started(self) -> bool:
        return self._client is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        return f"{self.base_url}/{path}"

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Any:
        """Parse iLink response as JSON.

        iLink returns ``application/octet-stream`` for some endpoints (notably
        ``getupdates`` long-poll) even though the body is valid JSON. Use this
        helper instead of ``resp.json()`` directly so we don't 500 on the
        first poll.

        Tries the standard JSON decoder first; on failure, decodes the raw
        bytes manually. Raises ``ValueError`` if the body is not valid JSON.
        """
        try:
            return resp.json()
        except (ValueError, json.JSONDecodeError):
            text = resp.content.decode("utf-8", errors="replace")
            return json.loads(text)

    async def _get(
        self, path: str, params: Dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        assert self._client is not None, "ILinkClient not started"
        headers = make_headers(self.bot_token)
        resp = await self._client.get(
            self._url(path),
            params=params or {},
            headers=headers,
            timeout=timeout or _DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return self._safe_json(resp)

    async def _post(
        self,
        path: str,
        body: Dict[str, Any],
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> Any:
        assert self._client is not None, "ILinkClient not started"
        headers = make_headers(self.bot_token)
        resp = await self._client.post(
            self._url(path),
            json=body,
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        return self._safe_json(resp)

    # ------------------------------------------------------------------
    # Auth APIs
    # ------------------------------------------------------------------

    async def get_bot_qrcode(self) -> Dict[str, Any]:
        """Fetch login QR code.

        Returns dict with keys:
            qrcode (str): QR code string to poll status.
            qrcode_img_content/url (str): Renderable WeChat QR image URL.
        """
        return await self._get("ilink/bot/get_bot_qrcode", {"bot_type": 3})

    async def get_qrcode_status(self, qrcode: str) -> Dict[str, Any]:
        """Poll QR code scan status (iLink long-polls this ~30s).

        The server holds the connection until the status changes
        (scanned/confirmed/expired) or ~30s timeout with "wait".
        When user scans during a hold, the server releases immediately,
        giving near-instant detection.

        Returns dict with keys:
            status (str): "wait" | "scanned" | "confirmed" | "expired"
            bot_token (str): Bearer token (only when status=="confirmed")
            baseurl (str): API base URL (only when status=="confirmed")
        """
        return await self._get(
            "ilink/bot/get_qrcode_status",
            {"qrcode": qrcode},
            timeout=_QRCODE_STATUS_TIMEOUT,
        )

    async def wait_for_login(
        self,
        qrcode: str,
        poll_interval: float = 1.5,
        max_wait: float = 300.0,
    ) -> Tuple[str, str]:
        """Block until QR code is confirmed or timeout.

        Returns:
            Tuple of (bot_token, base_url).

        Raises:
            TimeoutError: If login not confirmed within max_wait.
            RuntimeError: If QR code expired.
        """
        elapsed = 0.0
        while elapsed < max_wait:
            data = await self.get_qrcode_status(qrcode)
            status = data.get("status", "")
            if status == "confirmed":
                token = data.get("bot_token", "")
                base_url = data.get("baseurl", self.base_url)
                return token, base_url
            if status == "expired":
                raise RuntimeError(
                    "WeChat QR code expired, please retry login",
                )
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"WeChat QR code not scanned within {max_wait}s")

    # ------------------------------------------------------------------
    # Messaging APIs
    # ------------------------------------------------------------------

    async def getupdates(self, cursor: str = "") -> Dict[str, Any]:
        """Long-poll for incoming messages (holds up to 35 seconds).

        Returns:
            Dict with keys:
                ret (int): 0 = success, -1 = normal timeout.
                msgs (list): List of WeixinMessage dicts.
                get_updates_buf (str): Cursor for next call.
        """
        body: Dict[str, Any] = {
            "get_updates_buf": cursor,
            "base_info": {"channel_version": channel_version()},
        }
        return await self._post(
            "ilink/bot/getupdates",
            body,
            timeout=_GETUPDATES_TIMEOUT,
        )

    async def send_text(
        self,
        to_user_id: str,
        text: str,
        context_token: str = "",
    ) -> Dict[str, Any]:
        """Send a plain text message to a WeChat user.

        Args:
            to_user_id: Recipient user ID (xxx@im.wechat).
            text: Message text.
            context_token: context_token from inbound message (required for reply).
        """
        msg: Dict[str, Any] = {
            "from_user_id": "",
            "to_user_id": to_user_id,
            "client_id": str(uuid.uuid4()),
            "message_type": 2,      # BOT → USER
            "message_state": 2,     # FINISH
            "item_list": [{"type": 1, "text_item": {"text": text}}],
        }
        if context_token:
            msg["context_token"] = context_token

        return await self._post(
            "ilink/bot/sendmessage",
            {"msg": msg, "base_info": {"channel_version": channel_version()}},
        )

    # ------------------------------------------------------------------
    # Media helpers
    # ------------------------------------------------------------------

    async def download_media(
        self,
        url: str = "",
        aes_key_b64: str = "",
        encrypt_query_param: str = "",
    ) -> bytes:
        """Download a CDN media file and optionally decrypt it.

        iLink media files are stored on https://novac2c.cdn.weixin.qq.com/c2c.

        Args:
            url: CDN HTTP URL, or hex media-ID (ignored if encrypt_query_param).
            aes_key_b64: Base64-encoded AES-128 key; if empty, no decryption.
            encrypt_query_param: Query param from media.encrypt_query_param.

        Returns:
            Decrypted (or raw) file bytes.
        """
        assert self._client is not None, "ILinkClient not started"

        if encrypt_query_param:
            cdn_base = "https://novac2c.cdn.weixin.qq.com/c2c"
            enc = quote(encrypt_query_param, safe="")
            download_url = f"{cdn_base}/download?encrypted_query_param={enc}"
        elif url.startswith("http"):
            download_url = url
        else:
            raise ValueError(
                f"Cannot download media: no valid HTTP URL. "
                f"url={url[:40]!r}, encrypt_query_param empty.",
            )

        from .ilink_utils import aes_ecb_decrypt

        resp = await self._client.get(download_url, timeout=60.0)
        resp.raise_for_status()
        data = resp.content
        if aes_key_b64:
            data = aes_ecb_decrypt(data, aes_key_b64)
        return data
