# Implementation Plan: WeChat Conversational Agent

**Branch**: `054-wechat-conversational-agent` | **Date**: 2026-07-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/054-wechat-conversational-agent/spec.md`

## Summary

在 REQ-052 微信通道与 REQ-053 新状态模型之上，将当前「闲聊式」`PersonalAgentReply` 升级为**可执行工具的对话编排器**：LLM 意图解析 → 确认态状态机 → 调用 Jobs / Interviews / Ability Profile 服务 → 微信文字回复。同时提供微信异步文字模拟面试（复用 LangGraph checkpoint，跨 Web/微信全局互斥与续面）。

技术方案：在 `backend/app/modules/agent/` 内新增 conversation 子层（intent / tools / context / interview adapter），替换入站回复入口；工具层**进程内调用**现有 Service（非 HTTP 自调用）；会话态存 Redis（TTL 24h）；无新业务表（可选扩展 `agent_messages` 元数据列）。

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 仅复用既有 Web（无新对话 UI）

**Primary Dependencies**: FastAPI, SQLAlchemy (async), Redis, LangGraph + Postgres checkpointer, DeepSeek V4 Pro via `LLMClient`, ARQ（既有出站 drain）

**Storage**: PostgreSQL（复用 `agent_messages` / `jobs` / `interview_sessions`）；Redis（`ConversationContext` TTL=24h）

**Testing**: pytest（意图解析、工具、确认态、面试适配）；Playwright E2E（mock 微信入站 → 验证 Jobs/Interview 落库，覆盖 US1/US2/US4）

**Target Platform**: Linux server (backend); WeChat via iLink（REQ-052）

**Project Type**: web-service 后端能力扩展（对话编排）；前端无新页面

**Performance Goals**:
- SC-004: 用户消息到达后回复 P95 ≤ 15s（含意图解析 + 工具 + 生成，不含确认等待）
- SC-001: 新增岗位端到端 ≤ 60s（含确认中位数 ~15s）
- 面试评分：超时 30s 先发「评分中…」再推送结果

**Constraints**:
- 写操作必须文字确认（无 iLink 按钮）
- 相对时间固定 `Asia/Shanghai`
- 意图 LLM 失败：重试 1 次后友好降级，禁止关键词写数据
- 微信写范围：create / status / location|jd|notes；删除与 Offer → Web
- 全局面试互斥 + 允许跨渠道续面
- Token：意图解析增量需配额扩容（见 research）

**Scale/Scope**:
- 6 User Stories；~12 意图枚举；3 写工具 + 3 查询工具 + 面试编排
- 0 张新业务表；1 个 Redis key 模式；扩展 agent CLI 2 命令
- 主要改动集中在 `modules/agent` + `agents/personal.py` 替换点

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | 对话能力作为 agent 模块内自包含子库（`conversation/`），边界清晰，可独立单测 |
| II. CLI Interface | ✅ PASS | FR-021：`parse-intent`、`simulate-chat` |
| III. Test-First | ✅ PASS | 实现前写意图/工具/确认态/面试适配测试；SC-009 规定 E2E |
| IV. Integration Testing | ✅ PASS | 集成点：channels→conversation、conversation→jobs/interviews/ability、LangGraph checkpoint |
| V. Observability | ✅ PASS | FR-019/020：Prometheus + 结构化日志（不含原文） |

### Post-Design Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | contracts 定义意图/工具/CLI；不侵入 jobs/interviews 内部 |
| II. CLI Interface | ✅ PASS | 见 [contracts/cli.md](./contracts/cli.md) |
| III. Test-First | ✅ PASS | [quickstart.md](./quickstart.md) 验证场景可驱动 TDD |
| IV. Integration Testing | ✅ PASS | 数据模型与工具契约标明跨模块调用 |
| V. Observability | ✅ PASS | 指标与日志 schema 已写入 research + contracts |

## Project Structure

### Documentation (this feature)

```text
specs/054-wechat-conversational-agent/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── intents.yaml     # Intent enum + entity schemas
│   ├── tools.yaml       # Tool I/O contracts
│   └── cli.md           # CLI command contracts
└── tasks.md             # Phase 2 (/speckit-tasks) — not created here
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── agents/
│   │   └── personal.py                 # [MODIFY] 委托 ConversationOrchestrator（保留薄包装）
│   ├── channels/
│   │   └── ilink_pool.py               # [TOUCH] 入站仍走 process_inbound_reply；串行化同用户处理（如需）
│   └── modules/
│       ├── agent/
│       │   ├── cli.py                  # [MODIFY] parse-intent, simulate-chat
│       │   ├── service.py              # [MODIFY] process_inbound_reply → orchestrator
│       │   └── conversation/           # [NEW]
│       │       ├── __init__.py
│       │       ├── orchestrator.py     # 状态机：idle / awaiting_confirmation / in_interview
│       │       ├── intent_parser.py    # LLM 结构化意图解析 + 重试/降级
│       │       ├── context_store.py    # Redis ConversationContext
│       │       ├── confirmations.py    # 确认/取消词表 + pending_action 执行
│       │       ├── job_matcher.py      # 岗位模糊匹配
│       │       ├── time_parser.py      # Asia/Shanghai 相对时间
│       │       ├── reply_formatter.py  # 微信短文案 / 分段
│       │       ├── metrics.py          # FR-019 指标
│       │       ├── tools/
│       │       │   ├── create_job.py
│       │       │   ├── update_status.py
│       │       │   ├── update_fields.py
│       │       │   ├── query_jobs.py
│       │       │   ├── query_reports.py
│       │       │   └── query_ability.py
│       │       └── interview/
│       │           ├── adapter.py      # 微信异步 ↔ InterviewSessionService / graph
│       │           └── mutex.py        # 全局 pending/in_progress 互斥
│       ├── jobs/                       # [REUSE] JobService
│       ├── interviews/                 # [REUSE] InterviewSessionService + graph
│       └── ability_profile/            # [REUSE] dashboard API/service
│
└── tests/
    ├── unit/
    │   └── agent/conversation/         # intent, matcher, time_parser, confirmations
    └── integration/
        └── agent/
            ├── test_conversation_jobs.py
            └── test_conversation_interview.py

tests/e2e/
└── wechat-conversation/
    ├── create-job.spec.ts              # US1
    ├── update-status.spec.ts           # US2
    └── mock-interview.spec.ts          # US4
```

**Structure Decision**: 对话编排放在 `modules/agent/conversation/`，复用 052 通道与 053/既有业务服务；**不**新建独立 FastAPI 路由（用户入口仍是微信）。CLI 挂在既有 `agent.cli` 上满足原则 II。前端无新页面——绑定仍用 052 AgentSettings。

## Complexity Tracking

> No constitution violations. No entries required.

## Implementation Notes (for /speckit-tasks)

1. **替换入口**：`AgentService.process_inbound_reply` / `PersonalAgentReply.run` → `ConversationOrchestrator.handle(parsed)`。
2. **工具调用**：直接 `JobService` / `InterviewSessionService` / ability service，带同一 `AsyncSession` + RLS `user_id`。
3. **面试适配**：优先复用 `submit_answer` + `resume`/`get_current_state`，而非拆节点无状态调用（见 research）。
4. **同用户串行**：入站处理按 user 串行（锁或队列），满足「先完成当前再处理下一条」。
5. **可选迁移**：若需审计意图，给 `agent_messages` 增加可空 `intent`/`confidence`/`metadata` JSONB；非阻塞，可延后。
