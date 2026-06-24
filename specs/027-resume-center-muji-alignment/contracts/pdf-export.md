# Contract: PDF Export (Refactored)

**Feature**: 027-resume-center-muji-alignment
**Endpoint**: `POST /api/v1/export/render`（重构）

后端 PDF 渲染器重构为接收前端生成的完整 HTML，不再自行解析 Markdown。

## 重构前（现状）

```http
POST /api/v1/export/render
Content-Type: application/json

{
  "markdown": "# 标题\n\n内容...",
  "style_id": "compact-one-page",
  "format": "pdf"
}
```

后端 `_markdown_to_html(markdown)` 自研解析（只支持 H1/H2/list/bold/frontmatter），与前端 react-markdown 漂移。

## 重构后

```http
POST /api/v1/export/render
Content-Type: application/json

{
  "html": "<div class='resume-style-compact'><style>...主题CSS...</style><div class='rs-view-inner' data-pages='1'>...内容...</div></div>",
  "format": "pdf" | "png" | "jpeg"
}
```

**变更**:
- 移除 `markdown` 与 `style_id` 参数（前端已生成完整 HTML 含 style）
- 新增 `html` 参数（前端 `renderMarkdown` 输出）
- 保留 `format` 参数

## 请求校验

- `html` 必须非空字符串
- `html` 长度 ≤ 1MB（防止超大内容 DoS）
- `format` ∈ {'pdf', 'png', 'jpeg'}
- 危险标签过滤：后端再次过滤 `<script>` / `<iframe>` / `on*` 事件属性（双层防御）

## 响应

成功（200）：
```http
Content-Type: application/pdf | image/png | image/jpeg
Content-Disposition: attachment; filename="resume.pdf"

<binary>
```

失败（400）：
```json
{
  "error": "INVALID_HTML",
  "message": "HTML content is empty or exceeds 1MB limit"
}
```

失败（422）：
```json
{
  "error": "RENDER_FAILED",
  "message": "Playwright rendering timeout"
}
```

## 后端实现

```python
# backend/app/api/v1/export.py — 重构
@router.post("/render")
async def render_resume(req: RenderRequest):
    sanitize_html(req.html)  # 过滤危险标签
    html_doc = wrap_html_document(req.html)  # 包裹 <html><head><meta charset></head><body>...
    result = await render_with_playwright(html_doc, req.format)
    return StreamingResponse(io.BytesIO(result), media_type=...)
```

```python
# backend/src/services/pdf_renderer/renderer.py — 重构
async def render_with_playwright(html: str, format_type: str) -> bytes:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 794, "height": 1123})
        await page.set_content(html, wait_until="networkidle")
        if format_type == "pdf":
            result = await page.pdf(format="A4", print_background=True, margin={"top":"0","bottom":"0","left":"0","right":"0"})
        else:
            result = await page.screenshot(full_page=True, type=format_type, scale="device")
        await browser.close()
        return result
```

**废弃**: `_markdown_to_html`、`_load_css`、`_load_template`、`_escape` 函数全部删除。`styles/` 与 `templates/` 目录废弃（前端生成 HTML 时内联 CSS）。

## 一致性保证

前端 `renderMarkdown(markdown, opts)` 输出的 HTML 与后端 `render_with_playwright(html)` 接收的 HTML 必须完全一致（前端直接 POST 渲染结果，后端不二次处理）。

## 迁移

- ExportMenu.tsx：调用 `renderMarkdown` 生成 HTML，再调 `exportResume({html, format})`
- 后端 export API schema 更新（`RenderRequest` 字段变更）
- 后端测试更新（`test_pdf_renderer_html.py` 新增，旧 `test_pdf_renderer.py` 废弃）
- 前端 `src/api/export.ts`：`exportResume` 参数从 `{markdown, style_id, format}` 改为 `{html, format}`

## 向后兼容

不兼容变更（spec 027 是破坏性重构）：
- `markdown` 与 `style_id` 参数移除
- 旧前端调用会 422 失败

但前端与后端同步发布，无外部消费者，故无需版本化过渡。
