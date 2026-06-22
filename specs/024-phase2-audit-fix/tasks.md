# Tasks: Phase 2 (M5-M11) spec/code 偏差审计与修复

**Input**: Design documents from `/specs/024-phase2-audit-fix/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included (Constitution III TDD). Each user story phase has test tasks first.

**Organization**: Tasks grouped by user story (US1 Offer+Panel / US2 outbox / US3 status_history / US4 archived / US5 PIN+share / US6 PDF), in priority order P1 → P2.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline + grep removal targets.

- [ ] T001 [P] Verify backend tests green: `cd backend && uv run pytest`
- [ ] T002 [P] Verify frontend typecheck + tests green: `cd frontend && npm run typecheck && npm test`
- [ ] T003 [P] Verify E2E baseline: `cd frontend && npx playwright test` 21/21 pass
- [ ] T004 [P] Grep existing `archived` / `archived_at` / `pin_hash` / `ProfileView` references to confirm removal targets

---

## Phase 2: Foundational (No Blocking Prerequisites)

**Purpose**: This feature has no shared blocking infrastructure — each US is independent. Skip to US phases.

---

## Phase 3: User Story 1 — M9 Offer 字段 + JobsDetailPanel (Priority: P1) 🎯 MVP

**Goal**: Offer 4 字段端到端可用（迁移 + service + API + UI），JobsDetailPanel 覆盖 FR-002/003/009/019/025。

**Independent Test**: 创建岗位 → 推进到 offered → 录入 Offer 字段 → 查询验证持久化 → 前端 JobsDetailPanel 展示时间线/Offer/activities。

### Tests for User Story 1 (TDD)

- [ ] T010 [P] [US1] Unit test: `backend/tests/unit/test_jobs_offer_fields.py` — assert PATCH accepts 4 offer_* in status=offered; 422 in status=fresh; offer_deadline_at < today → 422
- [ ] T011 [P] [US1] Integration test: `backend/tests/integration/test_jobs_offer_e2e.py` — create job, advance to offered, PATCH offer fields, GET returns 4 fields
- [ ] T012 [P] [US1] Frontend component test: `frontend/tests/unit/test_jobs_detail_panel.test.tsx` — assert renders timeline / edit button / offer section / activities
- [ ] T013 [P] [US1] Frontend component test: `frontend/tests/unit/test_job_offer_editor.test.tsx` — assert offer_deadline_at < today shows validation error

### Implementation for User Story 1

- [ ] T014 [US1] Create Alembic migration `backend/alembic/versions/xxxx_add_jobs_offer_fields.py`: add 4 nullable columns (offer_salary_text / offer_contact_name / offer_contact_info / offer_deadline_at)
- [ ] T015 [US1] Modify `backend/app/modules/jobs/models.py`: add 4 fields to `Job` model
- [ ] T016 [US1] Modify `backend/app/modules/jobs/service.py`: PATCH accepts offer_* only when status in {offered, accepted}; validate offer_deadline_at ≥ today
- [ ] T017 [US1] Modify `backend/app/modules/jobs/api.py`: GET /jobs/{id} returns 4 offer_* fields; PATCH /jobs/{id} accepts them; GET /jobs (list) does NOT return offer_* (privacy)
- [ ] T018 [US1] Run migration: `cd backend && uv run alembic upgrade head`
- [ ] T019 [US1] [P] Create `frontend/src/components/jobs/JobOfferEditor.tsx`: Offer section editor with 4 fields + deadline validation
- [ ] T020 [US1] Rewrite `frontend/src/components/jobs/JobsDetailPanel.tsx`: 5 regions (basic info / timeline / edit mode / offer section / activities)
- [ ] T021 [US1] Modify `frontend/src/repositories/JobRepository.ts`: extend Job type with 4 offer_* fields
- [ ] T022 [US1] Modify `frontend/src/components/jobs/JobTimeline.tsx`: render status_history (uses aligned field names from US3, coordinate)

**Checkpoint**: US1 complete — SC-001 + SC-002 (Offer 字段 + JobsDetailPanel).

---

## Phase 4: User Story 2 — M9 outbox 接入 (Priority: P1)

**Goal**: 4 类岗位写操作（创建/编辑/推进/删除）走 outbox，离线兜底。

**Independent Test**: 离线状态下创建岗位，UI 显示「待同步」；恢复网络后 outbox 自动 flush，岗位出现。

### Tests for User Story 2 (TDD)

- [ ] T030 [P] [US2] Frontend unit test: `frontend/tests/unit/test_outbox_jobs.test.ts` — assert 4 operation types enqueue to outbox; dead letter after 3 retries; cancel removes from queue
- [ ] T031 [P] [US2] Integration test: `backend/tests/integration/test_outbox_jobs_offline.py` — simulate offline → enqueue 3 ops → network restore → FIFO flush

### Implementation for User Story 2

- [ ] T032 [US2] Create `frontend/src/lib/outbox/jobs.ts`: 4 enqueue adapters (create / edit / advance / delete) using existing `src/lib/outbox/` infrastructure
- [ ] T033 [US2] Modify `frontend/src/pages/Jobs.tsx`: replace direct react-query mutation with outbox enqueue (lines 55-57 per spec input)
- [ ] T034 [US2] Add UI "待同步" badge on outbox-pending jobs in list view
- [ ] T035 [US2] Add dead letter handling UI: toast "同步失败，请手动处理" after 3 retries
- [ ] T036 [US2] Add cancel-outbox-entry action: user can撤销 pending entry, removed from queue
- [ ] T037 [US2] Verify flush resumes on network restore: outbox engine hooks online/offline events

**Checkpoint**: US2 complete — SC-003 (outbox 离线兜底).

---

## Phase 5: User Story 3 — M9 status_history 字段名对齐 (Priority: P2)

**Goal**: 前端 `JobRepository.ts` / `JobTimeline.tsx` 使用 `{from, to, at, note}` 字段名。

**Independent Test**: `npm run typecheck` 通过，时间线渲染所有 status_history 节点。

### Tests for User Story 3 (TDD)

- [ ] T040 [P] [US3] Frontend component test: `frontend/tests/unit/test_job_timeline.test.tsx` — mock 3 status_history entries, assert renders 3 nodes with from/to/at/note

### Implementation for User Story 3

- [ ] T041 [US3] Modify `frontend/src/repositories/JobRepository.ts`: `StatusHistoryEntry` type change `from_status`→`from`, `to_status`→`to`, `changed_at`→`at`
- [ ] T042 [US3] Modify `frontend/src/components/jobs/JobTimeline.tsx`: read `entry.from` / `entry.to` / `entry.at` / `entry.note` (coordinate with T022)
- [ ] T043 [US3] Run `cd frontend && npm run typecheck` — 0 errors
- [ ] T044 [US3] Run E2E涉及岗位时间线用例，确认无回归

**Checkpoint**: US3 complete — SC-004 (字段名一致).

---

## Phase 6: User Story 4 — M7 archived 状态移除 (Priority: P2)

**Goal**: FSM 回归 3 态 + reset，移除 `archived_at` 列。

**Independent Test**: `fresh→archived` 返回 422；`fresh→practicing→mastered→fresh(reset=true)` 成功。

### Tests for User Story 4 (TDD)

- [ ] T050 [P] [US4] Unit test: `backend/tests/unit/test_error_fsm.py` — assert valid transitions (fresh→practicing→mastered→fresh+reset) + invalid (archived / practicing→fresh no reset) → 422
- [ ] T051 [P] [US4] Integration test: `backend/tests/integration/test_error_fsm_warning_log.py` — assert illegal transition logs warning with user_id / question_id / from / to

### Implementation for User Story 4

- [ ] T052 [US4] Modify `backend/app/modules/errors/service.py`: `VALID_TRANSITIONS` reduce to `{fresh→practicing, practicing→mastered, mastered→fresh(reset=true)}`; remove all `archived` entries
- [ ] T053 [US4] Modify `backend/app/modules/errors/api.py`: PATCH status returns 422 for illegal transitions; log warning
- [ ] T054 [US4] Create Alembic migration `backend/alembic/versions/xxxx_drop_error_questions_archived_at.py`: first UPDATE archived_at→deleted_at (if any), then DROP COLUMN archived_at
- [ ] T055 [US4] Modify `backend/app/modules/errors/models.py`: remove `archived_at` field
- [ ] T056 [US4] Run migration: `cd backend && uv run alembic upgrade head`
- [ ] T057 [US4] Verify 021 error_coach E2E still 3/3 pass (legal transitions unchanged)

**Checkpoint**: US4 complete — SC-005 (archived removed).

---

## Phase 7: User Story 5 — M8 PIN/ProfileView 移除 + 分享链接 (Priority: P2)

**Goal**: 移除 `pin_hash` 列 + `ProfileView` 表，分享链接仅走 `expires_at` + `revoked_at`。

**Independent Test**: 创建分享链接（7 天过期），第 6 天访问 200，第 8 天 410；revoke 后 403。

### Tests for User Story 5 (TDD)

- [ ] T060 [P] [US5] Unit test: `backend/tests/unit/test_ability_share_expiration.py` — assert expires_at < now → 410; revoked_at set → 403
- [ ] T061 [P] [US5] Integration test: `backend/tests/integration/test_ability_share_no_pin.py` — assert share link access works without PIN header

### Implementation for User Story 5

- [ ] T062 [US5] Create Alembic migration `backend/alembic/versions/xxxx_drop_ability_profile_pin_profileview.py`: `DROP COLUMN pin_hash` + `DROP TABLE profile_views`
- [ ] T063 [US5] Modify `backend/app/modules/ability_profile/models.py`: remove `pin_hash` field + `ProfileView` class
- [ ] T064 [US5] Modify `backend/app/modules/ability_profile/service.py`: remove PIN validation logic (lines 277, 352-356 per spec input); remove ProfileView record logic
- [ ] T065 [US5] Modify `backend/app/modules/ability_profile/api.py`: remove PIN validation middleware from share link access route
- [ ] T066 [US5] Run migration: `cd backend && uv run alembic upgrade head`
- [ ] T067 [US5] Modify `frontend/src/pages/AbilityProfile.tsx` (or share management UI): remove PIN input field; remove "访问次数" display
- [ ] T068 [US5] Verify share link works with only expires_at + revoked_at checks

**Checkpoint**: US5 complete — SC-006 (PIN/ProfileView removed).

---

## Phase 8: User Story 6 — M8 PDF 导出同步 (Priority: P2)

**Goal**: `GET /api/v1/ability-profile/export-pdf` 同步返回 PDF，≤ 3s，不走 ARQ。

**Independent Test**: 点击「导出 PDF」按钮，浏览器 ≤ 3s 内触发下载 `ability-profile-{user_id}-{date}.pdf`。

### Tests for User Story 6 (TDD)

- [ ] T070 [P] [US6] Unit test: `backend/tests/unit/test_ability_profile_pdf_sync.py` — assert GET returns 200 + Content-Type application/pdf + Content-Disposition attachment; response body starts with `%PDF-`; response time < 3s; no ARQ enqueue_job called

### Implementation for User Story 6

- [ ] T071 [US6] Modify `backend/app/modules/ability_profile/service.py`: remove `enqueue_job(...)` call (lines 419-420 per spec input); add sync `generate_pdf(user_id) -> bytes` function using existing reportlab/weasyprint
- [ ] T072 [US6] Modify `backend/app/modules/ability_profile/api.py`: `export-pdf` endpoint returns `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="ability-profile-{user_id}-{date}.pdf"'})`
- [ ] T073 [US6] Wrap PDF generation in `run_in_threadpool` to avoid blocking event loop (CPU-bound)
- [ ] T074 [US6] Remove ARQ PDF worker task function (or mark as deprecated/unused)
- [ ] T075 [US6] Modify `frontend/src/pages/AbilityProfile.tsx`: change "导出 PDF" button to `window.location.href = "/api/v1/ability-profile/export-pdf"` (direct download), remove polling logic
- [ ] T076 [US6] Verify 3 consecutive clicks each trigger download (no dedup)

**Checkpoint**: US6 complete — SC-007 (PDF sync direct download).

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Verify SC-008 E2E 零回归.

- [ ] T090 Run `cd backend && uv run pytest` — all unit + integration green
- [ ] T091 Run `cd frontend && npm run typecheck && npm test` — all vitest pass
- [ ] T092 Run `cd frontend && npx playwright test` — 21/21 round-1 + round-2 pass
- [ ] T093 Verify SC-001: quickstart Scenario 1 (Offer 端到端)
- [ ] T094 Verify SC-002: JobsDetailPanel 5 regions visible
- [ ] T095 Verify SC-003: quickstart Scenario 2 (outbox offline)
- [ ] T096 Verify SC-004: quickstart Scenario 3 (status_history 字段名)
- [ ] T097 Verify SC-005: quickstart Scenario 4 (archived 422)
- [ ] T098 Verify SC-006: quickstart Scenario 5 (PIN/ProfileView removed)
- [ ] T099 Verify SC-007: quickstart Scenario 6 (PDF sync < 3s)
- [ ] T100 Verify SC-008: E2E 21/21 pass
- [ ] T101 [P] Update `specs/024-phase2-audit-fix/requirements-status.md` (if exists) with SC roll-up

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Empty
- **User Stories (Phases 3-8)**: All independent, can run in parallel
  - US3 (status_history) should be done before/with US1 (JobsDetailPanel uses aligned fields)
  - US5 and US6 both touch ability_profile module — coordinate or serialize
- **Polish (Phase 9)**: Depends on all US complete

### User Story Dependencies

- **US1 (P1) Offer + Panel**: Depends on US3 (field name alignment) for timeline rendering
- **US2 (P1) outbox**: Independent
- **US3 (P2) status_history**: Independent, do early (unblocks US1 timeline)
- **US4 (P2) archived**: Independent
- **US5 (P2) PIN/ProfileView removal**: Independent, but coordinate with US6 (same module)
- **US6 (P2) PDF sync**: Coordinate with US5 (same module)

### Within Each User Story

- TDD: tests first, watch fail, then implement
- Migration before model change (US1/US4/US5)
- Backend before frontend (US1/US2/US6)
- Frontend typecheck after type changes (US3)

### Parallel Opportunities

- All Setup tasks T001-T004 can run in parallel
- US2 (outbox) + US4 (archived) + US3 (status_history) can run in parallel (different modules)
- US5 + US6 should serialize (same ability_profile module, avoid merge conflicts)

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup (baseline green)
2. Complete Phase 5: US3 (status_history, small change, unblocks US1)
3. Complete Phase 3: US1 (Offer + JobsDetailPanel)
4. Complete Phase 4: US2 (outbox)
5. **STOP and VALIDATE**: M9 岗位追踪端到端可用 (SC-001/002/003/004)
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + US3 → status_history aligned
2. Add US1 → Offer fields + JobsDetailPanel
3. Add US2 → outbox offline fallback
4. Add US4 → archived removed, FSM clean
5. Add US5 → PIN/ProfileView removed
6. Add US6 → PDF sync direct download
7. Polish → E2E 21/21 + all SC verified

---

## Notes

- [P] tasks = different files, no dependencies
- Constitution III TDD: tests first, watch them fail, then implement
- Commit after each task or logical group
- US5 + US6 should serialize (same ability_profile module)
- US3 should complete before US1 (JobsDetailPanel reads aligned field names)
- Migrations US1/US4/US5 are independent (different tables), can run in parallel
