# Subscription Contract

## GET /api/v1/subscription/plans

获取所有可用订阅方案。

**Response 200**:
```json
{
  "plans": [
    {
      "plan": "free",
      "monthly_token_quota": 500000,
      "features": {},
      "is_active": true
    },
    {
      "plan": "pro",
      "monthly_token_quota": 5000000,
      "features": {"priority_support": true},
      "is_active": true
    },
    {
      "plan": "enterprise",
      "monthly_token_quota": 50000000,
      "features": {"priority_support": true, "custom_quota": true},
      "is_active": true
    }
  ]
}
```

---

## GET /api/v1/subscription/current

获取当前用户的订阅状态。

**Response 200**:
```json
{
  "plan": "free",
  "monthly_token_quota": 500000,
  "monthly_token_used": 123456,
  "monthly_token_remaining": 376544,
  "usage_pct": 24.7,
  "reset_date": "2026-07-01T00:00:00Z",
  "can_start_interview": true
}
```

`can_start_interview`: `monthly_token_remaining > 0`,用于前端控制「开始面试」按钮状态。

---

## POST /api/v1/subscription/pre-check

面试启动前的配额预检。

**Response 200**:
```json
{
  "can_proceed": true,
  "estimated_token_cost": 28000,
  "monthly_token_remaining_before": 376544,
  "monthly_token_remaining_after": 348544
}
```

**Errors**: 429 (quota exhausted)
```json
{
  "detail": "本月 token 配额已用尽 (500000/500000)。请升级方案或等待下月重置。",
  "code": "QUOTA_EXHAUSTED",
  "reset_date": "2026-07-01T00:00:00Z"
}
```
