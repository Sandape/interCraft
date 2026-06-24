"""US9 Resume branch avatar router.

- POST   /resume-branches/{branch_id}/avatar          upload (multipart)
- GET    /resume-branches/{branch_id}/avatar          fetch bytes (owner)
- DELETE /resume-branches/{branch_id}/avatar          remove file + clear url
- POST   /resume-branches/{branch_id}/avatar/inherit  copy from parent

Stored file path is internal; the URL exposed on `resume_branches.avatar_url`
is the API endpoint itself, which serves the persisted bytes.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.core.logging import get_logger
from app.modules.resumes import avatar_service
from app.modules.resumes.schemas import PatchBranchInput

log = get_logger(__name__)

router = APIRouter()


def _http_error_from(exc: avatar_service.AvatarError) -> HTTPException:
    code: str = getattr(exc, "code", "AVATAR_ERROR")
    status_map = {
        "EMPTY_FILE": 400,
        "FILE_TOO_LARGE": 413,
        "UNSUPPORTED_FORMAT": 415,
        "STORAGE_WRITE_ERROR": 500,
        "BRANCH_NOT_FOUND": 404,
    }
    http_status = status_map.get(code, 500)
    return HTTPException(status_code=http_status, detail={"error": code, "message": str(exc)})


@router.post(
    "/resume-branches/{branch_id}/avatar",
    status_code=200,
)
async def upload_branch_avatar(
    branch_id: UUID,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
) -> dict[str, str]:
    try:
        result = await avatar_service.upload_branch_avatar(db, user_id, branch_id, file)
    except avatar_service.AvatarError as e:
        log.warning(
            "resume_avatar.upload.reject",
            user_id=str(user_id),
            branch_id=str(branch_id),
            code=getattr(e, "code", "AVATAR_ERROR"),
            message=str(e),
        )
        raise _http_error_from(e) from e
    await db.commit()
    return result


@router.get("/resume-branches/{branch_id}/avatar")
async def get_branch_avatar(
    branch_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
) -> FileResponse:
    pair = await avatar_service.get_branch_avatar(db, user_id, branch_id)
    if pair is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "AVATAR_NOT_FOUND", "message": "分支没有头像"},
        )
    path, content_type = pair
    return FileResponse(
        path,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete(
    "/resume-branches/{branch_id}/avatar",
    status_code=200,
)
async def delete_branch_avatar(
    branch_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
) -> JSONResponse:
    removed = await avatar_service.delete_branch_avatar(db, user_id, branch_id)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail={"error": "NO_AVATAR", "message": "分支没有头像"},
        )
    await db.commit()
    return JSONResponse(content={"ok": True})


@router.post(
    "/resume-branches/{branch_id}/avatar/inherit",
    status_code=200,
)
async def inherit_branch_avatar(
    branch_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
) -> JSONResponse:
    ok = await avatar_service.inherit_branch_avatar(db, user_id, branch_id)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "CANNOT_INHERIT",
                "message": "父级没有头像或本分支没有父级",
            },
        )
    await db.commit()
    return JSONResponse(content={"ok": True})


__all__ = ["router", "PatchBranchInput"]
