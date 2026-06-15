# M19 · General Coach 子图

> 状态: draft · 所属领域: E · 优先级: P2
> 引用原文档: §7.3 (general_coach 行), §7.5

## 1. 需求摘要

实现「**通用辅导 Agent**」LangGraph 子图:无业务锚点的通用问答 / 职业咨询;通过 `intent → route → respond` 节点路由意图,可能分发到子图(如「帮我优化简历」→ 提示用户跳转到 resume_optimize)。是一个意图分类 + 通用问答的轻量 Agent。

## 2. 验收标准

- [ ] `POST /api/v1/agents/general-coach/start` 启动(可选携带初始问题)
- [ ] 节点流程:`intent → route → respond`
- [ ] `intent` 节点分类用户意图(LLM 评估):resume_optimize / interview_practice / career_advice / chitchat
- [ ] `route` 节点根据意图 → 走 `respond` 通用回答 OR 返回「建议跳转到 X 子图」的引导
- [ ] LLM 流式 token 推 WS
- [ ] 用户关闭即结束,无强制终止条件
- [ ] thread_id 派生:`conversation_id`(uuid 新生成,无业务锚点)
- [ ] 集成测试:几种意图分类的端到端

## 3. 依赖与被依赖关系

**强依赖**: M14(LangGraph 基建)
**弱依赖**: 无
**被以下模块依赖**: M23(前端通用助手聊天)
**外部依赖**: 无

## 4. 数据模型

无新表。

**GeneralCoachState**:
```python
class GeneralCoachState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: UUID
    conversation_id: UUID  # = thread_id
    detected_intent: str | None
    suggested_redirect: str | None  # 子图名,如 "resume_optimize"
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/agents/general-coach/start` | 启动 |
| POST | `/api/v1/agents/general-coach/{thread_id}/messages` | 追加消息 |
| GET | `/api/v1/agents/general-coach/{thread_id}/state` | 状态 |
| POST | `/api/v1/agents/general-coach/{thread_id}/close` | 用户关闭 |

**WebSocket**: `agent.{thread_id}` 频道

**工具使用**: 通用 Agent 不强制调工具,但可以可选调 `query_resume_blocks` / `query_history` 增强上下文

## 6. 关键设计点

- **意图分类**:LLM 输出结构化结果 `{intent: enum, confidence: 0-1, reasoning: str}`
- **路由策略**:意图明确(confidence > 0.7)→ 给出「建议跳转」+ 一句话回答;意图模糊 → 直接通用回答
- **不持锁**:通用对话无独占性
- **无超时**:用户关闭即结束,后端可设软超时(2 小时无活动自动结束)
- **__version__ = "1.0.0"**
- **可观测**:意图分类的准确率是关键指标,记录每次意图判定到 tool_call_logs(虽然不是工具,但作为 LLM 调用结果)

## 7. 待澄清

- **[A6]** thread_id 派生 → 新生成 uuid
- 多轮对话上下文长度限制:超过 N 轮(如 30)是否自动 summarize 压缩
- 通用 Coach 是否允许调用其他 Agent 子图(嵌套 Agent):MVP 不支持,只给跳转建议

## 8. 实现提示

- 文件:
  - `backend/app/agents/graphs/general_coach.py`
  - `backend/app/agents/nodes/general_coach/{intent,route,respond}.py`
  - `backend/app/api/v1/agents_general_coach.py`
- 复用: M14 runtime
- 与 mockData 关系:无(全新)
