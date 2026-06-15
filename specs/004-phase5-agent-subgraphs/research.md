# Phase 5 Research: P1 Agent 子图扩展

**Status**: Phase 0 output · **Date**: 2026-06-15 · **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

> 本文档记录 Phase 5 中需要研究决议的不确定点。Phase 5 范围已在 spec.md 和 Clarifications(2026-06-15,2 项决议)中收敛。由于 Phase 5 完全基于 Phase 1-4 已确立的技术栈和基础设施,无新型技术选型或架构变更,本 research 篇幅较短。

## 0. 上下文

Phase 5 目标(参见 spec):「在 Phase 4 Interview Agent + LangGraph 基础设施基础上,实现剩余 4 个 Agent 子图:简历优化 Agent (M16)、错题强化 Agent (M17)、能力诊断 Agent (M18 完整版)、通用辅导 Agent (M19)」。

Phase 4 已落地 M14 LangGraph 基础设施(统一 LLM 客户端/checkpointer/WS 事件协议)+ M15 Interview 子图 + M22 审计初版。Phase 5 在其上叠加 M16-M19 四个子图,无新增技术栈、无新 DB 表。

## 1. 从 Phase 1-4 继承的决策

| # | 决策 | 来源 | Phase 5 影响 |
|---|---|---|---|
| D-1 | 后端 = FastAPI + SQLAlchemy 2.0 + asyncpg | Phase 1 research D-1 | 4 个子图复用同一框架 |
| D-2 | DB = PostgreSQL 15(在线托管) | Phase 1 research D-2 | langgraph checkpointer 延续 |
| D-3 | 队列 = ARQ + Redis 7 | Phase 1 research D-3/D-4 | M18 异步触发 + M16 超时巡检 |
| D-4 | 鉴权 = JWT(access 15min + refresh 7d) + RLS | Phase 1 research D-6/D-10 | 无需变更 |
| D-5 | AI 编排 = LangGraph | Phase 4 research R-1 | 4 个子图均使用同一框架 |
| D-6 | LLM = DeepSeek V4 Pro, OpenAI 协议 | 用户决议(2026-06-13) | 统一模型,4 子图共享 |
| D-7 | 统一 LLM 客户端(M14) | Phase 4 research R-2 | 全部复用 |
| D-8 | WS 事件协议 | Phase 4 research R-3 | 复用 + M16 interrupt 事件扩展 |
| D-9 | PostgreSQL checkpointer(langgraph schema) | Phase 4 research R-4 | 复用 |
| D-10 | token 预扣策略 | Phase 4 research R-6 | 复用,4 子图共享配额 |

## 2. Phase 5 研究决议

### R-1: M16 Resume Optimize — interrupt 机制与锁整合

**问题**:M16 是唯一启用 `interrupt_after` 的子图,需要在 LangGraph interrupt 生命周期内与 M12 锁服务协调。

**研究范围**:
- LangGraph interrupt 生命周期:节点执行 → `interrupt_after` 暂停 → 等待外部输入 → 节点恢复 → 继续
- M12 锁服务: `acquire_lock(resume_branch:{branch_id})` → 中断期间保持锁 → confirm 后释放 / 超时自动释放
- WS `interrupt` 事件:需在 Phase 4 WS 协议中新增事件类型

**评估结论**:选 **LangGraph `interrupt_after` + M12 锁 + 独立 WS 事件类型**:
- `interrupt_after` 使用 LangGraph 原生机制,checkpoint 在 interrupt 点自动保存
- start 时 acquire lock,confirm(discard)或超时时 release lock
- WS `interrupt` 事件作为独立事件类型,payload 格式自定义(不与 node.completed 混淆)

**产出**:`backend/app/agents/graphs/resume_optimize.py` + `backend/app/api/v1/agents_resume_optimize.py`

### R-2: M18 Ability Diagnose — 异步子图与 ARQ 整合

**问题**:M18 由 ARQ 任务触发运行完整的 LangGraph 子图,需确定 ARQ ↔ LangGraph 的集成模式。

**研究范围**:
- ARQ worker 中运行 LangGraph 子图:在 ARQ task 中创建 graph + 复用 M14 llm_client
- 子图间数据传递:ARQ job 只传 session_id,子图通过 query_* 工具从业务表加载(A5 决议)
- 完成通知:子图完成后通过 WS 推送 `agent.final` 事件

**评估结论**:选 **ARQ task 内创建 graph + 工具加载数据 + WS 推送完成事件**:
- ARQ task 内 `graph = create_ability_diagnose_graph()` → `graph.ainvoke(input, config=RunnableConfig(...))`
- 工具函数已封装在 `backend/app/agents/tools/` 中
- 完成通知通过 M14 WS 基础设施(复用 Phase 4 agent.final 事件模式)

**产出**:`backend/app/agents/graphs/ability_diagnose.py` + `backend/app/workers/tasks/diagnose_after_interview.py`

### R-3: M19 General Coach — 意图分类阈值与 few-shot 设计

**问题**:M19 的 `intent` 节点使用 LLM 分类 + few-shot 示例(Clarification Q2 决议),需确定分类方案细节。

**研究范围**:
- 支持意图: `resume_optimize` / `interview_practice` / `career_advice` / `chitchat`
- few-shot 示例:每个意图 2-3 个预配示例问题,prompt 中给出
- 阈值: `confidence > 0.7` → 走对应路由;否则 → 通用回答+引导
- 路由策略:LLM 意图判定 → confidence > 0.7 且匹配已有 Agent → 引导跳转;否则 → 通用回答

**评估结论**:选 **LLM 意图分类 + few-shot 示例 + 0.7 阈值**:
- Prompt 中预置每个意图 2-3 个示例(中英文混合,覆盖常见表达)
- 示例模板: "用户输入: 「{示例问题}」 → 意图: {意图}, 置信度: 0.9X"
- 阈值 0.7 在准确率和召回率之间取得合理平衡,MVP 后可根据线上数据调整

**产出**:`backend/app/agents/graphs/general_coach.py` + `backend/app/agents/prompts/general_coach/intent.md`

## 3. 不需要研究的默认选择

| 项 | 默认选择 | 理由 |
|---|---|---|
| M16 diff 格式 | RFC 6902 JSON Patch | 复用 Phase 1 版本系统 |
| M17 提示梯度内容 | LLM 基于 question.hint + ref answer 生成 | Phase 5 CLAR Q1 对齐 |
| M17 答对判定 | 0-10 分制,阈值 ≥ 8 | Phase 5 CLAR Q2 决议 |
| M19 意图分类 | 纯 LLM + few-shot,无关键词层 | Phase 5 CLAR Q2 决议 |
| 4 子图 prompts | 复用 Phase 4 `.md` 模板模式 | 沿用 Phase 4 模式 |
| 前端 mock 回退 | `VITE_USE_MOCK=true` | 沿用 Phase 1 模式 |
| 超时巡检 | ARQ cron(复用 Phase 2/3 模式) | 沿用 |
