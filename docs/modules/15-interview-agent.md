# M15 · Interview 子图

> 状态: draft · 所属领域: E · 优先级: P0
> 引用原文档: §7.1, §7.3 (interview 行), §7.5

## 1. 需求摘要

实现「**面试 Agent**」LangGraph 子图:从「启动 → 出题 → 等待回答 → 评分 → 下一题或结束 → 生成报告」全流程闭环。集成工具(query_resume / query_jd / record_score / evaluate_answer);LLM 流式 token 推 WS;结束时同步写 interview_reports + 异步触发 M18(Ability Diagnose)。

## 2. 验收标准

- [ ] `POST /api/v1/agents/interview/start` 启动子图(创建 session + 持锁 + 初始化 thread + 触发首个节点)
- [ ] `POST /api/v1/agents/interview/{thread_id}/messages` 追加用户回答
- [ ] `GET /api/v1/agents/interview/{thread_id}/state` 查询状态
- [ ] 节点流程:`intake → question_gen → wait_user → evaluate → next_or_finish → report`
- [ ] LLM 节点流式 token 推 WS `agent.{thread_id}/token.delta`
- [ ] 工具调用经 ToolNode → tool_call_logs 入库
- [ ] 终止条件:题目数达到 / 用户主动结束 / 超时 60min
- [ ] `report` 节点同步写 interview_reports(同事务)
- [ ] `report` 完成后触发 ARQ job `diagnose_after_interview(session_id)`(M18 接入)
- [ ] 释放悲观锁 + WS 广播 `lock.released`
- [ ] 答错的题目自动写入 error_questions(M08 接入)
- [ ] 单元测试:graph snapshot 测试(每个节点输入输出)
- [ ] 集成测试:5 题完整流程 + 断线重连

## 3. 依赖与被依赖关系

**强依赖**: M14(LangGraph 基建)、M11(interview_sessions)、M08(错题写入)、M12(悲观锁)
**弱依赖**: M18(下游异步触发)
**被以下模块依赖**: M18(读 session 数据)、M22(对账验证)、M23(前端面试页)
**外部依赖**: 无新增

## 4. 数据模型

无新表(全部复用 M11 / M14 / M08 表)。

**InterviewState TypedDict**(参见 §7.1):
```python
class InterviewState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID
    session_id: UUID
    position: str
    company: str
    jd: str  # 来自 query_jd 工具
    resume_snapshot: dict | None  # 来自 query_resume_blocks
    current_dimension: str  # 本轮考察维度
    questions_asked: list[Question]
    answers: list[Answer]
    per_question_score: list[float]
    elapsed_sec: int
    config: InterviewConfig  # 题目数 / 时长 / 模式
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/agents/interview/start` | 启动(创建 session+thread+lock) |
| POST | `/api/v1/agents/interview/{thread_id}/messages` | 用户回答 |
| GET | `/api/v1/agents/interview/{thread_id}/state` | 状态快照(断线恢复) |
| POST | `/api/v1/agents/interview/{thread_id}/abort` | 提前结束(标记 aborted) |

**WebSocket**: `agent.{thread_id}` 频道(由 M14 推送),9 个事件。
**工具使用**:
- `query_resume_blocks(branch_id)` 加载用户简历
- `query_jd(company, position)` 获取 JD
- `record_score(session_id, dimension, score, comment)` 记录评分
- `evaluate_answer(answer, ref_answer, dimension)` 评估回答

## 6. 关键设计点

- **graph 定义**(伪代码):
  ```python
  builder = StateGraph(InterviewState)
  builder.add_node("intake", intake_node)
  builder.add_node("question_gen", question_gen_node)
  builder.add_node("wait_user", wait_user_node)  # 阻塞等输入
  builder.add_node("evaluate", evaluate_node)
  builder.add_node("next_or_finish", route_node)
  builder.add_node("report", report_node)
  builder.add_edge(START, "intake")
  builder.add_edge("intake", "question_gen")
  builder.add_edge("question_gen", "wait_user")
  builder.add_edge("wait_user", "evaluate")
  builder.add_conditional_edges("evaluate", lambda s: ...)
  # next_or_finish → question_gen | report
  builder.add_edge("report", END)
  graph = builder.compile(checkpointer=checkpointer)
  ```
- **`wait_user` 节点**:不调 LLM,只等用户输入;通过 `interrupt_before=["wait_user"]` 实现「人在循环中」语义
- **题目数**:`config.question_count_target`(默认 5),`next_or_finish` 判定
- **超时巡检**:ARQ cron `*/5 * * * *` 扫 expired sessions → 强制 mark_aborted(M11)
- **answer ↔ message 双写**:LLM 输出问题时写一条 `ai_messages(role='ai', node='question_gen')`,用户答题写 `ai_messages(role='user', node='wait_user')`,评估写 `ai_messages(role='system', node='evaluate')`
- **错题入库**(M08 集成):`evaluate` 节点判定 score < 阈值时 `error_question_service.record_missed(...)`
- **触发 M18**:`report` 节点完成时 `await arq_pool.enqueue_job('diagnose_after_interview', session_id)`
- **锁释放**:`report` 节点末尾 `await lock_service.release('interview_session', session_id)` + WS 推 `lock.released`
- **`__version__ = "1.0.0"`** 字符串常量,M14 灰度参考

## 7. 待澄清

- **[A4]** 节点中途断线 token 重放策略 → 遵循 M14 决议
- **[A5]** ability_diagnose 数据传递 → 仅传 session_id,M18 自己查
- **[A6]** thread_id 派生 → 复用 session.id
- 评分阈值(< 60 入错题)需产品决议:MVP 用 60,可配置

## 8. 实现提示

- 文件:
  - `backend/app/agents/graphs/interview.py`
  - `backend/app/agents/nodes/interview/{intake,question_gen,evaluate,report}.py`
  - `backend/app/api/v1/agents.py`(start / messages / state / abort)
  - `backend/app/services/interview_agent_service.py`
- 复用: M14 runtime / state / tools / checkpoint;M11 InterviewService;M08 ErrorQuestionService;M12 LockService
- 与 mockData 关系:
  - `mockData.ts:169-273` `InterviewHistory.questions[]` → 由 question_gen 节点动态生成,落 ai_messages
  - `mockData.ts:204` `dimensions[]` → 由 evaluate 节点累积,report 节点合并到 interview_reports
