# Admin Observability CLI Contract

Primary module namespace: `python -m app.modules.agent_observability.cli`

Admin console helpers may live under `python -m app.modules.admin_console.cli`.
All commands must support `--json` for machine-readable CI output.

## `coverage-report`

Reports which production Agent/LLM flows are covered by centralized
instrumentation and which remain gaps.

```bash
cd backend
uv run python -m app.modules.agent_observability.cli coverage-report \
  --env production \
  --out docs/evidence/035-admin-dashboard-mvp/coverage-report.json \
  --json
```

Exit codes:

| Exit | Meaning |
|---:|---|
| 0 | Report generated; no high-severity unaccepted gaps. |
| 4 | High-severity unaccepted coverage gap exists. |
| 2 | Invalid arguments. |
| 1 | Operational failure. |

Required JSON fields:

```json
{
  "generated_at": "2026-06-29T12:00:00Z",
  "covered_count": 5,
  "gap_count": 1,
  "high_severity_gap_count": 0,
  "gaps": []
}
```

## `retention-purge`

Applies retention policy:

- PM metrics: 180 days.
- Redacted traces/spans: 60 days.
- Masked raw payloads: 14 days.

```bash
cd backend
uv run python -m app.modules.agent_observability.cli retention-purge \
  --env production \
  --dry-run \
  --json
```

Exit codes:

| Exit | Meaning |
|---:|---|
| 0 | Purge completed or dry run completed. |
| 3 | Policy violation, for example would retain expired masked raw. |
| 2 | Invalid arguments. |
| 1 | Operational failure. |

## `privacy-audit`

Validates payload/cURL redaction and masked raw access audit.

```bash
cd backend
uv run python -m app.modules.agent_observability.cli privacy-audit \
  --env production \
  --sample-size 50 \
  --out docs/evidence/035-admin-dashboard-mvp/privacy-audit.json \
  --json
```

Checks:

- Default production node/LLM views expose no raw business text.
- cURL views contain no real secrets.
- Masked raw reveal has actor, reason, target id, visibility mode, timestamp.
- Expired masked raw payloads are inaccessible.

## `dashboard-snapshot`

Generates the same privacy-safe snapshot exposed by the admin API.

```bash
cd backend
uv run python -m app.modules.admin_console.cli dashboard-snapshot \
  --date-from 2026-06-01 \
  --date-to 2026-06-29 \
  --environment production \
  --format markdown \
  --out docs/evidence/035-admin-dashboard-mvp/dashboard-snapshot.md \
  --json
```

Exit codes:

| Exit | Meaning |
|---:|---|
| 0 | Snapshot generated and privacy status is safe. |
| 3 | Snapshot privacy validation failed. |
| 2 | Invalid arguments. |
| 1 | Operational failure. |

## `seed-strong-debug-demo`

Creates deterministic local/staging seed data for quickstart validation:

- One admin with PM dashboard capability.
- One developer/reviewer with masked raw capability.
- One successful trace.
- One failed trace with node I/O, LLM call, eval failure, and badcase link.
- One expired masked raw payload for retention validation.

```bash
cd backend
uv run python -m app.modules.agent_observability.cli seed-strong-debug-demo \
  --env local \
  --json
```

This command is local/CI only and must refuse production unless an explicit
`--allow-production-seed` flag is present. Production seeding is not part of
normal operation.
