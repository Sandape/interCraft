# Interview Sessions REST API — Phase 4 扩展

> Phase 2 提供了只读 list/get(offset/limit)。Phase 4 扩展:CRUD 能力、游标分页、report 子资源、内部 API 落地。
> 原契约见 [specs/001-intercraft-product-spec/contracts/interview-sessions.md](../../001-intercraft-product-spec/contracts/interview-sessions.md)

## Phase 4 变更摘要

| 端点 | Phase 2 | Phase 4 |
|---|---|---|
| `GET /api/v1/interview-sessions` | offset/limit | **游标分页**(cursor),按 `-started_at` |
| `GET /api/v1/interview-sessions/{id}` | ✅ | ✅(不变) |
| `POST /api/v1/interview-sessions` | ❌ 405 | ✅ 创建 session + 初始化 LangGraph thread |
| `PATCH /api/v1/interview-sessions/{id}` | ❌ 405 | ✅ 更新 status/name 等 |
| `POST /.../sessions/{id}/start` | ❌ 405 | ✅ 启动面试(触发 LangGraph intake) |
| `GET /.../sessions/{id}/report` | ❌ 404 | ✅ 获取面试报告 |
| `POST /internal/interview-sessions` | ❌ 501 | ✅ 内部 API(Agent 调用) |

---

## 1. `POST /api/v1/interview-sessions`(Phase 4 新增)

**用途**:创建面试 session,初始化 LangGraph thread。

**Auth**:Bearer access

**请求体**:
```json
{
  "position": "高级前端工程师",
  "company": "字节跳动",
  "branch_id": "uuid (optional)",
  "mode": "text"
}
```

**验证**:
- `position`:必填,1-100 字符
- `company`:必填,1-100 字符
- `branch_id`:可选,必须是当前用户拥有的分支
- `mode`:固定 `"text"`(Phase 4)

**响应 201**:
```json
{
  "data": {
    "id": "uuid",
    "position": "高级前端工程师",
    "company": "字节跳动",
    "branch_id": "uuid",
    "mode": "text",
    "status": "pending",
    "thread_id": "uuid (LangGraph thread)",
    "created_at": "2026-06-13T08:00:00.000Z"
  }
}
```

**内部行为**:
1. 创建 `interview_sessions` 行(status=pending)
2. 初始化 LangGraph thread(调用 `graph.aget_state` 创建空 state)
3. 写入 `thread_id` 到 session 行
4. 返回 session 元数据

---

## 2. `POST /api/v1/interview-sessions/{id}/start`(Phase 4 新增)

**用途**:启动面试,触发 LangGraph intake 节点,开始 WS 事件推送。

**Auth**:Bearer access

**响应 202**:
```json
{
  "data": {
    "id": "uuid",
    "status": "in_progress",
    "started_at": "2026-06-13T08:00:01.000Z"
  }
}
```

**内部行为**:
1. 更新 `status = 'in_progress'`,`started_at = now()`
2. 异步触发 LangGraph intake 节点(run_in_executor)
3. WS 推送 `node.started(intake)` → `token.delta × N` → `node.completed(intake)`
4. 然后自动进入 question_gen 循环

**错误**:
- 409:session 状态不是 `pending`
- 429:token 配额不足(QuotaExceededError)

---

## 3. `GET /api/v1/interview-sessions/{id}/report`(Phase 4 新增)

**用途**:获取面试报告。

**Auth**:Bearer access

**响应 200**:
```json
{
  "data": {
    "id": "uuid",
    "session_id": "uuid",
    "overall_score": 7.25,
    "per_question_score": [
      {"question_no": 1, "dimension": "tech_depth", "score": 7.5, "feedback": "技术深度好..."},
      {"question_no": 2, "dimension": "architecture", "score": 6.5, "feedback": "架构能力需提升..."}
    ],
    "dimension_scores": {
      "tech_depth": 7.2,
      "architecture": 6.5,
      "engineering_practice": 7.8,
      "communication": 7.0,
      "algorithm": 6.8,
      "business_understanding": 8.0
    },
    "strengths": [
      {"dimension": "business_understanding", "score": 8.0, "detail": "..."}
    ],
    "improvements": [
      {"dimension": "architecture", "score": 6.5, "detail": "...", "suggestions": ["..."]}
    ],
    "summary_md": "# 面试报告\n\n本次面试...",
    "generated_at": "2026-06-13T08:25:00.000Z"
  }
}
```

**响应 404**:session 不存在或 report 未生成(session 未完成)

---

## 4. `POST /internal/interview-sessions/{id}/finish`(Phase 4 内部)

**用途**:Agent report 节点完成后调用的内部 API,写入 session 结束信息。

**Auth**:内部(127.0.0.1 / Docker 网络 IP 校验)

**请求体**:
```json
{
  "overall_score": 7.25,
  "duration_sec": 1380,
  "thread_id": "uuid"
}
```

**内部行为**:
1. 更新 `status = 'completed'`,`ended_at = now()`,`duration_sec`,`overall_score`
2. 发 ARQ 任务 `ability_diagnose`(异步,不阻塞响应)
3. 返回 200

---

## 5. 游标分页(Phase 4 升级)

`GET /api/v1/interview-sessions` Phase 4 切换为游标分页:

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `status` | enum | — | pending / in_progress / completed / expired |
| `cursor` | string(base64url) | — | 分页游标 |
| `limit` | int 1-50 | 20 | 分页大小 |

**响应 200**:
```json
{
  "data": [ /* InterviewSession[] */ ],
  "pagination": {
    "cursor": "base64url_next_page_cursor",
    "has_more": true,
    "limit": 20
  }
}
```

**排序**:`started_at DESC NULLS LAST, id DESC`(in_progress 优先于 pending,completed 末尾)
