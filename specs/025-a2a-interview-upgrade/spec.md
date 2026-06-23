# Feature Specification: 025 — A2A Interview Upgrade (Planner + Interviewer)

**Feature Directory**: `specs/025-a2a-interview-upgrade/`

**Created**: 2026-06-23

**Status**: done

**Input**: User description: "引入 A2A 架构，升级模拟面试工作流。用户提交面试请求后，先启动 Interview Planner Agent（使用 Tavily websearch 搜索该岗位面试经验/公司风评等），生成面试计划，通过 A2A 发送给 Interviewer Agent，由 Interviewer 基于计划进行面试。"

---

## Objectives

将当前单 Agent 面试系统升级为**双 Agent A2A 协作架构**，分 5 个 Phase 逐步完成：

1. **Phase 1: Foundation** — Tavily 搜索工具集成 + 数据库 schema 扩展 + Planner 骨架
2. **Phase 2: Planner Logic** — 完整 Interview Planner，含 Tavily 搜索 + 计划生成
3. **Phase 3: A2A Integration** — LangGraph Supervisor 路由 + Command 跳转 + 持久化
4. **Phase 4: Frontend** — 面试计划在面试页和报告页展示
5. **Phase 5: Testing & Polish** — MockTavily + 单元/E2E 测试

---

## Phase 1 — Foundation

### 目标

搭建基础设施：Tavily 搜索工具、数据库字段扩展、Planner subgraph 骨架。

### User Story 1 — Tavily 搜索工具 (Priority: P1)

开发者配置 Tavily API Key，后端集成 Tavily Python SDK，创建一个可供 LangGraph Tool 调用的搜索工具。

**Acceptance Scenarios**:

1. **Given** `TAVILY_API_KEY=tvly-dev-...` 已配置在 `backend/.env`, **When** 调用 `TavilySearchTool(search_depth="advanced")` 进行搜索, **Then** 返回结构化搜索结果（标题/摘要/来源URL/相关性分数）
2. **Given** 搜索工具返回结果, **When** 结果格式化为文本摘要, **Then** 每条结果包含来源 URL，可在后续 Agent 提示词中引用
3. **Given** Tavily API 不可用（超时/4xx/5xx）, **When** 工具执行, **Then** 优雅降级返回空结果而非抛出异常

**Key Entities**:

- `TavilySearchTool` — LangGraph `@tool`，封装 Tavily SDK 调用
- `settings.TAVILY_API_KEY` — 配置项（backend/.env）

### User Story 2 — Interview Plan 数据模型 (Priority: P1)

数据库 `interview_sessions` 表增加 `interview_plan` 字段，定义面试计划的序列化结构。

**Acceptance Scenarios**:

1. **Given** 新增 migration, **When** 执行 `alembic upgrade head`, **Then** `interview_sessions` 表增加 `interview_plan JSONB` 和 `web_research JSONB` 字段，均可为 NULL
2. **Given** `InterviewPlan` Pydantic model 定义, **When** 序列化, **Then** 包含 `target_company`, `target_position`, `focus_areas`, `suggested_questions`, `web_research_summary`, `tips` 字段
3. **Given** 现有面试记录, **When** migration 回滚, **Then** `downgrade` 正确移除两字段，不影响已有数据

**Key Entities**:

- `InterviewPlan` (Pydantic model) — `schemas.py`
- `interview_sessions.interview_plan` (JSONB) — migration
- `interview_sessions.web_research` (JSONB) — migration

---

## Phase 2 — Planner Logic

### 目标

实现完整的 Interview Planner Agent：读取用户简历和 JD、通过 Tavily 搜索外部信息、生成结构化面试计划。

### User Story 3 — 读取上下文数据 (Priority: P1)

Planner 从系统中读取用户的简历数据和目标岗位信息，作为计划生成的基础输入。

**Acceptance Scenarios**:

1. **Given** 用户有已保存的简历（来自 `resume_branches` / `resume_blocks`）, **When** Planner 读取, **Then** 获取简历中的技能标签、工作经历、项目经验
2. **Given** 用户选择了目标岗位（来自 `jobs` 或 `interview_sessions.target_jd`）, **When** Planner 读取, **Then** 获取岗位名称、JD 描述、任职要求
3. **Given** 简历或岗位数据不完整, **When** Planner 执行, **Then** 标记缺失信息，继续执行而非中断

**Key Entities**:

- Existing `resumes` / `resume_blocks` / `resume_branches` modules
- Existing `jobs` module
- `interview_sessions.target_jd`

### User Story 4 — Tavily 搜索面试信息 (Priority: P1)

Planner 使用 Tavily 搜索目标岗位的面试经验、公司技术栈、常见面试题。

**Acceptance Scenarios**:

1. **Given** 目标公司已知（如 "字节跳动"）+ 岗位已知（如 "前端开发"）, **When** Planner 执行 Tavily 搜索, **Then** 按 3 个维度搜索：
   - 岗位面试经验与面经
   - 公司技术栈与工程文化
   - 该岗位常见面试问题
2. **Given** Tavily 搜索结果返回, **When** Planner 处理结果, **Then** 汇总为 `web_research_summary`（控制在 500 字以内）
3. **Given** 搜索命中多个来源, **When** 整合, **Then** 优先采用时间最近的来源，标注来源 URL

### User Story 5 — 生成面试计划 (Priority: P1)

Planner 综合简历、JD、Tavily 搜索结果，生成结构化面试计划。

**Acceptance Scenarios**:

1. **Given** 简历 + JD + Tavily 结果已就绪, **When** Planner 调用 LLM 生成计划, **Then** 输出 `InterviewPlan` 包含：考察重点（area + weight + reason）、建议问题方向、面试建议提示
2. **Given** 面试计划已生成, **When** 验证计划格式, **Then** `focus_areas` 至少包含 3 个考察维度，`suggested_questions` 至少包含 5 个问题方向
3. **Given** 计划生成完成, **When** 更新面试 session, **Then** `interview_plan` 和 `web_research` 字段被正确写入

---

## Phase 3 — A2A Integration

### 目标

将 Planner 接入现有面试流程，实现 Supervisor 路由 + A2A Command 跳转 + 计划持久化。

### User Story 6 — Supervisor Graph 路由 (Priority: P1)

修改 `interview/graph.py`，升级为 Supervisor + Subgraph 架构，先路由到 Planner 再跳转到 Interviewer。

**Acceptance Scenarios**:

1. **Given** 用户发起面试请求, **When** 启动 interview graph, **Then** **先路由到** `interview_planner` subgraph（状态: `planning`）
2. **Given** Planner subgraph 完成, **When** `planner_complete` 节点执行, **Then** 通过 `Command(goto="interviewer", update={interview_plan, web_research})` 跳转到 Interviewer
3. **Given** 计划已传递给 Interviewer, **When** Interviewer 开始面试, **Then** 首轮 system prompt 中注入 `interview_plan.focus_areas` 和 `interview_plan.suggested_questions` 作为面试上下文
4. **Given** 用户发起面试但无需外部搜索（已有缓存计划）, **When** 系统检查, **Then** 可跳过 Tavily 搜索直接使用已有计划

**Key Entities**:

- `interview/graph.py` — 升级为 Supervisor graph
- `interview/planner_graph.py` — 新增 Planner subgraph
- `interview/state.py` — 扩展 InterviewState，添加 `interview_plan` / `web_research` 字段
- `interview/prompts/planner.md` — Planner 系统提示词
- `interview/prompts/interviewer.md` — 更新 Interviewer 提示词，注入计划上下文

### User Story 7 — 计划持久化与 API 暴露 (Priority: P2)

面试计划在面试全流程中持久化，并通过 API 暴露给前端。

**Acceptance Scenarios**:

1. **Given** Planner 完成计划生成, **When** 写入 DB, **Then** `interview_sessions.interview_plan` 保存完整计划
2. **Given** 面试进行中, **When** 前端请求会话状态, **Then** API 返回 `interview_plan` 字段（非 NULL 时）
3. **Given** 面试完成生成报告, **When** 查看报告, **Then** `GET /api/v1/interviews/{id}/report` 返回 `plan` 字段，包含面试计划和 Tavily 搜索结果摘要

---

## Phase 4 — Frontend

### 目标

在面试页和报告页展示面试计划，让用户感知到 Planner 的价值。

### User Story 8 — 面试页展示计划 (Priority: P2)

面试开始前/开始时，在 InterviewLive 页面展示面试计划摘要。

**Acceptance Scenarios**:

1. **Given** 用户进入 InterviewLive 页且计划已生成, **When** 页面加载, **Then** 在面试区域上方展示「面试计划」折叠面板，包含：考察重点、难度预估、面试建议
2. **Given** 用户点击折叠面板展开, **When** 查看详情, **Then** 展示完整的 `focus_areas` 列表和 `suggested_questions` 预览
3. **Given** 用户进入面试环节, **When** 面试开始, **Then** 计划面板可折叠但持续可见

### User Story 9 — 报告页展示计划与搜索摘要 (Priority: P2)

面试完成后，在 InterviewReport 页面展示面试计划和 Tavily 搜索结果来源。

**Acceptance Scenarios**:

1. **Given** 报告页加载且 `interview_plan` 非空, **When** 渲染, **Then** 在「面试概览」区域展示计划内容
2. **Given** 计划包含 `web_research_summary`, **When** 展示, **Then** 以「信息来源」区块展示搜索摘要及来源 URL 链接
3. **Given** 用户未使用 Planner（旧面试记录）, **When** 报告页加载, **Then** 计划区域不展示，不报错

---

## Phase 5 — Testing & Polish

### 目标

Mock 外部依赖，覆盖单元/集成/E2E 测试，确保质量。

### User Story 10 — MockTavilyClient (Priority: P1)

创建 MockTavilyClient，类似现有 MockLLMClient 模式，用于确定性测试。

**Acceptance Scenarios**:

1. **Given** `TAVILY_MOCK_MODE=1` 环境变量设置, **When** Tavily tool 被调用, **Then** 返回 MockTavilyClient 而非真实客户端
2. **Given** MockTavilyClient 初始化时传入预定义场景文件, **When** 搜索, **Then** 返回场景文件中定义的预设结果
3. **Given** MockTavilyClient 使用中, **When** 搜索词无对应场景, **Then** 返回空结果而非异常

**Key Entities**:

- `backend/app/agents/tools/tavily_client_mock.py` — MockTavilyClient
- `tests/e2e/round-2/fixtures/tavily-scenarios/active.json` — 场景文件

### User Story 11 — 单元测试 + 集成测试 (Priority: P1)

覆盖 Planner 核心路径和 A2A 路由逻辑。

**Acceptance Scenarios**:

1. **Given** Planner 收到简历 + JD, **When** 生成计划, **Then** 计划包含所有必需字段（验证 serialization）
2. **Given** Supervisor graph 启动, **When** 完成 plan → interviewer 路由, **Then** Interviewer 收到正确的 `interview_plan` 状态
3. **Given** Tavily API 降级场景, **When** Planner 执行, **Then** 无搜索结果时仍能生成基础计划（仅基于简历 + JD）
4. **Given** 简历缺失场景, **When** Planner 执行, **Then** 仅基于 JD + Tavily 结果生成计划，不崩溃

### User Story 12 — E2E 测试 (Priority: P2)

端到端验证 Planner → Interviewer 全流程。

**Acceptance Scenarios**:

1. **Given** 用户登录且选择岗位, **When** 发起面试, **Then** 在 10s 内看到面试计划展示（非空 `focus_areas`）
2. **Given** 面试计划已展示, **When** 用户开始面试, **Then** Interviewer 的问题与计划中的 `focus_areas` 相关
3. **Given** 面试完成, **When** 查看报告, **Then** 报告中包含计划内容和搜索来源

---

## Key Entities

```python
class InterviewPlan(BaseModel):
    target_company: str = ""
    target_position: str = ""
    job_requirements: list[str] = []
    tech_stack: list[str] = []
    interview_difficulty: str = "medium"  # easy / medium / hard
    focus_areas: list[FocusArea] = []      # at least 3
    suggested_questions: list[str] = []    # at least 5
    web_research_summary: str = ""
    tips: list[str] = []

class FocusArea(BaseModel):
    area: str           # e.g. "技术深度 — React 底层原理"
    weight: float       # 0.0 ~ 1.0, sum of all ≈ 1.0
    reason: str         # 为什么重点考察这个

class WebResearch(BaseModel):
    interview_experience: list[SearchResult] = []
    company_tech_stack: list[SearchResult] = []
    common_questions: list[SearchResult] = []

class SearchResult(BaseModel):
    title: str
    content: str
    url: str
```

## A2A 通信协议（技术方案）

使用 LangGraph 内置的 `Command(goto=...)` 机制实现 Agent-to-Agent 跳转：

```python
# interview/graph.py — Supervisor
builder = StateGraph(InterviewState)
builder.add_node("interview_planner", planner_subgraph)
builder.add_node("interviewer", interviewer_subgraph)
builder.add_edge("__start__", "interview_planner")
builder.add_conditional_edges("interview_planner", planner_complete, ["interviewer"])

def planner_complete(state: InterviewState) -> Command:
    return Command(
        goto="interviewer",
        update={
            "interview_plan": state["interview_plan"],
            "web_research": state["web_research"],
        }
    )
```

## Assumptions

- Tavily API Key 有效且有足够配额（开发 key 月调用有限）
- 现有 interview/state.py 的 InterviewState 可扩展（非冻结 TypedDict）
- Interviewer 的 prompts 可通过 system prompt 注入计划上下文（不需要改 graph 结构）
- 用户不一定有简历或 JD 数据，Planner 需处理缺失场景

## Success Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| SC-01 | Tavily 搜索工具可独立调用并返回结构化结果 | `pytest tests/.../test_tavily_tool.py` |
| SC-02 | Planner 能在 15s 内完成搜索+计划生成（含网络） | 集成测试带 MockTavily 模拟耗时 |
| SC-03 | A2A 路由 Planner → Interviewer 状态传递正确 | `interview_plan` 字段非空传入 Interviewer |
| SC-04 | 面试计划在面试页和报告页均可见 | E2E 测试 `tests/e2e/interview-a2a-planner.spec.ts` |
| SC-05 | 无 Tavily 结果时系统仍能完成面试 | Planner 降级测试 |
| SC-06 | 已有面试记录向后兼容（plan 字段 NULL） | 旧记录查看报告页不报错 |
