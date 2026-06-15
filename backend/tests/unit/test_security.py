"""Unit tests for app.core.security (bcrypt + JWT)."""

import jwt as pyjwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    new_refresh_secret,
    verify_password,
)


def test_bcrypt_roundtrip():
    h = hash_password("P@ssw0rd123")
    assert verify_password("P@ssw0rd123", h)
    assert not verify_password("wrong", h)


def test_access_token_decode():
    tok, _p = create_access_token("user-1", "session-1")
    decoded = decode_token(tok, expected_type="access")
    assert decoded.sub == "user-1"
    assert decoded.session_id == "session-1"
    assert decoded.type == "access"


def test_refresh_token_decode():
    tok, _p = create_refresh_token("user-2", "session-2")
    decoded = decode_token(tok, expected_type="refresh")
    assert decoded.sub == "user-2"
    assert decoded.session_id == "session-2"
    assert decoded.type == "refresh"


def test_type_mismatch_rejected():
    tok, _ = create_access_token("user-1", "session-1")
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(tok, expected_type="refresh")


def test_refresh_secret_format():
    s = new_refresh_secret()
    assert len(s) >= 32
    h = hash_refresh_token(s)
    assert len(h) == 64  # sha256 hex
    assert h == hash_refresh_token(s)
