# InterCraft Backend

FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 15 + Redis 7 backend for InterCraft.

## Quick start

```bash
# Install deps (uv required)
uv sync --extra dev

# Configure env
cp .env.example .env
# Edit .env with your real DATABASE_URL + JWT_SECRET + MASTER_KEY

# Run migrations (requires reachable Postgres)
uv run alembic upgrade head

# Boot the API
uv run uvicorn app.main:app --reload
# -> http://localhost:8000/docs

# Boot the ARQ worker (separate terminal)
uv run arq app.workers.main.WorkerSettings
```

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

- `GET /healthz` (root) — overall status with `db` + `redis` probes
- `GET /metrics` — Prometheus text format
- `GET /api/v1/openapi.json` — full OpenAPI 3.1 schema
- `GET /api/v1/docs` — Swagger UI
- `GET /api/v1/redoc` — ReDoc

## Notes

- `DATABASE_URL` placeholder is blocked by an integration-test guard (T008b).
- `JWT_SECRET` + `MASTER_KEY` are dev-only dummies — rotate before any production use.
- See `specs/001-intercraft-product-spec/` for the full plan, data model, and API contracts.
