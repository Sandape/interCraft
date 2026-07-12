"""REQ-061 US10 — encrypted content snapshot authorization & reveal audit (T135)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.badcases.models import BadcaseContentAuthorization
from app.modules.ai_runtime.models import AIEvidenceAccess, AIEvidenceSnapshot

SNAPSHOT_TTL = timedelta(days=30)
ALLOWED_DESTINATIONS = frozenset(
    {"admin_read_model", "operator_export", "langsmith", "none"}
)


class EvidencePrivacyError(PermissionError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


async def grant_content_authorization(
    session: AsyncSession,
    *,
    badcase_id: str,
    owner_user_id: UUID,
    purpose: str,
    permitted_content_classes: list[str],
    permitted_fields: list[str],
    privacy_class: str = "restricted",
    snapshot_ref: str | None = None,
    ttl: timedelta = SNAPSHOT_TTL,
) -> BadcaseContentAuthorization:
    now = datetime.now(timezone.utc)
    row = BadcaseContentAuthorization(
        id=new_uuid_v7(),
        badcase_id=badcase_id,
        owner_user_id=owner_user_id,
        permitted_content_classes=list(permitted_content_classes),
        permitted_fields=list(permitted_fields),
        purpose=purpose,
        privacy_class=privacy_class,
        snapshot_ref=snapshot_ref,
        expires_at=now + ttl,
        revoked_at=None,
        created_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def get_authorizations(
    session: AsyncSession, *, badcase_id: str
) -> list[BadcaseContentAuthorization]:
    stmt = select(BadcaseContentAuthorization).where(
        BadcaseContentAuthorization.badcase_id == badcase_id
    )
    return list((await session.execute(stmt)).scalars().all())


def authorization_allows(
    auth: BadcaseContentAuthorization, *, now: datetime | None = None
) -> bool:
    now = now or datetime.now(timezone.utc)
    if auth.revoked_at is not None:
        return False
    if auth.expires_at is not None and auth.expires_at <= now:
        return False
    return True


async def revoke_authorization(
    session: AsyncSession,
    *,
    authorization_id: UUID,
    actor_id: UUID,
    reason: str,
) -> BadcaseContentAuthorization:
    row = await session.get(BadcaseContentAuthorization, authorization_id)
    if row is None:
        raise EvidencePrivacyError("authorization not found", code="AUTH_NOT_FOUND")
    now = datetime.now(timezone.utc)
    row.revoked_at = now
    await session.flush()
    # Delete linked evidence snapshot content within policy window (FR-097)
    if row.snapshot_ref:
        await _delete_or_mark_snapshot(
            session, snapshot_ref=row.snapshot_ref, actor_id=actor_id, reason=reason
        )
    return row


async def reveal_snapshot(
    session: AsyncSession,
    *,
    badcase_id: str,
    owner_user_id: UUID,
    actor_id: UUID,
    reason: str,
    fields: list[str],
    export_destination: str | None = None,
) -> dict[str, Any]:
    """Reveal restricted content only when an owner-scoped authorization is active.

    Merged Bad Cases keep independent authorizations — caller must pass the
    correct ``owner_user_id``; other owners' consents do not grant access.
    """
    if export_destination and export_destination not in ALLOWED_DESTINATIONS:
        raise EvidencePrivacyError(
            f"destination {export_destination!r} not allowed",
            code="DESTINATION_DENIED",
        )

    auths = await get_authorizations(session, badcase_id=badcase_id)
    active = [
        a
        for a in auths
        if a.owner_user_id == owner_user_id and authorization_allows(a)
    ]
    if not active:
        raise EvidencePrivacyError(
            "no active content authorization for owner",
            code="AUTHORIZATION_REQUIRED",
        )

    auth = active[0]
    for field in fields:
        if field not in (auth.permitted_fields or []):
            raise EvidencePrivacyError(
                f"field {field!r} not permitted",
                code="FIELD_NOT_PERMITTED",
            )

    access = AIEvidenceAccess(
        id=new_uuid_v7(),
        evidence_snapshot_id=_parse_snapshot_uuid(auth.snapshot_ref),
        user_id=owner_user_id,
        actor_id=actor_id,
        reason=reason,
        fields=list(fields),
        action="reveal" if not export_destination else "export",
        export_destination=export_destination,
        accessed_at=datetime.now(timezone.utc),
    )
    # Only persist access when snapshot UUID is real; otherwise audit via payload
    if access.evidence_snapshot_id is not None:
        session.add(access)
        await session.flush()
        audit_id = str(access.id)
    else:
        audit_id = str(new_uuid_v7())

    return {
        "badcase_id": badcase_id,
        "owner_user_id": str(owner_user_id),
        "fields": fields,
        "privacy_class": auth.privacy_class,
        "snapshot_ref": auth.snapshot_ref,
        "export_destination": export_destination,
        "audit_event_id": audit_id,
        "expires_at": auth.expires_at.isoformat() if auth.expires_at else None,
    }


async def create_encrypted_snapshot(
    session: AsyncSession,
    *,
    user_id: UUID,
    badcase_id: str,
    encrypted_object_ref: str,
    content_classes: list[str],
    fields_included: list[str],
    purpose: str,
    consent_source: str,
) -> AIEvidenceSnapshot:
    now = datetime.now(timezone.utc)
    snap = AIEvidenceSnapshot(
        id=new_uuid_v7(),
        user_id=user_id,
        task_id=None,
        encrypted_object_ref=encrypted_object_ref,
        content_classes=list(content_classes),
        fields_included=list(fields_included),
        consent_source=consent_source,
        purpose=purpose,
        badcase_ticket_ref=badcase_id,
        privacy_class="restricted",
        retention_expires_at=now + SNAPSHOT_TTL,
        revoked_at=None,
        deleted_at=None,
        created_at=now,
    )
    session.add(snap)
    await session.flush()
    await grant_content_authorization(
        session,
        badcase_id=badcase_id,
        owner_user_id=user_id,
        purpose=purpose,
        permitted_content_classes=content_classes,
        permitted_fields=fields_included,
        privacy_class="restricted",
        snapshot_ref=str(snap.id),
    )
    return snap


def _parse_snapshot_uuid(ref: str | None) -> UUID | None:
    if not ref:
        return None
    try:
        return UUID(str(ref))
    except ValueError:
        return None


async def _delete_or_mark_snapshot(
    session: AsyncSession,
    *,
    snapshot_ref: str,
    actor_id: UUID,
    reason: str,
) -> None:
    snap_id = _parse_snapshot_uuid(snapshot_ref)
    if snap_id is None:
        return
    snap = await session.get(AIEvidenceSnapshot, snap_id)
    if snap is None:
        return
    now = datetime.now(timezone.utc)
    snap.revoked_at = now
    snap.deleted_at = now
    session.add(
        AIEvidenceAccess(
            id=new_uuid_v7(),
            evidence_snapshot_id=snap_id,
            user_id=snap.user_id,
            actor_id=actor_id,
            reason=reason,
            fields=[],
            action="revoke_delete",
            export_destination=None,
            accessed_at=now,
        )
    )
    await session.flush()


__all__ = [
    "ALLOWED_DESTINATIONS",
    "EvidencePrivacyError",
    "SNAPSHOT_TTL",
    "authorization_allows",
    "create_encrypted_snapshot",
    "get_authorizations",
    "grant_content_authorization",
    "reveal_snapshot",
    "revoke_authorization",
]
