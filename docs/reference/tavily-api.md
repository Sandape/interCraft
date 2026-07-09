---
name: a2a_interview_spec
description: A2A 智能面试升级 spec 已落地到 SPEC.md，提案中 Planner + Interviewer 双 Agent 通过 LangGraph Command 实现 A2A 通信，Tavily websearch 集成到 Planner 中。
metadata:
  type: project
---
# A2A 智能面试升级

**Spec 文件**: `D:\Project\eGGG\SPEC.md`

核心设计：
- Planner Agent 通过 Tavily 搜索面试经验 / 公司信息，产出面试计划
- 通过 LangGraph `Command(goto=...)` 实现 A2A 跳转到 Interviewer
- Interviewer 基于计划进行面试
- 面试计划持久化到 DB，面试报告中可查看

A2A 通信方案选择：LangGraph Supervisor + Subgraph 模式（项目已有 LangGraph），而非 Google A2A v1.0 协议。

**Why:** 项目已深度使用 LangGraph，引入外部 A2A 协议增加复杂度而无实质收益。LangGraph 的 `Command(goto=...)` 已能实现清晰的 Agent-to-Agent 跳转。

**How to apply:** 后续实现时，Planner 作为 subgraph 加入 interview graph，通过 `Command` 实现状态传递和路由跳转。MockTavilyClient 类似 MockLLMClient 模式用于测试。
