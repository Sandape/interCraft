# 简历中心模块 (`src/modules/resume/`)

> **目的**: 单一模块边界,封装简历中心所有功能(渲染/分页/主题/编辑器/列表/导出/AI/头像/双向定位/版本对比/本地历史)。
> **目标**: 与全局基础设施(Zustand/TanStack Query/Tailwind/Vite/React Router/FastAPI/ARQ)解耦,改动局限在模块内,不影响其他业务模块。

## 模块结构 (Phase A 完成后)

```
src/modules/resume/
├── index.ts                  # 公开 API (re-export)
├── README.md                 # 本文件
│
├── renderer/                 # 【从 src/lib/resume-renderer/】统一渲染引擎
│                             #   markdown-it + 3 木及插件 + svgMap 14 图标 + CLI
│                             #   US1, US2, US4
├── pagination/               # 【从 src/lib/resume-pagination/】智能分页
│                             #   rs-md-html-parser + window-scale A4 自适应
│                             #   US2
├── themes/                   # 【从 src/lib/resume-themes/】主题系统
│                             #   4 套木及主题 CSS + --bg 变量 + react-color
│                             #   US3
├── styles/                   # 【从 src/lib/resume-styles/ + src/styles/resume-*.css】
│                             #   布局样式元数据 (classic/compact/modern/editorial)
│                             #   + 4 个 CSS 文件
│
├── version-diff/             # 【从 src/lib/version-diff/】版本对比
│                             #   block 级 diff 算法
│                             #   US7
├── local-history/            # 【从 src/lib/local-history/】本地历史
│                             #   localStorage 8 条 FIFO
│                             #   US7
├── ui-pref/                  # 【从 src/lib/resume-ui-pref/】UI 偏好
│                             #   mode + splitRatio + scrollPos 持久化
│                             #   US7
│
├── editor/                   # 【从 src/components/resume/editor/】编辑器组件
│                             #   10 组件: ColorPicker/EditorSidebar/MarkdownEditor
│                             #   PageIndicator/QuickEditor/ResumePreview
│                             #   StyleSelector/ThemeSelector/UnifiedToolbar
│                             #   WysiwygEditor + useModeToggle hook
├── list/                     # 【从 src/components/resume/list/】列表组件
│                             #   PrimaryResumeCard
├── export/                   # 【从 src/components/resume/export/】导出组件
│                             #   ExportMenu
├── import/                   # 【从 src/components/resume/import/】导入组件
│                             #   ImportModal
│
├── avatar/                   # 【新建, US9】头像/证件照
│                             #   AvatarDialog + AvatarImage + 上传/压缩
├── nav/                      # 【新建, US8】内容↔预览双向定位
│                             #   resume-nav 库 (scroll + 高亮 + line map)
│
├── api/                      # 【从 src/api/avatar.ts + 部分 types.ts】
│                             #   头像 API + ResumeBranch 类型
├── hooks/                    # 【从 src/hooks/useResumeOptimize.ts】
│                             #   useResumeOptimize (重写为 pollState)
├── stores/                   # 【从 src/stores/useResumeUIStore.ts】
│                             #   useResumeUIStore
└── styles/                   # 【从 src/styles/resume-*.css】
                              #   4 个布局 CSS 文件
```

## 公开 API (目标)

```typescript
// @/modules/resume
// Renderer
export { renderMarkdown, type RenderOptions } from './renderer';
// Pagination
export { paginate, usePageIndicator, useWindowScale } from './pagination';
// Themes
export { loadTheme, applyColor, listThemes } from './themes';
export type { ResumeTheme } from './themes';
// Styles
export { getStyleMeta, listStyles } from './styles';
export type { ResumeStyleMeta } from './styles';
// Components
export { ResumeEditor, ResumePreview, QuickEditor, MarkdownEditor, WysiwygEditor } from './editor';
export { UnifiedToolbar, ThemeSelector, ColorPicker, PageIndicator } from './editor';
export { PrimaryResumeCard, ResumeListToolbar } from './list';
export { ExportMenu } from './export';
export { ImportModal } from './import';
export { AiOptimizePanel } from './editor';  // 计划放 editor 子目录
// US7
export { diffVersions, restoreVersion } from './version-diff';
export type { DiffResult, BlockDiff } from './version-diff';
export { saveLocalHistory, loadLocalHistory, clearLocalHistory } from './local-history';
export { loadUIPref, saveUIPref } from './ui-pref';
// US8
export { scrollToBlock, highlightBlock, getBlockLineMap } from './nav';
// US9
export { uploadAvatar, deleteAvatar, inheritAvatar } from './api';
export { AvatarDialog, AvatarImage } from './avatar';
// Hooks
export { useResumeOptimize } from './hooks';
// Stores
export { useResumeUIStore } from './stores';
// Types
export type { ResumeBranch, AIOptimizePatch, AvatarSettings } from './api';
```

## 约束 (宪章 + Library-First)

1. **Test-First**: 每个库/组件有 `__tests__/` 目录,测试先于实现
2. **TypeScript 严格**: 无 `any` 逃逸
3. **不污染全局**: 不修改 Zustand 全局 store、不引入全局 CSS 变量
4. **不改其他模块**: auth/jobs/interviews/errors/ability_profile/settings 全部不动
5. **数据契约稳定**: `resume_branches` 6 列 (theme 2 + avatar 4) 一次合并迁移
6. **木及"不搬运"清单**: 硬编码 HMAC 密钥 / OnePage clip / MobX / AntD 4 / CodeMirror / Webpack 全部不搬

## 改造历史

- **2026-06-24 Phase A1**: 创建目录骨架 (此文件)
- **A2-A5 (进行中)**: 7 lib + 12 组件 + hooks + store + CSS 全部 git mv
- **A6 (计划)**: 更新 12 个 import site
- **A7 (计划)**: typecheck + 单元 + E2E 验证不回归
- **A8 (计划)**: 删除 `src/lib/resume-*` + `src/components/resume/` 旧位置

参见 `specs/027-resume-center-muji-alignment/REVIEW-SUMMARY.md` 与
`specs/027-resume-center-muji-alignment/plan.md` Phase 2 节。
