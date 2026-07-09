#!/usr/bin/env bash
# dev-up.sh — boot the local dev stack.
#
# - Backend runs on :8000 via `uv run uvicorn`.
# - Frontend runs on :5173 via `npm run dev`.
# - Postgres is NOT started locally (T008b-blocked; user provides DATABASE_URL).
# - Redis must be running on localhost:6379.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

printf '\n\033[0;33m==> InterCraft dev stack\033[0m\n'
printf '  Redis expected at localhost:6379\n'
if ! command -v redis-cli >/dev/null 2>&1; then
  printf '  \033[0;31m! redis-cli not found; please install Redis 7+ and start it\033[0m\n'
fi

# Kill orphaned processes on ports 5173 (Vite) and 8000 (uvicorn) to prevent
# zombie services from competing for CPU / filesystem access.
for PORT in 5173 8000; do
  PID=$(netstat -ano | grep ":$PORT " | grep LISTENING | awk '{print $NF}' | head -1)
  if [ -n "$PID" ] && [ "$PID" -gt 0 ] 2>/dev/null; then
    printf '  \033[0;33m> Port %s in use by PID %s — killing\033[0m\n' "$PORT" "$PID"
    taskkill //F //PID "$PID" 2>/dev/null || true
    sleep 1
  fi
done

# Sync backend deps (uv.lock pinned)
printf '\n\033[0;33m==> uv sync (backend)\033[0m\n'
(cd "$ROOT/backend" && uv sync --extra dev)

# Sync frontend deps (package-lock.json pinned)
if [ -f "$ROOT/package.json" ]; then
  printf '\n\033[0;33m==> npm install (frontend)\033[0m\n'
  (cd "$ROOT" && npm install --no-audit --no-fund)
fi

# Backend migrations (only if a real DATABASE_URL is set)
if [[ "${DATABASE_URL:-}" != "postgresql+asyncpg://PLACEHOLDER"* && -n "${DATABASE_URL:-}" ]]; then
  printf '\n\033[0;33m==> Running migrations\033[0m\n'
  (cd "$ROOT/backend" && uv run alembic upgrade head)
else
  printf '\n\033[0;33m==> DATABASE_URL is placeholder; skipping migrations (T008b)\033[0m\n'
fi

# OpenAPI types (best-effort)
if command -v npm >/dev/null 2>&1 && [ -d "$ROOT/node_modules" ]; then
  printf '\n\033[0;33m==> Generating API types\033[0m\n'
  (cd "$ROOT" && npm run gen:api || true)
fi

# Start backend + frontend in parallel
printf '\n\033[0;33m==> Starting backend (uvicorn) and frontend (vite)\033[0m\n'
(cd "$ROOT/backend" && uv run uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!
(cd "$ROOT" && npm run dev) &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' EXIT
wait
