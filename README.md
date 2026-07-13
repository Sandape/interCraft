# InterCraft

AI-assisted resume editor + interview simulator. FastAPI + React + Postgres 15 + Redis 7.

## Quickstart (5-minute path)

```bash
# 1. Edit backend/.env with your real DATABASE_URL + JWT_SECRET + MASTER_KEY
#    (the .env.example at repo root is the template; copy it into backend/.env)

# 2. Start Redis (when no reachable local Redis exists), API, ARQ worker,
#    and Vite as one owned lifecycle. Logs and PIDs are under .tmp/intercraft-dev.
bash scripts/dev-up.sh

# 3. Restart only that managed stack; unrelated Python/Node/Redis processes
#    are never selected by port, command line, or executable image.
bash scripts/dev-restart.sh

# 4. Run all available tests
bash scripts/run-all-tests.sh
```

## What You Need First

| Tool | Version | Check |
|---|---|---|
| Python | 3.12.x | `python --version` |
| Node.js | 24.x | `node --version` |
| uv | 0.4.x or newer | `uv --version` |
| Bash on Windows | Git Bash | `D:\Develop\Git\bin\bash.exe --version` |
| Redis | 7+ on localhost:6379 | `redis-cli -p 6379 PING` |
| Postgres | 15 (online or local) | reachable per `DATABASE_URL` |

Docker is optional. `scripts/dev-up.sh` uses a reachable configured Redis or
starts an ephemeral host Redis that it owns; Postgres remains caller-provided.
`cd backend && docker compose up` is the equivalent containerized full stack.

On this Windows workspace, Bash is not added to `PATH`; invoke the scripts
from PowerShell with the exact Git Bash executable:

```powershell
& 'D:\Develop\Git\bin\bash.exe' scripts/dev-up.sh
& 'D:\Develop\Git\bin\bash.exe' scripts/dev-restart.sh
```

The scripts and application both resolve Redis/Postgres through
`backend/.env` and Pydantic `Settings`; the shell file is never sourced.
Host ports can be overridden with `INTERCRAFT_API_PORT`,
`INTERCRAFT_FRONTEND_PORT`, and Compose `INTERCRAFT_REDIS_PORT`. The managed
host launcher validates the port values, points Vite at the matching API port,
and safely adds both loopback frontend origins to CORS. For a non-loopback
browser origin, set `CORS_ALLOWED_ORIGINS` explicitly; a port override alone
cannot infer a public hostname.

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
