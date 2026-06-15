# Feature Specification: Phase 4 — Interview Agent 全流程跑通

**Feature Branch**: `003-phase4-interview-agent`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "Phase 4 — Interview Agent 跑通（超核心）。全流程面试(start → 5 轮对话 → 生成报告),WS 流式 token,双源持久化 + 对账。产品核心 AI 能力首次完整展示。"

## Clarifications

### Session 2026-06-13

- Q: LLM 模型族选择(原 Claude Opus/Sonnet/Haiku 分层)? → A: 全部使用 DeepSeek V4 Pro(`deepseek-chat`),OpenAI 兼容协议;所有节点统一模型,不分层;API key `sk-5053a1...` 已在 `backend/.env` 配置
- Q: token 配额默认值? → A: 500K/月(约 18 场面试)
- Q: API key 配置策略? → A: 用户提供 DeepSeek key,使用 OpenAI 协议;Anthropic 依赖被替换为 `openai>=1.0` SDK

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 启动并完成一场 AI 模拟面试 (Priority: P1)

用户选择目标岗位,启动一场 5 轮文字面试。AI 面试官逐轮提问,用户作答后即时评分,5 轮结束后生成完整报告。整个过程中用户通过 WS 实时看到 AI 逐字输出(token 流式)。

**Why this priority**: 这是产品「核心 AI 能力首次完整展示」,也是所有下游能力(能力画像更新、错题自动沉淀)的数据来源。没有它,Phase 5 的 Agent 扩展无法启动。

**Independent Test**: 从 InterviewList 页点击「开始模拟面试」→ 完成 5 轮对话 → 看到报告页 → 报告数据持久化(刷新后仍在)。

**Acceptance Scenarios**:

1. **Given** 用户已登录且在 InterviewList 页, **When** 选择目标岗位并点击「开始模拟面试」, **Then** 系统创建 `interview_sessions` 记录、初始化 LangGraph thread、推送 WS `node.started(intake)` 事件,前端跳转到 InterviewLive 页
2. **Given** 面试正在进行第 3 轮,AI 正在输出问题文本, **When** 用户观察屏幕, **Then** 前端实时渲染流式 `token.delta` 事件,文字逐字出现,延迟 ≤ 200ms
3. **Given** 用户完成第 3 轮回答并提交, **When** 评分节点执行, **Then** 系统在 1.5s 内返回评分结果,推送 `node.completed(question_3)` 后立即推送 `node.started(question_4)`
4. **Given** 用户完成全部 5 轮, **When** 报告节点(report)执行完毕, **Then** 系统同步写入 `interview_reports` 表、异步触发 ability_diagnose 子图,前端跳转到 InterviewReport 页展示完整报告(总分/每题得分/维度得分/优势/改进建议)
5. **Given** 报告页已展示, **When** 异步 ability_diagnose 完成, **Then** 系统推送 WS `ability.updated` 事件,报告页显示「能力画像已更新」提示

---

### User Story 2 — 面试中断与恢复 (Priority: P1)

用户在面试过程中意外断线(关闭 Tab / 网络断开 / WS 断连),重新进入后可从中断点继续面试,不会丢失已完成的轮次,也不会收到重复的 token。

**Why this priority**: 面试时长 25 分钟,断线是常见场景。如果没有可靠的断线恢复,用户体验极差,首场完成率会很低。

**Independent Test**: 在第 3 轮回答后关闭 Tab → 重新打开 InterviewList → 看到「进行中」标记 → 点击继续 → 从第 4 轮开始,前 3 轮内容完整保留。

**Acceptance Scenarios**:

1. **Given** 用户在第 3 轮回答后关闭 Tab, **When** 重新进入 InterviewList 页, **Then** 看到该面试标记为「进行中」,可点击「继续面试」
2. **Given** 用户点击「继续面试」, **When** 前端重连 WS 并携带 `last_seen_checkpoint_id`, **Then** 服务端从最近的 checkpoint 恢复,推送下一节点(第 4 轮),不重放已完成的 token
3. **Given** WS 在 token 流式传输中途断开, **When** 重连成功, **Then** 前端丢弃断线节点的 partial tokens,服务端从该节点开头重放(不产生重复 token)
4. **Given** 用户的面试 session 已过期(超过 24 小时未恢复), **When** 尝试继续, **Then** 系统提示「该面试已过期」,用户可查看已生成的部分报告

---

### User Story 3 — 面试历史查看 (Priority: P2)

用户在 InterviewList 页查看所有历史面试记录,包括完成的、进行中的、已过期的,可按时间/公司/岗位筛选,点击进入报告详情。

**Why this priority**: 历史记录是基础 CRUD,Phase 2 已落地 `interview_sessions` 表和只读 API。Phase 4 补全 create/update 能力并将前端从 mock 切到真实数据。

**Independent Test**: 完成 2 场面试后 → 进入 InterviewList → 看到 2 条记录(含状态/公司/岗位/时长) → 点击某条 → 跳转 InterviewReport 页查看完整报告。

**Acceptance Scenarios**:

1. **Given** 用户完成过 2 场面试, **When** 进入 InterviewList 页(`VITE_USE_MOCK=false`), **Then** 列表展示 2 条记录,含公司/岗位/状态/开始时间/时长,按时间倒序
2. **Given** 用户有 1 场「进行中」的面试, **When** 进入 InterviewList, **Then** 该记录显示「进行中」标记和「继续面试」CTA
3. **Given** 用户点击某条已完成面试, **When** 跳转, **Then** InterviewReport 页从真实 API 加载完整报告数据(总分/每题得分/维度得分/优势/改进建议/摘要)

---

### User Story 4 — AI 响应流式体验与错误处理 (Priority: P2)

用户在面试全程通过 WS 实时感知 AI 状态:当前节点、流式 token、评分进度。当发生错误(LLM 限流/模型超时/未知异常)时,前端展示清晰的错误信息并引导下一步操作。

**Why this priority**: 流式体验是 AI 产品的感知质量核心;错误处理直接影响用户信任度和完成率。

**Independent Test**: 模拟 LLM 超时 → 前端显示「AI 响应超时,正在重试…」→ 自动重试成功 → 继续面试;模拟配额用尽 → 显示「本月 token 已用尽,请升级订阅」。

**Acceptance Scenarios**:

1. **Given** AI 正在生成第 2 轮问题, **When** 用户观察 WS 事件流, **Then** 前端依次展示 `node.started(question_gen)` → 流式 `token.delta` × N → `node.completed(question_gen)`,每个状态变化均有对应 UI 动画
2. **Given** LLM 调用超时(> 30s), **When** 节点执行失败, **Then** 前端显示「AI 响应超时,正在重试(1/3)…」,服务端自动重试,成功后继续;3 次失败后显示「请联系支持」
3. **Given** 用户当月 token 配额已用尽, **When** 尝试启动新面试或继续答题, **Then** 系统预扣检查失败,返回 `QuotaExceededError`,前端显示「本月 AI 额度已用尽」+ 订阅升级引导
4. **Given** AI 返回的评分 JSON 格式异常, **When** 评分节点解析失败, **Then** 服务端记录结构化错误日志(含 request_id / session_id / raw_response),前端提示「评分出现异常,已记录,将使用默认评分继续」

---

### Edge Cases

| # | 场景 | 预期行为 |
|---|---|---|
| E1 | WS 在 token 流式中途断线 | 前端丢弃当前节点所有 partial tokens,重连后携带 `last_seen_checkpoint_id`,服务端从该 checkpoint 重放完整节点 |
| E2 | 用户快速连续提交同一轮回答 | 服务端按 `sequence_no` 去重,重复提交返回 409,前端禁用提交按钮直到本轮 `node.completed` |
| E3 | LangGraph checkpoint 写入失败 | 节点执行成功后重试 checkpoint 写入 3 次,仍失败则记录 critical 告警并降级为内存恢复(当次 session 有效,重启丢失) |
| E4 | 面试中用户账号被踢出(第 6 设备登录) | WS 收到 `account.lifecycle_changed` → 前端暂停面试 → 保留当前进度 → 引导用户在新设备继续 |
| E5 | 报告节点执行超过 60s | 前端显示「报告生成中,请耐心等待…」进度动画,超 120s 后允许用户离开页面,后台完成后推送通知 |
| E6 | 双源(ai_messages ↔ checkpoints)对账不一致 | 每日对账任务标记不一致记录,写入 `audit_logs`,发告警;不影响用户读取(以 checkpoints 为准) |
| E7 | 同用户多 Tab 同时启动面试 | 面试无悲观锁(每次启动新 thread),但前端检测同端已有「进行中」session 时弹出确认「你有进行中的面试,是否开启新面试?」 |

---

## Requirements *(mandatory)*

### Functional Requirements

#### LangGraph 基础设施 (M14)

- **FR-001**: System MUST 基于 LangGraph 构建 Interview Agent 子图,包含节点:intake(信息采集) → question_gen(生成问题) → score(评分) → report(报告生成),question_gen 与 score 节点循环 5 次后进入 report
- **FR-002**: System MUST 实现 LangGraph checkpointer,将每次节点执行的 state 持久化到 PostgreSQL,支持按 `thread_id` + `checkpoint_ns` 恢复
- **FR-003**: System MUST 通过统一 LLM 客户端集中处理模型调用,包括:速率限制、自动重试(最多 3 次,指数退避)、结构化日志(含 request_id / model / prompt_tokens / completion_tokens / cache_hit / duration_ms)
- **FR-004**: System MUST 在节点执行前预扣 token 配额,检查 `users.monthly_token_used + estimated_tokens ≤ monthly_token_quota`,超出时抛 `QuotaExceededError` 并阻止节点执行
- **FR-005**: System MUST 集中收集 token 用量 / prompt 缓存命中率 / 模型失败率指标,暴露给 Prometheus

#### 面试子图 (M15)

- **FR-010**: System MUST 支持文字面试模式,用户通过文本输入回答,AI 通过 WS 流式输出问题与评分
- **FR-011**: System MUST 在 intake 节点收集:目标岗位、公司、简历分支(可选)、面试难度,初始化 GraphState
- **FR-012**: System MUST 在 question_gen 节点基于简历内容(如有)和岗位要求生成面试问题,每个问题携带 `dimension`(6 维度之一)和 `difficulty` 标签
- **FR-013**: System MUST 在 score 节点对用户回答评分 0-10,返回 `score` + `feedback_json`(含维度子项得分 + 评语)
- **FR-014**: System MUST 在 report 节点汇总 5 轮评分,生成:overall_score(加权平均)、per_question_score 数组、dimension_scores(6 维各维均分)、strengths(得分最高 2 维)、improvements(得分最低 2 维)、summary_md(自然语言总结)
- **FR-015**: System MUST 在 report 节点完成后同步写入 `interview_reports` 表,异步触发 ability_diagnose 子图(发 ARQ 任务)
- **FR-016**: System MUST 通过 WS 推送以下事件类型:`node.started`(含 node_name) / `token.delta`(含 content 片段) / `node.completed`(含 node_name + 摘要) / `error`(含 code + message)

#### 面试会话管理

- **FR-020**: System MUST 支持创建面试 session(记录 user_id / position / company / mode / branch_id),并初始化 LangGraph thread
- **FR-021**: System MUST 支持从 checkpoint 恢复中断的面试,通过 `last_seen_checkpoint_id` 定位恢复点,从下一未完成节点继续
- **FR-022**: System MUST 维护 session 状态:`pending`(已创建未开始) / `in_progress`(面试中) / `completed`(已完成) / `expired`(超过 24h 未恢复)
- **FR-023**: System MUST 在 session 完成后记录 `duration_sec`(从 started_at 到 ended_at)
- **FR-024**: System MUST 在 report 节点完成后,异步触发 ability_diagnose 子图(ARQ 任务),更新 `ability_dimensions` 表并写入 `ability_dimensions_history`;失败自动重试 3 次,仍失败记录告警但不阻塞报告展示

#### 审计与可观测 (M22 初版)

- **FR-030**: System MUST 将每次 LLM 调用的请求/响应元数据写入 `ai_messages` 表(thread_id / role / model / prompt_tokens / completion_tokens / cache_hit / checkpoint_id),与 LangGraph checkpoints 形成双源
- **FR-031**: System MUST 实现每日对账任务,比对 `ai_messages` ↔ `checkpoints` 的记录一致性,不一致时写入 `audit_logs` 并触发告警
- **FR-032**: System MUST 在关键节点(intake / question_gen / score / report)记录结构化日志,含 request_id / session_id / node_name / duration_ms / result(status)
- **FR-033**: System MUST 为 Interview Agent 暴露 Prometheus 指标:`interview_started_total` / `interview_completed_total` / `interview_failed_total` / `node_duration_seconds`(按 node_name 分桶) / `token_consumed_total`(按 model 分桶)

#### 前端迁移 (M23 Phase 3)

- **FR-040**: System MUST 将 InterviewList 页从 mock 数据切换到真实 API(`GET /api/v1/interview-sessions`),支持状态过滤和分页
- **FR-041**: System MUST 实现 InterviewLive 页:WS 流式事件消费 + 节点状态机 UI + 文字输入提交 + 进度指示器(当前第 X/5 轮)
- **FR-042**: System MUST 将 InterviewReport 页从 mock 数据切换到真实 API(`GET /api/v1/interview-sessions/{id}/report`),展示完整报告内容
- **FR-043**: System MUST 实现 WS 客户端完整版:自动重连(指数退避 1s/2s/4s/8s/16s,max 5 次) + `last_seen_checkpoint_id` 携带 + 重连后恢复流式消费
- **FR-044**: System MUST 在 `VITE_USE_MOCK=false` 时三个面试相关页面完整可用

### Key Entities *(Phase 4 涉及的实体,已在 Phase 1/2 定义表结构)*

- **InterviewSession**: Phase 2 已建表。Phase 4 补全 create/update 能力,新增 `checkpoint_ns` 字段用于 LangGraph checkpoint 恢复。关键属性:user_id, branch_id(可选), position, company, mode(text/voice), status(pending/in_progress/completed/expired), thread_id, checkpoint_ns, started_at, ended_at, duration_sec
- **InterviewReport**: Phase 4 新增写入。1:1 InterviewSession。关键属性:overall_score, per_question_score(JSONB), dimension_scores(JSONB), strengths(JSONB), improvements(JSONB), summary_md, generated_at
- **AiMessage**: Phase 4 新增写入。由 LangGraph checkpointer 同步,双源存储。关键属性:thread_id, checkpoint_ns, role, content, model, prompt_tokens, completion_tokens, cache_hit, occurred_at, checkpoint_id
- **AbilityDimension / AbilityDimensionHistory**: Phase 2 已建表。Phase 4 通过异步 ARQ 任务首次写入真实数据(此前为空或 mock)
- **AuditLog**: Phase 4 初版写入。记录 LLM 调用审计和对账差异。关键属性:request_id, actor_id, action, target_type, target_id, changed_fields(JSONB), result, duration_ms, occurred_at

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户可在 10 分钟内完成「启动面试 → 5 轮对话 → 查看报告」全流程(不含思考时间)
- **SC-002**: WS 推送延迟 P95 ≤ 200ms(同区域网络)
- **SC-003**: LangGraph 单节点执行 P95 ≤ 1.5s(不含 LLM 调用时间)
- **SC-004**: 断线重连后 5s 内恢复到上一 checkpoint 并继续面试
- **SC-005**: 面试完成率 ≥ 85%(启动后到达 report 节点的比例)
- **SC-006**: 双源对账(ai_messages ↔ checkpoints)一致性 ≥ 99.9%,日报 0 缺失告警
- **SC-007**: InterviewList / InterviewLive / InterviewReport 三页面在 `VITE_USE_MOCK=false` 下完整可用,所有数据来自真实 API
- **SC-008**: LLM 调用失败后自动重试成功率 ≥ 80%,用户感知错误率 ≤ 5%
- **SC-009**: token 配额预扣检查延迟 ≤ 50ms,不阻塞节点启动
- **SC-010**: 报告生成完成后 10 秒内 ability_diagnose 异步任务启动(不阻塞报告展示)

## Assumptions

- 沿用 Phase 1/2 的技术栈:FastAPI + PostgreSQL 15 + Redis 7 + ARQ + LangGraph
- LLM 使用 DeepSeek V4 Pro(`deepseek-chat`),OpenAI 兼容协议,所有节点统一模型(2026-06-13 用户决议)
- Anthropic API key 不再需要;DeepSeek API key 已配置在 `backend/.env`
- 语音模式通过浏览器 Web Speech API 实现,Phase 4 仅支持文字模式,语音为后续增量
- LangGraph checkpointer 使用 PostgreSQL 后端(非内存/文件),与业务数据库共用
- token 配额沿用 Phase 1 的 `users.monthly_token_quota` 和 Phase 2 的 cron 重置机制
- 面试无悲观锁(每次启动新 thread),同端多 Tab 仅前端检测防误开
- LangSmith 默认不启用,所有链路追踪走结构化日志(待 Phase 6 法务评审后决定)
- 前端 WS 客户端在 Phase 1 已有骨架,Phase 4 补全流式消费和断线恢复逻辑
- Phase 2 已建 `interview_sessions` 表并实现只读 list/get API,Phase 4 扩增 CUD + checkpoint 恢复
- ability_diagnose 子图的完整实现在 Phase 5,Phase 4 仅实现 report 后的异步触发和基础写入
