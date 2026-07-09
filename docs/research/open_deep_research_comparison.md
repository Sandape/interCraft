# InterCraft vs openDeepResearch — LangGraph Agent 稳定性对比

**调研日期**: 2026-07-03
**对比对象**:
- **标杆**: `D:\Project\open_deep_research` — LangChain 官方深度研究助手（v2 Supervisor + Parallel Researcher 架构，5 个核心文件 ~2356 行）
- **生产**: `D:\Project\eGGG\backend\app\agents` — InterCraft v2 实际部署代码（5 个子图 + A2A 框架，~65 个 Python 文件）

---

## 0. 一句话总结

| 维度 | InterCraft | openDeepResearch | 差距判定 |
|---|---|---|---|
| 1. 状态设计 | 单一 TypedDict + total=False + add_messages | **四层状态 (Input/Overall/Output) + override_reducer** | **显著落后** |
| 2. 节点边界 | 节点混合 LLM+DB+I/O | 节点单一职责,子图嵌套清晰 | **中度落后** |
| 3. Checkpoint | 自研重连 + retry_graph_op 三层防御 | 依赖 LangGraph Server 外部注入 | **生产完备性领先,功能层面落后** |
| 4. 错误处理 | 三层手写重试 + 自定义异常 | `.with_retry()` + 业务级 while 重试 + token 截断 | **核心机制领先,工具层缺失** |
| 5. 工具可控性 | 工具非 LangChain Tool,直接调函数 | `@tool` + Pydantic 工具 + 限流+重试 | **显著落后** |
| 6. 记忆管理 | planner_context 单一入口 + 无压缩 | **多层隔离 + compress_research 节点** | **显著落后** |
| 7. 循环与终止 | 业务层硬编码,无 recursion_limit | 业务层计数器 + 工具终止信号双保险 | **持平** |
| 8. 可观测性 | OTel + structlog + Prometheus + AI 审计 | LangSmith tags + 节点命名规范 | **持平,方向不同** |

**核心结论**: InterCraft 在**生产完备性**(checkpointer 重连、错误处理三层防御、可观测性基础设施)上超过 openDeepResearch,但在**状态架构设计、子图隔离、工具系统、记忆压缩**这四个 LangGraph 范式层面**显著落后**。openDeepResearch 是架构范式的天花板,InterCraft 是生产工程的天花板,二者互补。

---

## 1. 状态设计

### openDeepResearch 的做法(state.py)

**四层状态 + 自定义 override_reducer**:

```python
# 输入态:只含 messages
class AgentInputState(MessagesState): pass

# 整体态:含 supervisor_messages / research_brief / notes / final_report
class AgentState(MessagesState):
    supervisor_messages: Annotated[list, override_reducer]
    research_brief: Optional[str]
    raw_notes: Annotated[list[str], override_reducer] = []
    notes: Annotated[list[str], override_reducer] = []
    final_report: str

# 子图态:supervisor / researcher 各自隔离
class SupervisorState(TypedDict): ...
class ResearcherState(TypedDict): ...

# 输出态:Pydantic 序列化
class ResearcherOutputState(BaseModel):
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = []
```

**关键设计点**:
- **InputState/OverallState/OutputState 三层模式**: LangGraph 官方推荐,隔离输入契约、内部状态、跨子图输出契约
- **override_reducer**: `state.py:55-60` 自定义,支持 `{"type": "override", "value": [...]}` 特殊字典完全替换值,否则追加
- **子图状态隔离**: supervisor_messages 在 SupervisorState 中,researcher_messages 在 ResearcherState 中,**完全不污染主图 messages**
- **Pydantic BaseModel 作为 OutputState**: 跨子图边界用 Pydantic 序列化,内部用 TypedDict 性能更好

### InterCraft 的做法(base.py + state/*.py)

**单层 TypedDict + total=False + 唯一 reducer**:

```python
# base.py:16 — 唯一共享基底
class GraphState(TypedDict, total=False):
    messages: Annotated[list[dict[str, Any]], add_messages]
    thread_id: str
    user_id: str
    request_id: str

# 5 个 agent 各继承一次
class InterviewGraphState(GraphState): ...  # +21 字段
class ErrorCoachState(GraphState): ...      # +6 字段
class AbilityDiagnoseState(GraphState): ... # +6 字段
class GeneralCoachState(GraphState): ...    # +5 字段
class ResumeOptimizeState(GraphState): ...  # +8 字段
```

**已识别的具体问题**:

1. **InterviewGraphState 21 字段严重膨胀**: `current_question` / `questions` / `scores` / `resume_context` / `position` / `company` / `base_location` / `difficulty` / `branch_id` / `overall_score` / `interview_report` / `error` / `job_id` / `requirements_md` / `requirements_provided` / `requirements_truncated` / `requirements_original_chars` / `interview_plan` / `web_research` / `planner_context` — 临时变量(intake 期间)、长期字段(thread_id)、工具结果(scores)全部混在同一个 TypedDict
2. **total=False 副作用**: 节点可返回部分更新,但**所有节点耦合在同一个状态类型**,新增字段后所有节点必须重看
3. **无 InputState/OutputState**: `start_interview()` / `submit_answer()` 共用 InterviewGraphState 全量,签名混乱
4. **唯一 reducer 是 add_messages**: 无 `override_reducer`,节点想"清空 `scores` 然后重写"只能用 `scores: []` 全量重写,容易与 LLM 自动生成的 tool_call 冲突
5. **planner_context 是 dict 包 dict**: `interview/nodes/planner_context.py:213` 把 DB 检索结果塞进 `state["planner_context"]["memories"]`,跨子图边界无 Pydantic 契约

### 改进建议(优先级 P0)

1. **拆 InterviewGraphState 为三层**:
   ```python
   class InterviewInputState(MessagesState): pass  # 只需要 messages + thread_id
   class InterviewOverallState(InterviewInputState): ...  # 内部状态
   class InterviewOutputState(BaseModel):  # 报告输出
       scores: list[int]
       overall_score: float
       interview_report: str
   ```
2. **引入 override_reducer**: 当 score 节点要重置 scores 列表时,用 `{"type": "override", "value": []}`,避免与 LLM 消息流冲突
3. **planner_context 改 Pydantic 模型**: `PlannerContext(memories: list[MemoryItem], web_research: WebResearchBundle)`,跨子图边界可校验

---

## 2. 节点边界

### openDeepResearch 的做法(deep_researcher.py)

**节点职责单一,子图边界清晰**:

```
主图 (AgentState):
├── clarify_with_user         (60)   LLM: 单一判定
├── write_research_brief      (118)  LLM: 单一转换
├── research_supervisor       (710)  subgraph ⬇
└── final_report_generation   (607)  LLM: 单一合成

supervisor subgraph (SupervisorState):
├── supervisor                (178)  LLM 决策
└── supervisor_tools          (225)  工具执行 + 终止判定

researcher subgraph (ResearcherState):
├── researcher                (365)  LLM 决策
├── researcher_tools          (435)  工具执行 + 终止判定
└── compress_research         (511)  LLM 压缩
```

**关键设计点**:
- **每节点 = 一次 LLM 调用 + 一次决策**: 没有"一次节点 LLM 调用 + DB 写 + 业务校验"的混合节点
- **Command 模式统一返回**: `Command(goto=..., update={...})`,跳转和状态更新一起表达
- **子图即函数**: `supervisor_subgraph` 和 `researcher_subgraph` 是纯黑盒,内部状态完全隔离
- **send 工具 vs state 字段**: 工具调用通过 `bind_tools()` 让 LLM 决定,**节点本身不感知下游结构**

### InterCraft 的做法

**节点混合度对比**:

| Agent | LLM+DB+I/O 混合节点 | 纯 LLM 节点 | 纯 I/O 节点 |
|---|---|---|---|
| Interview | intake (LLM+DB), score (LLM+DB error sink), report (LLM+memory) | question_gen | planner_complete |
| Error Coach | fetch_question (DB), evaluate (LLM) | hint_ladder | loop_or_finish |
| Ability Diagnose | aggregate_scores (DB), compare_baseline (DB), update_dimensions (DB+WS) | generate_insight | (无) |
| General Coach | (无) | intent, respond | route |
| Resume Optimize | load_branch (DB), snapshot (DB) | diff_jd, suggest_blocks | apply_or_discard |

**已识别的具体问题**:

1. **score 节点同时做 LLM 评分 + 错误本 sink**: `interview/nodes/score.py:37` `_sink_to_error_book()` 在 score 节点内调用,如果 sink 失败,会污染 score 结果。openDeepResearch 模式应该是"score_node 只评分,sink_node 只落库"
2. **update_dimensions 节点混合 DB 写 + WS push**: `nodes/ability_diagnose/update_dimensions.py:16` 三个职责(写 ability_dimensions / 写 history / 写 activities / push WS),其中任何一个失败的处理路径不一致
3. **planner_complete 是手工桥接节点**: `interview/graph.py:183` 显式从子图输出复制到父图状态,这是"子图状态不自动 merge"的痛点,**说明 Interview 没有用 LangGraph 推荐的 InputState/OutputState 模式**
4. **apply_or_discard 节点零代码**: `nodes/resume_optimize/apply_or_discard.py:12` 是个"interrupt 占位节点",用 interrupt_after 实现 HITL。这是 LangGraph 的合法用法,但有更简洁的写法(`interrupt()` 函数)

### 改进建议(优先级 P1)

1. **拆分 score 节点**: `score_llm` (LLM 调用) + `sink_to_error_book` (DB 写),中间用 conditional edge 串接,sink 失败不影响 score
2. **拆分 update_dimensions**: 4 个独立节点 + 1 个 fan-in,每个失败可独立重试
3. **planner subgraph 真正落地**: `planner_graph.py:24` 当前是 stub,应改成 `StateGraph(PlannerState, output=PlannerOutputState)`,自动 merge

---

## 3. 持久化与 Checkpoint

### openDeepResearch 的做法

**checkpointer 外部注入,不硬编码**:
```python
# deep_researcher.py:719
deep_researcher = deep_researcher_builder.compile()  # 不传 checkpointer
```

**设计哲学**: graph 定义与运行时基础设施解耦,由 LangGraph Server 在启动时根据 `langgraph.json` 配置注入。

**已知空白**:
- v2 代码本身不处理 checkpointer 选型 / 重连 / 池配置
- 全部依赖 LangGraph Platform

### InterCraft 的做法(checkpointer.py)

**生产级 checkpointer 生命周期管理(300 行)**:

```python
# checkpointer.py:97-99 — 单例 + 双重检查锁
_checkpointer: Optional[AsyncPostgresSaver] = None
_pool: Optional[psycopg_pool.AsyncConnectionPool] = None
_init_lock: Optional[asyncio.Lock] = None

# checkpointer.py:126 — 显式建 pool,不用 from_conn_string
self._pool = psycopg_pool.AsyncConnectionPool(
    conninfo=...,
    min_size=1, max_size=10, max_idle=300s,
    reconnect_timeout=300s, timeout=30s,
    keepalives=1, keepalives_idle=30,
    keepalives_interval=10, keepalives_count=5,
)
self._checkpointer = AsyncPostgresSaver(pool=self._pool)

# checkpointer.py:226-291 — retry_graph_op 三层防御
async def retry_graph_op(build_graph_fn, config, op_name, ...):
    for attempt in range(max_retries=2):
        try:
            return await op()
        except OperationalError as e:
            if _is_reconnectable(e):
                force_rebuild_singleton()  # 重置连接池
                await asyncio.sleep(1 * (attempt + 1))
            else:
                raise
    raise CheckpointerUnavailableError(retry_after=30)
```

**关键设计点**:
1. **手动建 AsyncConnectionPool**: 避开了 `from_conn_string` 静默忽略 pool_config 的坑(已写入 memory: dcae326)
2. **三层重连防御**: team-svc.sh + 端口兜底 + pre-merge guard(详见 memory: team-autonomous-loop-v3.1)
3. **WindowsSelectorEventLoopPolicy**: checkpointer.py:31-33 强制 selector loop,绕开 psycopg 拒绝 ProactorEventLoop 的限制
4. **sync list() crash 规避**: preheat() 故意不调用 `cp.list()`(langgraph-checkpoint-postgres 1.0.9 返回 generator,await 会 crash)

**已识别的具体问题**:

1. **checkpointer 是 app 级单例**: `_checkpointer` 全局共享,无法支持"按用户/按租户不同 checkpointer"(生产 OK,测试隔离麻烦)
2. **preheat() 仍调用 `SELECT 1`**: checkpointer.py:84 `_check_connection` 在 pool checkout 时跑一次,有热路径开销
3. **retry_graph_op 是 op-level wrapper,不是框架级**: 任何忘记 wrap 的新代码会绕过重试机制

### 改进建议(优先级 P2)

1. **checkpointer 池化**: 改造成 `get_checkpointer(thread_id)` 工厂,按业务分池
2. **reconnect 指标埋点**: `checkpointer_reconnect_total` 已在 Prometheus 中,但 fail 路径(`CheckpointerUnavailableError`)的 trace 应该强关联到 SLO 看板
3. **P0 改造: ainvoke 走 base 装饰器**: 不要让业务代码手动 wrap `retry_graph_op`,用 LangGraph 的 `RetryPolicy` 在 graph 级别统一处理(参考 openDeepResearch 的 `.with_retry` 模式)

---

## 4. 错误处理与重试

### openDeepResearch 的做法

**模型级 `.with_retry()` + 业务级 while 重试 + token 截断**:

```python
# 模型级:每个 LLM 调用都带
clarification_model = (
    configurable_model
    .with_structured_output(ClarifyWithUser)
    .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
)

# 业务级:token 截断重试
async def compress_research(state, config):
    synthesis_attempts = 0
    while synthesis_attempts < 3:
        try:
            response = await synthesizer_model.ainvoke(messages)
            return {...}
        except Exception as e:
            if is_token_limit_exceeded(e, ...):
                researcher_messages = remove_up_to_last_ai_message(researcher_messages)
                continue

# 渐进式截断:final_report_generation
while current_retry <= 3:
    try:
        return await configurable_model.with_config(...).ainvoke(...)
    except Exception as e:
        if is_token_limit_exceeded(e, ...):
            findings = findings[:findings_token_limit * 0.9]  # 每次 -10%
            continue
```

**关键设计点**:
- **三层重试**: 模型级(.with_retry) → 工具级(execute_tool_safely) → 业务级(while)
- **多 provider token 检测**: `is_token_limit_exceeded()` 支持 OpenAI/Anthropic/Gemini 三家,MODEL_TOKEN_LIMITS 表覆盖 88 个模型
- **失败降级是显式行为**: `compress_research` 失败返回 `compressed_research: "Error synthesizing research report: Maximum retries exceeded"`,不抛异常,不静默

### InterCraft 的做法(llm_client.py:193-250 + checkpointer.py:226-291)

**三层手写重试 + 自定义异常**:

```python
# LLM 层:指数退避
for attempt in range(max_retries=3):
    try:
        return await client.ainvoke(...)
    except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError):
        await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s

# Checkpointer 层:重连 + 重建
retry_graph_op(...)  # max_retries=2, 1s 增量

# A2A 层:retry-once
async def delegate(...):
    try:
        return await agent.handler(...)
    except asyncio.TimeoutError:
        raise  # timeout 不重试(消耗用户配额)
    except Exception:
        return await agent.handler(...)  # 重试 1 次

# Structured Output 层:三种策略
class NodeConfig:
    fallback_strategy: Literal["retry", "use_previous", "hard_fail"]
```

**关键设计点**:
1. **跨层异常类型分类**: `RateLimitError` / `APITimeoutError` / `APIConnectionError` / `InternalServerError` vs `AuthenticationError` / `PermissionDeniedError`(不可重试)
2. **QuotaExceededError 早抛**: 调 LLM 前先预扣,超额直接抛,避免无意义重试
3. **失败降级路径分散**: 各 agent 节点独立处理 Exception,无统一策略

**已识别的具体问题**:

1. **无 is_token_limit_exceeded 工具函数**: InterCraft 没移植 openDeepResearch 的多 provider token 检测,只能依赖 catch-and-retry。LLM 超长上下文时会反复失败 3 次才放弃
2. **Structured Output 重试只覆盖 3 个节点**: `interview.intake` / `interview.score` / `error_coach.evaluate`,其余 6 个 LLM 节点仍用 `re.search(r"\{.*\}", content, re.DOTALL)` 提取 JSON(已记 memory: feedback_reactive_resume_canonical)
3. **无渐进式 findings 截断**: 401 中文字符的 `findings` 一次性塞给 LLM,失败就失败
4. **失败时返回默认值不安全**: 某些节点 catch Exception 后返回 `score=5` / "无法生成建议" — **静默失败**比**显式失败**更危险,前端会显示"5 分"但实际 LLM 没跑通
5. **错误处理分散在 22 个文件**: 没有集中 `error_handler.py`,每个节点独立 `try/except`,策略不一致

### 改进建议(优先级 P0)

1. **移植 is_token_limit_exceeded**: 工具函数支持 OpenAI / Anthropic / DeepSeek,自动识别 token limit 异常
2. **统一错误处理装饰器**: `@node_error_handler(fallback="return_default"|"raise"|"retry_with_truncation")`,所有 LLM 节点统一
3. **禁用静默失败**: 节点失败必须写入 state.error 字段,前端可见。`score=5` 占位应该改为 `state.error="score_failed: <reason>"`
4. **完成 6 个剩余节点的 structured output 化**: REQ-038 US2/US3/US4 应该推进到 100%(当前 33%)

---

## 5. 工具调用可控性

### openDeepResearch 的做法(utils.py)

**`@tool` 装饰器 + Pydantic 工具 + 限流控制**:

```python
# @tool 装饰 + Annotated 参数
@tool(description=TAVILY_SEARCH_DESCRIPTION)
async def tavily_search(
    queries: List[str],
    max_results: Annotated[int, InjectedToolArg] = 5,  # 不可见
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
    config: RunnableConfig = None
) -> str:
    ...

# Pydantic 作为 Tool Schema(LLM bind)
class ConductResearch(BaseModel):
    research_topic: str = Field(description="...")

# MCP 工具 + 认证包装
def wrap_mcp_authenticate_tool(tool: StructuredTool) -> StructuredTool:
    """包装 MCP 工具,处理认证错误 + 异常链"""
    ...

# 多源工具聚合
async def get_all_tools(config):
    tools = [tool(ResearchComplete), think_tool]
    search_tools = await get_search_tool(SearchAPI(get_config_value(configurable.search_api)))
    tools.extend(search_tools)
    mcp_tools = await load_mcp_tools(config, existing_tool_names)
    tools.extend(mcp_tools)
    return tools
```

**关键设计点**:
- **InjectedToolArg**: 隐藏系统参数(config / max_results),LLM 只看到 `queries`
- **Pydantic 工具**: `ConductResearch` / `ResearchComplete` 直接作为 tool schema,LLM bind 后结构化输出
- **MCP OAuth 流程**: `get_mcp_access_token` + token 缓存 + 过期验证,完整生产级认证
- **think_tool 是显式信号**: 让 LLM 显式"反思",避免无脑继续搜索

### InterCraft 的做法(tools/)

**5 个工具,全部是普通 async 函数,无 LangChain Tool 包装**:

```python
# tools/tavily_search.py:67
async def tavily_search(queries: list[str], max_results: int = 5) -> str:
    """直接调用,无 @tool,无 InjectedToolArg"""
    try:
        ...
    except Exception:
        return ""  # 静默失败

# tools/query_error_question.py:17
async def query_error_question_by_id(question_id: str) -> dict | None:
    """DB 读,无 schema,无 LLM 绑定"""
    ...
```

**关键设计点**:
- 工具**不是给 LLM 调用的**,是给节点代码用的(在 LLM 前后做预处理)
- LLM 节点的"工具调用"实际是节点代码自己调,LLM 不感知

**已识别的具体问题**:

1. **工具不暴露给 LLM**: InterCraft 的 LLM 节点用 `with_structured_output(Pydantic)`,从不 `bind_tools([tavily_search, ...])`。这意味着 LLM 无法自主决定"先搜,再回答" — 流程完全由图边硬编码
2. **tavily_search 静默失败**: `tools/tavily_search.py` 任何异常都返回 `""`,`planner_search_node` 收到空结果也不知道
3. **无 LLM-可调工具**: 没有 think_tool 类似的"让 LLM 反思"信号工具
4. **无 Pydantic 工具作为契约**: `ConductResearch` / `ResearchComplete` 这种"用结构化输出做工具决定图跳转"的模式没用上
5. **tool metadata 缺失**: `prompt_caching/layer.py:228` 有 `serialize_tool_definitions` 但实际未启用(已记 memory: M state)
6. **无 MCP 集成**: InterCraft 没有 MCP server 集成(也不需要,场景是内网 DB 工具)

### 改进建议(优先级 P2)

1. **添加 LLM-可调工具**: 把 `tavily_search` 改成 `@tool`,绑定到 `planner_search_node` 的 LLM,让 LLM 自己决定"搜什么"
2. **工具统一接口**: `ToolSpec(name, schema, side_effects, requires_approval)`,HITL 工具(resume_optimize 写库)用 `requires_approval=True` 标记
3. **错误传播而非静默**: `tavily_search` 失败时返回 `ToolResult(error="rate_limit", fallback="empty")`,调用方决定降级策略

---

## 6. 记忆管理

### openDeepResearch 的做法

**四层隔离 + compress_research 节点**:

```
短期上下文(对话记忆):
├── messages (AgentState)         ← 用户对话,全程
├── supervisor_messages (SubState) ← supervisor 推理链
└── researcher_messages (SubState) ← researcher 搜索链

长期产出(结构化):
├── research_brief (AgentState)
├── raw_notes (聚合)
├── notes (精炼)
└── final_report (最终)
```

**关键设计点**:
- **supervisor_messages 隔离**: supervisor 的工具调用历史不污染用户消息,`notes` 通过 `get_notes_from_tool_calls()` 从 supervisor_messages 的 tool 消息提取
- **compress_research 是显式节点**: `deep_researcher.py:511-585` researcher 子图结束前必须压缩,避免原始搜索历史传播给 supervisor
- **final_report_generation 是二次压缩**: 把所有 notes 合成为用户可读报告,**同时清空 notes(state override)避免下次会话污染**
- **raw_notes 与 notes 分离**: raw 是搜索原文(用于 deep dive),notes 是精炼(用于 final report),各取所需

### InterCraft 的做法

**add_messages 是唯一记忆机制,无显式压缩**:

```python
# base.py:16
messages: Annotated[list[dict[str, Any]], add_messages]  # 唯一 reducer

# 唯一长期记忆入口:planner_context_node
def planner_context_node(state):
    memories = await retrieve_active_memories(
        user_id, graph="interview", node="planner_context", token_budget=500
    )
    return {"planner_context": {"memories": memories}}
```

**已识别的具体问题**:

1. **messages 无界累积**: `add_messages` 让 interview 5 轮 × 4 LLM 调用 = 20+ messages 全部进 checkpoint,error_coach 3 轮 + retry 还会更长。**没有 summarizer / windowing**(已记 memory: 156/156 通过但未引入压缩节点)
2. **无 messages 截断**: LLM 调用时 messages 完整传,token 消耗随轮次线性增长
3. **planner_context 是 dict-of-dict**: `state["planner_context"]["memories"]` 无 schema,跨子图边界无校验
4. **score 节点的 error_questions sink 是单向写入**: 没有反向读取,error_coach 拿不到"我之前答错过这道题"的记忆
5. **session 结束不压缩**: interview 5 轮后直接生成 report,但中间 messages 全部保留在 checkpoint,下次 resume 同一 thread_id 还在
6. **无 raw_notes / notes 分离**: Interview 没有"原始搜索结果"和"精炼笔记"的概念,所有结果都直接进 messages
7. **未启用 LangGraph Store**: `langgraph.config.get_store()` 在 openDeepResearch 里用于 token 持久化,InterCraft 完全没用

### 改进建议(优先级 P1)

1. **引入 messages 压缩器节点**: `compress_history` 节点在每次 LLM 调用前用 LLM 总结前 N 轮,只保留摘要 + 最近 K 条原文
2. **planner_context 改 Pydantic**: `class PlannerContext(BaseModel): memories: list[MemoryItem]; web_research: WebResearchBundle`
3. **raw_notes / notes 分离**: interview 节点如果未来加 web_research,需要分两层
4. **启用 LangGraph Store**: 跨 session 长期记忆用 `BaseStore`,而不是每次从 DB 查
5. **thread_id 30 天归档**: checkpoint 不应该永久保留,加 TTL 机制

---

## 7. 循环与终止

### openDeepResearch 的做法

**业务层计数器 + 工具终止信号双保险**:

```python
# supervisor_tools:deep_researcher.py:243-262
research_iterations = state.get("research_iterations", 0)
exceeded_allowed_iterations = research_iterations > configurable.max_researcher_iterations  # 默认 6
no_tool_calls = not most_recent_message.tool_calls
research_complete_tool_call = any(... "ResearchComplete" ...)

if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
    return Command(goto=END, ...)

# researcher_tools:deep_researcher.py:492-498
exceeded_iterations = state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls  # 默认 10
if exceeded_iterations or research_complete_called:
    return Command(goto="compress_research", ...)
```

**关键设计点**:
- **三层终止条件**:
  1. 硬上限(`max_researcher_iterations` = 6 / `max_react_tool_calls` = 10)
  2. LLM 决策(无 tool_calls)
  3. LLM 显式信号(`ResearchComplete` 工具)
- **业务计数器独立于 LangGraph 框架**: 不用 `recursion_limit`,业务自己掌控
- **配置化**: 所有上限都是 Configuration 字段,可在 LangGraph Studio UI 调

### InterCraft 的做法

**业务层硬编码终止条件**:

| Agent | 终止条件 | 是否可配置 |
|---|---|---|
| Interview | `current_question >= 5` | 否,硬编码 5 |
| Error Coach | `correct_count >= 3 or session_aborted` | 否,硬编码 3 |
| Ability Diagnose | 线性 END | N/A |
| General Coach | 线性 END | N/A |
| Resume Optimize | `decision == "apply"` | 是,用户决策 |

**已识别的具体问题**:

1. **无统一 max_steps 字段**: 每个 agent 自己写硬编码,没有 Configuration 化
2. **无 recursion_limit 配置**: 全局用 LangGraph 默认(25/50),interview 5 轮 + 4 LLM/轮 = 20+ 节点,接近上限
3. **无 LLM 显式终止信号**: 节点不向 LLM 暴露 "I'm done" 工具,LLM 无法主动结束循环
4. **无 tool_calls 计数**: error_coach 的 hint_ladder → evaluate 循环是固定的 hint+evaluate 两步,LLM 没有插入"再来一次 hint"的余地
5. **recursion_limit 风险**: 5 个 agent 任意一个死循环都会触发 LangGraph 默认上限(25),错误信息不友好

### 改进建议(优先级 P2)

1. **每个 agent 加 `max_iterations` 字段**: 统一从 `Configuration.from_runnable_config()` 读
2. **编译时设 `recursion_limit`**: `graph.compile(recursion_limit=...)`,每个 agent 不同
3. **给 LLM 提供"done"信号**: 对长循环 agent(interview / error_coach),加 `MarkComplete` Pydantic 工具,让 LLM 显式结束
4. **error_coach 暴露循环计数**: 让 LLM 看到 `attempt_count: 2/3`,避免它"再来一次 hint"的冲动

---

## 8. 可观测性

### openDeepResearch 的做法

**LangSmith 原生集成 + 节点命名规范**:

```python
# 每个 LLM 调用都带 langsmith tag
model_config = {
    "model": ...,
    "tags": ["langsmith:nostream"]  # 关键!避免 trace 中流式输出
}

# 节点命名规范
- clarify_with_user (动词+对象)
- write_research_brief (动作清晰)
- supervisor / supervisor_tools (角色+职责)
- compress_research (动作+产物)
```

**关键设计点**:
- **LangSmith Studio 集成**: 通过 `langgraph dev` 启动,自动 trace 所有节点
- **节点命名 = trace 路径**: 命名规范让 LangSmith UI 路径可读
- **返回 partial state(delta)**: 节点返回 `Command(update={...})`,LangSmith 自动对比前后 state
- **无自定义 observability 层**: 100% 依赖 LangSmith + LangGraph 平台

### InterCraft 的做法(observability/ + structured_output/observability.py)

**自研 OTel + structlog + Prometheus + AI 审计**:

```python
# observability/tracing.py:336
@traced_node(name)  # 装饰器,但实际未使用!
async def my_node(state): ...

# observability/tracing.py:228
@traced_tool(name)
async def tavily_search(...): ...

# 8 个 Prometheus 指标
- llm_invoke_total{model,node,result}
- llm_token_consumed_total{model,type}
- llm_invoke_duration_seconds{model,node}
- checkpointer_reconnect_total
- structured_invocation_total{node,contract,status,failure_category,fallback_used}
- llm_cache_hit_total{node,graph,result}
- llm_cache_cached_tokens_total{node,graph}
- llm_cache_uncached_tokens_total{node,graph}
- llm_cache_discount_tokens_total{user_id,graph}

# AI 调用审计
llm_client._extract_and_record_ai_invocation()  # 每次 LLM 写 ai_messages
- invocation_id, graph, node, model, prompt_fingerprint
- prompt_tokens, completion_tokens, estimated_cost
- latency_ms, retry_count, status, error_category

# A2A 消息审计
a2a_messages 表(trace_id, thread_id, parent_agent, child_agent, task, status, ...)
```

**关键设计点**:
1. **结构化日志全栈**: 22 个文件 115 次 structlog,logger 名规范 `agents.<module>`
2. **fail-open OTel**: tracing.py 全部 try/except,OTel 故障不阻塞业务
3. **trace_id 透传日志**: structlog processor 自动注入 `trace_id` + `span_id`
4. **AI 调用审计落库**: 每次 LLM 写入 ai_messages 表,可按 thread_id / user_id / node 查询
5. **P0 教训**: `@traced_node` 装饰器存在但**没有任何节点使用**(已记 memory: 11 batches 收官)

**已识别的具体问题**:

1. **节点命名不统一**: interview 用 snake_case + 名词(`intake` / `question_gen` / `score` / `report`),ability_diagnose 用 noun_verb(`aggregate_scores` / `compare_baseline` / `generate_insight` / `update_dimensions`),trace UI 看不出"哪个节点是 LLM 节点"
2. **`@traced_node` 装饰器未启用**: observability/tracing.py:336 定义了但所有节点都裸用,OTel 覆盖度 = 0%
3. **无 LangSmith 集成**: REQ-033 cycle 11 提到"trace drilldown"完成,但 LangGraph Studio 仍未启用
4. **Prometheus 指标过多未利用**: 9 个 cache 相关指标 + 8 个 LLM 指标,但没有 SLO 看板
5. **日志缺 trace_id 关联**: 业务日志 + structlog 有 trace_id,但**前端错误无 trace_id**,无法定位
6. **AI 审计无 retention**: ai_messages 表无限增长,无 TTL(已记 memory: 033 cycle 完成 redaction/retention)

### 改进建议(优先级 P0)

1. **应用 `@traced_node` 装饰器**: 给所有 17 个节点加上,OTel 覆盖度从 0 → 100%
2. **统一节点命名规范**: `{agent}.{role}_{action}` 格式,如 `interview.question_gen` / `error_coach.hint_ladder`
3. **前端错误带 trace_id**: 422/500 响应 header 加 `X-Trace-Id`,前端 alert 显示
4. **配置 LangSmith**: `LANGSMITH_API_KEY` 接入,与自研 OTel 并行(LangSmith 看 trace,Prometheus 看 SLO)
5. **AI 审计 30 天 TTL**: 加 PG 定期清理 job

---

## 9. 综合差距地图

### P0 — 影响稳定性的核心差距(必须修)

| # | 差距 | 影响 | 建议改动量 |
|---|---|---|---|
| 1 | Interview state 21 字段无分层 | 新增节点/字段时易踩坑 | 4 dev days |
| 2 | 6 个 LLM 节点未结构化输出 | JSON parse 失败率高,静默 fallback | 5 dev days |
| 3 | 无 is_token_limit_exceeded | 长上下文反复失败 3 次 | 1 dev day |
| 4 | 静默失败(score=5 占位) | 前端显示假数据 | 2 dev days |
| 5 | `@traced_node` 未应用 | OTel 覆盖度 0% | 1 dev day |
| 6 | 节点命名不统一 | trace 不可读 | 0.5 dev day |

### P1 — 架构层面的范式追赶(1-2 月内)

| # | 差距 | 建议 |
|---|---|---|
| 1 | 无 InputState/OutputState 分层 | 改造 InterviewGraphState |
| 2 | 无 messages 压缩器 | 加 compress_history 节点 |
| 3 | 无 override_reducer | 移植 state.py:55 |
| 4 | planner_context 改 Pydantic | 跨子图边界契约 |
| 5 | LLM 节点混合 DB/I/O | 拆 score / update_dimensions |
| 6 | 工具不暴露给 LLM | 至少给 planner_search 加 @tool |

### P2 — 长期演进(3-6 月)

| # | 差距 | 建议 |
|---|---|---|
| 1 | 无 MCP 集成 | 内网场景可选 |
| 2 | 无 LangSmith | 接入做 trace drilldown |
| 3 | checkpointer 池化 | 按用户分池 |
| 4 | recursion_limit 配置化 | 加 Configuration 字段 |
| 5 | AI 审计 TTL | PG 定期清理 |
| 6 | 跨 session LangGraph Store | 长期记忆 |

---

## 10. 落地建议(给 InterCraft 团队)

### 短期(2 周内, 5 dev days)
1. **统一节点命名规范** — 全局 rename,半天
2. **应用 `@traced_node` 装饰器** — 全局装饰,半天
3. **移植 is_token_limit_exceeded** — 工具函数,1 天
4. **禁用 score=5 静默失败** — 改写为 state.error 注入,1 天
5. **统一 Configuration 加 max_iterations** — 5 个 agent 各加字段,1 天

### 中期(1 月内, 15 dev days)
1. **Interview state 拆 InputState/OverallState/OutputState** — 5 天
2. **完成 6 个节点 structured output 化** — REQ-038 US2/3/4 推完,5 天
3. **引入 compress_history 节点** — 3 天
4. **拆分 score / update_dimensions 节点** — 2 天

### 长期(3 月内, 30 dev days)
1. **LLM 可调工具化** — 至少 tavily_search / 错误本查询,10 天
2. **LangSmith 集成** — 与自研 OTel 并行,5 天
3. **跨 session 长期记忆** — LangGraph Store + PG FTS,10 天
4. **recursion_limit / max_iterations 全配置化** — 5 天

---

## 附录 A:调研文件清单

### openDeepResearch 读取
- `D:\Project\open_deep_research\src\open_deep_research\state.py` (95 行)
- `D:\Project\open_deep_research\src\open_deep_research\configuration.py` (251 行)
- `D:\Project\open_deep_research\src\open_deep_research\deep_researcher.py` (718 行)
- `D:\Project\open_deep_research\src\open_deep_research\prompts.py` (367 行)
- `D:\Project\open_deep_research\src\open_deep_research\utils.py` (925 行)
- `D:\Project\open_deep_research\langgraph.json`

### InterCraft 调研范围
- `backend\app\agents\base.py` + `checkpointer.py` + `exceptions.py` + `llm_client.py`
- `backend\app\agents\interview\graph.py` + `planner_graph.py` + `nodes\*.py`
- `backend\app\agents\graphs\{ability_diagnose,error_coach,general_coach,resume_optimize}.py`
- `backend\app\agents\nodes\{error_coach,ability_diagnose,general_coach,resume_optimize}\*.py`
- `backend\app\agents\a2a\supervisor.py` + `schemas.py` + `delegation.py` + `routing.py`
- `backend\app\agents\state\*.py` + `tools\*.py` + `structured_output\*.py`
- `backend\app\observability\tracing.py` + `prompt_caching\layer.py`

### 历史背景(memory 关联)
- `interview_checkpointer_caveat.md` (023 fix dcae326) — checkpointer 重连
- `ability_diagnose_pipeline.md` — JSONB binds / UPSERT 模式
- `feedback_ac_lock_pattern.md` — AC 锁定 + Phase 2 Implementation Spec
- `feedback_dev_report_truthfulness.md` — dev 报告必须基于实际命令输出
- `req_033_cycle_completion.md` — REQ-033 11 batches 收官,eval gate + badcase FSM
- `team_autonomous_loop_v3_1.md` — 三层服务生命周期防御
- `req_039_log_center_full_done.md` — Log Center 落库 + UI 替代 admin-console
