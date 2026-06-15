# Quickstart: Resume Editor Enhancement

**Date**: 2026-06-13 | **Feature**: 002-resume-editor-enhancement

## Prerequisites

- Node.js 18+ with npm
- Python 3.11+ with uv (for PDF rendering service)
- PostgreSQL (existing project database)
- Puppeteer dependencies installed (Chromium)

## Setup

```bash
# 1. Install frontend dependencies
npm install @monaco-editor/react react-markdown remark-gfm remark-parse rehype-raw unified

# 2. Install Python PDF service dependencies
cd backend
uv pip install fastapi uvicorn playwright markdown pyyaml
playwright install chromium  # Install Chromium for Puppeteer-equivalent

# 3. Apply database migration
psql $DATABASE_URL -c "
ALTER TABLE resume_branches
ADD COLUMN IF NOT EXISTS style_preference VARCHAR(64) NOT NULL DEFAULT 'compact-one-page';
"

# 4. Start frontend dev server
npm run dev

# 5. Start PDF rendering service (separate terminal)
cd backend
python -m src.services.pdf_renderer.server --port 9000
```

## Validation Scenarios

### VS-1: WYSIWYG Mode Toggle

1. Open browser to resume list page (`/resume`)
2. Click on a resume branch to enter the editor
3. Verify the editor opens in Quick Mode (current block-card UI)
4. Click the mode toggle in the top toolbar → select "所见即所得"
5. **Expected**: Page transforms to split-pane: left is Monaco Markdown editor with all block content merged, right is A4 resume preview
6. Click mode toggle → select "快捷模式"
7. **Expected**: Returns to block-card view; content preserved

### VS-2: Markdown Editing with Live Preview

1. In WYSIWYG mode, type in the left editor
2. **Expected**: Right preview updates within 1 second of stopping typing
3. Modify a section heading (e.g., change "## 技能" to "## 技术技能")
4. **Expected**: Preview reflects the change immediately
5. Add a new section with `## 新模块`
6. **Expected**: Preview shows new section

### VS-3: Export — Markdown

1. In the editor, click Export button in toolbar → "导出 Markdown"
2. **Expected**: Browser downloads a `.md` file containing the full resume Markdown
3. Open the downloaded file → verify content matches editor

### VS-4: Export — PDF

1. Click Export → "导出 PDF"
2. **Expected**: Loading spinner while rendering (backend), then browser downloads a `.pdf`
3. Open PDF → verify A4 layout, correct styling, content matches preview

### VS-5: Export — Image

1. Click Export → "导出 PNG"
2. **Expected**: Browser downloads a `.png` at 2x resolution (~1654×2339px)
3. Verify image quality is sharp

### VS-6: Import Markdown

1. Prepare a test `.md` file:
   ```markdown
   # 测试简历
   
   ## 个人简介
   这是一个测试简历。
   
   ## 技能
   - React
   - TypeScript
   ```
2. Go to resume list page (`/resume`)
3. Click "导入 Markdown" button
4. Select the test file
5. **Expected**: Modal appears with branch name pre-filled as "测试简历"
6. Confirm → redirected to editor with 3 blocks created (heading, summary, skill)

### VS-7: Primary Resume Card

1. Ensure at least one main resume exists (is_main = true)
2. Go to resume list page
3. **Expected**: A full-width horizontal card at the top showing:
   - Resume name, status badge, company/position
   - "主简历 (数据源)" label
   - Text preview of first few lines of content
4. Below the card → grid of other resume branch cards
5. Delete the main resume → primary card area hidden

### VS-8: Style Switching

1. In editor (WYSIWYG mode), open style selector dropdown in toolbar
2. Select "现代双栏"
3. **Expected**: Preview re-renders with two-column layout; content unchanged
4. Switch back to "紧凑一页" → preview returns to single-column
5. Navigate away and back → style remembered
6. Create a second branch → switch to "现代双栏" on it
7. Return to first branch → still on "紧凑一页" (per-branch persistence)

### VS-9: Mode Toggle Data Integrity

1. Create a resume with multiple blocks in Quick Mode
2. Set metadata on experience block (company, role)
3. Switch to WYSIWYG → verify metadata appears as frontmatter in editor
4. Edit content in WYSIWYG mode
5. Switch back to Quick Mode → verify blocks recreated with correct types and metadata

### VS-10: Empty State Handling

1. Create a new branch with no blocks
2. Try exporting → "简历内容为空，无法导出"
3. Try switching to WYSIWYG mode → empty editor + empty preview
4. Import an empty `.md` file → error message

### VS-11: PDF Service Unavailable

1. Stop the PDF rendering service
2. Try exporting PDF → "PDF 导出服务暂不可用，您可以先导出 Markdown 格式"
3. Markdown export should still work
4. Image export should still work (if client-side fallback) or show similar error (if server-dependent)

## Running Tests

```bash
# Frontend unit tests
npm test -- --run tests/unit/markdown-converter.test.ts
npm test -- --run tests/unit/markdown-parser.test.ts

# Frontend component tests
npm test -- --run tests/component/WysiwygEditor.test.tsx
npm test -- --run tests/component/PrimaryResumeCard.test.tsx

# Backend PDF service tests
cd backend
python -m pytest tests/test_pdf_renderer.py -v

# E2E tests
npx playwright test tests/e2e/resume-editor.spec.ts
npx playwright test tests/e2e/resume-export.spec.ts
```

## Expected Outcome

After completing all validation scenarios, users should be able to:
- Edit resumes in both Quick Mode and WYSIWYG mode with seamless switching
- Export resumes to Markdown, PDF (server-rendered), PNG, and JPEG
- Import Markdown resumes from external sources
- Identify the main resume at a glance via the prominent card
- Switch between two resume styles with instant preview updates
