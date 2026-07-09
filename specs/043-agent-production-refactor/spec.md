# Feature Specification: 043 — Agent 生产层 refactor(可观测强化 + Checkpoint 池化)

**Feature Branch**: `043-agent-production-refactor`
**Created**: 2026-07-03
**Status**: done (merged 2026-07-04 commit 5669c7d, US1-MB1/MB2 + US2-MB3/MB4 done, terminal_status=merged per .claude/teams/req043/state.json)
**Input**: User description: "把 LangGraph Agent 8 个维度全部向 openDeepResearch 靠齐,4 个 REQ × 2 US 折中分组"

**所属路线图**: 040-043 4 个 REQ 协同实现 "LangGraph 范式现代化" 大特性,本文档为生产层 P4
**前置依赖**: REQ-040 架构层(@traced_node 已在 US-2 起步应用) + REQ-041/042 全部完成
**参考标杆**: `D:\Project\open_deep_research\src\open_deep_research\deep_researcher.py:85`(LangSmith tags) + 当前 InterCraft `backend/app/observability/tracing.py`
**现状基线**: `D:\Project\eGGG\docs\research\open_deep_research_comparison.md`

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 可观测性强化(@traced_node 全覆盖 + LangSmith 接入 + AI 审计 TTL) (Priority: P4)

**作为** LangGraph Agent 维护者 / SRE
**我希望** 所有 17 个 LangGraph 节点应用 `@traced_node` 装饰器(OTel 覆盖度 0% → 100%),接入 LangSmith 配合现有 OTel,AI 审计落库加 30 天 TTL
**以便于** LangGraph Studio 中能看到每个节点的 trace / 输入 / 输出,跨 session 调试可直接跳到 trace_id,审计表不会无限增长。

**Why this priority**: 这是生产完备性锦上添花。@traced_node 在 REQ-040 US-2 已开始应用,本 US 收尾。LangSmith 接入是 openDeepResearch 默认集成(deep_researcher.py:85 `tags=["langsmith:nostream"]`),InterCraft 当前 0% 集成。AI 审计(ai_messages 表)无 TTL 是已知欠债。

**Independent Test**: 给所有 17 个节点加 `@traced_node` 装饰器,LangSmith 项目应能看到全部 trace;运行 30 天后 ai_messages 表新增 PG 定时清理 job,保留 30 天数据。

**Acceptance Scenarios**:

1. **Given** 17 个节点全部应用 `@traced_node(name="interview.score_llm")`
   **When** 运行一个 interview session
   **Then** LangSmith UI 中能看到 17 个独立 span,每个 span 有 `trace_id` + `node_name` + 输入输出摘要
2. **Given** `LANGSMITH_API_KEY` 配置
   **When** LangGraph 应用启动
   **Then** LangSmith 项目 `intercraft-prod` 出现新 trace,与自研 OTel 并行(不冲突)
3. **Given** ai_messages 表 30 天前的记录
   **When** PG 定时 job 每日凌晨跑
   **Then** 30 天前数据被删除,表大小保持稳定

---

### User Story 2 — Checkpoint 池化与重连分级(分业务池 + 三级重连策略) (Priority: P4)

**作为** LangGraph Agent 维护者 / SRE
**我希望** checkpointer 从 app 级单例演进为按业务(用户/租户)分池,重连从单一 retry_graph_op 拆为三级策略(快速重试 / 重建连接 / 报警)
**以便于** 多租户隔离故障域(一个用户 checkpointer 卡死不影响其他用户),重连策略可分级告警(快速失败 vs 持续降级)。

**Why this priority**: 当前 checkpointer.py 300 行实现已 production-grade(memory: dcae326 fix),改造价值主要是多租户隔离和分级告警。openDeepResearch 依赖 LangGraph Server 外部注入 checkpointer,不处理池化。InterCraft 选择自管 checkpointer 是合理工程决策,只需做"分级池化"增强。

**Independent Test**: 引入 `get_checkpointer(pool_key)` 工厂,按 user_id 哈希到 4 个池;模拟一个池耗尽,其他池应不受影响;重连策略拆为 3 级(快速重试 3 次 / 重建连接 1 次 / 报警并写 state.error)。

**Acceptance Scenarios**:

1. **Given** `get_checkpointer(user_id="019ec1be-...")` 哈希到 pool_2
   **When** pool_2 全部连接被占
   **Then** pool_1 / pool_3 / pool_4 不受影响,其他用户 session 正常
2. **Given** checkpointer 连接断开
   **When** 三级重连策略触发
   **Then** L1 快速重试 3 次(每次 1s) → L2 重建连接 1 次(2s) → L3 写 state.error 并 Sentry 报警
3. **Given** CheckpointerUnavailableError(retry_after=30)
   **When** 业务节点捕获
   **Then** 写 `state.error = {"category": "checkpointer_unavailable", "retry_after": 30}`,前端提示稍后重试

---

### Edge Cases

- **LangSmith 成本**: 接入 LangSmith 会增加 token 消耗(trace 上传),需确认预算可承受(500K/月 quota 充裕)
- **OTel + LangSmith 双链路**: 两套 trace 系统并存需避免双倍开销,通过 tag 区分
- **AI 审计 30 天 TTL**: 已有的 ai_messages 数据保留不动,新数据进 TTL pipeline(渐进迁移)
- **Checkpoint 池数量**: 4 池分片规模是否覆盖当前用户量?建议先 AB 测试 1 周再扩到 8 池
- **跨 US 依赖**: US-1 可观测与 US-2 checkpoint 池化无强依赖,可并行推进

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST 给所有 17 个 LangGraph 节点应用 `@traced_node` 装饰器,OTel 覆盖度 100%
- **FR-002**: System MUST 接入 LangSmith(`LANGSMITH_API_KEY` 配置),与自研 OTel 并行不冲突
- **FR-003**: System MUST 为 `ai_messages` 表添加 PG 定时清理 job,保留 30 天数据
- **FR-004**: System MUST 在 LLM 调用时透传 `trace_id` 到 structlog 日志和 HTTP 响应 header(`X-Trace-Id`)
- **FR-005**: System MUST 引入 `get_checkpointer(pool_key)` 工厂,**上线即按 `pool_id = hash(user_id) % 8` 哈希到 8 个池**(支持多租户隔离;避免未来从 4 池扩 8 池的迁移成本)
- **FR-006**: System MUST 将重连策略拆为三级:L1 快速重试 3 次(1s 间隔) / L2 重建连接 1 次(2s) / L3 写 state.error 并 Sentry 报警
- **FR-007**: System MUST 保留旧版 graph 双轨运行 1 周观察期(本 REQ 上线期间新旧并存,可切换)
- **FR-008**: System MUST 保持 Constitution V (Observability) 合规:结构化日志 + trace_id 透传 + 关键指标 + CLI 可观测
- **FR-009**: System MUST 保持 Constitution III (Test-First) 合规:每个 US 先写测试(契约/单元/集成),跑红 → 评审 → 写实现 → 跑绿 → 重构

### Key Entities *(include if feature involves data)*

- **`CheckpointerPoolConfig`** (新, Pydantic): 池配置,`pool_id: int` + `min_size: int` + `max_size: int` + `health_check_interval: int`
- **`ReconnectAttempt`** (新, Pydantic): 重连尝试记录,`level: Literal["L1"|"L2"|"L3"]` + `attempt_at: datetime` + `error: str` + `outcome: Literal["success"|"retry"|"fail"]`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 17 个 LangGraph 节点 100% 应用 `@traced_node` 装饰器,LangSmith/OTel trace 中可见全部 span
- **SC-002**: LangSmith 接入后 trace 上传成功率 ≥ 99%,与 OTel trace 双链路不冲突
- **SC-003**: ai_messages 表数据量在 30 天后保持稳定(PG 定时 job 生效)
- **SC-004**: checkpointer 池化后单池故障不影响其他 7 个池,故障隔离率 100%
- **SC-005**: 重连分级策略触发时,Sentry 报警 ≤ 30 秒送达

## Assumptions

- 当前 checkpointer.py 300 行 production-grade 实现可作为本 REQ 池化改造的基线,无需重写
- LangSmith API key 预算已申请到位(500K/月 quota 足够覆盖),与现有 OTel 接入不冲突
- AI 审计 TTL 30 天符合现有数据保留策略(memory 中未提特殊需求)
- 8 池分片(上线即 8 池,免去未来 4→8 迁移);分片算法 `pool_id = hash(user_id) % 8`;若未来扩 16 池,改 hash 取模即可,无需重 hash 已有 checkpoint
- 工期评估: US-1 (5 dev days,含 LangSmith 接入) + US-2 (10 dev days,含 8 池池化改造) = 15 dev days
- **Clarifications 2026-07-03**: Checkpoint 池化 = 上线即 8 池,mod 8 分片;避免未来迁移成本
