# Testing Guide

This file is the canonical testing entry point. Requirement behavior is defined
in `specs/`; this guide only describes where tests live and how to run them.

## Commands

| Purpose | Command |
|---|---|
| Frontend unit tests | `npm run test` |
| Frontend type check | `npm run typecheck` |
| Frontend build | `npm run build` |
| Canonical E2E tests | `npm run e2e` |
| List canonical E2E tests | `npm run e2e -- --list` |
| Backend tests | `cd backend && uv run pytest -q` |
| Backend contract tests | `cd backend && uv run pytest tests/contract -q` |
| Worker readiness unit gate | `cd backend && uv run pytest tests/unit/test_worker_readiness.py -q` |
| Real worker lifecycle gate | See the isolated-Redis command below |

## Worker Readiness Gate

The PR CI job `worker-readiness` starts an ephemeral Redis 7 service, observes
multiple real ARQ heartbeats, consumes the registered no-cost `ping` job, and
verifies graceful removal plus abrupt-loss expiry of the sentinel. It uploads
JUnit, pytest output, and test-produced owned PID/fingerprint before/after
evidence even when the gate fails. The evidence intentionally excludes global
process command lines and unrelated runner arguments.
The same gate boots the real Vite configuration against FastAPI and requests
`/api/v1/openapi.json` through the frontend origin, catching a container/host
proxy target that points back at the frontend itself.

The integration test fails closed against arbitrary Redis instances. It never
uses `FLUSHDB`: all queue, heartbeat, and job IDs are unique and cleanup names
only those keys. To run it locally, provide a loopback, non-default Redis DB
that you explicitly own for the test:

```bash
cd backend
INTERCRAFT_TEST_REDIS_URL=redis://127.0.0.1:6379/15 \
INTERCRAFT_TEST_REDIS_OWNED=1 \
REDIS_URL=redis://127.0.0.1:6379/15 \
DATABASE_URL=postgresql+asyncpg://test:test@127.0.0.1:1/worker_readiness \
uv run pytest tests/integration/test_worker_lifecycle.py -q
```

The unreachable loopback `DATABASE_URL` is only used to bypass the repository's
directory-wide placeholder skip guard; this worker lifecycle file never opens
a PostgreSQL connection.

Do not point these variables at a shared development, staging, or production
Redis. When an isolated Redis is unavailable, run/collect the unit gate and
let the CI service execute the real lifecycle lane.

## Local MCP Setup

The tracked `.mcp.json` is a shareable project topology file. It must contain
server commands and environment-variable references only — never database
passwords, tokens, cookies, or complete credential-bearing connection strings.

Set the test database URL outside the repository before starting Claude Code.
Claude Code supports this environment-variable expansion in its
[MCP configuration](https://code.claude.com/docs/en/mcp). For example, in
PowerShell:

```powershell
$env:INTERCRAFT_TEST_DATABASE_URL = 'postgresql://<user>:<password>@<host>:<port>/<database>'
claude mcp list
```

Claude Code expands `${INTERCRAFT_TEST_DATABASE_URL}` when it starts the
project-scoped PostgreSQL MCP server. `claude mcp list` must report `postgres`
as connected after the project MCP configuration is approved and before a
database-backed acceptance run begins. If the variable is absent, treat
PostgreSQL evidence lanes as blocked; do not replace MCP evidence with copied
SQL output or application logs.

Use a test-only database and synthetic tenant/user identifiers. Never paste a
real connection string into Git, an Issue, a PR, screenshots, evidence, or
agent prompts. If a credential is ever committed, remove the literal value and
rotate/revoke it; deleting it from the current tree does not remove it from Git
history.

## Test Roots

| Root | Status | Purpose |
|---|---|---|
| `tests/e2e/` | canonical | Playwright E2E specs. Add new E2E tests here. |
| `src/**/*.test.ts(x)` | canonical | Frontend component, hook, repository, and utility tests. |
| `tests/unit/` | canonical | Frontend unit tests that are not colocated. |
| `backend/tests/` | canonical | Backend unit, integration, and contract tests. |

## E2E Policy

- The root `playwright.config.ts` points to `tests/e2e`.
- Keep feature E2E specs near the feature name, for example
  `tests/e2e/019-cross-module-linking.spec.ts`.
- Use `tests/e2e/fixtures/` or `tests/e2e/_fixtures/` for test assets.

## Current Round-1 Material

`docs/testing/round-1/` is retained because the active `020` feature uses its
defect catalog and summary as implementation evidence. Do not treat it as a
general historical reports folder; it is tied to the current fix workflow.

## Evidence Policy

- Generated screenshots, traces, logs, and manual verification records belong in
  `docs/evidence/` or a feature-specific evidence directory.
- Evidence proves behavior; it does not define requirements. Link evidence from
  requirement status tables when a requirement is marked `done`.

## Fresh-DB Checkpointer Contract (REQ-081)

The independent `checkpointer-fresh-db` CI job provisions a real
PostgreSQL 16 service and exercises the shipped
`build_checkpointer_connection_kwargs` builder against a truly empty
catalog. The contract must run end-to-end with zero skipped tests —
any skip means the env guard regressed.

| Field | Value |
|---|---|
| Test file | `backend/tests/integration/test_checkpointer_fresh_database.py` |
| CI job | `.github/workflows/ci.yml` → `checkpointer-fresh-db` |
| Service | `postgres:16-alpine` (independent, not shared) |
| Opt-in env var | `INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_URL` |
| Ownership marker | `INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_OWNED=1` |
| Repository-wide placeholder skip | bypassed by setting the env var |

The module refuses to run without both the URL and the explicit ownership
marker. It accepts only `checkpointer_fresh` or a unique database name
beginning `checkpointer_fresh_`. Before any mutation it reads the catalog
and fails if any `checkpoint_*` table exists; it never pre-cleans a dirty
catalog. Teardown drops only the contract-created tables after a successful
run. The JUnit step asserts `tests == 2` and `skipped == 0`.

To reproduce locally against your own throwaway Postgres (never
point this at a shared dev / staging / production instance):

```bash
cd backend
INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_URL=postgresql+asyncpg://USER:PASSWORD@127.0.0.1:5432/checkpointer_fresh \
INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_OWNED=1 \
DATABASE_URL="$INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_URL" \
JWT_SECRET="ci-only-dummy-secret-that-is-more-than-32-bytes-long!!" \
  uv run pytest tests/integration/test_checkpointer_fresh_database.py -v
```

The contract exercises both production code paths:

1. `app.agents.checkpointer.get_checkpointer()` — the shared singleton.
2. `app.agents.checkpointer_pool.get_checkpointer_pool(user_id)` —
   one randomly hashed shard.

Both init paths must complete `setup()` (with the latest migration —
`ALTER TABLE checkpoint_writes ADD COLUMN task_path`), create the
expected `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` /
`checkpoint_migrations` tables and the three `*_thread_id_idx`
indexes, and survive a minimal real `aput` → `aget_tuple` round trip.

Do not paste a real connection string into Git, an Issue, a PR,
screenshots, evidence, or agent prompts. Only synthetic test-owned
URLs with test-only credentials are allowed.

## CI Eval Gate Path Filter (REQ-033 US5)

Per FR-018 / FR-021 / US5 acceptance scenario 3, only prompt-adjacent,
rubric-adjacent, agent-node, eval-runner, and golden-case changes trigger
the golden-case eval as a PR merge gate. Non-prompt-adjacent PRs MUST NOT
be required to run the expensive eval suite as a merge gate.

The path filter is encoded in
[`.github/workflows/033-eval-gate.yml`](../../.github/workflows/033-eval-gate.yml):

| Path filter                            | Why it triggers eval                                            |
|----------------------------------------|-----------------------------------------------------------------|
| `backend/app/agents/**`                | Agent graph + node code; prompt templates; LLM call shapes.      |
| `backend/app/eval/**`                  | Eval runner / checker / golden loader / report rendering.       |
| `backend/app/modules/telemetry_contracts/**` | Version context + redaction policy — feeds dashboard metrics. |
| `.github/workflows/033-eval-gate.yml`  | The workflow itself, so changes to the gate re-verify the gate. |

Why this filter rather than "run on every PR":

- The golden-case eval can take 30s–2min depending on case count. Running
  it on every PR — including pure frontend / docs / infra PRs — adds
  CI cost without buying regression coverage.
- Only changes that can affect prompt behavior, rubric scoring, or
  agent node execution can introduce a regression that the golden-case
  suite would catch.
- Doc-only / dependency-only / config-only PRs are still validated by
  the canonical unit + contract test suites that run in the default
  `.github/workflows/ci.yml`.

When to manually trigger the full eval suite outside the path filter:

- A release-candidate promotion where you want to confirm no regression
  has slipped through from an unrelated change.
- A baseline refresh that requires dual approval (FR-024) — the gate
  must pass before the baseline is updated.
- After a LangSmith dataset schema change (US6 follow-up), since the
  gate report's `dataset` field includes the schema version.

Manual trigger from CLI (matches the workflow):

```bash
cd backend
uv run python -m app.eval.cli run \
  --suite golden \
  --env ci \
  --source-revision "$(git rev-parse --short HEAD)" \
  --branch "$(git rev-parse --abbrev-ref HEAD)" \
  --report-out docs/evidence/run-$(date +%Y%m%d-%H%M%S)/eval-report.json \
  --markdown-out docs/evidence/run-$(date +%Y%m%d-%H%M%S)/eval-report.md \
  --json
```

Exit code contract (per
[`specs/033-eval-pm-dashboard/contracts/eval-langsmith-cli.md`](../../specs/033-eval-pm-dashboard/contracts/eval-langsmith-cli.md)):

| Exit | Meaning                                                                |
|-----:|------------------------------------------------------------------------|
| 0    | All active golden cases pass.                                          |
| 4    | Deterministic prompt-adjacent failure — block PR.                      |
| 1    | Operational failure (nightly budget exhausted, etc.).                  |
| 3    | Policy violation — only relevant to `override-record` (FR-024).        |
| 2    | Invalid arguments — surface a bug in the workflow.                     |

Override flow when the gate blocks a hotfix (FR-024 / dual approval):

```bash
cd backend
uv run python -m app.eval.cli override-record \
  --run-id <run-id> \
  --gate pr_eval \
  --pm-approver <name> \
  --technical-approver <name> \
  --reason "<short reason>" \
  --evidence <path-or-url> \
  --json
```

Both the PM business owner AND the technical owner are required. A
single-signature record hard-fails with exit 3 (see
`app.eval.export_policy.PolicyViolation`).
