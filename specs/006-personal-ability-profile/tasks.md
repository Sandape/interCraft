# Tasks: Personal Ability Profile

**Input**: Design documents from `specs/006-personal-ability-profile/`
- [plan.md](./plan.md) (tech stack, structure, decisions)
- [spec.md](./spec.md) (7 user stories, P1-P3)
- [research.md](./research.md) (5 technical decisions)
- [data-model.md](./data-model.md) (3 new tables)
- [contracts/](./contracts/) (profile, share, export, admin)
- [quickstart.md](./quickstart.md) (6 validation scenarios)

**Scope**: Feature 006 — Personal Ability Profile. All 7 user stories.
**Tests**: REQUIRED by Constitution III (Test-First). Every non-trivial task has a test task that must FAIL before implementation.

## Format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: Required for US phases — `[US1]` / `[US2]` / `[US3]` / etc.
- **Phase labels**: Setup / Foundational / US phases / Polish use no story label
- **File paths** are exact (`backend/app/...`, `src/...`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependencies, migration skeleton, module directory structure.

- [X] T001 Add `playwright` dependency to `backend/pyproject.toml` (PDF generation)
- [X] T002 [P] Install Playwright Chromium: `playwright install chromium` in CI/Docker
- [X] T003 Create migration placeholder at `backend/migrations/versions/0007_ability_profile.py` (3 new tables: `profile_share_links`, `profile_views`, `export_logs`)
- [X] T004 [P] Create frontend page directory at `src/pages/AbilityProfile/` with `index.ts` re-export

**Checkpoint**: Dependencies declared, migration file created, frontend directory scaffolded.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: New backend module skeleton, models, and repository. MUST complete before any user story.

### Tests for Foundational (write FIRST, must FAIL)

- [X] T005 [P] Write model unit tests for `profile_share_links` at `backend/app/modules/ability_profile/tests/test_models.py` (test CHECK constraints: token length, revoked_at < expires_at, access_count >= 0)
- [X] T006 [P] Write model unit tests for `profile_views` at same `test_models.py` (test append-only, ip_prefix length)
- [X] T007 [P] Write model unit tests for `export_logs` at same `test_models.py` (test status enum, completed status requires file_path, status transitions)

### Backend Module Skeleton & Models

- [X] T08 Create backend module package at `backend/app/modules/ability_profile/__init__.py` and `backend/app/modules/ability_profile/README.md`
- [X] T009 [P] Create `ProfileShareLink` model in `backend/app/modules/ability_profile/models.py` (from data-model.md §1: fields, constraints, indexes, state machine)
- [X] T010 [P] Create `ProfileView` model in `backend/app/modules/ability_profile/models.py` (from data-model.md §2: append-only access log)
- [X] T011 [P] Create `ExportLog` model in `backend/app/modules/ability_profile/models.py` (from data-model.md §3: export tracking with status machine)
- [X] T012 Create repository at `backend/app/modules/ability_profile/repository.py` (CRUD for share_links, export_logs; query active links per user; paginate views)
- [X] T013 [P] Create Pydantic schemas at `backend/app/modules/ability_profile/schemas.py` (DashboardResponse, ShareLinkCreate/Response, ExportResponse, AdminViewResponse)
- [X] T014 [P] Create module CLI at `backend/app/modules/ability_profile/cli.py` (principle II: `list-links`, `revoke-expired`, `list-exports` commands with `--json`)
- [X] T015 Create migration at `backend/migrations/versions/0007_ability_profile.py` (creates `profile_share_links`, `profile_views`, `export_logs` with RLS policies and indexes per data-model.md)

**Checkpoint**: Foundation ready — 3 tables migrated, models + repository tested, CLI verified.

---

## Phase 3: User Story 1 — View Ability Profile Dashboard (P1) 🎯 MVP

**Goal**: Users see a radar chart of their 6 ability dimensions with actual vs ideal scores, and an ability list with trend indicators.

**Independent Test**: Navigate to `/ability-profile` and verify radar chart renders 6 dimensions with data from existing ability_dimensions API.

### Tests for US1 (write FIRST, must FAIL)

- [ ] T016 [P] [US1] Write unit test for dashboard aggregation service at `backend/app/modules/ability_profile/tests/test_service.py` (mock ability_dimensions data, verify dashboard response shape, trend calculation)
- [ ] T017 [P] [US1] Write integration test for dashboard API at `backend/tests/integration/test_ability_profile.py` (seed ability_dimensions rows, call `GET /api/v1/ability-profile/dashboard`, verify response)

### Backend: Dashboard Service & API

- [X] T018 [US1] Implement dashboard service at `backend/app/modules/ability_profile/service.py` — `get_dashboard(user_id)` reads existing ability_dimensions, calculates trends (compare last 2 history points), returns aggregated response
- [X] T019 [US1] Implement dashboard API at `backend/app/modules/ability_profile/api.py` — `GET /api/v1/ability-profile/dashboard` returns aggregated profile (calls service, requires auth)
- [X] T020 [P] [US1] Mount ability profile router at `backend/app/api/v1/__init__.py` (add `ability_profile.router` to v1 router)

### Frontend: Radar Chart & Dashboard Page

- [X] T021 [P] [US1] Create API client at `src/api/abilityProfileClient.ts` (fetch dashboard data, TypeScript types matching contracts/profile.md)
- [X] T022 [P] [US1] Create React Query hook at `src/pages/AbilityProfile/hooks/queries/useAbilityProfile.ts` (useQuery for dashboard data, staleTime = 30s)
- [X] T023 [US1] Create RadarChart component at `src/pages/AbilityProfile/RadarChart.tsx` (recharts RadarChart with PolarGrid + PolarAngleAxis + 2 Radars for actual vs ideal; 6-axis labels from dimensions-meta endpoint)
- [X] T024 [US1] Create AbilityCard component at `src/pages/AbilityProfile/AbilityCard.tsx` (single dimension card: label, actual score, ideal score, trend arrow up/down/stable)
- [X] T025 [US1] Create AbilityProfile page at `src/pages/AbilityProfile.tsx` (layout: radar chart top, ability list below; empty state when no dimensions active; loading skeleton)
- [X] T026 [US1] Add route `/ability-profile` in `src/App.tsx` (lazy-loaded, requires auth)

**Checkpoint**: US1 complete — user sees radar chart of all 6 dimensions with actual vs ideal, ability cards with trends.

---

## Phase 4: User Story 2 — Self-Assess Abilities (P1)

**Goal**: Users can self-assess their proficiency on each dimension via an intuitive UI.

**Independent Test**: Open ability detail, set self-assessment score, verify radar chart updates.

### Tests for US2 (write FIRST, must FAIL)

- [ ] T027 [P] [US2] Write integration test for self-assessment at `backend/tests/integration/test_ability_profile.py` (PATCH ability-dimensions, verify updated score reflected in dashboard)

### Backend: Self-Assessment (reuses existing PATCH endpoint)

- [X] T028 [US2] Add self-assessment service method in `backend/app/modules/ability_profile/service.py` — `self_assess(user_id, dimension_key, score, notes)` calls existing ability_dimensions PATCH endpoint logic
- [X] T029 [US2] Add self-assessment notes field support — ensure free-text notes/evidence stored and returned in dashboard

### Frontend: Self-Assessment UI

- [X] T030 [P] [US2] Create self-assessment mutation hook at `src/pages/AbilityProfile/hooks/mutations/useSelfAssess.ts` (useMutation → PATCH ability-dimensions, invalidate dashboard query on success)
- [X] T031 [US2] Create AbilityDetail component at `src/pages/AbilityProfile/AbilityDetail.tsx` (slider or clickable scale 0-10, notes textarea, submit button)
- [X] T032 [US2] Add edit button to AbilityCard → opens AbilityDetail in a modal/inline editor
- [X] T033 [US2] Add route `/ability-profile/:abilityKey` in `src/App.tsx` (ability detail page with self-assessment + history)

**Checkpoint**: US2 complete — user can self-assess any dimension, score appears on radar chart in a different color/layer.

---

## Phase 5: User Story 3 — View System-Assessed Abilities from Interviews (P2)

**Goal**: System scores from interview evaluations appear automatically on the profile dashboard as a separate assessment source.

**Independent Test**: Complete an interview that evaluates a dimension, then verify the dashboard shows the system score.

### Tests for US3 (write FIRST, must FAIL)

- [ ] T034 [P] [US3] Write integration test for system score propagation at `backend/tests/integration/test_ability_profile.py` (seed interview score data in ability_dimensions with source='interview', verify dashboard includes it)

### Backend: System Score Integration

- [X] T035 [US3] Add score aggregation logic in `backend/app/modules/ability_profile/service.py` — `aggregate_system_scores(user_id)`: collect ability_dimensions records where source = 'interview' or source = 'coach', compute time-weighted average per dimension (linear decay per research.md R-5)
- [X] T036 [US3] Update dashboard service to include `self_assessed_score` field — when user has manually set score (source='manual'), include as separate radar dimension; system score from aggregate_system_scores() becomes default actual_score

### Frontend: System Score Display

- [X] T037 [US3] Update RadarChart to show 3 layers when applicable: actual (system), ideal, self-assessed, with proper legend
- [X] T038 [US3] Update AbilityCard to show both scores when different: "系统 6.5 / 自评 7.0"

**Checkpoint**: US3 complete — radar chart shows both system-assessed and self-assessed scores.

---

## Phase 6: User Story 4 — Share Ability Profile (P3)

**Goal**: Users generate revocable share links; anyone with the link views a read-only profile.

**Independent Test**: Generate share link, open in incognito, verify read-only radar chart displays.

### Tests for US4 (write FIRST, must FAIL)

- [ ] T039 [P] [US4] Write integration test for share link lifecycle at `backend/tests/integration/test_ability_profile.py` (create → verify public access → revoke → verify 404)

### Backend: Share Link CRUD & Public Access

- [X] T040 [P] [US4] Implement share service in `backend/app/modules/ability_profile/service.py` — `create_share_link(user_id, pin?, expires_in?)`, `revoke_share_link(link_id)`, `list_share_links(user_id)`
- [X] T041 [US4] Implement share API at `backend/app/modules/ability_profile/api.py` — `POST /api/v1/ability-profile/share` (create, rate limit: 10 active per user), `GET /api/v1/ability-profile/share` (list), `DELETE /api/v1/ability-profile/share/{id}` (revoke)
- [X] T042 [US4] Implement public access endpoint — `GET /api/v1/ability-profile/share/{token}` (no auth, returns read-only profile, logs view, rate limit: 10/min/IP)
- [X] T043 [US4] Add PIN verification — bcrypt hash on create, verify on access; if PIN set and not provided, return 401

### Frontend: Share Dialog & Public Page

- [X] T044 [P] [US4] Create share mutation hooks at `src/pages/AbilityProfile/hooks/mutations/useShareLink.ts` (createShareLink, revokeShareLink)
- [X] T045 [US4] Create ShareDialog component at `src/pages/AbilityProfile/ShareDialog.tsx` (generate link UI, copy to clipboard, PIN option, expiry dropdown, list of active links with revoke button)
- [X] T046 [US4] Create SharedAbilityProfile page at `src/pages/SharedAbilityProfile.tsx` (public read-only page: radar chart + ability list + "Profile shared by [name]"; no edit controls, no nav shell)
- [X] T047 [US4] Add route `/shared/:shareToken` in `src/App.tsx` (public route, no auth)

**Checkpoint**: US4 complete — user can generate, copy, and revoke share links; public page renders read-only profile.

---

## Phase 7: User Story 5 — Track Ability Growth Over Time (P3)

**Goal**: Users see timeline charts showing how each dimension has changed over time.

**Independent Test**: Navigate to ability detail page, verify timeline chart renders historical data from ability_dimensions_history.

### Tests for US5 (write FIRST, must FAIL)

- [ ] T048 [P] [US5] Write integration test for growth timeline at `backend/tests/integration/test_ability_profile.py` (seed history records, verify dashboard returns history array)

### Backend: History Data (reuses existing endpoint)

- [X] T049 [US5] Dashboard service already includes `history` from ability_dimensions_history — verify data flow, add aggregation parameters if needed

### Frontend: Timeline Chart

- [X] T050 [P] [US5] Create TimelineChart component at `src/pages/AbilityProfile/TimelineChart.tsx` (recharts LineChart with actual_score + ideal_score lines over time; x-axis = date, y-axis = score 0-10)
- [X] T051 [US5] Integrate TimelineChart into AbilityDetail page at `/ability-profile/:abilityKey` (shows growth trajectory below the current scores)
- [X] T052 [US5] Update trend indicator on AbilityCard — color-coded arrow (green up, red down, gray stable)

**Checkpoint**: US5 complete — user sees growth curve for each dimension, ability cards show trend indicators.

---

## Phase 8: User Story 6 — Export Ability Profile as PDF (P3)

**Goal**: Users trigger a PDF export of their profile, download the result.

**Independent Test**: Click export, wait for completion, download and verify PDF file.

### Tests for US6 (write FIRST, must FAIL)

- [ ] T053 [P] [US6] Write unit test for PDF export service at `backend/app/modules/ability_profile/tests/test_service.py` (mock playwright, verify export_log status transitions)
- [ ] T054 [P] [US6] Write integration test for export endpoint at `backend/tests/integration/test_ability_profile.py` (POST export → GET status → verify flow)

### Backend: PDF Generation

- [X] T055 [US6] Implement PDF generation service at `backend/app/modules/ability_profile/pdf.py` (uses playwright-python: render profile HTML → page.pdf(); returns file path)
- [X] T056 [US6] Implement ARQ worker task at `backend/app/workers/tasks/pdf_export.py` (picks up pending export_log, calls pdf.py, updates status, error handling)
- [X] T057 [US6] Register PDF export cron/callback in `backend/app/workers/main.py`
- [X] T058 [US6] Implement export API at `backend/app/modules/ability_profile/api.py` — `POST /api/v1/ability-profile/export` (trigger, rate limit 5/h), `GET /api/v1/ability-profile/exports/{id}` (status), `GET /api/v1/ability-profile/exports/{id}/download` (serve file), `GET /api/v1/ability-profile/exports` (list)
- [ ] T059 [US6] Add file cleanup cron — schedule periodic cleanup of expired PDF files (> 24h)

### Frontend: Export UI

- [X] T060 [P] [US6] Create export mutation hook at `src/pages/AbilityProfile/hooks/mutations/useExportPDF.ts` (trigger export, poll status, download)
- [X] T061 [US6] Add export button to dashboard page — initiates export, shows progress, download link when ready

**Checkpoint**: US6 complete — user triggers PDF export, waits for completion, downloads valid PDF.

---

## Phase 9: User Story 7 — Admin Views User Ability Profile (P3)

**Goal**: Admin users can view any user's ability profile in read-only mode.

**Independent Test**: Admin navigates to `/admin/users/{id}/ability-profile`, sees the profile with no edit controls.

### Tests for US7 (write FIRST, must FAIL)

- [ ] T062 [P] [US7] Write integration test for admin view at `backend/tests/integration/test_ability_profile.py` (admin token → view another user's dashboard → 200; normal user → 403)

### Backend: Admin API

- [X] T063 [US7] Implement admin API at `backend/app/modules/ability_profile/api.py` — `GET /api/v1/ability-profile/admin/{user_id}` (calls dashboard service for target user; requires admin role check)
- [X] T064 [US7] Add admin role dependency — verify JWT or DB has `role=admin`; non-admin returns 403

### Frontend: Admin View

- [ ] T065 [US7] Create admin profile page (reuse AbilityProfile component with readOnly=true prop; no edit/share/export controls; shows "Viewing profile of: [user name]" header)
- [ ] T066 [US7] Add navigation link from user management UI to admin profile view

**Checkpoint**: US7 complete — admin sees any user's profile in read-only mode.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements across all user stories.

- [X] T067 [P] Add rate limit configs for new endpoints in `backend/app/core/rate_limit.py` (share link: 10 create/h/user, public access: 10/min/IP, export: 5/h/user)
- [X] T068 [P] Add audit logging at all share operations (create, revoke, access, export trigger, admin view) in `backend/app/modules/ability_profile/service.py`
- [X] T069 [P] Add Playwright E2E test at `tests/e2e/sc-ability-profile.spec.ts` (full flow: login → dashboard → self-assess → share → export → admin view)
- [ ] T070 [P] Run full validation against `specs/006-personal-ability-profile/quickstart.md` (all 6 scenarios pass)
- [X] T071 [P] Add empty state illustrations on dashboard when user has no ability data
- [X] T072 [P] Write CLI verification script at `scripts/verify-profile-aggregation.mjs` (validate time-weighted averaging from research.md R-5)

**Checkpoint**: All 7 user stories complete, E2E test passes, quickstart scenarios all green.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 Dashboard (Phase 3)**: Depends on Phase 2 — 🎯 **MVP**
- **US2 Self-Assessment (Phase 4)**: Depends on Phase 2. Reuses existing PATCH endpoint. Can start parallel with US1
- **US3 System Scores (Phase 5)**: Depends on Phase 3 (dashboard UI) + Phase 2. Requires Phase 4 interview scoring data
- **US4 Share (Phase 6)**: Depends on Phase 3 (dashboard read-only view). Independent of US2/US3
- **US5 Growth (Phase 7)**: Depends on Phase 3 (dashboard UI). Reuses existing history endpoint
- **US6 Export (Phase 8)**: Depends on Phase 3 (profile data). Independent of other US
- **US7 Admin (Phase 9)**: Depends on Phase 3 (dashboard service). Independent of other US
- **Polish (Phase 10)**: Depends on all desired US being complete

### User Story Dependencies

| Story | Depends On | Can Run Parallel With |
|---|---|---|
| US1 Dashboard | Phase 2 | — (base story) |
| US2 Self-Assessment | Phase 2, PATCH endpoint | US1 (separate UI) |
| US3 System Scores | Phase 2, US1 | US4, US5 (different services) |
| US4 Share | Phase 2, US1 | US2, US3, US5, US6 |
| US5 Growth | Phase 2, US1 | US2, US3, US4, US6 |
| US6 Export | Phase 2, US1 | US2, US3, US4, US5 |
| US7 Admin | Phase 2, US1 | US2, US3, US4, US5, US6 |

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Backend before frontend
- Story complete before moving to next phase

### Parallel Opportunities

- All T tasks marked [P] can run in parallel
- US2, US4, US5, US6, US7 can all be developed in parallel after Phase 2 + US1 are done
- Frontend tasks within a story can run in parallel with backend tasks for the same story

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 Dashboard
4. **STOP and VALIDATE**: Test US1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Add US1 (Dashboard) → **MVP!** User sees their profile
3. Add US2 (Self-Assessment) → User can contribute scores
4. Add US3 (System Scores) → Full dual-source profile
5. Add US4 (Share) → External visibility
6. Add US5 (Growth) → Long-term engagement
7. Add US6 (Export) → Offline use
8. Add US7 (Admin) → Internal operations

### Parallel Team Strategy

With multiple developers:

1. Complete Phase 1 + 2 together
2. Developer A: US1 (Dashboard) + US3 (System Scores)
3. Developer B: US2 (Self-Assessment) + US4 (Share)
4. Developer C: US5 (Growth) + US6 (Export)
5. All three: US7 (Admin) + Phase 10 Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [US1]-[US7] label maps task to specific user story
- Each user story is independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The existing `ability_dimensions` API (Phase 2) is NOT modified — all new code is additive
