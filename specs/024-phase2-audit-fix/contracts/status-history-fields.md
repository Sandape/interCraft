# Contract: status_history Field Names

**Feature**: 024-phase2-audit-fix
**Related FRs**: FR-020 ~ FR-023

## Backend Response (unchanged)

`GET /api/v1/jobs/{id}` 的 `status_history` 字段是 JSONB 数组，元素结构:

```json
{
  "status_history": [
    {
      "from": "fresh",
      "to": "applied",
      "at": "2026-06-22T10:00:00Z",
      "note": "投递"
    },
    {
      "from": "applied",
      "to": "interviewing",
      "at": "2026-06-22T11:00:00Z",
      "note": "面试邀请"
    }
  ]
}
```

**字段名** (已与后端 `service.py:49,100` 一致，不改):
- `from`: string，转换前状态
- `to`: string，转换后状态
- `at`: ISO 8601 timestamp，转换时间
- `note`: string (optional)，转换备注

## Frontend Type Definition (changed)

`src/repositories/JobRepository.ts`:

```typescript
// Before (错误)
interface StatusHistoryEntry {
  from_status: string;
  to_status: string;
  changed_at: string;
  note?: string;
}

// After (对齐后端)
interface StatusHistoryEntry {
  from: string;
  to: string;
  at: string;
  note?: string;
}
```

## Frontend Component (changed)

`src/components/jobs/JobTimeline.tsx`:

```typescript
// Before
{entry.from_status} → {entry.to_status}
<span>{formatDate(entry.changed_at)}</span>

// After
{entry.from} → {entry.to}
<span>{formatDate(entry.at)}</span>
```

## No Backend Change

后端 `jobs/service.py:49,100` 已用 `{from, to, at, note}`，本 feature 仅前端对齐。

## Testing

- `npm run typecheck` 通过，无类型错误。
- 前端组件测试 `JobTimeline.test.tsx`:
  - Mock status_history 含 3 条 entry → 断言渲染 3 条时间线节点。
  - 每条节点显示 `from` / `to` / `at` / `note`。
- 既有 E2E 涉及岗位时间线的用例通过。
