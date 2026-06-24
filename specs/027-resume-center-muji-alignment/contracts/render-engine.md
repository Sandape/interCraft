# Contract: Resume Render Engine

**Feature**: 027-resume-center-muji-alignment
**Library**: `src/lib/resume-renderer/`

统一渲染引擎公开 API，前端预览与后端 PDF 导出共用此引擎。

## 公开 API

### `renderMarkdown(markdown, options) → RenderResult`

```typescript
interface RenderOptions {
  themeId?: string         // default | blue | orange | pupple，默认 'default'
  accentColor?: string     // HEX，默认 '#39393a'
  paginate?: boolean       // 是否分页，默认 true
  styleId?: string         // classic/compact/modern/editorial，决定布局 class
}

interface RenderResult {
  html: string              // 完整 HTML（含主题 CSS 内联 + 分页标记）
  pageCount: number         // 分页数（paginate=false 时为 1）
  styleClass: string        // 应用的布局 class
}
```

**行为**:
1. 用 markdown-it + 3 木及插件（heading-block / blank-line / color-token）+ container + emoji 插件渲染 Markdown → HTML 字符串
2. 应用 `#{color}` token 替换为 `accentColor`
3. （可选）用 rs-md-html-parser 的 `htmlParser` 分页，插入 `.rs-line-split` 与 `data-pages`
4. 注入主题 CSS（fetch 的 CSS 字符串内联到 `<style>`）与布局 style class
5. 返回完整 HTML 片段（不含 `<html>/<head>/<body>`，由调用方包裹）

**契约**:
- 纯函数：相同输入产生相同输出（无随机性）
- 同步可调用（markdown-it 同步，分页需 DOM 故仅浏览器内同步；Node CLI 模式跳过分页）
- 不修改全局状态（除 `<style id="rs-themes-data">` 注入，这是设计意图）

### `paginateDom(domNode) → PaginationResult`

```typescript
interface PaginationResult {
  pageCount: number
  separators: HTMLElement[]  // 插入的 .rs-line-split 元素
}
```

**行为**: 对已渲染的 DOM 节点应用 `rs-md-html-parser` 的 `htmlParser`，返回页数与分隔符。

**用途**: 前端预览区在 Markdown 渲染后调用，实时显示分页线与页数。后端 PDF 导出时也调用（在 Playwright page 内执行）。

### CLI: `render-markdown`

```bash
node --experimental-strip-types src/lib/resume-renderer/cli.ts \
  --input resume.md \
  --theme default \
  --color '#39393a' \
  --style classic-one-page \
  --output resume.html
```

**用途**: E2E 测试夹具生成、本地调试、渲染引擎单元测试输入。

## 渲染管线

```
Markdown 字符串
  ↓ markdown-it.render() + 插件
HTML 字符串（含 .h1_block/.h2_block/.break-line/.lr-container 等结构化 class）
  ↓ colorPlugin: #{color} → accentColor
HTML 字符串（颜色 token 已替换）
  ↓ 注入到 DOM（.rs-view-inner）
渲染后 DOM
  ↓ htmlParser(domNode)
分页后 DOM（含 .rs-line-split + data-pages）
  ↓ 读取 .innerHTML
最终 HTML 字符串
  ↓ 注入主题 CSS + 布局 class
完整 HTML 片段（交付给预览或后端 PDF 渲染）
```

## 支持的 Markdown 语法

### 标准 Markdown
- 标题 `#` ~ `#####`（包装为 `<div class="h<N>_block block">`）
- 段落、换行
- 列表（有序/无序）
- 加粗 `**`、斜体 `*`、删除线 `~~`（GFM）
- 链接 `[text](url)`、图片 `![alt](url)`
- 代码块 ``` 与行内 `code`
- 引用 `>`
- 分隔线 `---`
- 表格（GFM）
- 任务列表 `- [ ]`（GFM）

### 木及扩展语法
- `::: left / ::: right` → `<div class="lr-container"><div class="left">...<div class="right">...`
- `::: header` → `<div class="header-block">...`
- `::: title` → `<div class="title-block">...`
- `icon:<name>` → 内联品牌图标 SVG（14 个：github/email/blog/weixin/juejin/zhihu/weibo/qq/twitter/facebook/csdn/yuque/sifou/phone）
- `[icon:blog label](url)` → 图标 + 文本 + 链接
- `#{color}` → 当前主题强调色 HEX（后渲染替换）
- 连续空行 → `<span class="break-line">` × N（保留垂直间距）

### 内联 HTML
- 允许：`<span>`（含 style）、`<div>`（含 style）、`<img>`、`<a>`、`<strong>`、`<em>`、`<br>`、`<hr>`
- 过滤：`<script>`、`<iframe>`、`<object>`、`<embed>`、`on*` 事件属性、`javascript:` 协议

## 一致性保证

- 前端预览与后端 PDF 导出必须使用相同 `renderMarkdown` 函数
- 后端 PDF 端点接收 `html` 参数（前端生成的完整 HTML），不再接收 `markdown` 自行解析
- 同一 Markdown 多次渲染产生字节级一致输出（除时间戳类动态内容，简历不含此类）

## 测试契约

- 渲染引擎单元测试覆盖所有语法（`src/lib/resume-renderer/__tests__/`）
- preview↔PDF 一致性契约测试：随机生成 10 份不同复杂度 Markdown，前端渲染 HTML → 后端 PDF → 对比视觉（截图 diff < 5% 像素差异）
