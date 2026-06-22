# Feature Specification: LangGraph Checkpointer 连接稳定性修复

**Feature Branch**: `023-checkpointer-stability`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "Feature 023 — LangGraph checkpointer 连接稳定性修复。补齐 v1 在 LangGraph checkpointer 连接管理方面的短板，范围聚焦在三项根因修复：连接池配置缺失、lifespan 不预热、retry 逻辑仅覆盖 interview 且 submit_answer 漏接。修复后 5 个 graph 的所有 checkpoint 操作统一走共享 retry wrapper。不改业务逻辑，不改 API 契约，不切换到 sync checkpointer。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 面试用户在 idle 后继续答题不中断 (Priority: P1)

作为面试求职者，当我开始一场面试后中途离开 5 分钟查看资料，回来继续提交下一题答案时，系统应当无缝接受我的答案继续面试流程，而不是抛出「连接已关闭」错误迫使我刷新页面重试。当前 interview agent 的 checkpointer 在 idle 一段时间后连接被 PostgreSQL 服务端或中间网络设备关闭，再次提交时首次请求失败，用户重试又是 no-op（因为 state 已部分写入），导致面试卡死。

**Why this priority**: 面试是核心业务流程，单次面试 30+ 分钟，用户中途查看资料是常态。idle 断连导致面试卡死直接影响用户求职体验，且当前无任何用户侧缓解措施（刷新也不解决）。这是 v1 上线后最高频的 agent 类 bug。

**Independent Test**: 启动后端，触发一次面试 start，等待 60 秒（模拟 idle），再次调用 submit_answer，断言响应 200 且返回有效 score，不抛 OperationalError。

**Acceptance Scenarios**:

1. **Given** 用户已开始面试（thread_id 存在），**When** 等待 60 秒后调用 `POST /interview-sessions/{tid}/messages`，**Then** 响应 200，返回 score 和下一题，不抛连接错误。
2. **Given** checkpointer 连接已断开（模拟：手动关闭底层连接），**When** 用户提交答案，**Then** 后端自动重连一次并成功处理，用户侧无感知。
3. **Given** 重连也失败（模拟：PostgreSQL 服务暂时不可达），**When** 用户提交答案，**Then** 后端返回 503 并提示「面试服务暂时不可用，请稍后重试」，不返回 500 内部错误。
4. **Given** 重连成功后，**When** 查询 `/metrics`，**Then** `checkpointer_reconnect_total` 指标值 +1（与 022 联动）。

---

### User Story 2 - 错题强化用户在 idle 后继续答题不中断 (Priority: P1)

作为面试备考用户，当我在错题强化 3 轮对话中途查看笔记几分钟后回来提交答案时，系统应当继续评分流程，而不是因为 checkpointer 断连导致 frequency 不递减或状态错乱。当前 error_coach agent 完全没有 retry 逻辑，idle 断连后 submit_answer 直接走 not_found 分支，client 重试时 state 已部分写入导致 no-op，frequency 永远不递减。

**Why this priority**: 错题强化是 021 刚补齐 E2E 覆盖的功能，但 E2E 在连续测试中不暴露 idle 问题。生产环境下用户中途暂停是常态，必须与 interview agent 同等可靠。

**Independent Test**: 启动后端，调用 error-coach start，等待 60 秒，调用 submit_answer，断言 correct_count 正确递增，frequency 在 3 轮答对后正确递减。

**Acceptance Scenarios**:

1. **Given** 用户已开始错题强化（thread_id 存在），**When** 等待 60 秒后提交答案，**Then** 响应 200，score 和 correct_count 正确返回。
2. **Given** 3 轮答对中有任何一轮发生在 idle 断连之后，**When** 第 3 轮提交完成，**Then** frequency 正确从 3 减为 2，status 保持 fresh。
3. **Given** checkpointer 断开后重连成功，**When** 查询 `/metrics`，**Then** `checkpointer_reconnect_total` 指标值递增。

---

### User Story 3 - 简历优化用户中断后恢复不报错 (Priority: P2)

作为简历优化用户，当 AI 生成 diff 后我离开页面查看其他资料，几分钟后回来点击「应用」或「放弃」按钮时，系统应当正确处理我的决策，而不是因为 checkpointer 断连导致 confirm 接口 500。当前 resume_optimize agent 完全没有 retry 逻辑。

**Why this priority**: 简历优化是低频但高价值功能，用户中断恢复的场景比面试少，但仍需可靠。优先级低于 interview 和 error_coach（高频 + 长流程）。

**Independent Test**: 启动后端，调用 resume-optimize start，等待 60 秒，调用 confirm，断言响应 200 且简历版本正确创建。

**Acceptance Scenarios**:

1. **Given** 用户已开始简历优化且 AI 已生成 diff（thread 处于 interrupt 状态），**When** 等待 60 秒后调用 `POST /agents/resume-optimize/{tid}/confirm`，**Then** 响应 200，简历版本正确创建（type=ai）。
2. **Given** 用户选择放弃，**When** 调用 confirm 接口 decision=discard，**Then** 响应 200，简历未修改，thread 标记为 aborted。

---

### User Story 4 - 能力诊断异步任务在 checkpointer 断连后自动重试 (Priority: P2)

作为面试结束后的用户，系统自动触发能力诊断任务更新我的能力画像。当 ARQ worker 执行诊断任务时遇到 checkpointer 断连，任务应当自动重试一次而非直接失败进入 dead letter。当前 ability_diagnose graph 完全没有 retry 逻辑。

**Why this priority**: 能力诊断是异步任务，用户不直接感知失败，但失败后能力画像不更新影响后续推荐。优先级低于用户直接交互的 agent。

**Independent Test**: 启动后端，触发面试完成后等待 ARQ 任务，模拟 checkpointer 断连（手动关闭连接），断言 ARQ 任务重试一次后成功，能力画像正确更新。

**Acceptance Scenarios**:

1. **Given** 面试已完成触发能力诊断 ARQ 任务，**When** 任务执行时 checkpointer 断连，**Then** 任务自动重试一次，重试成功后能力画像更新。
2. **Given** 重试也失败，**When** ARQ 任务达到最大重试次数，**Then** 任务进入 dead letter 队列，`arq_jobs_failed_total` 指标 +1（与 022 联动）。

---

### User Story 5 - 通用辅导对话在 idle 后继续不中断 (Priority: P2)

作为通用辅导用户，当我与 AI 对话中途暂停几分钟后继续发送消息时，系统应当继续对话上下文，而不是因为 checkpointer 断连导致上下文丢失或 500。当前 general_coach agent 完全没有 retry 逻辑。

**Why this priority**: 通用辅导是长会话型功能，用户中途暂停常见。优先级与简历优化、能力诊断同层。

**Independent Test**: 启动后端，调用 general-coach start 发送一条消息，等待 60 秒，发送第二条消息，断言响应 200 且 AI 回复引用了第一条消息的上下文。

**Acceptance Scenarios**:

1. **Given** 用户已开始通用辅导对话，**When** 等待 60 秒后发送新消息，**Then** 响应 200，AI 回复保持上下文连贯。
2. **Given** checkpointer 断连后重连成功，**When** 查询 `/metrics`，**Then** `checkpointer_reconnect_total` 指标值递增。

---

### User Story 6 - 服务启动后首请求无 schema 初始化延迟 (Priority: P2)

作为运维工程师，当后端服务重启后，首个访问 agent 接口的用户不应感受到明显的 schema 初始化延迟。当前 lifespan 启动时不预热 checkpointer，首次 agent 调用才执行 `setup()` 创建 checkpointer 表（可数百 ms），首用户体验差。

**Why this priority**: 服务重启后的首请求性能影响用户体验，且预热是低成本高收益的优化。优先级低于用户交互型 story。

**Independent Test**: 重启后端，立即调用 agent 接口，断言首请求延迟与稳态请求延迟差异 ≤ 50ms（无 schema 初始化开销）。

**Acceptance Scenarios**:

1. **Given** 后端服务刚启动，**When** 立即调用 `POST /agents/error-coach/start`，**Then** 响应延迟 ≤ 500ms（无 schema 初始化开销）。
2. **Given** 服务启动日志，**When** 查看启动阶段日志，**Then** 可见 `checkpointer.preheat ok` 日志，证明 checkpointer 在 lifespan 阶段已初始化。
3. **Given** 服务启动后，**When** 查询 `pg_tables` WHERE tablename LIKE 'checkpoint%'，**Then** checkpointer 表已存在（预热阶段创建）。

---

### Edge Cases

- 当 checkpointer 连接断开发生在 `aupdate_state` 中间（state 已部分写入）时，重试必须幂等：重试时先 `aget_state` 检查当前状态，避免重复写入。
- 当 checkpointer 重连也失败（PostgreSQL 服务不可达）时，必须返回 503 而非 500，且响应体包含 `retry_after` 提示。
- 当多个并发请求同时触发 checkpointer 重连时，必须有锁机制避免重复重建（只重建一次，其他请求等待）。
- 当 lifespan 预热 checkpointer 失败（数据库未就绪）时，服务必须仍然启动（降级为懒加载），并记录 warning 日志。
- 当 ARQ worker 中触发 checkpointer 操作时，retry 逻辑必须同样生效（worker 上下文无 HTTP request_id，但 retry 不依赖 request_id）。
- 当 checkpointer 表 schema 已存在（非首次启动）时，`setup()` 必须幂等，不报错。
- 当 TCP keepalive 探测失败（网络中间设备异常）时，psycopg 连接池应标记该连接为 dead 并重新创建，不影响业务请求。
- 当 `max_idle=300` 到期后连接被池回收，下一次请求获取新连接时不应有可感知延迟（≤ 50ms）。

## Requirements *(mandatory)*

### Functional Requirements

#### US1 + US2 — 共享 retry wrapper（interview + error_coach 高优先级）

- **FR-001**: 系统 MUST 在 `backend/app/agents/checkpointer.py` 提供共享的 `with_checkpointer_retry` 异步上下文管理器或装饰器，封装「检测断连 → 重建 checkpointer → 重试一次」逻辑。
- **FR-002**: retry 逻辑 MUST 匹配以下错误类型：`psycopg.OperationalError` 含 "connection is closed" / "the connection" / "admin shutdown" / "server closed the connection unexpectedly"。
- **FR-003**: retry 逻辑 MUST 对幂等操作（aget_state）直接重试；对非幂等操作（aupdate_state / ainvoke）重试前必须先 aget_state 检查当前状态，避免重复写入。
- **FR-004**: retry 逻辑 MUST 在重连失败时抛出可被 API 层捕获的 `CheckpointerUnavailableError` 异常，API 层返回 503。
- **FR-005**: 并发触发重连时 MUST 使用 asyncio.Lock 确保只重建一次，其他协程等待锁释放后使用新 checkpointer。
- **FR-006**: interview agent 的 `submit_answer` MUST 调用共享 retry wrapper（修复当前 graph.py:169 直接 aget_state 漏接 retry 的 bug）。
- **FR-007**: error_coach agent 的 `submit_answer` / `abort` MUST 调用共享 retry wrapper。

#### US3 + US4 + US5 — 扩展 retry 覆盖到其余 3 个 graph

- **FR-010**: resume_optimize agent 的 `confirm` / `abort` MUST 调用共享 retry wrapper。
- **FR-011**: ability_diagnose graph 的所有 checkpoint 操作（aget_state / ainvoke）MUST 调用共享 retry wrapper。
- **FR-012**: general_coach agent 的 `send_message` / `close` MUST 调用共享 retry wrapper。
- **FR-013**: 5 个 graph 的既有 `_is_checkpointer_alive` / `_rebuild_checkpointer` 本地实现 MUST 移除，统一调用共享 wrapper，避免逻辑重复。

#### US6 — lifespan 预热 + 连接池配置

- **FR-020**: `backend/app/main.py` lifespan startup MUST 调用 `get_checkpointer()` + `setup()` + 连接池 `open()`，预热 checkpointer 表 schema。
- **FR-021**: 预热失败 MUST 不阻塞服务启动，降级为懒加载并记录 warning 日志 `checkpointer.preheat_failed`。
- **FR-022**: 预热成功后 MUST 记录 info 日志 `checkpointer.preheat ok`，包含连接池配置参数。
- **FR-023**: `AsyncPostgresSaver` MUST 配置显式连接池参数：`min_size=1, max_size=10, max_idle=300, reconnect_timeout=300, timeout=30`。
- **FR-024**: 系统 MUST 配置 TCP keepalive：`keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5`，防止 NAT/RDS idle kill。
- **FR-025**: 连接池 MUST 启用 `check` 回调（psycopg-pool 3.2+ 的 `check_connection`），在获取连接时做轻量健康检查（SELECT 1），失败则标记为 dead 重新创建。

#### 跨切面

- **FR-030**: 本 feature MUST 不改动任何 API 请求/响应契约。
- **FR-031**: 本 feature MUST 不改动任何 graph 的业务节点逻辑（nodes/ 目录下文件不动）。
- **FR-032**: 本 feature MUST 不切换到 sync checkpointer（会阻塞 event loop）。
- **FR-033**: 本 feature MUST 保持所有现有 E2E 和单元测试通过（回归零退化）。
- **FR-034**: checkpointer 重连次数 MUST 通过 `checkpointer_reconnect_total` Prometheus 指标暴露（与 022 FR-042 联动）。
- **FR-035**: 本 feature MUST 不升级 langgraph 主版本（保持 0.2.x），避免引入 breaking change。

### Key Entities *(include if feature involves data)*

- **checkpoints / checkpoint_writes / checkpoint_blobs**: 既有 LangGraph checkpointer 表，本 feature 仅确保 schema 在 lifespan 阶段预热创建，不改表结构。
- **AsyncConnectionPool**: psycopg-pool 的异步连接池，本 feature 新增显式配置（min_size/max_size/max_idle/reconnect_timeout/keepalive），不改 pool 类本身。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 5 个 agent 的 submit_answer / confirm / send_message 接口在 idle 60 秒后调用，100% 返回 200，不抛连接错误。
- **SC-002**: 后端服务重启后首个 agent 接口调用延迟 ≤ 500ms（与稳态延迟差异 ≤ 50ms），无 schema 初始化开销。
- **SC-003**: checkpointer 断连重连次数通过 `/metrics` 端点的 `checkpointer_reconnect_total` 指标可观测，与 022 SC-005 联动验证。
- **SC-004**: 5 个 graph 的本地 retry 实现统一为共享 wrapper，代码行数净减少（移除 interview/graph.py:42-101 的 ~60 行本地实现）。
- **SC-005**: 既有 round-1 + round-2 E2E 测试套件 100% 通过，无回归（含 021 的 3 个 error_coach E2E）。
- **SC-006**: 连接池配置显式参数（min_size/max_size/max_idle/reconnect_timeout/keepalive）在启动日志中可见，运维可验证配置生效。
- **SC-007**: 并发触发 checkpointer 重连时（10 个并发请求），仅重建 1 次（通过日志计数验证），其他请求等待锁后复用新 checkpointer。

## Assumptions

- 后端使用 langgraph 0.2.x + langgraph-checkpoint-postgres 1.0.x，`AsyncPostgresSaver.from_conn_string` 底层使用 psycopg-pool 3.2+。
- PostgreSQL 服务端 `idle_in_transaction_session_timeout` 默认或显式配置为 > 300 秒，避免 checkpointer 连接被服务端主动关闭。
- 网络中间设备（NAT / 防火墙）的 idle timeout > 30 秒（TCP keepalive idle），否则 keepalive 无法防止断连。
- 本 feature 不升级 langgraph 主版本（0.2.x 内升级补丁版可接受），避免引入 breaking change。
- 本 feature 不引入 OpenTelemetry 追踪（留待 v2.0），仅通过结构化日志和 Prometheus 指标观测。
- 共享 retry wrapper 的「重试一次」策略是性能与可靠性的平衡：多次重试会放大延迟，一次重试覆盖绝大多数 transient 断连。
- 预热失败降级为懒加载是合理 trade-off：服务可用性优先于首请求性能。
- ARQ worker 中的 checkpointer 操作走同一 retry wrapper，无需 worker 特殊处理。
- `CheckpointerUnavailableError` 是新引入的异常类型，API 层现有异常处理需扩展支持（仅 agents/* 路由）。
- 本 feature 不修复 checkpointer 表 schema 性能问题（checkpoints 表无索引等），留待 v2.0。
