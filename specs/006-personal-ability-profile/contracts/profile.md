# Profile Dashboard Contract

## 1. `GET /api/v1/ability-profile/dashboard`

**用途**:返回能力画像仪表盘的聚合数据(含趋势计算)。

**Auth**: Bearer access

**响应 200**:
```json
{
  "data": {
    "dimensions": [
      {
        "key": "tech_depth",
        "label_zh": "技术深度",
        "actual_score": 6.5,
        "ideal_score": 9.0,
        "self_assessed_score": 7.0,
        "source": "manual",
        "trend": "up",
        "history": [
          { "date": "2026-05-01", "actual_score": 5.0, "ideal_score": 8.0 },
          { "date": "2026-06-01", "actual_score": 6.5, "ideal_score": 9.0 }
        ]
      }
    ],
    "generated_at": "2026-06-16T10:00:00Z"
  }
}
```

**趋势计算**:
- `trend`: 对比最近 2 个 historical 点的 actual_score 变化
  - `up`: 增幅 > 0.5
  - `down`: 降幅 > 0.5
  - `stable`: 变化 ≤ 0.5

**说明**:
- `actual_score` = 系统评分(从 ability_dimensions 读取,若多次面试评分则为时间衰减加权平均)
- `self_assessed_score` = 用户自评分数(optional;仅当用户通过 PATCH 手动设置过 actual_score 时返回)
- 当 actual_score 和 self_assessed_score 同时存在时,雷达图将两者分别绘制
- `history` 数据来自 `ability_dimensions_history`(已有表)
