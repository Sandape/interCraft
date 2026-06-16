"""Phase 13 — User Avatar module.

Owns avatar upload, fetch, and remove. Stores blobs on the local file
system under `avatar_storage_dir/{user_id}/{avatar_id}.{ext}`. Auth is
owner-only: the fetch route returns 404 for any caller other than the
avatar owner.

Pillow is an optional dependency. When Pillow is installed, uploaded
images are re-encoded (strips EXIF and normalizes to JPG/PNG) and the
dimension cap is enforced server-side. When Pillow is not installed,
the original bytes are stored after a content-sniff check.
"""
from __future__ import annotations

from app.modules.avatars.router import router

__all__ = ["router"]
