# Abilities Endpoints (M09)

> 能力画像 — 6 维度(技术深度/架构能力/工程实践/沟通表达/算法能力/业务理解)。
> Phase 2 写路径:注册时 seed(自动) + 用户手动 PATCH 校正;读路径完整。
> 数据模型见 [../data-model-phase-2.md](../data-model-phase-2.md) §3-4。

## 共享类型

```ts
type SubScore = {
  actual: number;                       // 0.00-10.00
  ideal: number;                        // 0.00-10.00
}

type AbilityDimension = {
  id: string;                           // uuid v7
  dimension_key: AbilityDimensionKey;
  actual_score: number;                 // 0.00-10.00
  ideal_score: number;                  // 0.00-10.00
  sub_scores: {                         // JSONB,DEC-P2-2 18 子项
    [sub_key: string]: SubScore;
  };
  is_active: boolean;                   // 用户可禁用某维度
  source: "manual" | "interview" | "error" | "coach";
  last_updated_at: string;
  created_at: string;
  updated_at: string;
}

type AbilityDimensionKey =
  | "tech_depth"
  | "architecture"
  | "engineering_practice"
  | "communication"
  | "algorithm"
  | "business"

type AbilityHistoryPoint = {
  snapshot_date: string;                // YYYY-MM-DD
  aggregate: "month" | "day";
  actual_score: number;
  ideal_score: number;
}

type PatchAbilityDimensionInput = {
  actual_score?: number;                // 0.00-10.00
  ideal_score?: number;                 // 0.00-10.00
  sub_scores?: { [sub_key: string]: SubScore };
  is_active?: boolean;
}
```

---

## 1. `GET /api/v1/ability-dimensions`

**用途**:列出当前用户的 6 维度画像。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `is_active` | bool | - | 过滤启用状态 |

**响应 200**:
```json
{
  "data": [ /* AbilityDimension[] — 固定 6 行 */ ]
}
```

**说明**:
- 新用户注册时,`AbilityService.seed_for_new_user(user_id)` 自动插入 6 行(`actual_score=0, ideal_score=10`)
- 列表按 `dimension_key` 字母升序(`tech_depth` 在前)
- 空用户(`ability_dimensions` 行为空)返回 `data: []` + 客户端 fallback 渲染 6 维度空态

---

## 2. `GET /api/v1/ability-dimensions/{dimension_key}`

**用途**:获取单维度详情(含 sub_scores)。

**Auth**:Bearer access

**响应 200**:`AbilityDimension`

**响应 404**:维度不存在或 RLS 隔离

---

## 3. `PATCH /api/v1/ability-dimensions/{dimension_key}`

**用途**:用户手动校正单维度分数(Phase 2 写路径)。

**Auth**:Bearer access

**请求体**:`PatchAbilityDimensionInput`

**校验**:
- `actual_score` 0.00-10.00
- `ideal_score` 0.00-10.00
- `sub_scores` 键必须在 DEC-P2-2 锁定的 18 子项中(否则 422)
- `dimension_key` 不可改(URL path 决定)

**响应 200**:更新后的 `AbilityDimension`

**副作用**:
- `last_updated_at = now()`
- `source='manual'`(单字段 PATCH 不改 source;Agent 写入时改)
- 结构化日志 `ability_dimension.updated`

**Phase 2 不写**:`ability_dimensions_history`(Phase 4-5 M18 异步诊断时再写)。

---

## 4. `POST /api/v1/ability-dimensions/{dimension_key}/toggle`

**用途**:启用/禁用某维度。

**Auth**:Bearer access

**请求体**:
```json
{ "is_active": false }
```

**响应 200**:更新后的 `AbilityDimension`

**副作用**:
- 禁用时雷达图不展示该维度(前端过滤 `is_active=true`)
- 结构化日志 `ability_dimension.toggled`

---

## 5. `GET /api/v1/ability-dimensions/history`

**用途**:时序数据(成长曲线),按维度 + aggregate 过滤。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `dimension_key` | enum | - | 单维度过滤;不传 = 全部 6 维度 |
| `aggregate` | enum | `month` | month / day |
| `from` | date | - | 起始日期(YYYY-MM-DD) |
| `to` | date | - | 结束日期(YYYY-MM-DD) |
| `limit` | int 1-50 | 20 | 限制点数 |

**响应 200**:
```json
{
  "data": [ /* AbilityHistoryPoint[] */ ]
}
```

**Phase 2 范围**:
- 端点开放,但 `ability_dimensions_history` 表无 Phase 2 写路径(Phase 4-5 M18 启用)
- 新用户查询 → `data: []`(空态)
- 演示场景:Phase 2 可手动 insert 几条 seed 数据验证前端时序图

---

## 6. `GET /api/v1/ability-dimensions/dimensions-meta`

**用途**:返回 6 维度 + 18 子项的元数据(静态,Phase 2 写死)。

**Auth**:Bearer access(可选;若公开可加 `@public_router`)

**响应 200**:
```json
{
  "dimensions": [
    {
      "key": "tech_depth",
      "label_zh": "技术深度",
      "label_en": "Technical Depth",
      "sub_keys": [
        { "key": "fundamentals", "label_zh": "基础知识" },
        { "key": "system_design", "label_zh": "系统设计" },
        { "key": "depth_specialty", "label_zh": "专精深度" }
      ]
    },
    /* 5 more */
  ]
}
```

**用途**:前端渲染雷达图时,从此端点获取 6 维度顺序 + 子项名称,避免前端硬编码。

---

## 错误码

| 状态码 | 触发场景 |
|---|---|
| 400 | 字段类型错误 |
| 401 | JWT 缺失/过期 |
| 403 | RLS 拒绝 |
| 404 | 维度不存在或被禁用(404 而非 403,避免信息泄露) |
| 422 | 字段值越界(0-10)或 sub_key 不在白名单 |
| 429 | 速率限制 |
| 500 | 服务端异常 |

---

## Phase 2 不开放(Phase 4-5 启用)

- `POST /api/v1/ability-dimensions`(注册时由 M04 钩子自动 seed,无 API 入口)
- `DELETE /api/v1/ability-dimensions/{dimension_key}`(disable 走 toggle;真删仅 Phase 6 M20)
- `POST /api/v1/ability-dimensions/{dimension_key}/diagnose`(Phase 4 M18 异步诊断触发器)
- `GET /api/v1/ability-dimensions/{dimension_key}/trends`(advanced analytics,Phase 6)
