# Quickstart: User Avatar Upload and Display

**Date**: 2026-06-16 | **Feature**: 013-user-avatar | **Spec**: [spec.md](./spec.md)

## Prerequisites

- Backend: Redis on `localhost:6379`, Postgres online (per `CLAUDE.md` local-env notes)
- Backend deps installed: `uv sync --extra dev` (or the project's equivalent)
- Frontend deps installed: `npm install`
- Pillow is **optional**; if installed, it is used for re-encode and dimension check. To install it explicitly: `uv pip install Pillow`.

## One-time setup

```bash
# Apply the new migration
cd backend
alembic upgrade head
# Confirms: 0008_user_avatar applied (new table user_avatars, new column users.avatar_id)

# Create the storage directory
mkdir -p .data/avatars
# .data/ is already in .gitignore

# Start the backend
uv run uvicorn app.main:app --reload --port 8000

# In another terminal, start the frontend
cd ..
npm run dev
```

## Backend validation via curl

Use a tiny JPG/PNG fixture. The repo's `tests/e2e/fixtures/` directory contains `sample-avatar.png`; for a manual test you can also use any local image ≤ 2 MB and ≤ 2048 px.

```bash
# 1. Log in and capture the access token
ACCESS=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"password"}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2. Upload the avatar
curl -i -X POST http://localhost:8000/api/v1/users/me/avatar \
  -H "Authorization: Bearer $ACCESS" \
  -F "file=@./sample-avatar.png;type=image/png"
# Expect: 200 OK with {"avatar_id": "...", "url": "/api/v1/users/me/avatar/..."}

# 3. Confirm the URL resolves
URL=$(curl -s -H "Authorization: Bearer $ACCESS" \
  http://localhost:8000/api/v1/users/me \
  | python -c 'import sys,json;print(json.load(sys.stdin)["avatar_url"])')

curl -i -H "Authorization: Bearer $ACCESS" "http://localhost:8000$URL"
# Expect: 200 OK with Content-Type: image/png and the avatar bytes

# 4. Reject an unsupported file
echo "not an image" > /tmp/bad.txt
curl -i -X POST http://localhost:8000/api/v1/users/me/avatar \
  -H "Authorization: Bearer $ACCESS" \
  -F "file=@/tmp/bad.txt;type=text/plain"
# Expect: 415 Unsupported Media Type

# 5. Remove the avatar
curl -i -X DELETE -H "Authorization: Bearer $ACCESS" \
  http://localhost:8000/api/v1/users/me/avatar
# Expect: 200 OK with {"status": "removed"}
```

## Cross-tenant ownership check

```bash
# Log in as Bob, then try to fetch Alice's avatar by ID
BOB_ACCESS=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","password":"password"}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

ALICE_AVATAR_ID=$(curl -s -H "Authorization: Bearer $ACCESS" \
  http://localhost:8000/api/v1/users/me \
  | python -c 'import sys,json;print(json.load(sys.stdin)["avatar_url"]).rsplit("/",1)[-1]')

curl -i -H "Authorization: Bearer $BOB_ACCESS" \
  "http://localhost:8000/api/v1/users/me/avatar/$ALICE_AVATAR_ID"
# Expect: 404 Not Found
```

## Frontend unit / E2E validation

```bash
# Frontend typecheck and tests
npm run typecheck
npx vitest run src/hooks/mutations/useUploadAvatar.test.ts

# Full-stack Playwright E2E
npx playwright test tests/e2e/user-avatar.spec.ts --workers=1
```

The Playwright spec covers:

| Test | Scenario | Expected |
|---|---|---|
| `uploads a valid PNG avatar` | US1 happy path | Preview, upload, avatar image in topbar |
| `rejects an unsupported file type` | US1 edge case | Inline error, no preview, prior avatar preserved |
| `rejects an oversized file (>2MB)` | US1 edge case | Inline error, no preview |
| `rejects an oversized dimension (>2048px)` | US1 edge case | Inline error, no preview |
| `removes the current avatar` | US2 happy path | Avatar slot reverts to initials |
| `avatar renders in the topbar after upload` | US3 happy path | `<img src="/api/v1/users/me/avatar/...">` in Topbar |
| `avatar renders in the share dialog` | US3 happy path | Share dialog shows the uploaded image |
| `avatar persists across a full page reload` | US3 happy path | After reload, image still shown |
| `cross-user fetch is rejected` | FR-006 security | User B fetches user A's avatar → 404 |

## Visual confirmation

Visual verification is done by capturing screenshots and asking the model to describe them (or by 识图 MCP). The Playwright spec saves screenshots to `test-results/user-avatar/` for the key states:

- `01-initial.png` — Settings → Profile before upload
- `02-preview.png` — after selecting a file but before confirming
- `03-uploaded.png` — after confirm, avatar image visible
- `04-topbar.png` — topbar shows the uploaded image
- `05-share-dialog.png` — Ability Profile share dialog with avatar
- `06-removed.png` — after remove, initials placeholder

## Rollback

```bash
# Downgrade the migration
cd backend
alembic downgrade -1
# Removes the user_avatars table and users.avatar_id column
```

The frontend changes are guarded by `user?.avatar_url`; if the API returns `null`, the initials placeholder renders. No frontend rollback is required.
