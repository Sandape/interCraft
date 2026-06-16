# Research: Global Search Command Palette

**Feature**: 011-global-search
**Date**: 2026-06-16
**Spec**: [spec.md](./spec.md)

## Decisions

### D1 — Backend search strategy: ILIKE substring match (no FTS)

**Decision**: Use Postgres case-insensitive substring match (`ILIKE '%q%'`) over type-appropriate text columns, joined with `OR` to also include the type's human-friendly alias where one exists (e.g., `dimensions_meta.label_zh` for abilities).

**Rationale**:
- The data scale per user is small (resumes: dozens; interviews: dozens; abilities: <10 dimensions; FAQ/resources: tens to hundreds platform-wide). Substring on indexed `text` columns is fast enough at this scale.
- The codebase already uses raw `select(...).where(Resource.title.ilike(...))` in `content.service.search`. Following the existing pattern keeps the diff small and the consistency high.
- Avoids pulling in Postgres `tsvector` / `pg_trgm` infrastructure, which is overkill for the current scale and would require a migration to add generated columns or extension enablement.
- The frontend is responsible for the *quality* of UX (debounce, 200-char truncation, abort-on-new) so the backend stays a thin aggregation layer.

**Alternatives considered**:
- **Postgres full-text (`to_tsvector` / `ts_query`)**: Rejected. Requires schema changes (generated tsvector columns + GIN indexes) and a Chinese tokenizer is non-trivial. Value doesn't justify the complexity for a v1.
- **Trigram similarity (`pg_trgm`)**: Rejected. Same migration cost as FTS, with less precise ranking for short Chinese phrases.
- **Pure client-side search (fetch all + filter)**: Rejected. Cannot scale to large user datasets; breaks RLS; the user is the only one who can decide what is "their" data.

### D2 — Result caps: 5 per type, 25 total

**Decision**: Backend returns up to 5 results per type and a hard cap of 25 total. Each per-type limit and the total cap are enforced in the service layer.

**Rationale**:
- 5 per type is the sweet spot for a command palette: enough to feel comprehensive, low enough to keep the response < 5 KB and the panel scannable in a single viewport.
- The 25-total cap protects the backend from pathological queries and the UI from overflowing.
- These limits are the *initial* response shape; pagination can be added later (FR-010) without changing the contract shape, only adding `total` and `offset` fields.

**Alternatives considered**:
- **10 per type, 50 total**: Too dense for a 5-line-per-group palette.
- **3 per type, 15 total**: Too sparse; users would not trust the search to find what they want.
- **Unlimited, paginated**: Defeats the "command palette" metaphor where the user expects to see the top result immediately.

### D3 — Stale request handling: AbortController on the client

**Decision**: The frontend uses the `fetch` AbortSignal (already supported by the existing `apiClient.request` via `RequestOptions.signal`) to cancel the previous request when a new one starts. Only the latest response renders.

**Rationale**:
- The existing `apiClient.request` already accepts `signal?: AbortSignal`, so no new infra is needed.
- Browsers natively support this; a TanStack Query wrapper can be added later if needed, but for a single endpoint the manual approach is small and explicit.
- Simpler than server-side generation tokens, which would require the client to round-trip the token and the server to track it. The cancel happens on the wire before the server processes the new request, saving CPU.

**Alternatives considered**:
- **Server-side generation token + ignore stale**: Rejected. Adds backend complexity for a problem the client can solve locally.
- **Debounce + only the latest wins**: Rejected. Debounce alone does not cancel in-flight; you can still get out-of-order responses.
- **TanStack Query cancellation**: Defer. A single endpoint doesn't justify the wrapper, but the implementation will be easy to migrate later.

### D4 — Where the search endpoint lives: a new `search` module

**Decision**: Add a new `backend/app/modules/search/` module with router, service, schemas, and tests. Mount it under `/api/v1/search` in `app/api/v1/__init__.py`. Reuse the existing `app.api.deps.db_session_user_dep` to inherit the RLS context.

**Rationale**:
- The codebase organizes each feature as its own module (`auth`, `resumes`, `interviews`, `abilities`, `content`, etc.). Adding a new module matches the project convention.
- Keeping the search logic out of `content` avoids the implication that help search and global search are the same concern (they share data sources but are different use cases).
- The module structure lets us add per-type repositories without leaking them into the source modules.

**Alternatives considered**:
- **Add to `content` module**: Rejected. Mixes help-content and global-search concerns.
- **Add to `core`**: Rejected. The `core` directory is for cross-cutting infra (db, redis, security, logging), not for endpoints.
- **Add directly to v1 `__init__`**: Rejected. The codebase consistently uses modules.

### D5 — Rate limit: piggy-back on the existing business rate limit

**Decision**: Reuse `enforce_rate_limit(scope="business", per_minute=<config>)` — no new Redis bucket, no new config. The default business rate is set in `app.core.config` and applies to all authenticated, non-auth endpoints.

**Rationale**:
- The rate limiter already supports `scope="business"` and keys by `user_id` automatically.
- The user can already only type so fast; a per-user bucket is sufficient.
- Reusing existing infra means no new failure modes and no new env vars.

**Alternatives considered**:
- **Dedicated rate limit (`scope="search"`)**: Rejected. No measurable benefit at the current scale.
- **Per-IP rate limit**: Rejected. Users share IPs; per-user is the correct unit.

### D6 — Frontend component layout: a dedicated `CommandPalette` component owned by `AppShell`

**Decision**: Create `src/components/layout/CommandPalette.tsx` (and supporting `useGlobalSearch` hook + `searchApi`). Mount it from `src/components/layout/AppShell.tsx` so it's available on every authenticated page. Wire the topbar search input to open it.

**Rationale**:
- `AppShell` already wraps every authenticated route, so mounting once covers the whole app.
- A dedicated component keeps the Topbar's existing layout simple (it only needs an `onClick` and a `data-testid`).
- The shortcut listener can live on `AppShell` (or a `useGlobalShortcut` hook) and is naturally scoped to authenticated pages.

**Alternatives considered**:
- **Inline in Topbar**: Rejected. Topbar already has help, notifications, theme, avatar menu — adding a full command palette makes the file too large.
- **Portal-based modal mounted at App root**: Considered. The current Modal pattern is similar. We will use a fixed-positioned overlay rendered from AppShell instead of a portal, since AppShell is the root of authenticated pages.

### D7 — Frontend debounce + truncation: 200 ms debounce, 200-char truncation

**Decision**: After the user types or pauses for 200 ms, send a request with the query truncated to 200 characters.

**Rationale**:
- 200 ms is the standard debounce for type-ahead search and matches user expectation.
- 200-character truncation protects the backend from pathological inputs without affecting normal queries.

**Alternatives considered**:
- **No debounce**: Rejected. Will spam the server on every keystroke.
- **500 ms debounce**: Rejected. Feels laggy for a "command" UI.
- **100-char truncation**: Rejected. Some Chinese job titles + company names can exceed 100 chars when written out.

### D8 — E2E testing approach: 4 tests covering 1 happy path + 3 edge cases

**Decision**: Write a single Playwright spec file `tests/e2e/global-search.spec.ts` with 4 tests:

1. Happy path — open via shortcut, type a query, see grouped results, click a result, navigate.
2. Keyboard navigation — ArrowDown/Up, Enter, Escape.
3. Empty + no-results state — empty hint, then a no-results message.
4. Outside-click + retry + slow network — clicking outside closes the panel; an error response shows an error state.

**Rationale**:
- Matches the testing pattern of recent features (e.g., `topbar-utility-actions.spec.ts`, `interview-search-recovery.spec.ts`).
- Each test maps to one user story or one edge case in the spec.
- 4 tests is the right size for a self-contained feature without over-investing.

**Alternatives considered**:
- **One giant test with many assertions**: Rejected. Hard to triage failures.
- **One test per FR**: Rejected. 15+ tests for a single feature is overkill at this scope.
