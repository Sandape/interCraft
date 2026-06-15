# Feature Specification: Phase 5 — P1 Agent 子图扩展

**Feature Branch**: `004-phase5-agent-subgraphs`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "Phase 5 — P1 Agent 子图扩展。在 Phase 4 Interview Agent (M15) + LangGraph 基础设施 (M14) 基础上,实现剩余 4 个 Agent 子图:简历优化 Agent (M16)、错题强化 Agent (M17)、能力诊断 Agent (M18 完整版)、通用辅导 Agent (M19)。配套前端迁移与 WS 事件扩展。"

## Clarifications

### Session 2026-06-15

- Q: M17 错题强化评分标准是否对齐 Phase 4 的 0-10 分制? → A: 是。M17 评分使用 0-10 分制,阈值 ≥ 8 视为答对,与 Phase 4 面试评分保持一致。
- Q: M19 通用 Coach 意图识别是否加关键词兜底? → A: 否,MVP 使用纯 LLM 分类 + few-shot 示例。在 prompt 中预置 3-5 个预配示例提升分类准确率,上线后如分类不准再加关键词层。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — AI 简历优化:人类介入的智能改稿 (Priority: P1)

用户在简历编辑器中对某个分支点击「AI 优化」,Agent 基于目标 JD 分析简历差距,生成 JSON Patch 修改建议。用户可在编辑器内审阅 diff,决定「应用」「丢弃」或手动调整后重新提交。优化落盘后自动创建版本快照。

**Why this priority**: 简历优化是用户高频需求,也是**唯一**需要 `interrupt` 人类介入的子图,交互流程最复杂。解锁后将简历从「手动编辑」升级为「AI 辅助编辑」。

**Independent Test**: 在简历分支上点击「AI 优化」→ Agent 分析后推送 interrupt → 编辑器展示 before/after diff → 用户点击「应用」→ 分支内容更新,版本历史出现 AI 优化记录。

**Acceptance Scenarios**:

1. **Given** 用户在简历编辑器打开某分支, **When** 点击「AI 优化」并传入目标 JD(可选公司+岗位), **Then** 系统持锁(acquire lock on resume_branch),调用 Agent 分析,持锁失败返回 423
2. **Given** Agent 完成分析生成建议 diff, **When** `apply_or_discard` 节点执行 interrupt, **Then** WS 推送 `interrupt` 事件含 proposed_patches + summary,前端进入「Review」态,块上内联显示 before/after
3. **Given** 用户审阅 diff 后点击「应用」, **When** 调用 `confirm` 端点, **Then** patch 落盘,创建新版本(`author_type='ai'`, `trigger='ai'`),释放锁
4. **Given** 用户审阅后点击「丢弃」, **When** 调用 `confirm` 端点, **Then** 简历不修改,thread 标记 aborted,释放锁
5. **Given** 用户长时间无操作(> 30 分钟), **When** 超时巡检触发, **Then** 自动标记 timeout,释放锁,前端提示「优化已超时,请重新开始」

---

### User Story 2 — 能力画像自动诊断:面试后的异步洞察 (Priority: P1)

用户完成一场模拟面试后,Ability Diagnose Agent 异步启动,自动汇总面试评分、比对历史基线、生成 6 维度能力更新与改进建议。用户在 Profile 页实时看到「能力画像更新中…」到「已更新」的转变。

**Why this priority**: 能力画像是产品的「价值证明」——用户回访的核心驱动力。Phase 4 仅实现了异步触发骨架,Phase 5 补全完整的 LLM 诊断子图。无此子图,Profile 页的能力曲线永远为空。

**Independent Test**: 完成 1 场模拟面试 → 等待 10-30 秒 → 进入 Profile 页 → 看到能力雷达图分数更新 → 改进建议清单出现 → 活动流中出现「能力画像已更新」记录。

**Acceptance Scenarios**:

1. **Given** Interview Agent report 节点完成, **When** ARQ 任务 `diagnose_after_interview(session_id)` 触发, **Then** Ability Diagnose 子图启动,节点流程: aggregate_scores → compare_baseline → generate_insight → update_dimensions
2. **Given** 子图完成 `aggregate_scores`, **When** 读取 interview_reports + ai_messages, **Then** 产出每维度加权分数(6 维度:技术深度/架构能力/工程实践/沟通表达/算法能力/业务理解)
3. **Given** 子图完成 `compare_baseline`, **When** 读取 ability_dimensions_history(近 90 天), **Then** 计算 delta:当前分数 - 历史基线,标记「上升/下降/持平」
4. **Given** 子图完成 `generate_insight`, **When** LLM 产出改进建议, **Then** 写入 activities(`type='ability.suggestion'`),每条含维度和优先级
5. **Given** 子图完成 `update_dimensions`, **When** 更新 ability_dimensions.actual + 追加 ability_dimensions_history, **Then** WS 推送 `agent.final` 事件,前端 Profile 页收到「能力画像已更新」通知
6. **Given** 子图执行失败(LLM 调用失败等), **When** ARQ 重试 3 次仍失败, **Then** 写入 dead_letter 表,记录告警,不阻塞用户后续操作

---

### User Story 3 — 错题强化 Agent:梯度式错题歼灭 (Priority: P2)

用户在错题本中对某道错题点击「开始强化」,Error Coach Agent 启动 3 轮梯度提示(easy → medium → detailed),引导用户逐步掌握知识点。累计答对 3 次后 frequency 递减,直至「已掌握」状态。

**Why this priority**: 错题本是产品闭环的关键环节,但 Phase 2 仅支持手动管理,Phase 4 面试评分可自动沉淀错题但无 AI 强化。Phase 5 的 Agent 强化使错题本从「记录工具」升级为「学习引擎」。

**Independent Test**: 进入错题本 → 选中 1 道错题点击「开始强化」→ 第 1 轮收到小提示,回答后评分 → 连续 3 轮答对 → frequency 减 3,状态可能变「已掌握」。

**Acceptance Scenarios**:

1. **Given** 用户在错题本选中某错题(frequency > 0), **When** 点击「开始强化」, **Then** Error Coach 子图创建新 thread,`hint_ladder` 节点根据 attempt_count 输出首轮提示(easy 级别)
2. **Given** 用户回答后提交, **When** `evaluate` 节点评分 ≥ 8 分(0-10 分制), **Then** correct_count +1,调 M08 `recall` 接口减 frequency,进入下一轮(medium 级别)
3. **Given** 用户回答评分 < 8 分, **When** `evaluate` 节点判定, **Then** correct_count 不变,`current_hint_level` 升级(小→中等或中等→详细),提示更具体
4. **Given** 用户累计答对 3 次(correct_count ≥ 3), **When** `loop_or_finish` 节点判定, **Then** 子图结束,标记成功完成
5. **Given** 用户中途退出或超过 10 分钟无活动, **When** 超时触发, **Then** 子图标记 aborted,已完成的答对次数已持久化到错题 frequency
6. **Given** 用户连续 3 次答错同一题(未答对任何一次), **When** 子图结束, **Then** frequency 不变或增加,建议用户暂缓后重试

---

### User Story 4 — 通用 Coach:AI 职业导师 (Priority: P2)

用户在「通用教练」页面发起任意技术/职业问题(如「如何准备系统设计面试」「React 项目结构最佳实践」),General Coach Agent 通过意图分类(intent → route → respond)给出针对性回答。当检测到意图属于已有 Agent 能力(简历优化/面试练习)时,给出跳转引导。

**Why this priority**: 提供产品边缘之外的 AI 问答能力,覆盖长尾场景,提升用户粘性。同时也是 M14 基础设施的完整验证——展示 LangGraph 子图编排的灵活性。

**Independent Test**: 进入通用 Coach 页 → 输入「帮我优化一下简历中的项目描述」→ Agent 识别意图并引导「建议使用简历优化功能」→ 输入「能用 React 做什么动画库」→ Agent 直接回答并推荐资源。

**Acceptance Scenarios**:

1. **Given** 用户进入通用 Coach 并输入问题, **When** `intent` 节点对输入分类, **Then** LLM 输出结构化的意图判定:`{intent: enum, confidence: 0-1, reasoning: str}`
2. **Given** 意图为 `career_advice` 或 `chitchat` 且 confidence > 0.7, **When** `route` 节点走 `respond` 通用回答, **Then** WS 流式推送 token,用户看到逐字回答
3. **Given** 意图为 `resume_optimize` 或 `interview_practice` 且 confidence > 0.7, **When** `route` 节点走引导路径, **Then** 用户收到一句简短回答 + 跳转引导「检测到你需要简历优化,建议使用编辑器中的「AI 优化」功能以获得更好的效果」
4. **Given** 用户意图模糊(confidence ≤ 0.7), **When** `route` 节点走通用回答, **Then** 正常回答并在末尾添加「你可以更具体地描述需求,或使用以下功能:简历优化/模拟面试/错题强化」
5. **Given** 用户结束对话关闭页面, **When** 前端调用 `close` 端点, **Then** 子图结束,释放资源

---

### Edge Cases

| # | 场景 | 预期行为 |
|---|---|---|
| E1 | M16 简历优化时锁被其他端抢占 | `start` 时 acquire lock 失败返回 423,前端提示「该简历正在被其他端编辑,请稍后重试」 |
| E2 | M16 用户拒绝 AI 建议后想重新生成 | MVP 不支持「再来一版」,用户需重新 start;v1.1 加 `regenerate` 端点 |
| E3 | M17 错题强化时用户关闭 Tab | 超时 10 分钟后自动结束,已答对次数已持久化到错题 frequency,不丢失进度 |
| E4 | M18 能力诊断与面试报告同时写入的竞态 | 诊断子图通过 session_id 原子读取 reports,写 dimensions 使用 `UPSERT`;不会丢失数据 |
| E5 | M18 单用户连续完成多场面试的串行诊断 | 每场面试独立触发 ARQ 任务,任务间无依赖,可并行执行写入时按 `(user_id, dimension_key)` 原子 upsert |
| E6 | M19 用户输入敏感信息(PII) | 通用 Coach 为开放问答,不存储对话历史到业务表(仅 ai_messages 审计),用户需注意不分享敏感信息 |
| E7 | M19 单用户多 Tab 同时使用通用 Coach | 每个对话独立 thread,无冲突,但前端提示「你有其他对话正在进行」 |
| E8 | 多个 Agent 子图同时消费 token 配额 | 统一走 M14 LLM 客户端,预扣检查在 invoke 入口串行化,确保配额不被超额消费 |
| E9 | M16/M17/M18/M19 中任一子图 LLM 调用失败 | 统一走 LLM 客户端重试(3 次指数退避),仍失败后记录错误 + 告警;M16 中断重试留给用户决定;M17/M19 重试自动;M18 ARQ 自带重试 |
| E10 | 前端 `VITE_USE_MOCK=true` 回退 | Phase 5 四个子图对应前端页面应支持 mock 回退模式,在 mock 下展示静态占位/演示数据 |

## Requirements *(mandatory)*

### Functional Requirements

#### M16 · 简历优化 Agent

- **FR-001**: System MUST 提供 `POST /api/v1/agents/resume-optimize/start` 端点,接收 `branch_id` + 可选 `target_jd`(或 `company` + `position`),acquire lock on resume branch,失败返回 423
- **FR-002**: System MUST 实现 Resume Optimize 子图节点流程:`load_branch → diff_jd → suggest_blocks → apply_or_discard(interrupt!) → snapshot`
- **FR-003**: System MUST 在 `apply_or_discard` 节点配置 `interrupt_after`,WS 推送 `interrupt` 事件,payload 含 `proposed_patches`(RFC 6902 JSON Patch) + `summary`
- **FR-004**: System MUST 提供 `POST /api/v1/agents/resume-optimize/{thread_id}/confirm` 端点接收 `{"decision": "apply"|"discard"}`,解决中断后子图恢复
- **FR-005**: System MUST 在 `apply` 决策时:应用 JSON Patch 到 resume_blocks,调 `save_resume_version` 创建版本(`author_type='ai'`, `trigger='ai'`)
- **FR-006**: System MUST 在 `discard` 决策时:不修改简历,thread 标记为 `aborted`
- **FR-007**: System MUST 通过 ARQ cron 巡检超时(30 分钟无活动)自动释放锁并标记 timeout

#### M17 · 错题强化 Agent

- **FR-010**: System MUST 提供 `POST /api/v1/agents/error-coach/start` 端点,接收 `error_question_id`,每次启动创建新 thread
- **FR-011**: System MUST 实现 Error Coach 子图节点流程:`fetch_question → hint_ladder → wait_user → evaluate → loop_or_finish`
- **FR-012**: System MUST 在 `hint_ladder` 节点根据 `attempt_count` 选择提示级别:第 1 次答错给 small hint / 第 2 次 medium / 第 3 次 detailed
- **FR-013**: System MUST 在 `evaluate` 节点对用户回答评分(0-10,与 Phase 4 面试评分对齐),阈值 ≥ 8 视为答对,cumulative correct_count +1
- **FR-014**: System MUST 在答对时调 M08 `recall` 接口递减 `frequency`(每个正确答案减 1,不允许低于 0)
- **FR-015**: System MUST 在 `correct_count ≥ 3` 时结束子图,标记成功;累计答对不同需要连续
- **FR-016**: System MUST 支持用户主动退出(`POST /api/v1/agents/error-coach/{thread_id}/abort`)和 10 分钟超时自动结束

#### M18 · 能力诊断 Agent(完整版)

- **FR-020**: System MUST 由 ARQ 任务 `diagnose_after_interview(session_id)` 触发 M18 子图(Phase 4 已建骨架,Phase 5 补全完整 LLM 节点)
- **FR-021**: System MUST 实现 Ability Diagnose 子图节点流程:`aggregate_scores → compare_baseline → generate_insight → update_dimensions`
- **FR-022**: System MUST 在 `aggregate_scores` 节点通过工具 `query_interview_score(session_id)` 读取面试评分,按 6 维度加权聚合
- **FR-023**: System MUST 在 `compare_baseline` 节点读取 `ability_dimensions_history`(近 90 天),计算 delta 并标记趋势(上升/下降/持平)
- **FR-024**: System MUST 在 `generate_insight` 节点通过 LLM 生成改进建议:每维度 3-5 条,含优先级,写入 activities(`type='ability.suggestion'`)
- **FR-025**: System MUST 在 `update_dimensions` 节点更新 `ability_dimensions.actual` + 追加 `ability_dimensions_history`,WS 推送 `agent.final` 事件
- **FR-026**: System MUST 失败时 ARQ 自动重试 3 次(指数退避),3 次后写入 dead_letter 表并告警,不阻塞用户

#### M19 · 通用辅导 Agent

- **FR-030**: System MUST 提供 `POST /api/v1/agents/general-coach/start` 端点,接收可选初始问题,创建新 thread(新 uuid)
- **FR-031**: System MUST 实现 General Coach 子图节点流程:`intent → route → respond`
- **FR-032**: System MUST 在 `intent` 节点通过 LLM 输出结构化意图:支持 `resume_optimize` / `interview_practice` / `career_advice` / `chitchat`,含 `confidence`(0-1);prompt 中预置 3-5 个 few-shot 示例提升分类准确率
- **FR-033**: System MUST 在 `route` 节点:confidence > 0.7 且意图匹配已有 Agent → 输出引导回答;否则 → 走 `respond` 通用问答
- **FR-034**: System MUST 通过 WS 流式推送 `token.delta` 事件(复用 Phase 4 格式),前端逐字渲染
- **FR-035**: System MUST 提供 `POST /api/v1/agents/general-coach/{thread_id}/close` 端点和 2 小时无活动自动结束

#### 前端迁移 (M23 Phase 5)

- **FR-040**: System MUST 在简历编辑器(ResumeEditor.tsx)集成「AI 优化」入口按钮,触发 M16 start 接口,展示 interrupt diff review UI(内联 before/after 对比)
- **FR-041**: System MUST 在错题本(ErrorBook page)中「错题卡片」添加「开始强化」CTA,点击触 M17 start,页面内嵌 3 轮对话面板
- **FR-042**: System MUST 在 Profile 页展示「能力画像更新中…」→「已更新」状态转换(基于 WS `agent.final` 事件),无需手动刷新
- **FR-043**: System MUST 新增「通用 Coach」页面,含对话列表 + 输入框 + 流式渲染,对接 M19 WS 事件
- **FR-044**: System MUST 在 `VITE_USE_MOCK=true` 时,M16/M17/M18/M19 对应前端页面展示 mock/占位数据,可独立演示

### Key Entities

Phase 5 不涉及新表创建。所有 Agent 子图通过已有业务表 + LangGraph checkpoints 中转数据。

- **ResumeOptimizeState** (M16): 子图内部 state,含 branch_id / target_jd / current_blocks / proposed_patches(JSON Patch 数组) / decision(apply|discard)
- **ErrorCoachState** (M17): 子图内部 state,含 error_question_id / correct_count / attempt_count / current_hint_level(small|medium|detailed)
- **AbilityDiagnoseState** (M18): 子图内部 state,含 session_id / interview_scores / historical_dims / current_dims / diagnoses / insights
- **GeneralCoachState** (M19): 子图内部 state,含 conversation_id / detected_intent / suggested_redirect
- **ai_messages**: Phase 4 已建,Phase 5 扩展写入 M16-M19 的 LLM 调用元数据
- **AuditLog**: Phase 4 已建,Phase 5 用于记录 Agent 子图的关键事件

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 简历优化 Agent(M16)从启动到 interrupt 推送在 15 秒内(不含 LLM 调用时间),用户决策后 apply/discard 在 3 秒内完成
- **SC-002**: 能力诊断 Agent(M18)在面试完成后 30 秒内完成全部诊断流程(含 LLM 调用),用户无需等待超过 1 分钟
- **SC-003**: 错题强化 Agent(M17)单轮问答(用户提交 → 评分反馈)在 5 秒内完成
- **SC-004**: 通用 Coach(M19)意图分类在 2 秒内完成,流式回答延迟 P95 ≤ 200ms(同区域)
- **SC-005**: 四个 Agent 子图的 LLM 调用成功率 ≥ 95%(3 次重试后)
- **SC-006**: 简历优化 interrupt 的 30 分钟超时后,锁自动释放率 100%,无死锁残留
- **SC-007**: 四个子图对应的前端页面在 `VITE_USE_MOCK=true` 和 `VITE_USE_MOCK=false` 模式下均完整可用
- **SC-008**: 新增后端模块的测试覆盖率 ≥ 85%,包含单元测试 + 集成测试 + 契约测试
- **SC-009**: M18 能力诊断与 Interview Agent 报告的写入时序无竞态,并发场景下 100% 数据一致

## Assumptions

- 沿用 Phase 1/2/3/4 全部技术栈:FastAPI + PostgreSQL 15 + Redis 7 + ARQ + LangGraph + DeepSeek V4 Pro
- M14 LangGraph 基础设施(统一 LLM 客户端/checkpointer/WS 事件协议)已在 Phase 4 落地,Phase 5 直接复用
- M16 resume_optimize 使用 Phase 1 的 resume_lock(M12 锁服务);锁与现有编辑锁共用同一资源命名空间
- M17 error_coach 不持锁(错题无悲观锁),允许同一题多端同时练习
- M18 ability_diagnose 子图与 M15 Interview 子图完全独立,通过 query_* 工具读取业务表中转数据
- M18 的 aggregate_scores 工具从 interview_reports + ai_messages 读取,不直接调 LLM(仅聚合运算)
- M19 general_coach 不存储对话历史到业务表(仅 ai_messages 审计),用户需注意不输入 PII
- 所有 Agent 子图共享 Phase 4 的 token 配额池,预扣/实扣走统一 LLM 客户端
- M16 diff 粒度:MVP 块级(整块替换),v1.1 字段级;M16 多轮优化同样 v1.1
- M19 不支持嵌套 Agent(不跳转执行其他子图),仅给跳转引导
- 前端 M23 迁移沿用 `VITE_USE_MOCK` 回退模式,保留 mock 数据兼容
- 四个 Agent 子图的 prompts 复用 Phase 4 的 `.md` 模板模式,放在各自子图目录下
- 语音模式仍不涉及(Phase 6 范畴)
