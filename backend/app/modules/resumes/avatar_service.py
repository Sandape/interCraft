"""US9 Resume branch avatar service.

- Validate image (JPG/PNG/WEBP), Pillow-compress to ≤500 KB.
- Persist bytes under {avatar_storage_dir}/branches/{user_id}/{branch_id}.{ext}.
- Update `resume_branches.avatar_url` (+ size/position/shape defaults).
- Serve via `GET /api/v1/resume-branches/{branch_id}/avatar` (see `api_avatar.py`).

The user-profile avatar service (`app.modules.avatars`) is a different
concern and reuses its own storage dir + user_avatars table.
"""
from __future__ import annotations

import contextlib
import imghdr
import os
from io import BytesIO
from pathlib import Path
from typing import Final
from uuid import UUID

from PIL import Image
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.resumes.models import ResumeBranch

log = get_logger(__name__)

ALLOWED_MIMES: Final[frozenset[str]] = frozenset({"image/jpeg", "image/png", "image/webp"})
JPEG_MAGIC: Final[frozenset[bytes]] = frozenset({b"\xff\xd8\xff"})
PNG_MAGIC: Final[frozenset[bytes]] = frozenset({b"\x89PNG\r\n\x1a\n"})
WEBP_MAGIC: Final[frozenset[bytes]] = frozenset({b"RIFF"})
COMPRESS_TARGET_BYTES: Final[int] = 500 * 1024  # ≤ 500 KB after Pillow compression
DEFAULT_SIZE: Final[int] = 100
DEFAULT_POSITION: Final[str] = "right"
DEFAULT_SHAPE: Final[str] = "circle"


# ---- typed errors (mapped to HTTP at the router) ----


class AvatarError(Exception):
    """Base class for resume avatar service errors."""


class EmptyFileError(AvatarError):
    code = "EMPTY_FILE"


class FileTooLargeError(AvatarError):
    code = "FILE_TOO_LARGE"


class UnsupportedFormatError(AvatarError):
    code = "UNSUPPORTED_FORMAT"


class StorageWriteError(AvatarError):
    code = "STORAGE_WRITE_ERROR"


class BranchNotFoundError(AvatarError):
    code = "BRANCH_NOT_FOUND"


# ---- helpers ----


def _detect_mime(raw: bytes) -> str | None:
    """Sniff image format from magic bytes. WEBP requires RIFF + WEBP at offset 8."""
    if any(raw.startswith(m) for m in JPEG_MAGIC):
        return "image/jpeg"
    if any(raw.startswith(m) for m in PNG_MAGIC):
        return "image/png"
    if raw.startswith(b"RIFF") and len(raw) >= 12 and raw[8:12] == b"WEBP":
        return "image/webp"
    kind = imghdr.what(None, raw)
    if kind == "jpeg":
        return "image/jpeg"
    if kind == "png":
        return "image/png"
    if kind == "webp":
        return "image/webp"
    return None


def _ext_for(mime: str) -> str:
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime]


def _avatar_url(branch_id: UUID) -> str:
    return f"/api/v1/resume-branches/{branch_id}/avatar"


def _branch_dir(user_id: UUID) -> Path:
    base = Path(get_settings().avatar_storage_dir)
    return base / "branches" / str(user_id)


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


def _compress_to_jpeg(raw: bytes, mime: str) -> tuple[bytes, int, int]:
    """Pillow-compress the image to ≤ COMPRESS_TARGET_BYTES.

    Returns (compressed_bytes, width, height). The output is always JPEG
    for size predictability (PNG/WEBP → JPEG conversion when compressing).
    Original JPEG that already fits is returned as-is.
    """
    img = Image.open(BytesIO(raw))
    img.load()
    if img.mode in ("RGBA", "P"):
        # Flatten onto white for non-alpha JPEGs.
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img.convert("RGBA"), mask=None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    width, height = img.size

    # Original is already small enough and is JPEG → keep as-is.
    if mime == "image/jpeg" and len(raw) <= COMPRESS_TARGET_BYTES:
        return raw, width, height

    quality = 88
    while quality >= 40:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= COMPRESS_TARGET_BYTES:
            return data, width, height
        quality -= 8
    # Last resort: shrink dimensions and try once more.
    scale = (COMPRESS_TARGET_BYTES / max(len(buf.getvalue()), 1)) ** 0.5
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    img = img.resize(new_size, Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=70, optimize=True)
    return buf.getvalue(), new_size[0], new_size[1]


def _save_bytes(user_id: UUID, branch_id: UUID, ext: str, raw: bytes) -> Path:
    """Atomic write: tmp → fsync → os.replace."""
    branch_dir = _branch_dir(user_id)
    branch_dir.mkdir(parents=True, exist_ok=True)
    final = branch_dir / f"{branch_id}.{ext}"
    tmp = branch_dir / f"{branch_id}.{ext}.tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, final)
    except OSError as e:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise StorageWriteError("无法保存头像到存储") from e
    return final


def _delete_file(user_id: UUID, branch_id: UUID) -> None:
    """Best-effort delete any avatar file for the branch (ignore missing)."""
    branch_dir = _branch_dir(user_id)
    for ext in ("jpg", "png", "webp"):
        with contextlib.suppress(OSError):
            (branch_dir / f"{branch_id}.{ext}").unlink(missing_ok=True)


# ---- public API ----


async def get_branch_avatar(
    db: AsyncSession, user_id: UUID, branch_id: UUID
) -> tuple[Path, str] | None:
    """Return (file_path, content_type) for the avatar if one is set, else None."""
    stmt = select(ResumeBranch).where(ResumeBranch.id == branch_id)
    result = await db.execute(stmt)
    branch = result.scalar_one_or_none()
    if branch is None or branch.user_id != user_id or not branch.avatar_url:
        return None
    ext = "jpg"
    if branch.avatar_url.endswith(".png"):
        ext = "png"
    elif branch.avatar_url.endswith(".webp"):
        ext = "webp"
    p = _branch_dir(user_id) / f"{branch_id}.{ext}"
    if not p.exists():
        return None
    content_type = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[ext]
    return p, content_type


async def upload_branch_avatar(
    db: AsyncSession,
    user_id: UUID,
    branch_id: UUID,
    file: UploadFile,
) -> dict[str, str]:
    """Validate, Pillow-compress, persist; update resume_branches.avatar_url.

    Returns `{"url": ..., "branch_id": ...}`. Size/position/shape are
    defaulted — the user edits them via PATCH branch.
    """
    settings = get_settings()
    raw = await read_upload(file, settings.avatar_max_bytes)
    if not raw:
        raise EmptyFileError("未选择文件")
    mime = _detect_mime(raw)
    if mime is None:
        raise UnsupportedFormatError("仅支持 JPG / PNG / WEBP 图片")

    # Find the branch (RLS enforces owner; double-check for safety).
    stmt = select(ResumeBranch).where(ResumeBranch.id == branch_id)
    result = await db.execute(stmt)
    branch = result.scalar_one_or_none()
    if branch is None or branch.user_id != user_id:
        raise BranchNotFoundError("分支不存在")

    compressed, _w, _h = _compress_to_jpeg(raw, mime)
    out_ext = "jpg"
    _save_bytes(user_id, branch_id, out_ext, compressed)

    from datetime import UTC, datetime

    branch.avatar_url = _avatar_url(branch_id)
    # Only set defaults if missing; preserve user-tuned placement.
    if branch.avatar_size is None:
        branch.avatar_size = DEFAULT_SIZE
    if branch.avatar_position is None:
        branch.avatar_position = DEFAULT_POSITION
    if branch.avatar_shape is None:
        branch.avatar_shape = DEFAULT_SHAPE
    branch.avatar_updated_at = datetime.now(UTC)
    branch.last_edited_at = branch.avatar_updated_at
    await db.flush()
    await db.refresh(branch)

    log.info(
        "resume_avatar.upload.success",
        user_id=str(user_id),
        branch_id=str(branch_id),
        bytes_in=len(raw),
        bytes_out=len(compressed),
    )
    return {"url": branch.avatar_url, "branch_id": str(branch_id)}


async def delete_branch_avatar(
    db: AsyncSession, user_id: UUID, branch_id: UUID
) -> bool:
    """Clear avatar_url + delete file. Returns True if there was an avatar."""
    stmt = select(ResumeBranch).where(ResumeBranch.id == branch_id)
    result = await db.execute(stmt)
    branch = result.scalar_one_or_none()
    if branch is None or branch.user_id != user_id:
        return False
    if not branch.avatar_url:
        return False
    _delete_file(user_id, branch_id)
    branch.avatar_url = None
    branch.avatar_updated_at = None
    branch.last_edited_at = None  # let repo normalize if needed
    from datetime import UTC, datetime

    branch.last_edited_at = datetime.now(UTC)
    await db.flush()
    log.info("resume_avatar.delete.success", user_id=str(user_id), branch_id=str(branch_id))
    return True


async def inherit_branch_avatar(
    db: AsyncSession, user_id: UUID, branch_id: UUID
) -> bool:
    """Copy avatar fields from parent. Returns False if no parent or parent has none."""
    stmt = select(ResumeBranch).where(ResumeBranch.id == branch_id)
    result = await db.execute(stmt)
    branch = result.scalar_one_or_none()
    if branch is None or branch.user_id != user_id or branch.parent_id is None:
        return False
    parent_stmt = select(ResumeBranch).where(ResumeBranch.id == branch.parent_id)
    parent = (await db.execute(parent_stmt)).scalar_one_or_none()
    if parent is None or not parent.avatar_url:
        return False
    # Copy metadata + persist a copy of the file under the child's id so the
    # URL is stable even if the parent's avatar is later changed/deleted.
    raw_ext = "jpg"
    src = _branch_dir(parent.user_id) / f"{parent.id}.{raw_ext}"
    if src.exists():
        data = src.read_bytes()
        _save_bytes(user_id, branch_id, raw_ext, data)

    from datetime import UTC, datetime

    branch.avatar_url = _avatar_url(branch_id)
    branch.avatar_size = parent.avatar_size
    branch.avatar_position = parent.avatar_position
    branch.avatar_shape = parent.avatar_shape
    branch.avatar_updated_at = datetime.now(UTC)
    branch.last_edited_at = branch.avatar_updated_at
    await db.flush()
    log.info(
        "resume_avatar.inherit.success",
        user_id=str(user_id),
        branch_id=str(branch_id),
        parent_id=str(parent.id),
    )
    return True


__all__ = [
    "AvatarError",
    "BranchNotFoundError",
    "EmptyFileError",
    "FileTooLargeError",
    "StorageWriteError",
    "UnsupportedFormatError",
    "delete_branch_avatar",
    "get_branch_avatar",
    "inherit_branch_avatar",
    "read_upload",
    "upload_branch_avatar",
]
