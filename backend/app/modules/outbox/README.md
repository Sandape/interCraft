# M13 — Outbox Replay Service

Server-side batch replay for client offline writes stored in IndexedDB Outbox.

## Public API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/outbox/replay` | Batch replay offline write entries (max 30) |
| GET | `/api/v1/outbox/status` | Server-side outbox health |

## Entity Routing Table

| entity_type | Operation | Conflict Detection |
|-------------|-----------|-------------------|
| `error_question` | create/update/delete | `updated_at` comparison |
| `activity` | create only | None (append-only) |
| `user_profile` | update | `updated_at` comparison |
| `job` | update | `updated_at` comparison |
| `task` | update (status only) | `updated_at` comparison |

## Conflict Detection Logic

When the server's `updated_at` is newer than the client's `entity_updated_at`,
the entry is marked `conflict` and the server entity returned for diff merge.

## CLI

```bash
# Replay from fixture file
uv run python -m app.modules.outbox.cli replay fixture.json

# Check status
uv run python -m app.modules.outbox.cli status --json

# Validate a single entry
uv run python -m app.modules.outbox.cli validate-schema entry.json
```
