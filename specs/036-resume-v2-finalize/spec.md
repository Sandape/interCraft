# Feature Specification: Resume v2 Finalize — 全面弃用 v1 + 脏数据清理 + Playwright 成品验收

**Feature Branch**: `036-resume-v2-finalize`
**Created**: 2026-06-29 (修订)
**Status**: Draft
**Input**: User description: "针对简历中心 v2 的内容进行收尾需求整理，v2 应该完全替代原有 v1 的位置，并且对于用户来说，不应该感知到版本号。全面弃用 v1，旧的 v1 数据丢弃，新的 v2 数据也要删除，避免脏数据。验收标准：1、前端路由逻辑正确；2、页面显示效果好，UIUX 风格统一，没有出现 v2 标识的说明导致用户看到感觉困惑；3、功能完好，能够参照 `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`，借助 Playwright 操作 v2 简历编辑器在系统简历一份成品简历，注意，要使用 Playwright 去做，而不是直接调接口生成；4、reactive-resume 的源码在 `D:\Project\reactive-resume`，如果遇到简历编辑器相关的功能有问题，可以参考源码进行修复。"

---

## Background & Motivation

经过 032 渲染引擎 v2 重建 + 034 reactive-resume 内容编辑对齐，**v2 是产品决策**：新数据模型、新编辑器、新模板体系。但当前状态残留大量 v1 触点与脏数据：

**v1 残留**
1. 侧边栏双菜单：`/resume`（简历中心，v1 list）+ `/resume-v2`（v2 简历，v2 list）
2. Topbar 新建下拉拆 v1/v2："空白创建" → `/resume?new=true`（v1 新分支）+ "新建 v2 简历" → `/resume-v2/new`
3. 路由表五处分散：`/resume`、`/resume-v2`、`/resume-v2/new`、`/resume/v2/:id`、`/resume/:branchId`
4. `resume_branches` 表 + v1 Markdown 编辑器 + 关联 API 仍存在
5. 历史用户可能在 `resume_branches` 有 v1 数据（陈年脏数据）

**v2 脏数据**
1. 历史 dev/test 流程注入的 mock 简历（来自 032 验证 + 034 内容注入 + 各类 E2E fixture）
2. `resumes_v2` 表里非用户真实创建的"演示数据"

**用户期望（验收标准 4 条）**
1. 前端路由逻辑正确（老 URL 不破、单一入口清晰）
2. UIUX 风格统一，无 "v2" 标识（用户感知不到版本号）
3. 功能完好：Playwright 操作 v2 编辑器在系统简历一份成品简历（参照 `大模型应用开发简历v1.md`），**用 UI 实操，不是 API 注入**
4. 遇到问题可参考 `D:\Project\reactive-resume` 源码修复

本 spec = 全面弃用 v1 + 清空 v1/v2 脏数据 + 用 Playwright 实操验收 v2 编辑器端到端可用。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 侧边栏只有 1 个"简历中心"入口（P1）

已登录用户进入应用，侧边栏主导航只看到 1 个简历入口（`简历中心`，FileText 图标），无"v2 简历"独立项。点击进入统一列表页。Topbar 新建按钮也只剩 1 项"新建简历"。

**Why this priority**: 用户感知最强的简化点；不解决则"无版本号"承诺永远落空。P1 是 MVP 必做项。

**Independent Test**: 启动 dev server → 登录 → 截图侧边栏；断言只有 1 个简历相关菜单项；点击进入列表页。

**Acceptance Scenarios**:
1. **Given** 用户登录后进入 `/dashboard`，**When** 查看左侧主导航，**Then** 只出现 1 个"简历中心"菜单项（FileText 图标），无"v2 简历"独立项
2. **Given** 用户点击"简历中心"，**When** 路由跳转，**Then** 进入 `/resume` 列表页
3. **Given** 用户在 Topbar 看到新建按钮（"+"图标），**When** 点击，**Then** 下拉菜单只显示 1 项"新建简历"（无"空白创建"/"新建 v2 简历"拆分）
4. **Given** 用户在浏览器 DOM 全文搜索 "v2 简历"，**When** 检查，**Then** 用户可见的中文文案中无任何命中（菜单、按钮、空状态、toast）

---

### User Story 2 — 路由收口：所有 v2 旧路径 301 重定向到规范路径（P1）

历史 URL 必须可点击访问避免书签/分享链失效：
- `/resume-v2` → 重定向到 `/resume`
- `/resume-v2/new` → 重定向到 `/resume?new=true`（或新模板选择流程入口）
- `/resume/v2/:id` → 重定向到 `/resume/:id`

应用内任何指向 `/resume-v2*` 或 `/resume/v2/*` 的链接改为规范路径。`App.tsx` 中 `ResumeListV2` 与 `ResumeV2New` 的 `lazy import` 与路由条目全部删除。

**Why this priority**: URL 也得规范；否则分享链暴露"v2"。P1 是 US1 的工程实现路径。

**Independent Test**: 浏览器手动访问三种老 URL，断言分别跳到规范路径；`App.tsx` 中 `ResumeListV2`/`ResumeV2New` 无引用。

**Acceptance Scenarios**:
1. **Given** 用户访问 `/resume-v2`，**When** 回车，**Then** 浏览器跳转到 `/resume`
2. **Given** 用户访问 `/resume/v2/abc-123`，**When** 完成，**Then** 跳转到 `/resume/abc-123`
3. **Given** 仓库源码被 grep，**When** 搜索 `"/resume-v2"` 或 `"/resume/v2/"`，**Then** 仅出现在重定向规则与测试 fixture；业务组件无残留
4. **Given** `src/App.tsx` 路由表，**When** 审核，**Then** 不再有 `ResumeListV2` / `ResumeV2New` 的 `lazy import` 或路由条目

---

### User Story 3 — 数据清理：v1 数据 + v2 mock 数据全部丢弃（P1）

系统执行一次"全清"动作，把 `resume_branches`（v1 表）整表清空；把 `resumes_v2`（v2 表）整表清空（含所有 mock 测试数据、演示数据）。同时清理关联子表：`resume_statistics_v2`、`resume_analysis_v2`、相关 outbox 行。

清理完成后，登录任意账号进入 `/resume`，列表页显示空状态 CTA"创建你的第一份简历"。前端编辑器打开是空白。

**Why this priority**: 用户明确要求"全面弃用 v1 + 清空脏数据"；不清理，E2E 与 Playwright 验收无法保证从干净起点开始。P1 必做。

**Independent Test**: 跑清理脚本 → 查 DB 确认 `resume_branches` 行数 = 0、`resumes_v2` 行数 = 0、关联子表行数 = 0；前端 `/resume` 显示空状态。

**Acceptance Scenarios**:
1. **Given** 清理脚本执行前 DB 有 v1/v2 数据，**When** 跑清理脚本，**Then** `resume_branches` 行数 = 0、`resumes_v2` 行数 = 0、`resume_statistics_v2` 行数 = 0、`resume_analysis_v2` 行数 = 0
2. **Given** 清理完成，**When** 用户登录后访问 `/resume`，**Then** 列表页显示空状态 CTA"创建你的第一份简历"
3. **Given** 清理完成，**When** 用户直接访问 `/resume/<uuid>`，**Then** 渲染 v2 编辑器空白模板（无任何遗留数据）
4. **Given** 清理脚本执行，**When** 完成，**Then** 输出报告（清理行数 / 关联表影响 / 失败回滚说明）写入 `docs/evidence/036-data-cleanup-<timestamp>.log`
5. **Given** 清理涉及 outbox 行，**When** 完成，**Then** 与已删除 resume 关联的 outbox 行一并删除（避免悬挂外键）

---

### User Story 4 — 新建流程：Topbar "+" → 模板选择 → 编辑器（P2）

Topbar "+" → "新建简历" 弹出 Template Gallery modal（复用 032 Gallery），含 8-10 套模板 + "空白模板"选项。用户点选后系统创建 v2 简历（POST `/api/v1/v2/resumes`）并跳到 `/resume/:newId`。无"v1/v2"分流。

**Why this priority**: 让"新建简历"成为连贯体验（选模板 → 编辑），用户无需面对版本号。P2。

**Independent Test**: 点 Topbar "+" → 选 Pikachu → 编辑器加载并使用 Pikachu；返回重选 Onyx → 编辑器切换。

**Acceptance Scenarios**:
1. **Given** 用户在任意已登录页面点 Topbar "+"，**When** 完成，**Then** 下拉显示 1 项"新建简历"
2. **Given** 用户点"新建简历"，**When** 完成，**Then** 弹出 Template Gallery modal，含"空白模板" + 8-10 套模板
3. **Given** 用户选模板并确认，**When** 完成，**Then** 创建 v2 简历并跳到 `/resume/:newId`
4. **Given** 用户选"空白模板"，**When** 完成，**Then** 创建空白 v2 简历并跳到编辑器
5. **Given** 用户取消 modal，**When** 完成，**Then** 不创建任何简历
6. **Given** 网络异常，**When** 创建失败，**Then** toast 错误，不跳转

---

### User Story 5 — 简化列表页：只显示 v2 简历 + 空状态 CTA（P1）

`/resume` 列表页只渲染 v2 简历（按更新时间倒序）。无 v1 数据（已被 US3 清空）、无"历史简历"折叠组。空状态显示 CTA"创建你的第一份简历" + 2-3 个推荐模板缩略图。点击 CTA 触发 US4 流程。

**Why this priority**: 清理后唯一存在的列表内容是 v2；显示逻辑简化。P1。

**Independent Test**: 登录 → 访问 `/resume` → 主区显示 v2 列表（或空状态）；点 CTA 触发模板选择。

**Acceptance Scenarios**:
1. **Given** 用户有 N 份 v2 简历，**When** 访问 `/resume`，**Then** 主区按更新时间倒序显示 N 张卡片
2. **Given** 用户无简历（清理后），**When** 访问 `/resume`，**Then** 显示空状态 CTA + 2-3 个推荐模板缩略图
3. **Given** 列表卡片点击，**When** 完成，**Then** 跳到 `/resume/:id` 编辑器
4. **Given** 搜索框输入关键词，**When** 完成，**Then** 仅匹配 v2 简历（v1 已被清空，无需 fallback）

---

### User Story 6 — 体验补强：UIUX 统一 + 跨模块引用 grep 收口（P2）

补齐统一后的体感细节：
- 跨模块引用（模拟面试、能力画像、求职追踪等模块的"我的简历"入口）全部走 `/resume` 规范路径
- 卡片/编辑器 tab title / browser tab title 均不含 "v2"
- 编辑器右上角/底部操作按钮组文案不含 "v2" 字样

**Why this priority**: 让统一入口成为真正"易用"产品。P2。

**Independent Test**: 全仓 grep `/resume-v2`、`/resume/v2/`、"v2 简历" 等关键字符串，业务代码命中数 = 0。

**Acceptance Scenarios**:
1. **Given** 模拟面试详情页有"我的简历"链接，**When** 点击，**Then** 跳 `/resume`（规范路径）
2. **Given** 浏览器打开编辑器，**When** 查看 tab title，**Then** 仅显示简历名（如"李祖荫的简历"），不含 "v2"
3. **Given** 仓库源码被 grep，**When** 搜业务代码 `/resume-v2` 或 `/resume/v2/`，**Then** 命中数 = 0（仅重定向规则与测试 fixture 可保留）
4. **Given** 用户可见文案 grep "v2"，**When** 检查，**Then** 命中数 = 0（除 data-testid 与 console 调试日志）

---

### User Story 7 — Playwright 实操：在 v2 编辑器制作一份成品简历（P1，验收关卡）

执行 Playwright 脚本，端到端走一遍"创建 → 编辑 → 保存 → 导出 PDF"流程，输入内容**严格参照 `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`**（李祖荫 - 大模型应用开发工程师），包括：
- Basics：姓名 / 邮箱 / 电话 / 地址 / GitHub / 头像（可选）
- Summary（优势亮点 6 条）
- Profiles（GitHub 等）
- Experience（浩鲸云 2024.04-至今 大模型应用开发工程师）
- Projects（企业级智能体平台，含 4 个技术工作段落）
- Skills（分组：大模型 / 后端 / 数据 / 工程）

**关键约束**：**全程通过 Playwright 操作 UI**（点击 / 输入 / 表单 / 按钮），**禁止**用 API（fetch/curl/Postman/前端 store 直接赋值）注入数据。验证 v2 编辑器的真实端到端可用性。

**Why this priority**: 这是用户验收关卡。"功能完好"的可信证据就是 UI 实操产出 PDF。P1。

**Independent Test**: 跑 Playwright 脚本 → 截图中段证据 → 最终导出 PDF 与参考简历字段一致。

**Acceptance Scenarios**:
1. **Given** Playwright 脚本启动，**When** 完成，**Then** 自动登录 + 访问 `/resume` + 截图空状态
2. **Given** 脚本点 Topbar"+" → 选模板，**When** 完成，**Then** 截图模板选择 modal
3. **Given** 脚本在编辑器各 section（Basics / Summary / Profiles / Experience / Projects / Skills）依次填字段，**When** 完成每个 section，**Then** 截图当前 section 编辑状态
4. **Given** 字段填写全部完成，**When** 触发导出 PDF，**Then** 截图下载按钮 + 验证 PDF 文件存在且可读
5. **Given** 成品 PDF 内容，**When** 与参考 `大模型应用开发简历v1.md` 字段对比，**Then** 关键字段（姓名/邮箱/学校/公司/项目名/技能分类）一致（差异容忍：模板渲染样式 / Markdown 富文本格式）
6. **Given** Playwright 脚本运行结束，**When** 完成，**Then** 报告写入 `docs/evidence/036-playwright-resume-<timestamp>/`，含中段截图 + 最终 PDF + 字段对比报告
7. **Given** 脚本遇错（如某 section 对话框字段找不到），**When** 失败，**Then** 主 Agent 参考 `D:\Project\reactive-resume` 源码修复 v2 对应编辑器组件，重跑 Playwright 通过

---

### Edge Cases

- **数据清理脚本回滚**：执行前自动备份 `resume_branches`/`resumes_v2` 关键表到 `docs/evidence/036-data-cleanup-<timestamp>/db-backup.sql`（仅本机 dev 环境；prod 由 DBA 决定）
- **清理后 outbox 悬挂外键**：用 `LEFT JOIN ... WHERE resumes_v2.id IS NULL` 删除关联行
- **e2e fixture 依赖 v1 数据**：清理前识别 → 改为 self-contained fixture（不依赖 v1 真实数据）
- **redirect 循环**：所有重定向一律 `replace: true`，避免历史栈污染
- **用户在老 URL 刷新**：`replace: true` 保证不会因浏览器刷新触发 redirect loop
- **公开分享链接 `/r/:u/:slug`**：清理后所有 share 失效，访问者看到 404（沿用既有 404 行为）
- **编辑器 dialog 字段缺失**：Playwright 找不到 selector 时，主 Agent 参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 对应组件（如 experience.tsx）补全 v2 对话框
- **模板选择 modal 在移动端折叠**：复用 032 移动端折叠逻辑（< 640px 单列）
- **Playwright 浏览器路径**：使用本机已装 chromium（沿用 `playwright.config.ts` 默认 webServer 配置）
- **清理脚本并发安全**：使用事务包裹 + SERIALIZABLE 隔离级别，避免与其他 dev 操作冲突
- **dev server 启动顺序**：backend (uvicorn) → arq worker → frontend (npm run dev)；Playwright 等 frontend 起来后再跑

---

## Requirements *(mandatory)*

### Functional Requirements

#### 入口与菜单

- **FR-001**: System MUST 在 `src/components/layout/Sidebar.tsx` 的 `primaryNav` 中只保留 1 个简历菜单项（`简历中心` + FileText 图标 + 路由 `/resume`）
- **FR-002**: System MUST 不再向用户暴露"v2 简历"字样（菜单项、按钮、占位、toast、modal title、browser tab title 均不允许出现"v2"前缀）
- **FR-003**: System MUST 在 `src/components/layout/Topbar.tsx` 的"+" 下拉中只保留 1 项"新建简历"（删除"空白创建"与"新建 v2 简历"两个独立项）
- **FR-004**: System MUST 让 Topbar"+" 跳到新建流程（详见 FR-013~FR-018）

#### 路由

- **FR-005**: System MUST 在 `src/App.tsx` 中：
  - 移除 `ResumeListV2` 与 `ResumeV2New` 的 `lazy import` 与路由条目
  - 移除 `path="/resume/v2/:id"` 路由条目
  - 移除 `path="/resume-v2"` 与 `path="/resume-v2/new"` 路由条目
  - 替换为 `<Route path="/resume-v2" element={<Navigate to="/resume" replace />} />` 等重定向条目
  - 删除 `path="/resume/:branchId"` 路由条目（v1 已弃用，不再挂 v1 editor 路由）
- **FR-006**: System MUST 把 v2 编辑器挂到规范路由 `/resume/:id`（无 v1 fallback）
- **FR-007**: System MUST 在 `/resume/:id` 路由组件中：v2 命中则渲染 v2 编辑器；不命中渲染 404 占位
- **FR-008**: System MUST 用 `Navigate replace` 实现重定向，避免历史栈污染

#### 数据清理

- **FR-009**: System MUST 提供数据清理脚本（`backend/scripts/cleanup_resume_data.py` 或 alembic 数据迁移），可幂等执行
- **FR-010**: 清理脚本 MUST 在事务中执行：清空 `resume_branches`、清空 `resumes_v2`、级联清理 `resume_statistics_v2` 与 `resume_analysis_v2`、清理关联 outbox 行
- **FR-011**: 清理脚本 MUST 执行前自动 dump 关键表到 `docs/evidence/036-data-cleanup-<timestamp>/db-backup.sql`（dev 环境）
- **FR-012**: 清理脚本 MUST 输出报告（清理行数 / 关联表影响 / 失败回滚说明）到 `docs/evidence/036-data-cleanup-<timestamp>/cleanup.log`

#### 新建流程

- **FR-013**: System MUST 在用户点击 Topbar"+" → "新建简历"后弹出 Template Gallery modal
- **FR-014**: Template Gallery MUST 包含"空白模板" + 8-10 套精选模板
- **FR-015**: 用户点选模板后 System MUST 调用 `POST /api/v1/v2/resumes` 创建简历，body 含 `{ template, source: "template-picker" }`，成功后跳到 `/resume/:newId`
- **FR-016**: 创建失败 MUST toast 错误并停留在 modal 中
- **FR-017**: 用户取消 modal MUST 不创建任何简历
- **FR-018**: System MUST 让"基于岗位创建"（Topbar"+" 二级菜单）继续走现有路径，触发同样的模板选择流程

#### 简化列表

- **FR-019**: `src/pages/ResumeList.tsx` MUST 是唯一的列表页路由 `/resume`
- **FR-020**: 列表主区 MUST 只显示 v2 简历卡片（更新时间倒序）；无"历史简历"折叠组
- **FR-021**: 当 v2 简历为 0 时 MUST 显示空状态 CTA"创建你的第一份简历" + 2-3 个推荐模板缩略图
- **FR-022**: 搜索框 MUST 仅匹配 v2 简历

#### 跨模块引用

- **FR-023**: System MUST 把所有跨模块引用（面试详情/能力画像/求职追踪/Settings 等）从 `/resume-v2*`、`/resume/v2/*` 改为 `/resume` 或 `/resume/:id`
- **FR-024**: System MUST 在 e2e 测试中保留老路径 fixture 兼容（重定向后行为不变），同时增加 canonical 路径断言

#### 工程清理

- **FR-025**: System MUST 在 `src/pages/` 下保留 `ResumeList.tsx` + `ResumeEditorV2.tsx`，**删除** `ResumeListV2.tsx` 与 `ResumeV2New.tsx`
- **FR-026**: System MUST 移除 `ResumeEditor.tsx`（v1 编辑器入口页面）与 `Sidebar.tsx` 中 `Sparkles` 图标的引入（若仅服务于已移除菜单项）
- **FR-027**: System MUST 移除后端 `backend/app/modules/resumes/` 下 v1 路由（如 `resume_branches` CRUD endpoints）
- **FR-028**: System MUST 删除 `resume_branches` 表的 alembic 迁移不变量（保留表结构但不再有业务代码写入）
- **FR-029**: System MUST 不动后端 v2 API（`/api/v1/v2/resumes*` 保持现状）
- **FR-030**: System MUST 不动后端 v1 数据表结构（仅清空数据；保留 schema 便于后续若需回滚）

#### Playwright 验收

- **FR-031**: System MUST 提供 Playwright 验收脚本 `tests/e2e/036-resume-v2-finalize.spec.ts`，执行完整端到端流程
- **FR-032**: 脚本 MUST：登录 → 访问 `/resume` → 点 Topbar"+" → 选模板 → 进入编辑器 → 在各 section 填字段（数据来自 `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`） → 保存 → 导出 PDF
- **FR-033**: 脚本 MUST **不使用 API 注入数据**（仅用 Playwright UI 操作：click / fill / type / submit）
- **FR-034**: 脚本 MUST 输出中段截图到 `docs/evidence/036-playwright-resume-<timestamp>/` + 最终 PDF + 字段对比报告
- **FR-035**: 脚本失败时主 Agent MUST 参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 源码修复 v2 对应编辑器组件，重跑 Playwright 至通过

### Key Entities

- **简历主表（v2）** — `resumes_v2` (id, user_id, name, slug, data jsonb, metadata jsonb, is_public, is_locked, password_hash, version, created_at, updated_at) — 清理后行数 = 0；Playwright 实操重建
- **v1 分支表** — `resume_branches` — 清理后行数 = 0；保留 schema 不动
- **路由表（前端）** — 单一 list `/resume` + 单一 editor `/resume/:id`；老 `/resume-v2*` / `/resume/v2/:id` 走 `Navigate replace` 重定向
- **清理产物** — `docs/evidence/036-data-cleanup-<timestamp>/{db-backup.sql, cleanup.log}`
- **Playwright 产物** — `docs/evidence/036-playwright-resume-<timestamp>/{step-*.png, final-resume.pdf, field-comparison.md}`

---

## Success Criteria *(mandatory)*

### 可衡量的成果

- **SC-001**: 侧边栏主导航对简历相关菜单项的 grep 结果 = 1
- **SC-002**: 清理脚本执行后 `resume_branches` 行数 = 0、`resumes_v2` 行数 = 0、`resume_statistics_v2` 行数 = 0、`resume_analysis_v2` 行数 = 0（用 `mcp__postgres__query` 实查落库）
- **SC-003**: 用户访问 `/resume-v2`、`/resume-v2/new`、`/resume/v2/:id` 三种 URL 必须分别跳到 `/resume`、`/resume?new=true`、`/resume/:id`（Playwright 断言 3/3 通过）
- **SC-004**: 列表页 `/resume` 主区只显示 v2 卡片（清理后空状态）；空状态 CTA + 推荐模板缩略图渲染正确
- **SC-005**: 用户可见文案中 "v2" 字样的 grep 命中数 = 0（除 `data-testid` 与 console 调试日志外的所有 i18n 文案、菜单、按钮、modal title、toast、空状态文案）
- **SC-006**: 跨模块引用 grep 业务代码 `/resume-v2` / `/resume/v2/` 命中数 = 0（仅重定向规则与测试 fixture 可保留）
- **SC-007**: `src/pages/ResumeListV2.tsx`、`ResumeV2New.tsx`、`ResumeEditor.tsx` 在 dev server 启动后无代码引用（grep 0 命中）
- **SC-008**: 后端测试 `backend/tests/**` 通过率 = 100%（无回归）
- **SC-009**: 前端 `npm run typecheck` clean；前端 `npm run test` 全绿
- **SC-010**: **Playwright 验收脚本 `tests/e2e/036-resume-v2-finalize.spec.ts` 全程通过**：登录 → 选模板 → 填字段（参照 `大模型应用开发简历v1.md`） → 保存 → 导出 PDF；最终 PDF 与参考简历字段一致（关键字段：姓名/邮箱/学校/公司/项目名/技能分类）
- **SC-011**: Playwright 脚本生成中段截图 ≥ 6 张（空状态 / 模板选择 / Basics / Summary / Experience / Projects / Skills / Skills / 导出）；最终 PDF 大小 > 0 且可读
- **SC-012**: 整个验证流程（点 UI 操作）总时长 ≤ 10 分钟（排除网络等待）

### 验收检查

- [ ] `Sidebar.tsx` 截图确认只有 1 个简历菜单项
- [ ] Topbar"+" 下拉截图确认只有 1 项"新建简历"
- [ ] `/resume-v2` `/resume/v2/:id` 重定向 Playwright 自动化通过
- [ ] 清理脚本执行后 DB 4 张关键表行数 = 0（mcp__postgres__query 实查）
- [ ] 列表页空状态 + 模板缩略图渲染正确
- [ ] 跨模块引用 grep 检查 = 0 命中
- [ ] `ResumeListV2.tsx`、`ResumeV2New.tsx`、`ResumeEditor.tsx` 已删除（git diff 显示）
- [ ] 后端测试 100% 通过；前端 typecheck 干净；前端 vitest 全绿
- [ ] **Playwright 验收脚本 100% 通过**，最终 PDF 与参考简历字段一致（关键字段对比报告写入 evidence 目录）
- [ ] Playwright 中段截图 ≥ 6 张 + 最终 PDF 写入 evidence 目录

---

## Assumptions

- 032 已经 ship（v2 数据模型 + 编辑器 + 8-10 套模板 + PDF 渲染）；034 已经 ship（10 类 item dialog + basics + 8 settings 面板真实现）
- Template Gallery 组件已存在（032 US2 FR-057-059）；本 spec 复用，不重新实现
- Playwright 在本机已可用（沿用 `playwright.config.ts` 默认 webServer 配置）
- `playwright.config.ts` 的 webServer 当前被注释（per 032 dev_round_1_result 备注）；本 spec 启用并配置 backend+frontend 启动顺序
- 公开分享 URL `/r/:username/:slug` 清理后全部失效，沿用既有 404 行为
- 用户接受"清理即丢失历史"的过渡（用户明确指示"旧的 v1 数据丢弃，新的 v2 数据也要删除"）；清理产物仅本地 dev 备份，不承诺恢复
- 桌面端优先（沿用现有 1280px+ 设计断点）；移动端支持沿用 Topbar 当前折叠逻辑

---

## Out of Scope

- v1 → v2 数据迁移工具（用户明确指示直接丢弃 v1 数据）
- v2 编辑器功能补强（内容编辑能力在 034 已完成）
- 模板数量扩展（032 8-10 套已 ship）
- 公开分享页改造（032 US11 已 ship）
- AI 简历优化（027 已 ship）
- AI 简历分析（032 US14 已 ship）
- 后端 v2 API 改动（`/api/v1/v2/resumes*` 保持现状）
- 后端 v1 表 schema 删除（仅清空数据，保留 schema）
- 多语言 i18n 翻译资源

---

## Technical Risks & Mitigations

| 风险 | 影响 | 缓解 |
|---|---|---|
| 清理脚本误删 prod 数据 | 不可逆数据丢失 | 仅在 dev 环境跑；执行前必 dump 备份到 evidence；用户接受清理过渡 |
| 清理脚本悬挂外键 | DB 报错 | 用 LEFT JOIN ... IS NULL 模式清理 outbox；事务包裹 |
| Playwright 找不到 v2 编辑器 selector | 验收失败 | 主 Agent 参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 源码修复；fallback 用 `data-testid` 定位 |
| dev server 启动失败 | Playwright 无法运行 | 检查 backend/frontend 端口 + log；arq worker 单独启动；后端先 health-check 通 |
| redirect 循环 | 用户卡死 | FR-008 `replace: true`；编辑器组件内不再写 `Navigate('/resume-v2*')` |
| 删除 `ResumeListV2.tsx` 导致 import 失败 | 编译错 | FR-025 + 实施步骤要求"先改 import 再删文件" |
| 跨模块引用残留 `/resume-v2` | 体验割裂 | FR-023/FR-024 + SC-006 grep 收口 |
| e2e fixture 写死老路径 | 测试失败 | US2 AC4 + SC-003 保留兼容断言 |
| Playwright 操作超时（quota / 网络） | 验收中断 | 脚本分段跑（每段保存截图）；失败可恢复 |
| 编辑器 dialog 字段命名与 reactive-resume 不一致 | Playwright selector 失效 | 主 Agent 实施 US7 时对照 reactive-resume 源码确认 v2 对话框字段命名规范 |

---

## Notes

- 本 spec 是 036 的"收尾验收"阶段，结合 032/034 ship 内容做端到端 UX 收口与 Playwright 实操验收
- 实施顺序建议：
  1. **Phase A**：数据清理（US3 / FR-009~FR-012）+ 路由/菜单/Topbar/页面/组件下线（US1 / US2 / FR-001~FR-008 / FR-023~FR-030）
  2. **Phase B**：列表页简化 + 新建流程（US4 / US5 / FR-013~FR-022）+ 体验补强（US6）
  3. **Phase C**：Playwright 验收（US7 / FR-031~FR-035 / SC-010~SC-012）
- US7 是关键验收关卡：必须用 Playwright UI 实操（不是 API 注入），最终产出成品 PDF 与参考简历字段对比报告
- 实施遇到问题可参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 对应组件（experience.tsx、education.tsx、project.tsx、skill.tsx 等）
- e2e 关键测试场景：清理后空状态 → 模板选择 → 各 section 编辑 → 保存 → 导出 PDF → 字段对比