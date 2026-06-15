"""Auth service — register, authenticate, refresh, logout."""
from __future__ import annotations

import hashlib
from uuid import UUID

import jwt as pyjwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AuthError,
    EmailTakenError,
    NotFoundError,
    RefreshInvalidError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import LoginInput, PublicUser, RegisterInput, TokenPair
from app.modules.sessions.service import SessionService


def _user_to_public(user: User) -> PublicUser:
    return PublicUser(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        title=user.title,
        years_of_experience=user.years_of_experience,
        target_role=user.target_role,
        bio=user.bio,
        subscription=user.subscription or "free",
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compute_device_id(fingerprint_raw: str) -> str:
    """Device id = sha256 hex of the raw fingerprint string."""
    return hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions_svc = SessionService(session)

    # ---- register ----
    async def register(
        self,
        payload: RegisterInput,
        *,
        ip: str | None = None,
        ua: str | None = None,
    ) -> tuple[PublicUser, TokenPair]:
        existing = await self.users.get_by_email(payload.email)
        if existing is not None:
            raise EmailTakenError()
        pwd_hash = hash_password(payload.password)
        # RLS chicken-and-egg: pre-generate the new user id, bind RLS to it,
        # so the WITH CHECK on users(id = app.user_id) lets the INSERT pass.
        from app.core.db import set_rls_user_id
        from app.core.ids import new_uuid_v7

        new_user_id = new_uuid_v7()
        await set_rls_user_id(self.session, new_user_id)
        user = await self.users.create_user(
            id=new_user_id,
            email=payload.email,
            password_hash=pwd_hash,
            display_name=payload.display_name,
        )
        # Seed 6 ability dimensions for the new user (DEC-P2-2)
        from app.modules.abilities.repository import AbilityDimensionRepository

        abilities_repo = AbilityDimensionRepository(self.session)
        await abilities_repo.seed_for_new_user(user.id)

        device_fingerprint = payload.device_fingerprint or "unknown-device"
        device_id = compute_device_id(device_fingerprint)
        session, _evicted = await self.sessions_svc.register_session(
            user_id=user.id,
            device_id=device_id,
            device_fingerprint=device_fingerprint,
            device_name=payload.device_name,
            ip=ip,
            ua=ua,
        )
        access, _ = create_access_token(str(user.id), str(session.id))
        refresh, _ = create_refresh_token(str(user.id), str(session.id))
        # Store the refresh-token hash so we can detect reuse.
        session.refresh_token_hash = hash_refresh_token(refresh)
        await self.session.flush()
        return _user_to_public(user), TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=get_settings().access_ttl,
        )

    # ---- login ----
    async def login(
        self,
        payload: LoginInput,
        *,
        ip: str | None = None,
        ua: str | None = None,
    ) -> tuple[PublicUser, TokenPair, str | None]:
        from app.core.metrics import auth_login_attempts_total

        user = await self.users.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            auth_login_attempts_total.labels(result="failed").inc()
            raise AuthError("auth.invalid_credentials", "Invalid email or password", http_status=401)
        auth_login_attempts_total.labels(result="success").inc()

        # Bind RLS to this user so subsequent writes (auth_sessions etc.) pass
        # the WITH CHECK (user_id = current_setting('app.user_id')::uuid).
        from app.core.db import set_rls_user_id
        await set_rls_user_id(self.session, user.id)

        device_fingerprint = payload.device_fingerprint or "unknown-device"
        device_id = compute_device_id(device_fingerprint)
        session, evicted_id = await self.sessions_svc.register_session(
            user_id=user.id,
            device_id=device_id,
            device_fingerprint=device_fingerprint,
            device_name=payload.device_name,
            ip=ip,
            ua=ua,
        )
        access, _ = create_access_token(str(user.id), str(session.id))
        refresh, _ = create_refresh_token(str(user.id), str(session.id))
        session.refresh_token_hash = hash_refresh_token(refresh)
        await self.session.flush()
        return _user_to_public(user), TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=get_settings().access_ttl,
        ), evicted_id

    # ---- refresh ----
    async def refresh(
        self,
        refresh_token: str,
    ) -> TokenPair:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except pyjwt.PyJWTError as e:
            raise RefreshInvalidError() from e
        # Bind RLS so the session lookup + UPDATE pass.
        from app.core.db import set_rls_user_id
        await set_rls_user_id(self.session, UUID(payload.sub))
        from app.modules.sessions.service import SessionService
        svc = SessionService(self.session)
        rotated, _evicted = await svc.rotate_refresh(
            user_id=UUID(payload.sub),
            session_id=UUID(payload.session_id) if payload.session_id else None,
            old_refresh_token=refresh_token,
        )
        access, _ = create_access_token(str(rotated.user_id), str(rotated.id))
        new_refresh, _ = create_refresh_token(str(rotated.user_id), str(rotated.id))
        rotated.refresh_token_hash = hash_refresh_token(new_refresh)
        await self.session.flush()
        return TokenPair(
            access_token=access,
            refresh_token=new_refresh,
            expires_in=get_settings().access_ttl,
        )

    # ---- logout ----
    async def logout(self, session_id: UUID) -> None:
        from app.modules.sessions.service import SessionService
        svc = SessionService(self.session)
        await svc.revoke_session(session_id)

    # ---- me ----
    async def get_me(self, user_id: UUID) -> PublicUser:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("user.not_found", "User not found")
        return _user_to_public(user)

    async def patch_me(self, user_id: UUID, **patch) -> PublicUser:
        user = await self.users.update_profile(user_id, **patch)
        if user is None:
            raise NotFoundError("user.not_found", "User not found")
        return _user_to_public(user)


__all__ = ["AuthService", "compute_device_id"]
