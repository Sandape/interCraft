"""Phase 6 — Account endpoints: lifecycle, export, import, notification, devices, security."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse

from app.api.deps import db_session_user_dep, get_current_user, get_current_user_id
from app.modules.account.export_service import ExportService, ExportError
from app.modules.account.import_service import ImportService, ImportError
from app.modules.account.lifecycle import LifecycleService, LifecycleError
from app.modules.account.notification import NotificationService
from app.modules.account.schemas import (
    CancelDeletionResponse,
    ChangePasswordInput,
    ChangePasswordResponse,
    DeleteAccountInput,
    DeleteAccountResponse,
    DeletionStatusResponse,
    DevicesResponse,
    DeviceOut,
    ExportCreateResponse,
    ExportInput,
    ExportStatusResponse,
    ImportResponse,
    LoginHistoryItem,
    LoginHistoryResponse,
    LogoutOtherDevicesResponse,
    NotificationCenterResponse,
    NotificationOut,
)
from app.modules.account.subscription import SubscriptionService, SubscriptionError
from app.modules.auth.models import User

router = APIRouter()


# ---- Subscription ----

@router.get("/subscription/plans", status_code=200)
async def list_subscription_plans(
    db: AsyncSession = Depends(db_session_user_dep),
    user = Depends(get_current_user),
):
    """Get all available subscription plans."""
    from app.modules.account.subscription import SubscriptionService
    svc = SubscriptionService(db)
    plans = await svc.list_plans()
    return {"plans": [{"plan": p.plan, "monthly_token_quota": p.monthly_token_quota, "features": p.features, "is_active": p.is_active} for p in plans]}


@router.get("/subscription/current", status_code=200)
async def get_current_subscription(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """Get current user's subscription status."""
    from app.modules.account.subscription import SubscriptionService
    svc = SubscriptionService(db, user.id)
    return await svc.get_current_subscription()


@router.post("/subscription/pre-check", status_code=200)
async def subscription_pre_check(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """Pre-check before starting an interview."""
    from app.modules.account.subscription import SubscriptionService, SubscriptionError
    svc = SubscriptionService(db, user.id)
    try:
        return await svc.pre_check()
    except SubscriptionError as e:
        from fastapi import HTTPException
        raise HTTPException(429, detail=str(e))


# ---- Lifecycle ----

@router.post("/account/delete", status_code=status.HTTP_200_OK)
async def delete_account(
    body: DeleteAccountInput,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> DeleteAccountResponse:
    if not body.confirmation:
        raise HTTPException(400, detail="请确认注销操作")

    svc = LifecycleService(db, user.id)
    try:
        result = await svc.delete_account()
    except LifecycleError as e:
        raise HTTPException(409, detail=str(e))

    return DeleteAccountResponse(
        status=result["status"],
        scheduled_purge_at=result["scheduled_purge_at"],
        cancellation_deadline=result["cancellation_deadline"],
        message="您的账号已进入注销流程。7 天内可取消，90 天后将物理清除。",
    )


@router.post("/account/cancel-deletion", status_code=status.HTTP_200_OK)
async def cancel_deletion(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> CancelDeletionResponse:
    svc = LifecycleService(db, user.id)
    try:
        result = await svc.cancel_deletion()
    except LifecycleError as e:
        code = getattr(e, "code", None)
        if code == "CANCELLATION_DEADLINE_PASSED":
            raise HTTPException(409, detail="冷静期已过，无法取消注销")
        raise HTTPException(409, detail=str(e))

    return CancelDeletionResponse(status=result["status"], message="账号注销已取消，您的账号已恢复正常。")


@router.get("/account/deletion-status", status_code=status.HTTP_200_OK)
async def deletion_status(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> DeletionStatusResponse:
    svc = LifecycleService(db, user.id)
    result = await svc.get_deletion_status()
    return DeletionStatusResponse(**result)


# ---- Export ----

@router.post("/account/export", status_code=status.HTTP_202_ACCEPTED)
async def create_export(
    body: ExportInput,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> ExportCreateResponse:
    svc = ExportService(db, user.id)
    try:
        task = await svc.create_export_task(body.include)
    except ExportError as e:
        raise HTTPException(400, detail=str(e))
    return ExportCreateResponse(task_id=task.id, status="pending", estimated_minutes=3)


@router.get("/account/export/{task_id}/status", status_code=status.HTTP_200_OK)
async def export_status(
    task_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> ExportStatusResponse:
    svc = ExportService(db, user.id)
    task = await svc.get_task(task_id)
    if task is None:
        raise HTTPException(404, detail="导出任务不存在")

    download_url = None
    if task.status == "completed":
        download_url = f"/api/v1/account/export/{task_id}/download"

    return ExportStatusResponse(
        task_id=task.id,
        status=task.status,
        progress_pct=task.progress_pct,
        created_at=task.created_at,
        completed_at=task.completed_at,
        download_url=download_url,
        expires_at=task.expires_at,
        file_size_bytes=task.file_size_bytes,
    )


@router.get("/account/export/{task_id}/download", status_code=status.HTTP_200_OK)
async def export_download(
    task_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = ExportService(db, user.id)
    task = await svc.get_task(task_id)
    if task is None:
        raise HTTPException(404, detail="导出任务不存在")
    if task.status != "completed":
        raise HTTPException(409, detail="导出尚未完成")
    if not task.file_path:
        raise HTTPException(404, detail="文件不存在")

    return FileResponse(
        task.file_path,
        media_type="application/zip",
        filename=f"export-{user.id}-{task.created_at.strftime('%Y%m%d')}.zip",
    )


# ---- Import ----

@router.post("/resumes/import", status_code=status.HTTP_201_CREATED)
async def import_resume(
    file: UploadFile = File(...),
    branch_name: str | None = Form(None),
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> ImportResponse:
    content = await file.read()
    text_content = content.decode("utf-8")

    svc = ImportService(db, user.id)
    name = branch_name or f"导入简历 - {file.filename or 'resume'}"

    try:
        if file.filename and file.filename.endswith(".json"):
            result = await svc.import_json(text_content, name)
        else:
            result = await svc.import_markdown(text_content, name)
    except ImportError as e:
        raise HTTPException(400, detail=str(e))

    return ImportResponse(
        branch_id=result["branch_id"],
        branch_name=result["branch_name"],
        blocks_count=result["blocks_count"],
        message="导入完成，请检查简历内容。",
    )


# ---- Notification Center ----

@router.get("/account/notification-center", status_code=status.HTTP_200_OK)
async def notification_center(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> NotificationCenterResponse:
    svc = NotificationService(db, user.id)
    notifications = await svc.list_notifications()
    unread_count = await svc.get_unread_count()

    return NotificationCenterResponse(
        notifications=[
            NotificationOut(
                id=n.id,
                type=n.type,
                title=n.title,
                message=n.message,
                related_task_id=n.related_task_id,
                is_read=n.is_read,
                created_at=n.created_at,
            )
            for n in notifications
        ],
        unread_count=unread_count,
    )


# ---- Devices ----

@router.get("/settings/devices", status_code=status.HTTP_200_OK)
async def list_devices(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> DevicesResponse:
    """List devices from auth_sessions table (M09)."""
    from sqlalchemy import select as sa_select
    from app.modules.auth.models import AuthSession

    result = await db.execute(
        sa_select(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.deleted_at.is_(None))
        .order_by(AuthSession.last_seen_at.desc())
    )
    sessions = result.scalars().all()

    return DevicesResponse(
        devices=[
            DeviceOut(
                id=s.id,
                device_name=s.device_name,
                browser=s.last_seen_ua,
                ip=s.last_seen_ip,
                last_seen_at=s.last_seen_at,
                created_at=s.created_at,
                is_current=False,
            )
            for s in sessions
        ]
    )


@router.post("/settings/devices/logout-others", status_code=status.HTTP_200_OK)
async def logout_other_devices(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> LogoutOtherDevicesResponse:
    """Terminate all other sessions except current."""
    from sqlalchemy import update as sa_update, delete as sa_delete
    from app.modules.auth.models import AuthSession

    result = await db.execute(
        sa_delete(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.id != getattr(user, "current_session_id", None),
        )
    )
    return LogoutOtherDevicesResponse(
        message="其他设备已下线",
        sessions_terminated=result.rowcount,  # type: ignore[attr-defined]
    )


# ---- Security ----

@router.post("/settings/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    body: ChangePasswordInput,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> ChangePasswordResponse:
    from app.core.security import hash_password, verify_password

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, detail="当前密码不正确")

    new_hash = hash_password(body.new_password)
    from sqlalchemy import update as sa_update
    await db.execute(sa_update(User).where(User.id == user.id).values(password_hash=new_hash))

    return ChangePasswordResponse(message="密码已更新")


@router.get("/settings/login-history", status_code=status.HTTP_200_OK)
async def login_history(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(db_session_user_dep),
) -> LoginHistoryResponse:
    from sqlalchemy import select as sa_select
    from app.modules.auth.models import AuthSession

    result = await db.execute(
        sa_select(AuthSession)
        .where(AuthSession.user_id == user.id)
        .order_by(AuthSession.created_at.desc())
        .limit(50)
    )
    sessions = result.scalars().all()

    return LoginHistoryResponse(
        items=[
            LoginHistoryItem(
                id=s.id,
                ip=s.last_seen_ip,
                user_agent=s.last_seen_ua,
                device_name=s.device_name,
                created_at=s.created_at,
            )
            for s in sessions
        ]
    )
