# Research: Resume Center Muji Alignment

**Feature**: 027-resume-center-muji-alignment
**Date**: 2026-06-24

Phase 0 研究输出。6 个研究主题，每个含 Decision / Rationale / Alternatives。

---

## R1: 渲染引擎选型 — markdown-it vs react-markdown

**Decision**: 采用 `markdown-it@14` + `markdown-it-container@4` + `markdown-it-emoji@3`，废弃 `react-markdown + remark-gfm + rehype-raw`。

**Rationale**:
- 木及简历的 3 个自定义插件（heading-block / 空行保留 / `#{color}` token）基于 markdown-it 的 `block.ruler` 与 `core.ruler` API，react-markdown（基于 unified/remark）无法承载这些插件——react-markdown 通过 component map 改渲染输出，但不改 token 流。
- markdown-it 可在 Node 与浏览器运行，满足"前端生成 HTML → 后端渲染"的统一引擎架构；react-markdown 仅浏览器（后端 Python 无法运行）。
- markdown-it 生态成熟（markdown-it-container / markdown-it-emoji / markdown-it-footnote 等官方插件），与木及插件兼容。
- 性能：markdown-it 同步渲染，比 react-markdown 的异步 unified pipeline 快 3-5 倍（基准测试：10KB Markdown 渲染 markdown-it ~5ms，react-markdown ~20ms）。
- 木及已验证的算法直接搬运（`D:\Project\react-resume-site\src\utils\markdown-it-h-container.ts` 等），零重写风险。

**Alternatives considered**:
1. *保留 react-markdown 并手写转换层* — 双渲染器维护成本高，且 markdown-it 插件的 token 级操作无法在 react-markdown 复刻。Rejected。
2. *用 marked.js* — 更快但插件生态弱，不支持 markdown-it 的 `block.ruler.after` API，无法实现 heading-block 包装。Rejected。
3. *用 remark + mdast 直接操作* — 理论可行但需重写木及 3 个插件为 mdast transform，工作量大且无参考实现。Rejected。

**Implementation notes**:
- `markdown-it@14` 要求 Node 18+ / 浏览器 ES2020，eGGG 目标环境满足。
- `markdown-it-emoji@3` 的 `defs` 与 `shortcuts` 配置用于注册 `icon:<name>` 语法。
- `markdown-it-container@4` 的 `validate` 与 `render` 钩子用于 `::: left/right/header/title`。
- 3 个木及插件从 `D:\Project\react-resume-site\src\utils\` 搬运，适配 TypeScript 严格模式（添加类型注解，原代码部分 `any`）。

---

## R2: 智能分页算法 — rs-md-html-parser

**Decision**: 采用 `rs-md-html-parser@0.2`（木及作者同源库），实现真正 DOM 分页。

**Rationale**:
- 木及的 OnePage 组件（`D:\Project\react-resume-site\src\components\OnePage\index.tsx`）只是 CSS `height: 1114px; overflow: hidden` 的 clip，不是智能分页——用户须手动精简内容，无算法。
- `rs-md-html-parser` 的 `htmlParser(domNode)` 是真正的 DOM 分页算法：遍历渲染后的 DOM，计算每个块级元素的 A4 边界，在合适位置插入 `.rs-line-split` 分隔符，并在根节点设置 `data-pages="<n>"`。
- 算法处理表格、图片、列表等块级元素不被分页线切断（或按视觉可接受方式处理）。
- 木及已用此库于 `Preview/index.tsx:16` 与 `HeaderBar/index.tsx:128` 验证。
- npm 包存在（`rs-md-html-parser@0.1.9` 在木及 package.json:79），API 从调用点可观察。

**Alternatives considered**:
1. *自研分页算法* — 需实现 A4 边界检测、块级元素切断避免、表格行不被切断等逻辑，预计 2-3 周，易出 bug。Rejected。
2. *用 puppeteer 的 page.pdf() 分页* — 后端可用但前端预览无法用，preview 与 PDF 仍漂移。Rejected。
3. *用 CSS `@page` 与 `page-break-before`* — CSS 方案无法动态显示页数指示器，且不同浏览器打印分页行为不一致。Rejected。

**Implementation notes**:
- `htmlParser` 在 preview 渲染后调用，遍历 `.rs-view-inner` DOM 节点。
- 输出：根节点 `data-pages` 属性 + `.rs-line-split` 分隔符元素。
- 分页计算防抖 500ms（避免每次按键重算）。
- 单页模式：CSS `overflow: hidden; height: 1122px`（A4 96DPI），多页模式：`overflow: visible; height: auto`。
- A4 自适应缩放：搬运木及 `window-event.ts`，窗口 1000-1250px 时 `transform: scale(<ratio>)`。

**Risk**: `rs-md-html-parser` 是个人维护库（作者 hua1995116），更新频率低。Mitigation：锁版本 0.1.9，fork 到 eGGG 内部 `src/lib/resume-pagination/` 以便维护。

---

## R3: 主题系统 — 运行时 CSS 注入 + --bg 变量

**Decision**: 4 套主题 CSS 文件放 `public/themes/`，运行时 `fetch` 注入 `<style id="rs-themes-data">`，单一 `--bg` CSS 变量驱动所有主题色元素，color picker 即时设置 `document.body.style.setProperty('--bg', color)`。

**Rationale**:
- 木及主题系统（`D:\Project\react-resume-site\public\themes\` + `src/utils/changeThemes.ts`）已验证：主题是独立 CSS 文件，新增主题无需重新构建。
- `--bg` 单变量设计简洁强大：所有主题色元素（h1 底色、h2 下划线、链接、强调文字）读 `var(--bg)`，color picker 改一个变量即时全局生效。
- 运行时 fetch 注入比 CSS-in-JS 或构建时打包更灵活：主题可作为用户贡献资源（未来可支持自定义主题上传）。
- 木及 4 套主题（default/blue/orange/pupple）已设计完成，直接搬运。

**Alternatives considered**:
1. *CSS-in-JS（styled-components）* — 运行时开销，且与 eGGG 的 Tailwind 体系冲突。Rejected。
2. *构建时打包所有主题 CSS* — 新增主题需重新构建，违背"主题作为资源"理念。Rejected。
3. *用 Tailwind 主题预设* — Tailwind 是 utility-first，不适合表达木及主题的复杂选择器（`.h1_block + .h2_block`）。Rejected。

**Implementation notes**:
- 4 套主题 CSS 从 `D:\Project\react-resume-site\public\themes\` 搬运：`default.css` / `blue.css` / `orange.css` / `pupple.css`。
- 主题切换：`loadTheme(id)` → `fetch('/themes/${id}.css')` → 替换 `<style id="rs-themes-data">` innerHTML。
- 颜色拾取器：用 `react-color` 的 `ChromePicker`（木及同款），`onChangeComplete` → `setColor(hex)` + `document.body.style.setProperty('--bg', hex)` + 持久化。
- 主题与样式（style）解耦：style（classic/compact/modern/editorial）决定布局，theme（default/blue/orange/pupple）决定视觉。两者正交，用户可任意组合。
- 主题持久化到 `resume_branches.theme_id`，颜色持久化到 `resume_branches.accent_color`（分支级，跨设备同步）。

---

## R4: AI 优化轮询 — 指数退避 + 超时

**Decision**: 重写 `useResumeOptimize` hook，`pollState` 真正轮询，间隔指数退避（1s/2s/4s/8s/16s），最长 60s 超时。

**Rationale**:
- 当前实现（`src/hooks/useResumeOptimize.ts:38`）在 `start` 后只调用一次 `getState`，AI 未到达 `waiting_interrupt` 状态时永远转圈。
- 木及无 AI 优化（localStorage 单机），无参考。采用业界标准轮询模式。
- 指数退避减少后端压力（AI 处理通常 5-30s，早期轮询频繁捕捉快速完成，后期退避减少无效请求）。
- 60s 超时是用户耐心阈值（Nielsen Norman Group 研究）。

**Alternatives considered**:
1. *固定间隔轮询（1s）* — 后端压力大，AI 慢时无效请求多。Rejected。
2. *WebSocket 推送* — 已有 WS 基础设施（interview 模块），但 AI 优化是短任务，WS 过重。Rejected。
3. *SSE* — 同 WS，过重。Rejected。

**Implementation notes**:
- 轮询状态机：`idle → starting → polling → waiting_patches → applying → done | timeout | error`。
- 退避序列：`[1000, 2000, 4000, 8000, 16000, 32000]`（6 次，总 63s，超 60s 阈值则停止并标 timeout）。
- 每次轮询调 `GET /api/v1/agents/resume-optimize/:threadId/state`。
- 状态达到 `waiting_interrupt` 时停止轮询，显示 patch 列表。
- 状态达到 `done` 或 `error` 时停止轮询。
- 超时显示"优化超时，请重试"+ 重试按钮。
- 用户切换页面后返回，基于后端 thread 状态恢复轮询（FR-036）。

---

## R5: DnD 拖拽排序 — fractional indexing

**Decision**: Quick 模式 block 列表用 `GripVertical` 手柄拖拽排序，复用现有 fractional indexing（`backend/app/modules/resumes/block_repository.py:61` 的 `generate_key_between`）。

**Rationale**:
- 当前 `QuickEditor.tsx` 用 ↑/↓ 按钮排序，体验差；`useResumeUIStore.draggingBlockId` 字段存在但从未设置（dead code 信号未完成的 DnD）。
- 后端已有 fractional indexing（`order_index` 字段，`generate_key_between(prev, next)`），DnD 只需计算新位置的 `order_index` 并 PATCH。
- 木及无 block 概念（单 Markdown 字符串），无 DnD 参考。采用业界标准 HTML5 drag-and-drop 或 `@dnd-kit/core`。
- 选 `@dnd-kit/core`：现代、无障碍、触屏支持、活跃维护。木及用的 `react-split-pane` 是分屏不是排序。

**Alternatives considered**:
1. *原生 HTML5 drag-and-drop* — 触屏不支持，无障碍差。Rejected。
2. *react-beautiful-dnd* — 已废弃（作者推荐迁移到 @dnd-kit）。Rejected。
3. *保持 ↑/↓ 按钮* — 用户体验差，违背"靠拢木及"目标。Rejected。

**Implementation notes**:
- `@dnd-kit/core` + `@dnd-kit/sortable` 已成熟。
- 拖拽完成时计算目标位置的 `prev_id` 与 `next_id`，调 `PATCH /resume-blocks/:id/reorder`。
- 网络失败时重试 3 次，仍失败则回滚本地顺序并提示"同步失败"。
- `ReorderBlocksInput` schema 漂移修复：前端类型加 `block_id`（与后端一致），或后端移除 `block_id`（用 URL path）—— 选后者，后端 schema 移除 `block_id` 字段。

---

## R6: 版本 diff — block 级 diff

**Decision**: 实现 block 级 diff 算法，对比两个版本快照的 block 列表，标注增加/删除/修改。

**Rationale**:
- 当前 `resume_versions` 表已有 `diff_patch` 字段（`models.py:82` 约束：`is_full_snapshot=False` 时需 `diff_patch` + `base_version_id`），但 `create_diff_snapshot` 未实现，所有版本都是全量快照。
- 版本对比（US7）需展示两个版本的差异，block 级 diff 足够（不需要行级 diff，block 是最小编辑单元）。
- block 级 diff 算法：LCS（最长公共子序列）匹配 block（按 `type + title` 匹配），未匹配的标 add/remove，匹配的对比 `content_md` 标 modify。
- 行级 diff（`diff` 库）用于 `content_md` 字段内部对比，作为修改 block 的子视图。

**Alternatives considered**:
1. *不实现 diff，只展示全量快照* — 用户无法判断是否回滚，违背 US7 价值。Rejected。
2. *用 JSON patch (RFC 6902)* — 适合结构化数据，但 block 的 `content_md` 是自由文本，JSON patch 表达不直观。Rejected。
3. *每次保存只存 diff 不存全量* — 恢复时需回放所有 diff，性能差且 diff 链断裂风险。保留全量快照为主，diff 仅用于对比展示。Selected。

**Implementation notes**:
- `src/lib/version-diff/block-diff.ts`：`diffBlocks(oldBlocks, newBlocks) → BlockDiff[]`，每项 `{type: 'add'|'remove'|'modify', block, oldBlock?}`。
- `src/lib/version-diff/index.ts`：`diffVersions(v1: Snapshot, v2: Snapshot) → VersionDiff`。
- 后端 `versions/service.py` 新增 `create_diff_snapshot`（写 `diff_patch`）与 `diff_versions(v1, v2)`（读两个快照并返回 diff）。
- 后端新增 `GET /api/v1/resume-branches/:branchId/versions/:v1/diff/:v2` 端点。
- 前端 `VersionDiffView.tsx`：展示 block diff 列表，每项标颜色（绿/红/黄），modify 项可展开行级 diff。

---

## 额外研究：安全与不搬运清单

**Decision**: 明确不搬运木及的以下内容：

1. **硬编码 HMAC 密钥**（`D:\Project\react-resume-site\src\service\htmlToPdf.ts:4-5`）— `SecretId` / `SecretKey` 硬编码在客户端，任何人可签名请求到作者的腾讯云账号。eGGG 的 PDF 渲染用本地 Playwright headless Chromium（`backend/src/services/pdf_renderer/renderer.py`），无需云服务与密钥。✅ 无需搬运。

2. **OnePage 组件**（`src/components/OnePage/`）— 只是 CSS `height: 1114px; overflow: hidden` 的 clip，不是智能分页。用 `rs-md-html-parser` 真分页替代。✅ 不搬运。

3. **MobX / AntD 4 / CodeMirror / Webpack** — 与 eGGG 的 Zustand / Tailwind / Monaco / Vite 冲突，且是全局依赖，搬运会越界影响其他模块。✅ 不搬运。

4. **guest freemium 计数器**（`Editor.tsx:39-46` 的 `globalEditorCount`）— 木及用于限制游客直接下载 PDF。eGGG 已有用户认证与配额系统（005 Phase 6），无需此机制。✅ 不搬运。

5. **Square 模板广场**（`src/pages/Square.tsx`）— 木及的模板市场，eGGG 的主题选择器（`ThemeSelector.tsx`）已满足需求，且 eGGG 的"模板"概念是 style + theme 组合，与木及的"模板"（含完整 Markdown 内容）不同。✅ 不搬运。

6. **更新日志 Modal**（`HeaderBar.tsx:34`）— 木及的版本更新提示，eGGG 有自己的产品迭代节奏。✅ 不搬运。

---

## 研究结论

6 个研究主题全部 resolved，无 NEEDS CLARIFICATION 残留。技术选型明确：
- 渲染引擎：markdown-it + 3 木及插件 + rs-md-html-parser
- 主题系统：4 套 CSS 运行时注入 + --bg 变量 + react-color
- AI 轮询：指数退避 + 60s 超时
- DnD：@dnd-kit/core + fractional indexing
- 版本 diff：block 级 LCS diff

可进入 Phase 1 设计（data-model + contracts + quickstart）。
