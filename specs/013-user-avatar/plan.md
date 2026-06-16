# Implementation Plan: User Avatar Upload and Display

**Branch**: `013-user-avatar` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-user-avatar/spec.md`

## Summary

Implement user avatar upload end-to-end. Wire the dead "更换头像" button in `src/components/settings/ProfileTab.tsx` to a real file picker with preview, add a backend endpoint that validates, re-encodes, and stores the image, persist the avatar reference on the `users` row, and render the uploaded image across the topbar, profile page, Ability Profile share dialog, and live interview room. Storage is local file system behind a UUID-based, owner-only authenticated route.

## Technical Context

**Language/Version**: TypeScript 5.6 strict mode, React 18, Vite 5 (frontend); Python 3.11, FastAPI 0.115, SQLAlchemy 2.0 async (backend)

**Primary Dependencies**:
- Frontend: TanStack Query, lucide-react, existing Avatar component, react-router-dom
- Backend: FastAPI UploadFile + python-multipart, alembic, asyncpg, Pillow (optional, with content-sniff fallback)
- E2E: Playwright (existing `tests/e2e/` setup) + model image recognition (or 识图 MCP fallback) for visual confirmation

**Storage**:
- Postgres `users.avatar_id` (UUID, nullable, FK to a new `user_avatars` table)
- New `user_avatars` table with `id`, `user_id`, `content_type`, `byte_size`, `width`, `height`, `storage_path`, `created_at`
- Binary blobs on local disk: `backend/.data/avatars/{user_id}/{avatar_id}.{ext}`

**Testing**: pytest + httpx AsyncClient for backend; Playwright for full-stack E2E

**Target Platform**: Vite dev server (frontend) + FastAPI uvicorn (backend); modern desktop browser

**Project Type**: Web application (full-stack)

**Performance Goals**: Upload completes within 3 s for a 2MB JPG on local network; avatar fetch p95 < 200 ms (cached headers: 1 h)

**Constraints**:
- 2MB upload cap, 2048px max-dimension, JPG/PNG only
- No `alert()` or `confirm()` for upload feedback (Constitution principle II + spec FR-011)
- Reuse existing `get_current_user` and `db_session_user_dep` deps
- Reuse existing Avatar component; only feed it an `src` URL
- Reuse the existing `CLAUDE.md` local-env note (Redis 6379, Postgres online)

**Scale/Scope**: One settings tab, one topbar component, one share dialog, one interview page slot; ~6 source files, ~2 new migration, 1 new table

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Library-First | Avatar feature is a self-contained module: `backend/app/modules/avatars/` (router + service + model) and `src/api/avatar.ts` + `src/hooks/mutations/useUploadAvatar.ts` on the frontend. No global state, no cross-module leaks. | PASS |
| II. CLI Interface | Backend exposes HTTP under `/api/v1/users/me/avatar`. Reuses existing auth + RLS deps. CLI surface is the curl-friendly endpoint contract documented in `contracts/avatar-api.md`. | PASS |
| III. Test-First | Playwright E2E spec is written first (`tests/e2e/user-avatar.spec.ts`); backend tests in `backend/tests/test_avatar_upload.py` use a fake image fixture to drive the contract. | PASS |
| IV. Integration & Synchronization Testing | E2E covers happy path + 4 failure paths (wrong type, oversize, over-dim, network fail). Cross-tenant ownership test asserts user A cannot fetch user B's avatar. | PASS |
| V. Observability | `app.core.logging` produces structured logs with `request_id`, `user_id`, `avatar_id`, `event` for upload_start, upload_success, upload_reject, fetch, remove. No PII beyond user_id. | PASS |

No constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/013-user-avatar/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── avatar-api.md    # Phase 1 output
├── checklists/
│   └── requirements.md  # Quality checklist (16/16 passing)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/
│   │   └── users.py                       # add avatar sub-router mount
│   ├── modules/
│   │   ├── auth/models.py                 # add User.avatar_id FK
│   │   └── avatars/                       # NEW module
│   │       ├── __init__.py
│   │       ├── models.py                  # UserAvatar ORM
│   │       ├── schemas.py                 # Pydantic in/out
│   │       ├── service.py                 # validation, re-encode, storage
│   │       ├── router.py                  # upload/fetch/remove endpoints
│   │       └── tests/
│   │           ├── __init__.py
│   │           ├── conftest.py
│   │           └── test_avatar_upload.py
│   ├── core/
│   │   └── config.py                      # AVATAR_STORAGE_DIR + AVATAR_MAX_BYTES + AVATAR_MAX_DIMENSION
│   └── deps unchanged
├── migrations/versions/
│   └── 0008_user_avatar.py                # NEW: add user_avatars table + users.avatar_id FK
└── .data/avatars/                         # NEW runtime storage dir (.gitignore)

src/
├── api/
│   ├── account.ts                         # extend with avatar upload/fetch/remove
│   └── avatar.ts                          # NEW: dedicated avatar API helpers
├── components/
│   ├── settings/ProfileTab.tsx            # wire 更换头像 button
│   ├── layout/Topbar.tsx                  # pass avatar_url into Avatar
│   ├── ui/Avatar.tsx                      # unchanged (already supports src)
│   └── AbilityProfile/ShareDialog.tsx     # pass avatar_url into Avatar
├── hooks/
│   ├── queries/useCurrentUser.ts          # (no change, already returns user)
│   └── mutations/
│       └── useUploadAvatar.ts             # NEW: upload + remove mutations
├── pages/
│   ├── Profile.tsx                        # render avatar in profile header
│   ├── Settings.tsx                       # (no change; uses ProfileTab)
│   └── InterviewLive.tsx                  # render avatar in interview header
└── types/
    └── user.ts                            # extend User type with avatar_url

tests/e2e/
└── user-avatar.spec.ts                    # NEW: Playwright E2E
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |

## Re-evaluation after Phase 1 design

The design remains: a focused self-contained feature, no new global state, no new cross-module abstractions, all five Constitution principles still PASS. Pillow is an optional dependency installed only when available; the fallback path uses the same validation contract. No new conventions are introduced.

## Phase 0 Research

See [research.md](./research.md) for the full Phase 0 study. Key findings:

1. **Image validation strategy**: Pillow (PIL) `Image.open().verify()` for content sniff + `Image.open().load()` for header read; `img.size` for dimensions. Falls back to the standard library `imghdr` (deprecated in 3.13 but still works in 3.11) when Pillow is not installed.
2. **Upload transport**: `multipart/form-data` with a single `file` part; FastAPI `UploadFile.read()` to bytes; size enforced both at router level (Content-Length pre-check) and after read.
3. **Storage keying**: `{user_id}/{avatar_id}.{ext}` where `avatar_id` is a fresh UUIDv4 and `ext` is `.jpg` or `.png` based on the normalized content type.
4. **Atomic replacement**: write the new file to a temp path `{user_id}/{avatar_id}.{ext}.tmp`, fsync, then `os.replace()` to the final path; update the user row in the same transaction; a separate cleanup sweep deletes orphaned avatars older than 1 h.

## Phase 1 Design Artifacts

- [data-model.md](./data-model.md) — `UserAvatar` entity, `User.avatar_id` FK, validation rules
- [contracts/avatar-api.md](./contracts/avatar-api.md) — HTTP contract: POST upload, GET fetch, DELETE remove, plus error envelope
- [quickstart.md](./quickstart.md) — curl + Playwright commands to validate the slice end-to-end

## Agent Context

The active feature is recorded in `.specify/feature.json` and will be referenced by `CLAUDE.md` once this plan is checked in. No additional agent context update is required for this slice (no new cross-cutting abstraction).
