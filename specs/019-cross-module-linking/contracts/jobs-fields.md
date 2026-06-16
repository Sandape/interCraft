# Contract: Job Fields Extension

**Feature**: 019-cross-module-linking | **Date**: 2026-06-17

> 本文档定义 `jobs` 表新增 5 列的端点契约。沿用 014 的端点签名(`/jobs`、`/jobs/{id}`、`PATCH /jobs/{id}`),仅扩展入参与出参。

## 1. 端点签名(无新增)

| Method | Path | 说明 |
|---|---|---|
| `POST` | `/jobs` | 创建 Job(扩展 5 字段入参) |
| `GET` | `/jobs` | 列出 Job(扩展 5 字段出参) |
| `GET` | `/jobs/{id}` | 详情 Job(扩展 5 字段出参) |
| `PATCH` | `/jobs/{id}` | 修改 Job(扩展 5 字段入参) |

(其他端点不动:`/jobs/{id}/timeline`、`/jobs/{id}/stats`、`/jobs/{id}/transitions`、`DELETE /jobs/{id}`)

## 2. 入参:`CreateJobInput` (扩展)

```python
class CreateJobInput(BaseModel):
    # 014 既有
    company: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=100)
    jd_url: str | None = Field(default=None, pattern=r'^https?://.*')
    branch_id: UUID | None = None
    notes_md: str | None = None

    # 019 新增
    base_location: str | None = Field(default=None, max_length=50)
    requirements_md: str | None = Field(default=None, max_length=5000)
    employment_type: Literal[
        "internship", "campus", "experienced", "contract", "unspecified"
    ] = "unspecified"
    salary_range_text: str | None = Field(default=None, max_length=100)
    headcount: int | None = Field(default=None, ge=1)
```

## 3. 入参:`PatchJobInput` (扩展)

```python
class PatchJobInput(BaseModel):
    # 014 既有(全部可空,None 表示不修改)
    company: str | None = Field(default=None, min_length=1, max_length=100)
    position: str | None = Field(default=None, min_length=1, max_length=100)
    jd_url: str | None = Field(default=None, pattern=r'^https?://.*')
    branch_id: UUID | None = None
    notes_md: str | None = None

    # 019 新增
    base_location: str | None = Field(default=None, max_length=50)
    requirements_md: str | None = Field(default=None, max_length=5000)
    employment_type: Literal[...] | None = None
    salary_range_text: str | None = Field(default=None, max_length=100)
    headcount: int | None = Field(default=None, ge=1)
```

## 4. 出参:`JobOut` (扩展)

```python
class JobOut(BaseModel):
    # 014 既有
    id: UUID
    user_id: UUID
    company: str
    position: str
    jd_url: str | None
    branch_id: UUID | None
    status: str
    status_history: list[dict]
    last_status_changed_at: datetime
    notes_md: str | None
    created_at: datetime
    updated_at: datetime

    # 019 新增
    base_location: str = ""                  # 默认 ''
    requirements_md: str | None = None
    employment_type: str = "unspecified"     # 默认 'unspecified'
    salary_range_text: str | None = None
    headcount: int | None = None

    model_config = {"from_attributes": True}
```

## 5. 校验规则

| 字段 | 规则 | 失败响应 |
|---|---|---|
| `base_location` | 1–50 字符;空字符串视为"未填",通过校验 | `422 Unprocessable Entity` `{detail: [{loc: ["body", "base_location"], msg: "String should have at most 50 characters"}]}` |
| `requirements_md` | ≤5000 字符;NULL 允许 | 同上 |
| `employment_type` | ∈ 5 枚举值 | 同上 |
| `salary_range_text` | ≤100 字符;NULL 允许 | 同上 |
| `headcount` | ≥1 整数;NULL 允许 | 同上 |

## 6. 前端 UI 文案(对齐 spec FR-026)

| 场景 | 文案 |
|---|---|
| `base_location` 为空 | "base 地: 未填写" |
| `base_location` 有值 | "base 地: 北京" |
| `requirements_md` 为空 | "招聘需求: 未填写" |
| `requirements_md` 有值 | 折叠卡片"招聘需求(点击展开)" |
| `employment_type = 'unspecified'` | "岗位类型: 未指定" |
| `employment_type = 'internship'` | "岗位类型: 实习" |
| `employment_type = 'campus'` | "岗位类型: 校招" |
| `employment_type = 'experienced'` | "岗位类型: 社招" |
| `employment_type = 'contract'` | "岗位类型: 合同" |
| `salary_range_text` 为空 | "薪资范围: 未填写" |
| `salary_range_text` 有值 | "薪资范围: 20-30K · 14薪" |
| `headcount` 为空 | 不展示 |
| `headcount` 有值 | "招聘人数: 5" |

## 7. 兼容性

- 既有 014 客户端在 Pydantic schema 扩展后,**零修改**:`CreateJobInput / PatchJobInput` 接受只传 014 既有字段;`JobOut` 解析时新增 5 字段默认为 `'' / NULL / 'unspecified'`。
- 既有 014 后端逻辑(状态机、时间线、outbox)不读取新增字段,行为不变。
- 014 `JobStatusBadge / NEXT_STATUS` 不读取新增字段,前端组件无须改动。

## 8. 验证场景

```bash
# 创建 job 不带 5 字段 → 成功,默认值
curl -X POST $BASE/jobs -H "Authorization: Bearer $TOKEN" \
  -d '{"company": "字节", "position": "前端"}'
# → 200,返回 JobOut 的 base_location="" / employment_type="unspecified" / 其他 NULL

# 创建 job 带 5 字段 → 成功,字段入库
curl -X POST $BASE/jobs -H "Authorization: Bearer $TOKEN" \
  -d '{"company":"字节","position":"前端","base_location":"北京",
       "requirements_md":"## 要求\n- 3年经验","employment_type":"experienced",
       "salary_range_text":"30-50K · 16薪","headcount":5}'
# → 200

# 校验失败:base_location 超长
curl -X POST $BASE/jobs -d '{"company":"x","position":"y","base_location":"$(printf 'a%.0s' {1..51})"}'
# → 422

# 校验失败:headcount = 0
curl -X POST $BASE/jobs -d '{"company":"x","position":"y","headcount":0}'
# → 422

# 校验失败:employment_type 非法
curl -X POST $BASE/jobs -d '{"company":"x","position":"y","employment_type":"foo"}'
# → 422
```
