# M18 Ability Diagnose: ARQ 触发契约

**Date**: 2026-06-15 | **Spec**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

M18 Ability Diagnose 为纯异步子图,由 ARQ 任务触发,无 REST 端点。

---

## ARQ Task

### `diagnose_after_interview(session_id: UUID)`

**触发源**: Phase 4 M15 Interview Agent `report` 节点完成时,通过 `arq_pool.enqueue_job('diagnose_after_interview', session_id)` 触发。

**触发条件**: 仅在 `report` 节点完成且 `interview_reports` 表已写入后触发。

**函数签名**:
```python
@worker_task
async def diagnose_after_interview(ctx: arq.Worker, session_id: UUID) -> dict:
    """M18 能力诊断子图入口。
    
    1. 从 session_id 读取 interview_reports + ai_messages
    2. 创建 Ability Diagnose LangGraph, 传入 session_id
    3. 执行子图: aggregate_scores → compare_baseline → generate_insight → update_dimensions
    4. 返回诊断结果摘要
    """
```

**返回**:
```json
{
  "status": "success | failed",
  "session_id": "uuid",
  "dimensions_updated": ["技术深度", "架构能力", "工程实践", "沟通表达", "算法能力", "业务理解"],
  "insights_count": 12,
  "duration_ms": 12500
}
```

**重试策略**: ARQ 自带重试,最多 3 次指数退避(1s/4s/16s)。3 次后写入 `dead_letter` 表。

---

## 子图节点

| 节点 | 输入 | 输出 | 是否调 LLM |
|---|---|---|---|
| `aggregate_scores` | session_id → interview_reports + ai_messages | `interview_scores`: 每维度加权分数 | 否(纯聚合运算) |
| `compare_baseline` | `interview_scores` + `ability_dimensions_history`(90天) | `historical_dims`: delta + 趋势标记 | 否(算术运算) |
| `generate_insight` | `diagnoses` + `current_dims` | `insights`: 每维度 3-5 条建议 | 是(LLM 生成) |
| `update_dimensions` | `insights` | 写 DB + WS 推送 | 否(持久化) |

---

## DB 写入

| 表 | 操作 | 时机 |
|---|---|---|
| `ability_dimensions` | `UPDATE actual = new_score` | update_dimensions 节点 |
| `ability_dimensions_history` | `INSERT` 新历史记录 | update_dimensions 节点 |
| `activities` | `INSERT` type='ability.suggestion' | update_dimensions 节点 |

---

## WS Event: `agent.final`

通过 Phase 4 WS 通道推送:

```json
{
  "event": "agent.final",
  "graph": "ability_diagnose",
  "thread_id": "uuid",
  "data": {
    "summary": "能力画像已更新:技术深度 +8, 算法能力 +5...",
    "dimensions_updated": true
  }
}
```
