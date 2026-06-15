# WebSocket Events: Interview Agent (M15)

> Phase 4 面试 WS 事件协议。WS 端点:`/api/v1/ws/interview?token=<JWT>`
> 复用 Phase 3 的 WS 连接管理器(单用户单连接)。面试事件与其他资源事件(锁)共用同一 WS 连接。

## 连接

**URL**:`wss://<host>/api/v1/ws/interview?token=<access_token>`

**Auth**:JWT access token 通过 query param 传递(Phase 1/3 一致)

**Heartbeat**:复用 Phase 3 锁心跳(同一 WS 连接,60s 间隔)

## 事件类型

### 1. `node.started`

节点开始执行。前端展示节点状态动画。

```json
{
  "type": "node.started",
  "event_id": "uuidv7",
  "session_id": "uuid",
  "timestamp": "2026-06-13T08:00:00.000Z",
  "node_name": "intake | question_gen | score | report",
  "payload": {
    "current_question": 1,
    "total_questions": 5
  }
}
```

- `node_name=intake`:`current_question=0`
- `node_name=question_gen`:`current_question=N`(即将生成的题号)
- `node_name=score`:`current_question=N`(正在评分的题号)
- `node_name=report`:无 `current_question`

### 2. `token.delta`

LLM 流式输出 token 片段。前端累积渲染逐字动画。

```json
{
  "type": "token.delta",
  "event_id": "uuidv7",
  "session_id": "uuid",
  "timestamp": "2026-06-13T08:00:01.500Z",
  "node_name": "question_gen | score | report",
  "payload": {
    "content": "面试",
    "index": 42
  }
}
```

- `content`:1-10 字符片段
- `index`:该节点流中的序号(从 0 开始,前端用于排序/去重)
- `node_name=question_gen`:token 是面试问题内容
- `node_name=score`:token 是评分反馈内容
- `node_name=report`:token 是报告摘要内容
- **不保证按 index 顺序到达**:前端需按 index 排序后再渲染

### 3. `node.completed`

节点执行完成。前端展示节点结果摘要。

```json
{
  "type": "node.completed",
  "event_id": "uuidv7",
  "session_id": "uuid",
  "timestamp": "2026-06-13T08:00:05.000Z",
  "node_name": "intake | question_gen | score | report",
  "payload": {
    "checkpoint_id": "uuid",
    "summary": {
      "intake": {"position": "高级前端工程师", "company": "字节跳动"},
      "question_gen": {"question_no": 2, "dimension": "architecture", "preview": "请描述你在项目中..."},
      "score": {"question_no": 2, "score": 7.5, "dimension": "architecture"},
      "report": {"overall_score": 7.2, "report_id": "uuid"}
    }
  }
}
```

- checkpoint_id:用于后续断线恢复,前端存储为 `last_seen_checkpoint_id`
- summary 内容按 node_name 不同

### 4. `error`

节点执行或系统错误。前端展示错误信息并引导下一步。

```json
{
  "type": "error",
  "event_id": "uuidv7",
  "session_id": "uuid",
  "timestamp": "2026-06-13T08:00:06.000Z",
  "node_name": "question_gen | score | report | system",
  "payload": {
    "code": "llm_timeout | quota_exceeded | llm_rate_limited | parse_error | internal_error",
    "message": "AI 响应超时,正在重试(1/3)…",
    "retryable": true,
    "retry_count": 1
  }
}
```

错误码:
- `llm_timeout`:LLM 调用超时(>30s),自动重试
- `quota_exceeded`:本月 token 配额用尽,不重试,引导升级
- `llm_rate_limited`:LLM 速率限制,自动重试(更长的退避)
- `parse_error`:LLM 返回格式异常,记录日志,降级继续
- `internal_error`:未知内部错误,记录日志,尝试恢复

## 客户端→服务端消息

### `reconnect`

断线后重连,携带最后已知 checkpoint。

```json
{
  "type": "reconnect",
  "session_id": "uuid",
  "last_seen_checkpoint_id": "uuid"
}
```

服务端响应:从 `last_seen_checkpoint_id` 恢复 LangGraph state,推送下一 `node.started` 事件。

### `submit_answer`

提交当前轮答案。

```json
{
  "type": "submit_answer",
  "session_id": "uuid",
  "sequence_no": 2,
  "content": "我认为 React 的 Fiber 架构..."
}
```

- `sequence_no`:当前题号(1-5),服务端用此去重

## 断线重连流程

```
Client                    Server
  │                          │
  │── WS disconnect ────────│  (网络断开/关闭 Tab)
  │                          │
  │── WS connect ──────────→│  (携带 token)
  │── reconnect ───────────→│  (携带 last_seen_checkpoint_id)
  │                          │
  │                    graph.aget_state(config)
  │                    恢复 state.values + state.next
  │                          │
  │←── node.started ───────│  (从下一节点推送)
  │←── token.delta × N ────│
  │←── node.completed ─────│
```

**关键规则**:
- 断线节点(收到部分 token.delta 的节点)的 partial tokens 被客户端丢弃
- 服务端从 checkpoint 重放完整节点(不是从断点续传)
- 已完成节点(有 checkpoint 的)不重放
