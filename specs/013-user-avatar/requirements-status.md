# 013 Requirement Status

Status reconciled against code on 2026-06-22. All 3 user stories and 13
FR are implemented; E2E covers upload + render.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | Upload a profile avatar | done | `backend/app/modules/avatars/router.py` `POST /users/me/avatar`; `src/components/settings/ProfileTab.tsx` file picker + preview; `tests/e2e/user-avatar.spec.ts` | — |
| US2 | Remove the current avatar | done | `backend/app/modules/avatars/router.py` `DELETE /users/me/avatar`; `service.py:238-247` `remove_user_avatar` | — |
| US3 | Avatar appears in the authenticated shell | done | `User.avatar_id` FK + Avatar component renders across Topbar / Profile / ShareDialog / InterviewLive | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | avatar upload control in Settings → Profile, image-only file picker | done | `src/components/settings/ProfileTab.tsx` file input `accept="image/*"` | — |
| FR-002 | validate MIME (jpeg/png) + content sniff + 2MB cap + 2048px cap | done | `backend/app/modules/avatars/service.py:5-6,28` Pillow + imghdr fallback | — |
| FR-003 | preview before confirm | done | `src/components/settings/ProfileTab.tsx:158` `previewUrl` state | — |
| FR-004 | persist + reflect across authenticated shell | done | `User.avatar_id` FK + Avatar component used in Topbar/Profile/ShareDialog/InterviewLive | — |
| FR-005 | remove-avatar affordance + revert to initials | done | `backend/app/modules/avatars/service.py:238` `remove_user_avatar` sets `avatar_id=NULL` | — |
| FR-006 | owner-only avatar URLs (not enumerable) | done | `backend/app/modules/avatars/router.py` `GET /users/me/avatar/{avatar_id}` auth + ownership check | — |
| FR-007 | sanitize + re-encode (strip EXIF + embedded scripts) via Pillow | done | `backend/app/modules/avatars/service.py:5-6,28` Pillow re-encode path | — |
| FR-008 | reject SVG/GIF/HEIC/BMP/TIFF/WebP with inline error | done | `backend/app/modules/avatars/service.py` content sniff rejects non-JPG/PNG | — |
| FR-009 | stable test selectors | done | `data-testid` attributes throughout ProfileTab + Avatar | — |
| FR-010 | initials placeholder consistent when no avatar | done | Avatar component initials fallback with color pair logic | — |
| FR-011 | inline error messages, no `alert()`/`confirm()` | done | `src/components/settings/ProfileTab.tsx:38` `avatarError` state | — |
| FR-012 | atomic avatar reference update; last-write-wins; no partial upload served | done | `backend/app/modules/avatars/service.py` transactional update of `users.avatar_id` | — |
| FR-013 | Chinese copy ("确认上传" / "移除头像") | done | `src/components/settings/ProfileTab.tsx` zh-CN button labels | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | upload from Settings → Profile in < 30s | done | `tests/e2e/user-avatar.spec.ts` | — |
| SC-002 | avatar renders in topbar/Profile/share/interview on next render | done | `tests/e2e/user-avatar.spec.ts` | — |
| SC-003 | avatar persists across full reload, owner-only | done | `backend/app/modules/avatars/router.py` owner check; `tests/e2e/user-avatar.spec.ts` | — |
| SC-004 | unsupported/oversized/failed each produce inline error within 1s, no alert/confirm | done | `src/components/settings/ProfileTab.tsx:38` `avatarError`; `tests/e2e/user-avatar.spec.ts` | — |

## Status Roll-up

- Total: 3 US + 13 FR + 4 SC = 20 rows.
- `done`: 20 rows.
