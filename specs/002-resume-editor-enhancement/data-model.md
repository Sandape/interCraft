# Data Model: Resume Editor Enhancement

**Date**: 2026-06-13 | **Feature**: 002-resume-editor-enhancement

## Schema Changes

### `resume_branches` table (ALTER)

Add one nullable column for style preference:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `style_preference` | VARCHAR(64) | `'compact-one-page'` | Which resume style template to use. Values: `'compact-one-page'`, `'modern-two-column'` |

**SQL**:
```sql
ALTER TABLE resume_branches
ADD COLUMN style_preference VARCHAR(64) NOT NULL DEFAULT 'compact-one-page';
```

### No other table changes

- **Blocks**: Unchanged — `content_md` continues to store per-block Markdown. Metadata stored in existing `meta` JSONB column.
- **Versions**: Unchanged — snapshots include all branch data.
- **Users/Sessions**: Unchanged.
- **No new tables needed** — styles are defined in CSS/HTML files, not in the database.

## Entity Definitions

### ResumeStyle (logical entity, not a DB table)

Represents a visual style template for resume rendering.

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | string | Style identifier: `'compact-one-page'` or `'modern-two-column'` |
| `label_zh` | string | Chinese display name: `'紧凑一页'` or `'现代双栏'` |
| `label_en` | string | English display name: `'Compact One-Page'` or `'Modern Two-Column'` |
| `description` | string | One-line description of the style |
| `css_path` | string | Path to CSS file (frontend and backend) |
| `template_path` | string | Path to HTML template (backend only) |
| `layout_type` | enum | `'single-column'` or `'two-column'` |

**Style registry** (defined in code as a static array):

```typescript
const RESUME_STYLES: ResumeStyle[] = [
  {
    id: 'compact-one-page',
    label_zh: '紧凑一页',
    label_en: 'Compact One-Page',
    description: '单栏全宽 A4 单页布局，极简设计',
    cssPath: 'compact-one-page.css',
    templatePath: 'compact-one-page.html',
    layoutType: 'single-column',
  },
  {
    id: 'modern-two-column',
    label_zh: '现代双栏',
    label_en: 'Modern Two-Column',
    description: '左窄右宽双栏布局，信息层次清晰',
    cssPath: 'modern-two-column.css',
    templatePath: 'modern-two-column.html',
    layoutType: 'two-column',
  },
];
```

### ExportRequest (API request entity)

Sent to backend PDF/image rendering service.

| Field | Type | Description |
|-------|------|-------------|
| `markdown` | string | Full Markdown content of the resume |
| `style_id` | string | Style identifier (`'compact-one-page'` or `'modern-two-column'`) |
| `format` | enum | `'pdf'`, `'png'`, `'jpeg'` |
| `locale` | string | `'zh'` (affects date formatting, labels) |

### ExportResult (API response entity)

| Field | Type | Description |
|-------|------|-------------|
| `content_type` | string | MIME type (e.g., `'application/pdf'`, `'image/png'`) |
| `filename` | string | Suggested download filename |
| `data` | binary | File binary data (base64 encoded in JSON, or direct binary response) |

### ImportResult (client-side entity)

Result of parsing an imported Markdown file.

| Field | Type | Description |
|-------|------|-------------|
| `branch_name` | string | Extracted or generated branch name |
| `blocks` | Array | Parsed block data ready for creation |
| `warnings` | Array<string> | Non-blocking warnings about unparseable content |

### Block ↔ Markdown Conversion Mapping

Established mapping for bidirectional conversion:

| Block Type | Markdown Representation |
|------------|------------------------|
| `heading` | `# {title}` — always first block |
| `summary` | `## 个人简介` + paragraph content |
| `experience` | `## 工作经历 — {company}` with frontmatter `company:` / `role:` / `duration:` |
| `project` | `## 项目经历 — {title}` with content (bullet points for details) |
| `skill` | `## 技能` followed by `- skill_name` bullet list |
| `education` | `## 教育背景` with structured sub-items |
| `custom` | `## {title}` (preserved as-is) |

**Metadata serialization** (for experience, project blocks):

```markdown
---
company: 字节跳动
role: 高级前端工程师
duration: 2024.01 - 至今
---

## 工作经历 — 字节跳动

- 主导了 XXX 项目的架构设计
- 优化了 YYY 性能，提升 40%
```

## State Transitions

### Style Selection

```
[default: compact-one-page]
         |
         v
[style_preference set on branch]
         |
    +---------+
    |         |
    v         v
[compact]  [modern]
    |         |
    +----+----+
         |
         v
[preview renders with selected style]
[export uses selected style]
[persisted to resume_branches.style_preference]
```

### Editing Mode

```
[page load]
    |
    v
[Quick Mode] ←──→ [WYSIWYG Mode]
    |                   |
    |  mode toggle      |  mode toggle
    |                   |
    v                   v
[blocks preserved]  [aggregated markdown preserved]
```

## Validation Rules

- `style_preference`: Must be one of `['compact-one-page', 'modern-two-column']`
- Imported Markdown: Max file size 100KB, `.md` extension required
- Export: At least one non-empty block required before export is allowed
- Mode switch: Markdown content must parse successfully back to blocks (validation before switch)
