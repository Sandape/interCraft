# Contract: Ability Profile PDF Export (Synchronous)

**Feature**: 024-phase2-audit-fix
**Related FRs**: FR-050 ~ FR-054

## Endpoint: GET /api/v1/ability-profile/export-pdf

**Before (async via ARQ)**:
```http
GET /api/v1/ability-profile/export-pdf
→ 200 {"job_id": "abc-123"}
→ client polls GET /api/v1/arq/jobs/abc-123 until complete
→ client downloads PDF from presigned URL
```

**After (sync direct download)**:
```http
GET /api/v1/ability-profile/export-pdf
→ 200 application/pdf
   Content-Disposition: attachment; filename="ability-profile-{user_id}-{YYYYMMDD}.pdf"
   Content-Length: <bytes>

   <binary PDF content>
```

## Response Headers

| Header | Value | Description |
|--------|-------|-------------|
| `Content-Type` | `application/pdf` | 固定值 |
| `Content-Disposition` | `attachment; filename="ability-profile-{user_id}-{YYYYMMDD}.pdf"` | 浏览器触发下载 |
| `Content-Length` | `<bytes>` | PDF 文件大小 |
| `X-Request-ID` | `<uuid>` | 与 022 联动 |

## Response Body

Binary PDF content, 包含:
- 能力维度雷达图（雷达图 + 5 维度评分）
- 维度说明（每个维度的文字描述）
- 建议（基于评分的改进建议）

## Performance Contract

- 响应时间 ≤ 3 秒（单用户能力画像 < 1MB PDF）。
- FastAPI 同步端点用 `run_in_threadpool` 包装 CPU-bound PDF 生成，不阻塞 event loop。
- 并发 10 用户同时导出 → 每个请求独立生成，不串行等待（threadpool 默认 40 线程）。

## Removed Components

- `service.py:419-420` 的 `enqueue_job(...)` 调用 → 移除。
- ARQ worker 中的 PDF 生成任务函数 → 移除（或保留为「批量导出」独立功能，但单次导出不走）。
- 前端轮询任务状态的逻辑 → 移除，改为直接 `window.location.href = url` 或 `<a download>`。

## Frontend Trigger

```typescript
// Before
const { job_id } = await api.post("/ability-profile/export-pdf");
await pollJobUntilComplete(job_id);
window.location.href = pdfUrl;

// After
window.location.href = "/api/v1/ability-profile/export-pdf";
// 浏览器原生下载, 无需轮询
```

## Testing

- 单测 `test_ability_profile_pdf_sync.py`:
  - GET 返回 200 + `Content-Type: application/pdf`。
  - `Content-Disposition` 含 `attachment; filename=`。
  - 响应体非空 + 是合法 PDF（`%PDF-` 魔数开头）。
  - 响应时间 < 3s。
  - 无 ARQ 任务入队（mock `enqueue_job` 断言未被调用）。
- 集成测试:
  - 连续点击 3 次导出 → 每次都返回 PDF，不因去重拒绝。
  - 用户无能力画像数据 → 返回空内容 PDF 或 404（按既有行为）。
