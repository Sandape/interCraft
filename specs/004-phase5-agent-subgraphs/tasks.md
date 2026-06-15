---

description: "Task list for Phase 5 — P1 Agent 子图扩展"
---

# Tasks: Phase 5 — P1 Agent 子图扩展

**Input**: Design documents from `/specs/004-phase5-agent-subgraphs/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included per Constitution III (Test-First, NON-NEGOTIABLE). Tests MUST be written and seen to FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on other [P] tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/`
- **Frontend**: `frontend/src/`
- **Tests**: `backend/tests/` and `frontend/tests/` (E2E in `tests/e2e/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify Phase 4 M14 infrastructure is ready for Phase 5 subgraph development.

**⚠️ Note**: Phase 5 has NO new dependencies, NO new DB migrations. All infrastructure is inherited from Phase 1-4.

- [X] T001 [P] Create Phase 5 agent subgraph directory structure: `backend/app/agents/{graphs,nodes,state,tools,prompts}/` sub-directories for each agent
- [X] T002 [P] Create frontend Phase 5 directory structure: `frontend/src/{hooks,repositories}/` new agent files + `frontend/src/pages/GeneralCoach.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared agent patterns and tools that multiple stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create shared tool `query_resume_blocks` in `backend/app/agents/tools/query_resume_blocks.py` (M16 reuses; wraps `resume_block_service.list_by_branch`)
- [X] T004 Create shared tool `query_error_question_by_id` in `backend/app/agents/tools/query_error_question.py` (M17 reuses; wraps `error_question_service.get_by_id`)
- [X] T005 Create shared tool `query_interview_score` in `backend/app/agents/tools/query_interview_score.py` (M18 reuses; reads `interview_reports` + `ai_messages`)

**Checkpoint**: Foundation ready — all 4 user stories can now be implemented independently

---

## Phase 3: User Story 1 — AI 简历优化 (Priority: P1) 🎯 MVP

**Goal**: 用户在简历编辑器中对分支点击「AI 优化」,Agent 基于目标 JD 分析差距生成 JSON Patch,通过 interrupt 等待用户确认后落盘

**Independent Test**: 调用 `POST /api/v1/agents/resume-optimize/start` → 收到 interrupt → 调用 `confirm(apply)` → 验证简历分支内容更新 + 版本创建

### Tests for User Story 1 (Test-First)

- [X] T006 [P] [US1] Contract test for M16 endpoints in `backend/tests/contract/test_agents_api.py` (Resume Optimize section: start/confirm/state)
- [X] T007 [P] [US1] Integration test for M16 complete flow in `backend/tests/integration/test_resume_optimize.py` (start → interrupt → confirm(apply/discard) → verify)

### Implementation for User Story 1

- [X] T008 [US1] Create `ResumeOptimizeState` TypedDict in `backend/app/agents/state/resume_optimize_state.py`
- [X] T009 [P] [US1] Create M16 node `load_branch.py` in `backend/app/agents/nodes/resume_optimize/load_branch.py`
- [X] T010 [P] [US1] Create M16 node `diff_jd.py` in `backend/app/agents/nodes/resume_optimize/diff_jd.py`
- [X] T011 [P] [US1] Create M16 node `suggest_blocks.py` in `backend/app/agents/nodes/resume_optimize/suggest_blocks.py`
- [X] T012 [P] [US1] Create M16 node `apply_or_discard.py` (interrupt!) in `backend/app/agents/nodes/resume_optimize/apply_or_discard.py`
- [X] T013 [P] [US1] Create M16 node `snapshot.py` in `backend/app/agents/nodes/resume_optimize/snapshot.py`
- [X] T014 [P] [US1] Create M16 prompts: `diff_jd.md` + `suggest_blocks.md` in `backend/app/agents/prompts/resume_optimize/`
- [X] T015 [US1] Create `ResumeOptimizeService` in `backend/app/services/resume_optimize_service.py` (lock acquire/release, patch apply, version creation)
- [X] T016 [US1] Create M16 StateGraph in `backend/app/agents/graphs/resume_optimize.py` (compile with `interrupt_after=["apply_or_discard"]`)
- [X] T017 [US1] Create M16 REST endpoints in `backend/app/api/v1/agents_resume_optimize.py` (POST start/confirm/state)
- [X] T018 [US1] Create M16 WS interrupt event handler (extend Phase 4 WS protocol for `interrupt` event type)
- [X] T019 [US1] Create M16 ARQ timeout cron in `backend/app/workers/tasks/resume_optimize_timeout.py` (巡检 30min 超时 → release lock)
- [X] T020 [US1] Create frontend `resumeOptimizeRepo.ts` in `frontend/src/repositories/resumeOptimizeRepo.ts` (start/confirm/state API calls)
- [X] T021 [US1] Create frontend `useResumeOptimize.ts` hook in `frontend/src/hooks/useResumeOptimize.ts`
- [X] T022 [US1] Create frontend `AiOptimizePanel.tsx` component in `frontend/src/components/resume/AiOptimizePanel.tsx` (interrupt diff review UI, before/after inline)
- [X] T023 [US1] Integrate M16 into `ResumeEditor.tsx` — add「AI 优化」button, wire up AiOptimizePanel

**Checkpoint**: M16 fully functional — user can start optimize → review diff → apply/discard → see version in history

---

## Phase 4: User Story 2 — 能力画像自动诊断 (Priority: P1)

**Goal**: 面试完成后 Ability Diagnose Agent 异步启动,自动汇总评分、比对历史、生成改进建议、更新能力画像

**Independent Test**: 完成面试(Phase 4) → 等待 30s → 验证 `ability_dimensions.actual` 已更新 + `activities` 中有 `ability.suggestion` 记录

### Tests for User Story 2 (Test-First)

- [X] T024 [P] [US2] Integration test for M18 in `backend/tests/integration/test_ability_diagnose.py` (指定 session → 验证 dimensions 更新 + activities 写入)

### Implementation for User Story 2

- [X] T025 [US2] Create `AbilityDiagnoseState` TypedDict in `backend/app/agents/state/ability_diagnose_state.py`
- [X] T026 [P] [US2] Create M18 node `aggregate_scores.py` in `backend/app/agents/nodes/ability_diagnose/aggregate_scores.py` (纯聚合,不调 LLM)
- [X] T027 [P] [US2] Create M18 node `compare_baseline.py` in `backend/app/agents/nodes/ability_diagnose/compare_baseline.py` (计算 delta + 趋势标记)
- [X] T028 [P] [US2] Create M18 node `generate_insight.py` in `backend/app/agents/nodes/ability_diagnose/generate_insight.py` (LLM 产出改进建议)
- [X] T029 [P] [US2] Create M18 node `update_dimensions.py` in `backend/app/agents/nodes/ability_diagnose/update_dimensions.py` (写 DB + WS 推送)
- [X] T030 [US2] Create M18 prompt `generate_insight.md` in `backend/app/agents/prompts/ability_diagnose/generate_insight.md`
- [X] T031 [US2] Create M18 StateGraph in `backend/app/agents/graphs/ability_diagnose.py`
- [X] T032 [US2] Upgrade ARQ task `diagnose_after_interview.py` in `backend/app/workers/tasks/diagnose_after_interview.py` (Phase 4 skeleton → full M18 graph invocation)
- [X] T033 [US2] Create M18 WS `agent.final` event handler (复用 Phase 4 WS 协议,新增 `ability_diagnose` graph 类型)
- [X] T034 [US2] Create frontend `useAbilityDiagnose.ts` hook in `frontend/src/hooks/useAbilityDiagnose.ts` (subscribe to agent.final event)
- [X] T035 [US2] Create frontend `AbilityUpdateStatus.tsx` component in `frontend/src/components/profile/AbilityUpdateStatus.tsx` (「能力画像更新中…」→「已更新」)
- [X] T036 [US2] Integrate M18 into Profile page — show AbilityUpdateStatus, auto-refresh on agent.final

**Checkpoint**: M18 fully functional — interview complete → auto-diagnose → Profile page shows updated dimensions + suggestions

---

## Phase 5: User Story 3 — 错题强化 Agent (Priority: P2)

**Goal**: 用户对错题点击「开始强化」,Error Coach 以 3 轮梯度提示引导掌握,答对 3 次后 frequency 递减

**Independent Test**: 调用 `POST /api/v1/agents/error-coach/start` → 提交 3 轮回答(≥ 8 分) → 验证 `error_questions.frequency` 已递减

### Tests for User Story 3 (Test-First)

- [X] T037 [P] [US3] Integration test for M17 in `backend/tests/integration/test_error_coach.py` (3 次答对完整流程 + 超时自动结束)

### Implementation for User Story 3

- [X] T038 [US3] Create `ErrorCoachState` TypedDict in `backend/app/agents/state/error_coach_state.py`
- [X] T039 [P] [US3] Create M17 node `fetch_question.py` in `backend/app/agents/nodes/error_coach/fetch_question.py`
- [X] T040 [P] [US3] Create M17 node `hint_ladder.py` in `backend/app/agents/nodes/error_coach/hint_ladder.py` (根据 attempt_count 选提示级别)
- [X] T041 [P] [US3] Create M17 node `evaluate.py` in `backend/app/agents/nodes/error_coach/evaluate.py` (0-10 评分,≥ 8 答对)
- [X] T042 [P] [US3] Create M17 node `loop_or_finish.py` in `backend/app/agents/nodes/error_coach/loop_or_finish.py`
- [X] T043 [US3] Create M17 prompt `hint_ladder.md` in `backend/app/agents/prompts/error_coach/hint_ladder.md`
- [X] T044 [US3] Create `ErrorCoachService` in `backend/app/services/error_coach_service.py` (调 M08 recall 接口减 frequency)
- [X] T045 [US3] Create M17 StateGraph in `backend/app/agents/graphs/error_coach.py`
- [X] T046 [US3] Create M17 REST endpoints in `backend/app/api/v1/agents_error_coach.py` (POST start/messages/abort/state)
- [X] T047 [US3] Create frontend `errorCoachRepo.ts` in `frontend/src/repositories/errorCoachRepo.ts`
- [X] T048 [US3] Create frontend `useErrorCoach.ts` hook in `frontend/src/hooks/useErrorCoach.ts`
- [X] T049 [US3] Create frontend `ErrorCoachPanel.tsx` in `frontend/src/components/error-book/ErrorCoachPanel.tsx` (3 轮对话面板)
- [X] T050 [US3] Integrate M17 into ErrorBook page — add「开始强化」CTA on error question cards, wire up ErrorCoachPanel

**Checkpoint**: M17 fully functional — click「开始强化」→ 3 轮问答 → frequency updated → mastered status achieved

---

## Phase 6: User Story 4 — 通用 Coach (Priority: P2)

**Goal**: 用户在通用 Coach 页面发起任意技术/职业问题,Agent 通过意图分类给出回答或跳转引导

**Independent Test**: 调用 `POST /api/v1/agents/general-coach/start` → `POST messages("如何准备系统设计面试")` → 收到 WS 流式回答,意图分类为 career_advice

### Tests for User Story 4 (Test-First)

- [X] T051 [P] [US4] Integration test for M19 in `backend/tests/integration/test_general_coach.py` (4 种意图分类端到端)
- [X] T052 [P] [US4] Contract test for M19 endpoints in `backend/tests/contract/test_agents_api.py` (General Coach section: start/messages/close/state)

### Implementation for User Story 4

- [X] T053 [US4] Create `GeneralCoachState` TypedDict in `backend/app/agents/state/general_coach_state.py`
- [X] T054 [P] [US4] Create M19 node `intent.py` in `backend/app/agents/nodes/general_coach/intent.py` (LLM 分类 + few-shot 示例)
- [X] T055 [P] [US4] Create M19 node `route.py` in `backend/app/agents/nodes/general_coach/route.py` (confidence > 0.7 路由)
- [X] T056 [P] [US4] Create M19 node `respond.py` in `backend/app/agents/nodes/general_coach/respond.py` (WS 流式回答)
- [X] T057 [P] [US4] Create M19 prompts: `intent.md` (with few-shot examples) + `respond.md` in `backend/app/agents/prompts/general_coach/`
- [X] T058 [US4] Create M19 StateGraph in `backend/app/agents/graphs/general_coach.py`
- [X] T059 [US4] Create M19 REST endpoints in `backend/app/api/v1/agents_general_coach.py` (POST start/messages/close/state)
- [X] T060 [US4] Create frontend `generalCoachRepo.ts` in `frontend/src/repositories/generalCoachRepo.ts`
- [X] T061 [US4] Create frontend `useGeneralCoach.ts` hook in `frontend/src/hooks/useGeneralCoach.ts` (WS 流式消费)
- [X] T062 [US4] Create frontend `GeneralCoach.tsx` page in `frontend/src/pages/GeneralCoach.tsx` (对话列表 + 输入框 + 流式渲染)
- [X] T063 [US4] Add M19 route to frontend React Router

**Checkpoint**: M19 fully functional — ask any question → intent detected → streaming answer or redirect suggestion

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Mock data, E2E tests, and final validation for all Phase 5 user stories

- [X] T064 [P] Add M16-M19 mock data to `frontend/src/data/mockData.ts` (预置 interrupt patches / error-coach dialog / ability diagnose results / general coach responses)
- [X] T065 [P] Create E2E test for M16 interrupt flow in `tests/e2e/resume-optimize.spec.ts`
- [X] T066 [P] Create E2E test for M19 general coach flow in `tests/e2e/general-coach.spec.ts`
- [X] T067 Run quickstart.md scenarios 1-4 to validate all Phase 5 features end-to-end
- [X] T068 Final review: ensure all 4 Agent subgraphs have README per Constitution I

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately (directory creation only)
- **Foundational (Phase 2)**: Depends on Setup — blocks ALL user stories (shared tools needed by M16/M17/M18)
- **US1 (Phase 3, P1)**: Depends on Foundational — No dependencies on other user stories
- **US2 (Phase 4, P1)**: Depends on Foundational — No dependencies on other user stories
- **US3 (Phase 5, P2)**: Depends on Foundational — No dependencies on other user stories
- **US4 (Phase 6, P2)**: Depends on Foundational — No dependencies on other user stories
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — No dependency on US2/US3/US4
- **US2 (P1)**: Can start after Foundational — No dependency on US1/US3/US4; requires Phase 4 M15 report node (assumed complete)
- **US3 (P2)**: Can start after Foundational — No dependency on US1/US2/US4; requires Phase 2 M08 error_questions (assumed complete)
- **US4 (P2)**: Can start after Foundational — No dependency on US1/US2/US3

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Constitution III)
- State → Nodes → Prompts → Service → Graph → API → Frontend (core → I/O)
- Story complete before moving to next priority

### Parallel Opportunities

| Phase | Parallelizable Tasks |
|---|---|
| Phase 1 (Setup) | T001 ∥ T002 |
| Phase 2 (Foundational) | T003 ∥ T004 ∥ T005 |
| Phase 3 (US1 Tests) | T006 ∥ T007 |
| Phase 3 (US1 Impl) | T009 ∥ T010 ∥ T011 ∥ T012 ∥ T013 ∥ T014 (all nodes/prompts) |
| Phase 4-6 | US1 ∥ US2 ∥ US3 ∥ US4 (4 independent agents, can be developed in parallel) |
| Phase 7 (Polish) | T064 ∥ T065 ∥ T066 |

---

## Parallel Example: User Story 1

```bash
# Tests (must fail first):
cd backend && python -m pytest tests/contract/test_agents_api.py::test_resume_optimize -x --no-header -q 2>&1 | head -5
cd backend && python -m pytest tests/integration/test_resume_optimize.py -x --no-header -q 2>&1 | head -5

# All nodes & prompts in parallel:
Task: "Create load_branch.py in backend/app/agents/nodes/resume_optimize/"
Task: "Create diff_jd.py in backend/app/agents/nodes/resume_optimize/"
Task: "Create suggest_blocks.py in backend/app/agents/nodes/resume_optimize/"
Task: "Create apply_or_discard.py in backend/app/agents/nodes/resume_optimize/"
Task: "Create snapshot.py in backend/app/agents/nodes/resume_optimize/"
Task: "Create prompts diff_jd.md + suggest_blocks.md in backend/app/agents/prompts/resume_optimize/"
```

---

## Implementation Strategy

### MVP First (US1 Only — Resume Optimize)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — shared tools)
3. Complete Phase 3: User Story 1 (M16 Resume Optimize)
4. **STOP and VALIDATE**: Test M16 independently (start → interrupt → confirm)
5. Deploy/demo if ready

### Incremental Delivery

1. **Phase 1-2 complete** → Foundation ready (shared tools in place)
2. **+ US1 (M16)** → AI resume optimization works → Deploy/Demo (MVP!)
3. **+ US2 (M18)** → Auto ability diagnosis after interview → Deploy/Demo
4. **+ US3 (M17)** → Error question reinforcement → Deploy/Demo
5. **+ US4 (M19)** → General AI coach → Deploy/Demo
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T005)
2. Once Foundational is done (4 shared tools):
   - Developer A: **US1 (M16)** — Resume Optimize (most complex, interrupt)
   - Developer B: **US2 (M18)** — Ability Diagnose (already has Phase 4 skeleton)
   - Developer C: **US3 (M17)** — Error Coach (medium complexity)
   - Developer D: **US4 (M19)** — General Coach (simplest, only 3 nodes)
3. Each story is independently testable — no merge conflicts between agents

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Constitution III requirement)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Phase 5 has NO new DB tables, NO new migrations, NO new dependencies**
- All Agent subgraphs reuse Phase 4 M14: checkpointer, LLM client, WS event protocol
