"""Durable, single-consumption write confirmations."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ids import new_uuid_v7
from app.modules.agent.models import (
    AgentConfirmation,
    AgentToolExecution,
    WeChatBinding,
)

Decision = Literal["approve", "edit", "reject", "cancel"]


def generate_confirmation_token() -> str:
    return secrets.token_urlsafe(16)


def hash_confirmation_token(token: str, *, secret: str) -> bytes:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).digest()


def token_matches(token: str, digest: bytes, *, secret: str) -> bool:
    return hmac.compare_digest(hash_confirmation_token(token, secret=secret), digest)


@dataclass(frozen=True, slots=True)
class IssuedConfirmation:
    token: str
    confirmation: AgentConfirmation


class ConfirmationService:
    def __init__(self, session: AsyncSession, *, user_id: UUID, secret: str | None = None) -> None:
        self.session = session
        self.user_id = user_id
        self.secret = secret or get_settings().master_key

    async def issue(
        self,
        *,
        task_id: UUID,
        tool_execution_id: UUID,
        args_hash: str,
        binding_id: UUID,
        binding_epoch: int,
        ttl_minutes: int = 15,
    ) -> IssuedConfirmation:
        if not args_hash:
            raise ValueError("args_hash is required")
        if ttl_minutes < 1 or ttl_minutes > 60:
            raise ValueError("ttl_minutes must be between 1 and 60")

        for _ in range(5):
            token = generate_confirmation_token()
            digest = hash_confirmation_token(token, secret=self.secret)
            collision = await self.session.scalar(
                select(AgentConfirmation.id).where(
                    AgentConfirmation.user_id == self.user_id,
                    AgentConfirmation.token_hash == digest,
                )
            )
            if collision is None:
                break
        else:  # pragma: no cover - cryptographically unreachable
            raise RuntimeError("unable to allocate a unique confirmation token")

        confirmation = AgentConfirmation(
            user_id=self.user_id,
            task_id=task_id,
            tool_execution_id=tool_execution_id,
            args_hash=args_hash,
            token_hash=digest,
            token_hint=token[:12],
            binding_id=binding_id,
            binding_epoch=binding_epoch,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
            version=1,
        )
        self.session.add(confirmation)
        await self.session.flush()
        await self.session.refresh(confirmation)
        return IssuedConfirmation(token=token, confirmation=confirmation)

    async def decide(
        self,
        *,
        token: str,
        task_id: UUID,
        decision: Decision,
        expected_args_hash: str,
        expected_version: int,
        edited_args: dict[str, Any] | None = None,
        source_message_id: UUID | None = None,
    ) -> AgentConfirmation | None:
        match = await self.resolve_pending(token=token, task_id=task_id)
        if match is None:
            return None

        target_status = {
            "approve": "consumed",
            "edit": "superseded",
            "reject": "rejected",
            "cancel": "cancelled",
        }[decision]
        now = datetime.now(UTC)
        statement = (
            update(AgentConfirmation)
            .where(
                AgentConfirmation.id == match.id,
                AgentConfirmation.user_id == self.user_id,
                AgentConfirmation.status == "pending",
                AgentConfirmation.version == expected_version,
                AgentConfirmation.args_hash == expected_args_hash,
                AgentConfirmation.expires_at > now,
                select(WeChatBinding.id)
                .where(
                    WeChatBinding.id == AgentConfirmation.binding_id,
                    WeChatBinding.user_id == self.user_id,
                    WeChatBinding.unbound_at.is_(None),
                    WeChatBinding.binding_epoch == AgentConfirmation.binding_epoch,
                )
                .exists(),
            )
            .values(
                status=target_status,
                decision=decision,
                edited_args_json=edited_args if decision == "edit" else None,
                source_message_id=source_message_id,
                decided_at=now,
                consumed_at=now if decision == "approve" else None,
                version=AgentConfirmation.version + 1,
            )
            .returning(AgentConfirmation)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def resolve_pending(
        self,
        *,
        token: str,
        task_id: UUID | None = None,
    ) -> AgentConfirmation | None:
        statement = select(AgentConfirmation).where(
            AgentConfirmation.user_id == self.user_id,
            AgentConfirmation.token_hint == token[:12],
            AgentConfirmation.status == "pending",
        )
        if task_id is not None:
            statement = statement.where(AgentConfirmation.task_id == task_id)
        candidates = (await self.session.execute(statement)).scalars().all()
        return next(
            (
                candidate
                for candidate in candidates
                if token_matches(token, candidate.token_hash, secret=self.secret)
            ),
            None,
        )

    async def decide_by_id(
        self,
        *,
        confirmation_id: UUID,
        decision: Decision,
        expected_version: int,
        edited_args: dict[str, Any] | None = None,
        source_message_id: UUID | None = None,
    ) -> AgentConfirmation | None:
        """Consume a web-authenticated owner-scoped confirmation by opaque ID."""
        current = await self.session.scalar(
            select(AgentConfirmation).where(
                AgentConfirmation.id == confirmation_id,
                AgentConfirmation.user_id == self.user_id,
                AgentConfirmation.status == "pending",
            )
        )
        if current is None:
            return None
        target_status = {
            "approve": "consumed",
            "edit": "superseded",
            "reject": "rejected",
            "cancel": "cancelled",
        }[decision]
        now = datetime.now(UTC)
        statement = (
            update(AgentConfirmation)
            .where(
                AgentConfirmation.id == confirmation_id,
                AgentConfirmation.user_id == self.user_id,
                AgentConfirmation.status == "pending",
                AgentConfirmation.version == expected_version,
                AgentConfirmation.expires_at > now,
                select(WeChatBinding.id)
                .where(
                    WeChatBinding.id == AgentConfirmation.binding_id,
                    WeChatBinding.user_id == self.user_id,
                    WeChatBinding.unbound_at.is_(None),
                    WeChatBinding.binding_epoch == AgentConfirmation.binding_epoch,
                )
                .exists(),
            )
            .values(
                status=target_status,
                decision=decision,
                edited_args_json=edited_args if decision == "edit" else None,
                source_message_id=source_message_id,
                decided_at=now,
                consumed_at=now if decision == "approve" else None,
                version=AgentConfirmation.version + 1,
            )
            .returning(AgentConfirmation)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def edit_and_reissue(
        self,
        *,
        token: str,
        task_id: UUID,
        expected_args_hash: str,
        expected_version: int,
        edited_args: dict[str, Any],
    ) -> IssuedConfirmation | None:
        """Validate edited arguments and atomically supersede the old proposal."""
        from app.modules.agent.runtime.context import sanitize_tool_arguments
        from app.modules.agent.tools.factory import build_production_registry

        pending = await self.resolve_pending(token=token, task_id=task_id)
        if pending is None:
            return None
        execution = await self.session.scalar(
            select(AgentToolExecution).where(
                AgentToolExecution.id == pending.tool_execution_id,
                AgentToolExecution.user_id == self.user_id,
                AgentToolExecution.status == "awaiting_confirmation",
            )
        )
        if execution is None:
            return None
        definition = build_production_registry().get(execution.tool_name)
        validated = definition.input_model.model_validate(
            sanitize_tool_arguments(edited_args)
        )
        normalized = validated.model_dump(mode="json", exclude_none=True)
        canonical = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        args_hash = hashlib.sha256(canonical.encode()).hexdigest()

        superseded = await self.decide(
            token=token,
            task_id=task_id,
            decision="edit",
            expected_args_hash=expected_args_hash,
            expected_version=expected_version,
            edited_args=normalized,
        )
        if superseded is None:
            return None
        return await self._replace_execution(execution, normalized, args_hash)

    async def edit_by_id_and_reissue(
        self,
        *,
        confirmation_id: UUID,
        expected_version: int,
        edited_args: dict[str, Any],
    ) -> IssuedConfirmation | None:
        """Web-authenticated edit variant that never exposes the secret token."""
        from app.modules.agent.runtime.context import sanitize_tool_arguments
        from app.modules.agent.tools.factory import build_production_registry

        pending = await self.session.scalar(
            select(AgentConfirmation).where(
                AgentConfirmation.id == confirmation_id,
                AgentConfirmation.user_id == self.user_id,
                AgentConfirmation.status == "pending",
            )
        )
        if pending is None:
            return None
        execution = await self.session.scalar(
            select(AgentToolExecution).where(
                AgentToolExecution.id == pending.tool_execution_id,
                AgentToolExecution.user_id == self.user_id,
                AgentToolExecution.status == "awaiting_confirmation",
            )
        )
        if execution is None:
            return None
        definition = build_production_registry().get(execution.tool_name)
        validated = definition.input_model.model_validate(
            sanitize_tool_arguments(edited_args)
        )
        normalized = validated.model_dump(mode="json", exclude_none=True)
        canonical = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        args_hash = hashlib.sha256(canonical.encode()).hexdigest()
        superseded = await self.decide_by_id(
            confirmation_id=confirmation_id,
            decision="edit",
            expected_version=expected_version,
            edited_args=normalized,
        )
        if superseded is None:
            return None
        return await self._replace_execution(execution, normalized, args_hash)

    async def _replace_execution(
        self,
        execution: AgentToolExecution,
        normalized: dict[str, Any],
        args_hash: str,
    ) -> IssuedConfirmation:
        cancelled = await self.session.execute(
            update(AgentToolExecution)
            .where(
                AgentToolExecution.id == execution.id,
                AgentToolExecution.user_id == self.user_id,
                AgentToolExecution.status == "awaiting_confirmation",
            )
            .values(status="cancelled", finished_at=datetime.now(UTC))
        )
        if cancelled.rowcount != 1:
            raise RuntimeError("confirmation proposal changed during edit")

        replacement = AgentToolExecution(
            id=new_uuid_v7(),
            task_id=execution.task_id,
            user_id=execution.user_id,
            tool_call_id=f"{execution.tool_call_id}:edit:{args_hash[:12]}",
            tool_name=execution.tool_name,
            tool_version=execution.tool_version,
            args_hash=args_hash,
            args_json=normalized,
            idempotency_key=hashlib.sha256(
                f"{execution.user_id}:{execution.task_id}:{execution.tool_name}:{args_hash}".encode()
            ).hexdigest(),
            side_effect=execution.side_effect,
            atomicity=execution.atomicity,
            status="awaiting_confirmation",
            binding_id=execution.binding_id,
            binding_epoch=execution.binding_epoch,
            claim_generation=execution.claim_generation,
        )
        self.session.add(replacement)
        await self.session.flush()
        return await self.issue(
            task_id=replacement.task_id,
            tool_execution_id=replacement.id,
            args_hash=replacement.args_hash,
            binding_id=replacement.binding_id,
            binding_epoch=replacement.binding_epoch,
        )


__all__ = [
    "ConfirmationService",
    "IssuedConfirmation",
    "generate_confirmation_token",
    "hash_confirmation_token",
    "token_matches",
]
