"""WeChat iLink channel utilities — REQ-052 T009.

Adapted from CoPaw's weixin channel utils:
  D:/Project/CoPaw/src/copaw/app/channels/weixin/utils.py

Provides:
  - make_headers()      — iLink API request headers (AuthorizationType + X-WECHAT-UIN)
  - aes_ecb_decrypt()   — AES-128-ECB decryption for CDN media (3 key formats)
  - split_text()        — Smart text splitting at 500-char boundaries
"""

from __future__ import annotations

import base64
import random
import re
from typing import Dict, List

# ---------------------------------------------------------------------------
# iLink API headers
# ---------------------------------------------------------------------------

_CHANNEL_VERSION = "2.0.1"

_FENCE_RE = re.compile(r"^(```+|~~~+)")


def make_headers(bot_token: str = "") -> Dict[str, str]:
    """Build iLink API request headers.

    X-WECHAT-UIN: base64(str(random_uint32)) — anti-replay, per request.
    Authorization: Bearer <bot_token> — only set when token is available.
    """
    uin_val = random.randint(0, 0xFFFFFFFF)
    uin_b64 = base64.b64encode(str(uin_val).encode()).decode()
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": uin_b64,
    }
    if bot_token:
        headers["Authorization"] = f"Bearer {bot_token}"
    return headers


def channel_version() -> str:
    return _CHANNEL_VERSION


# ---------------------------------------------------------------------------
# AES-128-ECB decryption (adapted from CoPaw utils.py)
# ---------------------------------------------------------------------------


def aes_ecb_decrypt(data: bytes, key_b64: str) -> bytes:
    """Decrypt AES-128-ECB encrypted bytes (iLink CDN media).

    Accepts three key formats (mirrors official TypeScript parseAesKey logic):
      1. Base64-encoded raw bytes  (standard, e.g. media.aes_key)
      2. Raw hex string (32 chars = 16 bytes, e.g. image_item.aeskey)
      3. Raw 16/24/32-byte string (passed through directly)

    Returns decrypted bytes with PKCS7 padding removed.
    """
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
    except ImportError as exc:
        raise ImportError(
            "pycryptodome is required for WeChat media decryption. "
            "Install with: pip install pycryptodome",
        ) from exc

    # Auto-detect key format
    raw = key_b64.strip()
    if len(raw) in (32, 48, 64) and all(c in "0123456789abcdefABCDEF" for c in raw):
        # Format: raw hex string (e.g. image_item.aeskey — 32 hex chars)
        key = bytes.fromhex(raw)
    else:
        # Format: base64-encoded
        try:
            decoded = base64.b64decode(raw + "==")
        except Exception:
            decoded = raw.encode()
        if len(decoded) == 16:
            key = decoded
        elif len(decoded) == 32 and all(
            c in b"0123456789abcdefABCDEF" for c in decoded
        ):
            key = bytes.fromhex(decoded.decode("ascii"))
        else:
            key = decoded

    if len(key) not in (16, 24, 32):
        raise ValueError(
            f"Invalid AES key length: {len(key)} (from key_b64={raw[:20]!r})",
        )

    cipher = AES.new(key, AES.MODE_ECB)
    decrypted = cipher.decrypt(data)
    return unpad(decrypted, AES.block_size)


# ---------------------------------------------------------------------------
# Text splitting (adapted from CoPaw channels/utils.py split_text)
# ---------------------------------------------------------------------------

_MAX_CHUNK_CHARS = 500  # InterCraft uses 500-char segments for WeChat readability


def split_text(text: str, max_len: int = _MAX_CHUNK_CHARS) -> List[str]:
    """Split text into chunks that fit within max_len characters.

    - Splits at newline boundaries to preserve paragraph structure.
    - Tracks Markdown code fences across chunk boundaries.
    - A single line exceeding max_len is hard-split at the limit.
    - Adds (n/total) segment markers.

    Returns list of text chunks.
    """
    if len(text) <= max_len:
        return [text]

    # First pass: split into raw chunks
    raw_chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    fence_open: str = ""

    for line in text.split("\n"):
        line_with_nl = line + "\n"
        stripped = line.strip()

        # Track markdown code fences
        if _FENCE_RE.match(stripped):
            if fence_open:
                fence_open = ""
            else:
                fence_open = stripped

        if current and current_len + len(line_with_nl) > max_len:
            saved_fence = fence_open
            body = "".join(current).rstrip("\n")
            if fence_open:
                body += "\n```"
            raw_chunks.append(body)
            current.clear()
            current_len = 0
            if saved_fence:
                fence_open = saved_fence
                reopener = saved_fence + "\n"
                current.append(reopener)
                current_len += len(reopener)

        if len(line_with_nl) > max_len:
            for i in range(0, len(line), max_len):
                raw_chunks.append(line[i : i + max_len])
        else:
            current.append(line_with_nl)
            current_len += len(line_with_nl)

    if current:
        raw_chunks.append("".join(current).rstrip("\n"))

    raw_chunks = [c for c in raw_chunks if c.strip()]
    total = len(raw_chunks)

    # Add segment markers
    if total == 1:
        return raw_chunks
    return [f"({i + 1}/{total})\n{c}" for i, c in enumerate(raw_chunks)]
