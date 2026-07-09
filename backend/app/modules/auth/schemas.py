"""Pydantic schemas for M04 (auth + user)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _validate_password_strength(value: str) -> str:
    """≥ 8 chars, must include at least one digit and one letter (spec FR-001, DEC-8).

    Raises ``ValueError`` so Pydantic wraps it as a standard ``ValidationError``
    at the schema boundary. Callers that need the app's ``PasswordTooWeakError``
    envelope can re-raise it explicitly.
    """
    if not isinstance(value, str) or len(value) < 8:
        raise ValueError("password must be at least 8 characters")
    if not re.search(r"\d", value):
        raise ValueError("password must include at least one digit")
    if not re.search(r"[A-Za-z]", value):
        raise ValueError("password must include at least one letter")
    return value


class RegisterInput(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = Field(default=None, max_length=64)
    device_name: str | None = Field(default=None, max_length=64)
    device_fingerprint: str | None = None

    @field_validator("email")
    @classmethod
    def _email_norm(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginInput(BaseModel):
    email: EmailStr
    password: str
    device_name: str | None = None
    device_fingerprint: str | None = None

    @field_validator("email")
    @classmethod
    def _email_norm(cls, v: str) -> str:
        return v.strip().lower()


class RefreshRequest(BaseModel):
    refresh_token: str | None = None
    device_fingerprint: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = 900


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None
    title: str | None
    years_of_experience: int | None
    target_role: str | None
    bio: str | None
    subscription: Literal["free", "pro", "enterprise"]
    is_admin: bool = False
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime


class PatchUserInput(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=128)
    years_of_experience: int | None = Field(default=None, ge=0, le=50)
    target_role: str | None = Field(default=None, max_length=128)
    bio: str | None = Field(default=None, max_length=1000)


class AuthRegisterResponse(BaseModel):
    user: PublicUser
    tokens: TokenPair


class AuthLoginResponse(BaseModel):
    user: PublicUser
    tokens: TokenPair
    evicted_session_id: str | None = None


class RefreshResponse(BaseModel):
    tokens: TokenPair


__all__ = [
    "AuthLoginResponse",
    "AuthRegisterResponse",
    "LoginInput",
    "PatchUserInput",
    "PublicUser",
    "RefreshRequest",
    "RefreshResponse",
    "RegisterInput",
    "TokenPair",
    "_validate_password_strength",
]
