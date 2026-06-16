# Contract: `GET /api/v1/jobs/transitions`

**Phase**: 1 (design)
**Date**: 2026-06-16
**Spec**: [spec.md](../spec.md)

## Purpose

Expose the canonical job status lifecycle graph (`app.domain.enums.JOB_TRANSITIONS`) over HTTP so the frontend can derive the status tab set, the row-level status popover menu, and the "Active" stat composition from a single response, instead of hard-coding a (previously broken) local copy.

## Endpoint

`GET /api/v1/jobs/transitions`

### Auth

- `Authorization: Bearer <access_token>` — same JWT used by every other `/api/v1/jobs/*` route.
- 401 on missing/expired token (handled by `get_current_user_id`).

### Request

No body. No query parameters.

### Response — 200 OK

```jsonc
{
  "statuses": [
    "applied",
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

### Errors

| Status | When | Body |
|---|---|---|
| 401 | No/invalid `Authorization` header | standard `{"detail": "..."}` |
| 500 | Unexpected (should never happen — the data is a static in-process dict) | standard `{"detail": "..."}` |

There is intentionally **no** 422 (no body to validate), **no** 429 (no DB or external call, no rate limit), and **no** 404 (the route is mounted under the jobs prefix and does not address a per-resource path).

### Caching

`Cache-Control: public, max-age=300` is acceptable but not required — the frontend uses TanStack Query `staleTime: Infinity` regardless. Backend MAY omit the header without breaking the contract.

## Implementation note (for the implementer)

```python
@router.get("/transitions", response_model=TransitionsOut)
async def job_transitions(
    user_id: UUID = Depends(get_current_user_id),
) -> TransitionsOut:
    statuses, transitions = [], []
    for i, (from_, tos) in enumerate(JOB_TRANSITIONS.items()):
        statuses.append(from_)
        for to in sorted(tos):
            transitions.append(TransitionEdge(from=from_, to=to))
    return TransitionsOut(statuses=statuses, transitions=transitions)
```

`TransitionsOut` and `TransitionEdge` are added to `app.modules.jobs.schemas`.

## Pydantic schemas (new)

```python
# app/modules/jobs/schemas.py
class TransitionEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str

class TransitionsOut(BaseModel):
    statuses: list[str]
    transitions: list[TransitionEdge]
```

(Use `from_` on the Python side; the JSON key is `from` via the `alias`.)

## Frontend mirror

```ts
// src/types/jobs.ts (new)
export interface JobTransitionEdge {
  from: string
  to: string
}
export interface JobTransitionsResponse {
  statuses: string[]
  transitions: JobTransitionEdge[]
}
```

```ts
// src/api/jobs.ts (add)
export async function getJobTransitions(): Promise<JobTransitionsResponse> {
  return apiClient.request<JobTransitionsResponse>('GET', '/api/v1/jobs/transitions')
}
```

```ts
// src/hooks/queries/useJobTransitions.ts (new)
import { useQuery } from '@tanstack/react-query'
import { getJobTransitions } from '@/api/jobs'
import type { JobTransitionsResponse } from '@/types/jobs'

const FALLBACK: JobTransitionsResponse = {
  statuses: ['applied', 'test', 'oa', 'hr', 'offer', 'rejected', 'withdrawn'],
  transitions: [
    { from: 'applied', to: 'test' },
    { from: 'applied', to: 'oa' },
    { from: 'applied', to: 'hr' },
    { from: 'applied', to: 'offer' },
    { from: 'applied', to: 'rejected' },
    { from: 'applied', to: 'withdrawn' },
    { from: 'test',    to: 'oa' },
    { from: 'test',    to: 'hr' },
    { from: 'test',    to: 'offer' },
    { from: 'test',    to: 'rejected' },
    { from: 'test',    to: 'withdrawn' },
    { from: 'oa',      to: 'hr' },
    { from: 'oa',      to: 'offer' },
    { from: 'oa',      to: 'rejected' },
    { from: 'oa',      to: 'withdrawn' },
    { from: 'hr',      to: 'offer' },
    { from: 'hr',      to: 'rejected' },
    { from: 'hr',      to: 'withdrawn' },
    { from: 'offer',   to: 'rejected' },
    { from: 'offer',   to: 'withdrawn' },
  ],
}

export function useJobTransitions() {
  const q = useQuery({
    queryKey: ['jobTransitions'],
    queryFn: getJobTransitions,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: 1,
  })
  return {
    data: q.data ?? FALLBACK,
    isStale: q.isError,        // banner shows when true
    isLoading: q.isLoading,
    refetch: q.refetch,
  }
}
```
