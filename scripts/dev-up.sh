#!/usr/bin/env bash
# Start one owned InterCraft local stack: Redis (when needed), API, ARQ worker,
# and Vite. Every native process has a distinct log and verified manifest row.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd -P)"
RUN_ROOT="${INTERCRAFT_RUN_ROOT:-$ROOT/.tmp/intercraft-dev}"
RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')-$$"
RUN_DIR="$RUN_ROOT/runs/$RUN_ID"
CURRENT_DIR="$RUN_ROOT/current"
MANIFEST="$CURRENT_DIR/manifest.tsv"
STARTUP_TIMEOUT_SECONDS="${INTERCRAFT_STARTUP_TIMEOUT_SECONDS:-30}"
STOP_TIMEOUT_SECONDS="${INTERCRAFT_STOP_TIMEOUT_SECONDS:-10}"
FORCE_STOP_TIMEOUT_SECONDS="${INTERCRAFT_FORCE_STOP_TIMEOUT_SECONDS:-2}"
API_PORT="${INTERCRAFT_API_PORT:-8000}"
FRONTEND_PORT="${INTERCRAFT_FRONTEND_PORT:-5173}"
CLEANING_UP=0
STOP_ONLY=0

case "${1:-}" in
  "") ;;
  --stop-only) STOP_ONLY=1 ;;
  -h|--help)
    printf 'Usage: bash scripts/dev-up.sh [--stop-only]\n'
    exit 0
    ;;
  *)
    printf 'Usage: bash scripts/dev-up.sh [--stop-only]\n' >&2
    exit 1
    ;;
esac
[ "$#" -le 1 ] || exit 1

is_windows() {
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

valid_pid() {
  [[ "${1:-}" =~ ^[1-9][0-9]*$ ]]
}

valid_port() {
  [[ "${1:-}" =~ ^[1-9][0-9]*$ ]] && [ "$1" -le 65535 ]
}

shell_pid_alive() {
  valid_pid "$1" && kill -0 "$1" 2>/dev/null
}

msys_pid_to_winpid() {
  local msys_pid="$1" output header data extra winpid
  valid_pid "$msys_pid" || return 1
  output="$(ps -p "$msys_pid" 2>/dev/null)" || return 1
  header="$(printf '%s\n' "$output" | sed -n '1p')"
  data="$(printf '%s\n' "$output" | sed -n '2p')"
  extra="$(printf '%s\n' "$output" | sed -n '3p')"
  [ -n "$header" ] && [ -n "$data" ] && [ -z "$extra" ] || return 1
  set -- $header
  [ "$#" -ge 4 ] && [ "$1" = "PID" ] && [ "$4" = "WINPID" ] || return 1
  set -- $data
  [ "$#" -ge 4 ] && [ "$1" = "$msys_pid" ] || return 1
  winpid="$4"
  valid_pid "$winpid" || return 1
  printf '%s\n' "$winpid"
}

native_pid_for() {
  if is_windows; then
    msys_pid_to_winpid "$1"
  else
    valid_pid "$1" && printf '%s\n' "$1"
  fi
}

resolve_native_pid() {
  local shell_pid="$1" native_pid attempt
  for ((attempt = 1; attempt <= 40; attempt++)); do
    native_pid="$(native_pid_for "$shell_pid" 2>/dev/null || true)"
    if valid_pid "$native_pid"; then
      printf '%s\n' "$native_pid"
      return 0
    fi
    shell_pid_alive "$shell_pid" || return 1
    sleep 0.05
  done
  return 1
}

native_pid_alive() {
  local native_pid="$1" state
  valid_pid "$native_pid" || return 1
  if is_windows; then
    powershell.exe -NoProfile -NonInteractive -Command \
      "if (Get-Process -Id $native_pid -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" \
      >/dev/null 2>&1
  else
    kill -0 "$native_pid" 2>/dev/null || return 1
    state="$(ps -o stat= -p "$native_pid" 2>/dev/null | tr -d ' ')"
    [[ "$state" != Z* ]]
  fi
}

process_fingerprint() {
  local native_pid="$1"
  valid_pid "$native_pid" || return 1
  if is_windows; then
    powershell.exe -NoProfile -NonInteractive -Command \
      "(Get-Process -Id $native_pid -ErrorAction Stop).StartTime.ToUniversalTime().Ticks" \
      2>/dev/null | tr -d '\r\n'
  elif [ -r "/proc/$native_pid/stat" ]; then
    awk '{print $22}' "/proc/$native_pid/stat"
  else
    ps -o lstart= -p "$native_pid" 2>/dev/null | tr -s ' ' | sed 's/^ //;s/ $//'
  fi
}

owned_process_matches() {
  local shell_pid="$1" native_pid="$2" expected="$3" current mapped
  valid_pid "$shell_pid" && valid_pid "$native_pid" && [ -n "$expected" ] || return 1
  native_pid_alive "$native_pid" || return 1
  if is_windows; then
    mapped="$(msys_pid_to_winpid "$shell_pid" 2>/dev/null || true)"
    [ "$mapped" = "$native_pid" ] || return 1
  fi
  current="$(process_fingerprint "$native_pid" 2>/dev/null || true)"
  [ -n "$current" ] && [ "$current" = "$expected" ]
}

terminate_native_tree() {
  local native_pid="$1" force="${2:-0}" child
  if is_windows; then
    if [ "$force" = "1" ]; then
      taskkill //T //F //PID "$native_pid" >/dev/null 2>&1 || true
    else
      taskkill //T //PID "$native_pid" >/dev/null 2>&1 || true
    fi
    return 0
  fi
  if command -v pgrep >/dev/null 2>&1; then
    while IFS= read -r child; do
      [ -n "$child" ] && terminate_native_tree "$child" "$force"
    done < <(pgrep -P "$native_pid" 2>/dev/null || true)
  fi
  if [ "$force" = "1" ]; then
    kill -KILL "$native_pid" 2>/dev/null || true
  else
    kill -TERM "$native_pid" 2>/dev/null || true
  fi
}

wait_native_gone() {
  local native_pid="$1" timeout="$2" deadline
  deadline=$((SECONDS + timeout))
  while native_pid_alive "$native_pid" && [ "$SECONDS" -lt "$deadline" ]; do
    sleep 0.1
  done
  ! native_pid_alive "$native_pid"
}

stop_verified_process() {
  local shell_pid="$1" native_pid="$2" fingerprint="$3"
  owned_process_matches "$shell_pid" "$native_pid" "$fingerprint" || return 2
  terminate_native_tree "$native_pid" 0
  if wait_native_gone "$native_pid" "$STOP_TIMEOUT_SECONDS"; then
    return 0
  fi
  printf '[dev-up] force stopping owned native_pid=%s after %ss\n' \
    "$native_pid" "$STOP_TIMEOUT_SECONDS" >&2
  terminate_native_tree "$native_pid" 1
  wait_native_gone "$native_pid" "$FORCE_STOP_TIMEOUT_SECONDS"
}

stop_unrecorded_process() {
  local shell_pid="$1" native_pid="${2:-}"
  if valid_pid "$native_pid" && native_pid_alive "$native_pid"; then
    terminate_native_tree "$native_pid" 1
    wait_native_gone "$native_pid" "$FORCE_STOP_TIMEOUT_SECONDS"
    return
  fi
  if shell_pid_alive "$shell_pid"; then
    kill -KILL "$shell_pid" 2>/dev/null || true
  fi
  # Without a native mapping, MSYS kill-0 becoming false does not prove that
  # the Windows process ended. Force the caller to retain UNVERIFIED evidence.
  return 1
}

cleanup() {
  [ "$CLEANING_UP" = "1" ] && return 0
  CLEANING_UP=1
  local format="" service pid c3 c4 c5 c6 native_pid owned log_file fingerprint
  local stop_failure=0 result
  [ -f "$MANIFEST" ] || return 0
  while IFS=$'\t' read -r service pid c3 c4 c5 c6; do
    c5="${c5%$'\r'}"
    c6="${c6%$'\r'}"
    if [ "$service" = "service" ]; then
      if [ "$c3" = "native_pid" ]; then
        format="native"
      elif [ "$c3" = "owned" ]; then
        format="legacy"
      else
        stop_failure=1
      fi
      continue
    fi
    if [ "$format" = "native" ]; then
      native_pid="$c3"; owned="$c4"; log_file="$c5"; fingerprint="$c6"
    elif [ "$format" = "legacy" ]; then
      owned="$c3"; log_file="$c4"; fingerprint="$c5"
      native_pid="$(native_pid_for "$pid" 2>/dev/null || true)"
    else
      stop_failure=1
      continue
    fi
    [ "$owned" = "1" ] || continue
    if [ "$fingerprint" = "UNVERIFIED" ]; then
      printf '[dev-up] UNVERIFIED ownership evidence retained: service=%s shell_pid=%s native_pid=%s\n' \
        "$service" "$pid" "$native_pid" >&2
      stop_failure=1
      continue
    fi
    if ! valid_pid "$native_pid"; then
      if shell_pid_alive "$pid"; then
        printf '[dev-up] cannot resolve owned service=%s shell_pid=%s\n' "$service" "$pid" >&2
        stop_failure=1
      fi
      continue
    fi
    native_pid_alive "$native_pid" || continue
    printf '[dev-up] stopping owned service=%s shell_pid=%s native_pid=%s log=%s\n' \
      "$service" "$pid" "$native_pid" "$log_file"
    if stop_verified_process "$pid" "$native_pid" "$fingerprint"; then
      continue
    else
      result=$?
    fi
    if [ "$result" = "2" ]; then
      printf '[dev-up] refusing stale/reused native_pid=%s service=%s\n' \
        "$native_pid" "$service" >&2
    else
      printf '[dev-up] owned native_pid=%s survived TERM and KILL\n' "$native_pid" >&2
    fi
    stop_failure=1
  done < "$MANIFEST"
  if [ "$stop_failure" = "1" ]; then
    printf '[dev-up] cleanup incomplete; manifest retained at %s\n' "$MANIFEST" >&2
    return 1
  fi
  rm -f "$MANIFEST"
}

on_exit() {
  local status="$1"
  trap - EXIT INT TERM
  if ! cleanup; then
    exit 4
  fi
  exit "$status"
}

fail_if_active_run_exists() {
  [ -f "$MANIFEST" ] || return 0
  local format="" service pid c3 c4 c5 c6 native_pid owned fingerprint active=0
  while IFS=$'\t' read -r service pid c3 c4 c5 c6; do
    c5="${c5%$'\r'}"
    c6="${c6%$'\r'}"
    if [ "$service" = "service" ]; then
      [ "$c3" = "native_pid" ] && format="native"
      [ "$c3" = "owned" ] && format="legacy"
      continue
    fi
    if [ "$format" = "native" ]; then
      native_pid="$c3"; owned="$c4"; fingerprint="$c6"
    elif [ "$format" = "legacy" ]; then
      owned="$c3"; fingerprint="$c5"
      native_pid="$(native_pid_for "$pid" 2>/dev/null || true)"
    else
      active=1
      continue
    fi
    [ "$owned" = "1" ] || continue
    if [ "$fingerprint" = "UNVERIFIED" ]; then
      printf '[dev-up] UNVERIFIED ownership evidence blocks startup: service=%s shell_pid=%s\n' \
        "$service" "$pid" >&2
      active=1
      continue
    fi
    if ! valid_pid "$native_pid"; then
      if shell_pid_alive "$pid"; then
        printf '[dev-up] unresolved live owned shell_pid=%s blocks startup: service=%s\n' \
          "$pid" "$service" >&2
      else
        printf '[dev-up] invalid native PID evidence blocks startup: service=%s\n' \
          "$service" >&2
      fi
      active=1
      continue
    fi
    if valid_pid "$native_pid" && native_pid_alive "$native_pid"; then
      if owned_process_matches "$pid" "$native_pid" "$fingerprint"; then
        printf '[dev-up] active managed service exists: %s native_pid=%s\n' \
          "$service" "$native_pid" >&2
      else
        printf '[dev-up] stale/reused PID evidence requires manual review: service=%s\n' \
          "$service" >&2
      fi
      active=1
    fi
  done < "$MANIFEST"
  [ "$active" = "0" ] || return 2
  rm -f "$MANIFEST"
}

record_service() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" >> "$MANIFEST"
}

start_service() {
  local service="$1" workdir="$2" log_file="$3" native_pid fingerprint
  shift 3
  (
    cd "$workdir"
    exec "$@"
  ) >"$log_file" 2>&1 &
  SERVICE_PID=$!
  native_pid="$(resolve_native_pid "$SERVICE_PID" 2>/dev/null || true)"
  if ! valid_pid "$native_pid"; then
    printf '[dev-up] failed to resolve native PID for service=%s shell_pid=%s\n' \
      "$service" "$SERVICE_PID" >&2
    if ! stop_unrecorded_process "$SERVICE_PID" ""; then
      record_service "$service" "$SERVICE_PID" 0 1 "$log_file" UNVERIFIED || true
      printf '[dev-up] unverified ownership evidence retained in manifest\n' >&2
    fi
    return 1
  fi
  fingerprint="$(process_fingerprint "$native_pid" 2>/dev/null || true)"
  if [ -z "$fingerprint" ]; then
    printf '[dev-up] failed to fingerprint service=%s native_pid=%s\n' \
      "$service" "$native_pid" >&2
    if ! stop_unrecorded_process "$SERVICE_PID" "$native_pid"; then
      record_service "$service" "$SERVICE_PID" "$native_pid" 1 "$log_file" UNVERIFIED || true
      printf '[dev-up] unverified ownership evidence retained in manifest\n' >&2
    fi
    return 1
  fi
  if ! record_service "$service" "$SERVICE_PID" "$native_pid" 1 "$log_file" "$fingerprint"; then
    stop_unrecorded_process "$SERVICE_PID" "$native_pid" || true
    return 1
  fi
  SERVICE_NATIVE_PID="$native_pid"
  printf '[dev-up] started service=%s shell_pid=%s native_pid=%s log=%s\n' \
    "$service" "$SERVICE_PID" "$SERVICE_NATIVE_PID" "$log_file"
}

wait_until() {
  local label="$1"
  shift
  local deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
  until "$@" >/dev/null 2>&1; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      printf '[dev-up] timed out waiting for %s after %ss\n' "$label" "$STARTUP_TIMEOUT_SECONDS" >&2
      return 1
    fi
    sleep 0.25
  done
}

redis_ready() {
  (
    cd "$ROOT/backend"
    uv run python -c 'import asyncio; from app.core.redis import redis_ping; raise SystemExit(0 if asyncio.run(redis_ping()) else 1)'
  ) >/dev/null 2>&1
}

settings_local_redis_port() {
  (
    cd "$ROOT/backend"
    uv run python -c 'from urllib.parse import urlparse; from app.core.config import get_settings; u=urlparse(get_settings().redis_url); ok=u.scheme=="redis" and u.hostname in {"127.0.0.1","localhost","::1"} and not u.username and not u.password; print(u.port or 6379) if ok else None; raise SystemExit(0 if ok else 1)'
  )
}

settings_database_configured() {
  (
    cd "$ROOT/backend"
    uv run python -c 'from app.core.config import get_settings; u=get_settings().database_url; raise SystemExit(0 if u and "PLACEHOLDER" not in u else 1)'
  ) >/dev/null 2>&1
}

settings_effective_cors_origins() {
  (
    cd "$ROOT/backend"
    uv run python -c '
import sys
from urllib.parse import urlsplit

from app.core.config import get_settings

port = int(sys.argv[1])
origins = [origin.rstrip("/") for origin in get_settings().cors_origins_list()]
origins.extend((f"http://localhost:{port}", f"http://127.0.0.1:{port}"))
origins = list(dict.fromkeys(origins))
for origin in origins:
    parsed = urlsplit(origin)
    valid = (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and parsed.path == ""
        and not parsed.query
        and not parsed.fragment
        and not any(ord(char) < 32 for char in origin)
    )
    if not valid:
        raise SystemExit(f"invalid CORS origin in Settings: {origin!r}")
print(",".join(origins))
' "$1"
  )
}

worker_ready() {
  (cd "$ROOT/backend" && uv run arq --check app.workers.main.WorkerSettings)
}

api_ready() {
  curl --fail --silent --show-error "http://127.0.0.1:$API_PORT/healthz" >/dev/null
}

full_stack_ready() {
  curl --fail --silent --show-error "http://127.0.0.1:$API_PORT/readyz" >/dev/null
}

frontend_ready() {
  curl --fail --silent --show-error "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null
}

if [ "$STOP_ONLY" = "1" ]; then
  cleanup
  exit 0
fi

for command in uv npm curl; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf '[dev-up] required command is missing: %s\n' "$command" >&2
    exit 1
  fi
done
if ! valid_port "$API_PORT" || ! valid_port "$FRONTEND_PORT"; then
  printf '[dev-up] INTERCRAFT_API_PORT/INTERCRAFT_FRONTEND_PORT must be 1..65535\n' >&2
  exit 1
fi

mkdir -p "$RUN_DIR" "$CURRENT_DIR"
fail_if_active_run_exists
printf 'service\tpid\tnative_pid\towned\tlog\tstart_fingerprint\n' > "$MANIFEST"
trap 'exit 130' INT TERM
trap 'on_exit $?' EXIT

printf '[dev-up] run_id=%s run_dir=%s\n' "$RUN_ID" "$RUN_DIR"
if [ "${INTERCRAFT_SKIP_INSTALL:-0}" != "1" ]; then
  (cd "$ROOT/backend" && uv sync --locked --extra dev)
  if [ ! -d "$ROOT/node_modules" ]; then
    (cd "$ROOT" && npm ci --no-audit --no-fund)
  fi
fi

if ! redis_ready; then
  LOCAL_REDIS_PORT="$(settings_local_redis_port 2>/dev/null || true)"
  if ! valid_port "$LOCAL_REDIS_PORT"; then
    printf '[dev-up] configured Redis is unreachable; refusing to replace remote/authenticated Redis\n' >&2
    exit 1
  fi
  if ! command -v redis-server >/dev/null 2>&1; then
    printf '[dev-up] Redis is unreachable and redis-server is not installed\n' >&2
    exit 1
  fi
  start_service redis "$ROOT" "$RUN_DIR/redis.log" \
    redis-server --save "" --appendonly no --port "$LOCAL_REDIS_PORT"
  wait_until Redis redis_ready
else
  record_service redis 0 0 0 external -
  printf '[dev-up] using reachable external Redis (not owned; it will not be stopped)\n'
fi

if settings_database_configured; then
  (cd "$ROOT/backend" && uv run alembic upgrade head)
else
  printf '[dev-up] Settings reports missing/placeholder DATABASE_URL; full stack cannot start\n' >&2
  exit 1
fi

EFFECTIVE_CORS_ALLOWED_ORIGINS="$(settings_effective_cors_origins "$FRONTEND_PORT")"
export CORS_ALLOWED_ORIGINS="$EFFECTIVE_CORS_ALLOWED_ORIGINS"

start_service api "$ROOT/backend" "$RUN_DIR/api.log" \
  uv run uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT"
API_PID="$SERVICE_PID"; API_NATIVE_PID="$SERVICE_NATIVE_PID"
start_service worker "$ROOT/backend" "$RUN_DIR/worker.log" \
  uv run arq app.workers.main.WorkerSettings
WORKER_PID="$SERVICE_PID"; WORKER_NATIVE_PID="$SERVICE_NATIVE_PID"
start_service frontend "$ROOT" "$RUN_DIR/frontend.log" \
  env "VITE_API_TARGET=http://127.0.0.1:$API_PORT" \
  npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
FRONTEND_PID="$SERVICE_PID"; FRONTEND_NATIVE_PID="$SERVICE_NATIVE_PID"

wait_until API api_ready
wait_until ARQ-worker worker_ready
wait_until full-stack-readiness full_stack_ready
wait_until Vite frontend_ready
printf '[dev-up] ready api=http://127.0.0.1:%s frontend=http://127.0.0.1:%s\n' \
  "$API_PORT" "$FRONTEND_PORT"

while native_pid_alive "$API_NATIVE_PID" && \
  native_pid_alive "$WORKER_NATIVE_PID" && \
  native_pid_alive "$FRONTEND_NATIVE_PID"; do
  sleep 1
done
printf '[dev-up] a managed service exited; see logs under %s\n' "$RUN_DIR" >&2
exit 1
