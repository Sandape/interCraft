# Data Model: 登录会话稳定性

## Overview

Changes to `auth_sessions` table and related data model.

## Entity: AuthSession

**Table**: `auth_sessions` — stores user login sessions

### Current Schema

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID v7 | PK | Session ID (used in JWT payload) |
| user_id | UUID | FK → users(id), NOT NULL, RLS | User who owns this session |
| device_id | Text | NOT NULL, **UNIQUE(user_id, device_id)** | SHA256 of device fingerprint |
| device_fingerprint | Text | NOT NULL | Raw fingerprint parts joined by `\|` |
| device_name | Text | nullable | Human-readable (e.g. "Chrome 128") |
| refresh_token_hash | Text | NOT NULL, CHECK(length=64) | SHA256 of refresh JWT |
| expires_at | Timestamptz | NOT NULL | Session expiry (currently refresh_ttl = 7d) |
| last_seen_ip | INET | nullable | Last IP seen |
| last_seen_ua | Text | nullable | Last user-agent |
| last_seen_at | Timestamptz | NOT NULL, DEFAULT now() | Last activity timestamp |
| trusted_at | Timestamptz | nullable | When device was trusted |
| deleted_at | Timestamptz | nullable, **indexed** | Soft-delete timestamp |
| created_at | Timestamptz | NOT NULL, DEFAULT now() | Row creation time |
| updated_at | Timestamptz | NOT NULL, DEFAULT now() | Row update time |

### Changes in This Feature

| Change | Type | Rationale |
|--------|------|-----------|
| Remove `UNIQUE(user_id, device_id)` | **DDL** | FR-001: allow multi-tab coexistence |
| Drop `device_id` UNIQUE constraint migration | **DDL** | No replacement needed; session_id is the true unique identifier |
| No new columns | — | All info captured in existing schema |

### Post-change Constraints

```sql
-- After migration:
-- NO unique constraint on (user_id, device_id)
-- PRIMARY KEY (id) remains
-- FK user_id → users(id) remains (CASCADE on delete)
-- CHECK (length(refresh_token_hash) = 64) remains
```

## Entity: SessionEvictionEvent (New Concept)

**Not a new table** — this data is captured via structured logging (FR-011) and metrics (FR-010), not a dedicated database table.

### Audit Event Schema

| Field | Type | Description |
|-------|------|-------------|
| event_type | Enum | `session_created`, `session_rotated`, `session_evicted`, `session_revoked` |
| timestamp | Timestamptz | Event time |
| actor_user_id | UUID (masked) | User whose session was affected |
| target_session_id | UUID | The session being created/evicted/rotated |
| cause | Enum | For eviction: `max_devices_exceeded`, `admin_revoke`, `reuse_detection`; for others: `login`, `refresh`, `logout` |
| device_id | Text(sha256) | Device identifier (for correlation) |

## Affected Queries

### list_active (FR-003)

Before:
```sql
SELECT * FROM auth_sessions
WHERE user_id = :uid AND deleted_at IS NULL
ORDER BY last_seen_at DESC
```

After:
```sql
SELECT * FROM auth_sessions
WHERE user_id = :uid AND deleted_at IS NULL
  AND expires_at > NOW()
ORDER BY last_seen_at DESC
```

### In-place rotation (FR-009)

Before:
```sql
-- Step 1: soft-delete old
UPDATE auth_sessions SET deleted_at = NOW() WHERE id = :old_id;
-- Step 2: insert new
INSERT INTO auth_sessions (user_id, device_id, ...) VALUES (...);
```

After:
```sql
UPDATE auth_sessions
SET refresh_token_hash = :new_hash,
    expires_at = :new_expires,
    updated_at = NOW()
WHERE id = :session_id;
```

### Eviction check (FR-002)

Before:
```sql
SELECT COUNT(*) FROM auth_sessions
WHERE user_id = :uid AND deleted_at IS NULL;
```

After:
```sql
SELECT COUNT(*) FROM auth_sessions
WHERE user_id = :uid AND deleted_at IS NULL
  AND expires_at > NOW();
```

### Oldest session for eviction (FR-002)

```sql
SELECT * FROM auth_sessions
WHERE user_id = :uid AND deleted_at IS NULL
  AND expires_at > NOW()
ORDER BY last_seen_at ASC
LIMIT 1;
```
