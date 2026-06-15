# Implementation Plan: Phase 6 — 全局能力收尾

**Branch**: `005-phase6-global-capabilities` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-phase6-global-capabilities/spec.md`

**Note**: 本 plan.md 是「Phase 6 增量计划」;Phase 1 提供基础设施(账号/RLS/版本/用户基础字段),Phase 2 提供错题本/能力画像/任务/活动流/Jobs/面试历史骨架/基础 Settings 资料 tab,Phase 3 提供锁/WS 控制面/Outbox,Phase 4 提供 LangGraph 基础设施(M14) + Interview Agent(M15),Phase 5 提供剩余 4 个 Agent 子图(M16-M19)。Phase 6 在其上叠加 M20 用户生命周期 + M21 导入导出 + M22 审计完整版 + Settings 全部 tab + Resources/Help + 订阅管理。

---

## Summary

落地 **Phase 6 — 全局能力收尾**:补齐产品最后的基础设施层——用户生命周期管理(注销/冷静期/物理清除)、数据导入导出(全量 ZIP 导出/简历导入)、审计可观测完整版(audit_logs 全量写入 + admin 端点 + 可选 LangSmith)、Settings 全部 tab 从 mock 切真实 API、Resources/Help 真实内容、以及订阅管理与 token 配额控制。Phase 6 是 P1 开发的最终阶段,交付后产品达到完整可用状态,前端 mock 数据仅用于 `VITE_USE_MOCK=true` 开发模式。

**技术路径**(沿用全部已有决议):
- M20 生命周期: `soft_deleted` 标记 + `scheduled_purge_at(90d)` + `cancellation_deadline(7d)` + 两个 ARQ cron(purge_expired_accounts 每日 / physical_cleanup 每周)
- M21 导入导出:ARQ 异步导出任务 → ZIP 打包 → 本地文件系统存储 → 邮件+站内通知;Markdown/JSON 简历导入
- M22 审计: `audit_logs` 表全量写入(写操作 + Agent 子图关键节点) + 用户/admin 双端点 + LangSmith 可选
- 前端 Settings 4 tab: 设备/订阅/安全/导出,各自对接新端点
- Resources/Help: 后端内容 API + 前端展示页面
- 订阅: `free/pro/enterprise` 三级方案 + ARQ cron 月度重置 + 配额检查

---

## Technical Context

**Language/Version**(沿用 Phase 1/2/3/4/5):
- 后端:Python 3.11+(pyproject.toml 锁定)
- 前端:TypeScript 5.6 strict mode
- 数据库 SQL:PostgreSQL 15 方言

**Primary Dependencies**(沿用全部 + 少量新增):
- 后端:沿用 `fastapi` / `sqlalchemy[asyncio]` / `asyncpg` / `arq` / `redis` / `structlog` / `openai>=1.0`
- 后端新增:`openpyxl`(可选,ZIP 元数据写入)、标准库 `zipfile`/`json`/`csv`(导出打包)、`markdown`(Markdown 导入解析)
- 前端:沿用 `react` / `react-router-dom` / `zustand` / `@tanstack/react-query` / `vitest` / `@playwright/test`
- 前端新增:无新增依赖,Settings tab 均复用现有 UI 组件模式
- Phase 6 不引入新的 AI/LLM 依赖

**Storage**:
- 主库:PostgreSQL 15(沿用 T008b 在线 DB)
- 缓存/Pub-Sub:Redis 7(沿用本地 6379,用于 ARQ 任务队列)
- 导出文件:本地文件系统,路径由 `EXPORT_STORAGE_PATH` 环境变量配置(开发默认 `/tmp/exports/`),72 小时自动清理
- LangGraph checkpointer:PostgreSQL langgraph schema(沿用 Phase 4,仅审计读取 tracing 信息)

**Testing**:
- 后端单测:`pytest` + `pytest-asyncio`,每个模块独立测试:M20 状态流转 / M21 打包解析 / M22 audit 写入查询
- 后端集成:`tests/integration/`,起真实 PostgreSQL + Redis,M20/M21/M22 各有一条集成测试覆盖完整流程
- 后端合约:OpenAPI schema 自动生成,新增约 10 个 REST 端点
- 前端单测:`vitest` + `@testing-library/react` + MSW(HTTP),覆盖 4 个 Settings tab + Resources/Help 页面
- 前端 E2E:`playwright`,`tests/e2e/`,覆盖 Settings 全部 tab 流程 + 数据导出闭环

**Target Platform**:
- 后端:Linux 容器(本地开发 Windows + WSL2)
- 前端:现代桌面浏览器(Chrome/Edge/Firefox/Safari 最近 2 个大版本)
- WebSocket:WSS(生产) / WS(开发)

**Project Type**: **web**(frontend + backend,Phase 1 已确立)

**Performance Goals**(对齐 spec §Success Criteria):
- SC-001:账号状态流转 100% 正确,无遗漏
- SC-002:数据导出任务在 5 分钟内完成 95% 的请求(数据量 < 100MB)
- SC-003:审计日志写入延迟 ≤ 1 秒(从操作完成到 audit_logs 记录可见)
- SC-004:Settings 4 tab 在 `VITE_USE_MOCK=false` 模式下完整可用
- SC-005:Resources/Help 首屏加载 ≤ 2 秒,搜索响应 ≤ 1 秒
- SC-006:M20 物理清除不影响在读用户操作(分批 + 低优先级)
- SC-007:订阅配额检查 ≤ 50ms,不阻塞面试启动

**Constraints**:
- M20 物理清除采用异步批量模式(每批 100 条),不影响在读用户
- M20 `cancellation_deadline` 过后不可取消注销,需重新发起
- M21 导出 ZIP 有效期 72 小时,过期自动清理
- M21 导入仅支持 JSON(对称格式)和 Markdown 两种
- M22 audit_logs 按月分区,保留 12 个月;用户仅可见自己的日志
- M22 admin 端点需 admin 角色,Phase 6 不实现 admin 角色管理(通过 DB 直接标记)
- LangSmith 默认不启用,仅开发调试时通过 `backend/.env` 配置
- 订阅不涉及支付网关,升级通过后台手动处理
- 语音模式不在 Phase 6 范围(已 deferred)

**Scale/Scope**(Phase 6 范围):
- 3 个后端模块(M20/M21/M22)
- 约 10 个新 REST 端点(account deletion/export/audit/subscription/resources/help)
- 2 个新 ARQ cron 任务(purge_expired_accounts / physical_cleanup)
- 1 个新 ARQ 任务队列(export_user_data)
- 4 个前端 Settings tab 迁移 + 2 个内容页面(Resources/Help)
- 2 个新增 User 字段(scheduled_purge_at / cancellation_deadline)
- 3 个新增实体表(audit_logs / export_tasks / subscription_plans)
- 2 个新增内容实体(resources / help_faq)
- 0 个新 AI 子图,0 个新外部服务集成

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Library-First

| 检查项 | 状态 | 说明 |
|---|---|---|
| M20 Lifecycle 为独立模块 | ✅ PASS | `backend/app/account/lifecycle.py` 自含状态流转/cron/端点 |
| M21 Export 为独立模块 | ✅ PASS | `backend/app/account/export_service.py` 自含打包/存储/通知 |
| M21 Import 为独立模块 | ✅ PASS | `backend/app/account/import_service.py` 自含解析/校验/创建 |
| M22 Audit 为独立模块 | ✅ PASS | `backend/app/audit/` 自含写入/查询/admin |
| Subscription 为独立模块 | ✅ PASS | `backend/app/account/subscription.py` 自含方案/配额/cron |
| Resources/Help 为独立模块 | ✅ PASS | `backend/app/content/` 自含 CRUD/搜索 |
| Settings tab 前端组件独立 | ✅ PASS | 每个 tab 独立组件,可独立测试 |
| 每个库有 README + 测试 | ✅ PASS | plan 阶段确认,实现阶段交付 |

### II. CLI Interface

| 检查项 | 状态 | 说明 |
|---|---|---|
| M20 Lifecycle CLI | ✅ PASS | `uv run python -m app.account.lifecycle --user-id X --action cancel-deletion` |
| M21 Export CLI | ✅ PASS | `uv run python -m app.account.export --user-id X --output-dir /tmp/` |
| M21 Import CLI | ✅ PASS | `uv run python -m app.account.import --user-id X --file ./resume.md` |
| M22 Audit query CLI | ✅ PASS | `uv run python -m app.audit.logs --user-id X --days 30` |
| Subscription CLI | ✅ PASS | `uv run python -m app.account.subscription --user-id X --plan pro` |

### III. Test-First (NON-NEGOTIABLE)

| 检查项 | 状态 | 说明 |
|---|---|---|
| M20 状态流转测试先行 | ✅ PASS | 先写测试覆盖 `active→soft_deleted→purged→deleted` 全链路 |
| M20 cron 任务测试先行 | ✅ PASS | 先写测试验证 `purge_expired_accounts` / `physical_cleanup` |
| M21 export 打包测试先行 | ✅ PASS | 先写测试验证 ZIP 结构/内容完整性 |
| M21 import 解析测试先行 | ✅ PASS | 先写测试验证 JSON/Markdown 解析 |
| M22 audit 写入查询测试先行 | ✅ PASS | 先写测试验证 audit_logs 写入/RLS 过滤/admin 权限 |
| Settings tab 组件测试先行 | ✅ PASS | 每个 tab 组件测试先于 API 集成 |
| Resources/Help 页面测试先行 | ✅ PASS | 先写组件测试,再连真实 API |

### IV. Integration & Synchronization Testing

| 检查项 | 状态 | 说明 |
|---|---|---|
| M20 cron + DB 集成 | ✅ PASS | 起真实 PostgreSQL + Redis,验证 cron 执行状态流转 |
| M21 导出 + 文件系统 + 通知 | ✅ PASS | 验证 ZIP 生成 → 存储 → 通知闭环 |
| M22 audit 写入 + 查询 | ✅ PASS | 验证写操作触发 audit → 用户查询 → admin 全量查询 |
| Settings API + 前端集成 | ✅ PASS | 验证前端 tab 调用真实 API,数据正确渲染 |
| Resources API 集成 | ✅ PASS | 验证内容 CRUD + 搜索端点 |

### V. Observability

| 检查项 | 状态 | 说明 |
|---|---|---|
| 所有新端点结构化日志 | ✅ PASS | 遵循 Phase 1 JSON 日志 schema |
| M20 关键事件日志 | ✅ PASS | 注销请求/取消/超期/purge 均记录 audit_logs |
| M21 导出进度日志 | ✅ PASS | 导出启动/完成/失败均记录结构化日志 |
| M22 审计自带可观测 | ✅ PASS | M22 本身就是可观测基础设施 |
| 请求关联 ID 传播 | ✅ PASS | 沿用 Phase 1 `request_id` header 传播 |

### Gate Result: ✅ ALL PASS — 可以进入 Phase 0 研究阶段

---

## Project Structure

### Documentation (this feature)

```text
specs/005-phase6-global-capabilities/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output (设计决策)
├── data-model.md        # Phase 1 output (数据模型)
├── quickstart.md        # Phase 1 output (验证指南)
├── contracts/           # Phase 1 output (API 契约)
│   ├── README.md
│   ├── account.md       # M20 + M21 端点
│   ├── audit.md         # M22 端点
│   ├── subscription.md  # 订阅端点
│   └── content.md       # Resources/Help 端点
└── checklists/
    └── requirements.md  # 质量检查清单
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── account/
│   │   ├── lifecycle.py       # M20: 注销/冷静期/purge 状态流转 + endpoints
│   │   ├── export_service.py  # M21: ZIP 打包/存储/通知
│   │   ├── import_service.py  # M21: JSON/Markdown 简历导入
│   │   └── subscription.py    # 订阅方案 + 配额管理 + cron
│   ├── audit/
│   │   ├── service.py         # M22: audit_logs 写入/查询
│   │   ├── router.py          # 用户端 + admin 端点
│   │   └── middleware.py      # 写操作自动审计写入
│   └── content/
│       ├── service.py         # Resources/Help CRUD + 搜索
│       └── router.py          # 内容 API 端点
├── migrations/
│   └── versions/
│       └── XXX_add_lifecycle_audit.sql  # 新增字段 + 表
└── tests/
    ├── unit/account/
    │   ├── test_lifecycle.py
    │   ├── test_export_service.py
    │   ├── test_import_service.py
    │   └── test_subscription.py
    ├── unit/audit/
    │   └── test_audit_service.py
    ├── unit/content/
    │   └── test_content_service.py
    └── integration/
        ├── test_m20_lifecycle.py
        ├── test_m21_export_import.py
        └── test_m22_audit.py

frontend/
├── src/
│   ├── pages/
│   │   ├── Settings.tsx          # 更新 4 tab 为真实 API
│   │   ├── Resources.tsx         # mock → 真实内容
│   │   └── Help.tsx              # mock → 真实 FAQ + 搜索
│   ├── components/
│   │   ├── settings/
│   │   │   ├── DevicesTab.tsx    # 设备管理
│   │   │   ├── SubscriptionTab.tsx # 订阅+配额展示
│   │   │   ├── SecurityTab.tsx   # 修改密码+注销
│   │   │   └── ExportTab.tsx     # 导出入口+进度
│   │   └── content/
│   │       ├── ResourceCard.tsx
│   │       └── FaqAccordion.tsx
│   └── services/
│       └── api/
│           ├── account.ts        # M20 + M21 API 调用
│           ├── audit.ts          # M22 API 调用
│           └── content.ts        # Resources/Help API 调用
└── tests/
    ├── unit/components/
    │   └── settings/
    │       ├── DevicesTab.test.tsx
    │       ├── SubscriptionTab.test.tsx
    │       ├── SecurityTab.test.tsx
    │       └── ExportTab.test.tsx
    └── e2e/
        └── settings-flow.spec.ts
```

**Structure Decision**: 沿用 Phase 1 确立的 backend/frontend 两层结构。Phase 6 模块按业务领域(account/audit/content)组织,每个模块自含 service + router。前端 Settings tab 拆分为独立组件,便于独立开发和测试。

---

## Complexity Tracking

> **无宪法违规项,本表留空。** Phase 6 所有模块均遵循已有模式和决议,无新增技术选型。

---
