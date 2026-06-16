# Data Model: User Avatar

**Date**: 2026-06-16 | **Feature**: 013-user-avatar | **Spec**: [spec.md](./spec.md)

## Entities

### `user_avatars` (new table)

Represents a single uploaded avatar file owned by a single user. Each user has at most one *active* avatar (pointed to by `users.avatar_id`), but the table can keep historical records for audit / undo purposes.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID PK | NOT NULL, default `uuidv7()` | Stable identifier used in URLs and FKs |
| `user_id` | UUID FK → `users.id` | NOT NULL, ON DELETE CASCADE | Owner of the avatar |
| `content_type` | TEXT | NOT NULL, CHECK IN (`image/jpeg`, `image/png`) | Normalized MIME after re-encode |
| `byte_size` | INTEGER | NOT NULL, CHECK (0 < byte_size <= 2_097_152) | Bytes on disk |
| `width` | INTEGER | NULL, CHECK (0 < width <= 2048) | Pixel width after re-encode (NULL if Pillow unavailable) |
| `height` | INTEGER | NULL, CHECK (0 < height <= 2048) | Pixel height after re-encode (NULL if Pillow unavailable) |
| `storage_path` | TEXT | NOT NULL, UNIQUE | Relative path under `AVATAR_STORAGE_DIR`; format `{user_id}/{avatar_id}.{ext}` |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | Upload timestamp |

Indexes:
- `ix_user_avatars_user_id_created_at` on `(user_id, created_at DESC)` — for "list my avatars" and cleanup sweeps.
- UNIQUE on `storage_path` — protects against duplicate writes.

### `users.avatar_id` (new column)

A nullable FK on the existing `users` table pointing to the user's currently active avatar.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `avatar_id` | UUID FK → `user_avatars.id` | NULL, ON DELETE SET NULL | Currently displayed avatar |

The relationship is `users.avatar_id → user_avatars.id` (many-to-one), with `user_avatars.user_id → users.id` (one-to-many back-reference). When a user removes their avatar, `users.avatar_id` is set to `NULL`; the underlying `user_avatars` row may be deleted by a future cleanup sweep but is not required to be.

## Validation rules

| Rule | Source | Action |
|---|---|---|
| File size ≤ 2 MB | FR-002, SC-005 | 413 if larger |
| File MIME in {`image/jpeg`, `image/png`} | FR-002, FR-008 | 415 if other |
| File content sniff matches declared MIME | FR-002 | 415 if mismatch (e.g., a PDF renamed `.jpg`) |
| Width and height ≤ 2048 px | FR-002 | 422 if larger |
| Authenticated user only | FR-006 | 401 if no token |
| Owner match on fetch | FR-006 | 404 if another user's avatar_id |
| Concurrent upload from same user | FR-012 | last-write-wins; no 409 |

## State transitions

The `users.avatar_id` column has three meaningful states:

```
NULL ──── upload succeeds ───► user_avatars[id=X] ──── upload another ───► user_avatars[id=Y]
                                       │
                                       └─── remove ────► NULL
```

The `user_avatars` row is created at upload time and never transitions. The `users.avatar_id` reference is the only mutable state.

## Storage

- Disk path: `{AVATAR_STORAGE_DIR}/{user_id}/{avatar_id}.{ext}` where `ext` is `jpg` or `png`.
- Atomic write: temp file `{storage_path}.tmp` → `os.replace()` → final.
- Orphan cleanup: at the start of each upload, `*.tmp` files older than 1 h are removed for that user.

## RLS

The `user_avatars` table is user-scoped (tenant column `user_id`). All reads/writes go through `db_session_user_dep` so RLS enforces `user_id = current_user_id()`. There is no admin endpoint in this slice; admin tools can be added later as a separate spec.

## Migration

- New alembic migration `0008_user_avatar.py` (down_revision: `0007_ability_profile`).
- `upgrade()`: create `user_avatars` table, add `users.avatar_id` column.
- `downgrade()`: drop FK, drop column, drop table.
- No backfill needed (existing users start with `avatar_id = NULL`).
