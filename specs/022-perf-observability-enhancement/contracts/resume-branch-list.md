# Contract: Resume Branch List Response

**Feature**: 022-perf-observability-enhancement
**Related FRs**: FR-010 ~ FR-013

## Endpoint

```
GET /api/v1/resume-branches
Authorization: Bearer <token>
```

## Response 200

```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "title": "我的主简历",
      "parent_id": null,
      "created_at": "2026-06-22T10:00:00Z",
      "updated_at": "2026-06-22T10:00:00Z",
      "version_count": 3,
      "block_count": 15
    }
  ]
}
```

## New Fields

| Field | Type | Description |
|-------|------|-------------|
| `version_count` | integer | 该分支下的简历版本总数 |
| `block_count` | integer | 该分支下所有版本的所有块数总和 |

## Field Name Compatibility

- 若既有响应已用 `versions_count`（复数 s），则沿用 `versions_count`，不擅自改名（spec FR-013）。
- 实现前需 grep 既有 `resume_branches` 响应 schema，确认字段名。
- 前端 `JobRepository.ts`（应为 `ResumeRepository.ts`）类型定义同步扩展。

## SQL Query Count Contract

- **Before**: 1 + N + N*M 次 SQL（N = 分支数，M = 每分支版本数）。
- **After**: ≤ 2 次 SQL（1 次分支 + 1 次 `selectinload` 版本和块）。
- 验证方式: 测试中 hook SQLAlchemy `before_cursor_execute` 事件计数。

## Error Responses

- 401 Unauthorized: token 无效或过期。
- 500 Internal Server Error: 数据库异常（不应发生，记录 request_id 供排障）。

## No Breaking Change

- 既有字段（`id` / `user_id` / `title` / `parent_id` / `created_at` / `updated_at`）保持不变。
- 仅新增 `version_count` / `block_count` 两个可选字段，旧客户端忽略即可。
