# Implementation Plan: 018-fix-product-defects (v1 Quality Batch)

**Branch**: `018-fix-product-defects` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/018-fix-product-defects/spec.md` (14 个 v1 质量缺陷批次)

**Note**: 本 plan 由 `/speckit-plan` 生成。所有 NEEDS CLARIFICATION 已在 spec 阶段通过 3 个澄清问答解决（spec § Clarifications）。

## Summary

修复 InterCraft v1 阶段从用户 / E2E 复现出来的 14 个生产质量缺陷，覆盖 5 个产品域：注册深链（#1）、Dashboard 数据可信度（#2）、简历编辑器 / 导出（#3 #4 #5）、面试量纲与同步（#6 #7 #8 #9）、错题与求职（#10 #11 #12）、生产级控制台与无障碍（#13 #14）。

技术形态：**13 个为前端/集成层修复，1 个（缺陷 #9 能力画像同步）需后端补 `interviews → ability_profile` 回调**。**零 schema 变更**（后端 `JobApplication.notes_md` 字段已落库，前端只改字段映射）。**零新依赖**，所有修复在已有契约内完成。

## Technical Context

**Language/Version**:
- 前端：TypeScript 5.x（strict）+ React 18.3 + Vite 5
- 后端：Python 3.11+ / FastAPI 0.115 / SQLAlchemy 2.0 async

**Primary Dependencies**:
- 前端：`react-router-dom@6.27.0`（无 future flag），`@tanstack/react-query@5.59`，`zustand@4.5`，`fast-json-patch@3.1`，`fractional-indexing@3.2`，`@monaco-editor/react@4.7`
- 后端：`fastapi-users@14`，`langgraph@0.2` + `langgraph-checkpoint-postgres@1.0`，`arq@0.25`，`playwright@1.48`（PDF 渲染），`structlog@24.1`

**Storage**:
- PostgreSQL 15 + RLS（用户数据强隔离）
- Redis 7（arq 队列 / 会话）
- 本地 Dexie（前端 outbox 同步）

**Testing**:
- 前端：Vitest 单元 / 组件 + Playwright 1.60.0 E2E（`@playwright/test` 已固定到 1.60.0）
- 后端：pytest + pytest-asyncio + httpx AsyncClient

**Target Platform**:
- 开发：Windows 11 + bash + uv（Python）+ npm（前端，非 pnpm）；本地 Redis 6379 + 在线 Postgres
- 生产：Linux（部署目标，与开发对齐）

**Project Type**:
- 单仓 monorepo：
  - 前端：`src/`（页面 / 组件 / hooks / repositories / stores / api） + `e2e/` + `tests/`
  - 后端：`backend/app/`（modules / agents / api / core / domain） + `backend/tests/` + `backend/migrations/`

**Performance Goals**:
- 简历 PDF 导出 p95 < 8s（受 weasyprint 渲染约束，非热路径）
- Dashboard 首屏 TTI < 2s（已建缓存）
- 错题 Coach 启动首响 < 1s

**Constraints**:
- 不得新增后端依赖（lockfile 冻结；新增需独立 issue）
- 不得新增 schema migration（除非 review 发现实际缺字段）
- 不得修改 Constitution 已有原则（Library-First / CLI / Test-First / Integration / Observability）
- 跨 RLS 边界的"当前用户"判断 MUST 走后端会话

**Scale/Scope**:
- 单用户产品，单租户；14 个缺陷 + 8 用户故事 + 22 FR + 11 SC
- 修复范围：~14 个文件改、~6 个新测试文件、~3 个新 fixtures

## Constitution Check

*GATE: 必须通过 Phase 0 调研；Phase 1 设计后复检。*

### I. Library-First
- ✅ 每个修复视为"前端/后端已有库内的局部改动"，不引入新库
- ✅ 简历 PDF 渲染复用 `backend/app/src/services/pdf_renderer/`，不重写
- ✅ 错题 Coach 复用 `backend/app/agents/nodes/error_coach/`，不重写
- ✅ 简历锁复用 `src/lib/lock/useLock`，不重写

### II. CLI Interface
- ✅ 修复不涉及 CLI surface（产品功能修复）
- ✅ 但约束：若实施中发现需要调试/手动触发，可加 `intercraft debug fix-product-defects` 子命令（out of scope for v1）

### III. Test-First (NON-NEGOTIABLE)
- ✅ 每个修复 MUST 配套测试（单元 / 组件 / E2E 三层按需选最低合理层级）
- ✅ 任务拆分时把测试任务放在实现前（参考 Phase 1 / 4 / 5 的 T 编号惯例）
- ✅ E2E 必跑：14 个缺陷对应的 8 个用户故事各 ≥ 1 个 E2E

### IV. Integration & Synchronization Testing
- ✅ 缺陷 #3（简历只读）涉及前端 ↔ 后端 lock 协议 → 需要契约测试
- ✅ 缺陷 #5（PDF 404）涉及前端 ↔ 后端 export 契约 → 需要契约测试
- ✅ 缺陷 #9（能力画像未更新）涉及 interviews → ability_profile 跨模块回调 → 需要集成测试（不 mock 链路）
- ✅ 缺陷 #6 / #10 涉及 WS 路径 → 需要在真后端 + 真实 WS 适配器上跑

### V. Observability
- ✅ 缺陷 #5 后端 export 已用 `structlog` + `X-Request-ID`（`backend/app/api/v1/export.py:55-61`），结构化日志已就位
- ✅ 缺陷 #10 错题 Coach 启动需加 `start.error` / `start.timeout` 结构化日志
- ✅ 缺陷 #2 / #4 / #7 等前端修复必须有"可读错误"（不在控制台泄露 `Restored N answers...` 这种技术日志）

### Technology & Stack Constraints
- ✅ 前端 React 18 + Vite + Tailwind + react-router-dom 全部沿用
- ✅ 后端 FastAPI + SQLAlchemy 2.0 async + Alembic 沿用
- ✅ AI 编排 LangGraph 沿用（缺陷 #9 触发 ability_dimensions 写入走 SQL，不需新增 LLM 调用）

### Development Workflow
- ✅ 分支 `018-fix-product-defects` 沿用 Spec Kit 命名
- ✅ 修复 PR 每条 MUST 通过 lint / typecheck / unit / e2e / contract
- ✅ Constitution Check 已在 plan Phase 0 完成首轮；Phase 1 设计后复检（见末尾"Post-Design Constitution Re-check"）

**门禁结论：全部通过。无需 Complexity Tracking 条目。**

## Project Structure

### Documentation（本特性）

```text
specs/018-fix-product-defects/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出
│   ├── auth-routing.md          # FR-001 / FR-002
│   ├── dashboard-suggestions.md # FR-003 / FR-004
│   ├── resume-editor.md         # FR-006 / FR-007 / FR-010
│   ├── export-pdf.md            # FR-008 / FR-009
│   ├── interview-scoring.md     # FR-011..FR-015
│   ├── error-coach.md           # FR-016..FR-018
│   ├── jobs-notes.md            # FR-019 / FR-020
│   └── shell-ux.md              # FR-021 / FR-022
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # 由 /speckit-tasks 生成（不在本 plan 范围）
```

### 源代码（仓库根）

```text
# 前端（仓库根 src/，与 e2e/、tests/ 平级）
src/
├── pages/
│   ├── Login.tsx                  # 缺陷 #1
│   ├── Register.tsx               # 缺陷 #1
│   ├── Dashboard.tsx              # 缺陷 #2
│   ├── ResumeEditor.tsx           # 缺陷 #3
│   ├── ResumeList.tsx             # 缺陷 #3
│   ├── InterviewLive.tsx          # 缺陷 #6 / #7
│   ├── InterviewReport.tsx        # 缺陷 #8
│   ├── ErrorBook.tsx              # 缺陷 #10 / #11
│   ├── Jobs.tsx                   # 缺陷 #12
│   ├── AbilityProfile.tsx         # 缺陷 #9（消费端）
│   └── Dashboard.tsx              # 缺陷 #9（消费端）
├── components/
│   ├── resume/AiOptimizePanel.tsx # 缺陷 #4
│   ├── error-book/ErrorCoachPanel.tsx # 缺陷 #10
│   └── layout/Topbar.tsx          # 缺陷 #13
├── hooks/
│   ├── useAbilities.ts            # 缺陷 #2 / #8 / #9
│   └── useErrorCoach.ts           # 缺陷 #10
├── api/
│   ├── export.ts                  # 缺陷 #5（URL / 错误处理）
│   ├── client.ts                  # 全局错误规范化
│   └── jobs.ts                    # 缺陷 #12（字段映射）
├── repositories/
│   ├── resume.ts                  # 缺陷 #3
│   └── jobs.ts                    # 缺陷 #12
├── App.tsx                        # 缺陷 #1 / #14
└── main.tsx

# 后端
backend/app/
├── api/v1/
│   └── export.py                  # 缺陷 #5（错误信息已就位）
├── modules/
│   ├── interviews/
│   │   └── service.py             # 缺陷 #9 补回调
│   ├── ability_profile/
│   │   └── service.py             # 缺陷 #9 消费端（已有 record_dimension_score）
│   ├── jobs/
│   │   ├── models.py              # 缺陷 #12 验证（notes_md 已存在）
│   │   └── schemas.py             # 缺陷 #12 验证（notes_md 已存在）
│   └── errors/                    # 缺陷 #10 验证（coach start 路径）
└── tests/
    ├── integration/
    │   ├── test_interview_to_ability_sync.py  # 缺陷 #9
    │   └── test_export_contract.py            # 缺陷 #5
    └── contract/
        └── test_jobs_notes_field.py           # 缺陷 #12

# 测试
e2e/
├── auth/
│   ├── register-deep-link.spec.ts           # 缺陷 #1
│   └── logout-menu-semantics.spec.ts        # 缺陷 #13
├── dashboard/
│   ├── no-fake-suggestions.spec.ts          # 缺陷 #2
│   └── progressive-tiers.spec.ts            # 缺陷 #2 三档
├── resume/
│   ├── new-resume-editable.spec.ts          # 缺陷 #3
│   ├── empty-resume-no-fake-ai.spec.ts      # 缺陷 #4
│   └── pdf-export-flow.spec.ts              # 缺陷 #5
├── interview/
│   ├── setup-resume-pick.spec.ts            # 缺陷 #6
│   ├── restore-zh-text.spec.ts              # 缺陷 #7
│   ├── scoring-scale-0-10.spec.ts           # 缺陷 #8
│   └── ability-sync.spec.ts                 # 缺陷 #9
├── error-book/
│   ├── coach-start-feedback.spec.ts         # 缺陷 #10
│   └── auto-select-new.spec.ts              # 缺陷 #11
├── jobs/
│   └── notes-roundtrip.spec.ts              # 缺陷 #12
└── shell/
    └── router-future-flags.spec.ts          # 缺陷 #14
```

**Structure Decision**: 单仓 monorepo 沿用现状。前端代码在仓库根 `src/`（不引入 `frontend/src/`），后端在 `backend/app/`（不引入 `backend/src/app/`），均与 Phase 1..6 既有路径一致。

## Complexity Tracking

无 — Constitution Check 全部通过，未触发 Complexity Tracking。

---

## Post-Design Constitution Re-check

*Phase 1 设计完成后复检（research / data-model / 8 份 contracts / quickstart 落地）。*

### I. Library-First
- ✅ 14 个修复都限定在已有库内：
  - 简历 PDF 渲染复用 `backend/app/src/services/pdf_renderer/`
  - 错题 Coach 复用 `backend/app/agents/nodes/error_coach/`
  - 简历锁复用 `src/lib/lock/useLock`
  - 能力画像写复用 `AbilityDimensionRepository.patch`（已被 `self_assess` 验证）
- ✅ 不引入新库（`package.json` / `pyproject.toml` 不动）

### II. CLI Interface
- ✅ 修复不涉及 CLI surface
- ✅ 与 spec § A-001..A-010 一致

### III. Test-First (NON-NEGOTIABLE)
- ✅ 每个 contracts/*.md 都列了"单元 + 契约 + E2E"三层测试
- ✅ 任务拆分时会按 Phase 1 / 4 / 5 惯例把测试任务前置
- ✅ quickstart.md 列出 14 个缺陷 × ≥1 个 E2E 路径

### IV. Integration & Synchronization Testing
- ✅ 缺陷 #3（锁协议）→ `e2e/resume/new-resume-editable.spec.ts`（真后端 + 真锁）
- ✅ 缺陷 #5（PDF 导出）→ `backend/tests/contract/test_export_contract.py` + `e2e/resume/pdf-export-flow.spec.ts`
- ✅ 缺陷 #9（interview → ability_profile 跨模块回调）→ `backend/tests/integration/test_interview_to_ability_sync.py`（不 mock 链路）
- ✅ 缺陷 #6 / #10 涉及 WS 路径 → 端到端跑真后端 + 真 WS（不走 mock 快乐路径）

### V. Observability
- ✅ 缺陷 #5 后端 `structlog` + `X-Request-ID` 已就位（`backend/app/api/v1/export.py:55-61`）
- ✅ 缺陷 #9 面试完成时 patch 写 `ability_dimensions` 由 SQL 触发；R-002 在 `_sync_ability_dimensions` 加结构化日志
- ✅ 缺陷 #10 Coach 启动失败 / 状态错误都映射到中文 + `request_id` 留痕
- ✅ 缺陷 #2 / #4 / #7 全部 UI 渲染真实 / 用户友好文案，前端控制台不泄露 `Restored N answers...` / `+14` 等内部日志

### Technology & Stack Constraints
- ✅ 不触发 schema migration（Q3 验证 `Job.notes_md` 已落库）
- ✅ 不引入新依赖
- ✅ React Router 升级被显式排除（FR-021 用 v6 future flag 走兼容路径）

### Development Workflow
- ✅ 分支 `018-fix-product-defects` 沿用 Spec Kit 命名
- ✅ CLAUDE.md 指针已更新（在 SPECKIT START/END 标记内）
- ✅ 复杂度追踪表为空，遵循 Constitution § Governance

**Post-design 复检结论：全部通过，零新增违规。无需 Complexity Tracking 条目。**

---

## 实施前最终摘要

| 维度 | 数字 |
|---|---|
| 缺陷数 | 14（1 Blocker + 5 High + 5 Medium + 3 Low） |
| 用户故事 | 8（4 P1 + 3 P2 + 1 P3） |
| FR 数 | 22 |
| SC 数 | 11 |
| 修复层 | 13 前端 + 1 后端（缺陷 #9） |
| 后端改动文件 | 1（`backend/app/modules/interviews/service.py` 加 `_sync_ability_dimensions`） |
| Schema 变更 | 0 |
| 新增依赖 | 0 |
| 调研决策 | 14（R-001..R-014） |
| Contracts 文件 | 8 |
| E2E 文件 | 14（每个缺陷 ≥1） |
| 集成 / 契约测试 | 2（后端） |
| 单元 / 组件测试 | 14+（前端） |

**计划完成。**

