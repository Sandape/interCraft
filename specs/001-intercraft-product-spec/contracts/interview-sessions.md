# Interview Sessions Endpoints (M11)

> 面试会话 — **Phase 2 只读骨架**(澄清 Q3 决议 2026-06-13)。
> Phase 2 范围:表落地 + list/get 读 API,**无** create/update/delete。
> Phase 4 M15 Agent 启动时补 create/update。
> 数据模型见 [../data-model-phase-2.md](../data-model-phase-2.md) §8。

> ⚠️ **命名区分**:本文件 M11 interview_sessions(面试会话);[sessions.md](./sessions.md) M05 auth_sessions(设备/认证会话)。两者**完全不同**。

## 共享类型

```ts
type InterviewSession = {
  id: string;                           // uuid v7
  branch_id: string | null;             // 关联 resume_branches.id
  position: string | null;              // Phase 4 M15 启动时必填
  company: string | null;
  mode: "text" | "voice" | null;
  status: "pending" | "running" | "completed" | "aborted";
  thread_id: string | null;             // Phase 4 LangGraph thread_id
  checkpoint_ns: string | null;         // LangGraph checkpoint namespace
  started_at: string | null;
  ended_at: string | null;
  duration_sec: number | null;
  overall_score: number | null;         // 0.00-10.00
  created_at: string;
  updated_at: string;
}
```

---

## 1. `GET /api/v1/interview-sessions`

**用途**:列出当前用户的面试会话(可分页)。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `status` | enum | - | 过滤状态 |
| `branch_id` | uuid | - | 过滤关联分支 |
| `offset` | int ≥ 0 | 0 | Phase 2 简单 offset 分页(Phase 4 升游标) |
| `limit` | int 1-50 | 20 | 分页大小 |
| `order_by` | enum | `-started_at` | 排序:`-started_at` / `-created_at` |

**响应 200**:
```json
{
  "data": [ /* InterviewSession[] */ ],
  "pagination": {
    "offset": 0,
    "limit": 20,
    "total": 42
  }
}
```

**Phase 2 分页说明**:
- 用简单 offset/limit,Phase 4 M15 启动后切换到游标(消息流场景)
- offset 性能在小数据集可接受(每用户 ≤ 200,Phase 2 演示规模)

**排序规则**:`status ASC(running/pending 在前,completed/aborted 末尾), started_at DESC NULLS LAST`

---

## 2. `GET /api/v1/interview-sessions/{id}`

**用途**:获取单条面试会话详情。

**Auth**:Bearer access

**响应 200**:完整 `InterviewSession`

**响应 404**:不存在或 RLS 隔离

---

## 3. Phase 2 不开放(返回 405 Method Not Allowed)

### `POST /api/v1/interview-sessions`
- **Phase 4 启用**(M15 Agent 启动入口)
- Phase 2 行为:返回 405 + `Allow: GET` 头

### `PATCH /api/v1/interview-sessions/{id}`
- **Phase 4 启用**(用户可改 status 到 `aborted` 等)
- Phase 2 行为:405

### `DELETE /api/v1/interview-sessions/{id}`
- **Phase 6 启用**(M20 软删除)
- Phase 2 行为:405

### `POST /api/v1/interview-sessions/{id}/start` / `/finish` / `/abort`
- **Phase 4 启用**(M15 子图控制面)
- Phase 2 行为:405

**统一错误响应**:
```json
{
  "error": {
    "code": "method_not_allowed",
    "message": "Method POST is not supported for /api/v1/interview-sessions in Phase 2. Available in Phase 4 (M15 Agent).",
    "details": { "phase": 2, "available_in_phase": 4 }
  }
}
```
状态码 405 + `Allow: GET, OPTIONS` 头

---

## 4. 内部 API(非公开,Phase 2 占位)

> Phase 4 M15 Agent 启动时通过内部 API 创建 session。Phase 2 端点已挂占位路由,返回 501。

### `POST /internal/interview-sessions`(Phase 4 启用)

**Phase 2 行为**:返回 501 Not Implemented(路由占位但不实现 handler)

**用途**:
- M15 Agent 启动 session 时调用,创建 `interview_sessions` + 初始化 LangGraph thread
- 关联 `ai_conversations.thread_id`(M14)

### `PATCH /internal/interview-sessions/{id}`(Phase 4 启用)

**Phase 2 行为**:501

**用途**:
- Agent 推进 status(running → completed)
- 写 `started_at` / `ended_at` / `duration_sec` / `overall_score`

---

## 5. 状态机(Phase 4 启用,Phase 2 仅可读)

```
pending ──start──► running ──finish──► completed
                       │
                       └──abort──► aborted
```

**Phase 2 行为**:
- 表中所有行的 `status` 默认 `'pending'`
- 不开放任何转换 API
- 前端 InterviewList 页面 Phase 2 仍读 mockData(见 [phase-2.md](../phase-2.md) §0);Phase 4 切真实 API

---

## 6. 错误码

| 状态码 | 触发场景 |
|---|---|
| 400 | 字段类型错误 |
| 401 | JWT 缺失/过期 |
| 403 | RLS 拒绝 |
| 404 | session 不存在或 RLS 隔离 |
| **405** | **Phase 2 调用 POST/PATCH/DELETE(见 §3)** |
| **501** | **调用内部 API 端点(Phase 4 启用)** |
| 422 | 字段值越界 |
| 429 | 速率限制 |
| 500 | 服务端异常 |

---

## 7. Phase 2 vs Phase 4 迁移路径

| 维度 | Phase 2 | Phase 4 |
|---|---|---|
| 表存在 | ✅ | ✅ |
| list | ✅ offset/limit | ✅ 游标分页 |
| get | ✅ | ✅ |
| create(POST) | ❌ 405 | ✅ 内部 API |
| update status | ❌ 405 | ✅ PATCH /status |
| start/finish/abort | ❌ 405 | ✅ 内部 API |
| 关联 LangGraph thread | ❌(thread_id 列占位 NULL) | ✅ |
| WS 推送 | ❌ | ✅ node.* / token.* / interrupt |
| 报告生成 | ❌ | ✅ interview_reports 同步写 |
| 能力画像触发 | ❌ | ✅ ability_diagnose 异步触发 |

Phase 2 → Phase 4 切换时无需迁移(数据兼容,NULL 字段逐步填充)。
