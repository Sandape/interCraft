# PDF Rendering Service Contract

**Service**: PDF / Image Export Rendering Service
**Feature**: 002-resume-editor-enhancement
**Protocol**: HTTP REST (JSON request, binary response)

## Endpoint

### `POST /api/export/render`

Renders a resume Markdown document into PDF or image format using the specified style template.

**Request**:

```json
{
  "markdown": "# 张三\n\n## 个人简介\n\n资深前端工程师...\n\n## 工作经历 — 字节跳动\n---\ncompany: 字节跳动\nrole: 高级前端工程师\nduration: 2024.01 - 至今\n---\n\n- 主导 XXX 项目\n- 优化 YYY 性能\n\n## 技能\n\n- React\n- TypeScript\n- Python",
  "style_id": "compact-one-page",
  "format": "pdf",
  "locale": "zh"
}
```

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `markdown` | string | Yes | Full resume Markdown content |
| `style_id` | string | Yes | `"compact-one-page"` or `"modern-two-column"` |
| `format` | string | Yes | `"pdf"`, `"png"`, or `"jpeg"` |
| `locale` | string | No (default: `"zh"`) | Locale for date formatting, labels |

**Response** (success — 200 OK):

- Content-Type: `application/pdf` for PDF, `image/png` for PNG, `image/jpeg` for JPEG
- Content-Disposition: `attachment; filename="resume-{timestamp}.{ext}"`
- Body: Binary file data

**Response** (error — 4xx/5xx):

```json
{
  "error": "RENDERING_FAILED",
  "message": "Human-readable error description",
  "request_id": "uuid"
}
```

**Error codes**:

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `EMPTY_CONTENT` | 400 | Markdown field is empty or whitespace only |
| `INVALID_STYLE` | 400 | style_id not recognized |
| `INVALID_FORMAT` | 400 | format not one of pdf/png/jpeg |
| `CONTENT_TOO_LARGE` | 413 | Markdown exceeds max size (500KB) |
| `RENDERING_FAILED` | 500 | Internal rendering error (Puppeteer crash, timeout, etc.) |
| `SERVICE_UNAVAILABLE` | 503 | Rendering service is down or overloaded |

## Logging Contract

Each request MUST produce a structured log line:

```json
{
  "timestamp": "2026-06-13T10:30:00Z",
  "level": "INFO",
  "service": "pdf-renderer",
  "request_id": "uuid",
  "user_id": "uuid (if available)",
  "style_id": "compact-one-page",
  "format": "pdf",
  "content_size_bytes": 1234,
  "render_duration_ms": 1250,
  "status": "success"
}
```

On error, include `error_code` and `error_message` fields.

## Frontend Client Usage

```typescript
// src/api/export.ts
interface ExportRequest {
  markdown: string;
  styleId: string;
  format: 'pdf' | 'png' | 'jpeg';
  locale?: string;
}

async function exportResume(req: ExportRequest): Promise<Blob> {
  const response = await fetch('/api/export/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      markdown: req.markdown,
      style_id: req.styleId,
      format: req.format,
      locale: req.locale ?? 'zh',
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new ExportError(error.error, error.message);
  }

  return response.blob();
}
```

## Frontend Error Handling

| Backend Error | User-Facing Message |
|---------------|-------------------|
| `EMPTY_CONTENT` | "简历内容为空，无法导出" |
| `INVALID_STYLE` | "不支持的简历样式" |
| `CONTENT_TOO_LARGE` | "简历内容过大，请精简后重试" |
| `RENDERING_FAILED` | "PDF 导出失败，请稍后重试" |
| `SERVICE_UNAVAILABLE` | "PDF 导出服务暂不可用，您可以先导出 Markdown 格式" |
