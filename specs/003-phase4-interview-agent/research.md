# Phase 4 Research: Interview Agent 全流程跑通

**Status**: Phase 0 output · **Date**: 2026-06-13 · **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

> 本文档记录 Phase 4 中需要研究决议的不确定点。Phase 4 范围已在 spec.md 和 Clarifications(2026-06-13,10 项决议)中收敛,本 research 聚焦于 LangGraph 子图设计/LLM 客户端架构/WS 事件协议/checkpoint 恢复策略/双源对账方案。

## 0. 上下文

Phase 4 目标(参见 spec):「全流程面试(start → 5 轮对话 → 生成报告),WS 流式 token,双源持久化 + 对账」。Phase 1/2/3 基础设施已就位:账号/RLS/版本、interview_sessions 只读表、锁/WS 控制面/Outbox。

Phase 4 新增后端模块:M14(LangGraph 基础设施)、M15(Interview 子图)、M22(审计可观测初版);前端 3 页面(InterviewList/InterviewLive/InterviewReport)从 mock 切真实 API。

**Phase 4 不涉及**:语音模式/M16-M19 agent 子图/ability_diagnose 完整实现/M20-M21 生命周期/langSmith 启用。

## 1. 已知决策(从 spec + Phase 1/2/3 继承)

| # | 决策 | 来源 | Phase 4 是否需要进一步研究 |
|---|---|---|---|
| D-1 | 后端 = FastAPI + SQLAlchemy 2.0 + asyncpg | Phase 1 research D-1 | 否 |
| D-2 | DB = PostgreSQL 15(在线托管) | Phase 1 research D-2 | 否 |
| D-3 | 队列 = ARQ + Redis 7 | Phase 1 research D-3/D-4 | 否 |
| D-4 | 鉴权 = JWT(access 15min + refresh 7d) + RLS | Phase 1 research D-6/D-10 | 否 |
| D-5 | AI 编排 = LangGraph | spec §6 A6 | **是**:子图结构、checkpointer 选型 |
| D-6 | LLM = DeepSeek V4 Pro(`deepseek-chat`),OpenAI 协议 | 用户决议(2026-06-13) | 否:统一模型,不分层 |
| D-7 | token 配额 = ARQ cron 每月 1 日重置 | 澄清 Q1(2026-06-13) | **是**:预扣策略、estimate 算法 |
| D-8 | 面试无悲观锁 | spec §6 A21 | 否 |
| D-9 | WS 单连接复用 | 澄清 Q9(2026-06-13) | **是**:面试事件协议 |
| D-10 | LangGraph checkpointer = PostgreSQL | spec assumption | **是**:schema 设计、恢复策略 |
| D-11 | 前端 M23 Phase 3 = 3 页面切真实 API | spec FR-040~FR-044 | 否 |
| D-12 | ability_diagnose = 异步 ARQ 触发(Phase 4 基础) | spec FR-024 | **是**:触发阈值与数据格式 |

## 2. Phase 4 需要研究的不确定点

### R-1: LangGraph Interview 子图结构设计

**问题**:spec FR-001 定义节点为 intake → question_gen ↔ score(×5) → report,但未详细定义 GraphState schema、节点间数据传递、条件路由、checkpoint 粒度。

**研究范围**:
- GraphState TypedDict 字段设计:messages(对话历史)、current_question(当前题号 1-5)、questions(已生成问题列表)、scores(评分列表)、resume_context(简历内容)、position/company/difficulty
- 条件路由:score 节点后判断 `current_question < 5` → question_gen,否则 → report
- checkpoint 粒度:每个节点执行后自动保存(MemorySaver 开发,PostgresSaver 生产)
- 节点超时:单节点 LLM 调用超时 30s,节点级别超时 60s
- `interrupt` 机制:Phase 4 不使用(Phase 5 M16 Resume Optimize 启用)

**评估结论**:选 **单 GraphState + 条件边循环 5 次**:
- GraphState 使用 TypedDict,所有节点共享,messages 用 `add_messages` reducer 追加
- 循环由 `score → question_gen` 条件边驱动,`question_gen → score` 正常边
- checkpoint 在每个 `node.completed` 后自动保存(stack=False 的 interrupt 节点不留)

**理由**:
- LangGraph 原生支持条件循环,无需外部循环控制器
- 单 state 简化序列化/反序列化,checkpoint 恢复从 state 重建上下文
- messages reducer 自动去重(按 message ID),防止重放时重复

**产出**:`backend/app/agents/interview/state.py`(InterviewGraphState) + `graph.py`(StateGraph 定义)

### R-2: 统一 LLM 客户端设计（DeepSeek V4 Pro + OpenAI 协议）

**问题**:spec FR-003 要求「统一 LLM 客户端集中处理模型调用:速率限制、自动重试、结构化日志、token 预扣」。2026-06-13 用户决议:使用 DeepSeek V4 Pro(`deepseek-chat`),OpenAI 兼容协议,所有节点统一模型,API key `sk-5053a1...`。

**研究范围**:
- OpenAI 兼容协议:`openai.AsyncOpenAI(base_url="https://api.deepseek.com/v1", api_key=...)`
- DeepSeek `deepseek-chat` 模型能力:支持流式(streaming)、JSON mode(function calling)、128K context
- 预扣算法:单模型定价统一 → 按节点类型估算 input/output token → `SELECT ... FOR UPDATE` 原子扣减
- 重试策略:指数退避 1s/2s/4s,最多 3 次,仅对 transient error(rate_limit/overloaded/server_error)重试
- 结构化日志:每次调用记录 request_id/model/prompt_tokens/completion_tokens/duration_ms/retry_count
- DeepSeek 无 prompt caching → 去掉 cache_hit 字段

**评估结论**:选 **单例 OpenAI client + 单模型 `deepseek-chat` + 预扣原子化**:
- 使用 `openai.AsyncOpenAI` SDK(base_url 指向 DeepSeek,api_key 从 env 读)
- 所有 4 种节点(intake/question_gen/score/report)统一用 `deepseek-chat`,无需模型分层
- 预扣在 `invoke` 入口执行:读 quota → 预扣 → 调 DeepSeek → 实扣(按实际 token 数调整)
- 流式输出通过 `stream=True` + async iterator 逐 token 推送 WS

**理由**:
- DeepSeek V4 Pro 能力足以覆盖全部 4 种节点(intake→report),质量一致性好
- OpenAI 协议通用,未来切换模型(如 Qwen/GPT)只需改 env
- 单模型降低客户端复杂度,无需 model dispatch 逻辑
- DeepSeek 性价比优于 Claude Opus,单一模型成本可控(一场面试 ≈ 27,700 tokens,约 ¥0.05)

**被拒方案**:
- Anthropic SDK + Claude 分层:用户已提供 DeepSeek key,直接使用
- 多模型分层(原 Opus/Sonnet/Haiku 方案):DeepSeek V4 Pro 统一覆盖不需要

**产出**:`backend/app/agents/llm_client.py`(LLMClient 类 + invoke 方法,基于 openai SDK)

### R-3: WS 面试事件协议设计

**问题**:spec FR-016 定义了 4 种 WS 事件类型(node.started / token.delta / node.completed / error),需确定事件 JSON schema、序列化格式、`last_seen_checkpoint_id` 携带方式。

**研究范围**:
- 事件 JSON schema:每个事件含 `event_id`(uuidv7) + `session_id` + `timestamp` + `node_name` + `payload`
- `token.delta` 流式:content 片段 ≤ 10 chars/event,前端累积渲染
- 断线重连:client 发送 `{"type": "reconnect", "last_seen_checkpoint_id": "..."}`,server 从该 checkpoint 恢复,跳过已完成的节点,从下一节点开始推送
- 事件顺序保证:server 侧 FIFO 队列,client 侧按 `event_id` 去重
- heartbeat:复用 Phase 3 锁心跳通道(同一 WS 连接)

**评估结论**:选 **JSON 事件 + checkpoint_id 显式传递 + server 端 checkpoint 恢复**:
- 每个事件为单行 JSON(`\n` 分隔),无嵌套流
- `token.delta` 的 content 为 1-10 字符片段,前端 `useReducer` 累积
- 重连时 client 发送 `reconnect` 消息携带 `last_seen_checkpoint_id`,server 调用 `graph.aget_state(config)` 恢复,从 `state.next_node` 继续

**理由**:
- JSON 单行分割简单可调试,Playwright E2E 可直接解析
- server 端恢复避免 client 理解 graph 状态机
- 小片段推送保证流式体验,10 字/event 产生流畅的逐字动画

**产出**:`specs/003-phase4-interview-agent/contracts/ws-events.md`

### R-4: PostgreSQL Checkpointer Schema 与恢复策略

**问题**:spec FR-002 要求「LangGraph checkpointer 持久化到 PostgreSQL」,需确定表结构、索引、清理策略、与业务表的 schema 隔离。

**研究范围**:
- langgraph-checkpoint-postgres 库:表结构由库定义(`checkpoints` / `checkpoint_writes` / `checkpoint_blobs`),schema 默认为 `public`,建议隔离为 `langgraph` schema
- checkpoint 恢复:调用 `graph.aget_state(config)` → 获取 `state.values` + `state.next` → 从 `next` 节点继续
- checkpoint 清理:保留 90 天(TTL),ARQ 定时清理过期 checkpoint
- 与 `ai_messages` 的双源关系:checkpoints 存 state(内容快照),ai_messages 存 LLM 调用元数据(审计),互相独立

**评估结论**:选 **langgraph schema 隔离 + 90 天 TTL + ARQ 清理 cron**:
- checkpoint 表创建在 `langgraph` schema,与 `public` 业务表隔离
- 恢复流程:`GET /api/v1/interview-sessions/{id}/resume` → 查 session.thread_id + checkpoint_ns → `graph.aget_state(config)` → 返回 `{"next_node": "...", "current_question": N}`
- 清理:`DELETE FROM langgraph.checkpoints WHERE created_at < NOW() - INTERVAL '90 days'`,每周执行

**理由**:
- schema 隔离避免 checkpoint 表与业务表命名冲突
- 90 天覆盖面试恢复需求(24h 过期) + 数据分析窗口
- ARQ 清理避免 checkpoint 无限膨胀

**产出**:`backend/migrations/versions/0004_phase4_agent.py`(checkpointer schema 初始化)

### R-5: 双源对账策略

**问题**:spec FR-031 要求「每日对账比对 ai_messages ↔ checkpoints」,需确定对账粒度、不一致处理、性能考量。

**研究范围**:
- 对账粒度:按 `thread_id` 维度,比对每条 thread 的 ai_messages 记录数与 checkpoints 节点数是否匹配
- 对账规则:
  - 每个 checkpoint(对应一个已完成节点)应有 ≥1 条 ai_message(该节点的 LLM 调用记录)
  - ai_message 中 `checkpoint_id` 对应 checkpoints 中一条记录
  - 孤立的 ai_messages(checkpoint 缺失):标记 `ORPHAN_MESSAGE`
  - 孤立的 checkpoints(ai_message 缺失):标记 `MISSING_AUDIT`
- 对账时间窗口:每天 03:00 UTC 执行,扫描前一天 00:00-23:59 的 thread
- 不一致处理:写入 audit_logs,Prometheus counter `reconcile_mismatch_total` +1,不自动修复

**评估结论**:选 **thread 级对账 + 仅告警不自动修复**:
- SQL query 比对 `langgraph.checkpoints` 与 `public.ai_messages`,LEFT JOIN 找孤儿
- 不一致率 <0.1% 目标(SC-006),超过阈值发 critical 告警
- 不自动修复:数据不一致原因需人工排查(checkpoint 写入失败/ai_message 丢失/LangGraph bug)

**理由**:
- 自动修复风险高:错误原因不确定时写回数据可能造成二次损坏
- 告警即可:checkpoints 是权威源,读取以 checkpoints 为准,ai_messages 是审计辅助
- 每日全量扫描在 ≤1000 用户规模下毫秒级完成

**产出**:`backend/app/audit/reconcile.py` + `backend/app/workers/tasks/daily_reconcile.py`

### R-6: Token 预扣估算策略(DeepSeek 单模型)

**问题**:spec FR-004 要求「节点执行前预扣 token 配额」,需确定如何估算每个节点的 token 消费量。

**研究范围**:
- DeepSeek V4 Pro 定价:input ¥0.001/1K tokens,output ¥0.002/1K tokens(约)
- 按节点类型固定估算:
  - intake:≈500 input + 200 output = 700 tokens
  - question_gen:≈2000 input + 500 output = 2500 tokens
  - score:≈1500 input + 300 output = 1800 tokens
  - report:≈4000 input + 1500 output = 5500 tokens
- 一场面试总计:700 + 5×2500 + 5×1800 + 5500 ≈ 27,700 tokens(估算上限 35,000)
- 预扣使用上限估算,实际调用后按真实 token 数调整
- QuotaExceededError:当 `monthly_token_used + estimate > monthly_token_quota` 时拒绝

**评估结论**:选 **固定估算表 + 实扣调整(单模型 deepseek-chat)**:
- 每节点预扣前查表得 estimate,原子 `SELECT ... FOR UPDATE` 扣减
- LLM 调用完成后按 response.usage 实扣,差额调整回 `monthly_token_used`
- 预扣超限时抛 QuotaExceededError,不消耗任何配额

**理由**:
- 固定估算简单可靠,Phase 4 开发期用户少,估算偏差容忍度高
- 实扣调整保证公平:用户不为高估付费,也不因低估占便宜
- Phase 6 可升级为动态估算(按用户历史平均)

**产出**:`backend/app/agents/llm_client.py`(estimate 方法 + 原子预扣)

## 3. 不需要研究的默认选择

| 项 | 默认选择 | 理由 |
|---|---|---|
| Prompt 模板格式 | Markdown(.md)文件,变量 `{variable}` 占位 | 沿用 LangChain PromptTemplate 惯例 |
| InterviewSession status 枚举 | pending / in_progress / completed / expired(FR-022) | 与 Phase 2 interview-sessions.md 契约对齐 |
| LangGraph 版本 | >=0.2(LangGraph Cloud 已 stable) | 避免 0.1.x breaking changes |
| WS 认证方式 | JWT token 通过 query param(`?token=...`) | 沿用 Phase 3 WS 认证(FR-060) |
| 对账时间 | 每日 03:00 UTC(低峰期) | 沿用 Phase 2 cron 约定(00:00 配额重置) |
