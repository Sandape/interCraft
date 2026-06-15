"""User repository — email lookup, registration, profile updates."""
from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.repositories.base import BaseRepository


def _sha256_email(email: str) -> bytes:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).digest()


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, id: UUID) -> User | None:
        return await self.get(id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(
            User.email == email.strip().lower(),
            User.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_sha256(self, email: str) -> User | None:
        stmt = select(User).where(
            User.email_sha256 == _sha256_email(email),
            User.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        id: UUID | None = None,
        display_name: str | None = None,
        title: str | None = None,
        years_of_experience: int | None = None,
        target_role: str | None = None,
        bio: str | None = None,
    ) -> User:
        normalized = email.strip().lower()
        user = User(
            id=id if id is not None else None,
            email=normalized,
            email_sha256=_sha256_email(normalized),
            password_hash=password_hash,
            display_name=display_name,
            title=title,
            years_of_experience=years_of_experience,
            target_role=target_role,
            bio=bio,
        )
        return await self.create(user)

    async def update_profile(
        self,
        user_id: UUID,
        *,
        display_name: str | None = None,
        title: str | None = None,
        years_of_experience: int | None = None,
        target_role: str | None = None,
        bio: str | None = None,
    ) -> User | None:
        patch: dict = {}
        if display_name is not None:
            patch["display_name"] = display_name
        if title is not None:
            patch["title"] = title
        if years_of_experience is not None:
            patch["years_of_experience"] = years_of_experience
        if target_role is not None:
            patch["target_role"] = target_role
        if bio is not None:
            patch["bio"] = bio
        if not patch:
            return await self.get(user_id)
        return await self.update(user_id, patch)


__all__ = ["UserRepository", "_sha256_email"]
