"""Phase 6 — Audit endpoints (M22): user + admin."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user
from app.modules.audit.schemas import (
    AdminAuditLogListResponse,
    AdminAuditLogOut,
    AuditLogListResponse,
    AuditLogOut,
)
from app.modules.audit.service import AuditService

router = APIRouter()


def _require_admin(user):
    if user.role != "admin":
        raise HTTPException(403, detail="Admin access required")
    return user


@router.get("/audit-logs", status_code=200, response_model=AuditLogListResponse)
async def get_audit_logs(
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """Get current user's audit logs (RLS filters by actor_id)."""
    svc = AuditService(db)
    items, total = await svc.query(
        actor_id=user.id,
        resource_type=resource_type,
        action=action,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )

    return AuditLogListResponse(
        items=[
            AuditLogOut(
                id=item.id,
                action=item.action,
                resource_type=item.resource_type,
                resource_id=item.resource_id,
                old_values=item.old_values,
                new_values=item.new_values,
                ip_address=item.ip_address,
                user_agent=item.user_agent,
                token_usage=item.token_usage,
                duration_ms=item.duration_ms,
                node_input_summary=item.node_input_summary,
                node_output_summary=item.node_output_summary,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/admin/audit-logs", status_code=200, response_model=AdminAuditLogListResponse)
async def get_all_audit_logs(
    user_id: UUID | None = Query(None),
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin = Depends(_require_admin),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """Get all users' audit logs (admin only)."""
    svc = AuditService(db)
    # Admin bypasses actor_id filter — query without it
    items, total = await svc.query(
        actor_id=user_id,  # Optional filter by specific user
        resource_type=resource_type,
        action=action,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )

    return AdminAuditLogListResponse(
        items=[
            AdminAuditLogOut(
                id=item.id,
                actor_id=item.actor_id,
                action=item.action,
                resource_type=item.resource_type,
                resource_id=item.resource_id,
                old_values=item.old_values,
                new_values=item.new_values,
                ip_address=item.ip_address,
                user_agent=item.user_agent,
                token_usage=item.token_usage,
                duration_ms=item.duration_ms,
                node_input_summary=item.node_input_summary,
                node_output_summary=item.node_output_summary,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
