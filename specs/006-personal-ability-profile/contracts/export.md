# PDF Export Contracts

## 1. `POST /api/v1/ability-profile/export`

**用途**:触发 PDF 导出任务(异步)。

**Auth**: Bearer access

**请求体**: (空,无参数)

**响应 202**:
```json
{
  "data": {
    "export_id": "uuid-v7",
    "status": "pending",
    "estimated_wait_seconds": 10,
    "requested_at": "2026-06-16T10:00:00Z"
  }
}
```

**说明**:
- PDF 由 ARQ worker 异步生成
- 同一用户最多 5 次/小时(含所有状态);超限返回 429

---

## 2. `GET /api/v1/ability-profile/exports/{id}`

**用途**:查询导出任务状态。

**Auth**: Bearer access

**响应 200**:
```json
{
  "data": {
    "export_id": "uuid-v7",
    "status": "completed",
    "file_size_bytes": 245000,
    "download_url": "/api/v1/ability-profile/exports/uuid-v7/download",
    "requested_at": "2026-06-16T10:00:00Z",
    "completed_at": "2026-06-16T10:00:10Z"
  }
}
```

`status` 枚举: `pending` / `processing` / `completed` / `failed`

---

## 3. `GET /api/v1/ability-profile/exports/{id}/download`

**用途**:下载已生成的 PDF 文件。

**Auth**: Bearer access

**响应 200**: `application/pdf` 二进制流

**错误**:
| 状态码 | 场景 |
|---|---|
| 404 | 导出 ID 不存在或不属于当前用户 |
| 400 | 导出尚未完成 |
| 410 | 文件已过期(> 24h) |

---

## 4. `GET /api/v1/ability-profile/exports`

**用途**:列出当前用户最近的导出记录。

**Auth**: Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int(1-20) | 10 | 记录数 |

**响应 200**:
```json
{
  "data": [
    {
      "export_id": "uuid-v7",
      "status": "completed",
      "file_size_bytes": 245000,
      "requested_at": "2026-06-16T10:00:00Z",
      "completed_at": "2026-06-16T10:00:10Z"
    }
  ]
}
```
