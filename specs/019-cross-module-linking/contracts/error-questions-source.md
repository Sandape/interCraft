# Contract: ErrorQuestion.source_question_id + clear-source

**Feature**: 019-cross-module-linking | **Date**: 2026-06-17

> 本文档定义 `error_questions` 表扩展 + 错题自动沉淀 + 移除自动来源端点契约。沿用 016 的 `error_questions` 表与 Recall/Reset/Delete 流程,仅扩展字段 + 新增 1 个端点(`PATCH /error-questions/{id}/clear-source`)。

## 1. 数据库扩展(详见 data-model.md §3)

- `error_questions.source_question_id` (UUID, FK `interview_questions.id`, nullable)
- `error_questions_source_question_id_idx` (B-tree)
- 部分唯一索引:`UNIQUE (source_question_id) WHERE source_question_id IS NOT NULL`

## 2. 端点签名

### 2.1 新增:`PATCH /error-questions/{id}/clear-source`

| 项 | 说明 |
|---|---|
| Method | `PATCH` |
| Path | `/error-questions/{id}/clear-source` |
| Auth | 当前用户必须拥有该 error_question |
| Body | 空 |
| 响应 | `200 OK` + 更新后的 `ErrorQuestionOut` |
| 副作用 | `source_session_id` 与 `source_question_id` 置 NULL,`updated_at` 更新 |

**响应示例**:
```json
{
  "id": "019xxx-yyy",
  "user_id": "019uuu-uuu",
  "source_session_id": null,
  "source_question_id": null,
  "dimension": "tech_depth",
  "question_text": "请解释一下 React Fiber 的调度原理",
  "answer_text": "...",
  "reference_answer_md": "...",
  "score": 4.5,
  "status": "fresh",
  "frequency": 3,
  "tags": ["auto-from-interview"],
  "created_at": "2026-06-17T10:30:00Z",
  "updated_at": "2026-06-17T11:00:00Z"
}
```

**错误码**:
| 场景 | HTTP | 错误码 |
|---|---|---|
| id 不存在 | 404 | `error_question_not_found` |
| id 属于其他 user | 404 | (与不存在同响应,避免泄露存在性) |
| 当前 `source_session_id` 已为 NULL | 400 | `source_already_cleared` |

### 2.2 扩展:`GET /error-questions` (扩展 `source` 查询参数)

| 项 | 说明 |
|---|---|
| Method | `GET` |
| Path | `/error-questions` |
| Query 参数 | `?source=auto|manual|all`(默认 `all`) |
| 过滤逻辑 | `source=auto` → `source_session_id IS NOT NULL`;`source=manual` → `source_session_id IS NULL`;`source=all` → 不过滤 |

**响应**:与 016 既有 `ErrorQuestionListOut` 相同 schema,只增加 `source_question_id` 字段输出。

### 2.3 扩展:`POST /error-questions` (扩展 `source_question_id` 入参)

支持手动创建错题时携带 `source_question_id`(可选,用于用户从面试报告手动标注某题进错题本)。

### 2.4 沿用:016 既有端点

| Method | Path | 019 行为 |
|---|---|---|
| `GET /error-questions/{id}` | 详情 | 扩展输出 `source_question_id` |
| `PATCH /error-questions/{id}` | 修改 | 允许修改 `source_question_id`(可选) |
| `DELETE /error-questions/{id}` | 删除 | **沿用**,不修改 |
| `POST /error-questions/{id}/recall` | 答对一次 | **沿用**,不修改 |
| `POST /error-questions/{id}/reset` | 重置 | **沿用**,不修改 |

## 3. 出参:`ErrorQuestionOut` (扩展)

```python
class ErrorQuestionOut(BaseModel):
    # 016 既有
    id: UUID
    user_id: UUID
    source_session_id: UUID | None          # 016 已有
    dimension: str | None
    question_text: str
    answer_text: str | None
    reference_answer_md: str | None
    score: int | None
    status: str
    frequency: int
    tags: list[str] | None
    archived_at: datetime | None
    last_practiced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # 019 新增
    source_question_id: UUID | None = None
```

## 4. 错题自动沉淀(后端内部,不暴露 API)

**触发位置**:`backend/app/agents/score/nodes.py` 在写入 `interview_questions.score` 后同步调用。

**函数签名**:
```python
# backend/app/modules/errors/service.py
AUTO_ERROR_THRESHOLD = 6

async def maybe_create_from_question(
    *,
    user_id: UUID,
    session_id: UUID,
    question_id: UUID,
    score: int,
    dimension: str | None,
    question_text: str,
    answer_text: str | None,
    reference_answer_md: str | None,
    db: AsyncSession,
) -> ErrorQuestion | None:
    """若 score < AUTO_ERROR_THRESHOLD 则 UPSERT 一条错题,否则返回 None。
    
    UPSERT 逻辑:INSERT INTO error_questions (...) ON CONFLICT (source_question_id)
    WHERE source_question_id IS NOT NULL DO UPDATE SET score=..., answer_text=...,
    reference_answer_md=..., updated_at=now();
    """
```

**幂等保证**:由部分唯一索引 + ON CONFLICT DO UPDATE 保证。

**记录溯源日志**:
```python
logger.info(
    "auto_error_created",
    user_id=str(user_id),
    session_id=str(session_id),
    question_id=str(question_id),
    score=score,
    error_question_id=str(new_or_updated.id),
)
```

## 5. 前端 UI 文案(对齐 spec FR-019 / FR-026)

| 场景 | 文案 |
|---|---|
| 详情面板 source_session_id 非空 | 静态文案:"来自 {company} · {position} · {interview_started_at YYYY-MM-DD HH:mm}" |
| 移除自动来源按钮 | "移除自动来源" |
| 移除自动来源 Toast | "已移除自动来源" |
| 删除按钮(source 非空) | "删除『来自 {company} · {position} · {interview_started_at} 的错题』" |
| 删除按钮(source 为空) | "删除『{question_text 前 30 字}』"(016 既有) |
| 列表筛选 source=auto | "来自面试" |
| 列表筛选 source=manual | "手动录入" |
| 列表筛选 source=all | "全部" |

## 6. 兼容性

- 既有 016 客户端在 schema 扩展后,**零修改**:`ErrorQuestionOut` 解析时新增 `source_question_id` 默认为 NULL;`GET /error-questions` 不带 `source` 参数时默认 `all`,行为不变。
- 既有 016 Recall/Reset/Delete 流程不读取新增字段,行为不变。

## 7. 验证场景

```bash
# 1. 模拟 score < 6 触发自动沉淀
curl -X POST $BASE/interview-sessions -d '{"position":"前端","company":"字节"}'
# → session_id = "s1"

# (Phase 4 mock LLM 答 5 题,其中 1 题返回 score=3.5)

# 2. 查错题本
curl $BASE/error-questions -H "Authorization: Bearer $TOKEN"
# → 至少 1 条 source_session_id == "s1" 的错题

# 3. 筛选 auto
curl "$BASE/error-questions?source=auto" -H "Authorization: Bearer $TOKEN"
# → 仅返回 source_session_id 非空的错题

# 4. 筛选 manual
curl "$BASE/error-questions?source=manual" -H "Authorization: Bearer $TOKEN"
# → 仅返回 source_session_id 为 NULL 的错题

# 5. 移除自动来源
curl -X PATCH $BASE/error-questions/<id>/clear-source \
  -H "Authorization: Bearer $TOKEN"
# → 200,source_session_id 与 source_question_id 都为 NULL

# 6. 删除错题(沿用 016)
curl -X DELETE $BASE/error-questions/<id> \
  -H "Authorization: Bearer $TOKEN"
# → 200 / 204,deleted_at 置位

# 7. 重评不重复创建(ON CONFLICT DO UPDATE)
# (再次触发同 question_id 的 score=2.0)
# → 仍然只有 1 条错题(同 id),score 更新为 2.0
```
