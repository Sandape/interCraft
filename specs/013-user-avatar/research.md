# Research: User Avatar Upload and Display

**Date**: 2026-06-16 | **Feature**: 013-user-avatar | **Spec**: [spec.md](./spec.md)

## Unknowns from Technical Context

| ID | Unknown | Status | Resolution |
|---|---|---|---|
| U1 | How to validate image content (sniff, dimensions, re-encode) | RESOLVED | Pillow primary, stdlib `imghdr` fallback |
| U2 | How to key storage paths for non-enumerable, owner-only URLs | RESOLVED | `{user_id}/{uuidv4}.{ext}` |
| U3 | How to atomically replace the active avatar | RESOLVED | Temp file + `os.replace()` + DB transaction |
| U4 | How to clean up orphan avatars | RESOLVED | Background sweep or first-write check; for MVP, GC on next upload |
| U5 | How to serve avatar bytes through FastAPI with auth | RESOLVED | `FileResponse` with owner check in dependency |
| U6 | How to update CLAUDE.md / agent context for this slice | RESOLVED | Append a `Feature 013 — User Avatar (in progress)` line |

---

## U1 — Image validation strategy

**Decision**: Use Pillow (`PIL.Image`) for content sniff, dimension check, EXIF strip, and re-encode. When Pillow is not installed, fall back to `imghdr.what()` + size cap only and store the original bytes.

**Rationale**:
- Pillow is the de-facto Python image library and gives us re-encode, dimension, and EXIF strip in one call.
- The project does not currently depend on Pillow, so we make it optional. The feature still works without it (validation just becomes stricter on the frontend and the backend stores the original).
- `imghdr` is the standard-library fallback. It only sniffs; it does not give dimensions. We keep the 2048px dimension check as a *frontend* guarantee (preview + early reject) and the 2MB cap as the *backend* hard limit.

**Alternatives considered**:
- **Wand (ImageMagick binding)**: too heavy for a single file; not in pyproject.
- **`python-magic` + manual header check**: smaller surface but loses the EXIF strip; rejected.
- **Re-encoding always via Pillow**: would require Pillow as a hard dep; not justified for the MVP.

**Implication for tasks**: T-impl-service must branch on `PIL.Image` import success and document the two paths in module docstring.

---

## U2 — Storage path keying

**Decision**: `{AVATAR_STORAGE_DIR}/{user_id}/{avatar_id}.{ext}` where `avatar_id` is a `uuid.uuid4()` and `ext` is `.jpg` or `.png` derived from the normalized content type.

**Rationale**:
- `user_id` makes it trivial to enforce owner-only access: the auth check is `row.user_id == current_user.id`.
- A fresh UUIDv4 per upload makes the path unguessable. Even if the directory listing leaks, an attacker cannot enumerate other users' avatars.
- We do not embed the storage path in the user row; we keep an `avatar_id` FK so the row is a joinable, auditable reference.

**Alternatives considered**:
- **Single flat `avatars/{uuidv4}.{ext}`**: harder to bulk-delete a user's avatars.
- **`{user_id}.{ext}` (one avatar per user)**: blocks the "history of avatars" we may want later, and the file system has no transactional rename.
- **Cloud object storage key**: matches S3 patterns but adds a runtime dep; deferred per Assumptions.

**Implication for tasks**: T-impl-service must create the per-user directory lazily and tolerate concurrent `mkdir` calls (use `exist_ok=True`).

---

## U3 — Atomic avatar replacement

**Decision**: Write the new avatar bytes to `{user_id}/{avatar_id}.{ext}.tmp`, `os.fsync()`, then `os.replace(tmp, final)`. The DB update that flips `users.avatar_id` happens in the same transaction that inserted the `user_avatars` row. A separate post-commit cleanup deletes any prior `user_avatars` row whose storage file is no longer referenced.

**Rationale**:
- `os.replace()` is atomic on POSIX (and atomic on Windows when the destination and source are on the same volume, which they are).
- The DB row + file rename is "logically atomic" for a single user: readers always see either the old file or the new file, never a half-written one.
- A crashed upload leaves a `.tmp` file that the next cleanup sweep can remove.

**Alternatives considered**:
- **Two-phase commit**: overkill; we control both sides of the rename.
- **Versioning (keep N historical avatars)**: nice-to-have, not in scope for MVP.

**Implication for tasks**: T-impl-service wraps the file write + DB commit in a try/except that removes the temp file on any failure.

---

## U4 — Orphan cleanup

**Decision**: At the start of each upload, the service scans `{AVATAR_STORAGE_DIR}/{user_id}/*` and removes any `*.tmp` file older than 1 h. Periodic full-table reconciliation is out of scope for the MVP.

**Rationale**:
- This handles the common "client aborted" case without a background worker.
- A failed `os.replace()` cannot leak a temp file for long.
- We do not delete the *previous* avatar at upload time because of an outage window: if the new upload fails after writing the temp, the user still has their previous avatar.

**Alternatives considered**:
- **Cron job sweeping the whole table**: needs a worker setup we don't have yet.
- **Inline delete on upload success**: simpler but racy if the previous file is still being served.

**Implication for tasks**: T-impl-service includes a 5-line `_cleanup_tmp_files(user_id)` helper.

---

## U5 — Serving avatar bytes through FastAPI

**Decision**: `GET /api/v1/users/me/avatar/{avatar_id}` returns a `FileResponse` with the right content type and `Cache-Control: private, max-age=3600`. The auth dep loads the `user_avatars` row, checks `row.user_id == current_user.id`, and 404s otherwise.

**Rationale**:
- A single endpoint keeps the auth check in one place.
- `FileResponse` streams the file without loading it all into memory.
- A 1-hour `Cache-Control: private` lets the browser cache without leaking to shared caches.

**Alternatives considered**:
- **Signed time-limited URL**: works for cross-origin sharing but adds signing overhead we don't need.
- **Embed image as base64 in the user payload**: bloats every `me` response by 2MB.

**Implication for tasks**: T-impl-router must enforce the ownership check; the cross-tenant test in T-test-isolation hits user A's avatar with user B's token and asserts 404.

---

## U6 — CLAUDE.md / agent context

**Decision**: Append a `**Feature 013 — User Avatar (in progress)**` line under the existing `<!-- SPECKIT START -->` block in `CLAUDE.md` once the implementation is in progress. No other context files need updating for this slice.

**Rationale**:
- The slice is bounded; it does not introduce a new architectural pattern that downstream specs need to know about.
- The new `UserAvatar` model is colocated with the user-scoped RLS, so other specs that touch the user table already have the context.

**Implication for tasks**: T-finalize touches CLAUDE.md in the same commit as the migration.

---

## Dependency summary

| Dep | Required? | Notes |
|---|---|---|
| Pillow | Optional | Re-encode + EXIF strip; falls back to content-sniff if absent |
| python-multipart | Required | Already in pyproject; needed for `UploadFile` |
| alembic | Required | Already in pyproject; new migration `0008_user_avatar.py` |
| Playwright | Required (E2E) | Already in pyproject; new spec `tests/e2e/user-avatar.spec.ts` |

No new top-level dependencies are introduced. Pillow is intentionally optional and the fallback path is documented in the service module docstring.
