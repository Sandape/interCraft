# Feature Specification: 042 — Agent 运行层 refactor(记忆压缩 + 循环终止)

**Feature Branch**: `042-agent-runtime-refactor`
**Created**: 2026-07-03
**Status**: done (merged 2026-07-04 commit 353753d, US1-MB1/MB2 + US2-MB3/MB4 done, terminal_status=merged per .claude/teams/req042/state.json)
**Input**: User description: "把 LangGraph Agent 8 个维度全部向 openDeepResearch 靠齐,4 个 REQ × 2 US 折中分组"

**所属路线图**: 040-043 4 个 REQ 协同实现 "LangGraph 范式现代化" 大特性,本文档为运行层 P3
**前置依赖**: REQ-040 架构层(状态分层) + REQ-041 稳定性层(错误处理 + MarkComplete 工具)
**参考标杆**: `D:\Project\open_deep_research\src\open_deep_research\deep_researcher.py:511-585`(compress_research) + `state.py`(raw_notes/notes 分离) + `utils.py:665-785`(MODEL_TOKEN_LIMITS)
**现状基线**: `D:\Project\eGGG\docs\research\open_deep_research_comparison.md`

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 循环终止配置化与显式信号(max_iterations + recursion_limit + LLM 终止工具) (Priority: P3)

**作为** LangGraph Agent 维护者
**我希望** 每个 Agent 配置 max_iterations 字段,graph 编译时设 recursion_limit,长循环 Agent 暴露 MarkComplete 工具给 LLM 显式结束
**以便于** 终止条件可配置、可观测(超过 N 次触发告警),LLM 主动结束(避免错误教练非要凑 3 次 correct 的死板)。

**Why this priority**: 配合 REQ-041 错误处理(避免死循环反复重试)和 REQ-041 工具 LLM 化(终止是工具之一)一起做。openDeepResearch supervisor 终止三条件:1) `research_iterations > max_researcher_iterations`(硬上限,默认 6) 2) 无 tool_calls(LLM 决策) 3) `ResearchComplete` 工具(LLM 显式信号)。InterCraft 当前 5 个 agent 终止条件硬编码。

**Independent Test**: 引入 `Configuration.max_iterations` 字段(每个 agent 一个),graph 编译时 `compile(recursion_limit=...)`;interview 节点 LLM `bind_tools([MarkComplete])`;构造一个 7 轮硬上限场景,应在第 7 轮触发 `MaxIterationsReached` 异常并写 state.error。

**Acceptance Scenarios**:

1. **Given** Configuration.max_researcher_iterations=6(默认)
   **When** supervisor 进入第 7 轮
   **Then** 节点返回 `Command(goto=END, update={"research_iterations_exceeded": True})` 不再继续
2. **Given** interview LLM 工具集含 `MarkComplete`
   **When** LLM 调用 `MarkComplete(reason="用户主动结束")`
   **Then** 路由到 END,前端 API 响应 200,无超时
3. **Given** `graph.compile(recursion_limit=30)`
   **When** 死循环触发 30 步上限
   **Then** LangGraph 抛 `GraphRecursionError`,节点捕获后写 state.error(非崩溃)

---

### User Story 2 — 记忆压缩与跨 session 存储(messages 压缩 + raw_notes/notes 分离 + LangGraph Store) (Priority: P3)

**作为** LangGraph Agent 维护者
**我希望** interview / error_coach 长会话引入 messages 压缩节点(超 N 条触发),研究型子图(raw_notes/notes)分离,跨 session 长期记忆用 LangGraph Store
**以便于** 长 session 不再线性增长 token 消耗,研究产出有"原始 / 精炼"两层,跨 session 知识可复用。

**Why this priority**: 这是性能优化层,不影响线上稳定性但显著降本。openDeepResearch researcher 子图用 `compress_research` 节点(deep_researcher.py:511-585)做精炼,supervisor 用 `notes`/`raw_notes` 分离两层(utils.py:599 `get_notes_from_tool_calls`),跨 token 存储用 `langgraph.config.get_store()`(utils.py:28)。InterCraft 当前 messages 无界累积,planner_context 唯一长期记忆入口,需 P3 落地。

**Independent Test**: 在 interview 节点的 LLM 调用前插入 `compress_history` 节点(若 messages > 20 条触发,前 N-10 条用 LLM 总结为 system message,保留最近 10 条原文);新增 raw_notes/notes 字段(在 interview 未来加 web_research 时启用);`planner_context` 节点改用 LangGraph Store 而非每次 DB 查询。

**Acceptance Scenarios**:

1. **Given** interview session 已进行 5 轮(每轮 ~4 messages)
   **When** 进入下一轮 question_gen 节点
   **Then** 前 16 条 messages 被压缩为 1 条 system message,LLM 输入 token 下降 ≥ 50%
2. **Given** researcher subgraph(若新增)返回 `raw_notes: list[str]` 和 `compressed_research: str`
   **When** supervisor 聚合多个 researcher 结果
   **Then** `raw_notes` 用于 deep dive,`notes` 用于 final report
3. **Given** 用户在 session 1 询问 Python 装饰器, session 2 询问闭包
   **When** planner_context 节点启动
   **Then** LangGraph Store 检索出 "用户近期在练 Python 高级特性" 注入到 prompt

---

### Edge Cases

- **循环 + 工具耦合**: US-1 `MarkComplete` 工具依赖 REQ-041 US-2 的 `bind_tools` 实现
- **压缩时机**: messages 压缩触发阈值(20 条)需在线 AB 测试调优,初始值是参考 openDeepResearch compress_research 触发时机
- **LangGraph Store 持久化**: 跨 session 知识需选定 backend(InterCraft 当前是 Postgres,优先用 LangGraph PostgresStore)
- **历史回填**: 已有的 session 数据是否回填到 LangGraph Store?建议"新数据进 Store,旧数据保持只读 DB 查询"双轨过渡

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST 为每个 Agent 添加 `Configuration.max_iterations` 字段(默认值 interview=5 / error_coach=10 / planner=6 / researcher=10)
- **FR-002**: System MUST 在 graph 编译时设 `recursion_limit`(interview=30 / error_coach=20 / 其他=25)
- **FR-003**: System MUST 给 interview / error_coach / planner 三个长循环 Agent 的 LLM `bind_tools([MarkComplete])`
- **FR-004**: System MUST 在 graph 编译时检测 `GraphRecursionError` 并写 `state.error`,非崩溃
- **FR-005**: System MUST 在 interview 节点前插入 `compress_history` 节点,采用**双层触发策略**:1) 主动 — messages ≥ 20 条时主动压缩(前 N-10 条用 LLM 总结为 system message,保留最近 10 条原文);2) 被动 — LLM 抛 token limit 异常时按 `is_token_limit_exceeded` 截断;两层任一触发即压缩
- **FR-006**: System MUST 引入 `CompressedHistory(summary, retained_message_count, original_message_count)` Pydantic 模型
- **FR-007**: System MUST 启用 LangGraph Store 替代每次 DB 查询的长期记忆入口,跨 session 知识可复用
- **FR-008**: System MUST 在 researcher 子图(若新增)中分离 `raw_notes: list[str]`(原始)和 `compressed_research: str`(精炼)两层
- **FR-009**: System MUST 保留旧版 graph 双轨运行 1 周观察期(本 REQ 上线期间新旧并存,可切换)
- **FR-010**: System MUST 保持 Constitution III (Test-First) 合规:每个 US 先写测试(契约/单元/集成),跑红 → 评审 → 写实现 → 跑绿 → 重构

### Key Entities *(include if feature involves data)*

- **`LangGraphStoreEntry`** (新): LangGraph Store 存储格式,`(user_id, namespace) -> value` 键值对
- **`CompressedHistory`** (新, Pydantic): 历史压缩结果,`summary: str` + `retained_message_count: int` + `original_message_count: int`
- **`MaxIterationsReached`** (新, Exception): 硬上限触发异常,`agent_name: str` + `limit: int` + `actual: int`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 5 个 Agent 全部支持 `Configuration.max_iterations` 字段配置,默认值可查
- **SC-002**: 长循环 Agent(>20 步)有显式 `MarkComplete` 工具,LLM 可主动结束
- **SC-003**: interview session 5 轮 LLM 调用 token 消耗下降 ≥ 50%(经 compress_history 压缩)
- **SC-004**: 跨 session 长期记忆命中:MTTR 调试中能通过 LangGraph Store 看到用户历史偏好

## Assumptions

- LangGraph Store Postgres 后端已就绪(InterCraft 已有 Postgres 依赖)
- 压缩阈值 20 条是初始值,实际需基于 1 周线上数据调优
- 压缩 summary 模型与主 LLM 同款(质量优先;cheaper model 总结在 REQ-043 评估,如需降本后续单独 REQ)
- 压缩失败兜底:若 LLM 总结失败,保留原文不压缩 + 写 `state.warning` 字段(不阻塞节点流程)
- **Clarifications 2026-07-03**: 压缩策略 = 主动按数量(20 条) + 被动按 token limit 双层兜底;summary 用主 LLM;失败保留原文 + state.warning
- 循环终止配置化对 5 个 agent 全部生效(无 agent 硬编码 max)
- 工期评估: US-1 (5 dev days) + US-2 (10 dev days,含 LangGraph Store 集成) = 15 dev days
