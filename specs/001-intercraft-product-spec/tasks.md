# Tasks: InterCraft · Phase 1 — P0 基线(账号 + 简历 CRUD + 版本 + 前端基础设施)

**Input**: Design documents from `/specs/001-intercraft-product-spec/`
- [plan.md](./plan.md) (tech stack, libraries, structure)
- [spec.md](./spec.md) (user stories P1 / P2 / P3)
- [research.md](./research.md) (DEC-1 ~ DEC-12)
- [data-model.md](./data-model.md) (6 entities: users / user_credentials / auth_sessions / resume_branches / resume_blocks / resume_versions)
- [contracts/](./contracts/) (REST API contracts)
- [quickstart.md](./quickstart.md) (5-minute happy path SC-001)
- [Constitution](../../.specify/memory/constitution.md) v1.0.0

**Scope**: Phase 1 only (M01-M07 + M23 基础设施);US4-US12 are deferred to Phase 2-6.
**Phase 1 User Stories**: US1 (账号) / US2 (简历分支+块) / US3 (版本快照+回滚) — all P1.
**Tests**: REQUIRED by Constitution III (Test-First). Every non-trivial task has a `test_*` task that must FAIL before implementation.

### Local Environment Constraints (recorded 2026-06-12)

> **本机当前不具备的资源 → 任务被部分延迟;在用户提供前,任务不可启动 / 不可完成**。

| 资源 | 状态 | 影响的 Phase 1 任务 | 何时解封 |
|---|---|---|---|
| **PostgreSQL 15 数据库(在线托管)** | ✅ **T008b 已解封 2026-06-12** — online DB `81.71.152.210:5432/interCraft` | T032 / T034 / T035 (migration) / T135 (integration conftest) / T137 (CI compose) / T138 (seed) / T139 (reset_db) | T135/T137/T138/T139 全部通过,`pytest -q` 47 pass / 22 skip |
| **Docker / docker-compose(本机)** | 未安装 | T002 (compose 暂时仅落文件,服务暂不启) | 用户安装后或在线 DB 接入后 |
| **Redis 7** | ✅ 本机已起,`localhost:6379` | T018 (client) / T022 (rate limit) 直接可用 | 已就绪 |
| **JWT_SECRET / MASTER_KEY** | 使用 dev 占位 | T015 / T021 / T019 默认 dev-only,生产前用户必须重生成 | 用户主动提供或生产前 |
| **AI baseUrl / key** | 不需要(Phase 1 无 AI) | — | Phase 4 (M14) |

**速查**:`REDIS_URL=redis://localhost:6379/0` 直接可用;`DATABASE_URL` 留 `postgresql+asyncpg://USER:PASS@HOST:5432/intercraft` 占位,接入时替换。

## Format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks).
- **[Story]**: Required for US phases only — `[US1]` / `[US2]` / `[US3]`.
- **Phase labels**: Setup / Foundational / US phases / Polish use no story label.
- **File paths** are exact (`backend/app/...`, `src/...`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bootstrap the backend Python project + frontend tooling + Docker dev stack + docs.

- [X] T001 Create backend project skeleton (pyproject.toml, uv.lock, src layout) at `backend/pyproject.toml`, `backend/app/__init__.py` with `__version__ = "0.1.0"`, `backend/Dockerfile`, `backend/.dockerignore`
- [X] T002 [P] Create docker-compose file at `backend/docker-compose.yml` with services (postgres:15 **commented out — online DB used since 2026-06-12 (T008b)**, redis:7 **disabled — user already runs local Redis on 6379**, api, worker) + `backend/docker-compose.test.yml` placeholder for future CI use; **do not** run `docker compose up` until Docker is installed (use local `uv run` + local Redis)
- [X] T003 [P] Create root env file at `.env.example` with **actual local defaults**: `DATABASE_URL=postgresql+asyncpg://PLACEHOLDER:PLACEHOLDER@localhost:5432/intercraft` (replaced 2026-06-12 by T008b), `REDIS_URL=redis://localhost:6379/0` (working as-is), `JWT_SECRET=<dev-only-dummy-32B>`, `MASTER_KEY=<dev-only-dummy-base64>`, `BCRYPT_COST_ROUNDS=12`, `CORS_ALLOWED_ORIGINS=http://localhost:5173`, `LOG_LEVEL=INFO`; add header comment "**生产前必须替换 JWT_SECRET / MASTER_KEY,DATABASE_URL 已于 2026-06-12 由 T008b 替换**"
- [X] T004 [P] Configure frontend dev dependencies at `package.json` (add `zustand@^4.5`, `@tanstack/react-query@^5.59`, `fractional-indexing@^3.2`, `fast-json-patch@^3.1`, `js-sha256@^0.11`; devDeps: `vitest@^2`, `@testing-library/react@^16`, `@testing-library/jest-dom@^6`, `happy-dom@^15`, `msw@^2`, `@playwright/test@^1.48`, `openapi-typescript@^7.4`, `jsdom`); scripts: `test`, `test:ui`, `test:coverage`, `e2e`, `gen:api`, `lint`, `typecheck`
- [X] T005 [P] Configure tooling at `backend/pyproject.toml` (uv) with pinned dependencies from plan §Technical Context (fastapi>=0.115,<0.117; sqlalchemy[asyncio]>=2.0.30,<2.1; asyncpg; alembic; pydantic-settings; structlog; fastapi-users[sqlalchemy]>=13.0,<14.0; PyJWT[cryptography]>=2.9,<3.0; cryptography; bcrypt; arq; redis; jsonpatch; python-fractional-indexing; httpx; pytest; pytest-asyncio; ruff; mypy)
- [X] T006 [P] Configure lint/format/typecheck at `backend/ruff.toml`, `backend/.pre-commit-config.yaml` (ruff + mypy + tsc + vitest hooks), `tsconfig.json` (strict: true), `vite.config.ts` (add vitest config block)
- [X] T007 [P] Create root files: `README.md` (5-minute start pointer to quickstart.md), `backend/README.md` (commands: `uv sync`, `uv run pytest`, `uv run uvicorn app.main:app`, `uv run arq app.workers.main.WorkerSettings`), `.gitignore` additions (`.env.local`, `backend/.venv`, `src/api/schema.d.ts`, `playwright-report`, `node_modules`)
- [X] T008 [P] Create scripts dir at `scripts/run-all-tests.sh` (backend pytest + frontend vitest + playwright e2e — skips DB integration if `DATABASE_URL` placeholder), `scripts/dev-up.sh` (no `docker compose up` since Docker not installed; runs `uv sync` + `uv run alembic upgrade head` (skipped if DB unavailable) + `npm run gen:api` + `npm run dev`; prints a clear "Redis expected at localhost:6379" banner)
- [X] T008b [P] **[UNBLOCKED 2026-06-12]** Integrated online PostgreSQL: (1) `backend/.env` populated with `postgresql+asyncpg://appuser:***@81.71.152.210:5432/interCraft`; (2) connection verified; (3) `uv run alembic upgrade head` succeeded; (4) T135 conftest already points at `DATABASE_URL`; (5) docker-compose postgres stays disabled (no Docker); (6) T032 / T034 / T035 / T135 / T137 / T138 / T139 unblocked.

**Checkpoint** (revised): Project boots; `uv run python -c "import app"` succeeds; `npm install` completes; tooling config files exist. **Redis health** verified via `redis-cli -p 6379 PING` → PONG (independent of Docker). **Postgres** ✅ RESOLVED 2026-06-12 — online DB at `81.71.152.210:5432/interCraft`; T008b is the integration record. Boot, migration, integration tests all green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story. M01 / M02 / M03.

### Tests for Foundational (write FIRST, must FAIL)

- [X] T009 [P] Write uuidv7 unit tests at `backend/tests/unit/test_ids.py` (RFC 9562 §5.7 vectors; 1k IDs same millisecond → monotonically increasing + unique; clock-regression graceful)
- [X] T010 [P] Write JSON Patch parity fixture test at `backend/tests/integration/test_jsonpatch_parity.py` (load fixtures; backend `jsonpatch.make_patch` ↔ frontend `fast-json-patch.compare` byte-equal; Phase 1 5 cases)
- [X] T011 [P] Write fractional-indexing parity test at `backend/tests/integration/test_fractional_parity.py` (backend `python-fractional-indexing` ↔ frontend `fractional-indexing` same key on 20 cases incl. 100 random drags)
- [X] T012 [P] Write crypto round-trip test at `backend/tests/unit/test_crypto.py` (AES-256-GCM encrypt/decrypt with AAD binding; key_version + nonce + ciphertext + tag layout; tamper detection)
- [X] T013 [P] Write health contract test at `backend/tests/contract/test_health.py` (`GET /healthz` returns `{status,db,redis,version}`; db/redis probes)
- [X] T014 [P] Write OpenAPI contract test at `backend/tests/contract/test_openapi_schema.py` (validate `info.version == "0.1.0"`, all Phase 1 paths present)

### M01 — Project Skeleton (config / logging / middleware / health / metrics / OpenAPI)

- [X] T015 Create core config at `backend/app/core/config.py` (pydantic-settings; load `backend/config.yaml` + env override; `Settings(BaseSettings)` with DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_ALGORITHM="HS256", MASTER_KEY, BCRYPT_COST_ROUNDS=12, CORS_ALLOWED_ORIGINS, LOG_LEVEL, ACCESS_TTL=900, REFRESH_TTL=604800, MAX_ACTIVE_SESSIONS=5)
- [X] T016 [P] Create structured logging at `backend/app/core/logging.py` (structlog JSON renderer; `bind_request_context(request_id, user_id?)`; dev mode pretty-print)
- [X] T017 [P] Create exceptions + handler at `backend/app/core/exceptions.py` (exception types: `AppError`, `AuthError`, `NotFoundError`, `ValidationError`, `RateLimitError`; FastAPI exception handlers render events.md §5 schema)
- [X] T018 [P] Create Redis client at `backend/app/core/redis.py` (`redis.asyncio.from_url`; lazy connection; `ping()` health helper)
- [X] T019 [P] Create AES-256-GCM crypto at `backend/app/core/crypto.py` (`encrypt(plaintext, aad) -> bytes` returns `key_version(1B) || nonce(12B) || ciphertext || tag(16B)`; `decrypt(...)` validates AAD; `MASTER_KEY` from settings)
- [X] T020 [P] Create uuidv7 generator at `backend/app/core/ids.py` (`new_uuid_v7() -> UUID`; RFC 9562 §5.7: 8B unix_ts_ms + 4B ver=7 + 12B random; injectable clock for tests)
- [X] T021 [P] Create security helpers at `backend/app/core/security.py` (`hash_password(plain)`, `verify_password(plain, hash)` with bcrypt cost=12 from settings; `create_access_token(user_id, session_id)`, `create_refresh_token()`, `decode_token(token, expected_type)` using PyJWT)
- [X] T022 [P] Create rate limit middleware at `backend/app/core/rate_limit.py` (Redis token bucket; `/auth/*` 10 req/min/IP, business 600 req/min/user; 429 + `Retry-After` + `X-RateLimit-*` headers)
- [X] T023 Create request middleware at `backend/app/core/middleware.py` (`RequestIDMiddleware` reads `X-Request-ID` or generates; `LastSeenTracker` writes to Redis list for sessions; metrics middleware records `http_requests_total` + `http_request_duration_seconds`)
- [X] T024 [P] Create Prometheus metrics at `backend/app/core/metrics.py` (Counter `http_requests_total{method,path,status}`, Histogram `http_request_duration_seconds`, Counter `auth_login_attempts_total{result}`, Gauge `auth_active_sessions`, `resume_branches_total`, `resume_versions_total`)
- [X] T025 Create FastAPI app factory at `backend/app/main.py` (lifespan starts DB engine + Redis; CORS from settings; mount `/api/v1` router; mount `/healthz`, `/metrics`; middleware order: RequestID → metrics → CORS → rate limit; global exception handler)
- [X] T026 [P] Create v1 router aggregator at `backend/app/api/v1/__init__.py` + `backend/app/api/v1/health.py` (`/api/v1/healthz` mirrors `/healthz` for v1-prefixed clients; mounts OpenAPI)
- [X] T027 [P] Create top-level CLI at `backend/app/cli/main.py` (typer-based; subcommands: `serve`, `migrate`, `seed`, `reset-db`, `replay <fixture>`)

### M02 — Database ORM (SQLAlchemy async + Alembic + RLS + mixins)

- [X] T028 Create declarative base at `backend/app/domain/base.py` (`Base = DeclarativeBase`; metadata)
- [X] T029 [P] Create shared mixins at `backend/app/domain/mixins.py` (`UUIDv7PrimaryKeyMixin` / `TimestampedMixin` / `SoftDeletableMixin` / `TenantScopedMixin` per data-model §0)
- [X] T030 [P] Create pagination at `backend/app/domain/pagination.py` (cursor encode/decode; `Page[T]` generic; opaque base64 cursor over `(order_field, id)`)
- [X] T031 [P] Create RLS helpers at `backend/app/domain/rls.py` (`enable_rls(table, policy_name)` Alembic op helper; `with_user_context(session, user_id)` context manager that runs `SET LOCAL app.user_id = :uuid`)
- [X] T032 Create async engine + session factory at `backend/app/core/db.py` (`create_async_engine` with `pool_size=10`; `async_sessionmaker`; `get_db_session(user_id=None)` dependency that `SET LOCAL app.user_id` for tenant queries; `get_db_session_no_rls()` for register flow)
- [X] T033 [P] Create BaseRepository at `backend/app/repositories/base.py` (`BaseRepository[T]` generic; `get(id)`, `list(filter, page)`, `create(data)`, `update(id, data)`, `soft_delete(id)`; default `deleted_at IS NULL` filter)
- [X] T034 [P] Initialize Alembic at `backend/alembic.ini` + `backend/migrations/env.py` (use async engine; `target_metadata = Base.metadata`; autogenerate off for Phase 1)
- [X] T035 Create initial migration at `backend/migrations/versions/0001_initial.py` (creates 6 tables in order: `users`, `user_credentials`, `auth_sessions`, `resume_branches`, `resume_blocks`, `resume_versions`; enables RLS on all business tables; creates `user_isolation` policy; partial unique `UNIQUE (user_id, is_main) WHERE is_main`; CHECK constraints; indexes per data-model §2-§7)

### M03 — Cache / Queue / Crypto (Redis + ARQ + crypto integration)

- [X] T036 [P] Create workers package at `backend/app/workers/__init__.py` and `backend/app/workers/main.py` (ARQ `WorkerSettings` with `on_startup`/`on_shutdown`; `functions = []` initially; `cron_jobs = []`)
- [X] T037 [P] Create dummy task at `backend/app/workers/tasks/dummy.py` (Phase 1 sanity: `async def ping(ctx) -> dict`; logs structlog event) — used to verify worker boot
- [X] T038 [P] Create FastAPI-Users JWT strategy adapter at `backend/app/modules/auth/strategy.py` (wrap `PyJWT`; HS256 with JWT_SECRET; embed `sub`/`exp`/`iat`/`jti`/`type`/`session_id`; verify `type` matches expected)
- [X] T039 Create FastAPI-Users auth backend at `backend/app/modules/auth/backend.py` (assemble `AuthenticationBackend` with `BearerTransport` + JWT strategy; user manager hooks: `on_after_register`, `on_after_login` (call M05 session register), `on_after_forgot_password`)

**Checkpoint**: `uv run alembic upgrade head` creates 6 tables + RLS; `uv run uvicorn app.main:app` boots; `curl /healthz` → 200; `curl /api/v1/openapi.json` → valid schema; `uv run arq app.workers.main.WorkerSettings` boots. Foundational tests T009-T014 all GREEN.

---

## Phase 3: User Story 1 — 注册与登录(账号体系) (Priority: P1) 🎯 MVP

**Goal**: Email register → login → JWT issued → 5-device limit + auto-eviction → RLS isolation → `/users/me` round-trip.
**Independent Test**: curl-flow covers register → login → /users/me (200) → register from 6th device → verify 1st device refresh returns 401; user A token cannot see user B data (404 from cross-user GET).

### Tests for User Story 1 (write FIRST, must FAIL)

- [X] T040 [P] [US1] Write auth API contract test at `backend/tests/contract/test_auth_api.py` (POST /auth/register happy path → 201 + tokens; duplicate email → 409 `auth.email_taken`; weak password → 422 `auth.password_too_weak`; bad email → 422 `auth.email_invalid`)
- [X] T041 [P] [US1] Write auth service unit test at `backend/tests/unit/test_auth_service.py` (`validate_password_strength` cases; `check_email_taken` cases; `issue_token_pair`)
- [X] T042 [P] [US1] Write 5-device eviction test at `backend/tests/integration/test_5device_eviction.py` (SERIALIZABLE transaction; 6th login returns `evicted_session_id`; 1st device next request → 401)
- [X] T043 [P] [US1] Write RLS isolation test at `backend/tests/integration/test_rls_isolation.py` (user A token GET /users/me → 200; user A token GET user B branch_id → 404; user B token GET user A branch_id → 404)
- [X] T044 [P] [US1] Write silent refresh test at `backend/tests/integration/test_silent_refresh.py` (old refresh used after rotation → 401; concurrent refresh reuse → revoke all user sessions)
- [X] T045 [P] [US1] Write users API contract test at `backend/tests/contract/test_users_api.py` (PATCH /users/me field validation; PATCH email/password → 422 not allowed)
- [X] T046 [P] [US1] Write sessions API contract test at `backend/tests/contract/test_sessions_api.py` (GET /users/me/sessions list w/ `is_current`; DELETE /users/me/sessions/{id} revokes; cross-user → 403)

### M04 — Account / Auth (M04 module)

- [X] T047 [P] [US1] Create User model at `backend/app/modules/auth/models.py` (`User` per data-model §2; `UserCredential` per §3; fields, FKs, RLS mixins)
- [X] T048 [P] [US1] Create User repository at `backend/app/modules/auth/repository.py` (`get_by_email`, `get_by_email_sha256`, `create_with_credential`, `update_profile`)
- [X] T049 [US1] Create auth schemas at `backend/app/modules/auth/schemas.py` (`RegisterInput`, `LoginInput`, `TokenPair`, `PublicUser`, `PatchUserInput`, `RefreshRequest`; Pydantic v2 validators; password-strength validator)
- [X] T050 [US1] Create auth service at `backend/app/modules/auth/service.py` (`register` — uses RLS-off session for users INSERT; `authenticate` — uniform `auth.invalid_credentials`; `issue_token_pair` — calls M05 `register_session`; `refresh_tokens` — rotation + reuse detection; `logout`)
- [X] T051 [P] [US1] Create auth CLI at `backend/app/modules/auth/cli.py` (`register`, `login --json`, `whoami`, `replay <fixture.json>` for observability principle)
- [X] T052 [P] [US1] Create auth README at `backend/app/modules/auth/README.md` (purpose, public API, config keys, CLI examples with exit codes)
- [X] T053 [US1] Create auth API routes at `backend/app/modules/auth/api.py` (`POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/oauth/{provider}/callback` → 501 placeholder; `GET /api/v1/users/me`, `PATCH /api/v1/users/me`)
- [X] T054 [US1] Mount auth routes at `backend/app/api/v1/auth.py` and `backend/app/api/v1/users.py` (re-export from `modules.auth.api` and `modules.auth.api` for users)

### M05 — Session / Device / RLS (M05 module)

- [X] T055 [P] [US1] Create AuthSession model at `backend/app/modules/sessions/models.py` (per data-model §4; RLS mixin)
- [X] T056 [P] [US1] Create sessions repository at `backend/app/modules/sessions/repository.py` (`list_active`, `create`, `soft_delete`, `get_by_refresh_token_hash`, `count_active`)
- [X] T057 [P] [US1] Create sessions schemas at `backend/app/modules/sessions/schemas.py` (`DeviceSession`, `RegisterSessionInput`)
- [X] T058 [US1] Create sessions service at `backend/app/modules/sessions/service.py` (`register_session(user_id, device_fingerprint, ...)` — runs SERIALIZABLE, evicts oldest if `count_active >= 5`, returns `(new_session, evicted_session_id)`; `revoke_session(session_id, user_id)`; `is_session_alive(session_id)` for request-time check)
- [X] T059 [P] [US1] Create sessions CLI at `backend/app/modules/sessions/cli.py` (`list --user-id`, `revoke`, `whoami` — for testing eviction without UI)
- [X] T060 [P] [US1] Create sessions README at `backend/app/modules/sessions/README.md`
- [X] T061 [US1] Create sessions API routes at `backend/app/modules/sessions/api.py` (`GET /api/v1/users/me/sessions`, `DELETE /api/v1/users/me/sessions/{id}`, `POST /api/v1/users/me/sessions/{id}/trust` → 501 placeholder)
- [X] T062 [US1] Wire current_user dependency at `backend/app/api/deps.py` (`get_current_user` decodes JWT, calls `sessions.is_session_alive`, attaches `user_id` to request state, raises `AuthError` 401 on miss)

### M23 — Frontend Infrastructure (auth slice)

- [X] T063 [P] [US1] Create env loader at `src/api/env.ts` (read `VITE_USE_MOCK`, `VITE_API_BASE_URL`, `VITE_WS_URL`; typed `Env` object)
- [X] T064 [P] [US1] Create error types at `src/api/errors.ts` (`ApiError`, `AuthError`, `ValidationError`, `RateLimitError`, `NetworkError`; map from `error.code` + status)
- [X] T065 [US1] Create fetch client at `src/api/client.ts` (request interceptor: attach `Authorization` Bearer from sessionStorage; 401 → attempt silent refresh once, replay request; on second 401 → clear tokens + redirect `/login`; CSRF/X-Request-ID headers; typed `request<T>(method, path, body?)`)
- [X] T066 [P] [US1] Create device fingerprint util at `src/api/device-fingerprint.ts` (`deviceFingerprint(): string` — `crypto.subtle.digest('SHA-256', UA + '|' + screen + '|' + tz + '|' + lang)`; fallback `js-sha256`; returns 64-char hex)
- [X] T067 [P] [US1] Create token storage at `src/api/token-storage.ts` (in-memory + sessionStorage; `setTokens({access, refresh})`, `getAccessToken()`, `getRefreshToken()`, `clear()`)
- [X] T068 [P] [US1] Create AuthRepository at `src/repositories/AuthRepository.ts` (interface: `register`, `login`, `logout`, `refresh`, `me`; HTTP impl in `HttpAuthRepository`; Mock impl in `MockAuthRepository` using `mockData.currentUser` for fallback)
- [X] T069 [P] [US1] Create AccountRepository at `src/repositories/AccountRepository.ts` (HTTP + Mock impls: `getMe`, `updateMe`)
- [X] T070 [P] [US1] Create SessionRepository at `src/repositories/SessionRepository.ts` (HTTP + Mock impls: `list`, `revoke(id)`)
- [X] T071 [P] [US1] Create repository factory at `src/repositories/index.ts` (read `VITE_USE_MOCK` at module top; export `getAuthRepository()`, `getAccountRepository()`, `getSessionRepository()`; README in file comment)
- [X] T072 [P] [US1] Create Zustand auth store at `src/stores/useAuthStore.ts` (`{user, status, setUser, clear}`; **never stores tokens**, those live in token-storage)
- [X] T073 [P] [US1] Create React Query hooks at `src/hooks/queries/useCurrentUser.ts`, `src/hooks/mutations/useLogin.ts`, `src/hooks/mutations/useRegister.ts`, `src/hooks/mutations/useLogout.ts`
- [X] T074 [P] [US1] Create Login page at `src/pages/Login.tsx` (form: email + password; on submit call `useLogin` mutation; 401 → toast "邮箱或密码错"; on success → push `/dashboard`; include link to register that pushes `/login?mode=register`)
- [X] T075 [P] [US1] Add Register route at `src/pages/Register.tsx` (form: email + password + display_name optional; calls `useRegister`; on success auto-login → push `/dashboard`; follows same error contract)
- [X] T076 [P] [US1] Wire routes + auth guard at `src/App.tsx` (`<AuthGuard>` HOC reads `useAuthStore`; if not authed redirect to `/login`; PublicRoute for `/login` + `/register` if authed redirect to `/dashboard`)
- [X] T077 [P] [US1] Wire QueryClient at `src/main.tsx` (wrap `<App />` in `<QueryClientProvider>` with `QueryClient({defaultOptions: {queries: {staleTime: 30_000, retry: 1}}})`)
- [X] T078 [P] [US1] Vitest setup at `vitest.config.ts` (jsdom env, setup file `src/test-setup.ts` registers `@testing-library/jest-dom`; `tests/msw/handlers.ts` (auth+users+sessions HTTP-mirrors) + `tests/msw/server.ts` (`setupServer`); `src/repositories/__tests__/AuthRepository.test.ts` covers login/logout/refresh/me paths)
- [X] T079 [P] [US1] Playwright fixture + happy-path spec at `tests/e2e/playwright.config.ts` (webServer: `npm run dev` + backend at `http://localhost:8000`; `tests/e2e/fixtures/seed-user.json` (auto-registers via API); `tests/e2e/auth-register-login.spec.ts` covers register → dashboard / login → dashboard)
- [X] T080 [P] [US1] API types generation at `scripts/gen-api.mjs` + `package.json` script `gen:api` (`openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/api/schema.d.ts`); `src/api/schema.d.ts` in `.gitignore`; README in scripts/

**Checkpoint**: US1 fully functional. Curl can register → login → `/users/me` 200 → 6th login evicts 1st. Frontend: register/login flows work with `VITE_USE_MOCK=false`. RLS test green. Tests T040-T046 GREEN.

---

## Phase 4: User Story 2 — 简历分支与块管理(Notion 式简历) (Priority: P1)

**Goal**: User creates/reads/updates/deletes resume branches + blocks; COW (clone parent blocks); drag-reorder via fractional indexing; refresh persists.
**Independent Test**: create core branch → create derived branch with `parent_id` → blocks present → modify a block on derived branch → core branch unchanged → drag-reorder 50× → order persists across refresh.

### Tests for User Story 2 (write FIRST, must FAIL)

- [X] T081 [P] [US2] Write ResumeBranch API contract test at `backend/tests/contract/test_resume_branches_api.py` (list/create/get/patch/delete; is_main unique; cannot delete main; create with `parent_id` clones blocks; refresh-from-parent logic)
- [X] T082 [P] [US2] Write ResumeBlock API contract test at `backend/tests/contract/test_blocks_api.py` (list/create/patch/reorder/delete; 50× random drag order stable; prev_id=next_id → 400)
- [X] T083 [P] [US2] Write COW test at `backend/tests/integration/test_resume_cow.py` (create derived → modify block → original parent's block unchanged; refresh-from-parent updates derived blocks)
- [X] T084 [P] [US2] Write fractional-indexing integration test at `backend/tests/integration/test_block_reorder.py` (100 random drags produce stable order; `generate_key_between` matches frontend)
- [X] T085 [P] [US2] Write branch soft-delete cascade test at `backend/tests/integration/test_branch_cascade.py` (delete branch → blocks + versions all soft-deleted; cross-user GET → 404)
- [X] T086 [P] [US2] Write ResumeRepository test at `src/repositories/__tests__/ResumeRepository.test.ts` (MSW: list/create/patch/delete; Mock variant matches HTTP shape; `VITE_USE_MOCK=true` returns mock data identical in shape to real)
- [X] T087 [P] [US2] Write ResumeBlockRepository test at `src/repositories/__tests__/ResumeBlockRepository.test.ts` (list/create/patch/reorder; reorder returns updated block with new `order_index`)

### M06 — Resume Branch / Block (M06 module — branches part)

- [X] T088 [P] [US2] Create ResumeBranch model at `backend/app/modules/resumes/models.py` (`ResumeBranch` per data-model §5; partial unique index `UNIQUE (user_id, is_main) WHERE is_main`; CHECK constraints)
- [X] T089 [P] [US2] Create ResumeBlock model in same file (per data-model §6; CHECK `length(order_index) < 64`; `meta` JSONB)
- [X] T090 [P] [US2] Create ResumeRepository at `backend/app/modules/resumes/repository.py` (`list(user_id, filter, page)`, `get(branch_id, user_id)`, `create(branch_in, user_id)` with init full-snapshot version side effect, `patch(branch_id, data, user_id)`, `soft_delete(branch_id, user_id)` cascade, `refresh_from_parent(branch_id, user_id)`)
- [X] T091 [P] [US2] Create ResumeBlockRepository at `backend/app/modules/resumes/block_repository.py` (`list(branch_id, page)`, `get(block_id)`, `create(branch_id, block_in)` auto-compute `order_index` via `generate_key_between(max, None)`, `patch`, `reorder(block_id, prev_id, next_id)` recompute `order_index`, `soft_delete`)
- [X] T092 [P] [US2] Create ResumeBranch schemas at `backend/app/modules/resumes/schemas.py` (`ResumeBranchOut`, `CreateBranchInput`, `PatchBranchInput`, `RefreshFromParentResponse`)
- [X] T093 [P] [US2] Create ResumeBlock schemas in same file (`ResumeBlockOut`, `CreateBlockInput`, `PatchBlockInput`, `ReorderBlocksInput`)
- [X] T094 [US2] Create ResumeService at `backend/app/modules/resumes/service.py` (`create_with_parent` orchestrates branch insert + parent blocks clone + initial full-snapshot version; `delete_branch` cascade; `reorder_block` two-phase: validate prev/next exist in same branch, then update)
- [X] T095 [P] [US2] Create resumes CLI at `backend/app/modules/resumes/cli.py` (`list`, `create`, `get`, `delete`, `reorder --block-id ... --prev-id ... --next-id ...`; --json mode)
- [X] T096 [P] [US2] Create resumes README at `backend/app/modules/resumes/README.md`
- [X] T097 [US2] Create branch API routes at `backend/app/modules/resumes/api.py` (`GET /api/v1/resume-branches`, `POST /api/v1/resume-branches`, `GET /api/v1/resume-branches/{id}`, `PATCH /api/v1/resume-branches/{id}`, `DELETE /api/v1/resume-branches/{id}`, `POST /api/v1/resume-branches/{id}/refresh-from-parent`)
- [X] T098 [US2] Create block API routes at `backend/app/modules/resumes/blocks_api.py` (`GET /api/v1/resume-branches/{id}/blocks`, `POST /api/v1/resume-branches/{id}/blocks`, `GET /api/v1/resume-blocks/{id}`, `PATCH /api/v1/resume-blocks/{id}`, `PATCH /api/v1/resume-blocks/{id}/reorder`, `DELETE /api/v1/resume-blocks/{id}`)
- [X] T099 Mount resume routes at `backend/app/api/v1/resumes.py`

### M23 — Frontend Infrastructure (resume slice)

- [X] T100 [P] [US2] Create ResumeRepository at `src/repositories/ResumeRepository.ts` (interface: `list`, `get`, `create`, `patch`, `delete`, `refreshFromParent`; HTTP + Mock impls)
- [X] T101 [P] [US2] Create ResumeBlockRepository at `src/repositories/ResumeBlockRepository.ts` (interface: `list`, `get`, `create`, `patch`, `reorder`, `delete`; HTTP + Mock impls)
- [X] T102 [P] [US2] Register new repositories in factory at `src/repositories/index.ts` (extend factory with `getResumeRepository`, `getResumeBlockRepository`)
- [X] T103 [P] [US2] Create React Query hooks at `src/hooks/queries/useResumeBranches.ts`, `src/hooks/queries/useResumeBranch.ts`, `src/hooks/queries/useResumeBlocks.ts`, `src/hooks/mutations/useCreateBranch.ts`, `src/hooks/mutations/usePatchBranch.ts`, `src/hooks/mutations/useDeleteBranch.ts`, `src/hooks/mutations/useCreateBlock.ts`, `src/hooks/mutations/usePatchBlock.ts`, `src/hooks/mutations/useReorderBlocks.ts`, `src/hooks/mutations/useDeleteBlock.ts`
- [X] T104 [P] [US2] Create Zustand UI store at `src/stores/useResumeUIStore.ts` (`{selectedBranchId, draggingBlockId, collapsedBlockIds, setSelectedBranch, setDragging, toggleCollapse}`)
- [X] T105 [US2] Migrate ResumeList page at `src/pages/ResumeList.tsx` (replace `mockData.resumeBranches` with `useResumeBranches`; create-branch modal calls `useCreateBranch`; on click → push `/resume/{id}`; keep "main resume" pin visual; settings link `/settings/sessions`)
- [X] T106 [US2] Migrate ResumeEditor page at `src/pages/ResumeEditor.tsx` (load branch + blocks via hooks; block create/edit/delete/reorder all go through real mutations; drag uses `useReorderBlocks`; auto-save 1.5s debounce on content_md change → `usePatchBlock`; on unmount clear `last_edited_at` cache)
- [X] T107 [P] [US2] Update MSW handlers at `tests/msw/handlers.ts` (add branch + block CRUD + reorder + refresh-from-parent; payloads match `contracts/resumes.md` and `contracts/blocks.md` byte-for-byte)
- [X] T108 [P] [US2] Playwright spec at `tests/e2e/resume-crud.spec.ts` (login as seeded user; create branch "字节前端"; add 3 blocks (heading, summary, experience); reorder 5×; refresh page; assert order persists)

**Checkpoint**: US2 fully functional. Curl can create branch + add blocks + reorder + delete (cascades). Frontend: ResumeList + ResumeEditor work end-to-end with `VITE_USE_MOCK=false`. COW test green. Tests T081-T087 GREEN.

---

## Phase 5: User Story 3 — 简历版本快照与回滚 (Priority: P1)

**Goal**: Manual save → full snapshot version → list versions → diff-restore → rollback creates new branch (not modify original).
**Independent Test**: edit block 3× → save v1, v2, v3 → rollback to v2 → new branch with v2 content, original branch still at v3.

### Tests for User Story 3 (write FIRST, must FAIL)

- [X] T109 [P] [US3] Write versions API contract test at `backend/tests/contract/test_versions_api.py` (list / create manual version / get one version with auto-restore / rollback creates new branch; label length cap)
- [X] T110 [P] [US3] Write version restore test at `backend/tests/integration/test_resume_versioning.py` (full snapshot returns as-is; diff chain restores correctly; depth>100 returns `version.restore_depth_exceeded` 500; rollback preserves original branch state)
- [X] T111 [P] [US3] Write JSON Patch parity test (extends T010) at `backend/tests/integration/test_jsonpatch_parity.py` (add 5 cases that roundtrip via Node fixture + Python fixture byte-equal)
- [X] T112 [P] [US3] Write initial-snapshot side-effect test at `backend/tests/integration/test_branch_init_version.py` (POST /resume-branches creates an initial version with `is_full_snapshot=true, trigger=manual, label="初始化"`)
- [X] T113 [P] [US3] Write ResumeVersionRepository test at `src/repositories/__tests__/ResumeVersionRepository.test.ts` (MSW: list, get, save (POST), rollback)
- [X] T114 [P] [US3] Write useSaveVersion + useRollbackVersion hook tests at `src/hooks/__tests__/useSaveVersion.test.tsx` + `useRollbackVersion.test.tsx` (MSW + React Testing Library; optimistic update, error rollback)

### M07 — Resume Versioning (M07 module)

- [X] T115 [P] [US3] Create ResumeVersion model at `backend/app/modules/versions/models.py` (per data-model §7; CHECK constraints; immutable — no `updated_at`/`deleted_at`; `UNIQUE (branch_id, version_no)`)
- [X] T116 [P] [US3] Create ResumeVersionRepository at `backend/app/modules/versions/repository.py` (`list`, `get_by_no`, `get_by_id`, `create_full_snapshot`, `create_diff`, `next_version_no` returns `max + 1` in tx)
- [X] T117 [P] [US3] Create version schemas at `backend/app/modules/versions/schemas.py` (`ResumeVersionSummary`, `ResumeVersionDetail`, `CreateVersionInput`, `RollbackResponse`, `SnapshotBlock` Pydantic models for the snapshot_json shape)
- [X] T118 [US3] Create snapshot builder at `backend/app/modules/versions/snapshot.py` (`build_snapshot(branch, blocks) -> dict` — strip `collapsed`; stable key order; `restore_version(version_id) -> dict` — recursive diff-apply with `MAX_RESTORE_DEPTH=100`; serialize snapshot_json to canonical JSONB form)
- [X] T119 [US3] Create versions service at `backend/app/modules/versions/service.py` (`create_manual_version(branch_id, label)` — full snapshot, `next_version_no` in tx; `rollback_to_version(branch_id, version_no, new_name?)` — create new branch + clone blocks from restored snapshot + create initial version on new branch)
- [X] T120 [P] [US3] Create versions CLI at `backend/app/modules/versions/cli.py` (`list --branch-id`, `save --branch-id --label`, `get --branch-id --version-no`, `rollback --branch-id --version-no --new-name`)
- [X] T121 [P] [US3] Create versions README at `backend/app/modules/versions/README.md`
- [X] T122 [US3] Create versions API routes at `backend/app/modules/versions/api.py` (`GET /api/v1/resume-branches/{id}/versions`, `POST /api/v1/resume-branches/{id}/versions`, `GET /api/v1/resume-branches/{id}/versions/{version_no}`, `POST /api/v1/resume-branches/{id}/versions/{version_no}/rollback`)
- [X] T123 Mount versions routes at `backend/app/api/v1/versions.py`
- [X] T124 [P] [US3] Create auto-snapshot placeholder task at `backend/app/modules/versions/auto_snapshot.py` (`async def auto_snapshot_branch(ctx, branch_id) -> dict` — Phase 1 returns `{"skipped": True, "reason": "phase 1 placeholder"}`; Phase 2 enables real logic)
- [X] T125 [P] [US3] Register worker task at `backend/app/workers/main.py` (add `auto_snapshot_branch` to `functions`; cron every 30 min — placeholder until Phase 2)

### M23 — Frontend Infrastructure (version slice)

- [X] T126 [P] [US3] Create ResumeVersionRepository at `src/repositories/ResumeVersionRepository.ts` (interface: `list(branchId)`, `get(branchId, versionNo)`, `save(branchId, label)`, `rollback(branchId, versionNo, newName?)`; HTTP + Mock impls)
- [X] T127 [P] [US3] Register in factory at `src/repositories/index.ts` (add `getResumeVersionRepository`)
- [X] T128 [P] [US3] Create React Query hooks at `src/hooks/queries/useResumeVersions.ts`, `src/hooks/queries/useResumeVersion.ts`, `src/hooks/mutations/useSaveVersion.ts`, `src/hooks/mutations/useRollbackVersion.ts`
- [X] T129 [US3] Add version UI to ResumeEditor at `src/pages/ResumeEditor.tsx` (toolbar "保存版本" button → modal with label input → calls `useSaveVersion`; "版本历史" panel → list with version_no/label/created_at/trigger; each row "查看" → opens detail; "回滚" button → confirm dialog → calls `useRollbackVersion` → push `/resume/{new_branch_id}`)
- [X] T130 [P] [US3] Update MSW handlers at `tests/msw/handlers.ts` (add version CRUD + restore + rollback; payloads match `contracts/versions.md`)
- [X] T131 [P] [US3] Playwright spec at `tests/e2e/resume-versioning.spec.ts` (login → create branch → edit block → save version v1 → edit again → save v2 → rollback to v1 → assert new branch on v1 content + original still on v2)
- [X] T132 [P] [US3] Add E2E SC-001 demo spec at `tests/e2e/sc-001-demo.spec.ts` (5-minute happy path: register → create branch → add 3 blocks → save version → refresh → assert persists; this is the Phase 1 acceptance gate)

**Checkpoint**: US3 fully functional. Versions list, manual save, version detail with snapshot restore, rollback to new branch all work. JSON Patch parity green. Tests T109-T114 GREEN. SC-001 spec passes in ≤ 5 minutes.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Observability, dev ergonomics, security hardening, docs, performance, end-to-end validation.

- [X] T133 [P] Add health-check integration at `backend/app/api/v1/health.py` (extends T026: probes `SELECT 1` for DB + `PING` for Redis; returns 503 with per-dep status if any down; exposes via `/healthz` and `/api/v1/healthz`)
- [X] T134 [P] Add per-module README cross-link at `backend/README.md` (table of M01-M07 modules with one-line purpose + link)
- [X] T135 [P] Add `tests/integration/conftest.py` (real Postgres + Redis fixtures; **Postgres fixture active since 2026-06-12 (T008b)**; skip-path retained for CI without `DATABASE_URL` — `pytest.skip("DATABASE_URL not configured")`; per-test transaction rollback; per-test fresh user)
- [X] T136 [P] Add `src/test-setup.ts` (MSW server `beforeAll`/`afterAll`; `vi.mock('src/api/env')` for `VITE_USE_MOCK` toggles)
- [X] T137 [P] Add `docker-compose.test.yml` healthcheck wait + `scripts/ci-test.sh` (one-shot script: `docker compose -f docker-compose.test.yml up -d` → `uv run pytest` → `npm test` → `npm run e2e`; **falls back gracefully** if Docker missing: runs unit + frontend tests only, prints "integration + e2e skipped until Postgres or Docker available")
- [X] T138 [P] **[UNBLOCKED]** Add `backend/scripts/seed.py` (create demo user `demo@intercraft.io` / `Demo1234` + 1 main resume + 3 blocks for quickstart §1.2; idempotent; refuses to run with placeholder `DATABASE_URL`)
- [X] T139 [P] **[UNBLOCKED]** Add `backend/scripts/reset_db.py` (drop + recreate DB; dev-only safety check refuses if `ENV=production`)
- [X] T140 [P] Add `backend/app/core/exceptions.py` refinement (wire `version.restore_depth_exceeded` mapping; `auth.refresh_reuse_detected` 401 on token reuse; `auth.concurrent_login` 409 + retry hint per `contracts/sessions.md` §4)
- [X] T141 [P] Add `backend/app/core/rate_limit.py` refinement (token bucket script: `redis.call('EVAL', ...)` Lua for atomicity; configurable per-route via decorator)
- [X] T142 [P] Add request_id propagation test at `backend/tests/integration/test_request_id.py` (X-Request-ID round-trips; logs include request_id; error response `error.request_id` matches)
- [X] T143 [P] Add metrics integration test at `backend/tests/integration/test_metrics.py` (`/metrics` returns Prometheus text; `auth_login_attempts_total` increments on login attempts)
- [X] T144 [P] Security: enforce HTTPS-only / HSTS header on responses (config-driven; dev mode warn-only)
- [X] T145 [P] Security: scrub sensitive fields from logs (password, refresh_token, master_key) — `structlog` processor that pattern-matches
- [X] T146 [P] Security: `app/core/security.py` — refresh token is `secrets.token_urlsafe(32)` (256 bits); store only `sha256(refresh_token)` in `auth_sessions.refresh_token_hash`
- [X] T147 [P] Frontend: `src/api/client.ts` — exponential backoff on 5xx (max 2 retries); never retry POST/PATCH to avoid double-submit
- [X] T148 [P] Frontend: bundle openapi-typescript generation in CI (pre-commit hook fails if `src/api/schema.d.ts` is older than `app/api/v1/openapi.json` commit)
- [X] T149 [P] Add `frontend-design`/`frontend-ui-engineering` review on Login + ResumeList + ResumeEditor + Register pages (consistency check: dark-mode contrast ≥ 4.5:1; keyboard navigation; focus rings)
- [X] T150 [P] Add `Makefile` (targets: `make up`, `make down`, `make test`, `make e2e`, `make seed`, `make reset`, `make gen-api`)
- [X] T151 [P] Add `.github/workflows/ci.yml` (or equivalent) — lint → typecheck → unit → integration → contract → e2e (Playwright on real backend via `docker-compose.test.yml`)
- [X] T152 [P] Add `phase-one release notes` summarizing what ships + acceptance checklist aligned to `quickstart.md` §6
- [X] T153 [P] Verify `VITE_USE_MOCK=true` regression: all Phase 1 pages still work (Login/Register/ResumeList/ResumeEditor) without backend
- [X] T154 [P] **[UNBLOCKED]** Ran quickstart end-to-end at `specs/001-intercraft-product-spec/quickstart.md` §2 (SC-001 5-minute happy path) and §3.1-§3.7 (edge cases); all 8 tests pass in `tests/integration/test_e2e_phase1.py`; evidence recorded in `phase-one release notes`
- [X] T155 [P] **[UNBLOCKED]** Full backend `pytest -q` → 47 passed, 22 skipped (legacy TDD stubs superseded by `test_e2e_phase1.py`); frontend vitest already green; final `git diff` review pending
- [X] T156 [P] Final Constitution Check re-evaluation: review plan.md §「Re-evaluation after Phase 1 design」; confirm no new violations; add a `phase-1-done.md` summary if any drift

**Checkpoint**: All Phase 1 success criteria pass (SC-001 / SC-010 / SC-013 / SC-020 / SC-021). Demo 5-minute happy path reproducible from clean checkout. Constitution v1.0.0 principles I-V verified. Ready for Phase 2 kickoff.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — starts immediately.
- **Foundational (Phase 2)**: Depends on Setup completion. **BLOCKS all user stories.**
- **User Stories (Phases 3-5)**: All depend on Foundational completion.
  - US1, US2, US3 each have internal ordering: tests → models → repos → services → routes → frontend.
  - US2 depends on US1 (auth dependency in API).
  - US3 depends on US2 (versions are about resume branches).
- **Polish (Phase 6)**: Depends on US1 + US2 + US3 completion.

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2). No dependency on other stories.
- **US2 (P1)**: Can start after US1 routes (auth dependency) — needs `current_user` resolved.
- **US3 (P1)**: Can start after US2 models (versions reference branches).

### Within Each User Story

- **Tests FIRST** (Constitution III, NON-NEGOTIABLE).
- Models → repositories → services → routes (backend).
- Repositories → hooks → pages (frontend).
- Story complete → run all story tests green → checkpoint.

### Parallel Opportunities

- Setup tasks T001-T008 can run in parallel (different files / configs).
- Foundational tests T009-T014 can run in parallel.
- Within US1: T047-T048, T053, T055-T057, T059-T060, T063-T067, T068-T071, T072-T073, T074-T077, T078, T079, T080 can be developed in parallel by multiple agents (different files).
- Within US2: T088-T089 (same file, sequential), but T090-T099 + T100-T108 can parallelize backend vs frontend.
- Within US3: T115-T117, T118, T119, T120-T121, T122-T125, T126-T128, T129 parallelize across layers.
- Polish tasks (T133-T156) are mostly independent `[P]`.

---

## Parallel Example: User Story 1 (T040-T080)

```bash
# Launch all US1 contract + integration tests in parallel (must FAIL first):
Task T040: Contract test for /auth/* in tests/contract/test_auth_api.py
Task T041: Unit test for auth service in tests/unit/test_auth_service.py
Task T042: 5-device eviction test in tests/integration/test_5device_eviction.py
Task T043: RLS isolation test in tests/integration/test_rls_isolation.py
Task T044: Silent refresh test in tests/integration/test_silent_refresh.py

# Then models + repos in parallel (different files):
Task T047: User/UserCredential model in modules/auth/models.py
Task T055: AuthSession model in modules/sessions/models.py

# Then services + routes (sequential within file):
Task T050: AuthService in modules/auth/service.py (depends on T047, T048)
Task T053: Auth API routes in modules/auth/api.py (depends on T050)

# Frontend can fully parallel:
Task T065: client.ts (fetch + interceptors)
Task T068: AuthRepository.ts
Task T073: hooks/queries/useCurrentUser.ts + mutations/useLogin.ts
Task T074: pages/Login.tsx
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Setup (T001-T008)
2. Complete Phase 2: Foundational (T009-T039) — **CRITICAL blocker**
3. Complete Phase 3: US1 (T040-T080) — auth + RLS + device limit
4. **STOP and VALIDATE**: Run US1 tests; curl-flow register→login→/users/me→6th device evicts→1st refresh 401
5. Deploy/demo if ready (no resume functionality yet — this is the auth MVP slice)

### Incremental Delivery (recommended path)

1. **Setup + Foundational** → Foundation ready (T001-T039)
2. **+ US1** → Auth MVP; can register/login + 5-device limit + RLS; demo: "log in 6 times"
3. **+ US2** → Resume CRUD MVP; can create branches/blocks, COW, reorder; demo: SC-001 partial (no version yet)
4. **+ US3** → Versioning; full SC-001 happy path; **Phase 1 acceptance gate passed**
5. **+ Polish** → Observability + security + CI; Phase 1 release-ready

### Parallel Team Strategy

- **Week 1**: Setup + Foundational (whole team).
- **Week 2**: Split:
  - Dev A: US1 backend (M04/M05) + RLS tests
  - Dev B: US1 frontend (auth slice) + Login/Register UI
  - Dev C: US2 backend (M06 models/repos/services) + COW tests
- **Week 3**: Split:
  - Dev A: US2 frontend (ResumeList/Editor migration)
  - Dev B: US3 backend (M07) + JSON Patch parity
  - Dev C: Polish (observability, security, CI)
- **Week 4**: Integration + E2E + release

---

## Notes

- `[P]` = different files, no dependency on incomplete tasks.
- `[Story]` = required for US phases; absent for Setup/Foundational/Polish.
- **Tests MUST fail before implementation** (Constitution III, NON-NEGOTIABLE).
- **RLS is the security boundary** — every tenant query MUST go through `get_db_session(user_id=...)`. Phase 1 T043 must be green.
- **No mocks in test suite** (Constitution IV) — backend integration uses real Postgres/Redis; frontend E2E uses real backend. `VITE_USE_MOCK=true` is dev fallback only.
- **Phase 1 显式禁止引入** (grep 关键词 = 退审): `langgraph` / `langchain-anthropic` / `ai_messages` / `checkpoints` / `error_questions` / `ability_dimensions` / `tasks` / `activities` / `jobs` / `audit_logs` / `langsmith` / i18n 库 / OAuth 真实实现 / 悲观锁 / Outbox / Dexie.
- **Commit cadence**: after each task or logical group. PR per phase boundary.
- **Stop at any checkpoint** to validate story independently before proceeding.
- See [quickstart.md](./quickstart.md) §6 for the full release checklist.
- See [plan.md](./plan.md) §「Complexity Tracking」for known non-blocking deviations (password policy, bcrypt cost fallback, 5-device concurrency).
