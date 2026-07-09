# Tasks: 姹傝亴璁粌鎸囨尌鍙帮紙宸ヤ綔鍙伴椤碉級

**Input**: Design documents from `/specs/057-dashboard-home-optimize/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included (Constitution III Test-First + quickstart validation). Write failing tests before implementation in each story where marked.

**Organization**: Phases by user story (P1 US1鈥揢S5 = MVP; P2 US6鈥揢S10 follow).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no incomplete deps)
- **[Story]**: `[US1]`鈥[US10]` on story-phase tasks only
- Paths are repo-relative from workspace root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create module/hook skeletons and wire routing so later stories can fill behavior.

- [x] T001 Create package skeleton `backend/app/modules/dashboard/` with `__init__.py`, empty `api.py`, `service.py`, `schemas.py`, `cache.py`, `activity_labels.py`, `funnel.py`, `cli.py`
- [x] T002 [P] Create evidence dir placeholder `docs/evidence/057-dashboard-home-optimize/README.md` noting MVP validation target
- [x] T003 [P] Create FE hook stub `src/hooks/queries/useDashboardSummary.ts` exporting `DASHBOARD_SUMMARY_KEY` and a typed `useDashboardSummary` that calls `GET /api/v1/me/dashboard-summary` (may 404 until T011)
- [x] T004 Mount dashboard router in `backend/app/api/v1/__init__.py` as `GET` under `/me/dashboard-summary` (prefix consistent with [contracts/dashboard-summary.md](./contracts/dashboard-summary.md))

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schemas, label/funnel/cache primitives, failing contract suite, auth non-reblock 鈥?**blocks all user stories**.

**鈿狅笍 CRITICAL**: No user-story UI/endpoint completion until this phase passes its checkpoint.

- [x] T005 [P] Implement Pydantic response models for `DashboardSummary` / L0 / L1 / L2 in `backend/app/modules/dashboard/schemas.py` per [data-model.md](./data-model.md)
- [x] T006 [P] Implement activity label map in `backend/app/modules/dashboard/activity_labels.py` per [contracts/activity-labels.md](./contracts/activity-labels.md)
- [x] T007 [P] Implement funnel aggregation helpers in `backend/app/modules/dashboard/funnel.py` (applying / interviewing / awaiting_feedback) per research R5
- [x] T008 [P] Implement Redis get/set/delete helpers in `backend/app/modules/dashboard/cache.py` with key `dashboard_summary:{user_id}:{local_date}` per [contracts/cache-invalidation.md](./contracts/cache-invalidation.md)
- [x] T009 [P] Add failing contract tests in `backend/tests/contract/test_dashboard_summary_schema.py` asserting schema + known activity titles never equal raw `type`
- [x] T010 [P] Add failing unit tests in `backend/tests/unit/test_activity_labels.py` and `backend/tests/unit/test_dashboard_funnel.py`
- [x] T011 Implement `DashboardService.build_summary` skeleton in `backend/app/modules/dashboard/service.py` (tz 鈫?local_date, empty L0/L1/L2, cache miss path) and wire `backend/app/modules/dashboard/api.py` to return it
- [x] T012 Implement `dump-summary` CLI in `backend/app/modules/dashboard/cli.py` per [contracts/cli.md](./contracts/cli.md)
- [x] T013 Fix auth non-reblock in `src/hooks/queries/useCurrentUser.ts`: when store already has user + tokens, refetch/`isFetching` MUST NOT set status to `unknown` (REQ-037 minimal); add/adjust test under `src/hooks/queries/__tests__/` or nearest existing auth test file
- [x] T014 [P] Add shared FE invalidation helper `src/hooks/queries/invalidateDashboardSummary.ts` (or export from `useDashboardSummary.ts`) calling `queryClient.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY })`

**Checkpoint**: `GET /api/v1/me/dashboard-summary` returns valid empty-ish schema for authenticated user; label/funnel unit tests can go green for pure helpers; auth refetch no longer full-screen blocks.

---

## Phase 3: User Story 1 鈥?浠婃棩鎸囨尌鍙?(Priority: P1) 馃幆 MVP

**Goal**: L0 鎯呭鍙?+ 涓嬩竴鍦洪潰璇曟彁绀?+ 涓?CTA锛涙寚鏍囧彲鐐广€佹棤鍋囨定璺岋紱灏忓睆涓?CTA 鍙揪銆?
**Independent Test**: 鏈変粖鏃ラ潰璇?/ 鏃犱粖鏃?/ 鏂扮敤鎴蜂笁绉嶈处鍙锋墦寮€宸ヤ綔鍙帮紝鎯呭鍙ヤ笌涓?CTA 姝ｇ‘锛涚獎瑙嗗彛浠嶈涓?CTA銆?
### Tests

- [x] T015 [P] [US1] Add Vitest fixtures for Dashboard L0 hero states in `src/pages/__tests__/Dashboard.commandCenter.test.tsx` (or `src/pages/__tests__/Dashboard.test.tsx`)
- [x] T016 [P] [US1] Add Playwright smoke skeleton `tests/e2e/057-dashboard-command-center/l0-hero.spec.ts` asserting primary CTA visible at mobile viewport

### Implementation

- [x] T017 [US1] Extend `backend/app/modules/dashboard/service.py` to populate `l0.greeting_context`, `l0.next_interview`, `l0.primary_cta` from jobs + onboarding emptiness rules
- [x] T018 [US1] Rewrite L0 hero in `src/pages/Dashboard.tsx`: greeting + context line + primary/secondary CTAs; remove decorative-only emoji dependency; hide fake growth deltas on stat chips
- [x] T019 [US1] Ensure mobile primary CTA remains in-flow or sticky in `src/pages/Dashboard.tsx` (md breakpoint must not hide the only CTA)
- [x] T020 [US1] Make remaining stat chips navigate to `/resume`, `/interview`, `/ability-profile` (or product-correct routes) in `src/pages/Dashboard.tsx`

**Checkpoint**: US1 demoable with summary-driven hero even if today list still incomplete.

---

## Phase 4: User Story 2 鈥?浠婃棩闈㈣瘯鍒楄〃 (Priority: P1) 馃幆 MVP

**Goal**: 銆屼粖鏃ュ緟鍔炪€? 浠婃棩闈㈣瘯宀椾綅鍒楄〃锛涘彲璺宠浆锛涙棤鍕鹃€夛紱銆屽叏閮ㄣ€嶈繘姹傝亴杩借釜銆?
**Independent Test**: 浠婂ぉ 2 / 鏄庡ぉ 1 鈫?鍒楄〃鎭板ソ 2锛涚偣鍑昏繘宀椾綅銆?
### Tests

- [x] T021 [P] [US2] Add integration cases in `backend/tests/integration/test_dashboard_summary.py` seeding today/tomorrow `interview_time` jobs and asserting `today_interviews` length
- [x] T022 [P] [US2] Extend E2E `tests/e2e/057-dashboard-command-center/today-interviews.spec.ts` for count + navigation

### Implementation

- [x] T023 [US2] Implement today-interview SQL/filter in `backend/app/modules/dashboard/service.py` (`interview_time` in `tz` local_date); fill `l0.today_interviews` + `relative_label` (鍚凡杩囩偣)
- [x] T024 [US2] Replace tasks-based銆屼粖鏃ュ緟鍔炪€峌I in `src/pages/Dashboard.tsx` with summary `today_interviews`; remove checkbox visuals; wire item click +銆屽叏閮ㄣ€嶁啋 jobs list
- [x] T025 [US2] Remove `useTasks` usage from `src/pages/Dashboard.tsx` for this panel

**Checkpoint**: US2 independently verifiable via API + UI.

---

## Phase 5: User Story 3 鈥?绠€鍘嗗尯瀵归綈绠€鍘嗕腑蹇?(Priority: P1) 馃幆 MVP

**Goal**: 鏍?娲剧敓鎽樿涓庣畝鍘嗕腑蹇冧竴鑷达紱绌烘€佸紩瀵硷紱寤鸿渚с€屾湁绠€鍘嗐€嶅垽鏂纭€?
**Independent Test**: 鏈夋牴+娲剧敓璐﹀彿鎽樿涓€鑷村彲鐐癸紱鏃犵畝鍘嗙┖鎬佹棤銆岀畝鍘嗗垎鏀€嶄富鏍囬銆?
### Tests

- [x] T026 [P] [US3] Extend `backend/tests/integration/test_dashboard_summary.py` for `resume_summaries` / `resume_counts` against seeded v2 resumes
- [x] T027 [P] [US3] Add Vitest assert in `src/pages/__tests__/Dashboard.commandCenter.test.tsx` that branch stub empty-state title is gone when summary has resumes

### Implementation

- [x] T028 [US3] Populate `l1.resume_summaries` + `resume_counts` in `backend/app/modules/dashboard/service.py` via resumes_v2 list projection
- [x] T029 [US3] Replace銆屾垜鐨勭畝鍘嗗垎鏀€峛lock in `src/pages/Dashboard.tsx` with root/derived cards from summary; links match resume center editor routes; empty 鈫?`/resume`
- [x] T030 [US3] Delete Dashboard imports/usages of `useResumeBranches` in `src/pages/Dashboard.tsx` (and suggestion inputs in later US4)

**Checkpoint**: Resume panel matches center; no v1 branch dependency on Dashboard.

---

## Phase 6: User Story 4 鈥?鍗曚竴銆屼笅涓€姝ャ€嶅缓璁?(Priority: P1) 馃幆 MVP

**Goal**: 浠呬竴涓缓璁潰鏉匡紱鐪熷疄鏁版嵁鍒嗘。锛涙棤銆屽疄鏃躲€嶅窘绔狅紱鏈?v2 绠€鍘嗕笉鎻愮ず鏃犵畝鍘嗐€?
**Independent Test**: 涓夋。澶瑰叿锛涘弻鏍忓悓鏂囨秷澶便€?
### Tests

- [x] T031 [P] [US4] Add unit/contract coverage for `next_action` tier inputs in `backend/tests/unit/test_dashboard_next_action.py` (or extend service tests)
- [x] T032 [P] [US4] Vitest: single suggestion panel + no銆屽疄鏃躲€峛adge in `src/pages/__tests__/Dashboard.commandCenter.test.tsx`

### Implementation

- [x] T033 [US4] Implement `l1.next_action` builder in `backend/app/modules/dashboard/service.py` (tier 0/1/2; `has_resume` from v2 counts; no fake copy)
- [x] T034 [US4] Refactor `src/hooks/useDashboardSuggestions.ts` to prefer summary `next_action` (or remove hook and read summary directly in page)
- [x] T035 [US4] Merge AI + 鎻愬崌寤鸿 into one銆屼笅涓€姝ャ€峱anel in `src/pages/Dashboard.tsx`; remove duplicate list and銆屽疄鏃躲€岯adge

**Checkpoint**: One honest next-action panel driven by real counts.

---

## Phase 7: User Story 5 鈥?棣栧睆棰勭畻涓庢憳瑕佺紦瀛?(Priority: P1) 馃幆 MVP

**Goal**: L0 涓嶆尅浜?L2锛汻edis 缂撳瓨闅旂/澶辨晥锛涗簩娆¤繘鍏?SWR锛沵utation 澶辨晥銆?
**Independent Test**: L2 寤惰繜鏃?L0 鍙偣锛汚/B 涓嶄覆璇伙紱鏀归潰璇曟椂闂村悗鍒楄〃鏇存柊銆?
### Tests

- [x] T036 [P] [US5] Add cache isolation + invalidate cases in `backend/tests/integration/test_dashboard_summary_cache.py`
- [x] T037 [P] [US5] Vitest/React Query test that `useDashboardSummary` uses `placeholderData` previous in `src/hooks/queries/__tests__/useDashboardSummary.test.ts`

### Implementation

- [x] T038 [US5] Wire cache read/write in `backend/app/modules/dashboard/service.py` + hit/miss structured logs; TTL 60s
- [x] T039 [US5] Call cache delete from job write paths in `backend/app/modules/jobs/service.py` (create/update/status/`interview_time`)
- [x] T040 [P] [US5] Call cache delete from resume v2 / derive write paths (touch the service modules that commit resume changes under `backend/app/modules/resumes_v2/` and `backend/app/modules/resume_derive/` as applicable)
- [x] T041 [P] [US5] Call cache delete from interview session status transitions in `backend/app/modules/interviews/service.py` and activity log writes in `backend/app/modules/activities/service.py` (or shared helper)
- [x] T042 [US5] Progressive render in `src/pages/Dashboard.tsx`: L0 skeleton鈫抎ata first; L2 panels independent error/empty; no whole-page blank on L2 failure
- [x] T043 [US5] Add `invalidateDashboardSummary` to FE mutation `onSuccess` in `src/hooks/mutations/useJobMutations.ts` and parallel resume/interview mutation hooks that Dashboard depends on

**Checkpoint**: MVP (US1鈥揢S5) ready for quickstart 搂1鈥? smoke.

---

## Phase 8: User Story 6 鈥?姹傝亴婕忔枟 (Priority: P2)

**Goal**: 涓夋鍙偣婕忔枟锛涜鏁版纭紱鏃犲矖浣嶇┖鎬併€?
**Independent Test**: 澶氱姸鎬佸矖浣嶈鏁颁竴鑷达紱鐐瑰嚮杩涜繃婊ゅ垪琛ㄣ€?
### Tests

- [x] T044 [P] [US6] Extend funnel assertions in `backend/tests/unit/test_dashboard_funnel.py` + integration seed in `backend/tests/integration/test_dashboard_summary.py`

### Implementation

- [x] T045 [US6] Populate `l1.job_funnel` in `backend/app/modules/dashboard/service.py` using `funnel.py` (do not use legacy `JobRepository.stats` old keys)
- [x] T046 [US6] Render clickable funnel strip in `src/pages/Dashboard.tsx` with empty-state CTA to `/jobs`

**Checkpoint**: Funnel answers銆屾姇閫掑崱鍦ㄥ摢銆嶃€?
---

## Phase 9: User Story 7 鈥?闈㈣瘯鍑嗗鍖?(Priority: P2)

**Goal**: 浠婃棩/涓嬩竴鍦?鈫?宀椾綅 + 娲剧敓绠€鍘嗘垨鍘绘淳鐢?+ 鍙€夋ā鎷熷叆鍙ｃ€?
**Independent Test**: 鏈?鏃?`derived` 缁戝畾鐨勪粖鏃ュ矖浣嶅噯澶囪矾寰勬纭€?
### Tests

- [x] T047 [P] [US7] Integration fixture for prep_pack with/without derived resume in `backend/tests/integration/test_dashboard_summary.py`

### Implementation

- [x] T048 [US7] Build `l1.prep_pack` in `backend/app/modules/dashboard/service.py` (job_id, derived_resume_id, actions)
- [x] T049 [US7] Render prep actions on today/next interview row or card in `src/pages/Dashboard.tsx`; hide unsupported mock-interview deep-link rather than dead-link

**Checkpoint**: Prep path usable without leaving command center first click.

---

## Phase 10: User Story 8 鈥?鏂扮敤鎴蜂笁姝ュ喎鍚姩 (Priority: P2)

**Goal**: 绠€鍘?鈫?宀椾綅 鈫?棣栧満闈㈣瘯杩涘害鏉★紱瀹屾垚鍚庨€€鍑?L0銆?
**Independent Test**: 鏂拌处鍙疯涓夋锛涘畬鎴愪竴姝ヨ繘搴︽洿鏂帮紱涓夋鍚庢秷澶便€?
### Tests

- [x] T050 [P] [US8] Unit/integration for onboarding step flags in `backend/tests/unit/test_dashboard_onboarding.py` (or service tests)

### Implementation

- [x] T051 [US8] Populate `l0.onboarding` in `backend/app/modules/dashboard/service.py` (`show` when any step incomplete)
- [x] T052 [US8] Render onboarding stepper in L0 of `src/pages/Dashboard.tsx`; current step drives primary CTA; hide when complete

**Checkpoint**: Cold-start no longer multi empty-state pile.

---

## Phase 11: User Story 9 鈥?缁х画鏈畬鎴?(Priority: P2)

**Goal**: 杩涜涓ā鎷熼潰璇曘€岀户缁€嶅叆鍙ｏ紱缁撴潫鍚庢秷澶便€?
**Independent Test**: `in_progress`/`pending` session 鈫?continue锛沜ompleted 鈫?鏃犲叆鍙ｃ€?
### Tests

- [x] T053 [P] [US9] Integration seed resumable sessions in `backend/tests/integration/test_dashboard_summary.py`

### Implementation

- [x] T054 [US9] Populate `l0.resumable_sessions` (鈮?) in `backend/app/modules/dashboard/service.py` with href `/interview/{id}/live`
- [x] T055 [US9] Render銆岀户缁潰璇曘€峛lock in `src/pages/Dashboard.tsx` only when list non-empty

**Checkpoint**: Interrupt recovery visible on home.

---

## Phase 12: User Story 10 鈥?鏈€杩戞椿鍔ㄥ彲璇?(Priority: P2)

**Goal**: 娲诲姩涓枃鏍囬锛涙湭鐭ョ被鍨嬩腑鎬у洖閫€锛涘彲鐐瑰垯璺宠浆銆?
**Independent Test**: 鎶芥鏃?raw `job_created` 浣滃敮涓€鏍囬銆?
### Tests

- [x] T056 [P] [US10] Integration assert `recent_activities[].title_zh == "鏂板鎶曢€?` for seeded `job_created` in `backend/tests/integration/test_dashboard_summary.py`
- [x] T057 [P] [US10] E2E `tests/e2e/057-dashboard-command-center/activities-zh.spec.ts` forbids raw type strings in activity titles

### Implementation

- [x] T058 [US10] Fill `l2.recent_activities` via `activity_labels.py` in `backend/app/modules/dashboard/service.py`
- [x] T059 [US10] Replace `getActivityDisplay` raw-type fallback in `src/pages/Dashboard.tsx` to consume `title_zh`/`detail_zh` (optional thin `src/lib/activityLabels.ts` fallback only for unknown)
- [x] T060 [P] [US10] Populate lightweight `l2.ability_snapshot` + `interview_trend` in `backend/app/modules/dashboard/service.py` and render existing L2 panels from summary (defer-friendly)

**Checkpoint**: Activities trustworthy; L2 fully summary-driven.

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Quickstart green, evidence, status docs, cleanup.

- [x] T061 Run [quickstart.md](./quickstart.md) backend contract/unit/integration suite and fix regressions
- [x] T062 [P] Run FE unit + Playwright `tests/e2e/057-dashboard-command-center/` and record notes under `docs/evidence/057-dashboard-home-optimize/`
- [x] T063 [P] Update `specs/057-dashboard-home-optimize/requirements-status.md` story statuses to `in_progress`/`done` as verified
- [x] T064 Remove dead Dashboard code paths (unused imports, dual suggestion remnants, tasks panel leftovers) in `src/pages/Dashboard.tsx` and related hooks
- [x] T065 [P] Confirm panel intake note in `specs/057-dashboard-home-optimize/README.md` (new panels default L2)
- [x] T066 Optional: fix `JobRepository.stats` old keys in `backend/app/modules/jobs/repository.py` so `/jobs/stats` matches FSM (non-blocking for summary funnel)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup** 鈫?no deps
- **Phase 2 Foundational** 鈫?blocks all stories
- **Phases 3鈥? (US1鈥揢S5)** 鈫?MVP; prefer sequential US1鈫扷S2鈫扷S3鈫扷S4鈫扷S5 (shared `Dashboard.tsx` / `service.py`)
- **Phases 8鈥?2 (US6鈥揢S10)** 鈫?after MVP; can parallelize across BE service slices vs FE panels if staffed
- **Phase 13 Polish** 鈫?after desired stories complete

### User Story Dependencies

| Story | Depends on | Notes |
|---|---|---|
| US1 | Phase 2 | Hero can use partial summary |
| US2 | Phase 2; soft-dep US1 | Same L0 region |
| US3 | Phase 2 | L1 resumes |
| US4 | US3 counts preferred | `has_resume` must use v2 |
| US5 | US1鈥揢S4 fields exist | Cache wraps full builder |
| US6鈥揢S10 | Phase 2 + preferably US5 cache hooks | Independently testable panels |

### Parallel Opportunities

- T002/T003; T005鈥揟010; T015/T016; T021/T022; T026/T027; T031/T032; T036/T037; T040/T041; T044; T047; T050; T053; T056/T057/T060; T062/T063/T065
- After Foundational: BE label/funnel tests vs FE auth test (T013) already in Phase 2
- P2 stories: US6 funnel BE vs US10 labels largely parallel; FE panel work serializes on `Dashboard.tsx` 鈥?prefer one owner for that file

### Parallel Example: Foundational helpers

```text
T005 schemas.py
T006 activity_labels.py
T007 funnel.py
T008 cache.py
T009 contract tests
T010 unit tests
```

### Parallel Example: US5 invalidation writers

```text
T039 jobs/service.py invalidate
T040 resumes_v2 / resume_derive invalidate
T041 interviews + activities invalidate
```

---

## Implementation Strategy

### MVP First (US1鈥揢S5)

1. Phase 1 + Phase 2  
2. US1 鈫?US2 鈫?US3 鈫?US4 鈫?US5  
3. **STOP**: Run quickstart 搂1鈥?; demo command center  
4. Then US6鈥揢S10 incrementally  

### Incremental Delivery

1. Foundation 鈫?empty summary + auth fix  
2. L0 hero + today list 鈫?鈥渢oday command center鈥?demo  
3. Resumes + single next-action 鈫?trust restored  
4. Cache + progressive render 鈫?performance bar  
5. Funnel / prep / onboarding / continue / activities 鈫?full REQ  

### Suggested MVP Scope

**US1 + US2 + US3 + US4 + US5** (not US1 alone) 鈥?matches plan.md P1 MVP definition.

---

## Notes

- Constitution Test-First: keep story tests failing before implementation where listed  
- Do not reintroduce `useResumeBranches` or tasks-as-today-todos  
- Cache keys always include `user_id` + `local_date`  
- Commit after each story checkpoint when possible  
- `tasks.md` is the execution checklist for `/speckit-implement`  
