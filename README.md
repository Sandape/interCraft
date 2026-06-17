# InterCraft

AI-assisted resume editor + interview simulator. FastAPI + React + Postgres 15 + Redis 7.

## Quickstart (5-minute path)

```bash
# 1. Install all deps (uses uv for backend, npm for frontend)
bash scripts/dev-up.sh

# 2. Edit backend/.env with your real DATABASE_URL + JWT_SECRET + MASTER_KEY
#    (the .env.example at repo root is the template; copy it into backend/.env)

# 3. Run all available tests
bash scripts/run-all-tests.sh

# 4. (Optional) Boot the full stack in two terminals
#    Terminal A: cd backend && uv run uvicorn app.main:app --reload
#    Terminal B: cd backend && uv run arq app.workers.main.WorkerSettings
#    Terminal C: npm run dev   # frontend on http://localhost:5173
```

## What You Need First

| Tool | Version | Check |
|---|---|---|
| Python | 3.12.x | `python --version` |
| Node.js | 20.x or 22.x | `node --version` |
| uv | 0.4.x or newer | `uv --version` |
| Redis | 7+ on localhost:6379 | `redis-cli -p 6379 PING` |
| Postgres | 15 (online or local) | reachable per `DATABASE_URL` |

Docker is **not** required. The local dev path uses your host Redis and a
user-provided online Postgres.

## Layout

```text
.
|- backend/    FastAPI + SQLAlchemy 2.0 + Alembic + ARQ
|- src/        React + Vite + TanStack Query + Zustand
|- scripts/    dev-up.sh, run-all-tests.sh, gen-api.mjs
|- specs/      Canonical requirements, contracts, and tasks
`- docs/       Testing, evidence, architecture, and decisions
```

## More Docs

- [Documentation index](docs/README.md) - testing, evidence, architecture, and decisions
- [Specs index](specs/README.md) - canonical requirements status and active feature entry
- [Backend README](backend/README.md) - module map, CLI, health endpoints
- [Evidence guide](docs/evidence/README.md) - where to put new verification artifacts

## License

Internal - not for redistribution.
