# Data Model: Personal Agent + WeChat Channel

**Feature**: REQ-052 | **Date**: 2026-07-07

## Entity Relationship

```
users (existing)  1──1  agents (new)
agents            1──0..1  wechat_credentials (new)
users             1──0..1  wechat_bindings (new)
users             1──0..1  agent_preferences (new)
users             1──*  agent_messages (new)
users             1──*  agent_status_history (new)
```

## New Tables

### 1. `agents`

Personal AI Agent — one per user, auto-created on user registration.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid_v7() | Agent unique ID |
| `user_id` | UUID | FK→users.id, UNIQUE, NOT NULL | Owning user |
| `status` | TEXT | NOT NULL, DEFAULT 'dormant' | `active` / `degraded` / `dormant` |
| `wechat_uin` | TEXT | NULLABLE | Bound WeChat UIN (from iLink) |
| `last_heartbeat_at` | TIMESTAMPTZ | NULLABLE | Last successful long-poll |
| `status_changed_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last status change time |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Index**: `idx_agents_status` ON (`status`) — for monitoring queries

### 2. `wechat_credentials`

iLink channel runtime credentials. Separated from `wechat_bindings` for credential rotation support.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, UNIQUE, NOT NULL | Per-user unique |
| `bot_token_encrypted` | BYTEA | NULLABLE | AES-256-GCM encrypted iLink bearer token |
| `base_url` | TEXT | NOT NULL, DEFAULT 'https://ilinkai.weixin.qq.com' | iLink API base URL |
| `cursor` | TEXT | NULLABLE, DEFAULT '' | get_updates_buf for long-poll resume |
| `context_token` | TEXT | NULLABLE | Last inbound message's context_token |
| `status` | TEXT | NOT NULL, DEFAULT 'inactive' | `active` / `expired` / `revoked` |
| `last_polled_at` | TIMESTAMPTZ | NULLABLE | Last getupdates() return time |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Encryption**: `bot_token_encrypted` uses AES-256-GCM. Encryption key from `settings.WECHAT_TOKEN_ENCRYPTION_KEY` (env var, 32-byte base64).

**Index**: `idx_wechat_credentials_active` ON (`status`) WHERE `status = 'active'` — startup recovery scan

### 3. `wechat_bindings`

WeChat account ↔ InterCraft user binding (1:1 both directions).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, UNIQUE, NOT NULL | |
| `wechat_uin` | TEXT | UNIQUE, NOT NULL | iLink WeChat UIN |
| `bound_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `unbound_at` | TIMESTAMPTZ | NULLABLE | NULL = still active |
| `last_qrcode_login_at` | TIMESTAMPTZ | NULLABLE | |

**Index**: `idx_wechat_bindings_wechat_uin` ON (`wechat_uin`) — lookup by WeChat UIN

### 4. `agent_messages`

All messages sent/received through the WeChat channel.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, NOT NULL | |
| `direction` | TEXT | NOT NULL | `inbound` / `outbound` |
| `content` | TEXT | NOT NULL | Message text content |
| `message_type` | TEXT | NOT NULL, DEFAULT 'text' | `text` / `image` / `voice` / `file` |
| `status` | TEXT | NOT NULL, DEFAULT 'received' | inbound: `received`; outbound: `pending` / `sent` / `failed` / `expired` |
| `wechat_msg_id` | TEXT | NULLABLE | iLink message ID (inbound) |
| `context_token` | TEXT | NULLABLE | iLink session token (inbound) |
| `client_id` | UUID | NULLABLE | Outbound dedup ID |
| `segments_total` | INTEGER | NULLABLE | Total segment count (outbound long msg) |
| `segment_index` | INTEGER | NULLABLE | Current segment index (1-based) |
| `received_at` | TIMESTAMPTZ | NULLABLE | When message was received from iLink |
| `sent_at` | TIMESTAMPTZ | NULLABLE | When outbound message was sent |
| `error_message` | TEXT | NULLABLE | Error details if status=failed |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Index**: `idx_agent_messages_user_time` ON (`user_id`, `created_at` DESC) — message history queries
**Index**: `idx_agent_messages_pending` ON (`user_id`, `status`) WHERE `status = 'pending'` — rebuild queue

### 5. `agent_preferences`

User-configurable Agent behavior preferences.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, UNIQUE, NOT NULL | |
| `display_name` | TEXT | NOT NULL, DEFAULT '我的求职助手' | Max 20 chars |
| `quiet_hours_start` | TIME | NULLABLE | e.g., 22:00 |
| `quiet_hours_end` | TIME | NULLABLE | e.g., 08:00 |
| `notification_mode` | TEXT | NOT NULL, DEFAULT 'realtime' | `realtime` / `hourly_digest` |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

### 6. `agent_status_history`

Append-only audit log of Agent state transitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, NOT NULL | |
| `old_status` | TEXT | NOT NULL | |
| `new_status` | TEXT | NOT NULL | |
| `reason` | TEXT | NOT NULL | e.g., 'binding_completed', 'longpoll_failure', 'token_expired' |
| `changed_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

## Existing Tables (Used, Not Modified)

- `users` — referenced by FK from all new tables
- `jobs` — Agent reads via AgentContext (no schema change in this REQ)
- `interview_sessions` / `interview_reports` — Agent reads via AgentContext
- `ability_dimensions` / `error_questions` — Agent reads via AgentContext
- `resume_branches` — Agent reads via AgentContext

## Migration Notes

- All new tables use UUID v7 primary keys (consistent with project convention)
- `wechat_credentials.bot_token_encrypted` uses BYTEA with AES-256-GCM encryption at the application layer
- Indexes designed for startup recovery scan (`idx_wechat_credentials_active`) and message rebuild (`idx_agent_messages_pending`)
- All tables are RLS-enabled — `app.user_id` must be SET before access (consistent with constitution)
