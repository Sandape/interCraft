# Data Model: Global Search Command Palette

**Feature**: 011-global-search
**Date**: 2026-06-16
**Spec**: [spec.md](./spec.md)

This feature does not introduce any new database tables. It is a read-only
aggregator over existing tables (`resume_branches`, `interview_sessions`,
`ability_dimensions`, `help_faq`, `resources`) plus a static dimension metadata
table that's already loaded in memory.

The "data model" in this case is the response contract and the in-memory
client state machine. Both are documented below.

## 1. Search Response (API contract)

```ts
type SearchType = 'resume' | 'interview' | 'ability' | 'faq' | 'resource'

interface SearchResultItem {
  id: string                          // UUID for all types
  type: SearchType                    // discriminator
  title: string                       // primary display label
  subtitle?: string                   // secondary line (company, category, dimension key)
  destination: string                 // client-side route to navigate to on click
  score: number                       // backend-assigned ordering score (higher = better)
  meta?: Record<string, unknown>      // optional per-type extras (e.g., branch.status, dimension.key)
}

interface SearchGroup {
  type: SearchType                    // same as SearchType
  label: string                       // i18n label, e.g., "简历分支" / "面试记录"
  items: SearchResultItem[]           // up to 5 items
  total: number                       // total matches for this type (not just returned)
}

interface SearchResponse {
  groups: SearchGroup[]               // 0..5 groups, in a fixed order
  query: string                       // echo of the query
  took_ms: number                     // backend wall time, for observability
}
```

### Type → destination mapping (client)

| Type       | Destination route                  | Title source            | Subtitle source                |
|------------|------------------------------------|-------------------------|--------------------------------|
| resume     | `/resume/{id}`                     | `branch.name`           | `branch.position` (or `—`)     |
| interview  | `/interview/{id}/report`           | `session.position`      | `session.company`              |
| ability    | `/ability-profile/{dimension_key}` | `meta.label_zh`         | `meta.label_en`                |
| faq        | `/help#faq/{id}`                   | `faq.question`          | `category` label               |
| resource   | `/help#resource/{id}`              | `resource.title`        | `resource.summary`             |

## 2. Backend Pydantic schemas (mirror)

```python
class SearchResultItem(BaseModel):
    id: UUID
    type: Literal["resume", "interview", "ability", "faq", "resource"]
    title: str
    subtitle: str | None = None
    destination: str
    score: float
    meta: dict[str, Any] = {}


class SearchGroup(BaseModel):
    type: Literal["resume", "interview", "ability", "faq", "resource"]
    label: str
    items: list[SearchResultItem]
    total: int


class SearchResponse(BaseModel):
    groups: list[SearchGroup]
    query: str
    took_ms: int
```

## 3. Client state machine

The `CommandPalette` component holds the following state:

| Field           | Type                | Initial   | Notes                                       |
|-----------------|---------------------|-----------|---------------------------------------------|
| `open`          | `boolean`           | `false`   | Toggled by shortcut, input click, or result |
| `query`         | `string`            | `''`      | Bound to the input element                  |
| `highlight`     | `number`            | `0`       | Index into the flat result list             |
| `requestState`  | `'idle'\|'loading'\|'success'\|'error'` | `'idle'` | Request status |
| `error`         | `string \| null`    | `null`    | Error message (only when state = 'error')   |
| `groups`        | `SearchGroup[]`     | `[]`      | Latest response                             |
| `abortRef`      | `AbortController \| null` | `null` | Cancels in-flight request                 |
| `debounceRef`   | `number \| null`    | `null`    | setTimeout handle for debounce              |

### State transitions

```
[closed] --shortcut/click--> [open: query=''] --type--> [open: query=q]
[open] --Escape/outside-click--> [closed]
[open: query=q] --Enter on highlight--> [closed] + navigate
[open: query=q] --type--> [open: query=q'] --200ms--> fetch() ---> requestState='loading'
                                                --> response: requestState='success', groups=...
                                                --> network error: requestState='error'
```

## 4. Source data model (no new tables)

| Source table         | Read fields                              | Match fields (ILIKE)                          | RLS                |
|----------------------|------------------------------------------|------------------------------------------------|--------------------|
| `resume_branches`    | `id`, `name`, `position`, `company`, `status`, `is_main` | `name`, `position`, `company`                | user-scoped (RLS)  |
| `interview_sessions` | `id`, `position`, `company`, `status`    | `position`, `company`                          | user-scoped (RLS)  |
| `ability_dimensions` | `dimension_key`, joined to `dimensions_meta.label_zh` | `dimension_key`, `label_zh`                   | user-scoped (RLS)  |
| `help_faq`           | `id`, `question`, `category`             | `question`                                     | platform-wide      |
| `resources`          | `id`, `title`, `summary`, `category`     | `title`, `summary`                             | platform-wide      |

Notes:
- `dimensions_meta` is a static dict returned by `GET /ability-dimensions/dimensions-meta`. For the search endpoint, we read the static dict from `app.modules.abilities.api.DIMENSIONS_META_STATIC` and join to ability rows in service code (avoids a join across a non-tabular source).
- `resume_branches` and `interview_sessions` use the existing `TenantScopedMixin` + RLS; the new endpoint inherits this by using `db_session_user_dep`.

## 5. Validation rules (enforced by backend)

- `q`: 1 ≤ length ≤ 200 (after trimming whitespace). Empty or whitespace-only → 422.
- `limit` (per type): default 5, min 1, max 5 (capped at 5; requester can ask for less but not more).
- `total cap`: backend service enforces a hard cap of 25 items across all groups in a single response (sum of `len(items)` per group ≤ 25).
- Auth: required. Missing/invalid token → 401.
- Rate limit: per-user, uses the existing `scope="business"` bucket.
