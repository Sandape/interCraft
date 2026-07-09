# Data Model: REQ-057 求职训练指挥台

**Date**: 2026-07-10  
**Spec**: [spec.md](./spec.md)  
**Note**: 逻辑模型；多数字段复用既有表，本 REQ **不**强制新业务表。摘要为只读聚合视图。

## Entities

### DashboardSummary (聚合视图，非持久表)

| Field | Type | Notes |
|---|---|---|
| generated_at | datetime | UTC |
| cache_ttl_sec | int | 告知客户端建议新鲜度 |
| tz | string | 解析用时区，默认 `Asia/Shanghai` |
| local_date | date | `YYYY-MM-DD` 用户本地日 |
| l0 | CommandCenterL0 | 关键首屏 |
| l1 | CommandCenterL1 | 资产与下一步 |
| l2 | CommandCenterL2 | 洞察（可降级为空） |

### CommandCenterL0

| Field | Type | Notes |
|---|---|---|
| greeting_context | string | 情境一句（中文） |
| next_interview | TodayInterviewItem \| null | 下一场（今日最早未过点，或今日最近一场） |
| today_interviews | TodayInterviewItem[] | 今日全部 |
| primary_cta | Cta | label + href |
| onboarding | OnboardingProgress \| null | 未完成三步时出现 |
| resumable_sessions | ResumableSession[] | ≤3 |

### TodayInterviewItem

| Field | Type | Source |
|---|---|---|
| job_id | UUID | jobs.id |
| company | string | jobs.company |
| position | string | jobs.position |
| interview_time | datetime | jobs.interview_time |
| status | JobStatus | jobs.status |
| relative_label | string | 服务端或 FE 格式化（如「3 小时后」「已过点」） |
| href | string | `/jobs/{id}` 或产品约定路径 |

**Validation**:
- 仅 `interview_time` 本地日 = `local_date` 的岗位
- 无法解析时间 → 排除

### OnboardingProgress

| Field | Type | Done when |
|---|---|---|
| steps[].id | `resume` \| `job` \| `interview` | — |
| steps[].done | bool | resume: v2 任意简历>0；job: jobs>0；interview: completed sessions>0 |
| steps[].href | string | `/resume`, `/jobs`, `/interview/mode` |
| show | bool | 任一步未完成 |

### ResumableSession

| Field | Type | Source |
|---|---|---|
| session_id | UUID | interview_sessions.id |
| company / position | string | session 字段 |
| status | `pending` \| `in_progress` | |
| href | string | `/interview/{id}/live` |

### CommandCenterL1

| Field | Type | Notes |
|---|---|---|
| resume_summaries | ResumeSummary[] | ≤5，按 updated_at |
| resume_counts | { root, derived, standard?, total } | |
| next_action | NextAction \| null | 单一建议 |
| job_funnel | FunnelSegment[] | 恰好或至少 3 段 |
| prep_pack | PrepPack \| null | 基于 next_interview / 首条今日 |

### ResumeSummary

| Field | Type | Source |
|---|---|---|
| id | UUID | resumes_v2 |
| name | string | |
| resume_kind | `root` \| `derived` \| `standard` | |
| job_id | UUID \| null | derived |
| updated_at | datetime | |
| href | string | 与简历中心编辑路由一致 |

### NextAction

| Field | Type | Notes |
|---|---|---|
| id | string | 稳定机器 id |
| title_zh / body_zh | string | 用户可见 |
| cta | Cta | |
| tier | 0 \| 1 \| 2 | 对齐 018 精神，数据源已换 v2 |

### FunnelSegment

| Field | Type | Notes |
|---|---|---|
| key | `applying` \| `interviewing` \| `awaiting_feedback` | |
| label_zh | string | 投递中 / 面试中 / 待反馈 |
| count | int | ≥0 |
| filter_statuses | JobStatus[] | 用于跳转提示 |
| href | string | 求职追踪带过滤 |

**待反馈规则**（见 research R5）: 面试相关非终态 + `interview_time < now()`。

### PrepPack

| Field | Type | Notes |
|---|---|---|
| job_id | UUID | |
| derived_resume_id | UUID \| null | resumes_v2 where kind=derived & job_id |
| actions | Cta[] | 打开岗位、打开/去派生、可选模拟 |

### CommandCenterL2

| Field | Type | Notes |
|---|---|---|
| ability_snapshot | { overall_score, weakest_dimensions[], href } \| null | |
| recent_activities | ActivityView[] | ≤5，已含 title_zh |
| interview_trend | { completed_count, avg_score } \| null | |

### ActivityView

| Field | Type | Notes |
|---|---|---|
| id | UUID | activities.id |
| type | ActivityType | 内部，可不展示 |
| title_zh | string | **必填** 展示用 |
| detail_zh | string | |
| occurred_at | datetime | |
| href | string \| null | |

## Existing tables touched (read / invalidate)

| Table | Read | Invalidate on write |
|---|---|---|
| jobs | today, funnel, prep | status / interview_time / create/delete |
| resumes_v2 (list projection) | summaries, onboarding | CRUD / kind changes |
| interview_sessions | resumable, trend, onboarding | status transitions |
| activities | recent | new activity rows |
| ability_dimensions / profile | L2 snapshot | interview completed / dimension patch |

## Cache record

| Key | Value | TTL |
|---|---|---|
| `dashboard_summary:{user_id}:{local_date}` | serialized DashboardSummary JSON | 60s |

无独立 DB 表。

## State / transitions

本 REQ 不新增岗位/面试状态机；仅消费：

- JobStatus FSM（REQ-053）
- Interview session: `pending` → `in_progress` → `completed` \| `aborted` \| `expired`
