"""Phase 6 — Audit service (M22): write/query audit_logs with RLS."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


class AuditService:
    """Audit log write and query service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        actor_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        token_usage: int | None = None,
        duration_ms: int | None = None,
        node_input_summary: str | None = None,
        node_output_summary: str | None = None,
    ) -> None:
        """Write an audit log entry."""
        # Use raw SQL to avoid partition PK issues with ORM
        stmt = sa_text(
            """INSERT INTO audit_logs (actor_id, action, resource_type, resource_id, old_values, new_values, ip_address, user_agent, token_usage, duration_ms, node_input_summary, node_output_summary, created_at)
               VALUES (:actor_id, :action, :resource_type, :resource_id, :old_values, :new_values, :ip_address, :user_agent, :token_usage, :duration_ms, :node_input_summary, :node_output_summary, :created_at)"""
        )
        await self.db.execute(
            stmt,
            {
                "actor_id": actor_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "old_values": old_values,
                "new_values": new_values,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "token_usage": token_usage,
                "duration_ms": duration_ms,
                "node_input_summary": node_input_summary,
                "node_output_summary": node_output_summary,
                "created_at": datetime.utcnow(),
            },
        )

    async def log_ai_admin_access(
        self,
        *,
        actor_id: UUID,
        capability: str,
        field: str | None = None,
        allowed: bool,
        reason: str | None = None,
        resource_id: UUID | None = None,
        reveal_ttl_seconds: int | None = None,
    ) -> None:
        """REQ-061 T024 — audit hook for named AI admin capability / field decisions."""
        await self.log(
            actor_id=actor_id,
            action=f"ai.admin.{capability}",
            resource_type="ai_admin_capability",
            resource_id=resource_id,
            new_values={
                "capability": capability,
                "field": field,
                "allowed": allowed,
                "reason": reason,
                "reveal_ttl_seconds": reveal_ttl_seconds,
            },
        )

    async def query(
        self,
        actor_id: UUID | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Query audit logs for a specific user (RLS will auto-filter)."""
        conditions = []
        params: dict = {}

        if actor_id:
            conditions.append("actor_id = :actor_id")
            params["actor_id"] = actor_id
        if resource_type:
            conditions.append("resource_type = :resource_type")
            params["resource_type"] = resource_type
        if action:
            conditions.append("action = :action")
            params["action"] = action
        if date_from:
            conditions.append("created_at >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("created_at <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # Count
        count_result = await self.db.execute(
            sa_text(f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"),
            params,
        )
        total = count_result.scalar() or 0

        # Query
        rows_result = await self.db.execute(
            sa_text(
                f"SELECT * FROM audit_logs WHERE {where_clause} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": limit, "offset": offset},
        )
        rows = rows_result.fetchall()

        items = [
            AuditLog(
                id=row.id,
                actor_id=row.actor_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                old_values=row.old_values,
                new_values=row.new_values,
                ip_address=row.ip_address,
                user_agent=row.user_agent,
                token_usage=row.token_usage,
                duration_ms=row.duration_ms,
                node_input_summary=row.node_input_summary,
                node_output_summary=row.node_output_summary,
                created_at=row.created_at,
            )
            for row in rows
        ]

        return items, total
