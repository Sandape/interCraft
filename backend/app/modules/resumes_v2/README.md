# M032 — Resume Renderer v2

> Authored in T179 (Polish phase). Replaces the Wave 1 stub.
>
> Source of truth: `specs/032-resume-renderer-v2/{spec.md, plan.md, tasks.md}`.

## Purpose

Replace the v1 block + Markdown resume model with a JSON-Schema data model
mirrored from [reactive-resume v5](https://github.com/AmruthPillai/Reactive-Resume),
plus a 10-template three-column editor with auto-save, sharing, public
viewing, AI analysis, and PDF export.

Key capabilities:

- **CRUD** with optimistic concurrency (`If-Match` header → `409 VERSION_CONFLICT`).
- **10 HTML/CSS templates** (`onyx/azurill/kakuna/chikorita/ditgar/bronzor/pikachu/lapras/scizor/rhyhorn`).
- **Lock** toggle (`PUT /lock`) — independent of `version`.
- **Duplicate** (`POST /duplicate`) — deep-copies `data`, resets public/lock/password.
- **Sharing** (`PUT /sharing`) — public toggle + bcrypt-hashed password (cost 12).
- **Public view** (`GET /public/{u}/{s}`) — no-auth read; cookies for password.
- **Statistics** (`GET /statistics`) — view + download counters.
- **AI Analysis** (`POST /analyze`) — DeepSeek V4 Pro, 3-attempt retry, no cache.
- **SSE** (`GET /events`) — `resume_update_v2` + `resume_v2_public` pg_notify channels.
- **PDF render** (`POST /export/render`) — via shared `/api/v1/export/render` gateway.

## Public API (16 endpoints under `/api/v1/v2`)

| # | Method | Path | Status | Implemented in |
|---|---|---|---|---|
| 1 | GET    | `/resumes`                                  | ✅ | US1 T022 |
| 2 | POST   | `/resumes`                                  | ✅ | US1 T022 |
| 3 | GET    | `/resumes/{id}`                             | ✅ | US1 T022 |
| 4 | PUT    | `/resumes/{id}`                             | ✅ | US1 T022 + T023 |
| 5 | DELETE | `/resumes/{id}`                             | ✅ | US1 T022 |
| 6 | POST   | `/resumes/{id}/duplicate`                   | ✅ | US16 T158 |
| 7 | PUT    | `/resumes/{id}/lock`                        | ✅ | US1 T022 |
| 8 | PUT    | `/resumes/{id}/sharing`                     | ✅ | US11 T141 |
| 9 | GET    | `/resumes/{id}/statistics`                  | ✅ | US11 T145 |
| 10| POST   | `/resumes/{id}/analyze`                     | ✅ | US14 T152 |
| 11| GET    | `/resumes/{id}/analysis`                    | ✅ | US14 T153 |
| 12| GET    | `/public/{username}/{slug}`                 | ✅ | US11 T142 |
| 13| POST   | `/public/{username}/{slug}/verify-password` | ✅ | US11 T143 |
| 14| GET    | `/public/{username}/{slug}/pdf`             | ✅ | US11 T144 |
| 15| GET    | `/resumes/events` (SSE)                     | ⚠ stub | US12 T116 |
| 16| POST   | `/export/render`                            | ⚠ stub | US10 T106 |

### Error envelope

All 4xx responses use the *flat* shape:
```json
{"error": "VERSION_CONFLICT", "message": "..."}
```

Codes: `MISSING_IF_MATCH`, `INVALID_IF_MATCH`, `LEGACY_FORMAT`, `VERSION_CONFLICT`,
`RESUME_LOCKED`, `NOT_FOUND`, `NOT_OWNER`, `INVALID_SLUG`, `SLUG_TAKEN`,
`INVALID_PASSWORD`, `INVALID_SHARING`, `UNAUTHENTICATED`, `PASSWORD_REQUIRED`,
`PASSWORD_INVALID`, `ANALYZE_STORE_FAILED`.

### Optimistic concurrency (US1)

```http
PUT /api/v1/v2/resumes/{id}
If-Match: 3
Content-Type: application/json
```
On conflict, server returns `409 VERSION_CONFLICT` with `latest_version` and `latest_data`.

## CLI commands

```bash
# Seed a sample Pikachu resume for a user
python -m app.cli resumes-v2 seed-test-data --user alice@example.com --slug pikachu-sample

# Show a v2 resume as JSON
python -m app.cli resumes-v2 show <resume-uuid> --json

# Duplicate a v2 resume
python -m app.cli resumes-v2 duplicate <resume-uuid> --user alice@example.com

# Print the data-schema markdown
python -m app.cli resumes-v2 dump-schema
```

All commands support `--json` for machine-readable output.

## Config vars

| Variable | Purpose | Default |
|---|---|---|
| `DEEPSEEK_API_KEY` | Enables AI analysis (US14). When unset, `/analyze` returns `failed`. | (required) |
| `RESUME_V2_SSE_MAX_CONN` | Max concurrent SSE connections per user (US12). | `10` |
| `RESUME_V2_PDF_TIMEOUT_S` | PDF render timeout (seconds). | `60` |
| `RESUME_V2_PASSWORD_MIN_LEN` | Min password length. | `6` |
| `RESUME_V2_PASSWORD_MAX_LEN` | Max password length. | `64` |
| `BCRYPT_ROUNDS` | Bcrypt cost for password hashing. | `12` |

## Example curl

### Create a v2 resume

```bash
curl -X POST http://localhost:8000/api/v1/v2/resumes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Resume",
    "slug": "my-resume",
    "template": "pikachu",
    "from_sample": true
  }'
# → 201 {"resume": {"id": "...", "version": 0, ...}}
```

### Update with optimistic concurrency

```bash
curl -X PUT http://localhost:8000/api/v1/v2/resumes/$RESUME_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "If-Match: 0" \
  -H "Content-Type: application/json" \
  -d '{"name": "Renamed Resume"}'
# → 200 {"id": "...", "version": 1, ...}
```

### Make public + set password

```bash
curl -X PUT http://localhost:8000/api/v1/v2/resumes/$RESUME_ID/sharing \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_public": true, "password": "secret-123"}'
# → 200 {"is_public": true, "password_set": true, "public_url": "/r/alice/my-resume"}
```

### View public resume (no auth)

```bash
curl http://localhost:8000/api/v1/v2/public/alice/my-resume
# → 200 {"id": "...", "data": {...}, ...}
# or 401 PASSWORD_REQUIRED if password-protected
```

### Trigger AI analysis

```bash
curl -X POST http://localhost:8000/api/v1/v2/resumes/$RESUME_ID/analyze \
  -H "Authorization: Bearer $TOKEN"
# → 200 {"status": "success", "analysis": {"overallScore": 82, ...}, ...}
```

## Example CLI invocation

```bash
# Provision a test user with sample data
cd backend
uv run python -m app.cli resumes-v2 seed-test-data \
  --user alice@example.com \
  --slug pikachu-sample \
  --name "Pikachu Sample"

# Dump the resume JSON
uv run python -m app.cli resumes-v2 show <resume-uuid> --json
```

## Structured logging keys

Backend handlers emit these structlog events (T177):
- `resume_v2.create` — POST success
- `resume_v2.update.conflict` — PUT 409
- `resume_v2.duplicate` — POST /duplicate success
- `resume_v2.analyze.retry` — AI retry attempt (1-3)
- `resume_v2.sse.subscribe` — SSE connect
- `resume_v2.export.render` — PDF render

Common fields: `request_id`, `user_id`, `resume_id`, `version`, `template`.

## OpenTelemetry spans (T178)

- `v2.resume.update` — PUT
- `v2.resume.analyze` — POST /analyze (with `llm.retry_count`)
- `v2.resume.sse.subscribe` — SSE connect
- `v2.resume.export.render` — PDF render

Skipped silently if OTel not configured (FR-017 fail-open).

## Architecture notes

- **DB**: 3 tables (`resumes_v2`, `resume_statistics_v2`, `resume_analysis_v2`),
  RLS-enforced per `user_id`. Migration: `backend/alembic/versions/0022_032_resumes_v2.py`.
- **Public cookies**: `v2_public_pw_<12hex>` — keyed off `sha256(password_hash)[:12]`.
  HttpOnly, SameSite=Lax, Max-Age=600s.
- **pg_notify channels**: `resume_update_v2` (data changes), `resume_v2_public`
  (sharing changes). The SSE handler (T116) fans them out to connected clients.
- **AI retry**: 3 attempts (1s/2s/4s exponential backoff). No in-memory cache
  (FR-091a) — every call hits DeepSeek fresh.

## See also

- Spec: `specs/032-resume-renderer-v2/spec.md`
- Plan: `specs/032-resume-renderer-v2/plan.md`
- Tasks: `specs/032-resume-renderer-v2/tasks.md`
- Contracts: `specs/032-resume-renderer-v2/contracts/`
- Frontend: `src/modules/resume/v2/`
- E2E: `tests/e2e/032-resume-renderer-v2/`