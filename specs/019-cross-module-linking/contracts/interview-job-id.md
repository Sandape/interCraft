# Contract: InterviewSession.job_id

**Feature**: 019-cross-module-linking | **Date**: 2026-06-17

> 本文档定义 `interview_sessions.job_id` 列扩展的端点契约。沿用 Phase 4 的端点签名(`POST /interview-sessions`、`GET /interview-sessions`、`GET /interview-sessions/{id}`),仅扩展入参与出参。

## 1. 端点签名(无新增)

| Method | Path | 说明 |
|---|---|---|
| `POST` | `/interview-sessions` | 创建 interview session(扩展 `job_id` 入参) |
| `GET` | `/interview-sessions` | 列出 session(扩展 `job_id` 出参) |
| `GET` | `/interview-sessions/{id}` | 详情 session(扩展 `job_id` 出参) |

(其他端点不动:`/interview-sessions/{id}/resume`、`/interview-sessions/{id}/start`、`/interview-sessions/{id}/report`、`DELETE /interview-sessions/{id}`)

## 2. 入参:`InterviewSessionCreate` (扩展)

```python
class InterviewSessionCreate(BaseModel):
    # Phase 4 既有
    position: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    branch_id: UUID | None = None
    mode: str | None = Field(default=None, max_length=20)

    # 019 新增
    job_id: UUID | None = None
```

## 3. 出参:`InterviewSessionOut` (扩展)

```python
class InterviewSessionOut(BaseModel):
    # Phase 4 既有
    id: UUID
    user_id: UUID
    position: str | None
    company: str | None
    branch_id: UUID | None
    mode: str | None
    status: str
    overall_score: float | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
    created_at: datetime
    updated_at: datetime

    # 019 新增
    job_id: UUID | None = None
```

## 4. 出参:`InterviewSessionStartOut` (扩展)

```python
class InterviewSessionStartOut(BaseModel):
    id: UUID
    status: str
    thread_id: str
    checkpoint_ns: str

    # 019 新增
    job_id: UUID | None = None
    branch_id: UUID | None = None
```

## 5. 校验规则

| 字段 | 规则 | 失败响应 |
|---|---|---|
| `job_id` | UUID 格式;若提供,服务端校验存在 + 同属当前 user | `422 Unprocessable Entity` `{detail: "Job 不存在或不属于当前用户"}` |
| `branch_id` | UUID 格式;若提供,服务端校验存在 + 同属当前 user | `422` (Phase 4 既有) |
| `job_id` + `branch_id` 同时提供 | 服务端校验 job 的 branch_id == 入参 branch_id(若 job 已有绑定) | `422` `{detail: "branch_id 与 job.branch_id 不一致"}` |

## 6. 「为该岗位开始模拟面试」调用示例

```bash
# 假设 job_id = "019xxx-yyy" 且 job.branch_id = "019aaa-bbb"
curl -X POST $BASE/interview-sessions \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "job_id": "019xxx-yyy",
    "branch_id": "019aaa-bbb",
    "position": "前端工程师",   # 可被 Intake 阶段预填覆盖
    "company": "字节"           # 可被 Intake 阶段预填覆盖
  }'
# → 200
# {
#   "id": "019sss-zzz",
#   "job_id": "019xxx-yyy",
#   "branch_id": "019aaa-bbb",
#   "status": "pending",
#   "thread_id": "...",
#   "checkpoint_ns": "..."
# }
```

## 7. 错误码

| 场景 | HTTP | 错误码 |
|---|---|---|
| `job_id` 不存在 | 422 | `job_not_found` |
| `job_id` 存在但属于其他 user | 422 | `job_not_owned` |
| `job_id` 与 `branch_id` 不一致 | 422 | `branch_id_mismatch` |
| `branch_id` 不存在 | 422 | `branch_not_found` (Phase 4 既有) |
| `branch_id` 已被软删 | 422 | `branch_deleted` |

## 8. Intake 阶段预填(后端不做,前端做)

后端 `POST /interview-sessions` **不**自动从 `jobs` 表读取字段预填。前端 Intake 阶段调用 `GET /jobs/{job_id}` 取元数据并预填表单(详见 contracts/requirements-md-prompt.md)。

## 9. 兼容性

- 既有 Phase 4 客户端调用 `POST /interview-sessions` 不带 `job_id` → 服务端接受,字段为 NULL(向后兼容)。
- 既有 Phase 4 后端逻辑不读取 `job_id`,行为不变。
- WS 事件流(`node.started / token.delta / node.completed`)不携带 `job_id`(前端若需要从 GraphState 读取)。

## 10. 验证场景

```bash
# 不带 job_id(向后兼容)
curl -X POST $BASE/interview-sessions -d '{"position":"前端","company":"字节"}'
# → 200,返回的 session.job_id = NULL

# 带合法 job_id
curl -X POST $BASE/interview-sessions -d '{"job_id":"<valid>","branch_id":"<valid>"}'
# → 200

# job_id 不存在
curl -X POST $BASE/interview-sessions -d '{"job_id":"00000000-0000-0000-0000-000000000000"}'
# → 422 {"detail": "Job 不存在或不属于当前用户"}

# job.branch_id != 入参 branch_id
curl -X POST $BASE/interview-sessions -d '{"job_id":"<job_a>","branch_id":"<branch_b>"}'
# → 422 {"detail": "branch_id 与 job.branch_id 不一致"}
```
