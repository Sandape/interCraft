"""AES-256-GCM symmetric encryption for sensitive columns.

Layout (binary): key_version(1B) || nonce(12B) || ciphertext || tag(16B).

AAD (additional authenticated data) MUST include the user_id and a
field identifier so ciphertexts cannot be moved between rows or fields
without detection. See M03 §6 in docs.
"""
from __future__ import annotations

import base64
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_NONCE_LEN = 12
_TAG_LEN = 16
_VERSION_LEN = 1


class CryptoError(Exception):
    """Raised when encryption / decryption fails (tamper / wrong key)."""


@dataclass
class _DerivedKey:
    raw: bytes


def _load_master_key() -> bytes:
    settings = get_settings()
    raw = settings.master_key
    try:
        decoded = base64.b64decode(raw, validate=True)
    except Exception as e:
        raise CryptoError(f"MASTER_KEY is not valid base64: {e}") from e
    if len(decoded) != 32:
        raise CryptoError(
            f"MASTER_KEY must decode to 32 bytes (got {len(decoded)}). "
            "Generate with: openssl rand -base64 32"
        )
    return decoded


_MASTER = _DerivedKey(raw=_load_master_key())
_AESGCM = AESGCM(_MASTER.raw)


def encrypt(plaintext: bytes, aad: bytes) -> bytes:
    """Encrypt `plaintext` bound to `aad`. Returns a self-describing blob."""
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError("plaintext must be bytes")
    if not isinstance(aad, (bytes, bytearray)):
        raise TypeError("aad must be bytes")
    settings = get_settings()
    nonce = __import__("os").urandom(_NONCE_LEN)
    ct = _AESGCM.encrypt(nonce, bytes(plaintext), bytes(aad))
    version = struct.pack("B", settings.crypto_key_version)
    return version + nonce + ct  # ct already includes the 16-byte tag


def decrypt(blob: bytes, aad: bytes) -> bytes:
    """Decrypt a blob produced by `encrypt`. Raises CryptoError on tamper."""
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("blob must be bytes")
    if not isinstance(aad, (bytes, bytearray)):
        raise TypeError("aad must be bytes")
    if len(blob) < _VERSION_LEN + _NONCE_LEN + _TAG_LEN:
        raise CryptoError("ciphertext too short")
    version = blob[0]
    settings = get_settings()
    if version != settings.crypto_key_version:
        raise CryptoError(
            f"unsupported key version {version} (expected {settings.crypto_key_version})"
        )
    nonce = blob[1 : 1 + _NONCE_LEN]
    ct = blob[1 + _NONCE_LEN :]
    try:
        return _AESGCM.decrypt(nonce, ct, bytes(aad))
    except InvalidTag as e:
        raise CryptoError("authentication failed (tampered or wrong AAD)") from e


def make_aad(user_id: str, field: str, version: int | None = None) -> bytes:
    """Build the standard AAD for `user_id`+`field` encryption."""
    v = version if version is not None else get_settings().crypto_key_version
    return f"v{v}|u={user_id}|f={field}".encode()


__all__ = ["CryptoError", "decrypt", "encrypt", "make_aad"]
