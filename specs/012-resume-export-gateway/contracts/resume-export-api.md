# Contract: Resume Export API

## `POST /api/v1/export/render`

Renders resume markdown into a binary PDF, PNG, or JPEG file.

### Request

```json
{
  "markdown": "# Candidate\n\n## Summary\n\nSenior engineer",
  "style_id": "compact-one-page",
  "format": "pdf",
  "locale": "zh"
}
```

### Success Response

Status: `200 OK`

Headers:

- `Content-Type`: `application/pdf`, `image/png`, or `image/jpeg`
- `Content-Disposition`: `attachment; filename="resume-{request_id}.{ext}"`
- `X-Request-ID`: request correlation identifier

Body: binary file bytes.

### Error Response

Status: `400`, `413`, or `500`

```json
{
  "error": "EMPTY_CONTENT",
  "message": "Resume content is empty.",
  "request_id": "uuid"
}
```

Error codes:

| Code | Status | Meaning |
|------|--------|---------|
| `EMPTY_CONTENT` | 400 | Markdown is empty or whitespace only |
| `INVALID_STYLE` | 400 | Style identifier is not supported |
| `INVALID_FORMAT` | 400 | Format is not `pdf`, `png`, or `jpeg` |
| `CONTENT_TOO_LARGE` | 413 | Markdown exceeds the accepted size |
| `RENDERING_FAILED` | 500 | Renderer crashed or returned an unexpected failure |

### curl validation

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/export/render \
  -H "Content-Type: application/json" \
  -d "{\"markdown\":\"# Candidate\\n\\n## Summary\\n\\nSenior engineer\",\"style_id\":\"compact-one-page\",\"format\":\"pdf\"}" \
  --output resume.pdf
```

Expected: HTTP 200 headers include `application/pdf`; output file is non-empty.
