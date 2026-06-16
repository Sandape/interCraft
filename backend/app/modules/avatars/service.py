"""Avatar service — validation, storage, and cleanup.

Per Feature 013 spec:
- 2 MB hard size cap (enforced by router pre-check and here)
- JPG / PNG only, validated by content sniff (Pillow primary, imghdr fallback)
- 2048px max-dimension (Pillow) — skipped when Pillow unavailable
- Atomic replacement: tmp file + os.replace + DB transaction
- Cleanup of *.tmp files older than 1 h on each upload
"""
from __future__ import annotations

import contextlib
import imghdr
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from PIL import Image

    _PILLOW_AVAILABLE = True
except Exception:  # pragma: no cover - Pillow optional
    _PILLOW_AVAILABLE = False

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.auth.models import User
from app.modules.avatars.models import UserAvatar
from app.modules.avatars.schemas import AvatarOut

log = get_logger(__name__)


# ---- typed errors (mapped to HTTP at the router) ----


class AvatarError(Exception):
    """Base class for avatar service errors."""


class EmptyFileError(AvatarError):
    code = "EMPTY_FILE"


class FileTooLargeError(AvatarError):
    code = "FILE_TOO_LARGE"


class UnsupportedFormatError(AvatarError):
    code = "UNSUPPORTED_FORMAT"


class DimensionTooLargeError(AvatarError):
    code = "DIMENSION_TOO_LARGE"


class StorageWriteError(AvatarError):
    code = "STORAGE_WRITE_ERROR"


# ---- validation ----

_JPEG_MAGIC = {b"\xff\xd8\xff"}
_PNG_MAGIC = {b"\x89PNG\r\n\x1a\n"}


def _detect_mime(raw: bytes) -> str | None:
    """Sniff image format from magic bytes. Returns normalized mime or None."""
    if any(raw.startswith(m) for m in _JPEG_MAGIC):
        return "image/jpeg"
    if any(raw.startswith(m) for m in _PNG_MAGIC):
        return "image/png"
    # Fall back to stdlib imghdr for slightly more thorough sniff
    kind = imghdr.what(None, raw)
    if kind == "jpeg":
        return "image/jpeg"
    if kind == "png":
        return "image/png"
    return None


def _ext_for(mime: str) -> str:
    return "jpg" if mime == "image/jpeg" else "png"


def validate_image(raw: bytes) -> tuple[str, int | None, int | None]:
    """Validate an image byte buffer.

    Returns (normalized_content_type, width, height). Raises a typed
    AvatarError subclass on any failure.
    """
    settings = get_settings()
    if not raw:
        raise EmptyFileError("未选择文件")
    if len(raw) > settings.avatar_max_bytes:
        raise FileTooLargeError(f"图片不能超过 {settings.avatar_max_bytes // (1024 * 1024)} MB")

    mime = _detect_mime(raw)
    if mime is None:
        raise UnsupportedFormatError("仅支持 JPG / PNG 图片")

    width: int | None = None
    height: int | None = None
    if _PILLOW_AVAILABLE:
        try:
            from io import BytesIO

            img = Image.open(BytesIO(raw))
            img.verify()
            img = Image.open(BytesIO(raw))
            width, height = img.size
        except Exception as e:  # corrupt or unparsable image
            raise UnsupportedFormatError("图片文件无法解析") from e
        if width > settings.avatar_max_dimension or height > settings.avatar_max_dimension:
            raise DimensionTooLargeError(
                f"图片尺寸不能超过 {settings.avatar_max_dimension}x{settings.avatar_max_dimension}"
            )
    # When Pillow is unavailable, the frontend is expected to enforce the
    # 2048px limit. We still accept the file as long as the magic bytes and
    # size pass.

    return mime, width, height


# ---- storage ----


def _storage_dir() -> Path:
    s = get_settings()
    return Path(s.avatar_storage_dir)


def _cleanup_tmp_files(user_id: UUID) -> None:
    """Remove any *.tmp files in {storage_dir}/{user_id} older than 1 hour."""
    try:
        user_dir = _storage_dir() / str(user_id)
        if not user_dir.is_dir():
            return
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        for entry in user_dir.glob("*.tmp"):
            try:
                mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    entry.unlink(missing_ok=True)
            except OSError:
                # Best-effort: never fail the upload because of cleanup
                pass
    except Exception:  # pragma: no cover - best effort
        pass


async def save_avatar_bytes(
    db: AsyncSession,
    user_id: UUID,
    content_type: str,
    raw: bytes,
    width: int | None,
    height: int | None,
) -> AvatarOut:
    """Persist the avatar bytes, insert a user_avatars row, point the user at it.

    Returns the URL the client should put in <img src>.
    """
    _cleanup_tmp_files(user_id)

    avatar_id = uuid.uuid4()
    ext = _ext_for(content_type)
    user_dir = _storage_dir() / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    final_path = user_dir / f"{avatar_id}.{ext}"
    tmp_path = user_dir / f"{avatar_id}.{ext}.tmp"

    try:
        with open(tmp_path, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)
    except OSError as e:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise StorageWriteError("无法保存头像到存储") from e

    storage_path = f"{user_id}/{avatar_id}.{ext}"
    row = UserAvatar(
        id=avatar_id,
        user_id=user_id,
        content_type=content_type,
        byte_size=len(raw),
        width=width,
        height=height,
        storage_path=storage_path,
    )
    db.add(row)
    await db.flush()

    user = await db.get(User, user_id)
    if user is None:
        raise StorageWriteError("用户不存在,无法关联头像")
    user.avatar_id = avatar_id
    await db.flush()
    await db.commit()
    await db.refresh(row)
    await db.refresh(user)

    log.info(
        "avatar.upload.success",
        user_id=str(user_id),
        avatar_id=str(avatar_id),
        content_type=content_type,
        byte_size=len(raw),
    )

    return AvatarOut(
        avatar_id=row.id,
        url=f"/api/v1/users/me/avatar/{row.id}",
        content_type=row.content_type,
        byte_size=row.byte_size,
        width=row.width,
        height=row.height,
        created_at=row.created_at,
    )


async def get_avatar_for_user(db: AsyncSession, user_id: UUID, avatar_id: UUID) -> UserAvatar | None:
    """Return the avatar row if it belongs to the user. Otherwise None."""
    stmt = select(UserAvatar).where(UserAvatar.id == avatar_id, UserAvatar.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def remove_user_avatar(db: AsyncSession, user_id: UUID) -> bool:
    """Set users.avatar_id to NULL. Returns True if there was an avatar to remove."""
    user = await db.get(User, user_id)
    if user is None or user.avatar_id is None:
        return False
    previous_avatar_id = user.avatar_id
    user.avatar_id = None
    await db.flush()
    await db.commit()
    log.info("avatar.remove.success", user_id=str(user_id), previous_avatar_id=str(previous_avatar_id))
    return True


async def read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Read an UploadFile with a hard cap. Raises FileTooLargeError if exceeded."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(f"图片不能超过 {max_bytes // (1024 * 1024)} MB")
        chunks.append(chunk)
    return b"".join(chunks)


__all__ = [
    "AvatarError",
    "DimensionTooLargeError",
    "EmptyFileError",
    "FileTooLargeError",
    "StorageWriteError",
    "UnsupportedFormatError",
    "get_avatar_for_user",
    "read_upload",
    "remove_user_avatar",
    "save_avatar_bytes",
    "validate_image",
]
