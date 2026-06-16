# Research: Jobs Status Alignment

**Phase**: 0 (precedes design)
**Date**: 2026-06-16
**Spec**: [spec.md](./spec.md)

## Goal

Resolve all "NEEDS CLARIFICATION" items from the plan and pick the smallest reliable design for shipping the spec.

## Decisions

### Decision 1 — Endpoint shape: a single flat endpoint vs. multiple per-job queries

- **Decision**: A single `GET /api/v1/jobs/transitions` returns `{statuses: string[], transitions: {from, to}[]}`. The UI fetches it once per session.
- **Rationale**: Keeps the UI derivation logic trivial (one source of truth), avoids N+1 calls per row, and matches how Phase 6 `content` module exposes its static enums (`GET /api/v1/help-faq`).
- **Alternatives considered**:
  - One `GET /api/v1/jobs/{id}/allowed-transitions` per row → would force N+1 fetches or per-row prefetching; rejected.
  - Embed allowed transitions inside `JobOut` → would bloat every list response and require a server-side change to the existing serializer; rejected.
  - Hard-code `JOB_TRANSITIONS` in the frontend → exactly the bug we are fixing; rejected.

### Decision 2 — Status popover pattern

- **Decision**: Popover (dropdown) anchored to the row's `MoreHorizontal` icon. Terminal moves (`rejected`, `withdrawn`) open a confirm modal first. Non-terminal moves apply directly.
- **Rationale**: Matches the existing 3-dots icon already imported in `src/pages/Jobs.tsx` (currently unused), keeps the table row compact, and the confirm modal is the same pattern used by `InterviewList.tsx` (per `specs/008-interview-delete-feedback`). One shared `Modal` component from `src/components/ui/Modal` is reused.
- **Alternatives considered**:
  - Inline buttons per allowed transition → too noisy once `test/oa/hr/offer` are all on the table.
  - Always-confirm modal → adds a click on every benign transition (`applied → test`).
  - Browser-native `<select>` → poor keyboard semantics and ugly styling, not idiomatic for the rest of the app.

### Decision 3 — Fallback when the transitions endpoint fails

- **Decision**: A small built-in fallback copy of the seven statuses + transitions is rendered. A non-blocking banner appears above the stats: "状态数据可能已过期，部分状态不可用 — 重试". All popover items still work.
- **Rationale**: The endpoint is static and extremely unlikely to fail in practice, but if it does (e.g., a CORS issue, a 502 from a proxy in production) the page must remain usable, not blank. The banner is the same shape used elsewhere in the app for non-fatal warnings.
- **Alternatives considered**:
  - Block the page on the endpoint → makes the page useless during a transient outage.
  - Silently fall back → hides a real bug from the user.

### Decision 4 — Where to fetch and how to cache

- **Decision**: A new `useJobTransitions` TanStack Query hook with `staleTime: Infinity`, `gcTime: Infinity`, `retry: 1`. Fetched once on Jobs page mount; cached for the rest of the session via the shared `QueryClient`.
- **Rationale**: TanStack Query's `staleTime: Infinity` is the documented pattern for "fetch once, use forever" in this codebase (see `src/hooks/queries/useErrorQuestions.ts` for a similar pattern). It avoids hammering the endpoint on tab switches and re-renders.
- **Alternatives considered**:
  - Plain `useEffect` + `useState` → loses the global cache and would re-fetch on every Jobs-page remount.
  - `localStorage` caching → adds staleness and a manual invalidation story; not worth it for a static endpoint.

### Decision 5 — `StatusBadge` rewrite scope

- **Decision**: Replace the `screening` and `interview` keys in `src/components/jobs/StatusBadge.tsx` with `test`, `oa`, `hr` (using the existing `JOB_STATUS_CN` Chinese labels). Keep the same icon mapping style. Add a "未知" fallback for unrecognized statuses (e.g., `wishlist` is in the existing config but is not a real backend status — leave it alone, it's unused but harmless).
- **Rationale**: A row could come back from the API in any real status, and the badge must show the right label + variant. Without this, a `test` job would render as the raw "test" string in the default variant.
- **Alternatives considered**:
  - Pass a label in from the parent → fine but requires every caller to know the mapping; the badge is the single source of display labels in this codebase.

### Decision 6 — `Active` stat composition

- **Decision**: The existing "进行中" (Active) stat sums `applied + test + oa + hr` (anything non-terminal that is also not `offer`). `offer`, `rejected`, `withdrawn` are reported as separate tiles.
- **Rationale**: "Active" should mean "the user can still do something about this job". `offer` is non-actionable (you either accept or reject it, but you can't interview again), and the two terminal states obviously aren't active.
- **Alternatives considered**:
  - Keep "Active" = `applied + test + oa + hr + offer` → meaningless; lumps `offer` with work-in-progress.
  - Drop "Active" entirely → loses the high-level glance value.

## Resolved Unknowns

- ✅ Source of the transition graph → new endpoint, fetched once
- ✅ Popover pattern → `MoreHorizontal` popover + confirm-modal for terminal
- ✅ Fallback on endpoint failure → built-in copy + non-blocking banner
- ✅ Caching strategy → TanStack Query, `staleTime: Infinity`
- ✅ Where the `screening`/`interview` strings live → `StatusBadge.tsx` + `Jobs.tsx`; both updated
- ✅ How "Active" is composed → `applied + test + oa + hr` only
