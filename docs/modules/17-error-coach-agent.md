# M17 · Error Coach 子图

> 状态: draft · 所属领域: E · 优先级: P2
> 引用原文档: §7.3 (error_coach 行), §7.5

## 1. 需求摘要

实现「**错题强化 Agent**」LangGraph 子图:针对单个错题,通过梯度提示(easy → medium → hard)引导用户重新作答;答对 3 次后结束;同时减少错题 frequency。每次启动新 thread(参见 A7)。

## 2. 验收标准

- [ ] `POST /api/v1/agents/error-coach/start` 启动(error_question_id)
- [ ] 节点流程:`fetch_question → hint_ladder → wait_user → evaluate → loop_or_finish`
- [ ] 提示梯度:第 1 次答错给小提示 / 第 2 次给中等提示 / 第 3 次给详细提示
- [ ] 终止:答对 3 次 / 用户退出 / 10 分钟超时
- [ ] 答对 → 调 M08 `recall` 接口减 frequency
- [ ] 不持锁(错题强化是只读 + 写入错题元数据,允许并发)
- [ ] 每次启动创建新 thread,thread_id = `f"{user_id}:{error_question_id}:{started_at_ms}"`
- [ ] 集成测试:3 次答对完整流程

## 3. 依赖与被依赖关系

**强依赖**: M14(LangGraph 基建)、M08(错题本)
**弱依赖**: 无
**被以下模块依赖**: M23(前端错题强化页)
**外部依赖**: 无

## 4. 数据模型

无新表。

**ErrorCoachState**:
```python
class ErrorCoachState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID
    error_question_id: UUID
    question: ErrorQuestion  # 来自 query_error_book(单条)
    correct_count: int
    attempt_count: int
    current_hint_level: Literal["small", "medium", "detailed"]
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/agents/error-coach/start` | 启动 |
| POST | `/api/v1/agents/error-coach/{thread_id}/messages` | 用户回答 |
| POST | `/api/v1/agents/error-coach/{thread_id}/abort` | 退出 |
| GET | `/api/v1/agents/error-coach/{thread_id}/state` | 状态快照 |

**WebSocket**: `agent.{thread_id}` 频道(M14 推送)

**工具**:
- `query_error_book(user_id, category=None, limit=1)` 获取题目(可改为 `query_error_question_by_id`)
- `evaluate_answer(answer, ref_answer, dimension)` 评估

## 6. 关键设计点

- **不持锁**:错题强化无独占性,允许同一题多端同时练(各自独立 thread)
- **梯度提示**:由 `hint_ladder` 节点根据 `attempt_count` 选 hint 级别,提示内容由 LLM 基于 question.hint + ref answer 生成
- **答对判定**:`evaluate_answer` 返回 `score`,阈值 ≥ 80 视为答对
- **3 次后结束**:不需要连续 3 次,只要累计答对 3 次
- **frequency-- 时机**:每答对 1 次调一次 M08 `recall`(累计 3 次 → frequency 减 3),但不允许低于 0
- **__version__ = "1.0.0"**

## 7. 待澄清

- **[A7]** thread_id 派生 → 每次创建新 thread
- 提示梯度的具体内容是否需要 admin 可配置:MVP 全 AI 生成,v1.1 加可编辑模板
- 超时 10min 是否过短:产品决议

## 8. 实现提示

- 文件:
  - `backend/app/agents/graphs/error_coach.py`
  - `backend/app/agents/nodes/error_coach/{fetch_question,hint_ladder,evaluate,loop_or_finish}.py`
  - `backend/app/api/v1/agents_error_coach.py`
- 复用: M14 runtime;M08 ErrorQuestionService(record_missed / recall)
- 与 mockData 关系:`mockData.ts:276-323` ErrorQuestion 字段全可用
