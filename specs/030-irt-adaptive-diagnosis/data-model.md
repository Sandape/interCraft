# REQ-030 Data Model — IRT Item Bank

**Spec**: [./spec.md](./spec.md) | **Plan**: [./plan.md](./plan.md) | **Status**: US1 done, US2/3/4 ⏳ deferred.

This file is a **spec-side reference** — the actual schema lives in
`backend/migrations/versions/0020_irt_item_bank.py` and the ORM in
`backend/app/modules/irt/models.py`. The two stay in sync via Alembic.

## Entity-Relationship Overview

```
                ┌─────────────────────┐
                │     irt_items       │  (GLOBAL, no RLS)
                ├─────────────────────┤
                │ id (PK)             │
                │ dimension           │
                │ question_text_hash  │◄─── partial unique
                │ difficulty_b        │     (dim, hash) WHERE
                │ discrimination_a    │     status != 'retired'
                │ model (2pl|3pl)     │
                │ status              │
                │ response_count      │
                │ standard_error      │
                │ last_calibrated_at  │
                └──────────┬──────────┘
                           │ 1
                           │ (ON DELETE SET NULL)
                           │ N
                           ▼
┌────────────────────────────┐         ┌────────────────────────────┐
│   irt_item_responses       │         │   irt_ability_thetas        │
├────────────────────────────┤         ├────────────────────────────┤
│ id (PK)                    │         │ id (PK)                    │
│ user_id (FK users)         │         │ user_id (FK users)         │
│ item_id (FK irt_items)     │         │ dimension                  │
│ response (correct|incor.)  │         │ theta                      │
│ score (0-10)               │         │ standard_error             │
│ source_interview_id        │         │ n_items                    │
│ created_at                 │         │ source_interview_id        │
└────────────────────────────┘         │ model (2pl|3pl)            │
                                       │ converged                  │
                                       │ created_at                 │
                                       └────────────────────────────┘
                  │                                   ▲
                  │ user_id (RLS)                     │ user_id (RLS)
                  └─────────────► users ◄─────────────┘
```

## Why RLS on responses + thetas, not items?

| Table | RLS | Rationale |
|---|---|---|
| `irt_items` | **No** | Item bank is a global psychometric resource. Calibration requires aggregating responses from many users onto each item; per-user item tables would prevent batch calibration. |
| `irt_item_responses` | **Yes** | Per-user response history — must not leak across users. |
| `irt_ability_thetas` | **Yes** | Per-user ability estimates — private data. |

## Detailed Schemas

### `irt_items` (GLOBAL)

| Column | Type | NULL | Default | Notes |
|---|---|---|---|---|
| `id` | UUID v7 | NO | uuid_v7() | PK |
| `dimension` | TEXT | NO | | one of the 5 interview dimensions |
| `question_text_hash` | TEXT | NO | | SHA-256 of canonical text |
| `difficulty_b` | NUMERIC(6,3) | NO | | [-6, +6] logits |
| `discrimination_a` | NUMERIC(6,3) | NO | | [0, 5] |
| `model` | TEXT | NO | `'2pl'` | CHECK `IN ('2pl','3pl')` |
| `status` | TEXT | NO | `'uncalibrated'` | CHECK `IN ('uncalibrated','calibrated','retired','flagged')` |
| `response_count` | INT | NO | `0` | CHECK `>= 0` |
| `standard_error` | NUMERIC(6,3) | NO | `0` | CHECK `>= 0` |
| `last_calibrated_at` | TIMESTAMPTZ | YES | NULL | |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | on update = now() |

**Indexes**:
- `uq_irt_items_active_dim_hash` (UNIQUE) on `(dimension, question_text_hash) WHERE status != 'retired'`
- `idx_irt_items_dimension_status` on `(dimension, status)`

### `irt_item_responses` (RLS: user_id)

| Column | Type | NULL | Default | Notes |
|---|---|---|---|---|
| `id` | UUID v7 | NO | uuid_v7() | PK |
| `user_id` | UUID | NO | | FK → users.id, ON DELETE CASCADE, RLS-scoped |
| `item_id` | UUID | YES | | FK → irt_items.id, **ON DELETE SET NULL** (preserves history on retirement) |
| `response` | TEXT | NO | | CHECK `IN ('correct','incorrect')` |
| `score` | NUMERIC(4,2) | NO | | [0, 10] — LLM score preserved for 3-PL |
| `source_interview_id` | UUID | YES | | nullable |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |

**Indexes**:
- `idx_irt_responses_user_id` on `(user_id)`
- `idx_irt_responses_user_dim` on `(user_id, created_at)`
- `idx_irt_responses_item_id` on `(item_id)`

### `irt_ability_thetas` (RLS: user_id)

| Column | Type | NULL | Default | Notes |
|---|---|---|---|---|
| `id` | UUID v7 | NO | uuid_v7() | PK |
| `user_id` | UUID | NO | | FK → users.id, ON DELETE CASCADE, RLS-scoped |
| `dimension` | TEXT | NO | | |
| `theta` | NUMERIC(6,3) | NO | | [-6, +6] |
| `standard_error` | NUMERIC(6,3) | NO | | > 0 |
| `n_items` | INT | NO | | >= 1 |
| `source_interview_id` | UUID | YES | | nullable |
| `model` | TEXT | NO | `'2pl'` | |
| `converged` | BOOL | NO | `true` | False if Newton hit max_iter |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |

**Indexes**:
- `idx_irt_thetas_user_id` on `(user_id)`
- `idx_irt_thetas_user_dim` on `(user_id, dimension, created_at)`

## RLS Policies

Both RLS-scoped tables get the same pattern (mirrors `agent_memory` 028):

```sql
ALTER TABLE irt_item_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE irt_item_responses FORCE ROW LEVEL SECURITY;

CREATE POLICY irt_item_responses_user_isolation ON irt_item_responses
    USING (user_id = current_setting('app.user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);
```

The caller must `SELECT set_config('app.user_id', '<user_uuid>', true)`
inside the transaction that issues the query. The repository does not set
the GUC — it stays composable with the caller's transaction boundary.
