# Research: WeChat Conversational Agent

**Feature**: REQ-054 | **Date**: 2026-07-09

## 1. Inbound Reply Entry — Replace PersonalAgentReply

**Decision**: 以 `ConversationOrchestrator` 替换/包装现有 `PersonalAgentReply`；`ilink_pool` → `AgentService.process_inbound_reply` 入口保持不变。

**Rationale**:
- 052 已验证：thinking 占位 + 后台 task + outbox 发送；054 只需换「生成回复」实现
- 保留 `PersonalAgentReply` 作为 fallback 薄包装（orchestrator 失败时的最后兜底文案）可降低回滚成本
- 不改动 iLink 长轮询与去重逻辑，降低回归面

**Alternatives considered**:
- 在 `message_handler` 内直接挂意图逻辑：与 052 分层冲突，难测
- 新建独立 ARQ worker 消费入站：增加延迟与运维复杂度，SC-004 更难达标

## 2. Tool Invocation — In-Process Services vs HTTP

**Decision**: 工具层**进程内调用** `JobService` / `InterviewSessionService` / Ability Profile service（共享 `AsyncSession` + 用户 RLS 上下文）。

**Rationale**:
- 避免服务自 HTTP 调用的鉴权/超时/循环依赖问题
- 与现有模块边界一致：API 层薄、Service 可复用
- 事务边界清晰：确认后单次 commit

**Alternatives considered**:
- 经 `httpx` 调本机 `/api/v1/*`：需伪造 JWT，测试脆弱
- 直接写 Repository：绕过状态机校验（`JOB_TRANSITIONS`、`interview_time` 必填），危险

## 3. LangGraph WeChat Interview Adapter

**Decision**: **不**做无状态 per-node 调用；复用现有 `InterviewGraph.submit_answer` + `resume_from_checkpoint` / `get_current_state`，由微信适配层把「用户文字作答」映射为 `submit_answer`，把 graph 输出格式化为 ≤500 字微信文案。

**Rationale**:
- 代码已用 Postgres checkpointer；`thread_id = str(session.id)`；Web/微信共享同一 checkpoint → 天然支持澄清结论「跨渠道续面」
- `submit_answer` 内部已是 `ainvoke`（非 token 流），与微信异步模型匹配
- `generate_plan` 的直接节点调用仅作规划阶段参考，面试主循环应走完整图以保持评分/报告一致性（spec：不因渠道降质）

**Alternatives considered**:
- 逐节点无状态调用 `question_gen` / `score_llm`：需重造 interrupt/状态同步，易与 Web 分叉
- 另建「微信专用轻量图」：违反公平性假设，双倍维护成本

**Implementation notes**:
- 开场：`InterviewSessionService` 创建 + start（或检测互斥）
- 每轮：用户文本 → `submit_answer` → 格式化评分+下一题 → enqueue 出站
- 暂停：仅更新 `ConversationContext.state`，session 保持 `in_progress`
- 继续：读 checkpoint / resume API 等价逻辑，发当前题或下一题
- 结束：≥3 轮生成部分报告；&lt;3 轮标 `expired`（若写入路径缺失，本特性补齐 service 方法）

## 4. ConversationContext Storage

**Decision**: Redis JSON，key = `wechat:conversation:{user_id}`，TTL = 24h，每次交互 `EXPIRE` 刷新。

**Rationale**:
- Spec 明确：纯运行时态，丢失可重建
- 与 052 已用 Redis（dedup / send_queue）一致
- 避免为确认态建 PG 表

**Schema（逻辑）**:
```json
{
  "state": "idle|awaiting_confirmation|in_interview",
  "pending_action": {"type": "...", "params": {}},
  "queued_intents": [],
  "interview_session_id": null,
  "interview_round": null,
  "unknown_streak": 0,
  "last_active_at": "ISO-8601"
}
```

**Alternatives considered**:
- PG 表：过重，且与「丢失可重建」矛盾
- 仅靠 `agent_messages` 历史推断状态：确认态不可靠，难测

**Dev note**: 若本地 Redis 只读（052 QR 曾遇此问题），context_store 需有明确失败降级：拒绝写操作并提示稍后重试（不可静默丢确认态）。

## 5. Intent Parsing Strategy

**Decision**: `LLMClient.invoke` + **JSON schema / 结构化输出**（intent、entities、confidence、alternatives）；confidence &lt; 0.6 → 列出 2–3 候选；LLM 失败 → 重试 1 次 → 友好降级（澄清 B）。

**Rationale**:
- 与面试/个人回复共用治理栈（配额、审计、指标）
- 禁止关键词写路径，避免「腾讯不行了」误推进 failed
- Prompt 内嵌 053 状态中文标签与口语变体（FR-002）

**Alternatives considered**:
- 纯规则/关键词：准确率无法达 SC-002 90%
- 独立 LangGraph 意图图：对单轮分类过重

**Token**: 日均 100 轮 × 1500 tok ≈ 4.5M/月增量 → 实现前需上调用户/系统配额或单独 `node_name=intent_parse` 计量告警。

## 6. Relative Time Parsing

**Decision**: 固定 `zoneinfo.ZoneInfo("Asia/Shanghai")`；用显式规则 +（可选）LLM 辅助抽取后规则归一；确认卡展示绝对本地时间。

**Rationale**:
- 澄清结论 B：忽略账号时区
- 规则解析「明天/下周一/下午2点」可单测，减少 LLM 幻觉日期

**Alternatives considered**:
- 完全交给 LLM：难保证 SC 可测性
- dateparser 默认本地 TZ：CI/服务器 TZ 不一致

## 7. Job Fuzzy Matching

**Decision**: 内存过滤用户活跃 jobs（`deleted_at IS NULL`），优先级：公司+岗位精确 → 公司包含 → 岗位包含 → `updated_at` 最近；多候选最多 5 条。

**Rationale**:
- 用户岗位量通常很小（&lt;50），无需搜索引擎
- 与 FR-007 一致，易写单测覆盖 SC-006

**Alternatives considered**:
- pg_trgm：过早优化
- 仅最近一个岗位：多岗位场景误伤高

## 8. Per-User Inbound Serialization

**Decision**: 同 `user_id` 入站处理串行（`asyncio.Lock` per user 或 Redis lock）；完成当前 `handle()` 再处理下一条。

**Rationale**:
- Spec Edge Case：不丢消息、不并行乱序确认
- 面试双通道作答也需串行评分

**Alternatives considered**:
- 完全并行：确认态竞态、重复写
- 全局单队列：吞吐差

## 9. Interview Mutex & Cross-Channel Resume

**Decision**: 查询用户是否存在 `status IN ('pending','in_progress')` 的 session；有则拒绝 `start_interview`；`continue_interview` 绑定该 session 并切 `ConversationContext` 为 `in_interview`。

**Rationale**:
- 澄清 A/A：全局互斥 + 跨渠道续面
- Session/checkpoint 本就渠道无关

**Gap to close in implementation**:
- `expired` 状态：resume 已检查，但写入路径可能缺失 → 054 在 `end_interview`（&lt;3 轮）与 24h 过期路径中补齐
- `InterviewStatus` 枚举与 DB `in_progress` 不一致 → 以 DB/服务实际值为准，必要时修枚举（小清理，非阻塞）

## 10. Observability & Privacy

**Decision**: 指标按 FR-019；日志按 FR-020（intent/参数摘要/latency，**不记原文**）。

**Rationale**:
- 宪法原则 V + 微信隐私敏感
- 复用 `LLMClient` 已有 token/延迟指标，另加 conversation_* 系列

## 11. Frontend Scope

**Decision**: 054 **不新增**前端对话 UI；E2E 通过 mock/注入入站 API 或 CLI `simulate-chat` + DB 断言。

**Rationale**:
- 用户交互面在微信；Web 仅查看结果
- 052 AgentSettings 绑定页若未挂路由，作为 052 遗留项，不阻塞 054 后端（测试可用已绑定种子用户）

## Resolved NEEDS CLARIFICATION (from Assumptions)

| Assumption | Resolution |
|------------|------------|
| LangGraph per-node 无状态调用？ | **否** — 复用 `submit_answer` + checkpoint |
| 对话摘要策略？ | v1：意图解析只用短窗口（最近 N 条 + ConversationContext）；面试轮次不把全文塞进意图 prompt |
| Token 配额？ | 实现前扩容/告警；`node_name=intent_parse` 单独计量 |
