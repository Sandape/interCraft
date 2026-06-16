# Feature Specification: Jobs Status Alignment

**Feature Branch**: `[015-jobs-status-alignment]`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Fix Jobs page status misalignment with backend JobStatus enum. Frontend uses `screening` and `interview` tabs which don't exist in the backend JobStatus (`applied`/`test`/`oa`/`hr`/`offer`/`rejected`/`withdrawn`). The main 'advance' button transitions `screening → interview` which the backend rejects with 409. Stats also lump `withdrawn` into `rejected`. Need a spec for: real JobStatus tabs (including `test`/`oa`/`hr`/`withdrawn`), working advance flow that matches backend JOB_TRANSITIONS, accurate stats, and an E2E test that exercises the happy path + the 409 failure case to prove the flow is reliable."

## Clarifications

### Session 2026-06-16

- Q: Which JobStatus values should appear as tabs? -> A: All real backend statuses (`applied`, `test`, `oa`, `hr`, `offer`, `rejected`, `withdrawn`) plus an "all" tab.
- Q: When the backend rejects an invalid transition with 409, how should the UI react? -> A: Surface an inline error toast/banner on the affected row, keep the original status visible, and keep the row in the list — no silent rollback.
- Q: Should the "advance" action still be a single primary button per row? -> A: Replace it with a status menu that lists the valid next statuses from `JOB_TRANSITIONS`, so the user picks a real next step and never sends an invalid transition.
- Q: How does the frontend obtain the authoritative `JOB_TRANSITIONS` graph? -> A: New backend endpoint `GET /api/v1/jobs/transitions` (response: `{statuses: string[], transitions: {from: string, to: string}[]}`). The UI fetches it once at session start (TanStack Query, `staleTime: Infinity`) and the status menu / status tabs / Stats "Active" composition all derive from it — no hard-coded local copy.
- Q: What is the final stats card layout? -> A: Four tiles in lifecycle order: `总申请` (total), `进行中` (Active = `applied + test + oa + hr`), `Offer`, `已拒绝` (Rejected = `rejected` only). `已撤回` (Withdrawn) is exposed as a fifth stat tile aligned to the right of `已拒绝` so the two terminal states never collapse together; total card count is 5 in display, but the lifecycle tiles (Active / Offer) remain the primary two. The "Active" composition explicitly excludes `offer`, `rejected`, and `withdrawn`.
- Q: After a successful status change, should the row stay in the current filter tab? -> A: No. On a successful status update, the row is removed from the current tab immediately (optimistic) once the server confirms the new status. The user sees the row leave as the new status lands. On a 409 failure, the row remains in the current tab with its previous status (per US4 / FR-007) and the 409 path never triggers a removal. The `all` tab is unaffected (it always shows the full set, so the row simply re-renders with the new badge).
- Q: What does the "retry" affordance look like after a 409? -> A: An explicit `重试` button rendered on the inline error row (same PATCH `/jobs/{id}/status` with the same `{to}` payload). The button has a stable `data-testid="job-row-retry"` so E2E tests can target it deterministically. Pressing `重试` keeps the error state visible during the in-flight request; a successful retry clears the error, removes the row from the current tab per the row-leaves-tab behavior, and increments the destination status count; a second 409 leaves the error visible and keeps the button enabled.
- Q: Which interaction pattern should the row-level status menu use? -> A: Popover (dropdown) with a confirm modal only for terminal moves (`rejected`, `withdrawn`); reuse the existing `MoreHorizontal` icon and keep the table row compact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Advance a job through its real lifecycle (Priority: P1)

An authenticated user tracking job applications on the Jobs page opens a record currently in `applied`, opens the row's status menu, picks one of the real next statuses (`test`, `oa`, `hr`, `offer`, `rejected`, `withdrawn`), and sees the new status reflected in the list and in the stats card without errors.

**Why this priority**: Today the "advance" button posts an invalid transition (`screening → interview`) that the backend rejects with HTTP 409. The most common reason a user opens this page is to move a job forward; the broken main action is the highest-impact defect.

**Independent Test**: Open the Jobs page with one `applied` record, click the row's status action, choose `offer`, and verify the row badge becomes "Offer" and the dashboard stat "Offer" increments by one.

**Acceptance Scenarios**:

1. **Given** a job is in `applied`, **When** the user opens the row status menu and picks a status allowed by `JOB_TRANSITIONS`, **Then** the new status is persisted and the row badge updates.
2. **Given** a job is in `rejected` or `withdrawn` (terminal states), **When** the user views the row, **Then** no advance/move actions are offered because there are no allowed transitions.
3. **Given** the user opens the Jobs page for the first time in a session, **When** the page loads, **Then** the status tab set and the row status menu options are both derived from the response of `GET /api/v1/jobs/transitions`, not from a hard-coded local list.
4. **Given** the user is viewing the `applied` tab and successfully advances a row to `test`, **When** the server confirms the change, **Then** the row is removed from the `applied` tab (and from the `Active` stat count by one) and appears in the `test` tab; the `Offer` / `Rejected` / `Withdrawn` tabs are unaffected.

---

### User Story 2 - Filter the job list by real status (Priority: P1)

An authenticated user with mixed job records filters the list by `test`, `oa`, `hr`, `offer`, `rejected`, or `withdrawn` and sees only the matching rows. Each tab shows the count of records it currently holds.

**Why this priority**: Today `test`, `oa`, `hr`, and `withdrawn` have no tab — users with records in those states cannot find them via filters. The "all" tab works but hides them behind unrelated rows.

**Independent Test**: Seed at least one job per real status, then click each tab and verify only jobs in that status appear, and the count badge on each tab matches the number of rows.

**Acceptance Scenarios**:

1. **Given** the user has jobs in multiple statuses, **When** they click the `withdrawn` tab, **Then** only withdrawn jobs are listed and the `withdrawn` tab badge shows the count of withdrawn jobs.
2. **Given** the user is on any tab, **When** they click `all`, **Then** every non-deleted job the user owns appears in creation order.

---

### User Story 3 - See accurate stats including `withdrawn` (Priority: P2)

An authenticated user sees the dashboard stats cards reflect real status counts. Five tiles are displayed in lifecycle order: `总申请` (total), `进行中` (Active), `Offer`, `已拒绝` (Rejected), `已撤回` (Withdrawn). `withdrawn` no longer collapses into `rejected`, the "Active" tile counts only `applied + test + oa + hr` (excluding `offer`, `rejected`, and `withdrawn`), and the two terminal states each get their own tile.

**Why this priority**: Wrong stats damage trust in the product. The stat tile currently sums `rejected + withdrawn` as "Rejected" which is misleading. Splitting the two makes the page trustworthy again.

**Independent Test**: Seed 2 `withdrawn` jobs and 1 `rejected` job; open Jobs; verify the stat tiles show `withdrawn: 2` and `rejected: 1` separately.

**Acceptance Scenarios**:

1. **Given** the user has jobs in `rejected` and `withdrawn`, **When** they view the stat tiles, **Then** the `已拒绝` tile shows only the `rejected` count and the `已撤回` tile shows only the `withdrawn` count, with no overlap.

---

### User Story 4 - Recover from an invalid transition with inline feedback (Priority: P2)

If the backend ever returns HTTP 409 `invalid_status_transition` for a transition the UI offered, the user sees an inline error on the affected row, the row keeps its previous status visible, and the UI offers a "重试" action or allows re-opening the status menu.

**Why this priority**: Defensive UI around the status change ensures users are never silently stuck. Without this, a 409 leaves the UI in an ambiguous state.

**Independent Test**: Force the backend to return 409 for a status transition, click an advance action, and verify the row shows an inline error and the row's status is unchanged.

**Acceptance Scenarios**:

1. **Given** the user picks a status from the row menu, **When** the backend responds 409, **Then** the row shows an inline error message with a `重试` button (`data-testid="job-row-retry"`) and the row badge remains at the previous status.
2. **Given** a row is showing a 409 error with the `重试` button, **When** the user clicks `重试`, **Then** the same PATCH `/jobs/{id}/status` request is re-fired with the same `{to}` payload; on success the error clears and the row leaves the current tab; on a second 409 the error and the button remain.

### Edge Cases

- A user with zero jobs in any of the seven real statuses sees the existing empty state under the `all` tab and a zero count on every status tab.
- The search input still filters the visible rows of the active tab after the status tabs are realigned.
- If `JOB_TRANSITIONS` ever changes (e.g., a new status is added), the UI MUST only show transitions that the backend currently accepts; UI MUST NOT send unknown transitions even if cached in the client.
- A user with an `offer` record sees only `rejected` and `withdrawn` in the row's status menu (offers are not auto-closed).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST render status tabs that match the backend's `JobStatus` enum values exactly: `applied`, `test`, `oa`, `hr`, `offer`, `rejected`, `withdrawn`, plus an `all` tab.
- **FR-002**: System MUST show a count badge on every status tab reflecting the number of records the current user owns in that status (0 is allowed and must display `0`).
- **FR-003**: System MUST replace the row's "advance" button with a status menu whose entries are exactly the allowed transitions for the row's current status, derived from `GET /api/v1/jobs/transitions` (see FR-009).
- **FR-004**: System MUST NOT post any status transition that the backend would reject: every status menu entry MUST come from the `transitions` array returned by the new endpoint; the client MUST refuse to render or send any status not present in that response.
- **FR-005**: System MUST display 5 stat tiles in lifecycle order: `总申请` (total), `进行中` (Active = `applied + test + oa + hr`), `Offer`, `已拒绝` (Rejected = `rejected` only), `已撤回` (Withdrawn = `withdrawn` only). The "已拒绝" tile MUST NOT include `withdrawn` records, and "已撤回" MUST NOT include `rejected` records.
- **FR-006**: System MUST keep the active/in-progress status of a row visible to the user (badge, list position) until a server-confirmed success response is received, at which point the row is removed from the currently filtered tab if its new status no longer matches that tab's filter (per the row-leaves-tab behavior).
- **FR-007**: When the status update request fails with HTTP 409 `invalid_status_transition`, System MUST surface an inline error on the affected row with an explicit `重试` button (`data-testid="job-row-retry"`) that re-fires the same PATCH `/jobs/{id}/status` payload. The previous status badge MUST stay visible and the row MUST stay in the current filter tab. A successful retry clears the error and triggers the row-leaves-tab behavior (per FR-006); a second 409 leaves the error and the button enabled.
- **FR-008**: The status tab order MUST be the lifecycle order: `applied → test → oa → hr → offer`, followed by the terminal states `rejected`, `withdrawn`.
- **FR-009**: Backend MUST expose `GET /api/v1/jobs/transitions` returning `{statuses: string[], transitions: {from: string, to: string}[]}` — the same graph defined in `app.domain.enums.JOB_TRANSITIONS`. This endpoint MUST require authentication and MUST be RLS-safe (it returns static enums, no user data).
- **FR-010**: Frontend MUST fetch `GET /api/v1/jobs/transitions` once per session (TanStack Query, `staleTime: Infinity`) and derive the status tab set, the status menu options, and the "Active" stat composition from that response. If the fetch fails, the UI MUST fall back to a small built-in copy AND show a non-blocking banner warning that statuses may be stale.

### Key Entities

- **JobStatus**: An enum with exactly seven values matching the backend: `applied`, `test`, `oa`, `hr`, `offer`, `rejected`, `withdrawn`. Each has a Chinese label for display.
- **JobStatusTransition**: A directed edge in the lifecycle graph. The full transition table is provided by the backend `JOB_TRANSITIONS` and is the source of truth.
- **JobStats**: Per-status counts plus a total. The UI consumes the same `counts` map; only the rendering changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A job in `applied` can be advanced to `offer` through the UI in 3 clicks (open row menu → pick `test` → pick `offer` after a second advance) without producing any HTTP 409 response.
- **SC-002**: 100% of status-tab counts in the UI match the per-status counts returned by `GET /api/v1/jobs/stats` for the same user, in any seeded scenario.
- **SC-003**: An invalid transition (a 409 response) is shown to the user as an inline error within one interaction and never silently rolls the status back without a visible message.
- **SC-004**: An E2E test passes that covers both the happy path (`applied → test → oa → hr → offer`) and the failure path (forcing a 409 from the backend) on the same row.
- **SC-005**: All seven real backend statuses appear as tabs, and the previous phantom statuses (`screening`, `interview`) no longer appear anywhere in the UI or in any URL state.

## Assumptions

- The backend `JOB_TRANSITIONS` and `JobStatus` enum remain the source of truth. The new `GET /api/v1/jobs/transitions` endpoint is a thin, static read of the same in-process data and is safe to cache.
- The existing `GET /api/v1/jobs` and `GET /api/v1/jobs/stats` endpoints already return all the user-scoped data this slice needs; the only backend addition is `GET /api/v1/jobs/transitions`.
- Tab URL state is intentionally out of scope for this slice — tab state can stay in React state.
- The search input on the page continues to operate per-tab (filter the rows of the active tab), and is not changed by this slice.
- The `all` tab shows every owned, non-deleted job, in `created_at` descending order, and is unchanged by this slice other than including the previously hidden `test/oa/hr/withdrawn` records.
