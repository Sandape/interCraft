"""Sessions service: registration, 5-device eviction, rotation, revocation."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, SessionOtherUserError
from app.modules.auth.models import AuthSession
from app.modules.sessions.repository import SessionRepository


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SessionRepository(session)

    async def register_session(
        self,
        *,
        user_id: UUID,
        device_id: str,
        device_fingerprint: str,
        device_name: str | None = None,
        ip: str | None = None,
        ua: str | None = None,
    ) -> tuple[AuthSession, str | None]:
        """Create a new session, evicting the oldest if the user has >= MAX_ACTIVE.

        Returns (new_session, evicted_session_id or None).
        """
        settings = get_settings()
        max_active = settings.max_active_sessions
        existing = await self.repo.list_active(user_id)
        evicted: str | None = None

        # If this device is already known, soft-delete the prior row (effectively
        # a re-login) so we don't accidentally evict another device.
        prior_for_device = next((s for s in existing if s.device_id == device_id), None)
        if prior_for_device is not None:
            prior_for_device.deleted_at = datetime.now(UTC)
            await self.session.flush()
            existing = [s for s in existing if s.id != prior_for_device.id]

        # Phase 1: 5-device cap is soft (delete oldest if needed).
        if len(existing) >= max_active:
            oldest = min(existing, key=lambda s: s.last_seen_at)
            oldest.deleted_at = datetime.now(UTC)
            evicted = str(oldest.id)
            await self.session.flush()

        new_session = AuthSession(
            user_id=user_id,
            device_id=device_id,
            device_fingerprint=device_fingerprint,
            device_name=device_name,
            last_seen_ip=ip,
            last_seen_ua=ua,
            # 64 zero hex chars = valid sha256 placeholder. The CHECK constraint
            # enforces length=64; the real hash is written in the same transaction
            # once the refresh JWT is issued.
            refresh_token_hash="0" * 64,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.refresh_ttl),
        )
        self.session.add(new_session)
        await self.session.flush()
        await self.session.refresh(new_session)
        return new_session, evicted

    async def revoke_session(self, session_id: UUID, *, user_id: UUID | None = None) -> None:
        sess = await self.repo.get_by_id(session_id)
        if sess is None or sess.deleted_at is not None:
            raise NotFoundError("session.not_found", "Session not found")
        if user_id is not None and sess.user_id != user_id:
            raise SessionOtherUserError()
        sess.deleted_at = datetime.now(UTC)
        await self.session.flush()

    async def rotate_refresh(
        self,
        *,
        user_id: UUID,
        session_id: UUID | None,
        old_refresh_token: str,
    ) -> tuple[AuthSession, str | None]:
        """Rotate a refresh token.

        Validates the supplied refresh JWT, then:
        - If session row not found OR hash mismatch → reuse detected → revoke all user sessions.
        - Otherwise soft-delete the old session and create a fresh one (Phase 1 simpler
          than keeping the same id).
        """
        from app.core.security import hash_refresh_token

        if session_id is None:
            raise NotFoundError("session.not_found", "Session id missing from token")
        old = await self.repo.get_by_id(session_id)
        if old is None or old.deleted_at is not None:
            raise NotFoundError("session.not_found", "Session no longer valid")
        if old.user_id != user_id:
            raise SessionOtherUserError()
        if old.refresh_token_hash != hash_refresh_token(old_refresh_token):
            # Reuse — revoke all
            for s in await self.repo.list_active(user_id):
                s.deleted_at = datetime.now(UTC)
            await self.session.flush()
            raise NotFoundError("session.not_found", "Refresh token reuse detected; all sessions revoked")
        # Mark old as deleted
        old.deleted_at = datetime.now(UTC)
        await self.session.flush()
        # Issue a new row in its place (Phase 1 simplification).
        new = AuthSession(
            user_id=old.user_id,
            device_id=old.device_id,
            device_fingerprint=old.device_fingerprint,
            device_name=old.device_name,
            last_seen_ip=old.last_seen_ip,
            last_seen_ua=old.last_seen_ua,
            refresh_token_hash="0" * 64,
            expires_at=datetime.now(UTC)
            + timedelta(seconds=get_settings().refresh_ttl),
        )
        self.session.add(new)
        await self.session.flush()
        await self.session.refresh(new)
        return new, None

    async def is_session_alive(self, session_id: UUID | None) -> bool:
        if not session_id:
            return False

        try:
            sid = UUID(str(session_id))
        except (ValueError, TypeError):
            return False
        sess = await self.repo.get_by_id(sid)
        return sess is not None and sess.deleted_at is None


async def is_session_alive(db: AsyncSession, session_id: str | None) -> bool:
    if not session_id:
        return False
    svc = SessionService(db)
    return await svc.is_session_alive(session_id)


__all__ = ["SessionService", "is_session_alive"]
