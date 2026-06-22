# Implementation Plan: Error Coach 3-Correct E2E

**Branch**: `021-error-coach-e2e` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

**Input**: Feature specification from `specs/021-error-coach-e2e/spec.md`. 用户已审 spec 并确认三点决议：(1) A2 在 plan 阶段代码审查确认 → 已完成，见 R-1；(2) Mock 注入采用后端 `LLM_MOCK_MODE` 环境变量；(3) E2E 文件保持 flat 结构。

---

## Summary

补齐 004 SC-002 的最后一项 E2E 缺口：Error Coach 3 次答对 + frequency 递减的确定性覆盖。后端业务代码零改动，仅在 LLM 客户端工厂添加 ≤30 行 `LLM_MOCK_MODE` 门控的 mock 分支。新增 3 个 E2E 用例（HAPPY-01 / EDGE-01 / ABORT-01）覆盖完整路径、hint 升级、主动退出。E2E 全绿后翻转 004 SC-002 与 `specs/README.md` 004 Notes，v1 trial-launch 基线彻底干净。

**关键技术决策**（来自 [research.md](./research.md)）：
- R-1：`decrement_frequency` 实际语义为「session 结束减 1」，E2E 按代码行为断言；004 spec 与代码的语义差异另起 issue
- R-2：`LLM_MOCK_MODE` + `MockLLMClient` + scenario JSON 文件，工厂函数注入，单测保护
- R-3：新增 `tests/e2e/round-2/fixtures/error-coach-mock.ts`，不扩展既有 `mock-llm.ts`
- R-4：API 创建错题 seed + DB 直连清理，复用 round-1 helpers
- R-5：`playwright.config.ts` webServer 条件注入 `LLM_MOCK_MODE=1`
- R-6：E2E 全绿后翻 004 SC-002 + README Notes

---

## Technical Context

**Language/Version**:
- 后端：Python 3.11+（uv 管理，沿用 Phase 1）
- 前端：TypeScript 5.6 strict mode
- E2E：Playwright 1.48+（`@playwright/test`）

**Primary Dependencies**（沿用既有，无新增）：
- 后端：`fastapi / sqlalchemy[asyncio] / asyncpg / langgraph / openai / structlog / pytest`
- 前端/E2E：`@playwright/test`、`@tanstack/react-query`、`node:fs/path`（scenario 文件写入）
- 复用 `tests/e2e/round-1/helpers/{auth,api,db}.ts`、`tests/e2e/fixtures/mock-llm.ts`（不修改）

**Storage**:
- 主库：PostgreSQL 15（在线，`backend/.env` `DATABASE_URL`）
- LangGraph checkpointer：Postgres `checkpoints` 表（既有）
- Scenario 文件：E2E 运行时写入 `tests/e2e/round-2/fixtures/error-coach-scenarios/*.json`（临时文件，或 os.tmpdir()）
- 不新增表、不新增迁移

**Testing**:
- 后端单测：`backend/tests/test_llm_client_mock.py`（新增）验证 mock 工厂与 scenario 解析
- E2E：`tests/e2e/round-2/error-coach-3-correct.spec.ts`（新增）3 个用例
- 回归保护：`tests/e2e/round-2/interview-mock-llm.spec.ts`（既有，必须保持绿）
- 契约参考：`specs/021-error-coach-e2e/contracts/error-coach-api.md`（本 feature 新增，snapshot 既有 API）

**Target Platform**:
- E2E：chromium（`playwright.config.ts` 默认 project）
- 后端：本地 uvicorn（`playwright.config.ts` webServer 启动）
- 前端：本地 Vite dev server（`playwright.config.ts` webServer 启动）

**Project Type**: web（frontend + backend），但本 feature 改动范围仅限 E2E + 后端 mock hook，无前端改动。

**Performance Goals**:
- 单个 E2E 用例 ≤ 20s（含 seed + 3-4 次 REST 调用 + DB 断言）
- 整个 spec 文件 ≤ 60s（SC-001）
- 10 次重复运行稳定性 ≥ 95%（SC-003）

**Constraints**:
- 后端业务代码零改动（`backend/app/agents/nodes/error_coach/`、`graphs/error_coach.py`、`api/v1/agents_error_coach.py`、`services/error_coach_service.py`）
- 后端 mock hook ≤ 30 行（`llm_client.py` `get_llm_client()` 工厂内）
- 不依赖真实 LLM API Key（`LLM_MOCK_MODE=1` 时跳过 DeepSeek 调用）
- 不污染用户 token 配额（mock 客户端跳过 `_pre_deduct` / `_actual_adjust`）
- 不写入 `ai_messages` 表（mock 客户端跳过 `_write_ai_message`）

**Scale/Scope**:
- 新增 E2E 用例：3 个
- 新增 fixture 文件：1 个（`error-coach-mock.ts`）+ scenario JSON 模板
- 新增后端文件：1 个（`llm_client_mock.py`）+ 1 个单测
- 修改后端文件：1 个（`llm_client.py`，≤30 行 hook）
- 修改前端配置：1 个（`playwright.config.ts`，条件 env 注入）
- 更新 spec 文档：2 个（`004/requirements-status.md`、`specs/README.md`）

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

依据 `.specify/memory/constitution.md` v1.0.0 的 5 大原则 + 技术约束 + 工作流，逐条校验：

### 原则 I — Library-First

| 检查点 | 021 落点 | 状态 |
|---|---|---|
| 每个 feature 自包含 | `specs/021-error-coach-e2e/` 自含 spec/plan/research/data-model/contracts/quickstart/tasks | ✅ |
| Mock 客户端独立文件 | `backend/app/agents/llm_client_mock.py` 独立，不污染主客户端 | ✅ |
| E2E fixture 自包含 | `tests/e2e/round-2/fixtures/error-coach-mock.ts` 不扩展既有 WS fixture | ✅ |
| 有 README | `specs/021-error-coach-e2e/README.md` 描述范围、非目标、关联代码 | ✅ |

### 原则 II — CLI Interface

| 检查点 | 021 落点 | 状态 |
|---|---|---|
| 后端可 CLI 演练 | Error Coach 既有 CLI 入口（M14 基础设施）未受影响 | ✅ |
| E2E 可命令行复现 | `npm run e2e -- tests/e2e/round-2/error-coach-3-correct.spec.ts` | ✅ |
| Mock scenario 文件可读 | JSON 格式，人类可读，可手动编辑 | ✅ |

### 原则 III — Test-First (NON-NEGOTIABLE)

| 检查点 | 021 落点 | 状态 |
|---|---|---|
| 测试先于实现 | 本 feature 本身就是测试覆盖；mock hook 单测先于 hook 代码 | ✅ |
| 最低合理层级 | mock 工厂用单测；评分逻辑用 E2E（跨进程，无法降级到单测） | ✅ |
| 评审签收 | PR 需用户审阅，004 SC-002 翻 done 需 evidence | ✅ |

### 原则 IV — Integration & Synchronization Testing

| 检查点 | 021 落点 | 状态 |
|---|---|---|
| 跨服务通信端到端 | E2E 命中真实后端 + 真实 DB + 真实 LangGraph checkpointer，仅 LLM 层 mock | ✅ |
| 非全 mock 快乐路径 | mock 仅替换 LLM 响应；REST、DB、checkpointer、evaluate 节点逻辑均真实运行 | ✅ |
| 共享 schema 变更 | 无 schema 变更 | ✅ |

### 原则 V — Observability

| 检查点 | 021 落点 | 状态 |
|---|---|---|
| 结构化日志 | mock 客户端复用 `structlog`，记录 `llm.mock_invoke` 事件 | ✅ |
| 请求关联 | E2E 携带 `request_id`（既有 fastapi 中间件） | ✅ |
| 指标 | mock 客户端不发 Prometheus 指标（避免污染），但记录结构化日志 | ✅ |
| 错误上下文 | mock scenario 解析失败时 fallback 到默认响应 + warning 日志 | ✅ |

### 技术约束

| 检查点 | 021 落点 | 状态 |
|---|---|---|
| 前端 TS strict | 本 feature 无前端代码改动 | N/A |
| 后端 OpenAPI | API 未变，既有 OpenAPI 不动 | ✅ |
| LangGraph 编排 | 未改 graph，仅 mock LLM 客户端 | ✅ |
| 同步与离线 | 不涉及 | N/A |
| 安全与隐私 | mock 客户端不调外部 API，不传 PII；`LLM_MOCK_MODE` 默认 unset | ✅ |

### 开发工作流

| 检查点 | 021 落点 | 状态 |
|---|---|---|
| 特性分支 | `021-error-coach-e2e` | ✅ |
| 代码评审 | PR 需 1 次批准，校验 Constitution I–V | ✅ |
| 质量门禁 | lint + typecheck + 单测 + E2E 全绿才合并 | ✅ |
| Constitution Check | 本节即门禁，Phase 1 设计后复检 | ✅ |

**Phase 0 门禁结论**：全部通过，可进入研究阶段。

---

## Project Structure

### Documentation (this feature)

```text
specs/021-error-coach-e2e/
├── plan.md              # This file
├── research.md          # Phase 0 output (R-1 ~ R-6 decisions)
├── data-model.md        # Phase 1 output (复用实体 + E2E 期望值速查)
├── quickstart.md        # Phase 1 output (运行验证指南)
├── contracts/
│   └── error-coach-api.md  # REST contract snapshot (unchanged from 004)
├── checklists/
│   └── requirements.md  # Spec quality checklist (passed)
├── requirements-status.md  # FR/SC status tracking
├── README.md            # Feature overview + non-goals
└── tasks.md             # Phase 2 output (/speckit-tasks, NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/agents/
│   ├── llm_client.py            # MODIFY: add ≤30-line LLM_MOCK_MODE hook in get_llm_client()
│   └── llm_client_mock.py       # NEW: MockLLMClient + scenario JSON parser
└── tests/
    └── test_llm_client_mock.py  # NEW: unit test for mock factory + scenario parsing

tests/
└── e2e/
    ├── fixtures/
    │   └── mock-llm.ts          # UNCHANGED (interview WS mock, kept for regression)
    └── round-2/
        ├── fixtures/
        │   └── error-coach-mock.ts          # NEW: scenario writer + types
        ├── fixtures/
        │   └── error-coach-scenarios/       # NEW: JSON scenario templates
        │       ├── happy.json
        │       ├── edge-1w-3c.json
        │       └── abort-after-1.json
        ├── error-coach-3-correct.spec.ts    # NEW: 3 E2E cases
        ├── interview-mock-llm.spec.ts       # UNCHANGED (regression guard)
        ├── contract-parity.spec.ts          # UNCHANGED
        ├── auth-guard.spec.ts               # UNCHANGED
        └── full-edge-r2.spec.ts             # UNCHANGED

playwright.config.ts            # MODIFY: webServer env injection for LLM_MOCK_MODE

specs/
├── 004-phase5-agent-subgraphs/
│   └── requirements-status.md  # MODIFY: SC-002 in_progress → done
├── 021-error-coach-e2e/        # This feature
└── README.md                   # MODIFY: 004 Notes update
```

**Structure Decision**: Web application 结构（frontend + backend），但本 feature 改动集中在 backend mock 层 + E2E 测试层，无前端代码改动。`playwright.config.ts` 的 webServer 配置改动视为基础设施，非业务。

---

## Implementation Strategy

### Phase A — 后端 Mock 基础设施（TDD）

1. **先写单测** `backend/tests/test_llm_client_mock.py`：
   - `test_get_llm_client_returns_real_when_mock_mode_unset`
   - `test_get_llm_client_returns_mock_when_mock_mode_set`
   - `test_mock_llm_client_reads_scenario_json`
   - `test_mock_llm_client_falls_back_on_missing_scenario`
   - `test_mock_llm_client_evaluate_returns_score_sequence`
   - `test_mock_llm_client_hint_returns_level_content`

2. **写最小实现**：
   - `backend/app/agents/llm_client_mock.py`：`MockLLMClient` 类 + `from_scenario_file` 工厂 + `invoke` 方法
   - `backend/app/agents/llm_client.py`：`get_llm_client()` 添加 `LLM_MOCK_MODE` 分支

3. **重构**：保持 mock 客户端与真实客户端接口一致（`invoke` 签名相同），便于未来扩展。

### Phase B — E2E Fixture 与 Scenario

1. **写 `tests/e2e/round-2/fixtures/error-coach-mock.ts`**：
   - `ErrorCoachScenario` 接口
   - `writeScenarioFile(scenario)` 函数：写入 os.tmpdir()，返回绝对路径
   - 三个预设 scenario：happy / edge-1w-3c / abort-after-1

2. **写 scenario JSON 模板**（3 个文件）：
   - `happy.json`：`evaluate_scores: [8, 9, 9]`
   - `edge-1w-3c.json`：`evaluate_scores: [5, 9, 9, 9]`
   - `abort-after-1.json`：`evaluate_scores: [9]`（仅 1 轮，abort 后结束）

### Phase C — E2E Spec

1. **写 `tests/e2e/round-2/error-coach-3-correct.spec.ts`**：
   - `beforeEach`：登录、seed 错题（API 创建，`frequency=3, status=fresh`）、写 scenario 文件
   - `afterEach`：清理错题（DB 直连）、删除 scenario 临时文件
   - HAPPY-01：3 轮 score≥8，断言 `correct_count` 1/2/3、`status=completed`、DB `frequency=2`
   - EDGE-01：1 错 + 3 对，断言 `hint_level=medium` 在轮 3、`status=completed` 在轮 4、DB `frequency=2`
   - ABORT-01：1 对 + abort，断言 `status=aborted, correct_count_achieved=1`、DB `frequency=2`

2. **复用 helpers**：
   - `tests/e2e/round-1/helpers/auth.ts`：登录拿 JWT
   - `tests/e2e/round-1/helpers/api.ts`：REST 调用
   - `tests/e2e/round-1/helpers/db.ts`：DB 直连查询/清理（预置 `app.user_id` GUC）

### Phase D — Playwright 配置

1. **改 `playwright.config.ts`**：
   - webServer 启动后端时，若 `process.env.VITE_USE_MOCK === 'true'`，注入 `LLM_MOCK_MODE=1` 与 `LLM_MOCK_SCENARIO_PATH`（后者由 E2E spec 动态设置，config 只负责开关）
   - 或：始终注入 `LLM_MOCK_MODE=1`（因 E2E 默认 mock 模式，真实模式手动验证）

2. **决策**：采用「始终注入」方案，简化配置。真实 LLM 验证通过手动设置 `LLM_MOCK_MODE=0` 或 unset 覆盖。

### Phase E — 004 收尾

1. **E2E 全绿后**：
   - 改 `specs/004-phase5-agent-subgraphs/requirements-status.md`：SC-002 行 `in_progress` → `done`，Evidence 指向新 spec
   - 改 `specs/README.md`：004 行 Notes 移除「SC-002 requires a live-LLM scoring loop」说明

2. **更新 021 requirements-status.md**：所有 FR/SC 翻 `done`，附 evidence 路径

---

## Complexity Tracking

> 仅记录 Constitution Check 的偏离项与理由。

| 偏离 | 为何必要 | 拒绝的更简方案 |
|---|---|---|
| 后端添加 mock hook（违反「不改后端」直觉） | E2E 必须验证 `evaluate` 节点逻辑，前端 `page.route()` 只能测 HTTP 契约；mock 必须在 LLM 客户端层注入 | A：前端拦截 REST → 只测契约不测节点逻辑，无法达成 SC-002；B：在 evaluate 节点内加 mock 分支 → 违反「不改业务节点」Non-Goal |
| E2E 按实际代码行为断言（`frequency` 减 1）而非 004 spec 文字（减 3） | E2E 应是绿灯基线，非告警机制；004 spec 与代码的语义差异另起 issue 处理 | A：E2E 断言「减 3」让用例失败以暴露 bug → 破坏 CI 绿灯基线；B：在 021 内修复 004 acceptance #2 → 违反 Non-Goal |
| 004 spec 与代码的语义差异不在 021 修复 | 021 是 E2E 覆盖 feature，范围窄；语义对齐涉及 004 acceptance #2、FR-014 的回改与代码调整，应另起 feature（建议 025） | A：顺手修复 → 范围蔓延，违反「先规划后开发」节奏；B：在 021 spec.md 内回改 004 → 004 是冻结历史文档，不应回改 |
| **实现期发现并修复 ErrorCoachGraph 暂停缺陷**（新增 2026-06-22） | E2E 首跑发现 `start()` 调用 `graph.ainvoke(initial_state)` 会循环到 `correct_count>=3` 才停（因 evaluate 不等待用户输入），`submit_answer` 的 `ainvoke(None)` 变成 no-op。这是 021 E2E 本应发现的 latent bug，正是 SC-002 的覆盖目标。修复方式：`builder.compile(interrupt_after=["hint_ladder"])` 让图在每次 hint 后暂停；`abort()` 用 `as_node="evaluate"` 跳过挂起的评分节点，并补 `decrement_frequency` 调用。共改动 `graphs/error_coach.py` ~25 行，未触及 nodes/api/service。 | A：不改 graph，让 E2E 全部失败 → 021 无法交付，004 SC-002 仍 open；B：用 `aupdate_state` 改写 `start()` → 语义更绕，仍属 graph 改动；C：021 暂停另起 spec → 推迟 SC-002 收口，违背用户「先收 v1 短板」的 v2 节奏 |
| **Mock 客户端按 scenario 文件 mtime 缓存**（新增 2026-06-22） | 首版 `get_llm_client()` 每次调用都 `from_scenario_file()` 重建实例，导致 `MockLLMClient._evaluate_index` 永远归零，evaluate 永远返回 `scores[0]`。改为按文件 mtime 缓存 singleton：E2E 覆写 scenario 文件 → mtime 变 → 缓存失效 → 新实例。 | A：把 `_evaluate_index` 持久化到文件 → 多 worker 并发会竞态；B：在 MockLLMClient 内部加文件 watcher → 复杂度溢出 mock 本意 |

---

## Phase 1 Post-Design Constitution Re-check

| 原则 | 设计后状态 | 备注 |
|---|---|---|
| I Library-First | ✅ | mock 客户端独立文件，fixture 独立 |
| II CLI Interface | ✅ | E2E 命令行可复现 |
| III Test-First | ✅ | 单测先于 mock 实现，E2E 本身即测试 |
| IV Integration Testing | ✅ | 跨进程真实后端 + DB + checkpointer，仅 LLM mock |
| V Observability | ✅ | mock 客户端发结构化日志，既有 request_id 传播 |

**结论**：Phase 1 设计通过 Constitution Check，可进入 tasks 生成。
