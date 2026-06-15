# M12 — Pessimistic Lock Service

Resource-level pessimistic locks with WebSocket push, heartbeat management, and audit logging.

## Public API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/locks/acquire` | Acquire a lock on a resource |
| DELETE | `/api/v1/locks/{lock_id}` | Release a lock |
| GET | `/api/v1/locks/{resource_type}/{resource_id}` | Query lock status |
| WS | `/api/v1/ws/locks?token=` | WebSocket for lock events + heartbeat |

## Configuration

| Constant | Value | Description |
|----------|-------|-------------|
| `LOCK_HEARTBEAT_INTERVAL` | 60s | Client heartbeat interval |
| `LOCK_AUTO_RELEASE` | 90s | Stale lock timeout (1.5x heartbeat) |
| `LOCK_TTL_HARD` | 300s | Redis key TTL cap |
| `WS_DISCONNECT_GRACE` | 30s | Grace period after WS disconnect |

## CLI

```bash
# Acquire
uv run python -m app.modules.locks.cli acquire --resource-type resume_branch --resource-id <uuid> --json

# Release
uv run python -m app.modules.locks.cli release --lock-id <uuid> --json

# Status
uv run python -m app.modules.locks.cli status --resource-type resume_branch --resource-id <uuid> --json

# List stale locks
uv run python -m app.modules.locks.cli list-stale

# Replay from fixture
uv run python -m app.modules.locks.cli replay fixture.json
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Lock conflict / not found / error |

## WS Events

### Server → Client

- `lock.acquired` — resource locked by a user (broadcast to all)
- `lock.released` — lock released (broadcast to all)
- `lock.lost` — lock forcibly removed from current holder

### Client → Server

- `lock.heartbeat` — renew lock TTL (must be sent every 60s)
