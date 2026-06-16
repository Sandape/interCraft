# Data Model: Jobs Status Alignment

**Phase**: 1 (design)
**Date**: 2026-06-16
**Spec**: [spec.md](./spec.md)

No new database tables. The slice reuses the existing `jobs` table and the existing `JOB_TRANSITIONS` Python dict in `app/domain/enums.py`. The only new shape is the HTTP response from the new endpoint.

## New HTTP shape (read-only)

### `JobTransitionsOut` (response of `GET /api/v1/jobs/transitions`)

```jsonc
{
  "statuses": [
    "applied",   // ordered: lifecycle first, then terminal states
    "test",
    "oa",
    "hr",
    "offer",
    "rejected",
    "withdrawn"
  ],
  "transitions": [
    { "from": "applied",  "to": "test" },
    { "from": "applied",  "to": "oa" },
    { "from": "applied",  "to": "hr" },
    { "from": "applied",  "to": "offer" },
    { "from": "applied",  "to": "rejected" },
    { "from": "applied",  "to": "withdrawn" },
    { "from": "test",     "to": "oa" },
    { "from": "test",     "to": "hr" },
    { "from": "test",     "to": "offer" },
    { "from": "test",     "to": "rejected" },
    { "from": "test",     "to": "withdrawn" },
    { "from": "oa",       "to": "hr" },
    { "from": "oa",       "to": "offer" },
    { "from": "oa",       "to": "rejected" },
    { "from": "oa",       "to": "withdrawn" },
    { "from": "hr",       "to": "offer" },
    { "from": "hr",       "to": "rejected" },
    { "from": "hr",       "to": "withdrawn" },
    { "from": "offer",    "to": "rejected" },
    { "from": "offer",    "to": "withdrawn" }
  ]
}
```

The shape is intentionally flat (a single list of edges) so the frontend can build an `allowedToMap: Record<string, string[]>` in O(n) and never has to re-query.

## Existing entity: `jobs` (no change)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID v7 | PK |
| `user_id` | UUID | FK `users.id` ON DELETE CASCADE |
| `company` | text | 1..100 chars |
| `position` | text | 1..100 chars |
| `jd_url` | text? | nullable |
| `branch_id` | UUID? | nullable, FK `resume_branches.id` |
| `status` | text | one of the seven values listed above |
| `status_history` | jsonb | append-only timeline (frontend already uses this) |
| `last_status_changed_at` | timestamptz | indexed for ordering |
| `notes_md` | text? | nullable |
| `created_at` | timestamptz | server default `now()` |
| `updated_at` | timestamptz | server default `now()` ON UPDATE |
| `deleted_at` | timestamptz? | soft-delete sentinel; not used by this slice |

No migration is required. The `status` field is already `text` and accepts any of the seven values; the previous `screening`/`interview` values were never written by the backend.

## State transition rules

Sourced from `app/domain/enums.py` `JOB_TRANSITIONS` (single source of truth on the backend):

```python
JOB_TRANSITIONS: dict[str, set[str]] = {
    "applied":  {"test", "oa", "hr", "offer", "rejected", "withdrawn"},
    "test":     {"oa", "hr", "offer", "rejected", "withdrawn"},
    "oa":       {"hr", "offer", "rejected", "withdrawn"},
    "hr":       {"offer", "rejected", "withdrawn"},
    "offer":    {"rejected", "withdrawn"},
    "rejected": set(),
    "withdrawn": set(),
}
```

The new endpoint serializes this dict into the flat edge list above. The Python dict is the source of truth; if a new status is ever added, the endpoint automatically exposes it (no second place to update).

## Computed (frontend-side, not stored)

| Computed | Formula | Used by |
|---|---|---|
| `allowedToFor(from)` | `transitions.filter(e => e.from === from).map(e => e.to)` | row popover menu items |
| `tabs` | `["all", ...statuses]` in `statuses` order | Tabs component |
| `activeCount` | `counts.applied + counts.test + counts.oa + counts.hr` | "进行中" stat tile |
| `rejectedCount` | `counts.rejected` | "已拒绝" stat tile (replaces `rejected + withdrawn` lump) |
| `withdrawnCount` | `counts.withdrawn` | new "已撤回" stat tile |
| `tabCount(status)` | `counts[status] ?? 0` | tab count badge |

The frontend MUST NOT cache `JOB_TRANSITIONS` in a separate local file. The hook (`useJobTransitions`) is the only place the graph lives on the client.

## Validation rules (unchanged)

- The existing `JobService.update_status` already validates against `JOB_TRANSITIONS` and returns HTTP 409 `invalid_status_transition` on a bad request — this slice relies on that existing behavior for the failure-path E2E scenario.
- No changes to input validation; the only new surface (`GET /api/v1/jobs/transitions`) takes no body and no query parameters.
