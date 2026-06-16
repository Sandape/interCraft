"""Avatar REST API (Feature 013 — User Avatar).

Mounted at /api/v1/users/me:
- POST   /avatar                  Upload or replace the caller's avatar
- GET    /avatar/{avatar_id}      Fetch the avatar bytes (owner-only)
- DELETE /avatar                  Remove the caller's avatar
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.avatars.schemas import AvatarOut, AvatarRemoveResponse
from app.modules.avatars.service import (
    AvatarError,
    DimensionTooLargeError,
    EmptyFileError,
    FileTooLargeError,
    StorageWriteError,
    UnsupportedFormatError,
    get_avatar_for_user,
    read_upload,
    remove_user_avatar,
    save_avatar_bytes,
    validate_image,
)

log = get_logger(__name__)

router = APIRouter(prefix="/users/me/avatar", tags=["avatars"])


def _http_error_from(exc: AvatarError) -> HTTPException:
    """Map a service exception to a project-standard HTTP error envelope."""
    code: str = getattr(exc, "code", "AVATAR_ERROR")
    if isinstance(exc, EmptyFileError):
        return HTTPException(status_code=400, detail={"error": code, "message": str(exc)})
    if isinstance(exc, FileTooLargeError):
        return HTTPException(status_code=413, detail={"error": code, "message": str(exc)})
    if isinstance(exc, UnsupportedFormatError):
        return HTTPException(status_code=415, detail={"error": code, "message": str(exc)})
    if isinstance(exc, DimensionTooLargeError):
        return HTTPException(status_code=422, detail={"error": code, "message": str(exc)})
    if isinstance(exc, StorageWriteError):
        return HTTPException(status_code=500, detail={"error": code, "message": str(exc)})
    return HTTPException(status_code=500, detail={"error": code, "message": str(exc)})


@router.post("", response_model=AvatarOut, status_code=200)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
) -> AvatarOut:
    settings = get_settings()
    log.info(
        "avatar.upload.start",
        user_id=str(user_id),
        declared_content_type=file.content_type,
        declared_filename=file.filename,
    )

    try:
        # Pre-check declared Content-Length when the client sends one
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > settings.avatar_max_bytes:
                    raise FileTooLargeError(
                        f"图片不能超过 {settings.avatar_max_bytes // (1024 * 1024)} MB"
                    )
            except ValueError:
                pass

        raw = await read_upload(file, settings.avatar_max_bytes)
        content_type, width, height = validate_image(raw)
        result = await save_avatar_bytes(
            db,
            user_id=user_id,
            content_type=content_type,
            raw=raw,
            width=width,
            height=height,
        )
    except AvatarError as e:
        log.warning(
            "avatar.upload.reject",
            user_id=str(user_id),
            code=getattr(e, "code", "AVATAR_ERROR"),
            message=str(e),
        )
        raise _http_error_from(e) from e

    return result


@router.get("/{avatar_id}")
async def get_avatar(
    avatar_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
) -> FileResponse:
    row = await get_avatar_for_user(db, user_id, avatar_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "AVATAR_NOT_FOUND", "message": "头像不存在"})

    settings = get_settings()
    full_path = settings.avatar_storage_dir + "/" + row.storage_path
    return FileResponse(
        full_path,
        media_type=row.content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("", response_model=AvatarRemoveResponse)
async def remove_avatar(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
) -> AvatarRemoveResponse:
    removed = await remove_user_avatar(db, user_id)
    if not removed:
        raise HTTPException(status_code=404, detail={"error": "NO_AVATAR", "message": "用户没有头像"})
    return AvatarRemoveResponse()


__all__ = ["router"]
