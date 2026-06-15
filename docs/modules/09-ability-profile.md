# M09 · 能力画像

> 状态: draft · 所属领域: C · 优先级: P1
> 引用原文档: §3.2 (ability_dimensions, ability_history), §7.4, §7.5

## 1. 需求摘要

实现能力画像:`ability_dimensions`(当前快照,如「算法 8.5/10」)+ `ability_history`(时序数据,按月聚合成长曲线)+ 子项细分。本模块**只做 CRUD + 读取聚合**,具体的能力评估算法由 M18(Ability Diagnose Agent)负责。

## 2. 验收标准

- [ ] `GET /api/v1/ability-dimensions` 当前用户所有维度(含 sub_items)
- [ ] `GET /api/v1/ability-dimensions/{key}` 单维度详情
- [ ] `GET /api/v1/ability-dimensions/history?dim={key}&days=90` 时序原始数据
- [ ] `GET /api/v1/ability-dimensions/history?aggregate=month&months=6` 月聚合
- [ ] `PATCH /api/v1/ability-dimensions/{key}` 更新 actual / ideal / sub_items(管理员或 Agent)
- [ ] Service 接口 `record_score(user_id, key, score)` → 同时写 dimensions(覆盖)+ history(追加)

## 3. 依赖与被依赖关系

**强依赖**: M02(表)、M05(RLS)
**弱依赖**: M18(Agent 写入)
**被以下模块依赖**: M18(Ability Diagnose)、M23(前端 Profile 页 / 成长曲线)
**外部依赖**: 无

## 4. 数据模型

**`ability_dimensions` 表**(快照):
```
id UUID PK
user_id UUID NOT NULL (Mixin)
key TEXT NOT NULL  -- tech / arch / eng / comm / algo / biz(受控词表)
name TEXT NOT NULL  -- 中文展示名
ideal NUMERIC(4,2) NOT NULL  -- 理想分(用户设定的目标)
actual NUMERIC(4,2) NOT NULL  -- 当前实际分
description TEXT NULL
sub_items JSONB NOT NULL DEFAULT '[]'  -- [{name, score}, ...]
last_evaluated_at TIMESTAMPTZ NULL  -- 上次评估时间
created_at / updated_at / deleted_at
```

**约束**:`(user_id, key)` 唯一

**`ability_history` 表**(时序):
```
id UUID PK
user_id UUID NOT NULL (Mixin)
dimension_key TEXT NOT NULL  -- 不外键,避免维度删除时丢历史
score NUMERIC(4,2) NOT NULL
source TEXT NOT NULL  -- interview / manual / ai_diagnose
source_id UUID NULL  -- 面试 id / 评估 run_id
recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

**索引**:
- `ability_history (user_id, dimension_key, recorded_at DESC)`
- `ability_history (user_id, recorded_at DESC)` 全维度时序

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/ability-dimensions` | 所有维度当前快照 |
| GET | `/api/v1/ability-dimensions/{key}` | 单维度 |
| GET | `/api/v1/ability-dimensions/history` | 时序(raw / month / week 聚合) |
| PATCH | `/api/v1/ability-dimensions/{key}` | 更新理想分 / 实际分 |

**Service 接口**(供 M18 调用):
```python
async def record_score(user_id, key, score, source, source_id):
    """同时更新 dimensions.actual 和追加 history"""
```

**工具**(LangGraph):
- `query_history(user_id, dim, days) → list[AbilityHistoryOut]`
- `query_dimensions(user_id) → list[AbilityDimensionOut]`

## 6. 关键设计点

- **快照 vs 时序双源**:`ability_dimensions.actual` 是最新分(查询便捷);`ability_history` 保留时间序列(成长曲线)
- **月聚合**:按 `date_trunc('month', recorded_at)` 取平均 / 最高 / 最低,默认平均
- **6 个固定维度**(从 mockData 派生):tech / arch / eng / comm / algo / biz;允许用户后续自定义(`is_system bool` 字段预留)
- **写入幂等**:同一 source_id(如 interview_session_id)对同一维度的多次写入应去重(取最新)
- **可观测**:维度评估操作入 `tool_call_logs`(M22),便于追溯

## 7. 待澄清

- 子项(sub_items)是否独立成表(`ability_sub_items` with FK)→ MVP 用 JSONB,v1.1 再独立(支持子项历史)
- 用户能否禁用某维度(如算法岗禁用 biz)→ 可,加 `is_active bool`

## 8. 实现提示

- 文件: `backend/app/api/v1/abilities.py`、`backend/app/services/ability_service.py`、`backend/app/repositories/ability_repo.py`
- 复用: 无
- 与 mockData 关系:
  - `mockData.ts:326-411` `AbilityDimension` → 直接落地;6 个维度作为初始受控词表
  - `mockData.ts:414-421` `growthTrajectory` → 由 history 聚合生成,前端不直接持久化
