# Account Contract: M20 + M21

## POST /api/v1/account/delete

发起账号注销。设置 `User.status = soft_deleted`, `scheduled_purge_at = NOW() + 90d`, `cancellation_deadline = NOW() + 7d`。

**Request Body**:
```json
{
  "confirmation": true
}
```

**Response 200**:
```json
{
  "status": "soft_deleted",
  "scheduled_purge_at": "2026-09-13T00:00:00Z",
  "cancellation_deadline": "2026-06-22T00:00:00Z",
  "message": "您的账号已进入注销流程。7 天内可取消,90 天后将物理清除。"
}
```

**Errors**: 409 (already soft_deleted), 400 (confirmation not true)

---

## POST /api/v1/account/cancel-deletion

取消账号注销。仅在 `cancellation_deadline` 之前有效。

**Response 200**:
```json
{
  "status": "active",
  "message": "账号注销已取消,您的账号已恢复正常。"
}
```

**Errors**: 409 (cooling period passed / not in soft_deleted)

---

## GET /api/v1/account/deletion-status

查询注销状态。

**Response 200** (active):
```json
{
  "status": "active",
  "is_deleting": false
}
```

**Response 200** (soft_deleted):
```json
{
  "status": "soft_deleted",
  "is_deleting": true,
  "scheduled_purge_at": "2026-09-13T00:00:00Z",
  "cancellation_deadline": "2026-06-22T00:00:00Z",
  "can_cancel": true,
  "days_until_purge": 90,
  "days_until_cancellation_deadline": 7
}
```

**Response 200** (purged):
```json
{
  "status": "purged",
  "is_deleting": true,
  "message": "账号数据正在清除中。"
}
```

---

## POST /api/v1/account/export

发起全量数据导出。入队 ARQ 任务。

**Request Body**:
```json
{
  "include": ["resumes", "interviews", "error_questions", "ability_dimensions", "activities"]
}
```

`include` 可选,默认为全部类型。

**Response 202**:
```json
{
  "task_id": "uuid",
  "status": "pending",
  "estimated_minutes": 3
}
```

---

## GET /api/v1/account/export/{task_id}/status

查询导出进度。

**Response 200**:
```json
{
  "task_id": "uuid",
  "status": "processing",
  "progress_pct": 45,
  "created_at": "2026-06-15T10:00:00Z",
  "completed_at": null,
  "download_url": null,
  "expires_at": null
}
```

**Response 200** (completed):
```json
{
  "task_id": "uuid",
  "status": "completed",
  "progress_pct": 100,
  "created_at": "2026-06-15T10:00:00Z",
  "completed_at": "2026-06-15T10:03:00Z",
  "download_url": "/api/v1/account/export/uuid/download",
  "expires_at": "2026-06-18T10:03:00Z",
  "file_size_bytes": 245760
}
```

---

## GET /api/v1/account/export/{task_id}/download

下载导出 ZIP。需要 `status=completed` 且未过期。

**Response 200**: `application/zip` 二进制流。

**Headers**: `Content-Disposition: attachment; filename="export-{user_id}-{timestamp}.zip"`

**Errors**: 404 (expired), 409 (not ready)

---

## POST /api/v1/resumes/import

导入简历文件。

**Request**: `multipart/form-data`
- `file`: JSON 或 Markdown 文件
- `branch_name`: 可选,新分支名称(默认从文件名生成)

**Response 201**:
```json
{
  "branch_id": "uuid",
  "branch_name": "导入简历 - 2026-06-15",
  "blocks_count": 7,
  "message": "导入完成,请检查简历内容。"
}
```

**Errors**: 400 (parse error, validation error)

---

## GET /api/v1/account/notification-center

获取站内通知列表(邮件降级后的备选通道)。

**Response 200**:
```json
{
  "notifications": [
    {
      "id": "uuid",
      "type": "export_ready",
      "title": "数据导出已完成",
      "message": "您的数据导出已准备就绪,请在 72 小时内下载。",
      "related_task_id": "uuid",
      "is_read": false,
      "created_at": "2026-06-15T10:03:00Z"
    }
  ],
  "unread_count": 1
}
```
