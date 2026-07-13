# InterCraft Backend

FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 15 + Redis 7 backend for InterCraft.

## Quick start

```bash
# Install deps (uv required)
uv sync --extra dev

# Configure env
cp ../.env.example .env
# Edit .env with your real DATABASE_URL + JWT_SECRET + MASTER_KEY

# Run migrations (requires reachable Postgres)
uv run alembic upgrade head

# From the repository root, boot Redis/API/worker/Vite together
cd ..
bash scripts/dev-up.sh
# -> API http://localhost:8000, frontend http://localhost:5173

# Containerized equivalent (from backend/)
cd backend
docker compose up
```

Compose fails before launch when `DATABASE_URL`, `JWT_SECRET`, or `MASTER_KEY`
is absent. Its API healthcheck uses full `/readyz` readiness, so the frontend
does not become healthy before Postgres, Redis, and the ARQ worker are ready.
Override published ports with `INTERCRAFT_API_PORT`,
`INTERCRAFT_FRONTEND_PORT`, and `INTERCRAFT_REDIS_PORT` when defaults conflict.
Compose keeps its loopback CORS defaults aligned with the frontend port and
sets the container-only Vite proxy target to `http://api:8000`. Set
`CORS_ALLOWED_ORIGINS` yourself for non-loopback browser origins.

## Modules

| Module | Purpose | README |
|---|---|---|
| M01  | Project skeleton, health, metrics, OpenAPI | [app/main.py](app/main.py) |
| M02  | ORM, Alembic, RLS helpers, mixins | [app/domain/](app/domain/) |
| M03  | Redis client, ARQ worker, crypto | [app/core/](app/core/) |
| M04  | Account / Auth (register, login, JWT) | [app/modules/auth/](app/modules/auth/README.md) |
| M05  | Session / Device / 5-device cap | [app/modules/sessions/](app/modules/sessions/README.md) |
| M06  | Resume branches + blocks | [app/modules/resumes/](app/modules/resumes/README.md) |
| M07  | Versioning (full snapshot + JSON Patch) | [app/modules/versions/](app/modules/versions/README.md) |
| M08  | Abilities (dimensions + history) | [app/modules/abilities/](app/modules/abilities/) |
| M09  | Error Questions (错题管理) | [app/modules/errors/](app/modules/errors/) |
| M10  | Jobs (求职意向追踪) | [app/modules/jobs/](app/modules/jobs/) |
| M11  | Tasks (任务看板) | [app/modules/tasks/](app/modules/tasks/) |
| M12  | Lock Service (悲观锁 + WS) — v0.3.0 | [app/modules/locks/](app/modules/locks/README.md) |
| M13  | Outbox Replay (离线回放) — v0.3.0 | [app/modules/outbox/](app/modules/outbox/README.md) |

## Tests

```bash
uv run pytest -q                 # unit + skipped-when-no-DB integration
uv run pytest --cov=app          # coverage
```

## CLI (Constitution II)

```bash
uv run python -m app.cli.main serve               # boot uvicorn
uv run python -m app.cli.main migrate --action upgrade
uv run python -m app.cli.main seed
uv run python -m app.modules.auth.cli register -e a@b.com -p 'P@ssw0rd'
uv run python -m app.modules.sessions.cli list --user-id <UUID>
uv run python -m app.modules.resumes.cli list   --user-id <UUID> --json
uv run python -m app.modules.versions.cli list  --branch-id <UUID> --user-id <UUID>
```

## Health checks

- `GET /healthz` (root) — dependency-free API process liveness
- `GET /readyz` (root) — bounded Postgres + Redis + fresh ARQ heartbeat
- `GET /metrics` — Prometheus text format
- `GET /api/v1/openapi.json` — full OpenAPI 3.1 schema
- `GET /api/v1/docs` — Swagger UI
- `GET /api/v1/redoc` — ReDoc

## Notes

- `DATABASE_URL` placeholder is blocked by an integration-test guard (T008b).
- A reachable Redis is not enough for derive/analysis readiness: `/readyz`
  returns 503 unless the registered ARQ worker heartbeat is fresh.
- `uv run arq --check app.workers.main.WorkerSettings` checks the same sentinel
  used by `/readyz` and the Compose worker healthcheck.
- `JWT_SECRET` + `MASTER_KEY` are dev-only dummies — rotate before any production use.
- See `specs/001-intercraft-product-spec/` for the full plan, data model, and API contracts.
