# Contract: Frontend Dashboard Query & UI

**Spec refs**: FR-005, FR-010, FR-022, FR-027～032, SC-005, SC-007, SC-009

## Hook

```ts
// src/hooks/queries/useDashboardSummary.ts
export const DASHBOARD_SUMMARY_KEY = ['me', 'dashboard-summary'] as const

useDashboardSummary(opts?: { tz?: string })
// queryKey: [...DASHBOARD_SUMMARY_KEY, localDate, tz]
// staleTime: 30_000
// placeholderData: (prev) => prev
// refetchOnWindowFocus: true
```

`localDate` = calendar date in `tz` (default `Asia/Shanghai`).

## Dashboard page rules

1. Primary data source: `useDashboardSummary` only for L0/L1/L2 panels listed in spec.
2. MUST NOT call `useResumeBranches` for display or suggestion inputs.
3. MUST NOT use `useTasks` for「今日待办」.
4. MUST render exactly one suggestion / next-action panel (no duplicate AI + 提升建议 lists).
5. MUST NOT show checkbox UI on today interviews.
6. MUST NOT show「实时」badge on suggestions.
7. Mobile (< md): primary CTA MUST remain visible (sticky bottom or always-in-flow control).
8. Panel loading: skeleton per region; errors local to panel.

## Auth

`useCurrentUser`: if auth store already has user and tokens present, refetch MUST keep `status === 'authenticated'` (or equivalent non-blocking). MUST NOT flip to `unknown` solely because `isFetching`.

## Invalidation

After successful mutations that change jobs / resumes v2 / interview sessions / activities, callers MUST:

```ts
queryClient.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY })
```

## Retired patterns

| Pattern | Action |
|---|---|
| Dual suggestion cards | Remove one; keep「下一步」 |
| Stat cards with fake +0 growth | Hide delta or link through without fake trend |
| Title「我的简历分支」 | Rename to 简历中心语义（根/派生） |
