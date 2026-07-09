"""M04 / M05 — User / UserCredential / AuthSession ORM models."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import BYTEA, INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domain.mixins import (
    SoftDeletableMixin,
    TenantScopedMixin,
    TimestampedMixin,
    UUIDv7PrimaryKeyMixin,
)


class User(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampedMixin,
    SoftDeletableMixin,
):
    """The `users` table — every other tenant table references this row."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False)
    email_sha256: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_sha256: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    scheduled_purge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    cancellation_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_provider_pref: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    subscription: Mapped[str] = mapped_column(Text, nullable=False, default="free")
    monthly_token_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=100000)
    monthly_token_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quota_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    allow_concurrent_sessions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Feature 013 — User Avatar. Nullable FK to the active avatar row. SET NULL
    # on avatar deletion so a removed avatar does not leave a dangling pointer.
    avatar_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_avatars.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    # Relationships
    credentials: Mapped[UserCredential | None] = relationship(
        "UserCredential", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    avatar: Mapped["UserAvatar | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "UserAvatar",
        primaryjoin="User.avatar_id == UserAvatar.id",
        foreign_keys=[avatar_id],
        lazy="joined",
    )
    avatars: Mapped[list["UserAvatar"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "UserAvatar",
        primaryjoin="User.id == UserAvatar.user_id",
        foreign_keys="UserAvatar.user_id",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    sessions: Mapped[list[AuthSession]] = relationship(
        "AuthSession", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("email", name="users_email_unique"),
        UniqueConstraint("email_sha256", name="users_email_sha256_unique"),
        UniqueConstraint("phone_sha256", name="users_phone_sha256_unique"),
        Index("users_status_deleted_at_idx", "status", "deleted_at"),
        CheckConstraint(
            "status IN ('active','soft_deleted','purged','frozen')",
            name="users_status_chk",
        ),
        CheckConstraint(
            "subscription IN ('free','pro','enterprise')",
            name="users_subscription_chk",
        ),
        CheckConstraint(
            "years_of_experience IS NULL OR (years_of_experience >= 0 AND years_of_experience <= 50)",
            name="users_yoe_chk",
        ),
    )


class UserCredential(
    Base,
    TenantScopedMixin,
    TimestampedMixin,
):
    """Sensitive per-user credentials (id_card / real_name / salary).

    Phase 1: table is created and encrypt/decrypt round-trip is tested.
    API surface is NOT exposed (deferred to Phase 2).
    """

    __tablename__ = "user_credentials"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    id_card_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    real_name_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    salary_range_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="credentials")


class AuthSession(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampedMixin,
    SoftDeletableMixin,
    TenantScopedMixin,
):
    """M05 — device-bound session row, RLS-scoped to its user."""

    __tablename__ = "auth_sessions"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[str] = mapped_column(Text, nullable=False)
    device_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    last_seen_ua: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    trusted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")

    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="auth_sessions_device_id_unique"),
        Index(
            "auth_sessions_user_last_seen_idx",
            "user_id",
            "last_seen_at",
        ),
        Index("auth_sessions_refresh_hash_idx", "refresh_token_hash"),
        CheckConstraint("length(device_id) = 64", name="auth_sessions_device_id_chk"),
        CheckConstraint(
            "length(refresh_token_hash) = 64", name="auth_sessions_refresh_hash_chk"
        ),
    )


__all__ = ["AuthSession", "User", "UserCredential"]
