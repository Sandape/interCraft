# Error Questions Endpoints (M08)

> 错题本 CRUD(Phase 2 数据源仅手动创建,澄清 Q4 决议 2026-06-13)。
> 数据模型见 [../data-model-phase-2.md](../data-model-phase-2.md) §2。

## 共享类型

```ts
type ErrorQuestion = {
  id: string;                           // uuid v7
  source_session_id: string | null;     // Phase 4 FR-040 写入;Phase 2 手动创建时为 null
  dimension: ErrorDimension | null;      // 6 维度之一(可空,DEC-P2-8)
  question_text: string;                // 1-2000 字符
  answer_text: string | null;
  reference_answer_md: string | null;   // Phase 5 Error Coach 写入
  score: number | null;                 // 0-10
  status: "fresh" | "practicing" | "mastered" | "archived";
  frequency: number;                    // 0-3
  tags: string[] | null;
  archived_at: string | null;
  last_practiced_at: string | null;
  created_at: string;
  updated_at: string;
}

type ErrorDimension =
  | "tech_depth"
  | "architecture"
  | "engineering_practice"
  | "communication"
  | "algorithm"
  | "business"

type CreateErrorQuestionInput = {
  dimension?: ErrorDimension | null;
  question_text: string;                // 1-2000
  answer_text?: string | null;
  reference_answer_md?: string | null;
  score?: number | null;                // 0-10
  tags?: string[] | null;
}

type PatchErrorQuestionInput = {
  dimension?: ErrorDimension | null;
  question_text?: string;
  answer_text?: string | null;
  reference_answer_md?: string | null;
  score?: number | null;
  status?: "fresh" | "practicing" | "mastered" | "archived";
  frequency?: number;                   // 0-3,status 转换时联动
  tags?: string[] | null;
}
```

---

## 1. `GET /api/v1/error-questions`

**用途**:列出当前用户的错题(可分页)。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `dimension` | enum | - | 过滤维度(6 维度之一) |
| `status` | enum | - | 过滤状态 |
| `frequency_min` | int 0-3 | 0 | 频次下限 |
| `cursor` | string | - | 游标分页(DEC-P2-1) |
| `limit` | int 1-50 | 20 | 分页大小 |
| `order_by` | enum | `-created_at` | 排序白名单:`-created_at` / `-updated_at` / `-last_practiced_at` / `-frequency` |

**响应 200**:
```json
{
  "data": [ /* ErrorQuestion[] */ ],
  "pagination": {
    "next_cursor": "opaque_or_null",
    "has_more": true
  }
}
```

**排序规则**:`status ASC, frequency DESC, created_at DESC`(让"高频未掌握"题优先)。

---

## 2. `POST /api/v1/error-questions`

**用途**:手动创建错题(Phase 2 数据源仅此一种)。

**Auth**:Bearer access

**请求体**:`CreateErrorQuestionInput`

**校验**:
- `question_text` 长度 1-2000
- `score` 0-10(可空)
- `dimension` 6 维度之一或 null

**响应 201**:完整 `ErrorQuestion` 对象

**副作用**:
- 写 `activities` 表 `type='error_logged'`(DEC-P2-4 触发器)
- 结构化日志 `error_question.created`

---

## 3. `GET /api/v1/error-questions/{id}`

**用途**:获取单条错题详情。

**Auth**:Bearer access

**响应 200**:完整 `ErrorQuestion` 对象

**响应 404**:RLS 强制空集(其他用户的错题不可见)

---

## 4. `PATCH /api/v1/error-questions/{id}`

**用途**:更新错题(改 status / frequency / 内容 / 标签 / 分数)。

**Auth**:Bearer access

**请求体**:`PatchErrorQuestionInput`

**校验**(DEC-P2-5 状态机):
- 合法转换见 [data-model-phase-2.md §2](../data-model-phase-2.md) 状态机
- 非法转换返回 409 Conflict `{error: {code: "invalid_state_transition", ...}}`
- `status='mastered'` MUST `frequency=0`
- `status='practicing'` MUST `frequency IN (1,2)`
- `status='fresh'` MUST `frequency=3`
- `status='archived'` → 软删?否:`archived` 是 status 值,`deleted_at` 仍 NULL(可恢复)

**响应 200**:更新后的 `ErrorQuestion`

**响应 409**:非法状态转换
```json
{
  "error": {
    "code": "invalid_state_transition",
    "message": "Cannot transition from 'mastered' to 'fresh' directly. Use 'reset' action.",
    "details": { "from": "mastered", "to": "fresh" }
  }
}
```

**副作用**:
- `last_practiced_at` 字段在 `practicing` 转换时自动更新
- 结构化日志 `error_question.updated` + 状态机转换记录

---

## 5. `DELETE /api/v1/error-questions/{id}`

**用途**:软删除(物理移除 = 软删)。

**Auth**:Bearer access

**响应 204**:No Content

**响应 404**:不存在或已删

**副作用**:
- 写 `deleted_at = now()`
- Repository 默认过滤(列表 API 看不到)
- 结构化日志 `error_question.soft_deleted`

---

## 6. `POST /api/v1/error-questions/{id}/reset`

**用途**:重置错题状态(从 `mastered` 反悔回 `fresh`,DEC-P2-5)。

**Auth**:Bearer access

**请求体**:无

**响应 200**:更新后的 `ErrorQuestion`
- `status='fresh', frequency=3`
- `last_practiced_at` 不变

**响应 409**:当前 status 不是 `mastered`

**副作用**:
- 写 `activities` 表 `type='task_completed' | manual` 或新 `error_reset` 类型(Phase 5 决议)
- Phase 2 简化为:`activities.type='error_logged', payload={action: 'reset', from: 'mastered'}`

---

## 7. 状态机 API 提示

前端可调用 `GET /api/v1/error-questions/{id}/transitions` 获取合法下一步(可选 Phase 2 端点):
```json
{
  "current": "practicing",
  "available": [
    { "action": "mark_mastered", "target": "mastered", "frequency": 0 },
    { "action": "reset", "target": "fresh", "frequency": 3 },
    { "action": "archive", "target": "archived" }
  ]
}
```

**Phase 2 实现**:可选,简化方案是前端本地 `reduce_status` 函数(spec M23 提示前端可独立验证)。

---

## 错误码

| 状态码 | 触发场景 |
|---|---|
| 400 | 字段类型错误(非 enum 等) |
| 401 | JWT 缺失/过期 |
| 403 | RLS 拒绝(用户访问他人错题) |
| 404 | 错题不存在或已删 |
| 409 | 状态机非法转换(见 PATCH 校验) |
| 422 | 字段语义错误(长度/范围) |
| 429 | 速率限制(>600 req/min) |
| 500 | 服务端异常 |

详见 [events.md](./events.md)。
