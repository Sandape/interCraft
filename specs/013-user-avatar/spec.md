# Feature Specification: User Avatar Upload and Display

**Feature Branch**: `013-user-avatar`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Add avatar upload capability so the dead 更换头像 button in Settings → Profile actually works. The button at src/components/settings/ProfileTab.tsx:43-45 has no onClick handler. Backend User model has no avatar_url field. Need an avatar upload endpoint, file storage, avatar_url field on User model with migration, frontend file picker with preview, and render the uploaded avatar everywhere the Avatar component is used (Topbar, Profile, ShareDialog, InterviewLive)."

## Clarifications

### Session 2026-06-16

- Q: Storage strategy for uploaded avatars? → A: Local file system under `backend/.data/avatars/{user_id}/{avatar_id}.{ext}` (UUID-based, owner-only, no S3 dependency).
- Q: Avatar fetch URL strategy? → A: UUID-based path served through authenticated `GET /api/v1/users/me/avatar/{id}`; auth middleware enforces owner-only access (guessed URLs from other users return 403/404).
- Q: Image re-encoding approach? → A: Pillow re-encodes to normalized JPG/PNG, strips EXIF metadata, and validates max 2048px on any side. If Pillow is unavailable at runtime, fall back to content sniff + size check only.
- Q: Concurrent upload behavior? → A: Last-write-wins with an atomic user-row update; the new file reference replaces the old one, and a stale partial upload can never be served.
- Q: UI button copy? → A: Chinese copy: "确认上传" for confirm, "移除头像" for remove, to match the rest of the authenticated shell.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a profile avatar (Priority: P1)

A signed-in user opens Settings → Profile and changes their profile picture. They click the existing "更换头像" (Change Avatar) button, pick an image file from their device, see a preview, confirm the upload, and the new avatar appears in the form immediately.

**Why this priority**: This is the primary purpose of the feature. A dead button that does nothing creates a misleading UI and erodes user trust in the entire Settings page.

**Independent Test**: Open Settings → Profile, click the avatar change control, select a valid JPG/PNG up to 2MB, confirm, and verify the avatar image replaces the initials placeholder in the form.

**Acceptance Scenarios**:

1. **Given** a user is on Settings → Profile with no avatar, **When** they click the change-avatar control, **Then** a native file picker opens accepting only image files.
2. **Given** a file picker is open, **When** the user selects a valid image (JPG/PNG, ≤ 2MB), **Then** a preview of the chosen image appears in the avatar slot before they confirm.
3. **Given** a preview is shown, **When** the user confirms the upload, **Then** the new avatar is saved to the account and the initials placeholder is replaced.
4. **Given** a user selects an unsupported file (e.g., PDF, TXT, 5MB image), **When** the file picker closes, **Then** an inline error explains the limit and no preview is shown.

---

### User Story 2 - Remove the current avatar (Priority: P2)

A signed-in user wants to revert to the default initials-only avatar. They open Settings → Profile, see a "remove avatar" affordance next to the preview, click it, and the avatar returns to the initial-based placeholder.

**Why this priority**: Upload-only flows trap users with an unwanted image and create support noise. A remove path is required to make the feature whole.

**Independent Test**: With an avatar already set, open Settings → Profile, click the remove-avatar control, verify the avatar slot reverts to initials and the change persists after reload.

**Acceptance Scenarios**:

1. **Given** a user has an avatar set, **When** they view Settings → Profile, **Then** a remove-avatar control is visible.
2. **Given** a remove-avatar control is visible, **When** the user clicks it, **Then** the avatar slot reverts to the initials placeholder and the change is saved.

---

### User Story 3 - Avatar appears in the authenticated shell (Priority: P1)

A signed-in user sees their uploaded avatar in the topbar avatar menu trigger, on the Profile page, in the Ability Profile share dialog, and inside the live interview room. After a refresh, the avatar persists.

**Why this priority**: An uploaded avatar that only shows in the Settings page has little value. The user expects the avatar to follow them across the app.

**Independent Test**: Upload an avatar in Settings, navigate to Dashboard, Profile, Ability Profile, and start a mock interview. Verify the avatar image is rendered (not initials) in the topbar, profile header, share dialog, and any avatar slot in the interview live page.

**Acceptance Scenarios**:

1. **Given** a user has uploaded an avatar, **When** they view the topbar avatar trigger on any authenticated page, **Then** the uploaded image is shown.
2. **Given** a user has uploaded an avatar, **When** they reload the page, **Then** the avatar image is still shown.
3. **Given** a user has uploaded an avatar, **When** they open the Ability Profile share dialog, **Then** the avatar image is shown next to the user name in the share preview.
4. **Given** a user has no avatar, **When** they view the topbar or profile, **Then** the initial-based placeholder continues to render with the same color pair.

### Edge Cases

- A user uploads an SVG, GIF, or HEIC file: the system MUST reject it with an inline error.
- A user uploads a non-image (e.g., PDF renamed to .jpg): MIME sniffing rejects it with an inline error.
- The image is too large (> 2MB) or has extreme dimensions (> 2048px on any side): the system rejects it with a clear inline error.
- The upload network request fails (e.g., 5xx, timeout): the user sees an inline error and the previous avatar is preserved.
- The user picks a file and then picks a different one before confirming: only the latest selection is previewed.
- The user reloads Settings → Profile mid-upload: the upload must either complete or fail cleanly without leaving the avatar in a partial/broken state.
- A user with an avatar changes their display name: the avatar continues to render correctly.
- An avatar uploaded by user A must NEVER be retrievable via a guessed URL by user B.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add an avatar upload control to Settings → Profile that opens a file picker accepting image files only.
- **FR-002**: System MUST validate the chosen file by MIME type (image/jpeg, image/png) AND by content sniffing, AND enforce a 2MB size cap and 2048px max-dimension cap.
- **FR-003**: System MUST show a preview of the chosen image in the avatar slot before the user confirms the upload.
- **FR-004**: System MUST persist the uploaded avatar against the user account and reflect it across the authenticated shell (topbar, Profile, Ability Profile share, interview live).
- **FR-005**: System MUST provide a remove-avatar affordance when an avatar is set, and reverting to initials MUST also persist.
- **FR-006**: System MUST serve avatar images via authenticated, owner-only URLs that are not enumerable (i.e., guessing another user's URL returns 403/404). Specifically, the fetch route is `GET /api/v1/users/me/avatar/{avatar_id}` and the auth middleware rejects requests where the requesting user is not the owner.
- **FR-007**: System MUST sanitize and re-encode uploaded images to strip EXIF metadata and any embedded scripts before storage, using Pillow when available with a content-sniff-only fallback.
- **FR-008**: System MUST reject SVG, GIF, HEIC, BMP, TIFF, WebP and any non-JPG/PNG file with a clear inline error.
- **FR-009**: All new interactive controls MUST expose stable test selectors for automated verification.
- **FR-010**: System MUST render the initials placeholder consistently when no avatar is set, with the same color pair logic as today.
- **FR-011**: System MUST display inline error messages for unsupported files, oversized files, and upload failures without using `alert()` or `confirm()`.
- **FR-012**: System MUST atomically update the user record's avatar reference on upload; concurrent uploads are resolved as last-write-wins, and a partial upload can never become a served avatar.
- **FR-013**: System MUST use Chinese copy for the confirm and remove actions ("确认上传" and "移除头像") to match the rest of the authenticated shell.

### Key Entities *(include if feature involves data)*

- **User Avatar**: A user-owned image that overrides the initials placeholder. Key attributes: owner user_id, image bytes (with MIME and size), upload timestamp, storage path.
- **Avatar Storage Object**: A binary blob stored on the server with a non-guessable identifier. Key attributes: id, content_type, byte size, owner user_id, created_at.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of authenticated users can complete an avatar upload from Settings → Profile in under 30 seconds, including picking a local file.
- **SC-002**: After upload, the avatar image renders in the topbar, Profile page, Ability Profile share dialog, and any in-app avatar slot on the very next page render (no manual refresh required for in-session navigation).
- **SC-003**: After a full browser reload, the avatar continues to render for the owning user and only the owning user.
- **SC-004**: Unsupported file types, oversized files, oversized dimensions, and failed uploads each produce a clear inline error message within 1 second of the user action, with no `alert()` or `confirm()` dialogs.
- **SC-005**: 100% of rejected files (wrong type / too large / over-dimension) leave the previous avatar state intact (no partial save).
- **SC-006**: A user can remove their avatar and return to the initials placeholder in a single click, and the change persists across reloads.

## Assumptions

- The existing user record already has a unique `id` (UUIDv7) usable as the avatar storage key prefix.
- Storage location is local file system at `backend/.data/avatars/{user_id}/{avatar_id}.{ext}`. Cloud object storage (S3/MinIO) can replace it later behind the same API.
- The fetch route is `GET /api/v1/users/me/avatar/{avatar_id}`. The auth middleware (`get_current_user`) is reused for upload, fetch, and remove; no new permission system is needed for this scope.
- Image re-encoding uses the Python Pillow library when installed; if Pillow is unavailable, validation falls back to MIME sniff + size cap only, and the original bytes are stored as-is.
- The existing Avatar React component (`src/components/ui/Avatar.tsx`) already supports an `src` prop, so we only need to feed it a URL.
- We will not introduce avatar cropping or rotation in this slice; users pick a file and confirm.
- The "share preview" mentioned in US3 is the ShareDialog on the Ability Profile page; no other share surfaces are in scope.
- File size limit 2MB matches the existing UI hint on the dead button; this is the user-facing contract we preserve.
- Concurrent uploads from the same user are resolved as last-write-wins; the new file reference replaces the old one atomically on the user row.
