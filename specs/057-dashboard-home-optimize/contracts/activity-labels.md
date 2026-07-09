# Contract: Activity Chinese Labels

**Spec refs**: FR-019～021, SC-011  
**Enum source**: `backend/app/domain/enums.py` `ActivityType`

## Mapping table (minimum)

| type | title_zh template | detail_zh from payload |
|---|---|---|
| `job_created` | 新增投递 | `{company} · {position}` |
| `job_status_changed` | 岗位状态更新 | `{company} · {position}`（可选附中文 to_status） |
| `task_created` | 新建任务 | `{title}` |
| `task_completed` | 完成任务 | `{title}` |
| `interview_started` | 开始模拟面试 | `{company} · {position}` |
| `interview_completed` | 完成模拟面试 | `{company} · {position}`（可选分数） |
| `branch_created` | 简历更新 | 名称字段若有 |
| `error_logged` | 错题已记录 | 简短说明 |
| `manual` | 手动记录 | payload 摘要或空 |
| _(unknown)_ | 系统更新 | 空或通用说明 |

## Rules

1. Dashboard / summary MUST use this map (or equivalent) before falling back.
2. Fallback for unknown types: `系统更新` — NEVER raw `type` as sole title.
3. Prefer payload business fields (`company`, `position`, `title`) over `summary` if both exist inconsistently.
4. If writers later add `summary`, labels MAY prefer non-empty `summary` when it is already Chinese user copy.

## Test contract

- Unit: each known `ActivityType` → title_zh matches table.
- Integration: seed `job_created` activity → summary `recent_activities[0].title_zh` is `新增投递`.
