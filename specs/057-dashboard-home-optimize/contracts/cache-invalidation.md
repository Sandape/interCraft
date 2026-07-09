# Contract: Dashboard Summary Cache

**Spec refs**: FR-024～027, SC-006, SC-012  
**Research**: R6

## Key

```
dashboard_summary:{user_id}:{local_date}
```

- `user_id`: UUID string
- `local_date`: `YYYY-MM-DD` in request `tz`
- MUST NOT use keys without `user_id`

## TTL

| Scope | TTL |
|---|---|
| Full summary blob | 60 seconds |
| (Optional split) ability slice | 300 seconds |

## Read path

1. Compute `local_date` from `tz` + server now.
2. `GET` Redis key; on hit return parsed JSON (log `cache=hit`).
3. On miss / Redis unavailable: build from DB, `SET` with TTL (log `cache=miss` or `cache=bypass`).
4. Redis errors MUST NOT fail the request.

## Invalidate (delete key)

On successful write for the same `user_id`, delete at least:

```
dashboard_summary:{user_id}:{today_local}
dashboard_summary:{user_id}:{yesterday_local}   # optional safety for TZ edge
```

| Writer domain | Examples |
|---|---|
| Jobs | create/update/delete; status change; `interview_time` change |
| Resumes v2 | create/update/delete; kind/job bind changes |
| Interview sessions | status → in_progress/completed/aborted/expired; create |
| Activities | any new activity row for user |

Invalidation SHOULD be best-effort in the same request/transaction boundary as the write (after commit preferred).

## Isolation test

1. User A summary cached with A's jobs.
2. User B requests summary → MUST NOT receive A's `today_interviews` or resumes.
3. User A updates `interview_time` → next summary within TTL window after invalidate reflects change (or max wait = TTL if invalidate missed — treat miss as bug).

## Client

- TanStack Query key includes `localDate`; on date change, new key (natural日切).
- `placeholderData: previous` for SWR UX; still refetch on focus.
