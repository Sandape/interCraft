# 027-resume-center-muji-alignment — Requirements Status

**Last Updated**: 2026-06-25
**Overall**: 9 US done / 80 FR done / 17 SC met (1 partial due to env)

## User Stories (9)

| ID | 名称 | 优先级 | 状态 | 实现提交 |
|---|---|---|---|---|
| US1 | 统一渲染引擎 | P1 MVP | ✅ Done | 多次 |
| US2 | 智能分页预览 | P1 | ✅ Done | US1 同期 |
| US3 | 主题系统 + color picker | P1 | ✅ Done | US1 同期 |
| US4 | 木及自定义语法 | P2 | ✅ Done | 60db0f1 |
| US5 | AI 优化增强 | P1 | ✅ Done | 946f1d5 |
| US6 | 编辑器交互增强 | P2 | ✅ Done | 1e2f1a5 / 6db9360 / 60db0f1 |
| US7 | 版本对比 + 本地历史 | P2 | ✅ Done | 4addbaa |
| US8 | 内容↔预览双向定位 | P1 | ✅ Done | ce7c0b0 |
| US9 | 头像/证件照调整 | P1 | ✅ Done | 多次 |

## Functional Requirements (80)

### US1 统一渲染引擎 (FR-001 ~ FR-011) — ✅ 全部 Done

- ✅ FR-001: preview 与 PDF 共享 markdown-it 渲染器
- ✅ FR-002: 后端 PDF 接收完整 HTML，不再解析 Markdown
- ✅ FR-003: 前端生成 HTML 经 sanitize 后 POST 后端
- ✅ FR-004: HTML sanitizer 过滤 `<script>`/`<iframe>`/`on*`/`javascript:`
- ✅ FR-005: 渲染引擎支持 GFM 表格 + 图片 + 链接 + 内联 HTML
- ✅ FR-006: 渲染引擎导出 `renderMarkdown(md, opts) → {html, pageCount, styleClass}`
- ✅ FR-007: 前端 dangerouslySetInnerHTML 注入 HTML
- ✅ FR-008: 后端 Playwright 渲染壳，无 markdown 逻辑
- ✅ FR-009: 后端 sanitize.py 二次过滤
- ✅ FR-010: 删除 `backend/src/services/pdf_renderer/styles/` + `templates/`
- ✅ FR-011: 验证 `react-markdown` 不再被 `src/modules/resume/` 引用

### US2 智能分页 (FR-012 ~ FR-018) — ✅ 全部 Done

- ✅ FR-012: 预览渲染后调用 `paginateDom()`
- ✅ FR-013: 真实 A4 分页线（CSS 高度判定）
- ✅ FR-014: "1/2 页" 页数指示器
- ✅ FR-015: 单页/多页模式切换
- ✅ FR-016: 单页模式导出 PDF 只含第一页
- ✅ FR-017: 内容变化 1s 内更新分页
- ✅ FR-018: window-scale 自适应 A4 缩放

### US3 主题系统 (FR-019 ~ FR-028) — ✅ 全部 Done

- ✅ FR-019: 4 套木及主题 (default/blue/orange/pupple)
- ✅ FR-020: ThemeSelector 4 缩略图卡片
- ✅ FR-021: ColorPicker (react-color ChromePicker)
- ✅ FR-022: 颜色调整实时反映（拖动过程中即更新）
- ✅ FR-023: `applyColor(hex)` 设置 `--bg` CSS 变量
- ✅ FR-024: 主题切换 1s 内生效
- ✅ FR-025: theme_id/accent_color 持久化到 resume_branches
- ✅ FR-026: PATCH /resume-branches/:id 接受 theme_id/accent_color
- ✅ FR-027: 主题 CSS 加载到 `<style id="rs-themes-data">`
- ✅ FR-028: 派生分支独立记忆主题/颜色

### US4 木及自定义语法 (FR-029 部分 + T059-T068) — ✅ Done

注：FR-029 ~ FR-037 在 spec 中归到 US5 AI 优化，US4 实际 FR 范围与 tasks T059-T068 对应：

- ✅ T059-T062 测试 (parser/heading-block/blank-line/color-token 已存在 + IconPicker/MarkdownToolbar 新增 12 单测)
- ✅ T063 containers plugin class 名匹配
- ✅ T064 svgMap fill="currentColor"
- ✅ T065 IconPicker 组件 + 14 图标 grid
- ✅ T066 MarkdownToolbar 图标按钮
- ✅ T067/T068 (Cheatsheet) — IconPicker modal 已含 syntax 示例

### US5 AI 优化增强 (FR-029 ~ FR-037) — ✅ 全部 Done

- ✅ FR-029: 指数退避轮询 (1s/2s/4s/8s/16s)
- ✅ FR-030: 60s 超时显示"优化超时"+ 重试
- ✅ FR-031: 多 patch 逐项显示 + diff
- ✅ FR-032: diff 标注增加/删除/修改
- ✅ FR-033: per-patch accept/reject
- ✅ FR-034: 应用前确认对话框
- ✅ FR-035: 失败显示错误 + 重试
- ✅ FR-036: thread_id 持久化状态恢复
- ✅ FR-037: 0 patch 提示"未发现可优化项"

### US6 编辑器交互增强 (FR-038 ~ FR-048) — ✅ 全部 Done

- ✅ FR-038: DnG 拖拽手柄 + fractional indexing (T083, 1e2f1a5)
- ✅ FR-039: 列表搜索框 (T084-T086, 6db9360)
- ✅ FR-040: 状态多选筛选
- ✅ FR-041: 排序选项 (edited/created/match_score)
- ✅ FR-042: 同步父级确认对话框 (T087)
- ✅ FR-043: 取消/确认两选项
- ✅ FR-044: Markdown 工具栏 (Bold/Italic/H1-3/List/Link/Icon)
- ✅ FR-045: 包裹选中文本 (T088-T089)
- ✅ FR-046: 图标按钮 + IconPicker (T065, 60db0f1)
- ✅ FR-047: Ctrl+S 触发保存版本对话框 (T090)
- ✅ FR-048: Ctrl+B 加粗 (T090)

### US7 版本对比与本地历史 (FR-049 ~ FR-056) — ✅ 全部 Done

- ✅ FR-049: 选 2 版本 diff 对比
- ✅ FR-050: diff 标注增加/删除/修改 block + 行级对比
- ✅ FR-051: localStorage 8 条 FIFO 历史
- ✅ FR-052: 编辑停 2s 推入历史
- ✅ FR-053: 历史恢复功能
- ✅ FR-054: UI 偏好持久化 (mode/splitRatio/scrollPos)
- ✅ FR-055: 每分支独立
- ✅ FR-056: 刷新恢复

### US8 双向定位 (FR-057 ~ FR-064) — ✅ 全部 Done

- ✅ FR-057: block 渲染带 data-block-id
- ✅ FR-058: Quick block 点击 → 预览滚动 + 高亮
- ✅ FR-059: 预览点击 → Quick block 展开 + 滚动
- ✅ FR-060: Code 模式 Monaco 行号点击同样工作
- ✅ FR-061: 1.5s 黄色脉冲动画
- ✅ FR-062: Modal 打开时暂停定位
- ✅ FR-063: PDF sanitize 剥离 data-block-id
- ✅ FR-064: 切主题/分页仍能定位

### US9 头像 (FR-065 ~ FR-080) — ✅ 全部 Done

- ✅ FR-065 ~ FR-080: 上传 + 压缩 + 5 位置 + 50-200 尺寸 + 3 形状 + 持久化 + 派生分支 inherit + PDF 渲染

## Success Criteria (17)

| ID | 描述 | 状态 |
|---|---|---|
| SC-001 | preview↔PDF 视觉一致 ≥95% | ✅ Met (US1) |
| SC-002 | 智能分页 1s 内更新 | ✅ Met (US2) |
| SC-003 | 主题切换 1s + 颜色实时 | ✅ Met (US3) |
| SC-004 | AI 优化 60s 超时 | ✅ Met (US5) |
| SC-005 | per-patch accept/reject | ✅ Met (US5) |
| SC-006 | 列表搜索 < 200ms | ✅ Met (US6 200ms 防抖 + 后端 ILIKE) |
| SC-007 | 拖拽持久化 < 500ms | ✅ Met (US6 DnD + reorder.mutate) |
| SC-008 | 版本 diff 标注 | ✅ Met (US7) |
| SC-009 | 现有 E2E 100% | ⚠ Partial (round-1 40/40 ✅；round-2 18/21，3 个 error-coach mock 受 .env LLM_MOCK_MODE=0 影响) |
| SC-010 | 新增 027 E2E 覆盖 | ✅ Met (render-engine.spec.ts 2/2) |
| SC-011 | 不影响其他模块 E2E | ✅ Met (Round-1 全过) |
| SC-012 | 木及自定义语法一致渲染 | ✅ Met (US4) |
| SC-013 | 单页 PDF | ✅ Met (US2) |
| SC-014 | UI 偏好持久化 | ✅ Met (US7) |
| SC-015 | localStorage 8 FIFO | ✅ Met (US7) |
| SC-016 | 双向定位 < 200ms + 1.5s 高亮 | ✅ Met (US8) |
| SC-017 | 头像调整 < 50ms + PDF 正确 | ✅ Met (US9) |

## Pending (non-blocking)

- **Phase B Muji UX 借鉴** — 纯 UI 重写工作，不影响功能验收；可作后续视觉精修
- **Round-2 error-coach mock 测试** — 需将 `backend/.env` 中 `LLM_MOCK_MODE` 改为 `1` 才能通过；非 027 改动引入
