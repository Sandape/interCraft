"""Password hashing (bcrypt) + JWT helpers (PyJWT)."""
from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

# ---- Bcrypt ----


def hash_password(plain: str) -> str:
    settings = get_settings()
    if not isinstance(plain, str) or not plain:
        raise ValueError("password must be a non-empty string")
    cost = max(4, min(15, settings.bcrypt_cost_rounds))
    salt = bcrypt.gensalt(rounds=cost)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---- JWT ----


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    exp: int
    iat: int
    jti: str
    type: str  # "access" | "refresh"
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "sub": self.sub,
            "exp": self.exp,
            "iat": self.iat,
            "jti": self.jti,
            "type": self.type,
        }
        if self.session_id:
            d["session_id"] = self.session_id
        return d


def _now() -> int:
    return int(time.time())


def create_access_token(user_id: str, session_id: str) -> tuple[str, TokenPayload]:
    settings = get_settings()
    now = _now()
    payload = TokenPayload(
        sub=user_id,
        exp=now + settings.access_ttl,
        iat=now,
        jti=str(uuid.uuid4()),
        type="access",
        session_id=session_id,
    )
    token = jwt.encode(payload.to_dict(), settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, payload


def create_refresh_token(user_id: str, session_id: str) -> tuple[str, TokenPayload]:
    """Refresh token = opaque secret (256-bit) PLUS JWT carrying metadata.

    The opaque secret is what gets hashed and stored; the JWT carries
    the session binding + jti for revocation.
    """
    settings = get_settings()
    now = _now()
    payload = TokenPayload(
        sub=user_id,
        exp=now + settings.refresh_ttl,
        iat=now,
        jti=str(uuid.uuid4()),
        type="refresh",
        session_id=session_id,
    )
    token = jwt.encode(payload.to_dict(), settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, payload


def decode_token(token: str, expected_type: str) -> TokenPayload:
    """Decode + verify a JWT. Raises jwt.PyJWTError on failure."""
    settings = get_settings()
    data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if data.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected type={expected_type}, got {data.get('type')}")
    return TokenPayload(
        sub=str(data["sub"]),
        exp=int(data["exp"]),
        iat=int(data["iat"]),
        jti=str(data["jti"]),
        type=str(data["type"]),
        session_id=data.get("session_id"),
    )


def new_refresh_secret() -> str:
    """256-bit URL-safe token used as the refresh_token value."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(secret: str) -> str:
    """Stable hash for `auth_sessions.refresh_token_hash` lookup."""
    import hashlib

    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


__all__ = [
    "TokenPayload",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "hash_refresh_token",
    "new_refresh_secret",
    "verify_password",
]


