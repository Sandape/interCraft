# Research: 018-fix-product-defects

**Phase**: 0 — Outline & Research
**Date**: 2026-06-17
**Owner**: plan workflow
**Purpose**: 把 plan § Technical Context 中所有 NEEDS CLARIFICATION 收敛为"已决策"，并记录关键技术抉择与备选。

> 本批次是 v1 质量修复，无新增技术栈 / 库 / 契约；research 的重点是**根因定位 + 修复策略抉择**（每个缺陷可能有 2-3 种修法），并把"为什么选这条"写下来。

---

## R-001 简历 PDF 导出 404（缺陷 #5）：客户端调用路径 vs 后端路由

### Decision
**不修改后端 export 路由**（已存在且契约合理）。在前端 `src/api/export.ts` 增加：
1. 单一调用点统一路径 `POST /api/v1/export/render`，移除 Vite 代理 / 客户端 base URL 漂移
2. 401 / 403 / 404 / 422 / 5xx 各自映射成可读中文错误
3. 渲染服务不可用时（依赖未装）引导用户重试 + 在控制台留 `request_id`

### Rationale
- 后端 `backend/app/api/v1/export.py:14,51` 已正确注册 `prefix="/export"` + `POST /render`，返回结构化错误 `{error, message, request_id}`
- "返回 404" 几乎肯定是 Vite proxy 未转发 `/api/v1` 或前端 base URL 拼错（常见漂移点：开发期用相对路径 / 生产期用绝对 URL）
- 修复成本：1 个文件 + 1 个 e2e，远低于重写后端

### Alternatives considered
- **A. 后端再加一层 facade** — 拒绝（破坏 Constitution 原则 I"Library-First"，且后端已经合理）
- **B. 前端 fetcher 抽到 React Query 全局 client** — 接受（作为 R-001 的伴随改造：建立 `apiErrorToMessage()` 工具函数，被 export.ts 复用）
- **C. 单独写一个 `useExportPdf()` hook** — 拒绝（与 R-001 单一调用点目标冲突）

### Verification
- 单元：`src/api/__tests__/export.test.ts` 覆盖 401/403/404/422/500 错误 → 中文文案映射
- E2E：`e2e/resume/pdf-export-flow.spec.ts`：登录 → 新建简历 → 加块 → 触发导出 → 收到 PDF

---

## R-002 能力画像未更新（缺陷 #9）：同步触发位置

### Decision
**在 `backend/app/modules/interviews/service.py` 的 `complete_session()` 末尾，按 5 题每题 `dim` 标签聚合 → 对每个 dim 调用 `ability_profile_repo.patch(user_id, dim, {"actual_score": Decimal(mean_0_10), "source": "interview"})`**。不引入新的 LLM 调用，沿用 `AbilityDimensionRepository.patch` 已有的 SQL 路径（参考 `self_assess` 实现：`backend/app/modules/ability_profile/service.py:187-216`）。

### Rationale
- `backend/app/modules/ability_profile/service.py:36-100` 是只读路径，**未发现**任何 "interview 完成 → ability_dimensions 写入" 的调用
- 写入口是 `AbilityDimensionRepository.patch(user_id, dim, {actual_score, source, sub_scores})`，由 `self_assess` 使用（`service.py:204-210`）
- 维度白名单 `ALLOWED_DIMENSION_KEYS`（`backend/app/modules/abilities/schemas.py`）已由 Feature 005 定义，patch 走同一白名单
- 面试 5 题每题带 `dim` 标签（Phase 4 / 5 已实现），取该 session 每 dim 的题均分（0-10 量纲）作为 score；`source='interview'` 让 `aggregate_system_scores` 在读取时用上时间加权（`service.py:218-258`）

### Alternatives considered
- **A. 在 `interview_report` 生成时同步触发** — 接受，但耦合更深；选 `complete_session` 是单一事实点
- **B. 用 arq 异步任务** — 拒绝（缺陷描述"完成面试后能力画像未更新"已让用户失去信任，再做异步会让"更新中"窗口更长）
- **C. 让前端在前端拉报告后主动调 `POST /ability-profile/refresh`** — 拒绝（破坏 Constitution 原则 IV"用户数据 MUST 走 RLS"，且违反"不引入前端补偿"原则）

### Verification
- 集成测试 `backend/tests/integration/test_interview_to_ability_sync.py`：
  1. 创建 user + 简历分支 + 5 题面试（每题带 `dim` 标签）
  2. 提交 5 个答案，调用 `complete_session()`
  3. 立即 `GET /api/v1/ability-profile/dashboard`，断言对应 dim 分数 > 0
  4. 同时 patch 验证：DB 行 `ability_dimensions` 出现新行，`source='interview'`，`actual_score == 题目均分（0-10）`
- E2E：`e2e/interview/ability-sync.spec.ts`：登录 → 完成一场面试 → 立即打开 `/ability-profile` 看到维度分 > 0

---

## R-003 错题 Coach 启动无反馈（缺陷 #10）：轮询 vs WS 推送

### Decision
**前端 `useErrorCoach` 在 `start()` 后建立 `setInterval(1500ms)` 轮询 `GET /api/v1/agents/error-coach/{thread_id}/state`，直到状态为 `running` / `awaiting_answer` / `done` / `error` 任一终态**。同时保留 WS 推送作为优化路径（若 WS 收到 `coach.state` 则提前清掉轮询）。

### Rationale
- 后端 `backend/app/api/v1/agents_error_coach.py:18,70` 已暴露 `POST /start` 与 `GET /{thread_id}/state`
- 当前实现是"fire-and-forget"，前端 `start()` 后只设了 `started=true` 就停，没有反馈循环
- 5 秒内必须给反馈（SC-006），轮询周期 1.5s + 后端 0.5s 处理 = 2s 内首响，达标
- WS 已经接好（`backend/app/modules/errors/` 与 `agents_error_coach.py:139`），用作加速而非唯一通道

### Alternatives considered
- **A. 只走 WS 推送** — 拒绝（WS 在某些网络环境会断，轮询是兜底）
- **B. 用 React Query 替代手写轮询** — 接受（`useQuery({ refetchInterval: 1500 })` 比手写 setInterval 更声明式）
- **C. 把 Coach 状态写到 React Query cache，前端订阅** — 接受（作为实现细节）

### Verification
- 组件测试 `src/components/error-book/__tests__/ErrorCoachPanel.test.tsx`：mock 5s 才返回 → 断言 1.5s 内出现 loading 指示
- E2E：`e2e/error-book/coach-start-feedback.spec.ts`：点"开始强化" → 5s 内见到 loading / 错误 / 第一道题

---

## R-004 求职记录备注字段名（缺陷 #12）：前端 vs 后端字段映射

### Decision
**前端 `src/api/jobs.ts` + `src/pages/Jobs.tsx` + `src/repositories/jobs.ts` 全部将字段名从 `note` 改为 `notes_md`（匹配后端 `backend/app/modules/jobs/schemas.py:15,23,47` 与 `models.py:36`）**。后端 schema / DB 字段 `notes_md`（Text nullable）不动。

### Rationale
- 后端实际字段：`JobApplication.notes_md`（db）+ `CreateJobInput.notes_md` / `PatchJobInput.notes_md` / `JobOut.notes_md`（pydantic）
- 前端当前用 `note` / `j.note` / `JobRepository.create({ note })` → 后端 `model_dump(exclude_none=True)` 不映射别名 → 字段被静默丢弃
- 这是 Q3 验证的结论：schema 已存在，**只修前端**

### Alternatives considered
- **A. 后端加 `note` 别名** — 拒绝（鼓励脏数据；Pydantic alias 在序列化时也漂移）
- **B. 前端发 payload 时手工 attach 两次** — 拒绝（脆弱）
- **C. 用 zod / pydantic 双向 codegen** — 长期方案，超出本批次；现选最简"对齐字段名"

### Verification
- 单元：`src/api/__tests__/jobs.test.ts`：mock API 收到 `{notes_md: "X"}`，断言 UI 显示 X
- 契约测试 `backend/tests/contract/test_jobs_notes_field.py`：POST /jobs with `{notes_md: "X"}` → DB 行有 X；GET /jobs/{id} 返 X
- E2E：`e2e/jobs/notes-roundtrip.spec.ts`：添加带备注的职位 → 列表备注列非 — → 编辑回填原备注

---

## R-005 简历编辑器只读（缺陷 #3）：新建分支立即申请锁 vs 后端空分支豁免

### Decision
**前端 `ResumeList.tsx` 在新建分支成功后立即调用 `useLock('resume_branch', branchId).acquire()`**，后端在 `isReadOnly` 决策里**保留**只读语义（不豁免空分支），保证锁协议一致性。

### Rationale
- 后端默认只读 = "未持有锁"，锁协议在 Feature 003 / Phase 3 已固化
- 新建空分支后没主动申请锁 → 第一次刷新读到后端 `isReadOnly=true`
- 前端补 `acquire()` 是最小改动；后端豁免会破坏"锁 = 写权限"的不变量

### Alternatives considered
- **A. 后端空分支豁免只读** — 拒绝（破坏 Phase 3 锁协议）
- **B. 前端新建分支时同步调 POST /resume-branches + POST /locks/acquire** — 接受（实现方式）
- **C. 简历创建时后端默认分配锁** — 拒绝（隐式副作用，不符合 Library-First 显式 API）

### Verification
- 单元：`src/lib/lock/__tests__/useLock.test.ts`：模拟新建分支 → 调 acquire → isReadOnly=false
- E2E：`e2e/resume/new-resume-editable.spec.ts`：新建 → 看到 "添加块" 入口 → 点击 → 成功新增块

---

## R-006 Dashboard 假数据（缺陷 #2）：三档渐进式披露数据流

### Decision
**前端 `src/pages/Dashboard.tsx` 引入一个 `useDashboardSuggestions(tier)` selector hook**，根据当前用户的真实数据档位（0/1/2）渲染对应区块。硬编码的"系统设计失分 3 次""字节跳动简历分支"等字面量**全部删除**。

档位规则（Q2 锁定）：
- **档位 0**：无面试/简历/错题/投递 → CTA
- **档位 1**：≥1 场面试 且 简历/错题/投递 三项中 <2 项 → 单场面试要点 + 关联简历
- **档位 2**：≥3 场面试 且 简历+错题+投递 齐全 → 全局综合建议

### Rationale
- 现有 Dashboard 是写死的字面量（"硬编码"），没有从 useAbilities 派生
- `useAbilities()` 已经返回 `{dimensions, dashboard, refresh}`，3 档选择器只需在 selector 层判断数据稀疏度
- 避免引入新 AI 能力生成建议（Q4 隐含决策：A-004 已声明"不引入新 AI 能力"）

### Alternatives considered
- **A. 引入"建议生成器"后端 endpoint** — 拒绝（A-004 限定，不引入新 AI 能力）
- **B. 用现成的 `useSuggestions()` store** — 拒绝（store 是 mock 数据源，不是真实数据）
- **C. 三档用同一个组件 + tier prop** — 接受（实现方式）

### Verification
- 单元：`src/pages/__tests__/Dashboard.test.tsx` 三档 fixture
- E2E：`e2e/dashboard/no-fake-suggestions.spec.ts` + `e2e/dashboard/progressive-tiers.spec.ts`

---

## R-007 面试启动关联简历（缺陷 #6）：表单加 branch 下拉

### Decision
**前端 `src/pages/InterviewLive.tsx` 的 setup phase 增加 "选择简历分支" 控件**，使用 `useResumeBranches()` 拉取当前用户的简历分支列表（已存在 Feature 002 能力）。提交时 body 带 `branch_id`。后端 `POST /interview-sessions` schema 已支持 `branch_id`（Feature 002 落库），不动。

### Rationale
- Feature 002 已实现 branch 选择器 + 简历 branch 与 interview 的关联（DB 字段存在）
- 前端 setup form 只收集 `position` / `company`，遗漏 `branch_id` → 提交时 null → 报告无简历关联
- 最小改动：setup form 加 1 个 select + 1 个 useResumeBranches 调用

### Alternatives considered
- **A. 强制必须有简历分支** — 拒绝（破坏无简历用户路径；FR-011 明示可跳过）
- **B. 自动选最近编辑的简历** — 接受（默认值；用户可改）

### Verification
- 单元：`src/pages/__tests__/InterviewLive.setup.test.tsx`
- E2E：`e2e/interview/setup-resume-pick.spec.ts`

---

## R-008 面试恢复英文文案（缺陷 #7）：硬编码字符串本地化

### Decision
**前端 `src/pages/InterviewLive.tsx:549` 把 `Restored {n} answers, {m} questions, {k} scores.` 改为中文：`已恢复 {n} 道回答，{m} 道题目，{k} 个评分`**，并把此字符串移到 i18n bundle（即便当前只有 zh-CN）。

### Rationale
- 单行硬编码改文案 + 加 i18n key 准备后续多语言
- 不引入 i18n 库（避免超 scope），仅在 `src/lib/i18n/zh-CN.ts` 维护一份

### Alternatives considered
- **A. 引入 react-i18next** — 拒绝（超 scope）
- **B. 不本地化，只改文案** — 接受（最小实现，i18n 留给未来）

### Verification
- E2E：`e2e/interview/restore-zh-text.spec.ts`

---

## R-009 面试总分 0-10 vs 0-100（缺陷 #8）：全应用统一到 0-10

### Decision
**所有"总分 / 能力分"展示位统一 0-10 量纲**：
- `src/pages/InterviewReport.tsx`：报告卡显示 `X.X / 10` + `满分 10`
- `src/pages/AbilityProfile.tsx`：维度分显示 `X.X / 10`
- `src/pages/Dashboard.tsx`：综合能力卡显示 `X.X / 10`
- 后端 LLM 出题 prompt 不动（保持 0-10 粒度）
- **禁止**任何位置出现 `X / 100` 形式的总分

### Rationale
- Q1 锁定：保留 0-10 粒度，不做 0-100 换算
- 现状是 Dashboard 误用 0-100 语义 + 报告"满分 100" 文案错位
- 量纲统一后 LLM 出题 → 题分 → 总分 → 能力分 → Dashboard 全部 0-10 一致

### Alternatives considered
- **A. 全文换 0-100** — 拒绝（Q1 选项 C 被否）
- **B. 报告 / Dashboard 各自量纲独立** — 拒绝（Q1 选项 A 已选统一 0-10）

### Verification
- E2E：`e2e/interview/scoring-scale-0-10.spec.ts` 巡检全应用 string 不含 `/ 100`

---

## R-010 退出登录菜单语义（缺陷 #13）：把"注销账号" 与"退出登录"在 UI 上分开

### Decision
**前端 `src/components/layout/Topbar.tsx`**：
- "退出登录"（`logout`）从 danger 区移到常规区，文字与"个人资料"同区，色块 = 中性
- "注销账号"（`accountDelete`）保留在 danger 区
- 两者之间加 separator，让 a11y 树清晰

### Rationale
- 现状两个动作挤在 danger 区（红色），用户 / 屏幕阅读器难以区分"退出"与"注销"
- 行为不变（Q5 隐含决策：维持 logout + deleteAccount 两条 API），只改视觉分组

### Alternatives considered
- **A. 合并为单一动作"注销"** — 拒绝（FR-022 要求可独立"退出登录"按钮）
- **B. 用 menuitem role 替代 button** — 拒绝（FR-022 选项 A 优先 button）

### Verification
- E2E：`e2e/auth/logout-menu-semantics.spec.ts` 用 `getByRole('button', { name: /退出登录/ })` 稳定定位

---

## R-011 React Router future flags（缺陷 #14）：opt-in 所有 v7 future flag

### Decision
**`src/App.tsx:116` 的 `<BrowserRouter>` 改为：**

```tsx
<BrowserRouter
  future={{
    v7_startTransition: true,
    v7_relativeSplatPath: true,
    v7_fetcherPersist: true,
    v7_normalizeFormMethod: true,
    v7_partialHydration: true,
    v7_skipActionErrorRevalidation: true,
  }}
>
```

### Rationale
- react-router-dom 6.27 已支持上述所有 v7 future flag
- 一次性 opt-in 消除控制台 warning，避免技术债积累
- 行为差异（v7_startTransition 让导航走 React 18 startTransition）已与 React 18 + StrictMode 兼容

### Alternatives considered
- **A. 升级到 react-router-dom 7** — 拒绝（独立升级路径，超出本批次）
- **B. 只 suppress warning，不 opt-in** — 拒绝（治标不治本，warning 还会以其他形式出现）

### Verification
- E2E：`e2e/shell/router-future-flags.spec.ts` 巡检 console 不含 future flag warning

---

## R-012 /register 深链（缺陷 #1）：让 Register.tsx 不再 re-export Login

### Decision
**前端 `src/pages/Register.tsx` 从 `export { default } from './Login'` 改为显式包装：**

```tsx
import Login from './Login'
export default function Register() {
  return <Login initialMode="register" />
}
```

并让 `Login.tsx` 的 `initialMode` 在 `searchParams.get('mode')` 变化时同步更新（而非仅挂载时读一次）。

### Rationale
- Register.tsx 当前 re-export Login，丢失"我是注册页"的语义
- 修复后 `/register` 路径稳定进入注册态
- FR-002 已登录态访问 `/register` 的跳转行为由 App.tsx 的"已登录守卫"覆盖

### Alternatives considered
- **A. App.tsx 路由里写 `<Register />` 与 `<Login />` 是两个组件实例** — 拒绝（重复实现）
- **B. 在 Login 内监听 `searchParams` 变化** — 接受（作为 R-012 的伴随实现）

### Verification
- E2E：`e2e/auth/register-deep-link.spec.ts`

---

## R-013 新增错题未自动选中（缺陷 #11）：在 `handleCreate` 成功后 `invalidate` 再 set

### Decision
**前端 `src/pages/ErrorBook.tsx:114-123`**：
- `handleCreate` 成功后先 `await queryClient.invalidateQueries(['error-questions'])` 再 `setSelectedId(created.id)`
- 或：直接 `setSelectedId(created.id)` 并从 cache 中 prepend 新项（避免 invalidate 等待）

### Rationale
- 现状是 `setSelectedId(created.id)` 已经存在（看似 OK），但 `items` 通过 `useMemo` filter，create 后 list 还没刷新 → selected 找不到对应 item
- 修复关键在"选中之前 list 已包含新项"
- 用 React Query 的 `setQueryData` 直接 prepend 更可控

### Alternatives considered
- **A. 选第一项而不是 created.id** — 拒绝（用户预期是新建的自动选中）
- **B. 加一个"是否包含"断言后重试** — 脆弱，放弃

### Verification
- E2E：`e2e/error-book/auto-select-new.spec.ts`

---

## R-014 空简历假 AI 摘要（缺陷 #4）：blocks.length===0 守卫

### Decision
**前端 `src/components/resume/AiOptimizePanel.tsx`**：
- 入口判断 `blocks.length === 0` → 渲染空态（"添加简历块以获取 AI 优化建议"），不调用 `/agents/resume-optimize`
- 即便 `markdown` 非空，blocks=0 也不展示摘要面板

### Rationale
- 现状是空 markdown 仍走 `useResumeOptimize` hook → 返回占位数据（前端 mock）→ 展示假摘要
- 修复后空简历完全跳过 AI 优化路径，与 FR-010 对齐

### Alternatives considered
- **A. 后端在 `notes_md` 为空时 422** — 接受（作为深度防御，但前端守卫先做）

### Verification
- E2E：`e2e/resume/empty-resume-no-fake-ai.spec.ts`

---

## 总结：14 缺陷 × 修复决策矩阵

| 缺陷 | 根因层 | 修复层 | 是否需后端 | 是否需 schema | 决策编号 |
|---|---|---|---|---|---|
| #1 /register | 前端 | 前端 | 否 | 否 | R-012 |
| #2 Dashboard 假数据 | 前端 | 前端 | 否 | 否 | R-006 |
| #3 简历只读 | 前端 | 前端 | 否 | 否 | R-005 |
| #4 空简历假 AI | 前端 | 前端 | 否 | 否 | R-014 |
| #5 PDF 导出 404 | 前端（调用路径）| 前端 | 否 | 否 | R-001 |
| #6 面试未关联简历 | 前端 | 前端 | 否 | 否 | R-007 |
| #7 恢复英文 | 前端 | 前端 | 否 | 否 | R-008 |
| #8 量纲 0-100 | 前端（多页）| 前端 | 否 | 否 | R-009 |
| #9 能力画像未更新 | 后端（缺回调）| 后端 | **是** | 否 | R-002 |
| #10 Coach 无反馈 | 前端 | 前端 | 否 | 否 | R-003 |
| #11 新增错题未选中 | 前端 | 前端 | 否 | 否 | R-013 |
| #12 求职备注 | 前端（字段名）| 前端 | 否 | 否 | R-004 |
| #13 退出登录菜单 | 前端 | 前端 | 否 | 否 | R-010 |
| #14 Router warnings | 前端 | 前端 | 否 | 否 | R-011 |

**唯一后端改动**：缺陷 #9，1 个 service 加 1 个回调 + 1 个集成测试。

**零 schema 变更** — Q3 验证后端 `notes_md` 字段已落库，本批次只修前端字段映射。
