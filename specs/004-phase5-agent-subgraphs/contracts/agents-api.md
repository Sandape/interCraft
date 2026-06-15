# Agent API 契约: M16 / M17 / M19

**Date**: 2026-06-15 | **Spec**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

本文档定义 Phase 5 三个同步 Agent 子图的 REST API 契约。M18 Ability Diagnose 为纯异步(ARQ 触发),参见 [ability-diagnose.md](./ability-diagnose.md)。

所有端点继承 Phase 1 鉴权(JWT Bearer token,通过 `Authorization` header)。

---

## M16 · Resume Optimize

### POST /api/v1/agents/resume-optimize/start

启动简历优化 Agent。如果目标简历分支已被其他端持锁,返回 423。

**Request**:
```json
{
  "branch_id": "uuid",
  "target_jd": "string (可选,JD 描述)",
  "company": "string (可选,当未传 target_jd 时使用)",
  "position": "string (可选,当未传 target_jd 时使用)"
}
```

**Response 201**:
```json
{
  "thread_id": "uuid",
  "status": "running",
  "current_node": "load_branch"
}
```

**Response 423** (锁冲突):
```json
{
  "detail": "Resume branch is locked by another session"
}
```

### POST /api/v1/agents/resume-optimize/{thread_id}/confirm

解决 interrupt,提交用户决策。

**Request**:
```json
{
  "decision": "apply | discard"
}
```

**Response 200**:
```json
{
  "thread_id": "uuid",
  "status": "completed",
  "decision": "apply | discard",
  "version_id": "uuid | null"
}
```

### GET /api/v1/agents/resume-optimize/{thread_id}/state

获取状态快照。

**Response 200**:
```json
{
  "thread_id": "uuid",
  "status": "running | waiting_interrupt | completed | aborted | timeout",
  "current_node": "string | null",
  "summary": "string | null",
  "proposed_patches": ["array | null"]
}
```

### WS Event: `interrupt`

通过 Phase 4 WS 通道推送(复用 `agent.{thread_id}` 频道):

```json
{
  "event": "interrupt",
  "thread_id": "uuid",
  "graph": "resume_optimize",
  "node": "apply_or_discard",
  "data": {
    "proposed_patches": [{"op": "replace", "path": "/blocks/0/content", "value": "..."}],
    "summary": "AI 建议:加强项目描述、调整技能顺序"
  }
}
```

---

## M17 · Error Coach

### POST /api/v1/agents/error-coach/start

启动错题强化 Agent。

**Request**:
```json
{
  "error_question_id": "uuid"
}
```

**Response 201**:
```json
{
  "thread_id": "uuid",
  "status": "running",
  "current_node": "fetch_question"
}
```

### POST /api/v1/agents/error-coach/{thread_id}/messages

用户提交一轮回答。

**Request**:
```json
{
  "content": "string (用户回答)"
}
```

**Response 200**:
```json
{
  "thread_id": "uuid",
  "status": "running | completed | aborted",
  "current_node": "evaluate | loop_or_finish",
  "score": 8,
  "correct_count": 2,
  "hint_level": "small | medium | detailed",
  "hint_content": "string (下一轮提示内容)"
}
```

### POST /api/v1/agents/error-coach/{thread_id}/abort

用户主动退出。

**Response 200**:
```json
{
  "thread_id": "uuid",
  "status": "aborted",
  "correct_count_achieved": 2
}
```

### GET /api/v1/agents/error-coach/{thread_id}/state

**Response 200**:
```json
{
  "thread_id": "uuid",
  "status": "running | completed | aborted",
  "correct_count": 2,
  "attempt_count": 3,
  "current_hint_level": "medium"
}
```

---

## M19 · General Coach

### POST /api/v1/agents/general-coach/start

启动通用辅导 Agent,可选携带初始问题。

**Request**:
```json
{
  "initial_question": "string (可选)"
}
```

**Response 201**:
```json
{
  "thread_id": "uuid",
  "conversation_id": "uuid",
  "status": "running"
}
```

### POST /api/v1/agents/general-coach/{thread_id}/messages

追加用户消息,返回 Agent 流式回答(通过 WS)。

**Request**:
```json
{
  "content": "string"
}
```

**Response 200**:
```json
{
  "thread_id": "uuid",
  "detected_intent": "resume_optimize | interview_practice | career_advice | chitchat",
  "confidence": 0.92,
  "redirect_to": "string | null"
}
```

### POST /api/v1/agents/general-coach/{thread_id}/close

用户关闭对话。

**Response 200**:
```json
{
  "thread_id": "uuid",
  "status": "closed"
}
```

### GET /api/v1/agents/general-coach/{thread_id}/state

**Response 200**:
```json
{
  "thread_id": "uuid",
  "detected_intent": "string | null",
  "message_count": 5,
  "session_active": true
}
```
