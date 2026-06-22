# Contract: Error Questions FSM

**Feature**: 024-phase2-audit-fix
**Related FRs**: FR-030 ~ FR-034

## States (3 + reset, archived removed)

| State | Description |
|-------|-------------|
| `fresh` | 新错题，未练习 |
| `practicing` | 练习中（frequency > 0）|
| `mastered` | 已掌握（frequency = 0）|

**Removed**: `archived`（spec 016 未授权，本 feature 移除）。

## Authorized Transitions

```
fresh → practicing     (开始练习)
practicing → mastered  (frequency 递减到 0)
mastered → fresh       (reset, 重置错题)
```

**Removed transitions**:
- `fresh → archived` ❌
- `practicing → archived` ❌
- `mastered → archived` ❌
- `practicing → fresh` ❌ (不允许回退，需 reset 路径)
- 任何状态 → `archived` ❌

## Endpoint: PATCH /api/v1/error-questions/{id}/status

**Request**:
```json
{
  "status": "practicing",
  "reset": false  // optional, 仅 mastered→fresh 时为 true
}
```

**Responses**:
- 200 OK: 转换合法，status 更新。
- 422 Unprocessable Entity: 转换非法，响应体:
  ```json
  {
    "detail": "非法状态转换",
    "from": "fresh",
    "to": "archived",
    "valid_transitions": ["practicing"]
  }
  ```
- 400 Bad Request: `reset=true` 但 from≠mastered 或 to≠fresh。

## Backend Implementation

`backend/app/modules/errors/service.py`:

```python
VALID_TRANSITIONS = {
    "fresh": {"practicing"},
    "practicing": {"mastered"},
    "mastered": {"fresh"},  # reset only, requires reset=True
}

async def transition_status(question_id, to_status, reset=False):
    current = await get_status(question_id)
    if to_status not in VALID_TRANSITIONS.get(current, set()):
        logger.warning("illegal_fsm_transition",
                       question_id=question_id,
                       from=current, to=to_status)
        raise InvalidTransitionError(current, to_status)
    if current == "mastered" and to_status == "fresh" and not reset:
        raise InvalidTransitionError(current, to_status, "reset flag required")
    # ... apply transition
```

## Testing

- 单测 `test_error_fsm.py`:
  - `fresh→practicing→mastered→fresh(reset=true)` 全部 200。
  - `fresh→archived` → 422。
  - `practicing→archived` → 422。
  - `mastered→archived` → 422。
  - `practicing→fresh`（无 reset）→ 422。
  - `mastered→fresh`（无 reset）→ 422。
  - `mastered→fresh`（reset=true）→ 200。
- 非法转换记录 warning 日志（含 user_id / question_id / from / to）。
- 既有 021 error_coach E2E 通过（3-correct + frequency decrement 路径合法）。
