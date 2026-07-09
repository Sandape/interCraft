# Feature Specification: 041 — Agent 稳定性层 refactor(错误处理 + 工具 LLM 化)

**Feature Branch**: `041-agent-stability-refactor`
**Created**: 2026-07-03
**Status**: done (merged 2026-07-03 commit 7b4b7fd, US1-MB1/MB2/MB3 + US2 + 2 fix done; P0 follow-up REQ-041-P0-APPROVAL merged 2026-07-05 commit 0ad2dfc, terminal_status=merged per .claude/teams/req041/state.json)
**Input**: User description: "把 LangGraph Agent 8 个维度全部向 openDeepResearch 靠齐,4 个 REQ × 2 US 折中分组"

**所属路线图**: 040-043 4 个 REQ 协同实现 "LangGraph 范式现代化" 大特性,本文档为稳定性层 P2
**前置依赖**: REQ-040 架构层 refactor(节点拆分后才有干净的错误边界和工具暴露点)
**参考标杆**: `D:\Project\open_deep_research\src\open_deep_research\utils.py:665-785`(is_token_limit_exceeded) + `deep_researcher.py`(bind_tools)
**现状基线**: `D:\Project\eGGG\docs\research\open_deep_research_comparison.md`

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 错误处理与重试统一化(is_token_limit_exceeded + 禁静默失败 + @node_error_handler) (Priority: P2)

**作为** LangGraph Agent 维护者
**我希望** 引入 `is_token_limit_exceeded()` 多 provider 工具函数,所有 LLM 节点走统一的 `@node_error_handler` 装饰器,禁用 score=5/空字符串等静默失败
**以便于** 长上下文场景不再反复失败 3 次才放弃,所有 LLM 节点失败对前端可见(state.error 字段),符合 openDeepResearch 显式降级范式。

**Why this priority**: 这是线上稳定性最直接的缺口。InterCraft 当前 LLM 节点用 `re.search(r"\{.*\}", content, re.DOTALL)` 提取 JSON + 失败时返回 score=5 占位,导致前端显示假数据。openDeepResearch utils.py:665-785 `is_token_limit_exceeded` 支持 OpenAI/Anthropic/Gemini 三 provider,MODEL_TOKEN_LIMITS 表覆盖 88 个模型。DeepSeek 当前也需支持(InterCraft 用 DeepSeek V4 Pro)。

**Independent Test**: 移植 `is_token_limit_exceeded` 工具函数并支持 DeepSeek;在 `interview.score_llm` 节点套 `@node_error_handler(fallback="raise")`;构造一个超长 context(超过 128k token)触发 token limit,应能识别为 `Quota` 或 `Timeout` 异常并写 `state.error`,前端 API 响应中能看到 `error_category` 字段而非 score=5。

**Acceptance Scenarios**:

1. **Given** LLM 调用因 prompt 过长抛 `BadRequestError("prompt is too long")`
   **When** 走 `is_token_limit_exceeded(e, "anthropic:claude-sonnet-4-5")`
   **Then** 返回 True,节点进入 token 截断重试分支(deep_researcher.py:663-683 模式)
2. **Given** LLM 节点失败且未在 `with_structured_output` 注册表中
   **When** 走默认 `fallback_strategy="retry"`
   **Then** 重试 3 次仍失败则抛 `LLMInvokeError`,不再返回 score=5 占位
3. **Given** 节点 `score_llm` 失败
   **When** 异常被捕获
   **Then** state 写入 `state["error"] = {"category": "schema_invalid", "node": "score_llm", "cause": "..."}` 供前端展示

---

### User Story 2 — 工具系统 LLM-bindable 化(对齐 openDeepResearch bind_tools 范式) (Priority: P2)

**作为** LangGraph Agent 维护者
**我希望** 内部工具(查询 DB、tavily_search)改造为 LangChain `@tool` 装饰器,绑定到 LLM 模型使 LLM 自主决定调用顺序与终止,并新增 think_tool/MarkComplete 等控制流工具
**以便于** LLM 拥有流程控制权(openDeepResearch 范式),并支持"反思后再搜索"等 LLM 主导的工作流。

**Why this priority**: 用户在 clarification 阶段明确选择"LLM 可调 (openDeepResearch 范式)"。当前 InterCraft 工具是节点代码调用,LLM 不感知工具存在,流程完全由图边硬编码,无法支持灵活重排。openDeepResearch `bind_tools([ConductResearch, ResearchComplete, think_tool])` 让 supervisor LLM 决定何时 ConductResearch、何时 ResearchComplete。本 US 落地路径:planner_search / planner_generate 节点先 LLM-bindable,error_coach 下一步。

**Independent Test**: 改造 `tavily_search` 为 `@tool` 装饰,绑定到 `planner_search_node` 的 LLM;构造 planner 子图调用,LLM 应能自主决定"先搜 2 个 query,再 think_tool 反思,再搜 1 个 query",而非节点硬编码"搜 3 个"。

**Acceptance Scenarios**:

1. **Given** `tavily_search` 改造为 `@tool(description=...)` 并 `bind_tools([tavily_search, think_tool, MarkComplete])`
   **When** planner LLM 收到 "需要调研某公司 2026 年产品路线"
   **Then** LLM 自主决定调用 `tavily_search(queries=["...", "..."], max_results=5)` 多次 + `think_tool(reflection=...)` 反思
2. **Given** `think_tool` 暴露为工具
   **When** LLM 调用 `think_tool(reflection="我已找到 X 公司的 2025 年报,接下来需要查 2026Q1 财报")`
   **Then** 节点收到 `ToolMessage("Reflection recorded: ...")`,LLM 继续推理
3. **Given** error_coach LLM 有 `MarkComplete` 工具
   **When** LLM 判断"用户已掌握该知识点,3 次 correct_count 不需要凑齐"
   **Then** LLM 调用 `MarkComplete()`,进入 END 而非继续 hint_ladder

---

### Edge Cases

- **DeepSeek 兼容性**: `is_token_limit_exceeded` 当前 openDeepResearch 仅支持 OpenAI/Anthropic/Gemini,需扩展 DeepSeek 异常类型(参考 OpenAI-like 分支)
- **MCP 不涉及**: openDeepResearch 完整支持 MCP(utils.py:449-524),InterCraft 当前无 MCP 需求,本 REQ 不引入
- **工具副作用治理**: `@tool` 暴露的 query_* 工具是只读,可直接 bind;未来引入写库工具时需 `requires_approval=True` 配合 HITL
- **跨 US 依赖**: US-1 错误处理与 US-2 工具 LLM 化无强依赖,可并行推进

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST 引入 `is_token_limit_exceeded(exception, model_name)` 工具函数,支持 OpenAI / Anthropic / Gemini / DeepSeek 四 provider
- **FR-002**: System MUST 提供 `@node_error_handler(fallback_strategy: "retry"|"use_previous"|"hard_fail", fallback_value: Any = None)` 装饰器,统一处理 LLM 节点异常;**默认 fallback_strategy="retry",max_retries=3,重试后 hard_fail 写 state.error**;节点可显式覆盖默认值(如 `intake` 用 `hard_fail` 因首问失败应立即结束)
- **FR-003**: System MUST 禁止 LLM 节点静默失败:失败时写 `state.error` 字段,前端 API 响应可见 `error_category` + `node_name`
- **FR-004**: System MUST 将 `tavily_search` / `query_error_question` / `query_resume_blocks` / `query_interview_score` 改造为 `@tool` 装饰器,绑定到对应 Agent 的 LLM 模型
- **FR-005**: System MUST 新增 `think_tool` 工具(给 LLM "反思"信号)与 `MarkComplete` 工具(给 LLM "显式结束"信号)
- **FR-006**: System MUST 提供 `ToolSpec(name, schema, side_effects, requires_approval)` 工具契约 Pydantic 模型,所有 `@tool` 工具自动生成 ToolSpec
- **FR-007**: System MUST 保留旧版 graph 双轨运行 1 周观察期(本 REQ 上线期间新旧并存,可切换)
- **FR-008**: System MUST 保持 Constitution III (Test-First) 合规:每个 US 先写测试(契约/单元/集成),跑红 → 评审 → 写实现 → 跑绿 → 重构

### Key Entities *(include if feature involves data)*

- **`NodeError`** (新, Pydantic): 节点错误结构,`category: Literal["schema_invalid"|"parse_fail"|"quota"|"timeout"|"oob"|"checkpointer_unavailable"]` + `node_name: str` + `cause: str` + `retry_after: Optional[int]`
- **`ToolSpec`** (新, Pydantic): 工具契约,`name: str` + `schema: dict` + `side_effects: list[str]` + `requires_approval: bool`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `is_token_limit_exceeded` 工具函数覆盖 4 个 provider(OpenAI/Anthropic/Gemini/DeepSeek),单元测试通过率 100%
- **SC-002**: LLM 节点失败 0 例静默 fallback,所有失败通过 `state.error` 字段上报,前端 API 响应中 `error_category` 字段填充率 100%
- **SC-003**: 4 个核心工具(`tavily_search` / `query_error_question` / `query_resume_blocks` / `query_interview_score`)全部支持 LLM `bind_tools` 调用
- **SC-004**: `think_tool` + `MarkComplete` 工具暴露后,LLM 在 planner / error_coach 中可自主决定工作流,无需图边硬编码

## Assumptions

- DeepSeek API 异常体系与 OpenAI 类似(参考 claude-code 经验),`is_token_limit_exceeded` 扩展时按"openai-like"分支处理
- 当前 6 个 LLM 节点中,3 个已结构化输出(REQ-038 US1),剩余 3 个(US2/3/4)由本 REQ 的 US-1 错误处理覆盖
- 工具 LLM 化采用渐进策略:planner_search 节点先全量 @tool 化(LLM 收益最大),error_coach 下一步
- 工期评估: US-1 (5 dev days) + US-2 (7 dev days) = 12 dev days
- **Clarifications 2026-07-03**: `@node_error_handler` 默认 `retry 3 次后 hard_fail`;节点可显式覆盖(如 `intake` 用 `hard_fail` 立即结束)
