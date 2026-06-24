# 027 综合方案评审摘要

**Feature**: 027-resume-center-muji-alignment
**日期**: 2026-06-24
**决策**: 激进重写 + Library-First 边界

---

## 一、与木及简历的差距分析

| 类别 | 木及 | eGGG 027 | 状态 |
|---|---|---|---|
| Markdown 写作 | ✅ | ✅ US1 | done |
| 智能分页 / A4 | ✅ | ✅ US2 | done |
| 主题 + color picker | ✅ | ✅ US3 | done |
| 远端存储 | ✅ | ✅ | done |
| **🎯 可视化定位 (内容↔视图)** | ✅ | ❌→**US8** | gap 已补 |
| **📎 证件照位置/大小调整** | ✅ | ❌→**US9** | gap 已补 |
| 模板广场 Square | ✅ | 🟡 theme+style 组合替代 | 概念不同 |
| 智能一页 (auto-shrink) | ✅ | 🟡 仅分页 | 接受差距 |
| 智能图标 / cheatsheet | ✅ | ❌→**US4 增强** | gap 已补 |
| Block 结构化 | ❌ | ✅ | eGGG 优势 |
| 版本快照 + COW | ❌ | ✅ | eGGG 优势 |
| AI 优化 | ❌ | ✅ M16 + US5 | eGGG 优势 |
| 多页 vs 单页模式 | ❌ | ✅ US2 | eGGG 优势 |
| 真后端渲染 | ❌ (云 HMAC) | ✅ Playwright | eGGG 优势 |

**结论**: 4 个 gap 已识别并入计划 (US8/US9/US4 增强/无 auto-shrink);4 个 eGGG 独有优势保留;1 个接受差距 (auto-shrink)。

---

## 二、9 用户故事 / 80 FR / 17 SC

| # | US | 优先级 | 主题 | 状态 |
|---|---|---|---|---|
| 1 | US1 统一渲染引擎 | P1 | preview↔PDF 用同一 HTML 生成器 | ✅ done (commit 83e0344) |
| 2 | US2 智能分页 | P1 | A4 真实分页 + 单/多页模式 | ✅ done |
| 3 | US3 主题系统 | P1 | 4 套木及主题 + --bg + color picker | ✅ done |
| 4 | US4 木及自定义语法 | P2 | 容器/图标/token/cheatsheet | ⏳ T059-T068 |
| 5 | US5 AI 优化增强 | P1 | pollState 真轮询 + per-patch + diff | ⏳ T069-T077 |
| 6 | US6 编辑器交互 | P2 | DnD + 搜索 + 工具栏 + 快捷键 | ⏳ T078-T092 |
| 7 | US7 版本对比 + 本地历史 | P2 | diff 视图 + localStorage 8 条 FIFO | ⏳ T093-T108 |
| 8 | **US8 内容↔预览双向定位** | P1 | Quick/Code 点击 ↔ 预览滚动+高亮 | ⏳ T121-T138 (新增) |
| 9 | **US9 头像/证件照调整** | P1 | 5 位置 + 50-200 尺寸 + 3 形状 | ⏳ T139-T160 (新增) |

**P1 任务**: US5 + US8 + US9 (3 个) — 优先实现以兑现"赶超木及"
**P2 任务**: US4 + US6 + US7 (3 个) — 锦上添花

---

## 三、激进重写范围 (per US, 用户已授权)

| US | 允许重写的组件 | 期望效果 |
|---|---|---|
| US4 | IconPicker / IconCheatsheet / MarkdownEditor 工具栏 | 木及风格图标快速插入 + 一键复制语法 |
| US5 | AiOptimizePanel (整重写) | 完整状态机 UI,真轮询,per-patch, diff 视图 |
| US6 | QuickEditor (整重写卡片化) + MarkdownEditor 工具栏 + ResumeListToolbar | DnD 拖拽 + 工具栏 + 列表 search/filter/sort |
| US7 | VersionDiffView (新) + 抽屉扩展 | 直观 diff + 一键回滚 |
| US8 | WysiwygEditor (整重写) + QuickEditor + MarkdownEditor (Monaco 行号) | 双向定位为核心交互 |
| US9 | AvatarDialog (新) + AvatarImage (新) + ResumePreview 集成 | 木及标志性身份证照定制 |

---

## 四、Library-First 边界 (强制保留)

1. **每个新库自包含** + README + 类型 + 测试夹具 (8 个库 + 头像后端服务)
2. **Test-First 强制** (宪章 NON-NEGOTIABLE, T001-T172 全含测试)
3. **TypeScript 严格** (无 `any` 逃逸)
4. **不污染全局状态** (Zustand / Tailwind / Vite / FastAPI / ARQ 全部不动)
5. **不改其他模块** (auth/jobs/interviews/errors/ability_profile/settings 全部不动)
6. **每个 US 独立 PR** (单 US 完成 → 测试 + 不回归 → 合入 master)
7. **数据契约稳定** (resume_branches 6 列合并迁移)
8. **木及"不搬运"清单** (HMAC 密钥 / OnePage clip / MobX / AntD 4 / CodeMirror / Webpack)

---

## 五、新增技术决策 (US8/US9 引入)

- **US8** 引入 `src/lib/resume-nav/` 库 (scroll + 1.5s 黄色高亮 + Monaco line→blockId 映射)
  - 理由: 双向定位是独立关注点,与渲染逻辑解耦才能测
  - 替代方案 (拒绝): 内联到 ResumePreview (不可测 + 耦合)
- **US8** 引入 `data-block-id` 渲染时属性
  - 理由: 需要 block UUID 在 DOM 上可识别以支持反向定位
  - 替代方案 (拒绝): 通过 block title 文本匹配 (相似 block 误识别)
  - PDF 渲染时通过 `sanitize.py` 剥离,不影响导出
- **US9** 引入后端 `avatar_service.py` (独立服务)
  - 理由: 头像上传 + Pillow 压缩 + 存盘 + inherit 父级是独立业务流程
  - 替代方案 (拒绝): 内联到 resumes/api.py (难维护)
- **US9** 引入本地 `static/uploads/avatars/` 存盘
  - 理由: 开发环境简单可靠, 无外部依赖
  - 替代方案 (拒绝): S3/OSS 对象存储 (v2 阶段引入)
- **US3+US9** 合并 Alembic 迁移 (6 列一次)
  - 理由: 减少 alembic upgrade 次数,部署更安全
  - 替代方案 (拒绝): 两次迁移 (多一次 restart)

---

## 六、风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 激进重写引入新 bug | 中 | 每 US 跑全量 e2e + 单元 + typecheck, 失败即回退到增量 |
| US8 data-block-id 残留 PDF | 低 | sanitize.py 显式剥离, 单元测试覆盖 |
| US9 头像上传攻击 | 中 | 前端 + 后端双重校验 (类型/大小), Pillow 重压缩破坏恶意载荷 |
| 6 列合并迁移失败 | 中 | 提供回滚 alembic downgrade, 单列 1 SQL 即可回滚 |
| 8 库之间耦合 | 低 | 每个库独立 README, 接口最小化, 无循环依赖 |

---

## 七、工作量估算

| US | 估算 | 备注 |
|---|---|---|
| US4 | 1-2 天 | plugin 已 done, 只需 UI 辅助 (IconPicker + Cheatsheet) |
| US5 | 2-3 天 | 独立模块, hook 重写 + panel 重写 + 后端 confirm 接受 path list |
| US6 | 3-4 天 | QuickEditor 卡片化 + DnD 集成 + 列表 search/filter/sort + 工具栏 |
| US7 | 2-3 天 | version-diff 新库 + 后端 diff endpoint + local-history + ui-pref |
| US8 | 2 天 | resume-nav 新库 + heading-block 加 data-block-id + Monaco gutter + sanitize |
| US9 | 3-4 天 | 后端 avatar_service + api_avatar + 前端 AvatarDialog + AvatarImage + ResumePreview 集成 |
| Phase 13 收尾 | 1-2 天 | 文档 + memory + typecheck + 全面回归 |
| **合计** | **14-21 天** | 含测试、回归、文档 |

P1 优先 (US5+US8+US9) = 7-9 天
P2 锦上添花 (US4+US6+US7) = 6-9 天

---

## 八、文件清单 (US4-US9 涉及, 估算)

### 前端新增/重写

- `src/lib/resume-nav/` (新) — scroll-highlight + block-line-map + index + README + 5 测试
- `src/styles/resume-bidir.css` (新) — 高亮动画
- `src/styles/resume-avatar.css` (新) — 头像位置
- `src/components/resume/editor/IconPicker.tsx` (新)
- `src/components/resume/editor/IconCheatsheet.tsx` (新) — 完整语法 cheatsheet
- `src/components/resume/editor/MarkdownToolbar.tsx` (新)
- `src/components/resume/editor/AvatarDialog.tsx` (新)
- `src/components/resume/editor/AvatarImage.tsx` (新)
- `src/components/resume/editor/VersionDiffView.tsx` (新)
- `src/components/resume/editor/WysiwygEditor.tsx` (重写) — US8 双向定位
- `src/components/resume/editor/QuickEditor.tsx` (重写) — US6 DnD + US8 双向定位
- `src/components/resume/editor/MarkdownEditor.tsx` (重写) — US6 工具栏 + US8 Monaco 行号
- `src/components/resume/editor/UnifiedToolbar.tsx` (重写) — 集成所有按钮
- `src/components/resume/AiOptimizePanel.tsx` (重写) — US5
- `src/components/resume/list/ResumeListToolbar.tsx` (新)
- `src/pages/ResumeList.tsx` (增强) — 接入 toolbar
- `src/pages/ResumeEditor.tsx` (增强) — 接入新功能
- `src/hooks/useResumeOptimize.ts` (重写) — US5 pollState
- `src/api/types.ts` (扩展) — avatar + data-block-id-aware
- `src/api/avatar.ts` (新) — upload/delete/inherit

### 后端新增/重写

- `backend/app/modules/resumes/models.py` (扩展) — +6 列
- `backend/app/modules/resumes/schemas.py` (扩展) — +avatar 字段
- `backend/app/modules/resumes/api.py` (扩展) — list search/filter/sort
- `backend/app/modules/resumes/api_avatar.py` (新) — upload/delete/inherit
- `backend/app/modules/resumes/avatar_service.py` (新) — Pillow 压缩 + 存盘
- `backend/app/modules/versions/service.py` (扩展) — diff_snapshot + diff_versions
- `backend/app/modules/versions/api.py` (扩展) — GET diff endpoint
- `backend/src/services/pdf_renderer/sanitize.py` (扩展) — 剥离 data-block-id
- `backend/migrations/versions/xxxx_add_theme_and_avatar.py` (新合并迁移)

### E2E 测试

- `tests/e2e/027-resume-muji/custom-syntax.spec.ts` (US4)
- `tests/e2e/027-resume-muji/ai-optimize.spec.ts` (US5)
- `tests/e2e/027-resume-muji/editor-ux.spec.ts` (US6)
- `tests/e2e/027-resume-muji/version-diff.spec.ts` (US7)
- `tests/e2e/027-resume-muji/bidirectional-nav.spec.ts` (US8 新)
- `tests/e2e/027-resume-muji/avatar.spec.ts` (US9 新)

合计 ~25 个新文件 + ~10 个重写/扩展文件

---

## 九、依赖变更

### 新增 (frontend)

- `@dnd-kit/core@6` + `@dnd-kit/sortable@8` + `fractional-indexing@3` (US6)
- `diff@5` (US5 patch diff + US7 version diff, 现有未确认是否已加)
- `react-color@2` (US3, 已加)

### 保留 (existing)

- `markdown-it@14` + 3 plugins (US1, 已加)
- `rs-md-html-parser@0.2` (US2, 已加)
- `react`, `zustand`, `@tanstack/react-query`, `tailwindcss`, `vite`, `@monaco-editor/react`

### 后端 (existing 即可)

- `Pillow` 已有 (用户头像模块 013 用过)
- `FastAPI`, `SQLAlchemy 2.0`, `Alembic`, `Playwright` 全部已有

---

## 十、验收标准 (汇总 SC-001 ~ SC-017)

- SC-001: preview↔PDF 视觉一致性 ≥ 95%
- SC-002: 分页在内容变化 1 秒内更新
- SC-003: 主题切换 ≤ 1s, 颜色实时跟随 < 50ms
- SC-004: AI 轮询 60s 超时, 不"永远转圈"
- SC-005: AI patch 逐项接受/拒绝
- SC-006: 列表搜索筛选 < 200ms
- SC-007: 拖拽持久化 < 500ms
- SC-008: 版本 diff 正确标注 add/remove/modify
- SC-009: 现有 E2E 100% 通过, 无回归
- SC-010: 027 新增 E2E 100% 通过
- SC-011: 其他模块 E2E 不受影响
- SC-012: 木及自定义语法一致渲染
- SC-013: 单/多页模式 PDF 与预览一致
- SC-014: UI 偏好持久化, 刷新恢复
- SC-015: localStorage 8 条 FIFO
- SC-016: 双向定位 < 200ms (US8)
- SC-017: 头像实时 < 50ms, PDF 一致 (US9)

---

## 十一、待用户确认事项

1. ✅ 计划结构: 9 US / 80 FR / 17 SC — 是否同意?
2. ✅ 激进重写策略 + Library-First 边界 — 是否同意 (已选)?
3. ✅ 实施顺序: P1 优先 (US5+US8+US9) — 是否同意?
4. ✅ 合并 Alembic 迁移 (6 列一次) — 是否同意?
5. ✅ 头像后端存本地 (v2 不上 S3) — 是否同意?
6. ❓ 接受 auto-shrink 差距 (木及有, 我们无) — 是否接受?
7. ❓ 模板广场 Square 概念 (用 theme+style 组合替代) — 是否接受?
8. ❓ 优先级 P1 vs P2 内部顺序 (US4 第一个 P2 因为 plugin 已就绪) — 是否同意?

---

## 十二、文件位置

- 主 spec: `specs/027-resume-center-muji-alignment/spec.md` (更新后 9 US)
- 主 plan: `specs/027-resume-center-muji-alignment/plan.md` (更新后 9 US + 激进重写策略)
- 主 tasks: `specs/027-resume-center-muji-alignment/tasks.md` (更新后 172 任务)
- 主 data-model: `specs/027-resume-center-muji-alignment/data-model.md` (更新后 +avatar)
- 本评审摘要: `specs/027-resume-center-muji-alignment/REVIEW-SUMMARY.md`
- Memory: `C:\Users\30803\.claude\projects\D--Project-eGGG\memory\v2_027_resume_muji.md`
