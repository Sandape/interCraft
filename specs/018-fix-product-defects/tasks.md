---
description: "Task list for 018-fix-product-defects (v1 Quality Batch)"
---

# Tasks: 018-fix-product-defects (v1 Quality Batch)

**Input**: Design documents from `/specs/018-fix-product-defects/`
- plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅
**Constitution**: v1.0.0 — Test-First is NON-NEGOTIABLE → 本 tasks 列表中**测试任务在每个故事内强制前置**。

**Organization**: 8 个用户故事 × 3 优先级（4 P1 / 3 P2 / 1 P3），按 spec § User Scenarios 排序。

**Test strategy**: 14 缺陷 × ≥1 个 E2E + 跨故事共用 1 个 component/unit。TDD 顺序在每个故事内显式标记：写测试 → 跑测试确认红 → 写实现 → 跑测试确认绿。

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 跨多个用户故事的共享基础设施与工具

- [ ] T001 [P] Add i18n bundle `src/lib/i18n/zh-CN.ts` (含 `interview.restore`, `errorCoach.starting`, `errorCoach.failed`, `export.empty`, `export.failed`, `login.welcomeBack`, `register.createAccount`)
- [ ] T002 [P] Create `src/lib/apiErrorToMessage.ts` with `exportErrorToMessage(e: ExportError)`, `interviewErrorToMessage(e)`, `coachErrorToMessage(e)`, `jobErrorToMessage(e)` (覆盖 401/403/404/422/5xx)
- [ ] T003 [P] Add TypeScript types `src/types/job.ts` — `Job`, `CreateJobInput`, `PatchJobInput` (统一字段名 `notes_md`)
- [ ] T004 [P] Add TypeScript type `src/types/dashboard.ts` — `Tier = 0|1|2`, `SuggestionBlock` discriminated union
- [ ] T005 [P] Update `src/api/export.ts` — 文件已存在(45 行,含 `exportResume()` + 503/502 + X-Request-ID);需新增 `ExportError` class 携带 `status` 字段, 401/404/422 走显式分支 (R-001 修复 #5 准备)
- [ ] T006 [P] Add `src/lib/__tests__/apiErrorToMessage.test.ts` 覆盖 6 个错误码 × 3 个 mapper

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 跨故事共享的 hooks / store / 全局初始化；**所有用户故事 MUST 等此阶段完成后开始**

**⚠️ CRITICAL**: 任何用户故事实现前必须先完成此阶段

- [ ] T007 Add `src/hooks/useDashboardSuggestions.ts` — `useDashboardSuggestions(): { tier, blocks }`, 档位 0/1/2 选择器 (R-006, 供 US3 / US4 共用)
- [ ] T008 [P] Add `src/hooks/useExportPdf.ts` — 包装 `api/export.ts` 的 `renderResume` + toast 反馈 (供 US1 共用)
- [ ] T009 [P] Refactor `src/hooks/useErrorCoach.ts` — 文件已存在(103 行, sync setState 模式); 真正缺的是 start 后**没有触发题目加载**(getState polling)。 改为: start() 完成 → chain `errorCoachRepo.getState(threadId)` → 拉第一题写入 state; 或起 React Query `useQuery(refetchInterval: 1500)` 轮询 (R-003 修复 #10)
- [ ] T010 [P] Add `src/lib/lock/__tests__/useLock.test.ts` — 单元覆盖 `acquire()/release()/isOwner()` (供 US1 共用)
- [ ] T011 Update `src/App.tsx` — `BrowserRouter` 加 `future={{ v7_startTransition, v7_relativeSplatPath, v7_fetcherPersist, v7_normalizeFormMethod, v7_partialHydration, v7_skipActionErrorRevalidation }}` (R-011, 供 US8 共用, 但作为基础设施提前应用)
- [ ] T012 [P] Add `backend/app/modules/interviews/__init__.py` export `_sync_ability_dimensions` 私有函数 (R-002 后端骨架, 供 US4 共用)
- [ ] T013 [P] Add `backend/tests/integration/test_interview_to_ability_sync.py` — 完整集成测试骨架, 包含 create_session/submit_answer/complete_session 准备 (供 US4 共用)

**Checkpoint**: 基础就绪 — 任何用户故事可开始并行实施

---

## Phase 3: User Story 1 — 新建简历可以直接编辑并导出 (Priority: P1) 🎯 MVP

**Goal**: 修复 Blocker（缺陷 #3 新建只读）+ 缺陷 #4 空简历假 AI + 缺陷 #5 PDF 导出 404
**Independent Test**: 创建空简历 → 立即可编辑 → 加 1 个块 → 导出 PDF 成功下载

### Tests for User Story 1 ⚠️ (TDD: 先红后绿)

- [ ] T014 [P] [US1] E2E `tests/e2e/018-fix-product-defects/resume/new-resume-editable.spec.ts` — 登录 → 新建简历 → 断言可写 + "+ 添加块" 入口可见 + 代码模式可输入 + 强制刷新后仍可写
- [ ] T015 [P] [US1] E2E `tests/e2e/018-fix-product-defects/resume/empty-resume-no-fake-ai.spec.ts` — 新建空简历 → 断言 AIOptimizePanel 显示空态, 不含 "LCP" / "76%" / "+14" 字面量
- [ ] T016 [P] [US1] E2E `tests/e2e/018-fix-product-defects/resume/pdf-export-flow.spec.ts` — 新建简历 + 1 块 → 导出 PDF → 断言下载非空 PDF; 模拟后端 500 → 断言 toast "导出服务暂不可用"
- [ ] T017 [P] [US1] Unit `src/api/__tests__/export.test.ts` — mock 200/400 EMPTY_CONTENT/401/404/500 → 断言 ExportError 抛出与文案映射
- [ ] T018 [P] [US1] Contract `backend/tests/contract/test_export_contract.py` — POST `/api/v1/export/render` 无 token=401, markdown=""=400 EMPTY_CONTENT, style_id="invalid"=400 INVALID_STYLE, format="gif"=400 INVALID_FORMAT, 正常=200 application/pdf

### Implementation for User Story 1

- [ ] T019 [US1] Diagnose 缺陷 #3 根因 + 修 useLock 静默失败 — `useLock.ts:161-165` 已有 auto-acquire, 真实失败路径 3 种可能: (a) vite 代理后端不可达 → status='conflict' 但 UI 显示 readonly; (b) `useResumeBranch` 401/404 → 早退到"未找到"; (c) URL branchId 错误。 **MUST 先打日志确认哪条路径**, 修 `useLock.ts:97` catch 分支区分"未授权"vs"网络"vs"资源不存在", 并在 `ResumeEditor.tsx:302` 早退前显示 `branchError` 而非空白只读 (R-005 修复 #3)
- [ ] T020 [US1] Update `src/pages/ResumeEditor.tsx` — `isReadOnly` 时显示可读原因文案（FR-007），不渲染裸 "只读"
- [ ] T021 [US1] Update `src/components/resume/editor/EditorSidebar.tsx` — **根因不在 AiOptimizePanel**, 而在 `EditorSidebar.tsx:18-40` 的 `MOCK_AI_SUMMARY` 硬编码常量 + `line 135` 渲染 + `line 161` `+14` + `line 166-172` `原始 72 / 当前 86` 字面量。 删除 `MOCK_AI_SUMMARY` 整段, 改用真实数据(空态时显示「暂无 AI 优化记录」, 非空时取最新 version 的 `ai_summary`), `+14` 改为真实匹配度差值 (R-014 修复 #4)
- [ ] T022 [US1] Update `src/api/export.ts` — `exportResume` 改用 T005 新增的 `ExportError` class, 401/404/422 走显式中文映射 (R-001 修复 #5, 需先于 T023 完成)
- [ ] T023 [US1] Update `src/components/resume/ExportMenu.tsx` — toast 错误用 `exportErrorToMessage` 而非裸 `Rendering failed:`

**Checkpoint**: US1 完全可独立测试 — 可作为 MVP 演示

---

## Phase 4: User Story 2 — 注册深链直达注册态 (Priority: P1)

**Goal**: 修复缺陷 #1 `/register` 不显示注册表单
**Independent Test**: 未登录访问 `/register` 看到「创建账号」表单; 已登录访问 `/register` 跳到主页

### Tests for User Story 2 ⚠️

- [ ] T024 [P] [US2] E2E `tests/e2e/018-fix-product-defects/auth/register-deep-link.spec.ts` — 3 个场景: 未登录 /register 看到注册表单; /login 点去注册切到注册态; 已登录访问 /register 跳到 /

### Implementation for User Story 2

- [ ] T025 [US2] Rewrite `src/pages/Register.tsx` — 不再 `export { default } from './Login'`, 改为 `export default function Register() { return <Login initialMode="register" /> }` (R-012 修复 #1)
- [ ] T026 [US2] Update `src/pages/Login.tsx` — `initialMode` prop 接受 "login" | "register"; 监听 `searchParams.get('mode')` 变化时切换 (避免仅挂载时读一次)

**Checkpoint**: US2 完成, 注册入口路径闭环

---

## Phase 5: User Story 3 — Dashboard 智能建议基于真实数据 (Priority: P1)

**Goal**: 修复缺陷 #2 Dashboard 假数据, 落地 Q2 三档渐进披露
**Independent Test**: 新账号看到档位 0 CTA; 完成 1 场面试看到档位 1; 完成 3 场 + 简历 + 错题 + 投递看到档位 2

### Tests for User Story 3 ⚠️

- [ ] T027 [P] [US3] Unit `src/pages/__tests__/Dashboard.test.tsx` — 3 个 fixture (零数据 / 1 场面试 / 3 场面试+齐全), 断言不出现 "字节跳动" / "系统设计" / "失分 N 次" 字面量
- [ ] T028 [P] [US3] Unit `src/hooks/__tests__/useDashboardSuggestions.test.ts` — 档位选择器 3 个 case (档位 0/1/2 边界)
- [ ] T029 [P] [US3] E2E `tests/e2e/018-fix-product-defects/dashboard/no-fake-suggestions.spec.ts` — 新账号访问 /dashboard, 见到档位 0 CTA
- [ ] T030 [P] [US3] E2E `tests/e2e/018-fix-product-defects/dashboard/progressive-tiers.spec.ts` — 3 个数据档位的 E2E 验证

### Implementation for User Story 3

- [ ] T031 [US3] Update `src/pages/Dashboard.tsx` — 删除硬编码"系统设计失分 3 次"/"字节跳动简历分支"/"+14" 等字面量, 改用 `useDashboardSuggestions()` (R-006 修复 #2)
- [ ] T032 [US3] Verify `src/hooks/useDashboardSuggestions.ts` (Phase 2 T007 已在 Setup) 实际数据 hook 集成: `useAbilities` + `useInterviewSessions` + `useResumeBranches` + `useErrorQuestions` + `useJobs`

**Checkpoint**: US3 完成, Dashboard 不再撒谎

---

## Phase 6: User Story 4 — 面试评分与能力画像口径一致 (Priority: P1)

**Goal**: 修复缺陷 #8 量纲 + 缺陷 #9 能力画像同步 (唯一后端改动)
**Independent Test**: 完成 1 场面试 → 报告卡显示 "X.X / 10" + "满分 10"; 立即 /ability-profile 看到对应维度分 > 0

### Tests for User Story 4 ⚠️

- [ ] T033 [P] [US4] E2E `tests/e2e/018-fix-product-defects/interview/scoring-scale-0-10.spec.ts` — 完成面试后报告卡显示 "X.X / 10"; 全应用 string 巡检无 "/ 100" 形式
- [ ] T034 [P] [US4] E2E `tests/e2e/018-fix-product-defects/interview/ability-sync.spec.ts` — 完成面试后立即打开 /ability-profile, 至少 1 个维度 actual_score > 0
- [ ] T035 [P] [US4] Integration `backend/tests/integration/test_interview_to_ability_sync.py` (T013 骨架已就位) — 完成 5 题面试后断言 `ability_dimensions` 出现 `source='interview'` 新行, `actual_score == 题均分`

### Implementation for User Story 4

- [ ] T036 [US4] Update `src/pages/InterviewReport.tsx` — 报告卡 `total / 10` + 文案 "满分 10" (Q1 锁定, R-009 修复 #8)
- [ ] T037 [US4] Update `src/pages/AbilityProfile.tsx` — 维度分 `X.X / 10` (禁止 0-100)
- [ ] T038 [US4] Update `src/pages/Dashboard.tsx` — 综合能力卡 `X.X / 10` (与 AbilityProfile 对齐)
- [ ] T039 [US4] Update `backend/app/modules/interviews/service.py` — 在 `complete_session()` 末尾调用 `await self._sync_ability_dimensions(session.id, user_id)` (R-002 修复 #9, 唯一后端改动)
- [ ] T040 [US4] Implement `_sync_ability_dimensions` in `backend/app/modules/interviews/service.py` — 聚合该 session 每 dim 题均分 (0-10), 通过 `AbilityDimensionRepository.patch(user_id, dim, {actual_score, source: "interview"})` 写入; 加结构化日志 `log.info("interview.ability_sync", session_id, user_id, dim, score)`

**Checkpoint**: US4 完成, 面试量纲统一, 能力画像同步生效

---

## Phase 7: User Story 5 — 面试启动关联简历、恢复状态友好 (Priority: P2)

**Goal**: 修复缺陷 #6 面试未关联简历 + 缺陷 #7 恢复英文文案
**Independent Test**: 新建面试表单有简历下拉; 强制刷新后看到中文恢复文案

### Tests for User Story 5 ⚠️

- [ ] T041 [P] [US5] E2E `tests/e2e/018-fix-product-defects/interview/setup-resume-pick.spec.ts` — 有 1 份简历 → 看到下拉 + 可选; 无简历 → 控件禁用 + 看到引导
- [ ] T042 [P] [US5] E2E `tests/e2e/018-fix-product-defects/interview/restore-zh-text.spec.ts` — 进行中面试刷新 → 顶部显示「已恢复 N 道回答, M 道题目, K 个评分」

### Implementation for User Story 5

- [ ] T043 [US5] Update `src/pages/InterviewLive.tsx` setup phase — 新增「使用简历」Select 控件, 数据源 `useResumeBranches()` (R-007 修复 #6)
- [ ] T044 [US5] Update `src/api/interviews.ts` — `startInterview` 入参加 `branch_id: UUID | null`
- [ ] T045 [US5] Update `src/pages/InterviewLive.tsx:549` — 恢复文案改为「已恢复 N 道回答, M 道题目, K 个评分」, 文案 key 存 `src/lib/i18n/zh-CN.ts:interview.restore` (R-008 修复 #7)
- [ ] T046 [US5] Update `src/pages/InterviewLive.tsx` — 无简历引导分支: 控件禁用 + 提示「暂无可用简历, 是否先创建?」+ 跳转 /resume/new

**Checkpoint**: US5 完成, 面试 setup 与恢复体验闭环

---

## Phase 8: User Story 6 — 错题 Coach 启动有反馈、错题自动选中 (Priority: P2)

**Goal**: 修复缺陷 #10 Coach 无反馈 + 缺陷 #11 新增未自动选中
**Independent Test**: 点「开始强化」5s 内见 loading/error/第一题; 新建错题后右侧自动定位

### Tests for User Story 6 ⚠️

- [ ] T047 [P] [US6] Unit `src/components/error-book/__tests__/ErrorCoachPanel.test.tsx` — mock start 5s 才返 → 1.5s 内见 loading; mock state=running → 显第一题; mock state=error → 显错误 + 重试按钮
- [ ] T048 [P] [US6] Unit `src/hooks/__tests__/useErrorCoach.test.ts` — 验证 `refetchInterval: 1500` 配置; status=done/error 时停轮询
- [ ] T049 [P] [US6] E2E `tests/e2e/018-fix-product-defects/error-book/coach-start-feedback.spec.ts` — 错题详情点开始强化 → 5s 内见 loading/题; 后端 503 → 见「启动失败, 请重试」
- [ ] T050 [P] [US6] E2E `tests/e2e/018-fix-product-defects/error-book/auto-select-new.spec.ts` — 新建错题 → 右侧自动切换 + 列表高亮

### Implementation for User Story 6

- [ ] T051 [US6] Update `src/hooks/useErrorCoach.ts` (Phase 2 T009 已在 Setup) — 确认 React Query 轮询与状态终态停止逻辑 (R-003 修复 #10)
- [ ] T052 [US6] Update `src/components/error-book/ErrorCoachPanel.tsx` — 显示 loading 状态文案; state=error 时保留「重试」按钮
- [ ] T053 [US6] Update `src/pages/ErrorBook.tsx` `handleCreate` — `await api.createErrorQuestion()` 后 `queryClient.setQueryData(['error-questions'], (old) => [newItem, ...old ?? []])` 再 `setSelectedId(created.id)` (R-013 修复 #11)
- [ ] T054 [US6] Add `src/lib/apiErrorToMessage.ts` coach mapper — `COACH_UNAVAILABLE` / `COACH_TIMEOUT` / 5xx → 中文文案

**Checkpoint**: US6 完成, 错题本体验闭环

---

## Phase 9: User Story 7 — 求职记录备注可保存可展示 (Priority: P2)

**Goal**: 修复缺陷 #12 求职记录备注未保存
**Independent Test**: 添加带备注职位 → 列表备注列非"—" → 编辑回填 → 修改后保存

### Tests for User Story 7 ⚠️

- [ ] T055 [P] [US7] Unit `src/api/__tests__/jobs.test.ts` — 创建/编辑/读取 jobs API 字段 `notes_md` 映射
- [ ] T056 [P] [US7] Contract `backend/tests/contract/test_jobs_notes_field.py` — POST /jobs { notes_md: "X" } → DB 行 notes_md="X"; GET 回返; PATCH 更新
- [ ] T057 [P] [US7] E2E `tests/e2e/018-fix-product-defects/jobs/notes-roundtrip.spec.ts` — 添加带备注职位 → 列表显示; 编辑回填; 修改保存

### Implementation for User Story 7

- [ ] T058 [US7] Update `src/api/jobs.ts` — send/recv 字段从 `note` 改为 `notes_md` (R-004 修复 #12, Q3 锁定)
- [ ] T059 [US7] Update `src/pages/Jobs.tsx` — 表单 `notes_md` state, 列表 `j.notes_md`, 编辑回填 `notes_md`
- [ ] T060 [US7] Update `src/repositories/jobs.ts` — `JobRepository.create/patch` payload 用 `notes_md`

**Checkpoint**: US7 完成, 求职记录备注字段映射修复

---

## Phase 10: User Story 8 — 生产级 Console 与无障碍 (Priority: P3)

**Goal**: 修复缺陷 #14 Router warnings + 缺陷 #13 退出登录菜单语义
**Independent Test**: 主流程页面 console 无 future flag warning; 退出登录可被 `getByRole` 稳定定位

### Tests for User Story 8 ⚠️

- [ ] T061 [P] [US8] E2E `tests/e2e/018-fix-product-defects/shell/router-future-flags.spec.ts` — 巡检主流程页面 console, 不出现 6 个 v7 future flag warning
- [ ] T062 [P] [US8] E2E `tests/e2e/018-fix-product-defects/auth/logout-menu-semantics.spec.ts` — 打开菜单 → `getByRole('button', { name: /退出登录/ })` 命中; 点击跳 /login
- [ ] T063 [P] [US8] Unit `src/components/layout/__tests__/Topbar.test.tsx` — 「退出登录」与「注销账号」不在同一危险色区; 两者间有 separator; 键盘 Tab 可达

### Implementation for User Story 8

- [ ] T064 [US8] Verify `src/App.tsx` (Phase 2 T011 已在 Setup 加 future flag, 此处确认 6 个 flag 全 opt-in) — 若发现漏, 补齐 (R-011 修复 #14)
- [ ] T065 [US8] Update `src/components/layout/Topbar.tsx` — 「退出登录」从 danger 区移到常规区; 与「注销账号」用 separator 分隔; 保持 a11y name 「退出登录」(R-010 修复 #13)

**Checkpoint**: US8 完成, 控制台干净 + 菜单可访问

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: 跨多个用户故事的关注点

- [ ] T066 [P] Run `npx playwright test --grep "018-fix-product-defects"` — 14 个 E2E spec 全绿
- [ ] T067 [P] Run `npm run lint && npm run typecheck` in `D:/Project/eGGG` — 前端 0 error
- [ ] T068 [P] Run `uv run pytest tests/contract/ tests/integration/` in `D:/Project/eGGG/backend` — 后端 2 个新文件全绿
- [ ] T069 [P] Run `uv run ruff check . && uv run mypy app/` in `D:/Project/eGGG/backend` — 后端 0 error
- [ ] T070 String lint — 巡检 `src/` 不出现 "字节跳动简历分支" / "系统设计失分 3 次" / "LCP 1.4s" / "76% 复用" / "+14" / "Restored N answers" / "/ 100" 等旧字面量
- [ ] T071 [P] Verify `specs/018-fix-product-defects/checklists/requirements.md` 11/11 项仍全勾选
- [ ] T072 [P] Update `tests/e2e/seed.spec.ts` (若存在 shared seed) — 添加本批次测试用户 / fixture
- [ ] T073 [P] Run `npx playwright test` (全量回归) — 不破坏既有 016 / 017 等特性的 E2E
- [ ] T074 Bump `CHANGELOG.md` (or `specs/CHANGELOG.md` 若项目用) — 018-fix-product-defects 入口

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖, 立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1 完成 — **阻塞所有用户故事**
- **Phase 3..10 (User Stories)**: 依赖 Phase 2 完成
  - US1, US2, US3, US4 (P1) 可在 Phase 2 完成后并行 (不同文件, 互不阻塞)
  - US5, US6, US7 (P2) 可在 US1..4 完成后并行 (US6 依赖 T051 useErrorCoach, US5 依赖 T043 setup form)
  - US8 (P3) 可与所有故事并行 (改 App.tsx + Topbar.tsx, 与其他故事无文件冲突)
- **Phase 11 (Polish)**: 依赖所有期望交付的用户故事完成

### User Story Dependencies

- **US1 (P1)**: Phase 2 完成后可开始 — 独立于其他故事
- **US2 (P1)**: 独立 — 改 Register.tsx + Login.tsx, 与其他故事无文件冲突
- **US3 (P1)**: 依赖 T007 useDashboardSuggestions (Phase 2) — 改 Dashboard.tsx
- **US4 (P1)**: 依赖 T012 / T013 骨架 (Phase 2) — 跨前后端, 唯一耦合
- **US5 (P2)**: 改 InterviewLive.tsx — 与 US4 同一文件但不同 phase, **串行** (US4 完成后再 US5)
- **US6 (P2)**: 改 ErrorBook.tsx + useErrorCoach + ErrorCoachPanel — 独立
- **US7 (P2)**: 改 Jobs.tsx + jobs.ts API + jobs.ts repository — 独立
- **US8 (P3)**: 改 App.tsx (Phase 2 已加 future flag) + Topbar.tsx — 独立

### Within Each User Story

- 测试任务 [P] 必须在实现任务之前
- 实现任务顺序: hooks → components → pages → API
- 跨文件实现可标 [P] 并行

### Parallel Opportunities

- **Phase 1**: T001..T006 全部 [P] — 6 个不同文件, 可并行
- **Phase 2**: T007 / T008 / T009 / T010 / T012 / T013 [P] — 但 T011 必须在 T007 之后 (App.tsx 内 useDashboardSuggestions import 之前需先存在)
- **P1 故事**: US1 (tests/e2e/018-fix-product-defects/resume + src/api/export + src/components/resume) ∥ US2 (src/pages/Register + Login) ∥ US3 (src/pages/Dashboard + src/hooks) ∥ US4 (src/pages/InterviewReport + AbilityProfile + backend)
- **P2 故事**: US5 (InterviewLive) ∥ US6 (ErrorBook + useErrorCoach) ∥ US7 (Jobs + jobs API)
- **P3 故事**: US8 (App.tsx + Topbar) 与 P1/P2 任意并行
- **Polish**: T066 / T067 / T068 / T069 / T070 / T071 [P]

---

## Parallel Example: User Story 1 (示例)

```bash
# US1 测试任务全部 [P], 可并行启动 5 个 LLM:
Task T014 [P] [US1] E2E new-resume-editable.spec.ts
Task T015 [P] [US1] E2E empty-resume-no-fake-ai.spec.ts
Task T016 [P] [US1] E2E pdf-export-flow.spec.ts
Task T017 [P] [US1] Unit export.test.ts
Task T018 [P] [US1] Contract test_export_contract.py

# US1 实现任务 (依赖测试, 串行):
Task T019 [US1] ResumeList 新建分支后 acquire lock
Task T020 [US1] ResumeEditor isReadOnly 可读原因
Task T021 [US1] AiOptimizePanel 空态守卫
Task T022 [US1] api/export.ts ExportError + 映射
Task T023 [US1] ExportMenu toast 用 exportErrorToMessage
```

---

## Implementation Strategy

### MVP First (US1 Only — Blocker 修复)

1. Phase 1 + Phase 2 完成 (T001..T013)
2. Phase 3 (US1) 完成 (T014..T023)
3. **STOP and VALIDATE**: 跑 T066 E2E subset
4. 部署: Blocker 修复 + 空态 + PDF 导出可上线

### Incremental Delivery

1. Phase 1 + Phase 2 → 基础就绪
2. US1 → 验证 → 部署 (MVP — Blocker 已修)
3. US2 + US3 + US4 (剩余 P1) → 验证 → 部署 (注册深链 + Dashboard 真实 + 量纲统一)
4. US5 + US6 + US7 (P2) → 验证 → 部署 (面试体验 + 错题 + 求职)
5. US8 (P3) → 验证 → 部署 (console 干净 + 菜单可达)
6. 每个故事加值不破坏前序

### Parallel Team Strategy

- 单人: 按 P1 → P2 → P3 串行
- 2 人:
  - Person A: US1 + US5 (resume + interview 域)
  - Person B: US3 + US6 + US7 (dashboard + error + jobs 域)
  - 共享: US2 (Register/Login) + US4 (后端) + US8 (App/Topbar)
- 3 人:
  - Person A: US1 + US5
  - Person B: US2 + US3 + US8
  - Person C: US4 (含后端) + US6 + US7

---

## Notes

- [P] 任务 = 不同文件, 无依赖
- [Story] 标签映射每个任务到 spec § User Story, 用于追溯
- 每个用户故事可独立完成 + 测试 + 部署
- 严格 TDD: 写测试 → 跑红 → 写实现 → 跑绿
- US4 是**唯一涉及后端的故事** (T039 + T040), 跨 backend/app/modules/interviews/service.py
- 14 缺陷 → 22 FR → 74 任务 (含 27 测试任务)
- 总测试文件: 14 E2E + 5 单元 + 3 集成/契约
- **T039 + T040 是唯一后端代码改动, 其他 72 任务全是前端 / 测试 / 配置**
- 巡检任务 T070 是关键回归保险: 旧字面量不得复活

---

## Summary

| 维度 | 数 |
|---|---|
| 总任务数 | 74 |
| 测试任务 | 27 (E2E: 14 / 单元: 7 / 集成+契约: 3 / 其他: 3) |
| 实现任务 | 38 |
| Polish 任务 | 9 |
| P 标记 (可并行) | 49 |
| 用户故事数 | 8 |
| 后端代码改动 | 2 个任务 (T039 + T040) |
| Schema 变更 | 0 |
| 新依赖 | 0 |
| 预计 MVP 任务 | 23 (Phase 1+2+3) |
