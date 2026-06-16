# Contract: Resume PDF Export

**Spec refs**: FR-008 / FR-009 / SC-002
**Defect**: #5 PDF 导出 404
**Decision**: R-001

---

## 后端契约（已存在，确认）

```text
POST /api/v1/export/render
Headers:
  Authorization: Bearer <token>
  X-Request-ID: <uuid>      # 可选，后端会回填
Body (ExportRequest):
  {
    "markdown": "string, 必填, ≤ 500_000 bytes",
    "style_id": "compact-one-page" | "classic-one-page" | "modern-two-column" | "editorial",
    "format":   "pdf" | "png" | "jpeg",
    "locale":   "zh" | "en"  (默认 "zh")
  }
Response 200:
  Content-Type: application/pdf | image/png | image/jpeg
  X-Request-ID: <uuid>
  Body: 二进制

Response 4xx / 5xx (JSON):
  {
    "error": "EMPTY_CONTENT" | "INVALID_STYLE" | "INVALID_FORMAT" | "CONTENT_TOO_LARGE" | "RENDER_FAILED",
    "message": "人类可读中文",
    "request_id": "<uuid>"
  }
  X-Request-ID: <uuid>
```

**已存在**：`backend/app/api/v1/export.py:14-90`，前缀 `/export` + 子路由 `/render` + `_user=Depends(get_current_user)`。**无需后端改动**。

---

## 前端契约（修复点）

```ts
// src/api/export.ts
const EXPORT_BASE = '/api/v1/export'  // 不带末尾斜杠，避免 double-slash
async function renderResume(payload: ExportRequest): Promise<Blob> {
  const res = await fetch(`${EXPORT_BASE}/render`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': crypto.randomUUID(),
    },
    body: JSON.stringify(payload),
    credentials: 'include',
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ExportError(res.status, body?.error ?? 'UNKNOWN', body?.message ?? '导出失败', body?.request_id)
  }
  return res.blob()
}

class ExportError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string
  ) {
    super(message)
  }
}

// src/lib/apiErrorToMessage.ts (新增)
export function exportErrorToMessage(e: ExportError): string {
  switch (e.code) {
    case 'EMPTY_CONTENT':     return '简历内容为空，请先添加简历块'
    case 'INVALID_STYLE':     return '所选简历样式暂不支持'
    case 'INVALID_FORMAT':    return '导出格式不支持'
    case 'CONTENT_TOO_LARGE': return '简历内容过大，请精简后再导出'
    case 'RENDER_FAILED':     return '渲染服务异常，请稍后重试'
    case 'UNAUTHORIZED':      return '会话已过期，请重新登录'
    case 'FORBIDDEN':         return '没有导出该简历的权限'
    default:
      if (e.status === 404) return '导出服务地址未找到，请联系管理员'
      if (e.status >= 500)  return '导出服务暂不可用，请稍后重试'
      return '导出失败：' + e.message
  }
}
```

### UI 契约

```tsx
// src/components/resume/ExportMenu.tsx
async function handleExportPdf() {
  try {
    const blob = await renderResume({ markdown, style_id, format: 'pdf', locale: 'zh' })
    downloadBlob(blob, `resume-${Date.now()}.pdf`)
    toast.success('导出成功')
  } catch (e) {
    if (e instanceof ExportError) {
      const message = exportErrorToMessage(e)
      toast.error(message, { description: e.requestId ? `Request ID: ${e.requestId}` : undefined })
    } else {
      toast.error('导出失败：' + String(e))
    }
  }
}
```

### 关键变更（vs 当前实现）

- ✅ 单一调用点 `${EXPORT_BASE}/render`
- ✅ 错误捕获到 `ExportError`，不再渲染裸 `Rendering failed:` 字符串
- ✅ 401 / 403 / 404 / 422 / 5xx 各自映射可读中文
- ✅ 请求带 `X-Request-ID`，便于后端日志关联
- ❌ 不再依赖 Vite 代理的隐式 base URL（写死 `/api/v1/export`）

---

## 测试契约

### 单元（`src/api/__tests__/export.test.ts`）

```text
- mock 200 → 返回 Blob
- mock 400 EMPTY_CONTENT → 抛 ExportError(code='EMPTY_CONTENT')
- mock 401 → 抛 ExportError(code='UNAUTHORIZED')
- mock 404 → 抛 ExportError(code='UNKNOWN', status=404)
- mock 500 RENDER_FAILED → 抛 ExportError(code='RENDER_FAILED')
```

### 契约测试（`backend/tests/contract/test_export_contract.py`）

```text
- POST /export/render 无 token → 401
- POST /export/render markdown="" → 400 EMPTY_CONTENT
- POST /export/render style_id="invalid" → 400 INVALID_STYLE
- POST /export/render format="gif" → 400 INVALID_FORMAT
- POST /export/render 正常 → 200 + application/pdf
```

### E2E（`e2e/resume/pdf-export-flow.spec.ts`）

```text
1. 登录 → 新建简历 → 加 1 个块
2. 点击「导出 → PDF 文件」
3. 断言：浏览器下载非空 PDF（page.on('download') 拦截）
4. 断言：toast 显示「导出成功」
5. 模拟后端 500 → toast 显示「导出服务暂不可用，请稍后重试」
```

---

## 验收对应

- FR-008 ✓ 走已有契约
- FR-009 ✓ 错误可读 + 后端结构化
- SC-002 ✓ 100% 走 200 或可读 4xx/5xx
