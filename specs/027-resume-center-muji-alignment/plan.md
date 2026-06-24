# Implementation Plan: Resume Center Muji Alignment

**Branch**: `027-resume-center-muji-alignment` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-resume-center-muji-alignment/spec.md`

## Summary

参照木及简历（`D:\Project\react-resume-site`）全面优化 InterCraft 简历中心。核心改造：

1. **统一渲染引擎**（US1, P1）— 废弃前端 `react-markdown + remark-gfm + rehype-raw` 与后端自研 Python markdown 解析器，改用 `markdown-it` + 3 个木及自定义插件（heading-block 包装 / 空行保留 / `#{color}` token）+ `rs-md-html-parser` 智能分页。前端生成完整 HTML（含主题 CSS + 分页标记），后端 PDF 渲染器只保留 Playwright 渲染壳，彻底消除 preview 与 PDF 漂移（修复 002 FR-010 未达成问题）。
2. **智能分页预览**（US2, P1）— A4 真实分页线 + 页数指示器 + 单页/多页模式切换。
3. **主题系统与 color picker**（US3, P1）— 4 套木及主题 CSS 运行时注入 `<style>` + 单一 `--bg` CSS 变量驱动所有主题色元素 + color picker 即时生效。
4. **木及自定义语法**（US4, P2）— `::: left/right/header/title` 容器 + `icon:<name>` 14 个品牌图标 + `#{color}` token + 空行保留 + heading-block 结构化包装。
5. **AI 优化增强**（US5, P1）— pollState 真轮询（指数退避 + 60s 超时）/ per-patch 接受拒绝 / diff 视图 / 确认对话框。
6. **编辑器交互增强**（US6, P2）— DnD 拖拽排序 / 列表搜索筛选排序 / refresh-from-parent 确认 / Markdown 工具栏 / 键盘快捷键。
7. **版本对比与本地历史**（US7, P2）— 版本 diff 视图 / localStorage 8 条 FIFO 历史 / 模式+分屏+滚动持久化。

**保留 eGGG 结构化优势**：block 模型 + version 快照 + COW 分支 + AI 优化（木及没有，因是 localStorage 单机应用）。改动局限在简历中心，不动全局基础设施与其他模块。

## Technical Context

**Language/Version**: TypeScript 5.x（严格模式，前端）+ Python 3.12（后端 PDF 渲染）

**Primary Dependencies**:
- *新增*：`markdown-it@14` + `markdown-it-container@4` + `markdown-it-emoji@3` + `@types/markdown-it` + `rs-md-html-parser@0.2`（智能分页）+ `react-color@2`（color picker，已有？检查）
- *保留*：React 18, Vite, TailwindCSS, react-router-dom, @tanstack/react-query, Zustand, @monaco-editor/react（Code 模式 Markdown 编辑器）
- *废弃*：`react-markdown` + `remark-gfm` + `rehype-raw`（被 markdown-it 替代，但暂不卸载以防其他模块引用 —— 实际仅 ResumePreview 使用，确认后可卸载）
- *后端*：FastAPI, SQLAlchemy 2.0, Alembic, Playwright（已有，PDF 渲染）
- *木及源码搬运*：`markdown-it-h-container.ts` / `markdown-it-n.ts` / `plugins.ts`（colorPlugin） / `svgMap.ts`（14 图标） / `window-event.ts`（A4 自适应缩放） / `public/themes/*.css`（4 套主题） — 从 `D:\Project\react-resume-site\src\utils\` 和 `public\themes\` 搬运，适配 TypeScript 严格模式

**Storage**:
- PostgreSQL：`resume_branches` 表新增 `theme_id`（VARCHAR(32)，default 'default'）与 `accent_color`（VARCHAR(7) HEX，default '#39393a'）两列（Alembic 迁移）
- `resume_versions` 表：`diff_patch` 字段已存在但未实现，本 feature 实现 diff 快照写入与读取
- localStorage：`rs-history-{branchId}`（8 条 FIFO 编辑历史）/ `rs-ui-pref-{branchId}`（mode + splitRatio + scrollPos）/ 全局 `rs-theme-{branchId}` + `rs-color-{branchId}`（分支级主题与颜色，与后端 branch 字段同步）

**Testing**: Vitest（前端单元/组件）+ pytest（后端单元/集成）+ Playwright（E2E，`tests/e2e/resume-center/` + 新增 `tests/e2e/027-resume-muji.spec.ts`）

**Target Platform**: Web（桌面 ≥1024px 编辑器；移动端列表页响应式）+ 后端 PDF 服务（Linux/Windows，Playwright headless Chromium）

**Project Type**: Web application（前端 SPA + 后端 FastAPI + PDF 渲染服务）

**Performance Goals**:
- 预览渲染 ≤ 500ms（防抖 300ms 后）
- 分页计算 ≤ 300ms（防抖 500ms 后）
- 主题切换 ≤ 1s
- 颜色调整实时跟随（< 50ms）
- AI 轮询超时 60s
- 列表搜索筛选 < 200ms
- 拖拽持久化 < 500ms
- PDF 导出 ≤ 5s（单页）/ ≤ 10s（多页）

**Constraints**:
- 改动局限在简历中心（`/resume` + `/resume/:branchId` + `src/components/resume/` + `src/styles/resume-*.css` + `src/lib/markdown-*` + `src/lib/resume-styles/` + `backend/app/modules/resumes/` + `backend/app/modules/versions/` + `backend/src/services/pdf_renderer/`）
- 不动全局基础设施（Zustand / TanStack Query / Tailwind / Vite / React Router / FastAPI / SQLAlchemy / ARQ）
- 不动其他模块（auth / jobs / interviews / errors / ability_profile）
- 不搬运木及的硬编码 HMAC 密钥（`htmlToPdf.ts:4-5`）— PDF 签名必须后端
- 不搬运木及的 OnePage 组件（只是 CSS clip）— 用 rs-md-html-parser 真分页
- 不搬运木及的 MobX / AntD 4 / CodeMirror / Webpack — 保留 Zustand / Tailwind / Monaco / Vite
- 保留 eGGG 的 block 模型 + version 快照 + COW 分支 + AI 优化
- 现有 002/017/019/M16 E2E 测试不回归
- 宪法"安全与隐私"：密钥从环境变量读取，严禁入仓
- 宪法"Test-First"：测试先于实现

**Scale/Scope**: 7 用户故事 / 63 FR / 15 SC / ~20 新增或重写前端文件 / ~5 后端文件 / 1 Alembic 迁移 / ~10 新增 E2E 测试用例

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Phase 0 Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | 渲染引擎（`src/lib/resume-renderer/`）、主题系统（`src/lib/resume-themes/`）、分页（`src/lib/resume-pagination/`）、AI 优化状态机（`src/hooks/useResumeOptimize.ts` 增强）、版本 diff（`src/lib/version-diff/`）各自作为自包含库，有 README + 公开 API + 测试夹具 |
| II. CLI Interface | ✅ PASS | 渲染引擎可被 Node CLI 调用（`src/lib/resume-renderer/cli.ts`）从 Markdown 生成 HTML，用于 E2E 测试夹具与本地调试；后端 PDF 渲染器已有 CLI（`python -m pdf_renderer`） |
| III. Test-First (NON-NEGOTIABLE) | ✅ PASS | 每个 US 先写测试：渲染引擎单元测试（markdown-it 插件输出）→ 分页单元测试（rs-md-html-parser 输出）→ 主题切换组件测试 → AI 轮询 hook 测试 → DnD 集成测试 → E2E 故事 |
| IV. Integration & Sync Testing | ✅ PASS | preview↔PDF 一致性契约测试（同 HTML 输入，前端生成 + 后端渲染对比）；AI 优化端到端（mock LLM）；版本 diff 跨快照对比；DnD 网络断开重试 |
| V. Observability | ✅ PASS | 渲染引擎日志（输入长度 / 输出页数 / 耗时）；AI 轮询日志（thread_id / 轮询次数 / 状态变化）；导出日志（style / format / 耗时 / 字节数）关联 request_id |

### Post-Phase 1 Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | 5 个库确认：`resume-renderer`（README + CLI + 测试夹具）、`resume-pagination`、`resume-themes`、`version-diff`、`resume-styles`（保留）。每个库自包含、有文档、可独立测试 |
| II. CLI Interface | ✅ PASS | `resume-renderer/cli.ts` 暴露 `render-markdown` 命令（markdown→HTML）；后端 PDF 渲染器接收 HTML 经 Playwright 渲染，可 `python -m pdf_renderer --html-file foo.html --format pdf` 调用 |
| III. Test-First (NON-NEGOTIABLE) | ✅ PASS | tasks.md 将为每个 US 先列测试任务：渲染引擎单元测试 → 分页测试 → 主题组件测试 → AI 轮询 hook 测试 → DnD 集成测试 → E2E 故事。每个测试先于实现 |
| IV. Integration & Sync Testing | ✅ PASS | 契约测试：preview↔PDF 一致性（`contracts/render-engine.md` 定义）；AI 端到端（MockLLMClient，复用 021 模式）；版本 diff 跨快照；DnD 网络断开重试（3 次后退避） |
| V. Observability | ✅ PASS | 渲染引擎日志（输入长度/输出页数/耗时）；AI 轮询日志（thread_id/轮询次数/状态变化/退避间隔）；导出日志（format/字节数/耗时）关联 request_id（022 ContextVar） |

**Phase 1 完成**：`research.md`（6 主题全 resolved）、`data-model.md`（2 列扩展 + 2 localStorage 实体 + diff_patch 启用）、`contracts/`（3 契约：render-engine / pdf-export / ai-optimize）、`quickstart.md`（7 场景 + 回归 + 单元 + 构建 checklist）。

## Project Structure

### Documentation (this feature)

```text
specs/027-resume-center-muji-alignment/
├── plan.md              # This file
├── research.md          # Phase 0: 渲染引擎选型、分页算法、主题系统、AI 轮询、DnD、版本 diff 研究
├── data-model.md        # Phase 1: theme_id/accent_color 列、diff_patch 实现、LocalHistoryEntry、AIOptimizePatch
├── quickstart.md        # Phase 1: 端到端验证指南（渲染引擎 CLI + E2E 测试命令）
├── contracts/
│   ├── render-engine.md       # 渲染引擎公开 API（markdown→HTML+分页）
│   ├── pdf-export.md          # 后端 PDF 导出契约（接收 HTML 而非 Markdown）
│   └── ai-optimize.md         # AI 优化轮询与 patch 契约
├── checklists/
│   └── requirements.md  # 已生成（spec 阶段）
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
# 前端 — 简历中心渲染引擎与组件
src/
├── lib/
│   ├── resume-renderer/          # 【新】统一渲染引擎库（Library-First）
│   │   ├── README.md             # 公开 API + 用法 + 测试夹具
│   │   ├── index.ts              # renderMarkdown(md, opts) → { html, pageCount }
│   │   ├── markdown-it-plugins/
│   │   │   ├── heading-block.ts  # 搬运木及 markdown-it-h-container.ts
│   │   │   ├── blank-line.ts     # 搬运木及 markdown-it-n.ts
│   │   │   ├── color-token.ts    # 搬运木及 plugins.ts colorPlugin
│   │   │   └── containers.ts     # ::: left/right/header/title
│   │   ├── icons/
│   │   │   └── svg-map.ts        # 搬运木及 svgMap.ts（14 品牌图标）
│   │   ├── parser.ts             # markdown-it 实例组装
│   │   └── cli.ts                # CLI: markdown → HTML（测试夹具用）
│   ├── resume-pagination/         # 【新】智能分页库
│   │   ├── README.md
│   │   ├── index.ts               # paginate(domNode) → { pages, separators }
│   │   └── window-scale.ts       # 搬运木及 window-event.ts A4 自适应缩放
│   ├── resume-themes/            # 【新】主题系统库
│   │   ├── README.md
│   │   ├── index.ts               # loadTheme(id) / listThemes() / applyColor(hex)
│   │   └── registry.ts            # 4 套主题元数据（default/blue/orange/pupple）
│   ├── version-diff/             # 【新】版本 diff 库
│   │   ├── README.md
│   │   ├── index.ts               # diffVersions(v1, v2) → DiffResult
│   │   └── block-diff.ts          # block 级 diff 算法
│   └── resume-styles/             # 【保留】现有 4 套样式元数据（classic/compact/modern/editorial）
│       └── index.ts               # 与 resume-themes 协作：style 决定布局，theme 决定视觉
├── styles/
│   ├── resume-classic-one-page.css   # 【保留】布局样式（与 theme 解耦）
│   ├── resume-compact-one-page.css
│   ├── resume-modern-two-column.css
│   └── resume-editorial.css
├── components/
│   └── resume/
│       ├── editor/
│       │   ├── ResumePreview.tsx     # 【重写】用 resume-renderer 替代 react-markdown
│       │   ├── MarkdownEditor.tsx    # 【增强】加格式工具栏 + 图标选择器
│       │   ├── MarkdownToolbar.tsx   # 【新】bold/italic/header/list/link/icon 按钮
│       │   ├── IconPicker.tsx        # 【新】14 图标选择器
│       │   ├── QuickEditor.tsx       # 【增强】DnD 拖拽手柄替代 ↑/↓ 按钮
│       │   ├── UnifiedToolbar.tsx    # 【增强】主题选择器 + color picker + 单页/多页切换
│       │   ├── ThemeSelector.tsx     # 【新】4 套主题缩略图选择器
│       │   ├── ColorPicker.tsx       # 【新】react-color 集成
│       │   ├── PageIndicator.tsx     # 【新】"1/2 页" 指示器 + 单页模式切换
│       │   └── VersionDiffView.tsx   # 【新】版本 diff 视图（增加/删除/修改标注）
│       ├── AiOptimizePanel.tsx       # 【重写】pollState 轮询 + per-patch + diff + 确认
│       └── list/
│           └── ResumeListToolbar.tsx # 【新】搜索 + 状态筛选 + 排序
├── pages/
│   ├── ResumeList.tsx               # 【增强】接入 ResumeListToolbar + PrimaryResumeCard hover 操作
│   └── ResumeEditor.tsx             # 【增强】接入新渲染引擎 + 主题 + 分页 + AI 增强 + DnD
├── hooks/
│   └── useResumeOptimize.ts         # 【重写】pollState 真轮询（指数退避 + 60s 超时）
├── stores/
│   └── useResumeUIStore.ts          # 【增强】+ splitRatio + scrollPos + 本地历史
└── api/
    └── types.ts                     # 【扩展】ResumeBranch +theme_id +accent_color；AIOptimizePatch +accepted

# 前端主题资源（运行时 fetch 注入）
public/
└── themes/                          # 【新】搬运木及 4 套主题 CSS
    ├── default.css
    ├── blue.css
    ├── orange.css
    ├── pupple.css
    └── README.md                    # 如何新增主题

# 后端 — PDF 渲染器重构
backend/
├── app/
│   ├── modules/
│   │   ├── resumes/
│   │   │   ├── models.py            # 【扩展】ResumeBranch +theme_id +accent_color
│   │   │   ├── schemas.py           # 【扩展】PatchBranchInput +theme_id +accent_color
│   │   │   ├── service.py           # 【扩展】refresh_from_parent 保留确认语义
│   │   │   └── api.py               # 【扩展】list 支持 search/status/sort 参数
│   │   └── versions/
│   │       ├── service.py           # 【扩展】create_diff_snapshot + diff_versions
│   │       ├── repository.py        # 【扩展】create_diff_snapshot 实现
│   │       └── api.py               # 【扩展】GET /versions/{v1}/diff/{v2}
│   └── api/v1/export.py             # 【重构】接收 HTML 而非 Markdown
├── src/services/pdf_renderer/
│   ├── renderer.py                  # 【重构】废弃 _markdown_to_html，接收 HTML 直接渲染
│   ├── styles/                      # 【废弃】不再需要后端 CSS（前端生成 HTML 时内联）
│   └── templates/                   # 【重构】单一模板，接收 {{HTML_BODY}} + {{STYLE_CSS}}
├── migrations/
│   └── versions/xxxx_add_theme_to_resume_branch.py  # 【新】Alembic 迁移
└── tests/
    └── test_pdf_renderer_html.py    # 【新】HTML→PDF 渲染契约测试

# E2E 测试
tests/e2e/
├── 027-resume-muji/
│   ├── render-engine.spec.ts        # US1: preview↔PDF 一致性
│   ├── pagination.spec.ts           # US2: 智能分页
│   ├── themes.spec.ts               # US3: 主题系统 + color picker
│   ├── custom-syntax.spec.ts        # US4: 容器/图标/颜色 token/空行
│   ├── ai-optimize.spec.ts          # US5: AI 优化增强
│   ├── editor-ux.spec.ts            # US6: DnD/搜索/确认/工具栏/快捷键
│   └── version-diff.spec.ts         # US7: 版本对比 + 本地历史
└── resume-center/                   # 【保留】现有 002/017/019/M16 测试不回归
```

**Structure Decision**: Web application（前端 SPA + 后端 FastAPI + PDF 服务）。三个核心库遵循 Library-First：
- `src/lib/resume-renderer/` — 渲染引擎（markdown→HTML+分页标记），可被 Node CLI 调用
- `src/lib/resume-themes/` — 主题系统（CSS 资源加载 + --bg 变量）
- `src/lib/version-diff/` — 版本 diff 算法（block 级 diff）

保留现有 `src/lib/resume-styles/`（布局样式元数据）与 `src/styles/resume-*.css`（布局 CSS），与 `resume-themes`（视觉主题）解耦：style 决定布局（单栏/双栏），theme 决定视觉（颜色/字体/装饰）。

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 在简历中心引入 markdown-it 替代 react-markdown | 木及渲染引擎依赖 markdown-it 插件生态（markdown-it-container / markdown-it-emoji），react-markdown 无法承载这些插件；且统一渲染引擎需前后端共用，markdown-it 可在 Node 与浏览器运行，react-markdown 仅浏览器 | 保留 react-markdown 并手写转换层 — 双渲染器维护成本高，且无法复用木及已验证的 3 个插件算法 |
| 后端 PDF 渲染器改为接收 HTML 而非 Markdown | 统一渲染引擎要求 preview 与 PDF 用同一 HTML 生成器；若后端继续解析 Markdown 则漂移无法消除 | 后端保留 Markdown 解析并增强至前端同等能力 — 需在 Python 重写 markdown-it 3 个插件与 GFM，工作量倍增且永远落后前端 |
| resume_branches 表新增 theme_id + accent_color 列 | 主题与颜色需分支级持久化（spec FR-018/019），localStorage 无法跨设备同步 | 仅用 localStorage — 用户换设备登录后主题丢失，违背"远端存储"承诺 |
| 搬运木及 svgMap.ts 14 个品牌图标 SVG | 木及已验证的图标集，重新设计成本高且视觉不一致 | 用 iconfont 或 SVG sprite — 需额外构建步骤，且木及图标已是内联 SVG 零依赖 |
| 引入 rs-md-html-parser 依赖 | 木及验证过的 DOM 分页算法，自研需重写 A4 边界检测 + 块级元素切断避免逻辑 | 自研分页 — 木及 OnePage 只是 CSS clip 不算真分页，自研正确分页需 2-3 周且易出 bug |

*所有违规均为"靠拢木及"的必要技术决策，已在 spec Clarifications 与 Assumptions 中记录用户授权。*

## Phase 0: Research (research.md)

（详见 `research.md` — 6 个研究主题：渲染引擎选型 / 分页算法 / 主题系统 / AI 轮询 / DnD / 版本 diff）

## Phase 1: Design (data-model.md, contracts/, quickstart.md)

（详见对应文件）
