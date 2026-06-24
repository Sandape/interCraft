# Quickstart: Resume Center Muji Alignment

**Feature**: 027-resume-center-muji-alignment
**Date**: 2026-06-24

端到端验证指南。每个场景可独立运行，证明对应用户故事已实现。

## 前置准备

```bash
# 1. 后端依赖
cd backend && uv sync

# 2. 前端依赖（新增 markdown-it 等）
cd .. && npm install

# 3. 数据库迁移（新增 theme_id + accent_color 列）
cd backend && uv run alembic upgrade head

# 4. 启动后端
uv run uvicorn app.main:app --reload --port 8000

# 5. 启动前端（新终端）
npm run dev
```

## 场景 1: 统一渲染引擎（US1）— preview↔PDF 一致

**验证**: 同一 Markdown 在预览和 PDF 中渲染一致。

```bash
# 生成测试 HTML（渲染引擎 CLI）
node --experimental-strip-types src/lib/resume-renderer/cli.ts \
  --input tests/e2e/027-resume-muji/fixtures/complex-resume.md \
  --theme default --color '#39393a' --style classic-one-page \
  --output /tmp/resume.html

# 手动检查 HTML 含表格/图片/内联 HTML/链接
grep -c '<table>' /tmp/resume.html  # 应 ≥ 1
grep -c '<img' /tmp/resume.html      # 应 ≥ 1
```

**E2E 自动化**:
```bash
npx playwright test tests/e2e/027-resume-muji/render-engine.spec.ts
```

**预期**: 预览渲染表格/图片/HTML，导出 PDF 与预览视觉一致（截图 diff < 5%）。

## 场景 2: 智能分页（US2）

**验证**: 内容超 A4 时显示分页线与页数指示器。

```bash
npx playwright test tests/e2e/027-resume-muji/pagination.spec.ts
```

**手动验证**:
1. 登录 → 简历中心 → 进入主简历编辑器
2. 切换到 Code 模式
3. 粘贴超长内容（> 1 A4 页）
4. 确认预览区出现分页线 + "2 页" 指示器
5. 点击"单页模式" → 只显示第一页
6. 切回"多页模式" → 显示所有页

## 场景 3: 主题系统 + color picker（US3）

```bash
npx playwright test tests/e2e/027-resume-muji/themes.spec.ts
```

**手动验证**:
1. 编辑器中打开主题选择器 → 4 套主题缩略图
2. 点击"蓝色" → 预览即时切换
3. 打开 color picker → 选新颜色 → 标题底色/分隔线即时变色
4. 离开编辑器返回 → 主题与颜色保留

## 场景 4: 木及自定义语法（US4）

```bash
npx playwright test tests/e2e/027-resume-muji/custom-syntax.spec.ts
```

**手动验证**: 在 Code 模式输入：
```markdown
::: left
# 张三
:::
::: right
icon:github zhangsan
icon:email zhangsan@example.com
:::

## 工作经历

**字节跳动** · 高级前端工程师

<span style="color: #{color}">重点项目</span>
```

确认：两栏布局、GitHub/Email 图标、`#{color}` 跟随主题色。

## 场景 5: AI 优化增强（US5）

```bash
npx playwright test tests/e2e/027-resume-muji/ai-optimize.spec.ts
```

**手动验证**:
1. 编辑器 → AI 优化面板 → 输入 JD → 开始优化
2. 确认轮询进度（而非挂起）
3. patch 列表显示 → 每个 patch 有 diff（绿/红/黄）
4. 勾选部分 patch → 应用 → 确认对话框
5. 确认后新版本创建，只应用勾选的 patch

## 场景 6: 编辑器交互增强（US6）

```bash
npx playwright test tests/e2e/027-resume-muji/editor-ux.spec.ts
```

**手动验证**:
1. Quick 模式拖拽 block 重排
2. 列表页搜索框输入公司名 → 实时筛选
3. 状态筛选下拉 → 选"草稿" → 只显示草稿
4. 派生分支"同步父级" → 确认对话框弹出
5. Code 模式工具栏 → 选中文本 → 点加粗 → `**` 包裹
6. 按 Ctrl+S → 保存版本对话框

## 场景 7: 版本对比与本地历史（US7）

```bash
npx playwright test tests/e2e/027-resume-muji/version-diff.spec.ts
```

**手动验证**:
1. 版本历史抽屉 → 选两个版本 → 对比 → diff 视图（绿/红/黄标注）
2. 编辑内容停顿 2s → localStorage 新增历史条目
3. 切换到 Code 模式 + 调整分屏 → 刷新 → 恢复

## 回归测试（不破坏现有功能）

```bash
# 现有 round-1 + round-2 E2E 全量
npm run e2e

# 或指定现有简历测试
npx playwright test tests/e2e/resume-center/
npx playwright test tests/e2e/M16-resume-optimize.spec.ts
npx playwright test tests/e2e/topbar-new-resume.spec.ts
npx playwright test tests/e2e/019-cross-module-linking.spec.ts
```

**预期**: 全部通过，无回归。

## 单元测试

```bash
# 渲染引擎
npx vitest run src/lib/resume-renderer/

# 分页
npx vitest run src/lib/resume-pagination/

# 主题
npx vitest run src/lib/resume-themes/

# 版本 diff
npx vitest run src/lib/version-diff/

# AI 优化 hook
npx vitest run src/hooks/useResumeOptimize.test.ts

# 后端
cd backend && uv run pytest tests/test_pdf_renderer_html.py -v
cd backend && uv run pytest app/modules/resumes/tests/ -v
cd backend && uv run pytest app/modules/versions/tests/ -v
```

## 类型检查

```bash
npm run typecheck
```

**预期**: 0 errors。

## 构建验证

```bash
npm run build
```

**预期**: 构建成功，`dist/` 含新主题 CSS 资源（`themes/*.css` 复制到 `dist/themes/`）。

## 完成 checklist

- [ ] 场景 1-7 全部通过
- [ ] 回归测试全绿
- [ ] 单元测试全绿
- [ ] 类型检查 0 error
- [ ] 构建成功
- [ ] 后端 Alembic 迁移可逆（downgrade 干净）
- [ ] localStorage 键名带 branchId 隔离
- [ ] 主题 CSS 资源在 `dist/themes/` 可访问
