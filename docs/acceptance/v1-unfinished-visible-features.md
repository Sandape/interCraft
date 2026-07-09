# v1 Visible Unfinished Features

Date: 2026-07-05 (initial freeze)
Last reconciled: 2026-07-05 (no new deferred surfaces added during v1 freeze)

These are frontend-visible entries, descriptions, buttons, or flows that exist
in v1 but are not accepted as fully production-complete. They are documented so
future work does not confuse visible availability with completed scope.

| Surface | Visible entry | v1 status | Notes |
|---|---|---|---|
| Resume v2 rich text editor | Image insertion button | Deferred | Button now reports that image insertion is unavailable instead of calling a missing editor command. Needs a real image extension/upload contract before enabling. |
| Admin Logs & Traces | Log/trace detail APIs and deep drilldowns | Deferred | `src/api/admin-logs.ts` and `src/admin/mocks/admin-logs-fixtures.ts` still provide local fixture-backed detail data until OTel-backed endpoints are complete. |
| Admin AI Operations | `View in Logs` and `View badcase` drilldowns | Deferred | The visible buttons/comments still point at US placeholder routes rather than fully linked log/badcase detail flows. |
| Product Analytics | Placeholder tab | Deferred | `src/admin/pages/ProductAnalytics.tsx` still has `product-analytics-tab-placeholder`; keep it out of v1 accepted production analytics scope. |
| Users & Accounts admin page | Seed user search / Phase 1 demo wording | Deferred | The page still documents seed demo user IDs and is not accepted as a complete production user-management surface. |
| Agent observability | Strong debug/demo trace data | Deferred | Backend agent observability service still contains demo-seeded data paths for local inspection. |
| Admin analytics/governance internals | Seed/demo or in-memory paths | Deferred | Several admin console services still rely on seeded/demo/in-memory data for local visibility. They are not accepted as authoritative v1 production data stores. |

## Not A Defect

`模拟面试` / `mock interview` is product terminology for simulated interviews.
It should not automatically be treated as mock data unless the code path uses a
fixture or explicit mock switch.

## Hidden Defects Resolved During v1 Freeze

These were not visible to end users but were recorded as `Skipped Defects` in
[`v1-production-freeze.md`](./v1-production-freeze.md). They are now
**fixed** and removed from the defect ledger:

| Surface | Fix |
|---|---|
| Backend pytest collection | Removed 11 superseded `test_035_*` files plus 1 obsolete capture-hooks test and 1 orphan `test_033_fixtures.py`; cleaned `tests/contract/fixtures/__init__.py`. `--collect-only` reports 0 errors. |
| Planner integration test drift | `tests/integration/test_planner.py` Tavily stub now exposes the `.ainvoke` adapter the production `tavily_search` tool expects, returning `list[dict]` payloads the parser prefers. |
| Resume template gallery descriptors | Removed stale `placeholder - uses Onyx in MVP` copy from the template registry. |
| Resume right settings panel | Replaced visible Design, Styles, and Layout TODO panels with usable v1 controls. |
| Resume AI analysis auth | Fixed long-session token fallback and refresh response shape so Analyze can call the real backend/LLM. |
| Resume AI analysis fallback data | Removed fake `优势 1/2/3` and fallback suggestion rows; empty analysis arrays now render explicit empty states. |
