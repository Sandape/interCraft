# Tasks Endpoints (M10 tasks)

> 任务列表 — 自动触发(Jobs 状态变更时)+ 手动创建。
> 幂等键:DB `UNIQUE (user_id, type, related_entity_id)` + service `find_or_create`(澄清 Q2 决议 2026-06-13)。
> 数据模型见 [../data-model-phase-2.md](../data-model-phase-2.md) §5。

## 共享类型

```ts
type Task = {
  id: string;                           // uuid v7
  type: TaskType;
  title: string;                        // 1-200 字符
  description_md: string | null;
  related_entity_type: "job" | "branch" | "error_question" | null;
  related_entity_id: string | null;     // 多态关联
  status: "todo" | "doing" | "done" | "archived";
  due_at: string | null;
  completed_at: string | null;
  auto_generated: boolean;
  created_at: string;
  updated_at: string;
}

type TaskType =
  | "interview_prep"                    // 准备 X 公司面试
  | "branch_optimize"                   // 简历分支优化
  | "application_followup"              // 投递跟进
  | "manual"                            // 用户手动

type CreateTaskInput = {
  type?: TaskType;                      // 默认 'manual'
  title: string;                        // 1-200
  description_md?: string | null;
  related_entity_type?: "job" | "branch" | "error_question" | null;
  related_entity_id?: string | null;
  due_at?: string | null;
}

type PatchTaskInput = {
  title?: string;
  description_md?: string | null;
  status?: "todo" | "doing" | "done" | "archived";
  due_at?: string | null;
}
```

---

## 1. `GET /api/v1/tasks`

**用途**:列出当前用户任务(可分页)。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `type` | enum | - | 过滤任务类型 |
| `status` | enum | - | 过滤状态 |
| `auto_generated` | bool | - | 过滤自动/手动 |
| `related_entity_type` | enum | - | 过滤关联实体类型 |
| `related_entity_id` | uuid | - | 过滤关联实体 |
| `cursor` | string | - | 游标分页(DEC-P2-1) |
| `limit` | int 1-50 | 20 | 分页大小 |
| `order_by` | enum | `-due_at` | 排序白名单:`-due_at` / `-created_at` / `-updated_at` |

**响应 200**:
```json
{
  "data": [ /* Task[] */ ],
  "pagination": {
    "next_cursor": "opaque_or_null",
    "has_more": true
  }
}
```

**排序规则**:`status ASC(archived 在最后), due_at ASC NULLS LAST, created_at DESC`。

---

## 2. `POST /api/v1/tasks`

**用途**:创建任务(手动)。

**Auth**:Bearer access

**请求体**:`CreateTaskInput`

**校验**:
- `type='manual'` 时,`related_entity_type` / `related_entity_id` 必为 null
- `type!='manual'` 时,可关联实体(可选,允许 null 表示「系统任务未挂实体」)
- `title` 长度 1-200
- `due_at` 必须为未来时间(可空)

**幂等行为**(DEC-P2-3):
- 若 `(user_id, type, related_entity_id)` 已存在(task 与 jobs 关联)→ 返回已存在 task,不改 title(防 race condition)
- 409 不抛出(幂等优先于 409);仅在并发竞争 + `IntegrityError` 兜底时返回 409

**响应 201**:完整 `Task`

**副作用**:
- `auto_generated=false`(用户手动)
- 写 `activities` 表 `type='task_created'`
- 结构化日志 `task.created`

---

## 3. `GET /api/v1/tasks/{id}`

**用途**:获取单条任务详情。

**Auth**:Bearer access

**响应 200**:完整 `Task`

**响应 404**:不存在或 RLS 隔离

---

## 4. `PATCH /api/v1/tasks/{id}`

**用途**:更新任务(改 status / title / due_at / description)。

**Auth**:Bearer access

**请求体**:`PatchTaskInput`

**校验**:
- `status='done'` 时自动 `completed_at = now()`
- `status='doing' | 'todo' | 'archived'` 时清 `completed_at`
- 不可改 `type` / `related_entity_*`(创建时锁定)
- 不可改 `auto_generated`(系统字段)

**状态机**:
```
todo → doing → done (→ 反悔回 doing)
 任意状态 → archived
```

**响应 200**:更新后的 `Task`

**副作用**:
- `status='done'` → 写 `activities` 表 `type='task_completed'`
- 其他 status 变化 → 不写 activity(M10 决议,避免噪声)
- 结构化日志 `task.updated`

---

## 5. `DELETE /api/v1/tasks/{id}`

**用途**:软删除任务。

**Auth**:Bearer access

**响应 204**

**副作用**:
- 写 `deleted_at = now()`
- Repository 默认过滤
- 结构化日志 `task.soft_deleted`

---

## 6. 内部 API(非公开)

> 供 JobService 在状态变更时调用,不在 OpenAPI 公开。

### `POST /internal/tasks/find-or-create`

**Auth**:Internal(middleware 校验 source IP = api 进程)

**请求体**:
```json
{
  "user_id": "uuid",
  "type": "interview_prep",
  "related_entity_id": "uuid",
  "title": "准备字节 · 高级前端工程师 面试",
  "update_title_if_exists": true
}
```

**响应 200**:`Task`(已存在或新建)

**行为**:
- 优先 SELECT(快路径)
- 失败时 INSERT + `IntegrityError` 兜底(并发竞争)
- `update_title_if_exists=true` 时,若任务存在,更新 title(用于 Job 状态推进时刷新提示)
- 结构化日志 `task.duplicate_skipped`(若已存在)

---

## 错误码

| 状态码 | 触发场景 |
|---|---|
| 400 | 字段类型错误 |
| 401 | JWT 缺失/过期 |
| 403 | RLS 拒绝 |
| 404 | 任务不存在或已删 |
| 409 | 并发竞争(罕见,`IntegrityError` 兜底) |
| 422 | 字段值越界(title 长度等) |
| 429 | 速率限制 |
| 500 | 服务端异常 |
