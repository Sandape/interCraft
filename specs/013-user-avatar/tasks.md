# Tasks: User Avatar Upload and Display

**Input**: Design documents from `/specs/013-user-avatar/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/avatar-api.md, quickstart.md

**Tests**: E2E tests are required by the feature scope and Constitution (Test-First principle, Principle III).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This is a web app. Paths follow the plan.md project structure:
- Backend: `backend/app/modules/avatars/`, `backend/migrations/versions/`
- Frontend: `src/api/`, `src/components/`, `src/hooks/`, `src/pages/`
- E2E: `tests/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and shared infrastructure for this slice.

- [X] T001 Verify backend Redis on `localhost:6379` and Postgres online (per CLAUDE.md local-env notes)
- [X] T002 [P] Create `backend/app/modules/avatars/` package skeleton with empty `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`, and `tests/__init__.py`
- [X] T003 [P] Add `AVATAR_STORAGE_DIR`, `AVATAR_MAX_BYTES`, `AVATAR_MAX_DIMENSION` settings in `backend/app/core/config.py` with defaults (`backend/.data/avatars`, `2_097_152`, `2048`)
- [X] T004 [P] Add `backend/.data/` to `.gitignore` (idempotent) and create the storage dir with `mkdir -p backend/.data/avatars`
- [X] T005 [P] Create `tests/e2e/_fixtures/sample-avatar.png` (256×256 solid color) for E2E and curl tests
- [X] T006 [P] Create `tests/e2e/_fixtures/avatar-too-large.png` (>2MB) and `avatar-too-wide.png` (>2048px) for negative-path tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database, ORM model, and shared API surface that all three user stories depend on. Tests are written first per Constitution Principle III.

- [X] T007 [P] Create alembic migration `backend/migrations/versions/0008_user_avatar.py`: add `user_avatars` table (id UUIDv7 PK, user_id UUID FK→users ON DELETE CASCADE, content_type, byte_size, width, height, storage_path UNIQUE, created_at) and `users.avatar_id` UUID FK→user_avatars.id ON DELETE SET NULL; down_revision = `0007_ability_profile`
- [X] T008 [P] Add `UserAvatar` ORM model in `backend/app/modules/avatars/models.py` mirroring the table, with `__tablename__ = "user_avatars"` and the relationships
- [X] T009 [P] Add `avatar_id` Mapped[UUID | None] FK to `User` in `backend/app/modules/auth/models.py` with `ondelete="SET NULL"`
- [X] T010 Add Pydantic response schema `AvatarOut` and the error union in `backend/app/modules/avatars/schemas.py`
- [X] T011 [P] Write `backend/app/modules/avatars/tests/test_avatar_upload.py` with 5 failing tests: happy-path upload, wrong MIME, oversize, over-dimension, cross-tenant fetch → 404 (test fixtures call `app.main:app` via httpx AsyncClient)
- [X] T012 [P] Write `tests/e2e/user-avatar.spec.ts` Playwright skeleton with 9 failing tests: upload, three reject paths, remove, topbar render, share dialog render, persist-across-reload, cross-user reject

**Checkpoint**: Schema and ORM are in place; tests describe the contract that all three stories must satisfy.

---

## Phase 3: User Story 1 - Upload a profile avatar (P1)

**Goal**: Signed-in user clicks 更换头像 in Settings → Profile, picks a JPG/PNG ≤ 2MB and ≤ 2048px, sees a preview, confirms, and the avatar replaces the initials placeholder.

**Independent Test**: `pytest backend/app/modules/avatars/tests/test_avatar_upload.py::test_upload_happy_path -q` + manual: open Settings → Profile, upload `tests/e2e/_fixtures/sample-avatar.png`, see avatar in form, see it in topbar.

### Implementation for User Story 1

- [X] T013 [US1] Implement `validate_image` in `backend/app/modules/avatars/service.py`: Pillow-based content sniff + dimension check (with `imghdr` fallback) raising typed errors `EmptyFileError`, `FileTooLargeError`, `UnsupportedFormatError`, `DimensionTooLargeError`
- [X] T014 [US1] Implement `save_avatar_bytes(db, user_id, content_type, raw_bytes)` in `backend/app/modules/avatars/service.py`: write to `{storage_dir}/{user_id}/{uuidv4}.{ext}.tmp` + `os.fsync` + `os.replace`; insert `user_avatars` row; update `users.avatar_id`; commit; on failure, remove temp file and re-raise as `StorageWriteError`
- [X] T015 [US1] Implement `_cleanup_tmp_files(user_id)` helper in `backend/app/modules/avatars/service.py`: removes `*.tmp` files older than 1 h under `{storage_dir}/{user_id}/`
- [X] T016 [US1] Implement `POST /api/v1/users/me/avatar` in `backend/app/modules/avatars/router.py`: `Depends(get_current_user)`, `UploadFile` param `file`, pre-check `Content-Length` against `AVATAR_MAX_BYTES`, call `validate_image` + `save_avatar_bytes`, return `AvatarOut`, with the project-standard error envelope on failures
- [X] T017 [US1] Mount `avatars_router` in `backend/app/api/v1/__init__.py` under prefix `/users/me` with tag `avatars`
- [X] T018 [P] [US1] Add `src/api/avatar.ts`: `uploadAvatar(file: File): Promise<AvatarOut>` and types `AvatarOut` mirroring backend schema
- [X] T019 [P] [US1] Add `useUploadAvatar` mutation hook in `src/hooks/mutations/useUploadAvatar.ts`: react-query `useMutation` calling `uploadAvatar`, exposing `{ mutateAsync, isPending, error }`
- [X] T020 [US1] Wire the 更换头像 button in `src/components/settings/ProfileTab.tsx`: hidden `<input type="file" accept="image/png,image/jpeg" data-testid="avatar-file-input">`, click triggers picker, on change create object URL for preview, render preview in the existing `Avatar` slot, add inline error state with `data-testid="avatar-error"`, show 确认上传 button (`data-testid="avatar-confirm"`) and 移除头像 button (`data-testid="avatar-remove"`) when preview or current avatar exists
- [X] T021 [US1] Extend `User` type in `src/api/types.ts` with `avatar_url: string | null`; verify `useCurrentUser` returns it (no fetch change needed if backend `GET /api/v1/users/me` already includes the field)

**Checkpoint**: User Story 1 is independently demoable.

---

## Phase 4: User Story 2 - Remove the current avatar (P2)

**Goal**: With an avatar set, a 移除头像 control is visible; clicking it reverts the avatar slot to the initials placeholder and the change persists.

**Independent Test**: `pytest backend/app/modules/avatars/tests/test_avatar_upload.py::test_remove_avatar -q` + manual: with avatar set, click 移除头像, see initials, reload, see initials.

### Implementation for User Story 2

- [X] T022 [US2] Add `remove_user_avatar(db, user_id)` in `backend/app/modules/avatars/service.py`: set `users.avatar_id = None` and commit; idempotent (no-op if already None); do NOT delete the underlying file (left for cleanup sweep)
- [X] T023 [US2] Add `DELETE /api/v1/users/me/avatar` in `backend/app/modules/avatars/router.py`: `Depends(get_current_user)`, returns `{"status": "removed", "message": "已移除头像"}`, 404 if user has no avatar
- [X] T024 [P] [US2] Add `removeAvatar(): Promise<{status: string}>` to `src/api/avatar.ts`
- [X] T025 [P] [US2] Add `useRemoveAvatar` mutation hook in `src/hooks/mutations/useUploadAvatar.ts` (same file as upload) that calls `removeAvatar` and invalidates the `currentUser` query
- [X] T026 [US2] Wire 移除头像 button in `src/components/settings/ProfileTab.tsx`: only visible when `user?.avatar_url` is non-null, calls `useRemoveAvatar`, shows pending + error states inline, on success the existing `useCurrentUser` refetch flips `avatar_url` to null and the slot reverts to initials

**Checkpoint**: User Story 2 is independently demoable.

---

## Phase 5: User Story 3 - Avatar appears in the authenticated shell (P1)

**Goal**: Uploaded avatar shows in Topbar, Profile page, Ability Profile ShareDialog, and InterviewLive; persists across reload.

**Independent Test**: `npx playwright test tests/e2e/user-avatar.spec.ts --grep "renders in the topbar|share dialog|persists"` + manual: upload, navigate across pages, see image everywhere.

### Implementation for User Story 3

- [X] T027 [P] [US3] Pass `user?.avatar_url` to `Avatar` in `src/components/layout/Topbar.tsx` (the avatar menu trigger); if `user?.avatar_url` exists, the existing `Avatar` component renders `<img src=...>` automatically
- [X] T028 [P] [US3] Pass `user?.avatar_url` to `Avatar` in `src/pages/Profile.tsx` (any header avatar slot; if none exists, add one at the page top with `data-testid="profile-page-avatar"`)
- [X] T029 [P] [US3] Pass `user?.avatar_url` to `Avatar` in `src/components/AbilityProfile/ShareDialog.tsx` (next to the user name in the share preview)
- [X] T030 [P] [US3] Pass `user?.avatar_url` to `Avatar` in `src/pages/InterviewLive.tsx` (any existing avatar slot in the live page header; if none, the existing initials display is sufficient — confirm and skip)
- [X] T031 [US3] Fill the topbar/share-dialog/persist-across-reload E2E tests in `tests/e2e/user-avatar.spec.ts` to pass: assert `<img src="/api/v1/users/me/avatar/...">` is in the topbar, in the share dialog, and still present after a full page reload

**Checkpoint**: User Story 3 is independently demoable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, observability, and E2E polish.

- [X] T032 [P] Add structured logging calls (`log.info("avatar.upload.start", user_id, content_type, byte_size)` and friends) in `backend/app/modules/avatars/service.py` and `router.py` using `app.core.logging.get_logger`
- [X] T033 [P] Fill the 4 reject-path tests in `backend/app/modules/avatars/tests/test_avatar_upload.py` to pass: wrong MIME → 415, oversize → 413, over-dimension → 422, cross-tenant fetch → 404
- [X] T034 Fill the cross-user reject test in `tests/e2e/user-avatar.spec.ts` to pass: user B navigates to a URL with user A's avatar id, sees 404/not-rendered
- [X] T035 Run `npm run typecheck` and `npx vitest run`
- [X] T036 Run `pytest backend/app/modules/avatars/tests/ -q`
- [X] T037 Run `npx playwright test tests/e2e/user-avatar.spec.ts --workers=1`
- [X] T038 Capture screenshots in the Playwright spec for the 6 visual states under `test-results/user-avatar/` (initial, preview, uploaded, topbar, share-dialog, removed) and use model image recognition (or 识图 MCP) to confirm visual state for each
- [X] T039 Mark all tasks `[X]` in `specs/013-user-avatar/tasks.md` and commit with the implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T002–T006 are parallelizable.
- **Foundational (Phase 2)**: Depends on Setup. T007/T008/T009 are parallelizable; T010 depends on T007–T009; T011/T012 are parallelizable and depend on T007–T010.
- **User Story 1 (Phase 3)**: Depends on Phase 2. T013 must precede T014; T014 precedes T016; T018/T019 depend on T016; T020 depends on T019; T021 is parallelizable with T020.
- **User Story 2 (Phase 4)**: Depends on Phase 2 + US1's `useUploadAvatar` (for the inline error pattern reuse). T022 precedes T023; T024/T025 depend on T022; T026 depends on T025.
- **User Story 3 (Phase 5)**: Depends on Phase 2 only (uses `user?.avatar_url` flowing from T021). T027–T030 are fully parallel.
- **Polish (Phase 6)**: Depends on all three stories.

### User Story Completion Order

```
US1 (P1) ─► US2 (P2) ─► US3 (P1)
```

US3 can technically start as soon as T021 lands (avatar_url on the User type), but it is sequenced after US1 to keep the diff per phase reviewable.

### Parallel Opportunities

- T002 / T003 / T004 / T005 / T006 (Setup) — all touch different files.
- T007 / T008 / T009 (Foundational) — migration, ORM, user model in different files.
- T011 / T012 (Foundational tests) — backend test file and frontend E2E file.
- T018 / T019 (US1 frontend) — `avatar.ts` and `useUploadAvatar.ts` in different files.
- T024 / T025 (US2 frontend) — same as above.
- T027 / T028 / T029 / T030 (US3 frontend) — four different files, fully independent.
- T032 / T033 (Polish) — backend logging and tests in different files.

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 + Phase 2 (Setup + Foundational).
2. Complete Phase 3 (US1) end-to-end: backend upload, frontend picker+preview+confirm.
3. Validate US1 with the `test_upload_happy_path` pytest and a manual click-through.
4. Demo: Settings → Profile → upload → avatar appears.

### Incremental Delivery

1. Add Phase 4 (US2 remove) — small delta, finishes the "upload-only flows trap users" concern.
2. Add Phase 5 (US3 shell-wide render) — feeds the uploaded avatar into the rest of the app; the visual payoff is largest here.
3. Phase 6 closes the loop with typecheck, full E2E, and visual confirmation.

### Test Discipline

- Every test in T011 and T012 is written before its corresponding implementation task lands.
- The 9 Playwright tests in T012 cover the entire spec (upload, 3 reject paths, remove, topbar, share, persist, cross-tenant) — no spec scenario is left untested.
- Visual confirmation (T038) uses model image recognition (or 识图 MCP) — never a manual eyeball check.
