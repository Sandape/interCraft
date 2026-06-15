# Research: Resume Editor Enhancement

**Date**: 2026-06-13 | **Feature**: 002-resume-editor-enhancement

## 1. Markdown Editor Component

**Decision**: `@monaco-editor/react` (Monaco Editor)

**Rationale**:
- Production-grade editor used by VS Code; robust syntax highlighting for Markdown
- Supports CJK (Chinese/Japanese/Korean) input natively
- Configurable minimap, line numbers, word wrap — all relevant for a Markdown writing experience
- Active React wrapper (`@monaco-editor/react`) with TypeScript types
- Large community, well-maintained

**Alternatives considered**:
- **CodeMirror 6** (`@codemirror/view`): More lightweight, better extensibility for custom syntax. Rejected because Monaco's CJK support and Markdown syntax highlighting are more mature.
- **Simple textarea** (like current `<Textarea>` component): No syntax highlighting, poor UX for Markdown writing. Rejected.
- **Milkdown**: WYSIWYG Markdown editor. Rejected — we want plain Markdown (not WYSIWYG in the editor itself); the "WYSIWYG" is achieved via the split preview pane.

## 2. Markdown Rendering (Preview + Export)

**Decision**: `react-markdown` + `remark-gfm` + `rehype-raw` + custom style CSS

**Rationale**:
- `react-markdown` is the standard for rendering Markdown to React components
- `remark-gfm` adds GitHub Flavored Markdown support (tables, strikethrough, task lists)
- `rehype-raw` allows HTML in Markdown to be rendered (needed for importing Markdown with embedded HTML)
- Custom component overrides allow injecting resume-style CSS classes into rendered elements
- Same rendering pipeline can be used for both frontend preview and backend PDF (backend uses Python markdown → HTML)

**Alternatives considered**:
- **marked**: Faster but produces raw HTML string (dangerouslySetInnerHTML). Rejected for security reasons; `react-markdown` outputs React elements.
- **markdown-it**: Plugin ecosystem but imperative API. Rejected in favor of unified/remark/rehype pipeline.

## 3. Block ↔ Markdown Bidirectional Conversion

**Decision**: Custom converter using remark AST for parsing, template serialization for writing

**Rationale**:
- **Blocks → Markdown** (Quick → WYSIWYG): Straightforward serialization. Each block type maps to a `## {type_label} {title}` heading followed by content. Block metadata (company, role for experience) serialized as YAML frontmatter under the heading.
- **Markdown → Blocks** (WYSIWYG → Quick): Parse with `remark-parse` to get MDAST. Split at `##` headings. Detect block type from heading text pattern (e.g., "## 经历 字节跳动" → experience block with company="字节跳动"). Content under heading becomes `content_md`.

**Conversion mapping**:

| Block Type | Markdown Representation |
|------------|------------------------|
| heading | `# Name` at document top |
| summary | `## 简介` or `## Summary` |
| experience | `## 经历 {company}` with YAML frontmatter for meta |
| project | `## 项目 {title}` |
| skill | `## 技能` with `- skill_name` bullet list |
| education | `## 教育` with structured sub-items |
| custom | `## {custom_title}` (preserve as-is) |

## 4. Resume Style System

**Decision**: CSS-based style templates with HTML page templates for backend rendering

**Rationale**:
- Each style = one CSS file + one HTML template file
- Frontend preview: Apply style CSS to the rendered Markdown output via a wrapper div with style-specific class
- Backend PDF: Insert Markdown-rendered HTML into the style's HTML template, apply the same CSS, render with Puppeteer
- Style CSS uses CSS custom properties for theme colors, plus layout-specific rules (grid/flex for two-column vs single-column)
- Style selection stored as `style_preference` column on `resume_branches` table (VARCHAR, nullable, defaults to `"compact-one-page"`)

**Style 1 — "紧凑一页" (Compact One-Page)**:
- Single column, full width
- CSS: `compact-one-page.css`
- Template: `compact-one-page.html`
- Colors: Black text on white, one subtle accent (#2563eb blue)
- Font: system-ui sans-serif, name in 24px bold, section headers 14px bold with thin bottom border

**Style 2 — "现代双栏" (Modern Two-Column)**:
- Left sidebar (30%) + right main (70%)
- CSS: `modern-two-column.css`
- Template: `modern-two-column.html`
- Left sidebar: light gray background (#f8f9fa), personal info, education, skills
- Right main: white background, summary, experience, projects
- Colors: Dark text (#1a1a2e), accent (#0f766e teal) for section headers
- Font: system-ui sans-serif, name in 22px bold

## 5. PDF Export Pipeline

**Decision**: Server-side Puppeteer (headless Chrome) via a new backend endpoint

**Rationale**:
- Consistent, pixel-perfect output regardless of client browser
- Full CSS print layout control (page size, margins, page breaks)
- Can reuse CSS from frontend styles (copy to backend templates directory)
- Async: client sends POST with markdown + style_id, backend renders and returns PDF binary

**API flow**:
1. Client `POST /api/export/pdf` with `{ markdown: string, style_id: string }`
2. Backend converts Markdown to HTML (Python `markdown` library with extensions)
3. Backend inserts HTML into style template, applies CSS
4. Backend launches Puppeteer, loads page, calls `page.pdf({ format: 'A4', printBackground: true })`
5. Returns PDF as `application/pdf` binary with appropriate headers
6. Client downloads the blob

**Alternatives considered**:
- **Client-side `window.print()`**: Browser-dependent output, no guarantee of A4 fidelity. Rejected (user explicitly chose server-side).
- **jsPDF client-side**: Cannot render CSS faithfully; requires manual layout. Rejected.
- **WeasyPrint / wkhtmltopdf**: Python alternatives to Puppeteer. Rejected because Puppeteer uses real Chrome rendering engine, ensuring CSS fidelity.

## 6. Image Export

**Decision**: Server-side Puppeteer screenshot at 2x device scale factor

**Rationale**:
- Same backend pipeline as PDF: POST with markdown + style_id
- Puppeteer `page.screenshot({ type: 'png', fullPage: true, deviceScaleFactor: 2 })`
- 2x DPI produces 1654×2339px output (A4 at 192 DPI)
- JPEG variant: convert with `sharp` or Pillow for smaller file size

**Endpoint**: `POST /api/export/image` with `{ markdown: string, style_id: string, format: 'png' | 'jpeg' }`

**Alternatives considered**:
- **html-to-image / dom-to-image (client-side)**: Works offline, but limited CSS support. Rejected for primary flow; could be a future offline fallback.
- **Reuse PDF endpoint + convert**: Adding complexity. Direct screenshot is simpler.

## 7. Markdown Import

**Decision**: Client-side parsing with `remark-parse` (unified ecosystem), heuristic block type detection

**Rationale**:
- Parse the uploaded `.md` file into MDAST
- Traverse the AST to identify:
  - Top-level `# heading` → resume name (branch name)
  - `## heading` with known patterns → block boundaries
  - Content between headings → block content
  - YAML frontmatter → metadata
- Block type detection by heading text:
  - Contains "经历"/"experience"/"工作" → `experience`
  - Contains "项目"/"project" → `project`
  - Contains "技能"/"skill" → `skill`
  - Contains "教育"/"education" → `education`
  - Contains "简介"/"summary"/"关于" → `summary`
  - Otherwise → `custom`

**File constraints**:
- Max file size: 100KB
- Must be `.md` extension
- Client-side parsing avoids uploading raw content to server

## 8. Primary Resume Card Design

**Decision**: Full-width `Card` component above the grid, reusing existing API data

**Rationale**:
- No backend changes needed — `is_main` already exists on branches
- Card layout: horizontal flex with icon/avatar area (left), metadata (center), action buttons (right)
- Content preview: first 150 characters of the main branch's first block's `content_md`
- Visual distinction: larger padding, subtle gradient or border accent, "主简历 (数据源)" badge

## 9. Unified Toolbar Design

**Decision**: Single top toolbar bar replacing current scattered controls in WYSIWYG mode

**Rationale**:
- Shared between Quick Mode and WYSIWYG Mode
- Contains (left to right): back link, mode toggle (segmented control), style selector (dropdown), export button (dropdown), version save & history buttons, lock indicator
- In Quick Mode: the toolbar replaces the current header area; block actions (add, move, delete) remain within block cards
- In WYSIWYG Mode: the toolbar sits above the split pane; split pane fills remaining viewport height
