# Contract: GET /api/v1/me/dashboard-summary

**Spec refs**: FR-001～018, FR-022～028, SC-001～012  
**Research**: R1, R5, R6, R10

## Endpoint

```
GET /api/v1/me/dashboard-summary
Authorization: required (RLS user)
Query:
  tz: string = "Asia/Shanghai"   # IANA TZ; invalid → 422
```

## Response 200

```json
{
  "data": {
    "generated_at": "2026-07-10T05:00:00Z",
    "cache_ttl_sec": 60,
    "tz": "Asia/Shanghai",
    "local_date": "2026-07-10",
    "l0": {
      "greeting_context": "今天有 2 场面试",
      "next_interview": {
        "job_id": "uuid",
        "company": "示例公司",
        "position": "后端工程师",
        "interview_time": "2026-07-10T14:00:00+08:00",
        "status": "interview_1",
        "relative_label": "3 小时后",
        "href": "/jobs/{id}"
      },
      "today_interviews": [],
      "primary_cta": { "label": "准备下一场面试", "href": "/jobs/{id}" },
      "onboarding": null,
      "resumable_sessions": []
    },
    "l1": {
      "resume_summaries": [],
      "resume_counts": { "root": 0, "derived": 0, "standard": 0, "total": 0 },
      "next_action": {
        "id": "start-first-interview",
        "title_zh": "完成首场模拟面试",
        "body_zh": "…",
        "cta": { "label": "开始面试", "href": "/interview/mode" },
        "tier": 0
      },
      "job_funnel": [
        {
          "key": "applying",
          "label_zh": "投递中",
          "count": 0,
          "filter_statuses": ["applied"],
          "href": "/jobs?status=applied"
        },
        {
          "key": "interviewing",
          "label_zh": "面试中",
          "count": 0,
          "filter_statuses": ["test", "interview_1", "interview_2", "interview_3"],
          "href": "/jobs"
        },
        {
          "key": "awaiting_feedback",
          "label_zh": "待反馈",
          "count": 0,
          "filter_statuses": [],
          "href": "/jobs"
        }
      ],
      "prep_pack": null
    },
    "l2": {
      "ability_snapshot": null,
      "recent_activities": [],
      "interview_trend": null
    }
  }
}
```

## Rules

1. `today_interviews` MUST only include jobs whose `interview_time` falls on `local_date` in `tz`.
2. `recent_activities[].title_zh` MUST be Chinese; MUST NOT equal raw `type` string for known types.
3. `resume_counts.total` MUST equal count of v2 resumes visible to user; `has_resume` for suggestions ≡ `total > 0`.
4. Exactly one logical next-action object (or null with empty-state handled by FE); FE MUST NOT render a second duplicate suggestion list.
5. `job_funnel` MUST include the three keys above; counts computed in-service (not legacy `/jobs/stats`).
6. `awaiting_feedback` count: non-terminal interview-related statuses with `interview_time < now(tz)`.
7. Unauthenticated → 401; RLS enforced.

## Errors

| Code | When |
|---|---|
| 401 | No session |
| 422 | Invalid `tz` |
| 500 | Unexpected; MUST NOT leak other users' data |

## Cache headers (optional)

- May set `Cache-Control: private, max-age=0` (browser); freshness owned by Redis + client Query.
- Response MAY include `X-Cache: HIT|MISS` for debugging (not required for product).
