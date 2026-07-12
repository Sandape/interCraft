"""Atomic poll acknowledgement and user-neutral durable inbox (REQ-060)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.channels.message_handler import parse_inbound_message
from app.core.config import get_settings
from app.core.db import get_session_context
from app.core.ids import new_uuid_v7
from app.core.logging import get_logger
from app.modules.agent.models import (
    WeChatBinding,
    WeChatCredential,
    WeChatInbox,
    WeChatPollBatch,
)
from app.modules.agent.runtime.telemetry import agent_span, emit_event, privacy_ref, record_metric
from app.modules.agent.service import encrypt_sensitive_text


class StaleConsumerFence(RuntimeError):
    """The poll response belongs to an owner that no longer holds the lease."""


log = get_logger("wechat.durable_inbox")


@dataclass(frozen=True, slots=True)
class PersistPollResult:
    batch_id: UUID
    item_count: int
    persisted_count: int
    new_inbox_ids: tuple[UUID, ...]
    processable_items: tuple[tuple[str, UUID, int], ...]
    quarantined_count: int


def _canonical_message(raw: dict) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def message_dedupe_key(credential_id: UUID, raw: dict) -> str:
    canonical = _canonical_message(raw)
    external_id = str(raw.get("msg_id") or "") or None
    return _fingerprint(f"wechat:{credential_id}:{external_id or canonical}")


async def persist_poll_batch(
    *,
    user_id: UUID,
    credential_id: UUID,
    previous_cursor: str,
    new_cursor: str,
    raw_messages: list[dict],
    consumer_key: str,
    owner_id: UUID,
    fencing_token: int,
) -> PersistPollResult:
    """Persist every poll item and advance its cursor in one fenced transaction."""
    settings = get_settings()
    started = time.perf_counter()
    started = time.perf_counter()
    batch_id = new_uuid_v7()
    new_ids: list[UUID] = []
    processable_items: list[tuple[str, UUID, int]] = []
    quarantined_count = 0

    with agent_span(
        "wechat.poll.persist",
        consumer_owner_ref=privacy_ref(str(owner_id), salt=settings.master_key),
        fencing_token=fencing_token,
    ):
        async with get_session_context(user_id=user_id) as session:
            fence_valid = await session.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM wechat_consumer_leases "
                    "WHERE consumer_key=:consumer_key AND owner_id=:owner_id "
                    "AND fencing_token=:fencing_token AND lease_until > now())"
                ),
                {
                    "consumer_key": consumer_key,
                    "owner_id": owner_id,
                    "fencing_token": fencing_token,
                },
            )
            if not fence_valid:
                raise StaleConsumerFence("consumer lease is no longer valid")

            credential = await session.scalar(
                select(WeChatCredential).where(
                    WeChatCredential.id == credential_id,
                    WeChatCredential.user_id == user_id,
                    WeChatCredential.status == "active",
                )
            )
            if credential is None:
                raise StaleConsumerFence("credential is not active for this owner")

            binding = await session.scalar(
                select(WeChatBinding).where(
                    WeChatBinding.user_id == user_id,
                    WeChatBinding.unbound_at.is_(None),
                )
            )

            batch = WeChatPollBatch(
                id=batch_id,
                consumer_key=consumer_key,
                credential_id=credential_id,
                cursor_before_hash=_fingerprint(previous_cursor) if previous_cursor else None,
                cursor_after_hash=_fingerprint(new_cursor) if new_cursor else None,
                fencing_token=fencing_token,
                item_count=len(raw_messages),
                persisted_count=0,
                status="received",
            )
            session.add(batch)
            await session.flush()

            for raw in raw_messages:
                canonical = _canonical_message(raw)
                parsed = parse_inbound_message(raw)
                sender = str(raw.get("from_user_id") or "")
                external_id = str(raw.get("msg_id") or "") or None
                dedupe_key = message_dedupe_key(credential_id, raw)

                parse_status = "valid"
                resolved_user_id: UUID | None = None
                resolved_binding_id: UUID | None = None
                resolved_epoch: int | None = None
                if parsed is None:
                    parse_status = "malformed" if raw.get("message_type") == 1 else "unsupported"
                elif (
                    binding is None
                    or not sender
                    or not hmac.compare_digest(binding.wechat_uin, sender)
                ):
                    parse_status = "quarantined"
                    quarantined_count += 1
                else:
                    resolved_user_id = user_id
                    resolved_binding_id = binding.id
                    resolved_epoch = binding.binding_epoch

                inbox_id = new_uuid_v7()
                statement = (
                    insert(WeChatInbox)
                    .values(
                        id=inbox_id,
                        batch_id=batch_id,
                        external_message_id=external_id,
                        dedupe_key=dedupe_key,
                        sender_ref_hash=privacy_ref(sender or "unknown", salt=settings.master_key),
                        credential_id=credential_id,
                        binding_id=resolved_binding_id,
                        user_id=resolved_user_id,
                        binding_epoch=resolved_epoch,
                        payload_encrypted=encrypt_sensitive_text(canonical),
                        parse_status=parse_status,
                        processing_status="received",
                        attempt_count=0,
                        created_at=datetime.now(UTC),
                    )
                    .on_conflict_do_nothing(index_elements=[WeChatInbox.dedupe_key])
                    .returning(WeChatInbox.id)
                )
                inserted_id = await session.scalar(statement)
                if inserted_id is not None:
                    new_ids.append(inserted_id)
                    if parse_status == "valid":
                        assert resolved_epoch is not None
                        processable_items.append((dedupe_key, inserted_id, resolved_epoch))

            # Re-check the same fence as part of the cursor UPDATE. If ownership
            # changed while parsing/inserting, rowcount is zero and the enclosing
            # transaction rolls back the batch and all inbox rows.
            cursor_update = await session.execute(
                update(WeChatCredential)
                .where(
                    WeChatCredential.id == credential_id,
                    WeChatCredential.user_id == user_id,
                    text(
                        "EXISTS (SELECT 1 FROM wechat_consumer_leases "
                        "WHERE consumer_key=:consumer_key AND owner_id=:owner_id "
                        "AND fencing_token=:fencing_token AND lease_until > now())"
                    ),
                )
                .values(
                    cursor=new_cursor or previous_cursor,
                    last_polled_at=datetime.now(UTC),
                ),
                {
                    "consumer_key": consumer_key,
                    "owner_id": owner_id,
                    "fencing_token": fencing_token,
                },
            )
            if cursor_update.rowcount != 1:
                raise StaleConsumerFence("consumer lease changed before cursor commit")
            await session.execute(
                text(
                    "UPDATE wechat_consumer_registrations "
                    "SET cursor=:cursor, updated_at=now() "
                    "WHERE user_id=:user_id AND credential_id=:credential_id AND active=true"
                ),
                {
                    "cursor": new_cursor or previous_cursor,
                    "user_id": user_id,
                    "credential_id": credential_id,
                },
            )

            batch.persisted_count = len(raw_messages)
            batch.status = "quarantined" if quarantined_count else "persisted"
            batch.persisted_at = datetime.now(UTC)

    result = PersistPollResult(
        batch_id=batch_id,
        item_count=len(raw_messages),
        persisted_count=len(raw_messages),
        new_inbox_ids=tuple(new_ids),
        processable_items=tuple(processable_items),
        quarantined_count=quarantined_count,
    )
    emit_event(
        log,
        "wechat.poll.persisted",
        batch_id=str(batch_id),
        item_count=len(raw_messages),
        quarantined_count=quarantined_count,
        fencing_token=fencing_token,
    )
    record_metric(
        "wechat_inbound_total",
        outcome="persisted" if not quarantined_count else "partially_quarantined",
    )
    record_metric(
        "wechat_inbound_processing_seconds",
        value=time.perf_counter() - started,
    )
    duplicate_count = max(0, len(raw_messages) - len(new_ids))
    if duplicate_count:
        record_metric("wechat_inbound_duplicate_total", value=duplicate_count)
    record_metric(
        "wechat_inbound_processing_seconds",
        value=time.perf_counter() - started,
    )
    duplicate_count = max(0, len(raw_messages) - len(new_ids))
    if duplicate_count:
        record_metric("wechat_inbound_duplicate_total", value=duplicate_count)
    if quarantined_count:
        record_metric("wechat_inbound_quarantined_total", reason="binding_mismatch")
    return result


__all__ = [
    "PersistPollResult",
    "StaleConsumerFence",
    "message_dedupe_key",
    "persist_poll_batch",
]


async def claim_inbox_item(
    *,
    user_id: UUID,
    inbox_id: UUID,
    binding_epoch: int,
    owner_id: UUID,
    claim_seconds: int,
) -> bool:
    """Claim one validated inbox item with binding-epoch fencing."""
    now = datetime.now(UTC)
    async with get_session_context(user_id=user_id) as session:
        result = await session.execute(
            update(WeChatInbox)
            .where(
                WeChatInbox.id == inbox_id,
                WeChatInbox.user_id == user_id,
                WeChatInbox.binding_epoch == binding_epoch,
                WeChatInbox.parse_status == "valid",
                WeChatInbox.processing_status.in_(["received", "retry_wait", "claimed"]),
                (WeChatInbox.next_attempt_at.is_(None)) | (WeChatInbox.next_attempt_at <= now),
                (WeChatInbox.claim_until.is_(None)) | (WeChatInbox.claim_until <= now),
            )
            .values(
                processing_status="processing",
                claim_owner=owner_id,
                claim_until=now + timedelta(seconds=claim_seconds),
                attempt_count=WeChatInbox.attempt_count + 1,
                error_category=None,
                error_detail_redacted=None,
            )
        )
        return result.rowcount == 1


async def finish_inbox_item(
    *,
    user_id: UUID,
    inbox_id: UUID,
    owner_id: UUID,
    succeeded: bool,
    error_category: str | None = None,
) -> bool:
    """CAS-complete or schedule retry for a claimed inbox item."""
    settings = get_settings()
    async with get_session_context(user_id=user_id) as session:
        inbox = await session.scalar(
            select(WeChatInbox).where(
                WeChatInbox.id == inbox_id,
                WeChatInbox.user_id == user_id,
                WeChatInbox.claim_owner == owner_id,
                WeChatInbox.processing_status == "processing",
            )
        )
        if inbox is None:
            return False
        inbox.claim_owner = None
        inbox.claim_until = None
        if succeeded:
            inbox.processing_status = "completed"
            inbox.processed_at = datetime.now(UTC)
            inbox.next_attempt_at = None
        elif inbox.attempt_count >= settings.wechat_agent_max_attempts:
            inbox.processing_status = "dead_letter"
            inbox.error_category = error_category or "processing_failed"
            inbox.next_attempt_at = None
        else:
            inbox.processing_status = "retry_wait"
            inbox.error_category = error_category or "processing_failed"
            inbox.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=min(300, 2 ** min(inbox.attempt_count, 8))
            )
        await session.flush()
        return True


__all__.extend(["claim_inbox_item", "finish_inbox_item"])
