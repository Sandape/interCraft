# Implementation Plan: 036 Resume v2 Finalize — 全面弃用 v1 + 脏数据清理 + Playwright 成品验收

**Branch**: `036-resume-v2-finalize` | **Date**: 2026-06-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/036-resume-v2-finalize/spec.md`

## Summary

036 = 036-resume-v2-finalize 的"收尾验收"阶段：
- **全面弃用 v1**：侧边栏 / Topbar / 路由表 / 页面 / 后端 CRUD 全部下线 v1 触点；`resume_branches` 表数据清空（保留 schema）。
- **脏数据清理**：`resumes_v2` / `resume_statistics_v2` / `resume_analysis_v2` / 关联 outbox 整表清空（dev 环境）。
- **Playwright 验收**：端到端 UI 实操在 v2 编辑器制作一份成品简历（参照 `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`），**禁止 API 注入**；每个细分功能点都要实测，产出「未完成功能清单」+「已完成验收功能清单」两份证据。

技术路径：复用 032 的 v2 编辑器（`src/modules/resume/v2/editor/BuilderShell.tsx`）+ 模板 Gallery（032 US2 FR-057-059）+ 034 的 10 类 item dialog + basics 表单；问题可参考 `D:\Project\reactive-resume` 源码修复。

## Technical Context

**Language/Version**:
- Frontend: TypeScript 5.x (strict) + React 18 + Vite + TailwindCSS
- Backend: Python 3.11 + FastAPI + SQLAlchemy 2.0 + Alembic + Redis/ARQ

**Primary Dependencies**:
- Frontend: react-router-dom 6.x, TanStack Query 5.x, Zustand 4.x, lucide-react, react-resizable-panels, @dnd-kit/core + @dnd-kit/sortable, Tiptap (or react-quill fallback per 034), Vitest, Playwright
- Backend: FastAPI 0.110+, SQLAlchemy 2.0, alembic, arq, pytest
- DB: PostgreSQL 16 (RLS enforced)

**Storage**:
- PostgreSQL — `resumes_v2` / `resume_branches` (待清空) / `resume_statistics_v2` / `resume_analysis_v2`
- Redis — session + cache
- Local FS — `docs/evidence/036-*` (cleanup log + Playwright artifacts)

**Testing**:
- Backend: `cd backend && uv run pytest -q` (单元 + 集成 + 契约)
- Frontend: `npm run test` (Vitest)
- E2E: `npm run e2e` (Playwright, root `playwright.config.ts` 指向 `tests/e2e/`)
- Type check: `npm run typecheck`

**Target Platform**:
- Local dev (Windows 11 + bash + uv + npm per AGENTS.md)
- Node 20+ for frontend tooling

**Project Type**: web application (frontend SPA + backend API)

**Performance Goals**:
- 模板切换 < 1 秒（沿用 032 SC-002）
- PDF 渲染 < 60 秒（沿用 032 SC-011）
- Playwright 验收脚本端到端 ≤ 10 分钟（SC-012）

**Constraints**:
- 仅 dev 环境数据清理（用户明确指示）
- Playwright 全程 UI 操作（禁止 API 注入）
- 后端 v1 API 路由下线但表结构保留
- reactive-resume 源码路径：`D:\Project\reactive-resume`（参考但不入仓）

**Scale/Scope**:
- 单用户演示场景（李祖荫一份简历）
- 7 US + 35 FR + 12 SC
- 测试矩阵：≥ 6 张中段截图 + 1 份最终 PDF + 1 份字段对比 + 2 份功能清单

## Constitution Check

*GATE: 必须通过 Phase 0 研究；Phase 1 设计后复检。*

### Constitution I — Library-First
- ✅ 复用 `src/modules/resume/v2/` 自包含库（032/034 ship）
- ✅ 复用 032 Template Gallery 组件
- ✅ 复用 034 dialog components（experience/education/project/skill 等）
- ✅ 清理脚本 `backend/scripts/cleanup_resume_data.py` 作为独立可执行 CLI（原则 II）

### Constitution II — CLI Interface
- ✅ 清理脚本 MUST 暴露 CLI（`uv run python -m app.scripts.cleanup_resume_data --dry-run | --execute`）
- ✅ 文本 I/O 协议：参数 + stdin → stdout/stderr
- ✅ 默认人类可读；`--json` 模式可选
- ✅ 退出码：0 = 成功 / 1 = 操作失败 / 2 = 参数错误 / 3 = 安全检查失败
- ✅ Playwright 脚本本身是可重放的 CLI：`npx playwright test tests/e2e/036-resume-v2-finalize.spec.ts`

### Constitution III — Test-First (NON-NEGOTIABLE)
- ⚠️ 实施 Phase A（数据清理）需要先写清理脚本的测试（dry-run 模式 + 行数断言）
- ✅ 实施 Phase B（菜单/路由清理）需要先写 frontend unit test 验证重定向 + 菜单结构
- ✅ 实施 Phase C（Playwright 验收）spec 本身就是测试
- ✅ 实施前必须经过代码评审 / 主 Agent 静态验证

### Constitution IV — Integration & Synchronization Testing
- ✅ Playwright e2e 真实跑完整链路（不能 mock happy path）
- ✅ 后端 pytest 100% 通过（无回归）
- ✅ 清理脚本输出行数可通过 `mcp__postgres__query` 实查落库（per memory `feedback_postgres_mcp_validation`）

### Constitution V — Observability
- ✅ 清理脚本输出结构化日志到 `docs/evidence/036-data-cleanup-<ts>/cleanup.log`
- ✅ Playwright 输出 `evidence` 目录（截图 + PDF + 字段对比 + 功能清单）
- ✅ 失败时 stack trace + 上下文（非裸 stack）

### Technology & Stack Constraints
- ✅ TypeScript strict + React 18 + Vite + Tailwind + react-router-dom
- ✅ 后端 HTTP/OpenAPI + SQLAlchemy 2.0 + alembic
- ✅ AI: 不在本 spec 范围（复用 032/034 已 ship 的 DeepSeek V4 Pro 配置）
- ✅ RLS 在 `resumes_v2` / `resume_branches` 已强制启用

### 违规 / 取舍
无。036 是收尾整合性质，沿用既有栈。

## Project Structure

### Documentation (this feature)

```text
specs/036-resume-v2-finalize/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cleanup-script-contract.md
│   ├── playwright-spec-contract.md
│   └── route-redirect-contract.md
├── checklists/          # Phase 1 output (already from /speckit-specify)
│   └── requirements.md
├── spec.md              # /speckit-specify output
└── tasks.md             # /speckit-tasks output (next phase)
```

### Source Code (repository root)

```text
D:/Project/eGGG/
├── backend/
│   ├── app/
│   │   ├── modules/
│   │   │   ├── resumes/             # v1 routes — REMOVE endpoints (keep schema)
│   │   │   └── resumes_v2/          # v2 routes — KEEP
│   │   └── scripts/
│   │       └── cleanup_resume_data.py   # NEW (Phase A)
│   └── alembic/
│       └── versions/
│           └── 036_cleanup_resume_data.py   # NEW (Phase A; idempotent)
├── src/
│   ├── pages/
│   │   ├── ResumeList.tsx           # EDIT (remove v1 logic)
│   │   ├── ResumeEditorV2.tsx       # KEEP
│   │   ├── ResumeEditor.tsx         # DELETE (v1 entry)
│   │   ├── ResumeListV2.tsx         # DELETE (v2 standalone list)
│   │   └── ResumeV2New.tsx          # DELETE (v2 standalone new)
│   ├── components/
│   │   └── layout/
│   │       ├── Sidebar.tsx          # EDIT (remove v2 entry)
│   │       └── Topbar.tsx           # EDIT (remove v1/v2 split)
│   ├── App.tsx                      # EDIT (remove v2 routes, add Navigate redirects)
│   └── modules/
│       └── resume/
│           └── v2/                  # KEEP (032/034 ship)
├── tests/
│   └── e2e/
│       └── 036-resume-v2-finalize.spec.ts   # NEW (Phase C)
└── docs/
    └── evidence/
        └── 036-*                   # NEW (cleanup log + Playwright artifacts)
```

**Structure Decision**: Option 2 (Web application) — 沿用既有 frontend + backend + tests 双层结构，新增 `backend/scripts/` 与 `docs/evidence/036-*` 子树。

## Implementation Phases

### Phase A — 数据清理 + v1 触点下线（前置 P1）
1. 写 `backend/scripts/cleanup_resume_data.py`（CLI：dry-run + execute；输出 evidence）
2. 写 `backend/tests/scripts/test_cleanup_resume_data.py`（dry-run 模式 + 行数断言）
3. 写 alembic 036 migration（幂等）
4. 跑清理脚本（dev 环境）→ 验证 `mcp__postgres__query` 行数 = 0
5. 修改 `src/App.tsx`：删除 v2 路由 + 添加 Navigate replace 重定向
6. 修改 `src/components/layout/Sidebar.tsx`：删除"v2 简历"菜单项
7. 修改 `src/components/layout/Topbar.tsx`：合并"+ 下拉"为单"新建简历"
8. 删除 `src/pages/ResumeListV2.tsx` + `ResumeV2New.tsx` + `ResumeEditor.tsx`（先 grep 引用）
9. 修复跨模块引用（面试/能力画像/求职追踪 → `/resume` 或 `/resume/:id`）
10. 后端下线 v1 API endpoints（保留 `resume_branches` 表 schema）
11. 跑后端 pytest 100% + 前端 typecheck + 前端 vitest 全绿

### Phase B — v2 编辑器端到端走通（前置 P1）
12. 简化 `src/pages/ResumeList.tsx`：删除 v1 混用逻辑 + v1 historical folder
13. 验证 Template Gallery modal（032 FR-057-059）触发逻辑
14. 验证 Topbar"+" → 模板选择 → 创建 → 跳 `/resume/:newId` 流程
15. 验证编辑器各 section 渲染：Basics / Summary / Profiles / Experience / Education / Projects / Skills / Languages / Interests / Awards / Certifications / Publications / Volunteer / References / Custom
16. 验证 Settings 12 子面板：Template / Layout / Typography / Design / Styles / Page / Notes / Sharing / Statistics / Analysis / Export / Information
17. 验证 8 个 dock 按钮：Zoom in/out / Center / Toggle stacking / Open AI agent / Copy URL / Download JSON / Download PDF
18. 验证 Undo/Redo（Ctrl+Z / Ctrl+Shift+Z）
19. 验证 500ms auto-save
20. 验证 PDF 导出（文件名 `{slug}-{YYYY-MM-DD}.pdf`）
21. 验证公开分享（`/r/:u/:slug`）与统计

### Phase C — Playwright 验收 + 两份清单（关键关卡 P1）
22. 写 `tests/e2e/036-resume-v2-finalize.spec.ts`：
    - 登录 → 访问 `/resume` → 截图空状态
    - 点 Topbar"+" → 选 Pikachu 模板 → 截图模板 modal
    - 进入编辑器 → 在 Basics 填字段（姓名 / 邮箱 / 电话 / GitHub / 学校）→ 截图
    - 填 Summary（6 条亮点）→ 截图
    - 填 Profiles（GitHub 等）→ 截图
    - 填 Experience（浩鲸云 2024.04-至今）→ 截图
    - 填 Projects（企业级智能体平台，含 4 个技术工作段落）→ 截图
    - 填 Skills（4 分组）→ 截图
    - 保存 → 触发 500ms auto-save 验证
    - 点 Download PDF → 截图 + 验证 PDF 文件存在
23. **逐个细分功能实测**（**用户补充**：每个功能点都必须 Playwright 实测）：
    - 编辑器顶部 Header / Breadcrumb / Sidebar toggle
    - 左侧 Section 列表展开/折叠（13 个内置 + Picture + Basics + Summary）
    - 右侧 Settings 12 个子面板展开/折叠 + 关键控件操作
    - Section item dialog（10 类）创建/编辑/删除/DnD 排序
    - Tiptap 富文本工具栏（15+ 功能）
    - dock 8 个按钮
    - 模板 Gallery 切换
    - 公开分享开关
    - AI 分析按钮（如可用）
    - PDF 导出 + JSON 导出
    - Undo/Redo
    - 移动端 sidebar 折叠
24. 输出到 `docs/evidence/036-playwright-resume-<ts>/`：
    - `step-*.png` 中段截图 ≥ 10 张
    - `final-resume.pdf` 最终 PDF
    - `field-comparison.md` 字段对比（与 `大模型应用开发简历v1.md` 比对）
    - **`incomplete-features.md` 未完成功能清单**
    - **`accepted-features.md` 已完成验收功能清单**

## Complexity Tracking

无违规。所有改动沿用既有栈（React 18 / FastAPI / Playwright / PostgreSQL / alembic）。无新增抽象或新依赖。

---

## User Supplement (2026-06-30)

> "简历编辑器的每个细分功能点，都需要通过 Playwright 进行实际操作测试，最终需要整理一份未完成功能清单，和一份已完成验收功能清单"

**实施含义**：
- Phase C 的 Playwright 验收 MUST 覆盖**每个细分功能点**（不只走"创建 → 编辑 → 保存 → 导出"主流程）
- 验收脚本 MUST 产生两份清单：
  - **`incomplete-features.md`** — 未完成功能清单（截图 + 现象 + 失败 selector + 修复建议）
  - **`accepted-features.md`** — 已完成验收功能清单（每个功能点的 Playwright 操作步骤 + 截图证据 + 通过断言）
- 若 Playwright 找不到某功能点的 selector（参考 034 已 ship 的 dialog），主 Agent MUST 参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 修复 v2 对应组件
- 主 Agent 持续把"发现的 v2 编辑器问题"灌入 `incomplete-features.md`，把"通过的细分功能点"灌入 `accepted-features.md`
- 直到两份清单可对外发布（本机 dev 演示通过），036 才算完成

---

## References

- 036 spec: `specs/036-resume-v2-finalize/spec.md`
- 036 checklist: `specs/036-resume-v2-finalize/checklists/requirements.md`
- 参考简历: `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`
- reactive-resume 源码: `D:\Project\reactive-resume`（apps/artboard/src/dialogs/resume/sections/ 为重点参考）
- 032 v2 MVP spec: `specs/032-resume-renderer-v2/spec.md`
- 034 reactive-resume parity spec: `specs/034-v2-reactive-resume-parity/spec.md`
- Constitution: `.specify/memory/constitution.md`