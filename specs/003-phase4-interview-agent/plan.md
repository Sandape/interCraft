# Implementation Plan: Phase 4 — Interview Agent 全流程跑通

**Branch**: `003-phase4-interview-agent` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-phase4-interview-agent/spec.md` + Phase 1/2/3 baseline.

**Note**: 本 plan.md 是「Phase 4 增量计划」;Phase 1 提供基础设施(账号/RLS/版本),Phase 2 提供 interview_sessions 表+只读 API+token 配额 cron,Phase 3 提供锁/WS 控制面/Outbox。Phase 4 在其上叠加 M14 LangGraph 基础设施 + M15 Interview 子图 + M22 审计(初版) + M23 Phase 3 前端迁移。

---

## Summary

落地 **Phase 4 — Interview Agent 全流程跑通**:用户可启动 → 完成 5 轮 AI 模拟面试 → 查看报告,全程 WS 流式 token 推送,支持断线重连,双源(ai_messages + checkpoints)持久化 + 每日对账。后端 3 模块(M14/M15/M22)+ 前端 3 页面(InterviewList/InterviewLive/InterviewReport)从 mock 切换到真实 API + WS 流式客户端完整版。

**技术路径**(沿用 Phase 1 DEC-1 ~ DEC-12 + Phase 2 决议 + Phase 3 决议,Phase 4 新增决议见 research.md):
- LLM:DeepSeek V4 Pro(`deepseek-chat`) via OpenAI 兼容协议(2026-06-13 用户决议)
- LangGraph 子图:intake → question_gen ↔ score(×5) → report,PostgreSQL checkpointer
- 统一 LLM 客户端(openai SDK):速率限制 + 自动重试(3 次,指数退避) + 结构化日志 + token 配额预扣
- WS 事件:node.started / token.delta / node.completed / error,单用户单连接复用
- 断线重连:last_seen_checkpoint_id 携带 + checkpoint 恢复
- 双源持久化:ai_messages(LLM 调用元数据) + LangGraph checkpoints(state 快照)
- 每日对账:ARQ cron 比对双源一致性,差异写入 audit_logs + 告警
- 前端 3 页面切真实 API:InterviewList(list/get) + InterviewLive(WS 流式) + InterviewReport(报告展示)

---

## Technical Context

**Language/Version**(沿用 Phase 1/2/3):
- 后端:Python 3.11+(pyproject.toml 锁定)
- 前端:TypeScript 5.6 strict mode
- 数据库 SQL:PostgreSQL 15 方言

**Primary Dependencies**(Phase 4 新增):
- 后端新增:`langgraph>=0.2`(LangGraph 编排) / `openai>=1.0`(OpenAI SDK,DeepSeek 兼容) / `langgraph-checkpoint-postgres>=0.1`(PostgreSQL checkpointer)
- 前端无新增依赖,复用 Phase 1 WS 客户端 + React Query
- Phase 1/2/3 依赖全部沿用

**Storage**:
- 主库:PostgreSQL 15(沿用 T008b 在线 DB)
- 缓存/Pub-Sub:Redis 7(沿用本地 6379)
- LangGraph checkpointer:PostgreSQL(与业务数据库共用,独立 schema 或前缀隔离)
- ARQ 队列:Redis 7(ability_diagnose 异步任务 + 对账 cron)
- 文件:不涉及对象存储(用户导出是 Phase 6 范畴)

**Testing**:
- 后端单测:`pytest` + `pytest-asyncio`,LangGraph 子图用 MemorySaver 测试
- 后端集成:`tests/integration/`,起真实 PostgreSQL + Redis,包含 checkpoint 恢复/双源对账/WS 事件流
- 后端契约:OpenAPI schema 自动生成,新增 WS 端点 + REST 端点
- 前端单测:`vitest` + `@testing-library/react` + MSW(HTTP) + mock WebSocket
- 前端 E2E:`playwright`,`tests/e2e/`,覆盖完整面试流程 + 断线重连

**Target Platform**:
- 后端:Linux 容器(本地开发 Windows + WSL2)
- 前端:现代桌面浏览器(Chrome/Edge/Firefox/Safari 最近 2 个大版本)
- WebSocket:WSS(生产) / WS(开发)

**Project Type**: **web**(frontend + backend,Phase 1 已确立)

**Performance Goals**(对齐 spec §4):
- SC-002:WS 推送延迟 P95 ≤ 200ms(同区域)
- SC-003:LangGraph 单节点执行 P95 ≤ 1.5s(不含 LLM 调用)
- SC-004:断线重连后 5s 内恢复到上一 checkpoint
- SC-009:token 配额预扣检查延迟 ≤ 50ms

**Constraints**:
- 语音模式暂不实现(Phase 4 仅文字模式,语音为后续增量)
- ability_diagnose 子图完整实现在 Phase 5,Phase 4 仅异步触发 + 基础写入
- LangSmith 默认不启用(待 Phase 6 法务评审)
- 面试无悲观锁(每次启动新 thread),同端多 Tab 仅前端检测
- 语音通过浏览器 Web Speech API 实现(不在本 Phase)
- 所有 LLM 调用走统一客户端,不允许各节点直接调 SDK

**Scale/Scope**(Phase 4 范围):
- 用户数:≤ 1000(开发期)
- 面试 session:每用户 ≤ 50
- LLM 调用量:每场面试 ≥ 12 次(5×question_gen + 5×score + intake + report)
- checkpoint 数量:每场面试 12+ 个 state 快照
- 对账:每日 1 次 cron,全量扫描

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Library-First

| 检查项 | 状态 | 说明 |
|---|---|---|
| M14 LangGraph 基础设施为独立库 | ✅ PASS | `backend/app/agents/` 独立 package,自含 prompt/工具/评估夹具 |
| M15 Interview 子图为独立库 | ✅ PASS | 继承 M14,声明自己的 graph/prompts/nodes |
| M22 审计对账为独立模块 | ✅ PASS | `backend/app/audit/` 独立,可被其他模块消费 |
| 每个库有 README + 测试 | ✅ PASS | plan 阶段确认,实现阶段交付 |

### II. CLI Interface

| 检查项 | 状态 | 说明 |
|---|---|---|
| Agent 子图可通过 CLI 调用 | ✅ PASS | `uv run python -m agents.interview --thread-id X --position Y` |
| LLM 调用重放 | ✅ PASS | 从已保存的 checkpoint 夹具重放失败场景 |
| 对账 job 可通过 CLI 手动触发 | ✅ PASS | `uv run python -m audit.reconcile --date 2026-06-13` |

### III. Test-First (NON-NEGOTIABLE)

| 检查项 | 状态 | 说明 |
|---|---|---|
| 所有非平凡变更有测试先行 | ✅ PASS | M14/M15/M22/前端每个 US 先写测试 → 看红 → 实现 |
| Agent prompt 变更有评估夹具 | ✅ PASS | 每个 prompt 模板有 eval fixture + 预期输出断言 |
| LLM mock 策略:单元测试 mock LLM,集成测试用真实 API |

### IV. Integration & Synchronization Testing

| 检查项 | 状态 | 说明 |
|---|---|---|
| WS contract test | ✅ PASS | 前端 WS 客户端 ↔ 后端 WS 服务端 contract |
| Checkpoint 恢复集成测试 | ✅ PASS | 模拟断线 → 重连 → 验证 checkpoint 恢复 |
| 双源对账集成测试 | ✅ PASS | 写入 ai_messages + checkpoints → 跑对账 → 验证一致性 |
| 跨服务通信测试 | ✅ PASS | LangGraph ↔ PostgreSQL checkpointer ↔ ARQ worker |

### V. Observability

| 检查项 | 状态 | 说明 |
|---|---|---|
| 结构化日志 | ✅ PASS | 所有 LLM 调用 + 节点执行 + 对账结果 |
| 请求关联 | ✅ PASS | request_id 跨 backend/LangGraph/ARQ 传播 |
| Prometheus 指标 | ✅ PASS | FR-033 定义的 5 类指标 |
| 错误上下文 | ✅ PASS | LLM 调用失败含 request_id/model/prompt_hash/retry_count |

**Gate Result**: ✅ ALL PASS — 无违规,无需 Complexity Tracking 说明

---

## Project Structure

### Documentation (this feature)

```text
specs/003-phase4-interview-agent/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── ws-events.md     # WS 事件契约
│   ├── interview-sessions-phase4.md  # 面试 REST API(Phase 4 扩展)
│   └── llm-client.md    # 统一 LLM 客户端接口
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── agents/                    # M14: LangGraph 基础设施
│   │   ├── __init__.py
│   │   ├── base.py               # BaseAgent, GraphState, NodeResult
│   │   ├── llm_client.py         # 统一 LLM 客户端(限流/重试/日志/预扣)
│   │   ├── checkpointer.py       # PostgreSQL checkpointer 封装
│   │   └── interview/            # M15: Interview Agent 子图
│   │       ├── __init__.py
│   │       ├── graph.py          # LangGraph StateGraph 定义
│   │       ├── nodes/
│   │       │   ├── intake.py     # 信息采集节点
│   │       │   ├── question_gen.py  # 问题生成节点
│   │       │   ├── score.py      # 评分节点
│   │       │   └── report.py     # 报告生成节点
│   │       ├── prompts/          # Prompt 模板
│   │       │   ├── intake.md
│   │       │   ├── question_gen.md
│   │       │   ├── score.md
│   │       │   └── report.md
│   │       ├── state.py          # InterviewGraphState TypedDict
│   │       └── tests/
│   │           ├── test_graph.py
│   │           ├── test_nodes/
│   │           └── fixtures/     # checkpoint 重放夹具
│   ├── api/
│   │   └── v1/
│   │       ├── interview_sessions.py  # Phase 4 扩展(POST/PATCH + start/finish)
│   │       ├── interview_reports.py   # GET report
│   │       └── ws/
│   │           └── interview.py       # WS 端点:面试流式事件
│   ├── audit/                    # M22: 审计与可观测(初版)
│   │   ├── __init__.py
│   │   ├── reconcile.py          # 双源对账 job
│   │   ├── ai_message_repo.py    # ai_messages 写入/查询
│   │   └── tests/
│   ├── workers/
│   │   └── tasks/
│   │       ├── ability_diagnose.py    # 异步触发 ability_diagnose(Phase 4 基础)
│   │       └── daily_reconcile.py     # 每日对账 cron
│   └── domain/
│       ├── interview_session.py  # InterviewSession domain model(Phase 4 扩展)
│       └── interview_report.py   # InterviewReport domain model
├── migrations/
│   └── versions/
│       └── 0004_phase4_agent.py  # ai_messages / interview_reports 表 + 索引
└── tests/
    ├── integration/
    │   ├── test_interview_graph.py      # 完整 graph 集成测试
    │   ├── test_checkpoint_recovery.py  # checkpoint 恢复测试
    │   ├── test_ws_interview.py         # WS 事件流测试
    │   └── test_reconcile.py            # 对账集成 test
    └── contract/
        └── test_ws_events.py           # WS 事件 contract test

frontend/
└── src/
    ├── pages/
    │   ├── InterviewList.tsx    # Phase 4:mock → 真实 API
    │   ├── InterviewLive.tsx    # Phase 4:真实 WS 流式
    │   └── InterviewReport.tsx  # Phase 4:mock → 真实 API
    ├── components/
    │   └── interview/           # 面试相关组件
    │       ├── StreamingText.tsx    # 流式 token 渲染
    │       ├── ScoreDisplay.tsx     # 评分展示
    │       ├── ProgressBar.tsx      # 第 X/5 轮
    │       └── ReportCard.tsx       # 报告卡片
    ├── hooks/
    │   ├── useInterviewWS.ts       # WS 连接 + 事件消费 + 断线重连
    │   ├── useInterviewSession.ts  # session 状态管理
    │   └── useReport.ts            # 报告数据查询
    └── repositories/
        ├── interviewSessionRepo.ts # Phase 4:扩展 CUD
        └── interviewReportRepo.ts  # Phase 4:新增

tests/
└── tests/e2e/
    ├── interview-flow.spec.ts      # 完整面试流程
    └── interview-reconnect.spec.ts # 断线重连流程
```

**Structure Decision**: 沿用 Phase 1 确立的 Web 应用结构。`backend/app/agents/` 为新增顶层 package(LangGraph 基础设施),`backend/app/audit/` 为新增审计模块。前端 interview 组件集中在 `src/components/interview/`。

---

## Complexity Tracking

> 无 Constitution 违规。Phase 4 复杂性在于:
> 1. LangGraph 子图编排(节点循环 + checkpoint 恢复) — 由 Constitution I(Library-First)约束:每个 agent 是独立库
> 2. WS 流式事件时序(断线重放/partial token 丢弃) — 由 Constitution IV(Integration Testing)约束:contract test 覆盖
> 3. 双源持久化一致性 — 由 Constitution V(Observability)约束:对账 job + Prometheus 告警
>
> 以上均不违反 Constitution,属于正常的架构复杂性,在 Constitution 框架内解决。
