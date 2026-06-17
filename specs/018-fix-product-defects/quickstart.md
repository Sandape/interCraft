# Quickstart: 018-fix-product-defects (v1 Quality Batch)

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-17
**Purpose**: 为 14 个缺陷提供**可执行的端到端验证场景**——按本指南可"以最少步骤复现缺陷 → 验证修复 → 回归"。

> **范围**：本批次覆盖 14 个缺陷、8 个用户故事、22 FR、11 SC。指南只列"如何验证"；具体实现细节在 [`research.md`](./research.md) 与 [`contracts/`](./contracts/)。

---

## 前置条件

```bash
# 1. 拉起后端 (本地 Redis 6379 + 在线 Postgres)
cd D:/Project/eGGG/backend
uv run uvicorn app.main:app --reload --port 8000

# 2. 拉起前端 (Vite dev server)
cd D:/Project/eGGG
npm run dev
# → http://localhost:5173

# 3. 准备一个测试账号
#    注册页: http://localhost:5173/register  （修复后能直进注册态）
#    邮箱: e2e-fix-defects@example.com
#    密码: TestPass!2026
```

## 全局环境

| 端口 | 服务 | 用途 |
|---|---|---|
| 5173 | Vite dev | 前端 |
| 8000 | FastAPI | 后端（/api/v1 前缀） |
| 6379 | Redis | arq 队列 / 会话 |
| online | Postgres | 主存 + RLS |

---

## 缺陷逐项验证

### 缺陷 #1 — /register 深链不显示注册态

**前置**：未登录。

**复现**：
1. 打开 `http://localhost:5173/register`
2. ❌ 看到「欢迎回来/登录」表单
3. ✓ 看到「创建账号」表单（含「确认密码」+「协议勾选」+「注册」按钮）

**回归测试**：
- 访问 `/login` → 看到「欢迎回来」表单
- 在 /login 点「去注册」→ URL 变为 `/register?mode=register` → 表单切换
- 已登录访问 `/register` → 跳转到 `/`

**E2E**：`tests/e2e/018-fix-product-defects/auth/register-deep-link.spec.ts`

---

### 缺陷 #2 — Dashboard 智能建议假数据

**前置**：登录新账号，无任何数据。

**复现**：
1. 打开 `http://localhost:5173/dashboard`
2. ❌ 看到「系统设计失分 3 次」「字节跳动简历分支」等字面量
3. ✓ 看到「完成首场面试以获取建议」CTA（档位 0）

**档位 1 触发**：
- 完成 1 场面试 → 看到该场面试的「失分维度 + 关联简历」（无"全局"措辞）

**档位 2 触发**：
- 完成 3 场面试 + 1 份简历 + 1 条错题 + 1 条投递 → 看到「全局综合建议」

**E2E**：`tests/e2e/018-fix-product-defects/dashboard/no-fake-suggestions.spec.ts` + `progressive-tiers.spec.ts`

---

### 缺陷 #3 — 新建简历只读

**前置**：已登录。

**复现**：
1. 进入「简历列表」 → 点「+ 新建简历」 → 填标题 → 提交
2. ❌ 跳转到编辑器后状态显示「只读」，无「+ 添加块」入口
3. ✓ 状态可编辑，「+ 添加块」可见且可点击
4. 切到「代码模式」→ textarea 可输入
5. 强制刷新（F5）→ 仍可写（锁已持有）

**E2E**：`tests/e2e/018-fix-product-defects/resume/new-resume-editable.spec.ts`

---

### 缺陷 #4 — 空简历假 AI 摘要

**前置**：已登录。

**复现**：
1. 新建空简历（不加任何块）
2. ❌ 看到「LCP 1.4s」「76% 复用」「+14」「当前 86」等字面量
3. ✓ AI 优化面板显示「添加简历块以获取 AI 优化建议」+「去添加块」按钮

**E2E**：`tests/e2e/018-fix-product-defects/resume/empty-resume-no-fake-ai.spec.ts`

---

### 缺陷 #5 — PDF 导出 404

**前置**：已登录，新建简历 + 至少 1 个块。

**复现**：
1. 在编辑器中点「导出 → PDF 文件」
2. ❌ 菜单显示 `Rendering failed: ...`，无具体错误
3. ✓ 浏览器下载一份非空 PDF（命名 `resume-{timestamp}.pdf`），UI toast「导出成功」

**错误路径回归**：
- 故意清空简历内容再导出 → toast「简历内容为空，请先添加简历块」
- 断网导出 → toast「导出服务暂不可用，请稍后重试」

**E2E**：`tests/e2e/018-fix-product-defects/resume/pdf-export-flow.spec.ts`

---

### 缺陷 #6 — 面试启动未关联简历

**前置**：已登录，有 ≥1 份简历。

**复现**：
1. 进入「新建面试」表单
2. ❌ 无「选择简历」控件
3. ✓ 有「使用简历」下拉控件，默认显示「不关联简历」，可选具体简历
4. 提交后，面试报告页显示「基于简历：xxx」提示

**无简历路径**：
- 删光所有简历 → 打开面试 setup → 控件禁用 + 提示「暂无可用简历，是否先创建？」

**E2E**：`tests/e2e/018-fix-product-defects/interview/setup-resume-pick.spec.ts`

---

### 缺陷 #7 — 面试恢复英文文案

**前置**：进行中面试（已答 2 题）。

**复现**：
1. 强制刷新（F5）页面
2. ❌ 顶部显示 `Restored 2 answers, 5 questions, 2 scores.`
3. ✓ 顶部显示「已恢复 2 道回答，5 道题目，2 个评分」
4. 浏览器控制台无 `Restored ...` 字样

**E2E**：`tests/e2e/018-fix-product-defects/interview/restore-zh-text.spec.ts`

---

### 缺陷 #8 — 面试总分 0-10 vs 0-100

**前置**：完成一场 5 题面试，每题 0-10 分。

**复现**：
1. 看完成卡
2. ❌ 显示「3.6 综合评分」+「满分 100」
3. ✓ 显示「3.6 / 10」+「满分 10」
4. 打开 `/ability-profile` → 维度分显示「X.X / 10」
5. 打开 Dashboard → 综合能力卡显示「X.X / 10」
6. 全应用 string 巡检：grep `\/ 100` 无命中

**E2E**：`tests/e2e/018-fix-product-defects/interview/scoring-scale-0-10.spec.ts`

---

### 缺陷 #9 — 完成面试后能力画像未更新

**前置**：已登录，无任何面试数据（能力画像全 0）。

**复现**：
1. 完成一场 5 题面试（每题带 dim 标签）
2. 打开 `/ability-profile`
3. ❌ 六维全 0
4. ✓ 至少 1 个维度 actual_score > 0（与该面试 dim 均分一致）
5. 打开 Dashboard → 综合能力卡显示 > 0

**后端验证**（可选）：
```bash
cd D:/Project/eGGG/backend
uv run python -m scripts.dbq
# SQL: SELECT dimension_key, actual_score, source FROM ability_dimensions WHERE source = 'interview' AND user_id = '...';
# 应看到新行
```

**E2E + 集成**：`tests/e2e/018-fix-product-defects/interview/ability-sync.spec.ts` + `backend/tests/integration/test_interview_to_ability_sync.py`

---

### 缺陷 #10 — 错题 Coach 启动无反馈

**前置**：已登录，有 ≥1 条错题。

**复现**：
1. 进入「错题详情」 → 点「开始强化」
2. ❌ 15 秒内无 loading、错误、答题表单，按钮消失
3. ✓ 1.5 秒内出现「正在启动强化辅导…」
4. ✓ 2 秒内切换到第一道强化题

**失败路径**：
- 故意 mock 后端 503 → 见到「启动失败，请重试」+「重试」按钮可点

**E2E**：`tests/e2e/018-fix-product-defects/error-book/coach-start-feedback.spec.ts`

---

### 缺陷 #11 — 新增错题未自动选中

**前置**：已登录，在「错题本」页面。

**复现**：
1. 点「+ 新建错题」 → 填内容 → 保存
2. ❌ 列表中出现新错题，但右侧详情区仍显示「请选择左侧错题查看详情」
3. ✓ 右侧详情区自动切换到该新错题内容，列表中该项高亮

**E2E**：`tests/e2e/018-fix-product-defects/error-book/auto-select-new.spec.ts`

---

### 缺陷 #12 — 求职记录备注未保存

**前置**：已登录。

**复现**：
1. 进入「求职记录」 → 点「+ 添加职位」 → 填备注「Codex E2E ... 测试投递记录」→ 提交
2. ❌ 列表「备注」列显示「—」
3. ✓ 列表「备注」列显示「Codex E2E ... 测试投递记录」

**编辑回归**：
- 点该职位「编辑」→ 备注字段回填
- 不修改备注 → 保存 → 列表仍显示原备注
- 修改备注 → 保存 → 列表更新

**E2E**：`tests/e2e/018-fix-product-defects/jobs/notes-roundtrip.spec.ts` + `backend/tests/contract/test_jobs_notes_field.py`

---

### 缺陷 #13 — 退出登录菜单语义

**前置**：已登录。

**复现**：
1. 打开个人菜单
2. ❌ 用 `getByRole('button', { name: /退出登录/ })` 定位失败
3. ✓ 稳定定位并触发
4. ✓「退出登录」与「注销账号」颜色不同：退出 = 中性，注销 = 危险红
5. ✓ 两者之间有 separator

**E2E**：`tests/e2e/018-fix-product-defects/auth/logout-menu-semantics.spec.ts`

---

### 缺陷 #14 — React Router warnings

**前置**：打开 DevTools Console。

**复现**：
1. 浏览主要页面：Dashboard / 简历 / 面试 / 错题 / 能力画像 / 设置
2. ❌ Console 多次出现 `React Router Future Flag Warning: v7_startTransition / v7_relativeSplatPath ...`
3. ✓ Console 干净，无任何 React Router future flag 警告

**E2E**：`tests/e2e/018-fix-product-defects/shell/router-future-flags.spec.ts`

---

## 批量回归命令

```bash
# 前端单元 + 组件
cd D:/Project/eGGG
npm run test
npm run typecheck
npm run lint

# 后端
cd D:/Project/eGGG/backend
uv run pytest tests/contract/ tests/integration/ -v
uv run ruff check .
uv run mypy app/

# E2E
cd D:/Project/eGGG
npx playwright test --grep "018-fix-product-defects"   # 用 grep 筛本批次

# 全量 E2E（建议每晚跑）
npx playwright test
```

## 验收矩阵（一表对照）

| 缺陷 | 验收点 | 自动化测试 |
|---|---|---|
| #1 | 100% 访问 `/register` 显示注册表单 | `tests/e2e/018-fix-product-defects/auth/register-deep-link.spec.ts` |
| #2 | 三档渐进披露，无占位文案 | `tests/e2e/018-fix-product-defects/dashboard/*.spec.ts` |
| #3 | 新建可编辑 + 锁已申请 | `tests/e2e/018-fix-product-defects/resume/new-resume-editable.spec.ts` |
| #4 | 空简历空态不假数据 | `tests/e2e/018-fix-product-defects/resume/empty-resume-no-fake-ai.spec.ts` |
| #5 | PDF 200 或可读 4xx/5xx | `tests/e2e/018-fix-product-defects/resume/pdf-export-flow.spec.ts` + `test_export_contract.py` |
| #6 | 简历可关联可跳过 | `tests/e2e/018-fix-product-defects/interview/setup-resume-pick.spec.ts` |
| #7 | 恢复中文文案 | `tests/e2e/018-fix-product-defects/interview/restore-zh-text.spec.ts` |
| #8 | 全应用 0-10 统一 | `tests/e2e/018-fix-product-defects/interview/scoring-scale-0-10.spec.ts` |
| #9 | 能力画像同步 | `tests/e2e/018-fix-product-defects/interview/ability-sync.spec.ts` + `test_interview_to_ability_sync.py` |
| #10 | 5s 内有反馈 | `tests/e2e/018-fix-product-defects/error-book/coach-start-feedback.spec.ts` |
| #11 | 新建自动选中 | `tests/e2e/018-fix-product-defects/error-book/auto-select-new.spec.ts` |
| #12 | 备注字段映射正确 | `tests/e2e/018-fix-product-defects/jobs/notes-roundtrip.spec.ts` + `test_jobs_notes_field.py` |
| #13 | 退出登录可定位 | `tests/e2e/018-fix-product-defects/auth/logout-menu-semantics.spec.ts` |
| #14 | 无 future flag warning | `tests/e2e/018-fix-product-defects/shell/router-future-flags.spec.ts` |
