"""Unit tests for app.core.crypto (AES-256-GCM with AAD binding)."""

import pytest

from app.core.crypto import CryptoError, decrypt, encrypt, make_aad


def test_roundtrip():
    pt = b"my-secret-data"
    aad = make_aad("user-1", "real_name")
    blob = encrypt(pt, aad)
    assert decrypt(blob, aad) == pt


def test_aad_mismatch_fails():
    pt = b"my-secret-data"
    aad1 = make_aad("user-1", "real_name")
    aad2 = make_aad("user-2", "real_name")
    blob = encrypt(pt, aad1)
    with pytest.raises(CryptoError):
        decrypt(blob, aad2)


def test_tamper_detection():
    pt = b"my-secret-data"
    aad = make_aad("user-1", "real_name")
    blob = bytearray(encrypt(pt, aad))
    blob[-1] ^= 0xFF  # flip a bit in the tag
    with pytest.raises(CryptoError):
        decrypt(bytes(blob), aad)


def test_short_blob_rejected():
    with pytest.raises(CryptoError):
        decrypt(b"abc", make_aad("u", "f"))


def test_layout_is_key_version_nonce_ct_tag():
    pt = b"x"
    aad = make_aad("u", "f")
    blob = encrypt(pt, aad)
    assert len(blob) == 1 + 12 + len(pt) + 16  # version + nonce + ct + tag
