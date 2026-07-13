#!/usr/bin/env bash
# Delegate stop semantics to dev-up.sh so PID mapping, fingerprint checks,
# bounded rechecks, and manifest retention have one implementation.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd -P)"
STOP_ONLY=0

case "${1:-}" in
  "") ;;
  --stop-only) STOP_ONLY=1 ;;
  -h|--help)
    printf 'Usage: bash scripts/dev-restart.sh [--stop-only]\n'
    exit 0
    ;;
  *)
    printf 'Usage: bash scripts/dev-restart.sh [--stop-only]\n' >&2
    exit 1
    ;;
esac
[ "$#" -le 1 ] || exit 1

if ! bash "$ROOT/scripts/dev-up.sh" --stop-only; then
  printf '[dev-restart] stop failed; manifest retained and restart aborted\n' >&2
  exit 2
fi
if [ "$STOP_ONLY" = "1" ]; then
  exit 0
fi
exec bash "$ROOT/scripts/dev-up.sh"
