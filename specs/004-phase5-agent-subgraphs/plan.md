# Implementation Plan: Phase 5 — P1 Agent 子图扩展

**Branch**: `004-phase5-agent-subgraphs` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-phase5-agent-subgraphs/spec.md`

**Note**: 本 plan.md 是「Phase 5 增量计划」;Phase 1 提供基础设施(账号/RLS/版本),Phase 2 提供错题本/能力画像只读/任务/活动流/Jobs/面试历史骨架,Phase 3 提供锁/WS 控制面/Outbox,Phase 4 提供 LangGraph 基础设施(M14)+ Interview 子图(M15)+ 审计(M22)。Phase 5 在其上叠加 M16 Resume Optimize + M17 Error Coach + M18 Ability Diagnose(完整版)+ M19 General Coach + M23 前端迁移。

---

## Summary

落地 **Phase 5 — P1 Agent 子图扩展**:实现剩余 4 个 Agent 子图,覆盖「简历优化→面试→能力诊断→错题强化→通用辅导」的完整 AI 闭环。后端 4 模块(M16/M17/M18/M19)+ 前端 4 交互页面从 mock 切换到真实 API。Phase 5 不涉及新表创建,所有子图复用 Phase 4 M14 基础设施(LangGraph checkpointer/统一 LLM 客户端/WS 事件协议)。

**技术路径**(沿用 Phase 1 DEC-1 ~ DEC-12 + Phase 2 决议 + Phase 3 决议 + Phase 4 决议,无新增技术选型):
- LLM:DeepSeek V4 Pro(`deepseek-chat`) via OpenAI 兼容协议(沿用 Phase 4 用户决议)
- LangGraph 子图:M16 `load_branch → diff_jd → suggest_blocks → apply_or_discard(interrupt!) → snapshot`;M17 `fetch_question → hint_ladder → wait_user → evaluate → loop_or_finish`;M18 `aggregate_scores → compare_baseline → generate_insight → update_dimensions`;M19 `intent → route → respond`
- 统一 LLM 客户端:沿用 Phase 4 M14,所有 4 个子图复用同一客户端
- WS 事件:复用 Phase 4 WS 协议(node.started/token.delta/node.completed/error),M16 新增 `interrupt` 事件,M18 新增 `agent.final` 事件
- 前端 4 交互点:ResumeEditor「AI 优化」入口 + ErrorBook「开始强化」CTA + Profile「能力画像更新」状态 + 通用 Coach 新页面

---

## Technical Context

**Language/Version**(沿用 Phase 1/2/3/4):
- 后端:Python 3.11+(pyproject.toml 锁定)
- 前端:TypeScript 5.6 strict mode
- 数据库 SQL:PostgreSQL 15 方言

**Primary Dependencies**(无新增关键依赖,全部沿用):
- 后端:沿用 `langgraph>=0.2` / `openai>=1.0` / `fastapi` / `sqlalchemy[asyncio]` / `asyncpg` / `arq` / `redis` / `jsonpatch` / `structlog`
- 前端:沿用 `react` / `react-router-dom` / `zustand` / `@tanstack/react-query` / `@monaco-editor/react` / `vitest` / `@playwright/test`
- Phase 5 不引入新的后端或前端依赖包

**Storage**:
- 主库:PostgreSQL 15(沿用 T008b 在线 DB)
- 缓存/Pub-Sub:Redis 7(沿用本地 6379)
- LangGraph checkpointer:PostgreSQL langgraph schema(沿用 Phase 4)
- 文件:不涉及对象存储

**Testing**:
- 后端单测:`pytest` + `pytest-asyncio`,每个 Agent 子图独立测试其图结构和节点
- 后端集成:`tests/integration/`,起真实 PostgreSQL + Redis,M16/M17/M18/M19 各有一条集成测试覆盖完整流程
- 后端合约:OpenAPI schema 自动生成,新增多个 agent REST 端点
- 前端单测:`vitest` + `@testing-library/react` + MSW(HTTP) + mock WebSocket
- 前端 E2E:`playwright`,`tests/e2e/`,覆盖 M16 interrupt 流程和 M19 对话流程

**Target Platform**:
- 后端:Linux 容器(本地开发 Windows + WSL2)
- 前端:现代桌面浏览器(Chrome/Edge/Firefox/Safari 最近 2 个大版本)
- WebSocket:WSS(生产) / WS(开发)

**Project Type**: **web**(frontend + backend,Phase 1 已确立)

**Performance Goals**(对齐 spec §Success Criteria):
- SC-001:M16 启动到 interrupt ≤ 15s(不含 LLM 调用),apply/discard ≤ 3s
- SC-002:M18 诊断全流程 ≤ 30s(含 LLM 调用)
- SC-003:M17 单轮问答 ≤ 5s
- SC-004:M19 意图分类 ≤ 2s,WS 流式 P95 ≤ 200ms
- SC-005:4 子图 LLM 调用成功率 ≥ 95%(3 次重试后)

**Constraints**:
- M16 resume_optimize 为唯一启用 interrupt 的子图,需持锁(复用 M12 锁服务)
- M17 error_coach 不持锁,允许同一题多端同时练习
- M18 ability_diagnose 完全异步(ARQ 触发),不阻塞用户操作
- M19 general_coach 不支持嵌套 Agent(仅给跳转引导)
- M16 diff 粒度:MVP 块级(整块替换),v1.1 字段级
- 所有子图共享 Phase 4 token 配额池,无单独配额
- 语音模式仍不涉及(Phase 6 范畴)

**Scale/Scope**(Phase 5 范围):
- 4 个 Agent 子图(M16/M17/M18/M19)
- 7 个新 REST 端点(start/confirm/state/abort/close 等)
- 4 个新 LangGraph 子图定义
- 4 个前端交互点(3 个嵌入现有页面 + 1 个新页面)
- 无新 DB 表,无新 migration

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Library-First

| 检查项 | 状态 | 说明 |
|---|---|---|
| M16 Resume Optimize 为独立库 | ✅ PASS | `backend/app/agents/graphs/resume_optimize.py` 自含 prompt/节点/评估夹具 |
| M17 Error Coach 为独立库 | ✅ PASS | `backend/app/agents/graphs/error_coach.py` 自含 |
| M18 Ability Diagnose 为独立库 | ✅ PASS | `backend/app/agents/graphs/ability_diagnose.py` 自含 |
| M19 General Coach 为独立库 | ✅ PASS | `backend/app/agents/graphs/general_coach.py` 自含 |
| 每个库有 README + 测试 | ✅ PASS | plan 阶段确认,实现阶段交付 |

### II. CLI Interface

| 检查项 | 状态 | 说明 |
|---|---|---|
| M16 子图可通过 CLI 调用 | ✅ PASS | `uv run python -m agents.resume_optimize --branch-id X --target-jd Y` |
| M17 子图可通过 CLI 调用 | ✅ PASS | `uv run python -m agents.error_coach --question-id X` |
| M18 子图可通过 CLI 调用 | ✅ PASS | `uv run python -m agents.ability_diagnose --session-id X` |
| M19 子图可通过 CLI 调用 | ✅ PASS | `uv run python -m agents.general_coach --initial-question X` |
| Prompt 变更可通过 CLI 夹具验证 | ✅ PASS | 复用 Phase 4 评估夹具模式 |

### III. Test-First (NON-NEGOTIABLE)

| 检查项 | 状态 | 说明 |
|---|---|---|
| 每个子图有测试先行 | ✅ PASS | 每个 US 先写测试 → 看红 → 实现,与 Phase 4 一致 |
| Agent prompt 变更有评估夹具 | ✅ PASS | 每个 prompt 模板有 eval fixture + 预期输出断言 |
| LLM mock 策略:单元测试 mock LLM,集成测试用真实 API |

### IV. Integration & Synchronization Testing

| 检查项 | 状态 | 说明 |
|---|---|---|
| M16 interrupt 集成测试 | ✅ PASS | 启动 → 中断 → confirm(apply/discard) → 验证简历更新/未变 |
| M17 error_coach 集成测试 | ✅ PASS | 3 次答对完整流程 + 超时自动结束 |
| M18 ability_diagnose 集成测试 | ✅ PASS | 指定 session → 验证 dimensions 更新值 + activities 写入 |
| M19 general_coach 集成测试 | ✅ PASS | 4 种意图分类的端到端测试 |
| 跨子图 token 配额测试 | ✅ PASS | 并发消费时配额不被超额 |

### V. Observability

| 检查项 | 状态 | 说明 |
|---|---|---|
| 结构化日志 | ✅ PASS | 所有 LLM 调用 + 节点执行(复用 Phase 4 格式) |
| 请求关联 | ✅ PASS | request_id 跨 backend/LangGraph/ARQ 传播(复用) |
| Prometheus 指标(扩展) | ✅ PASS | Phase 5 新增:per-agent 成功率/完成率/意图分类准确率 |
| 错误上下文 | ✅ PASS | LLM 调用失败含 request_id/model/prompt_hash/retry_count(复用) |

**Gate Result**: ✅ ALL PASS — 无违规,无需 Complexity Tracking 说明

---

## Project Structure

### Documentation (this feature)

```text
specs/004-phase5-agent-subgraphs/
├── plan.md              # This file
├── spec.md              # Feature specification (from /speckit-specify)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── agents-api.md    # 通用 Agent API 契约(M16-M17-M19 REST + WS)
│   └── ability-diagnose.md  # M18 ARQ 触发契约
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── agents/
│   │   ├── graphs/
│   │   │   ├── resume_optimize.py        # M16: Resume Optimize StateGraph
│   │   │   ├── error_coach.py            # M17: Error Coach StateGraph
│   │   │   ├── ability_diagnose.py       # M18: Ability Diagnose StateGraph
│   │   │   └── general_coach.py          # M19: General Coach StateGraph
│   │   ├── nodes/
│   │   │   ├── resume_optimize/
│   │   │   │   ├── load_branch.py
│   │   │   │   ├── diff_jd.py
│   │   │   │   ├── suggest_blocks.py
│   │   │   │   ├── apply_or_discard.py   # interrupt! 节点
│   │   │   │   └── snapshot.py
│   │   │   ├── error_coach/
│   │   │   │   ├── fetch_question.py
│   │   │   │   ├── hint_ladder.py
│   │   │   │   ├── evaluate.py
│   │   │   │   └── loop_or_finish.py
│   │   │   ├── ability_diagnose/
│   │   │   │   ├── aggregate_scores.py
│   │   │   │   ├── compare_baseline.py
│   │   │   │   ├── generate_insight.py
│   │   │   │   └── update_dimensions.py
│   │   │   └── general_coach/
│   │   │       ├── intent.py
│   │   │       ├── route.py
│   │   │       └── respond.py
│   │   ├── state/
│   │   │   ├── resume_optimize_state.py
│   │   │   ├── error_coach_state.py
│   │   │   ├── ability_diagnose_state.py
│   │   │   └── general_coach_state.py
│   │   ├── tools/
│   │   │   ├── query_interview_score.py  # M18 新工具
│   │   │   ├── query_resume_blocks.py    # M16 复用
│   │   │   └── query_error_question.py   # M17 复用
│   │   └── prompts/
│   │       ├── resume_optimize/
│   │       │   ├── diff_jd.md
│   │       │   └── suggest_blocks.md
│   │       ├── error_coach/
│   │       │   └── hint_ladder.md
│   │       ├── ability_diagnose/
│   │       │   └── generate_insight.md
│   │       └── general_coach/
│   │           ├── intent.md
│   │           └── respond.md
│   ├── api/
│   │   └── v1/
│   │       ├── agents_resume_optimize.py  # M16: POST start/confirm/state
│   │       ├── agents_error_coach.py      # M17: POST start/messages/abort/state
│   │       └── agents_general_coach.py    # M19: POST start/messages/close/state
│   ├── workers/
│   │   └── tasks/
│   │       └── diagnose_after_interview.py # M18: ARQ 任务(Phase 4 骨架升级)
│   └── services/
│       ├── resume_optimize_service.py     # M16 业务逻辑
│       └── error_coach_service.py         # M17 业务逻辑
├── migrations/
│   └── ── 无需新 migration
└── tests/
    ├── integration/
    │   ├── test_resume_optimize.py
    │   ├── test_error_coach.py
    │   ├── test_ability_diagnose.py
    │   └── test_general_coach.py
    └── contract/
        └── test_agents_api.py

frontend/
└── src/
    ├── pages/
    │   └── GeneralCoach.tsx              # M19: 新页面,对话列表 + 输入框 + 流式渲染
    ├── components/
    │   ├── resume/
    │   │   └── AiOptimizePanel.tsx       # M16: interrupt diff review UI (内联 before/after)
    │   ├── error-book/
    │   │   └── ErrorCoachPanel.tsx       # M17: 错题强化对话面板
    │   └── profile/
    │       └── AbilityUpdateStatus.tsx   # M18: 「能力画像更新中…」状态组件
    ├── hooks/
    │   ├── useResumeOptimize.ts          # M16: start/confirm/state
    │   ├── useErrorCoach.ts              # M17: start/messages/abort
    │   ├── useAbilityDiagnose.ts         # M18: 订阅 agent.final 事件
    │   └── useGeneralCoach.ts            # M19: WS 流式消费
    └── repositories/
        ├── resumeOptimizeRepo.ts
        ├── errorCoachRepo.ts
        └── generalCoachRepo.ts
```

**Structure Decision**: 沿用 Phase 1-4 确立的结构。每个 Agent 子图为独立库(Constitution I),各自持有 graph/state/nodes/prompts。前端新增通用 Coach 页面,其余 3 个 M23 交互点嵌入现有页面。

---

## Complexity Tracking

> 无 Constitution 违规。Phase 5 复杂性在于:
> 1. M16 interrupt 机制(唯一需要人类介入的子图) — 由 Constitution IV(Integration Testing)约束:interrupt → confirm(apply/discard) 完整集成测试覆盖
> 2. 4 个子图并行开发 — 由 Constitution I(Library-First)约束:每个子图独立库,可并行开发和测试
> 3. M18 与 Phase 4 M15 的时序耦合(报告完成后异步触发) — 由 Constitution V(Observability)约束:对账 + 告警

以上均不违反 Constitution,属于正常的架构复杂性,在 Constitution 框架内解决。
