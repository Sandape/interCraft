# Audit Contract: M22

## Common Query Parameters

All audit list endpoints support:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `resource_type` | string | - | Filter: `resume`/`resume_branch`/`interview_session`/etc |
| `action` | string | - | Filter: `create`/`update`/`delete`/`soft_delete`/etc |
| `date_from` | string(ISO) | - | 开始时间(含) |
| `date_to` | string(ISO) | - | 结束时间(含) |
| `limit` | int | 50 | 每页条数,最大 200 |
| `offset` | int | 0 | 分页偏移 |

---

## GET /api/v1/audit-logs

获取当前用户的操作日志(RLS: `actor_id = current_user`)。

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "action": "update",
      "resource_type": "resume_branch",
      "resource_id": "uuid",
      "old_values": {"name": "旧名称"},
      "new_values": {"name": "新名称"},
      "ip_address": "192.168.1.1",
      "created_at": "2026-06-15T10:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

## GET /api/v1/admin/audit-logs

获取全量用户的审计日志(需要 admin 角色)。

**Additional query parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `user_id` | UUID | - | 按用户筛选 |

**Response 200**: 同上,但 items 可包含不同 actor_id 的记录。

**Errors**: 403 (non-admin user)
