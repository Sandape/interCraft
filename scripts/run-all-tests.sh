#!/usr/bin/env bash
# run-all-tests.sh — runs the full test matrix: pytest, vitest, playwright.
#
# Kept for compatibility with tasks.md / spec references that name this file.
# Delegates to scripts/ci-test.sh which implements all three runners with
# graceful skipping when infrastructure (Docker, real Postgres) is unavailable.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/ci-test.sh" "$@"