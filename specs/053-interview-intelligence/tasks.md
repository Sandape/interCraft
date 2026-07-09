# Tasks: Interview Intelligence Engine

**Input**: Design documents from `/specs/053-interview-intelligence/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included per Constitution Principle III (Test-First) and SC-010 (E2E coverage mandate).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/`, `backend/migrations/`, `backend/tests/`
- **Frontend**: `frontend/src/`, `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding and new module skeleton

- [x] T001 Create research module directory structure per plan.md: `backend/app/modules/research/` with `__init__.py`, `models.py`, `schemas.py`, `repository.py`, `service.py`, `api.py`, `cli.py`, `report_generator.py`, `quality_checker.py`, `markdown_converter.py`
- [x] T002 [P] Create ARQ worker task file skeleton `backend/app/workers/tasks/interview_research.py`
- [x] T003 [P] Create backend test directories: `backend/tests/unit/modules/research/__init__.py`, `backend/tests/integration/test_research_pipeline.py`
- [x] T004 [P] Create Playwright E2E test file skeleton `frontend/tests/e2e/053-interview-intelligence.spec.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database Migration

- [x] T005 Create Alembic migration `backend/migrations/versions/0046_053_interview_research.py` with all DDL changes: add `interview_time` to `jobs`, create `interview_research_tasks` table, create `interview_research_results` table, extend `interview_reports` table (add `report_type`, `job_id`, `interview_time`, `research_task_id`, `rating` columns), create indexes, add foreign key constraints. Include `downgrade()` for full rollback.

### Domain Layer Changes

- [x] T006 [P] Update `JOB_TRANSITIONS` dict in `backend/app/domain/enums.py` to replace old 7-state model (applied/test/oa/hr/offer/rejected/withdrawn) with new 7-state model (applied/test/interview_1/interview_2/interview_3/failed/passed). See spec US1 transition matrix.
- [x] T007 [P] Update `JOB_STATUS_CN` dict in `backend/app/domain/enums.py` to map new states to Chinese labels: applied→已投递, test→笔试中, interview_1→一面中, interview_2→二面中, interview_3→三面中, failed→已失败, passed→已通过.

### Job Model Changes

- [x] T008 [P] Add `interview_time` column to `Job` model in `backend/app/modules/jobs/models.py`: `Column(TIMESTAMPTZ, nullable=True, default=None)`
- [x] T009 [P] Add `interview_time` field to `PatchJobInput` schema in `backend/app/modules/jobs/schemas.py`: `interview_time: datetime | None = Field(default=None)` with ISO 8601 validation
- [x] T010 Add `interview_time` field to `UpdateJobStatusInput` schema in `backend/app/modules/jobs/schemas.py`: `interview_time: datetime | None = Field(default=None)` with validation logic

### Interview Reports Extension

- [x] T011 Extend `interview_reports` table access in `backend/app/repositories/interview_report_repo.py`: add `create_research_report()` method for inserting research-type reports, add `get_by_job_id()` query, modify `create()` to support `report_type` parameter with backward-compatible default
- [x] T012 [P] Add research report Pydantic schemas to `backend/app/domain/interview_report.py`: `ResearchReportCreate`, `ResearchReportOut`, `ResearchReportListOut` with all new fields (report_type, job_id, interview_time, research_task_id, rating, delivery_status)

**Checkpoint**: Foundation ready — database schema migrated, domain enums updated, existing modules prepared for user story implementation

---

## Phase 3: User Story 7 — 存量数据迁移 (Priority: P1)

**Goal**: Existing job data is migrated from old 7-state model to new 7-state model with correct mapping and support for rollback

**Independent Test**: Run migration on test DB → verify all job statuses correctly mapped → verify `status_history` JSONB transformed → verify `downgrade()` restores original values → verify `GET /transitions` returns new state set

### Tests for US7

- [ ] T013 [P] [US7] Write Alembic migration unit test in `backend/tests/unit/modules/jobs/test_migration_053.py`: create jobs with all 7 old statuses, run upgrade, assert correct new statuses, run downgrade, assert restored
- [ ] T014 [P] [US7] Write status_history JSONB transformation test in `backend/tests/unit/modules/jobs/test_migration_053.py`: create history entries with old status values (oa, hr, offer, rejected, withdrawn), verify all `from`/`to` values transformed, verify note field preserves "原状态: rejected"

### Implementation for US7

- [x] T015 [US7] Implement `upgrade()` in `backend/migrations/versions/0046_053_interview_research.py`: status value UPDATE for all 7 mappings (applied→applied, test→test, oa→interview_1, hr→interview_2, offer→passed, rejected→failed, withdrawn→failed) + status_history JSONB transform using `jsonb_array_elements` + `jsonb_set`
- [x] T016 [US7] Implement `downgrade()` status restoration in migration: reverse mapping + restore original values from history note field where available
- [x] T017 [US7] Add `migrate-status` CLI command to `backend/app/modules/jobs/cli.py`: `--dry-run` flag to preview changes without executing, `--json` flag for machine output. Uses `asyncio.run()` pattern matching existing CLI commands.

**Checkpoint**: All existing job data migrated to new status model; migration is reversible; CLI dry-run works

---

## Phase 4: User Story 1 — 新状态模型下的求职追踪 (Priority: P1) 🎯 MVP

**Goal**: Users see new 7-state options, must set interview_time when advancing to interview rounds, terminal states block further transitions

**Independent Test**: Create applied job → advance to interview_1 with interview_time → verify saved → advance to passed without time picker → verify terminal state blocks further actions

### Tests for US1

- [ ] T018 [P] [US1] Write contract test for `GET /api/v1/jobs/transitions` in `backend/app/modules/jobs/tests/test_transitions.py`: assert returns new 7 statuses and correct transition edges per spec matrix
- [ ] T019 [P] [US1] Write integration test for status flow in `backend/tests/integration/test_jobs_status_053.py`: create job → advance to interview_1 with time → advance to interview_2 → advance to passed, verify each step's response and DB state

### Backend Implementation for US1

- [x] T020 [US1] Update `JobService.update_status()` in `backend/app/modules/jobs/service.py`: add validation that `interview_time` is required when `to` is test/interview_1/interview_2/interview_3; reject if `interview_time` is in the past (5-min tolerance); reject if `interview_time` provided when transitioning to applied/failed/passed
- [x] T021 [US1] Update `JobService.update_status()` in `backend/app/modules/jobs/service.py`: set `job.interview_time` from request when transitioning to interview-round states; clear `job.interview_time` when transitioning away from interview-round states (to failed/passed)
- [x] T022 [US1] Update `PATCH /{id}/status` handler in `backend/app/modules/jobs/api.py`: accept `interview_time` field from `UpdateJobStatusInput`, pass to service, return 422 with Chinese error messages for validation failures
- [x] T023 [US1] Update `PATCH /{id}` handler in `backend/app/modules/jobs/api.py`: accept `interview_time` field from `PatchJobInput`, validate FR-008 rules (must be future time, must be in interview-round status), cancel old research tasks on change
- [ ] T024 [US1] Add `cancel_pending_tasks()` method to `backend/app/modules/research/repository.py`: UPDATE interview_research_tasks SET status='cancelled' WHERE job_id=$1 AND status='pending'. Called from both `update_status` and `patch_job` paths per FR-011.

### Frontend Implementation for US1

- [ ] T025 [US1] Update status constants in `frontend/src/components/jobs/StatusTransition.tsx`: replace old status labels (OA, HR, Offer) with new labels (笔试中, 一面中, 二面中, 三面中, 已失败, 已通过). Source of truth from `GET /transitions` API.
- [ ] T026 [US1] Add interview time picker component in `frontend/src/components/jobs/StatusTransition.tsx`: DateTime picker (date + time, precise to minute) shown when target status is test/interview_1/interview_2/interview_3. Required field, marked with asterisk. Client-side validation: must be future time.
- [ ] T027 [US1] Implement terminal state handling in `frontend/src/components/jobs/StatusTransition.tsx`: disable "推进状态" button for failed/passed status, show tooltip "已终结的岗位无法推进". Hide time picker for non-interview transitions.
- [ ] T028 [US1] Update status badge/timeline in `frontend/src/components/jobs/` to display new Chinese status labels using `JOB_STATUS_CN` mapping from transitions API

**Checkpoint**: User Story 1 is fully functional — new status model, interview time picker, terminal state blocking all work correctly

---

## Phase 5: User Story 2 — 定时调研调度 (Priority: P1)

**Goal**: ARQ cron scans every 10 min, finds interviews ~5h away, creates research tasks with dedup via unique constraint

**Independent Test**: Create job with interview_time = now + 5h → wait for or manually trigger scan → verify InterviewResearchTask created → verify duplicate prevention → modify interview_time → verify old task cancelled

### Tests for US2

- [ ] T029 [P] [US2] Write unit test for scan query in `backend/tests/unit/modules/research/test_scheduler.py`: mock jobs in various states/times, assert correct jobs matched, assert expired users skipped, assert already-tasked jobs skipped
- [ ] T030 [P] [US2] Write integration test for scheduling in `backend/tests/integration/test_research_pipeline.py`: create job with interview in 5h → run scan → verify task created with status=pending → verify duplicate scan doesn't create second task

### Backend Implementation for US2

- [x] T031 [US2] Create `InterviewResearchTask` SQLAlchemy model in `backend/app/modules/research/models.py`: all columns per data-model.md (id, job_id FK, user_id FK, interview_time, status, search_dimensions JSONB, report_id FK, triggered_at, started_at, completed_at, error_message, created_at, updated_at). UniqueConstraint on (job_id, interview_time).
- [x] T032 [US2] Create `InterviewResearchTask` Pydantic schemas in `backend/app/modules/research/schemas.py`: `ResearchTaskCreate`, `ResearchTaskOut`, `ResearchTaskListOut`
- [x] T033 [US2] Implement `ResearchTaskRepository` in `backend/app/modules/research/repository.py`: `create()`, `get_by_id()`, `get_by_job_interview()`, `update_status()`, `cancel_pending()`, `list_by_user()` — all with RLS enforcement via user_id
- [x] T034 [US2] Implement `scan_interview_research()` ARQ cron function in `backend/app/workers/tasks/interview_research.py`: Redis lock (key=`lock:scan_interview_research`, TTL=540s), scan SQL per FR-009 (BETWEEN NOW()+4h55m AND NOW()+5h5m), skip deleted users, skip existing non-cancelled tasks, create tasks with status=pending, enqueue execute_research_task for each
- [x] T035 [US2] Register `scan_interview_research` in `backend/app/workers/main.py`: add import, add to `functions` list, add cron entry `cron(scan_interview_research, name="scan_interview_research", minute={0, 10, 20, 30, 40, 50})`

**Checkpoint**: Scheduler scans every 10 min, creates deduped research tasks, handles cancellation on interview_time change

---

## Phase 6: User Story 3 — 深度 Web Search 调研 (Priority: P1)

**Goal**: Research task executes 4 parallel search dimensions via Tavily, handles retries, persists results, implements 24h cache

**Independent Test**: Manual trigger research on test job → verify 4 dimensions all return results → verify results persisted to DB → verify retry on simulated failure → verify 24h cache reuse

### Tests for US3

- [ ] T036 [P] [US3] Write unit test for parallel search in `backend/tests/unit/modules/research/test_search.py`: mock Tavily responses for 4 dimensions, assert all 4 gathered concurrently, assert results correctly attributed to dimensions
- [ ] T037 [P] [US3] Write unit test for retry logic in `backend/tests/unit/modules/research/test_search.py`: mock Tavily to fail twice then succeed, assert 3 total attempts, assert exponential backoff timing (2s/4s/8s)
- [ ] T038 [P] [US3] Write unit test for 24h cache in `backend/tests/unit/modules/research/test_search.py`: create existing result within 24h, assert cache hit; create result older than 24h, assert cache miss

### Backend Implementation for US3

- [x] T039 [P] [US3] Create `InterviewResearchResult` SQLAlchemy model in `backend/app/modules/research/models.py`: all columns per data-model.md (id, task_id FK, dimension enum, query, results JSONB, result_count, company, error, searched_at)
- [x] T040 [P] [US3] Create `InterviewResearchResult` Pydantic schemas in `backend/app/modules/research/schemas.py`: `ResearchResultCreate`, `ResearchResultOut`
- [x] T041 [US3] Implement `ResearchResultRepository` in `backend/app/modules/research/repository.py`: `create()`, `get_by_task()`, `get_cached_for_company()` (24h lookup for interview_experience + company_product dimensions)
- [x] T042 [US3] Implement `extract_business_keywords()` in `backend/app/modules/research/service.py`: LLM call (~200 tokens) to extract 2-3 business keywords from job.position + job.notes_md. Fall back to `position` as keyword on failure.
- [x] T043 [US3] Implement `execute_search_dimensions()` in `backend/app/modules/research/service.py`: 4-way `asyncio.gather(return_exceptions=True)` — (1) interview_experience via tavily_search, (2) company_product via tavily_search with extracted keywords, (3) exam_points via tavily_search, (4) user_weakness via local DB query (ability_dimensions + error_questions). Each dimension: 3 retries, exponential backoff 2s/4s/8s, persist results to InterviewResearchResult.
- [x] T044 [US3] Implement `query_user_weakness()` in `backend/app/modules/research/service.py`: read 2 lowest `actual_score` dimensions from `AbilityDimensionRepository.list_for_user()`, read 20 freshest `status=fresh` questions from `ErrorQuestionRepository.list()`, return structured dict with dimension names, scores, improvements, error question tags
- [x] T045 [US3] Implement `check_search_cache()` in `backend/app/modules/research/service.py`: before executing web search for interview_experience and company_product, check `ResearchResultRepository.get_cached_for_company()` for results within 24h. If cache hit, reuse results and skip Tavily call.

**Checkpoint**: All 4 search dimensions execute in parallel, results persisted with retry handling, 24h cache functional

---

## Phase 7: User Story 4 — 面试前报告生成 (Priority: P1)

**Goal**: LLM synthesizes search results into 6-chapter structured report in Chinese (2000-3000 chars), quality check passes, report persisted to DB

**Independent Test**: Complete US3 search → generate report → verify 6 chapters present → verify 2000-3000 chars → verify quality check passes → verify report saved to interview_reports

### Tests for US4

- [ ] T046 [P] [US4] Write unit test for report generation in `backend/tests/unit/modules/research/test_report.py`: mock search results, call report generator, assert 6 chapter headings (📋 🏢 📝 🎯 ⚠️ 💡) present in output
- [ ] T047 [P] [US4] Write unit test for quality checker in `backend/tests/unit/modules/research/test_quality.py`: test (a) empty report → fail, (b) no company name → fail, (c) fewer than 3 interview questions → fail, (d) new user no ability data → skip (d) check, (e) valid report → all pass
- [ ] T048 [P] [US4] Write unit test for retry-on-quality-fail in `backend/tests/unit/modules/research/test_report.py`: first generation fails quality check → verify second attempt triggered (re-search + re-generate) → second attempt passes → verify report saved; both attempts fail → verify task.failed + admin notification

### Backend Implementation for US4

- [x] T049 [US4] Implement `generate_research_report()` in `backend/app/modules/research/report_generator.py`: single LLM call via `llm_client.invoke()` with system prompt defining 6-chapter structure, 2000-3000 char target, Chinese output, structured search results and user weakness data as user context. Set `node_name="research_report_gen"`, `max_retries=2`.
- [x] T050 [US4] Implement `check_report_quality()` in `backend/app/modules/research/quality_checker.py`: validate (a) content not empty/template-only, (b) ≥1 company/product name via regex on known patterns, (c) ≥3 interview questions via pattern matching on question marks + numbered items, (d) ≥1 ability dimension referenced (skip if `ability_dimensions` empty for new user). Return `(passed: bool, failures: list[str])`.
- [x] T051 [US4] Implement `execute_research_task()` main orchestrator in `backend/app/workers/tasks/interview_research.py`: full pipeline per contracts/events.yaml — load task+job → update status to running → extract keywords → execute searches (with cache check) → generate report → quality check → [retry once from search if failed] → save report → deliver (US5). Handle all error paths: search partial failure, LLM failure, quality check double-fail.
- [x] T052 [US4] Register `execute_research_task` in `backend/app/workers/main.py`: add import, add to `functions` list (no cron — this is enqueued on-demand)
- [x] T053 [US4] Implement `save_research_report()` in `backend/app/modules/research/service.py`: call `InterviewReportRepo.create_research_report()` with report content (Markdown), link task via `research_task_id`, set `delivery_status='pending'`
- [ ] T054 [US4] Implement historical comparison (US4-AC6) in `backend/app/modules/research/report_generator.py`: query for same-company report within last 7 days, if found, append "📊 历史对比" section comparing previous vs current weakness dimensions (progress/regress/unchanged)

**Checkpoint**: Reports generate with 6 chapters, quality check validates content, retry-on-fail works, reports persisted to DB

---

## Phase 8: User Story 5 — 微信报告推送 (Priority: P1)

**Goal**: Report delivered to user via WeChat in ~500-char segments, with Markdown→plain text conversion, DND respect, and notification fallback

**Independent Test**: Generate report → verify WeChat message segments received → verify `(1/N)` numbering → simulate send failure → verify notification created → verify report viewable on Web

### Tests for US5

- [ ] T055 [P] [US5] Write unit test for Markdown conversion in `backend/tests/unit/modules/research/test_markdown_converter.py`: test `**bold**` → `【bold】`, `### heading` → `▎heading`, `- list` preserved, code blocks flattened with `[代码]` prefix, total char count increase ≤10%
- [ ] T056 [P] [US5] Write unit test for message segmentation in `backend/tests/unit/modules/research/test_markdown_converter.py`: 2500-char input → ~5 segments of ~500 chars each, verify segment boundaries don't split mid-sentence, verify `(1/5)` through `(5/5)` numbering

### Backend Implementation for US5

- [x] T057 [P] [US5] Implement Markdown→plain text converter in `backend/app/modules/research/markdown_converter.py`: `convert_markdown_to_plain(md: str) -> str` applying all conversion rules from US4-AC5 (bold→【】, heading→▎, list preserved, code→[代码] prefix). `segment_for_wechat(text: str, max_chars: int = 500) -> list[str]` splitting at sentence/clause boundaries.
- [x] T058 [US5] Implement `deliver_report()` in `backend/app/modules/research/service.py`: convert Markdown → segment → for each segment: call `POST /agent/internal/send-message` (REQ-052) with `priority='high'`. Check user's WeChat binding status first; skip WeChat delivery if not bound. Check DND preference from `AgentPreferenceRepository`; delay if in DND window.
- [x] T059 [US5] Implement send retry logic in `backend/app/modules/research/service.py`: per-segment retry up to 3 times. If any segment fails 3 times: stop remaining segments, save full report to DB, create `Notification` via `NotificationService.create(type_="research_report_failed", ...)`, set report `delivery_status='failed'`
- [x] T060 [US5] Implement DND-aware delivery in `backend/app/modules/research/service.py`: if current time is within user's DND window (from `AgentPreference`), set report `delivery_status='delayed'`, store in pending queue. Add `drain_delayed_reports()` logic to `agents_outbound_drain` task (or new check in existing task) to send when DND ends.
- [x] T061 [US5] Implement `deliver_report_fallback()` for unbound/error cases in `backend/app/modules/research/service.py`: save complete report to DB, create notification with message "面试备战报告已生成（微信未绑定，无法推送），点击查看" or "面试备战报告已生成，微信发送失败，点击查看" depending on failure reason. Include link to Web report page.

**Checkpoint**: Reports delivered via WeChat in segments, Markdown converted to readable plain text, DND respected, notification fallback works

---

## Phase 9: User Story 6 — Web 端报告查看与历史 (Priority: P2)

**Goal**: Users can view research reports on Web, with "查看备战报告" button in job detail drawer and dedicated report detail page with Markdown rendering

**Independent Test**: Generate report → open job detail → click "查看备战报告" → verify full report with 6 chapters rendered → verify multi-round report history listing → submit rating

### Tests for US6

- [ ] T062 [P] [US6] Write contract test for `GET /api/v1/jobs/{id}/research-reports` in `backend/tests/unit/modules/research/test_api.py`: mock reports, assert list sorted by interview_time desc, assert correct fields returned
- [ ] T063 [P] [US6] Write contract test for `PATCH /api/v1/research-reports/{id}/rating` in `backend/tests/unit/modules/research/test_api.py`: assert rating 1-5 accepted, assert 0 and 6 rejected with 422

### Backend Implementation for US6

- [x] T064 [US6] Implement `GET /api/v1/jobs/{id}/research-reports` endpoint in `backend/app/modules/research/api.py`: query `interview_reports` WHERE job_id=$1 AND report_type='pre_interview_research', order by interview_time DESC. Return list with id, interview_time, status, generated_at, delivery_status, rating. Enforce RLS via user_id from job.
- [x] T065 [US6] Implement `GET /api/v1/jobs/{id}/research-reports/{report_id}` endpoint in `backend/app/modules/research/api.py`: return full report including summary_md (Markdown content), quality_check_passed, delivery_status, delivered_at. 404 if report not found or belongs to different job.
- [x] T066 [US6] Implement `PATCH /api/v1/research-reports/{report_id}/rating` endpoint in `backend/app/modules/research/api.py`: accept `{"rating": int}` with validation 1-5, UPDATE interview_reports SET rating=$1 WHERE id=$2. Return updated rating.
- [x] T067 [US6] Register research API router in `backend/app/api/v1/__init__.py`: `router.include_router(research_router, tags=["research"])` with prefix `/api/v1`
- [ ] T068 [US6] Add "查看备战报告" button to job detail drawer in `frontend/src/components/jobs/`: visible when `job.interview_time IS NOT NULL` AND `has_research_report === true`. Link navigates to `/research-reports/{report_id}`.
- [ ] T069 [US6] Create `ResearchReportDetail` page in `frontend/src/pages/ResearchReportPage.tsx`: fetch full report from API, render summary_md as Markdown (use existing Markdown renderer component or library), display 6 chapters with styled headings, show delivery_status badge, show rating stars (read-only if not yet rated, interactive to submit rating)
- [ ] T070 [US6] Implement report history list view in `frontend/src/components/jobs/ResearchReport.tsx`: when job has multiple reports (multi-round interviews), show chronological list with interview round labels and generation dates, click to view each
- [ ] T071 [US6] Implement historical comparison rendering (US6-AC4) in `frontend/src/pages/ResearchReportPage.tsx`: parse "📊 历史对比" section from summary_md, render as comparison table (dimension / last score / current score / trend arrow)

**Checkpoint**: Reports viewable on Web, rating functional, multi-round history browsable, historical comparison table rendered

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Observability, audit, CLI completion, E2E tests, final validation

### Observability (FR-023)

- [x] T072 [P] Add Prometheus metrics in `backend/app/core/metrics.py` or new `backend/app/modules/research/metrics.py`: `interview_research_tasks_total` Counter by status, `interview_research_duration_seconds` Histogram, `interview_report_generation_tokens` Counter, `web_search_api_calls_total` Counter by dimension. Instrument all relevant service methods.
- [x] T073 [P] Add structured logging to all research pipeline stages: task creation, search dimension start/end, LLM call start/end, quality check result, delivery attempt. Follow existing `logger.bind(request_id=...)` pattern.

### Audit Logging (FR-024)

- [x] T074 Implement audit log writing in `backend/app/modules/research/service.py`: after each task completes, write audit record with `research_task_id`, `user_id`, `job_id`, `company`, `position`, `interview_time`, `triggered_at`, `completed_at`, `duration_ms`, per-dimension `search_results_count`, `report_length_chars`, `quality_check_passed`, `delivery_status`. Use existing audit infrastructure.

### CLI Commands (FR-025)

- [x] T075 [P] Implement `trigger-research <job_id>` CLI command in `backend/app/modules/research/cli.py`: Typer command that directly enqueues `execute_research_task` for the given job. Validate job exists and has interview_time set. Use `--json` flag for machine output.
- [x] T076 [P] Implement `research-stats` CLI command in `backend/app/modules/research/cli.py`: Typer command that queries `interview_research_tasks` table, outputs counts by status, average duration, total reports, average rating. Use `--user-id` filter and `--json` flag.

### Backend Test Suite

- [ ] T077 Run all backend research module tests: `uv run pytest backend/tests/unit/modules/research/ -v` and `uv run pytest backend/tests/integration/test_research_pipeline.py -v`. Fix any failures. Target: 100% pass.
- [ ] T078 Run full backend regression: `uv run pytest backend/tests/ -v -k "not slow"`. Ensure no existing tests broken by job model/status changes.

### E2E Playwright Tests (SC-010)

- [ ] T079 [P] Write Playwright E2E for US1 in `frontend/tests/e2e/053-interview-intelligence.spec.ts`: login as demo user → create job → advance to interview_1 with time picker interaction → assert interview_time saved → advance to interview_2 → advance to passed → assert terminal state button disabled
- [ ] T080 [P] Write Playwright E2E for US4 in `frontend/tests/e2e/053-interview-intelligence.spec.ts`: navigate to job detail with existing report → click "查看备战报告" → assert 6 chapter headings visible → assert report content rendered as Markdown → submit star rating → assert rating saved
- [ ] T081 [P] Write Playwright E2E for US7 in `frontend/tests/e2e/053-interview-intelligence.spec.ts`: execute `migrate-status --dry-run --json` via API → assert old→new mapping correctness → assert transitions endpoint returns new state model
- [ ] T082 Run Playwright E2E tests: `npx playwright test tests/e2e/053-interview-intelligence.spec.ts --project=chromium`. Target: all pass.

### Final Validation

- [ ] T083 Run quickstart.md validation: execute all VS-1 through VS-8 scenarios, verify all expected outputs match. Fix any discrepancies.
- [ ] T084 TypeScript typecheck: `cd frontend && npx tsc --noEmit`. Fix any type errors.
- [ ] T085 Backend lint + typecheck: `cd backend && uv run ruff check app/modules/research/ && uv run mypy app/modules/research/`. Clean up all issues.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001) — BLOCKS all user stories
- **US7 Migration (Phase 3)**: Depends on Foundational (T005-T007) — BLOCKS US1
- **US1 Status Model (Phase 4)**: Depends on US7 (migration must exist first) — BLOCKS US2/US5
- **US2 Scheduler (Phase 5)**: Depends on US1 (needs interview_time on jobs) — BLOCKS US3
- **US3 Search (Phase 6)**: Depends on US2 (needs task creation flow) — BLOCKS US4
- **US4 Reports (Phase 7)**: Depends on US3 (needs search results) — BLOCKS US5/US6
- **US5 WeChat (Phase 8)**: Depends on US4 (needs generated reports)
- **US6 Web View (Phase 9)**: Depends on US4 (needs generated reports) — can parallel with US5
- **Polish (Phase 10)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Setup → Foundational → US7 (Migration)
                         ↓
                    US1 (Status Model)
                         ↓
                    US2 (Scheduler)
                         ↓
                    US3 (Search)
                         ↓
                    US4 (Reports)
                      ↙     ↘
            US5 (WeChat)   US6 (Web View)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T001-T004: All setup tasks can run in parallel
- T006-T009: Foundational domain + model changes can run in parallel (different files)
- T013-T014: US7 tests in parallel
- T018-T019: US1 tests in parallel
- T029-T030: US2 tests in parallel
- T036-T038: US3 tests in parallel
- T039-T040: US3 model + schema in parallel
- T046-T048: US4 tests in parallel
- T055-T056: US5 tests in parallel
- T062-T063: US6 tests in parallel
- T072-T073: Observability tasks in parallel
- T075-T076: CLI tasks in parallel
- T079-T081: E2E tests in parallel
- US5 and US6 can be implemented in parallel after US4 completes

---

## Parallel Example: User Story 3

```bash
# Launch all tests for US3 together:
Task: "Write unit test for parallel search in backend/tests/unit/modules/research/test_search.py"
Task: "Write unit test for retry logic in backend/tests/unit/modules/research/test_search.py"
Task: "Write unit test for 24h cache in backend/tests/unit/modules/research/test_search.py"

# Launch model + schema together:
Task: "Create InterviewResearchResult model in backend/app/modules/research/models.py"
Task: "Create InterviewResearchResult schemas in backend/app/modules/research/schemas.py"
```

---

## Implementation Strategy

### MVP First (US7 + US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US7 — Data Migration
4. Complete Phase 4: US1 — New Status Model
5. **STOP and VALIDATE**: Run migration, test new status flow end-to-end
6. Deploy/demo if ready — this alone delivers the new 7-state model + interview time tracking

### Core Value Delivery (US2-US5)

After MVP:
1. US2: Scheduler starts watching for upcoming interviews
2. US3: Search engine gathers intelligence
3. US4: Reports are generated and quality-checked
4. US5: Reports delivered to users via WeChat

This pipeline delivers the full "面试前智能调研" value proposition.

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US7 + US1 → Deploy (new status model live!)
3. US2 + US3 + US4 + US5 → Deploy (intelligence engine live!)
4. US6 → Deploy (Web viewer live!)
5. Polish → Final quality pass

### Parallel Team Strategy

With multiple developers after Foundation:

- Developer A: US2 → US3 → US4 (research pipeline)
- Developer B: US5 (WeChat delivery, can use mock reports while US4 in progress)
- Developer C: US6 (Web viewer, can use mock reports while US4 in progress)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Constitution Principle III)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- `backend/app/modules/research/` is a new module — ensure all new files have proper `__init__.py` exports
- All DB queries must enforce RLS via `user_id` column (Constitution Principle: Security & Privacy)
- Use `bindparam(type_=JSONB)` for JSONB columns (per [[interview_report_sql_caveat]])
- CLI commands use `asyncio.run()` pattern consistent with `backend/app/modules/jobs/cli.py`
