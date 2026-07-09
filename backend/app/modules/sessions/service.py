"""Sessions service: registration, 10-device eviction, rotation, revocation.

FR-001 (Phase 4): device_id dedup removed — multi-tab coexistence.
FR-003: list_active filters expires_at so expired rows don't consume quota.
FR-009: rotate_refresh uses in-place UPDATE instead of soft-delete + create.
FR-011: structured audit logging for session lifecycle events.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, RefreshReuseError, SessionEvictedError, SessionOtherUserError
from app.core.logging import get_logger
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

        FR-001: No longer soft-deletes a prior row for the same device_id.
        Multi-tab coexistence means the same device_id can have multiple rows.

        Returns (new_session, evicted_session_id or None).
        """
        settings = get_settings()
        max_active = settings.max_active_sessions
        existing = await self.repo.list_active(user_id)
        evicted: str | None = None

        # Phase 1: 10-device cap is soft (delete oldest if needed).
        if len(existing) >= max_active:
            oldest = min(existing, key=lambda s: s.last_seen_at)
            oldest.deleted_at = datetime.now(UTC)
            evicted = str(oldest.id)
            await self.session.flush()
            logger = get_logger("sessions")
            logger.info(
                "session_evicted",
                extra={
                    "event": "session_evicted",
                    "target_session_id": str(oldest.id),
                    "new_session_device_id": device_id,
                    "cause": "max_devices_exceeded",
                },
            )

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

        logger = get_logger("sessions")
        logger.info(
            "session_created",
            extra={
                "event": "session_created",
                "session_id": str(new_session.id),
                "device_id": device_id,
                "cause": "login",
            },
        )

        return new_session, evicted

    async def revoke_session(self, session_id: UUID, *, user_id: UUID | None = None) -> None:
        sess = await self.repo.get_by_id(session_id)
        if sess is None or sess.deleted_at is not None:
            raise NotFoundError("session.not_found", "Session not found")
        if user_id is not None and sess.user_id != user_id:
            raise SessionOtherUserError()
        sess.deleted_at = datetime.now(UTC)
        await self.session.flush()
        logger = get_logger("sessions")
        logger.info(
            "session_revoked",
            extra={
                "event": "session_revoked",
                "target_session_id": str(session_id),
                "cause": "logout",
            },
        )

    async def rotate_refresh(
        self,
        *,
        user_id: UUID,
        session_id: UUID | None,
        old_refresh_token: str,
    ) -> tuple[AuthSession, str | None]:
        """Rotate a refresh token using in-place UPDATE (FR-009).

        Validates the supplied refresh JWT, then:
        - If session row not found or deleted → raise NotFoundError.
        - If hash mismatch → reject only; do NOT revoke all user sessions (FR-008).
        - Otherwise update the existing row in-place: new refresh_token_hash,
          new expires_at, updated_at bumped. No new row created, no soft-delete.
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
            # FR-008: reject only — do NOT revoke all sessions.
            raise RefreshReuseError()
        # In-place rotation (FR-009): update the existing row atomically.
        # The caller sets refresh_token_hash immediately after this returns.
        settings = get_settings()
        old.expires_at = datetime.now(UTC) + timedelta(seconds=settings.refresh_ttl)
        old.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(old)
        return old, None

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
