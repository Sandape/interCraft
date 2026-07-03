# Feature Specification: 040 — Agent 架构层 refactor(状态分层 + 节点拆分)

**Feature Branch**: `040-agent-arch-refactor`
**Created**: 2026-07-03
**Status**: Draft
**Input**: User description: "把 LangGraph Agent 8 个维度全部向 openDeepResearch 靠齐,4 个 REQ × 2 US 折中分组"

**所属路线图**: 040-043 4 个 REQ 协同实现 "LangGraph 范式现代化" 大特性,本文档为架构层 P1
**参考标杆**: `D:\Project\open_deep_research\src\open_deep_research\state.py` + `deep_researcher.py`
**现状基线**: `D:\Project\eGGG\docs\research\open_deep_research_comparison.md`

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 状态架构现代化(InputState/OutputState + override_reducer) (Priority: P1)

**作为** LangGraph Agent 维护者
**我希望** 5 个 Agent 图的状态从单一 TypedDict 演进为 InputState / OverallState / OutputState 三层结构,并引入 override_reducer 区分追加和覆盖语义
**以便于** 新增字段/新节点时不踩 total=False 的隐性坑,且跨子图边界(Interview planner subgraph 与主图)有 Pydantic 契约,不再需要手工桥接节点(`_planner_complete_node`)。

**Why this priority**: 状态是图的根本,后续 REQ-041/042/043 都依赖清晰的状态边界。openDeepResearch 在 state.py:62-95 用了四层 AgentInputState/AgentState/SupervisorState/ResearcherState + InputState/OutputState Pydantic 契约。InterCraft 当前 InterviewGraphState 21 字段无分层是最大架构债,本 REQ 是其他 3 个 REQ 的前置。

**Independent Test**: 在不修改业务逻辑前提下,改造 InterviewGraphState 为 InterviewInputState/InterviewOverallState/InterviewOutputState,所有现有 e2e 用例应不变绿;新增 `class InterviewOutputState(BaseModel)` 替换 `_planner_complete_node` 手工桥接,planner subgraph 输出可直接 merge。

**Acceptance Scenarios**:

1. **Given** Interview graph 编译时指定 `input=InterviewInputState` 和 `output=InterviewOutputState`
   **When** planner subgraph 完成并返回 `compressed_plan: Pydantic`
   **Then** 父图状态自动包含 `interview_plan: Pydantic`,不需要 `_planner_complete_node` 桥接
2. **Given** score 节点需要重置 `scores` 列表
   **When** 节点返回 `{"scores": {"type": "override", "value": []}}`
   **Then** LangGraph 走 override 路径(完全替换),不与 LLM 工具调用冲突
3. **Given** planner_context 节点返回 `planner_context: dict`
   **When** 改造为 `planner_context: PlannerContext` Pydantic 模型
   **Then** planner_generate 节点访问 `state.planner_context.memories` 触发类型校验,字段缺失时清晰报错

---

### User Story 2 — 节点职责与命名规范化(单一职责 + `{agent}.{role}_{action}` + @traced_node) (Priority: P1)

**作为** LangGraph Agent 维护者
**我希望** 所有节点遵循单一职责(LLM 调用 / DB 写 / 工具执行分离),命名统一为 `{agent}.{role}_{action}` 格式,并应用 `@traced_node` 装饰器
**以便于** LangSmith/OTel trace UI 中可读、可定位、可独立重试单个职责,且符合 Constitution V (Observability) "请求关联"原则。

**Why this priority**: 节点混合是 REQ-041 静默失败的根因之一;节点命名规范是 REQ-043 可观测强化的前置;拆 score 节点 / update_dimensions 节点是 REQ-041 工具 LLM 化的边界前提。openDeepResearch 在 deep_researcher.py 中所有节点都是"一次 LLM 调用 + 一次决策",无混合职责。

**Independent Test**: 重写 `interview.score` 节点为 `score_llm` (LLM 调用) + `sink_error` (DB 写) 两个独立节点,中间用 conditional edge 串接;同时应用 `@traced_node` 装饰器,OTel trace 中应能看到 2 个独立 span。

**Acceptance Scenarios**:

1. **Given** `interview.score` 当前混合 LLM 评分 + 错误本 sink
   **When** 拆分为 `interview.score_llm` + `interview.sink_error`
   **Then** 两条边 `score_llm → [interviewer | sink_error | report]` 和 `sink_error → interviewer` 替代原 conditional edge
2. **Given** `ability_diagnose.update_dimensions` 当前混合 4 个 DB 写 + WS push
   **When** 拆分为 `update_dim_db` / `update_history` / `update_activities` / `ws_push` 4 个节点
   **Then** 每个节点可独立失败和重试,WS 推送失败不影响 DB 写
3. **Given** 当前 17 个节点命名风格不统一(intake / question_gen / score / report / aggregate_scores / ...)
   **When** 全局 rename 为 `interview.intake_locate` / `interview.question_gen` / `interview.score_llm` / `interview.report` / `ability_diagnose.aggregate_scores` / ...
   **Then** LangSmith trace 路径呈现 `{agent}.{role}_{action}` 规范,所有节点应用 `@traced_node` 装饰器

---

### Edge Cases

- **LangGraph 版本锁定**: `override_reducer` / `InputState/OutputState` 需 LangGraph ≥ 0.2;需核对当前依赖版本
- **跨 US 依赖**: US-1 状态分层未完成时,US-2 节点拆分的 `_planner_complete_node` 消除无法独立验证
- **生产回滚**: REQ 上线失败需保留旧版 graph 切换能力(双 graph 并存 1 周观察期)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST 引入 `override_reducer` 工具函数,支持 `{"type": "override", "value": [...]}` 完全替换语义,且与现有 `add_messages` reducer 并存可用
- **FR-002**: System MUST 将 `InterviewGraphState`(21 字段)拆为 `InterviewInputState`(仅 messages+thread_id) / `InterviewOverallState`(全量字段) / `InterviewOutputState`(Pydantic,含 interview_report/overall_score);**本 REQ 范围仅 Interview**(其他 4 agent 沿用单一 TypedDict 模式,后续 REQ 复用本 REQ 验证的模式)
- **FR-003**: System MUST 统一所有 LangGraph 节点命名为 `{agent}.{role}_{action}` 格式(如 `interview.score_llm` / `ability_diagnose.aggregate_scores`)
- **FR-004**: System MUST 将 `interview.score` 节点拆分为 `score_llm` (LLM) + `sink_error` (DB) 两个独立节点,中间用 conditional edge 串接
- **FR-005**: System MUST 将 `ability_diagnose.update_dimensions` 拆分为 `update_dim_db` / `update_history` / `update_activities` / `ws_push` 4 个独立节点
- **FR-006**: System MUST 给所有 17 个 LangGraph 节点应用 `@traced_node` 装饰器,OTel 覆盖度 100%
- **FR-007**: System MUST 引入 `planner_context` Pydantic 模型替代 dict-of-dict,字段含 `memories: list[MemoryItem]` + `web_research: WebResearchBundle`
- **FR-008**: System MUST 保留旧版 graph 双轨运行 1 周观察期(本 REQ 上线期间新旧并存,可切换)
- **FR-009**: System MUST 保持 Constitution III (Test-First) 合规:每个 US 先写测试(契约/单元/集成),跑红 → 评审 → 写实现 → 跑绿 → 重构

### Key Entities *(include if feature involves data)*

- **`AgentGraphState`** (基础): 所有 Agent 共享的字段,`messages: Annotated[list, add_messages]` / `thread_id: str` / `user_id: str` / `request_id: str`
- **`AgentInputState`** (新): 继承 MessagesState,只含 messages,作为图的 input schema
- **`AgentOutputState`** (新, Pydantic): 跨子图输出契约,含 `final_report` / `compressed_plan` / `error` 等
- **`PlannerContext`** (新, Pydantic): 长期记忆 + web research 上下文,`memories: list[MemoryItem]` + `web_research: WebResearchBundle`
- **`MemoryItem`** (新, Pydantic): 单条长期记忆,`content: str` + `source: str` + `created_at: datetime` + `relevance_score: float`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Interview Agent graph 支持 InputState/OutputState 三层结构,不再有 `_planner_complete_node` 手工桥接;其他 4 个 agent 暂保持原状(为后续 REQ 打样)
- **SC-002**: 17 个 LangGraph 节点 100% 应用 `@traced_node` 装饰器,OTel trace 中可见全部 span
- **SC-003**: 全局节点命名遵循 `{agent}.{role}_{action}` 规范,LangSmith 路径可读
- **SC-004**: `score_llm` 节点失败不再连带 `sink_error`,两个节点可独立重试和失败降级

## Assumptions

- LangGraph 当前依赖版本 ≥ 0.2,支持 `InputState/OutputState` 参数与 `override_reducer` 模式
- 当前 5 个 Agent state schema 已稳定(无并发修改),可在不破坏业务前提下重构
- `@traced_node` 装饰器已存在(observability/tracing.py:336),本 REQ 只需应用而非实现
- 工期评估: US-1 (2 dev days,只 Interview) + US-2 (5 dev days,全 17 节点) = 7 dev days
- **Clarifications 2026-07-03**: 状态分层范围限定为 Interview only(其他 4 agent 在后续 REQ 复用模式后批量处理)
