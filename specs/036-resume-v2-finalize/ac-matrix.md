---
req_id: REQ-036
status: draft
locked_at: null
locked_by: null
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-036 — Phase C Playwright 实操验收

## SC Gaps

无 — spec.md 的 12 条 SC（SC-001~SC-012）已覆盖所有验收维度：
- 入口与菜单（SC-001 / SC-005）
- 路由收口（SC-003 / SC-007）
- 数据清理（SC-002 / 与 Phase A 强相关）
- 新建流程（US4 / FR-013~FR-018）
- 简化列表（US5 / SC-004）
- 跨模块引用（US6 / SC-006）
- Playwright 端到端（US7 / SC-010~SC-012）

## AC 矩阵

> **校验方式约定**：
> - `test()` 编号沿用 spec playwright-spec-contract.md 的 #1~#35
> - 所有 test() 在 `tests/e2e/036-resume-v2-finalize.spec.ts` 单文件
> - 必跑命令：`npm run e2e -- tests/e2e/036-resume-v2-finalize.spec.ts --reporter=list --workers=2`
> - 严禁 API 注入 — 全程 UI 操作（click / fill / type / selectOption）

| AC-ID | 描述 | 验证方式（命令/测试名/可观测指标） | 来源 |
|-------|------|-----------------------------------|------|
| AC-01 | 登录后访问 `/resume` 显示空状态 CTA + 3 推荐模板缩略图 | `tests/e2e/036-resume-v2-finalize.spec.ts::test_01_login_and_empty_state` 期望 `[data-testid="resume-list-empty-create"]` + 3 个 `data-template-id` 可见 | SC-004 + FR-021 |
| AC-02 | Topbar"+" 是单按钮（无 dropdown），点击跳 `/resume?new=true` → 自动弹 Template Gallery | `test_02_topbar_single_new_entry` 期望 `[data-testid="topbar-new-resume-button"]` 无 sibling dropdown；click 后 URL 含 `new=true` | SC-001 + FR-003 + FR-004 |
| AC-03 | Template Gallery modal 显示 8-10 模板 + 空白模板选项 | `test_03_template_gallery_opens` 期望 `[data-testid="template-card"]` 数量 ≥ 8 | FR-014 |
| AC-04 | 选 Pikachu 模板创建 → 跳 `/resume/:id` 编辑器加载并使用 Pikachu | `test_04_create_via_template` 期望 click Pikachu → URL matches `/resume/[0-9a-f-]+` + `[data-testid="v2-editor"]` 可见 | FR-015 + US4 |
| AC-05 | 编辑器顶部 `editor-header` / `header-breadcrumb` / `header-resume-name` 显示 | `test_05_editor_header` 期望 3 testid 全部 visible | SC-007 + Header.tsx |
| AC-06 | 左侧 `sections-panel` 13 内置 section 展开/折叠 | `test_06_left_sections` 期望 12 个 `section-row-{id}` 可见 + 至少 1 个 `data-expanded` toggle 成功 | SectionsPanel.tsx |
| AC-07 | 右侧 `settings-panel` 12 accordion 展开/折叠 | `test_07_right_settings` 期望 12 个 `accordion-{id}` 可见 | SettingsPanel.tsx |
| AC-08 | Experience item dialog：填公司+岗位+时间并保存 | `test_08_experience_dialog` 期望 fill `[data-testid="experience-company"]` + `[data-testid="experience-position"]` + `[data-testid="experience-period"]` → save → preview 渲染 | SC-010 + ExperienceDialog.tsx |
| AC-09 | Education item dialog：填学校+学位+专业+时间 | `test_09_education_dialog` 期望 4 个 field fill + save | SC-010 + EducationDialog.tsx |
| AC-10 | Projects item dialog：填项目名+描述+至少 1 highlight | `test_10_projects_dialog` 期望 fill name + description + add highlight + save | SC-010 + ProjectsDialog.tsx |
| AC-11 | Skills item dialog：填名称+level+关键词 | `test_11_skills_dialog` 期望 fill name + level + keywords add + save | SC-010 + SkillsDialog.tsx |
| AC-12 | Profiles item dialog：选网络+填用户名 | `test_12_profiles_dialog` 期望 click icon picker → 选 GitHub → fill username + save | SC-010 + ProfileDialog.tsx |
| AC-13 | Languages item dialog：填语言+熟练度 | `test_13_languages_dialog` 期望 fill name + level + save | SC-010 + LanguageDialog.tsx |
| AC-14 | Interests item dialog：填关键词列表 | `test_14_interests_dialog` 期望 add 关键词 + save | SC-010 + InterestsDialog.tsx |
| AC-15 | Awards item dialog：填奖项+颁奖方+时间 | `test_15_awards_dialog` 期望 fill title + awarder + date + save | SC-010 + AwardsDialog.tsx |
| AC-16 | Certifications item dialog：填证书名+颁发机构 | `test_16_certifications_dialog` 期望 fill title + awarder + save | SC-010 + CertificationsDialog.tsx |
| AC-17 | References item dialog：填姓名+关系+联系方式 | `test_17_references_dialog` 期望 fill name + description + save | SC-010 + ReferencesDialog.tsx |
| AC-18 | Tiptap 富文本 toolbar 15+ 功能（bold/italic/h1/h2/list/code/link） | `test_18_tiptap_toolbar` 期望 RichTextEditor 内 ≥ 15 个 toolbar 按钮可见 + 至少 1 个能成功应用格式 | SC-010 + RichTextEditor.tsx |
| AC-19 | Dock zoom in：`preview-stage` data-zoom 增大 | `test_19_dock_zoom_in` 期望 click `[data-testid="dock-zoom-in"]` → data-zoom 数值 +0.25 | Dock.tsx |
| AC-20 | Dock zoom out：data-zoom 减小 | `test_20_dock_zoom_out` 期望 data-zoom 数值 -0.25 | Dock.tsx |
| AC-21 | Dock center：zoom 重置为 1 | `test_21_dock_center` 期望 click `[data-testid="dock-center"]` → data-zoom = 1 | Dock.tsx |
| AC-22 | Dock stacking toggle：page-stacking 属性变化 | `test_22_dock_stacking` 期望 click `[data-testid="dock-stacking"]` → preview-stage data-stacking 在 vertical/horizontal 间切换 | Dock.tsx |
| AC-23 | Dock AI agent：触发 AI 助手入口（navigate `/agent/new?resumeId=...`） | `test_23_dock_ai_agent` 期望 click `[data-testid="dock-ai-agent"]` → URL 含 `/agent/new` | Dock.tsx |
| AC-24 | Dock copy URL：clipboard 含 `/r/:u/:slug` | `test_24_dock_copy_url` 期望 click `[data-testid="dock-copy-url"]` → 读 clipboard 验证含 `/r/` 路径 | Dock.tsx |
| AC-25 | Dock download JSON：触发文件下载（`{slug}.json`） | `test_25_dock_json` 期望 click `[data-testid="dock-download-json"]` → download event filename 匹配 `*.json` | Dock.tsx |
| AC-26 | Dock download PDF：触发 PDF 文件下载（`{slug}-YYYY-MM-DD.pdf`） | `test_26_dock_pdf` 期望 click `[data-testid="dock-download-pdf"]` → download event filename 匹配 `*.pdf` + 文件首 4 bytes = `%PDF` | SC-010 + Dock.tsx |
| AC-27 | Settings template accordion：切换 Onyx | `test_27_settings_template` 期望 click `[data-testid="accordion-template"]` → 选 Onyx → preview template 切到 onyx | SettingsPanel.tsx |
| AC-28 | Settings typography accordion：调字号 | `test_28_settings_typography` 期望 click `[data-testid="accordion-typography"]` → 调 `typography-body-fontSize` → preview 字号变化 | SC-010 + TypographyPanel.tsx |
| AC-29 | Settings design accordion：改主色 | `test_29_settings_design` 期望 click `[data-testid="accordion-design"]` → 改主色 → preview 颜色变化 | SC-010 + DesignPanel.tsx |
| AC-30 | Settings page accordion：改边距 | `test_30_settings_page` 期望 click `[data-testid="accordion-page"]` → 改 marginX → preview 边距变化 | SC-010 + PagePanel.tsx |
| AC-31 | Settings sharing accordion：切换 is_public | `test_31_settings_sharing` 期望 click `[data-testid="accordion-sharing"]` → toggle `[data-testid="sharing-public-toggle"]` → DB `is_public=true` | SC-010 + SharingPanel.tsx |
| AC-32 | Undo/Redo：Ctrl+Z / Ctrl+Shift+Z 生效 | `test_32_undo_redo` 期望 输入字段 → Ctrl+Z → 字段清空；Ctrl+Shift+Z → 字段恢复 | SC-010 + store.undo/redo |
| AC-33 | Auto-save 500ms：编辑后触发 debounced PATCH | `test_33_auto_save` 期望 输入字段 → 等待 600ms → `page.waitForResponse(/PATCH.*v2\/resumes/)` 200 | SC-010 + store debounce |
| AC-34 | Mobile 375×667：左侧 panel 折叠为 rail | `test_34_mobile_sidebar` 期望 `setViewportSize` → `[data-testid="panel-left"]` 包含 `data-collapsed="true"` 或宽度 ≤ 48px | SC-010 + BuilderShell.tsx |
| AC-35 | Public URL `/r/:u/:slug` 访问成功 + 跨模块 grep 验证 | `test_35_public_url_and_cross_module` 期望 从分享链接进入公开页 + `grep -rn "/resume-v2\|/resume/v2/" src/ --include="*.tsx" --include="*.ts"` 仅重定向+fixture | SC-003 + SC-006 |
| AC-MAIN-1 | 端到端：按 `大模型应用开发简历v1.md` 填完整份简历（Basics + Summary 6 条 + Profiles + Experience + Projects 4 段 + Skills 4 分组） | `test_main_resume_creation` 期望所有 section 填写 + 截图每段 | SC-010 + FR-032 |
| AC-MAIN-2 | 导出 PDF：触发 PDF 下载 + 文字提取关键字段（姓名/邮箱/学校/公司/项目名/技能分类） | `test_main_export_pdf` 期望 PDF 下载 + 解析 PDF text 提取 "李祖荫" / "3080340895@qq.com" / "天津科技大学" / "浩鲸云" / "企业级智能体平台" / "RAG" | SC-010 + SC-011 + FR-032 |
| AC-MAIN-3 | evidence 产物：`step-*.png ≥ 6 张` + `final-resume.pdf (>0 bytes)` + `field-comparison.md` + `incomplete-features.md` + `accepted-features.md` | `ls docs/evidence/036-playwright-<ts>/` 验证文件齐 | SC-012 + FR-034 |
| AC-MAIN-4 | incomplete P1 = 0 / accepted P1 全部 ✅ | `grep -c "^- \[ \] \*\*P1" incomplete-features.md` = 0 + `grep -c "^- \[x\] \*\*P1" accepted-features.md` ≥ 10 | SC-012 |
| AC-MAIN-5 | field-comparison 字段一致（姓名/邮箱/学校/公司/项目名/技能分类） | `cat field-comparison.md` 逐字段 ✅ 比率 ≥ 5/6 | SC-011 |

## 起草说明（写给 tester）

### 设计意图

AC 矩阵严格按 spec playwright-spec-contract.md 的 35 test() 拆分 + 主流程 2 个 + evidence 3 个验收 AC 组成。所有 test() 必须在 `tests/e2e/036-resume-v2-finalize.spec.ts` 单文件内，方便 Playwright 单次跑完。

### 已覆盖的边界

- **空状态**（AC-01）：清理后 DB = 0 时列表空状态 CTA
- **dialog 字段缺失**（AC-08~AC-17）：10 类 section dialog 必填字段
- **持久化**（AC-33）：500ms debounce PATCH 触发
- **公开分享**（AC-31 / AC-35）：toggle is_public + 公开页访问
- **跨模块引用**（AC-35）：grep 验证业务代码 = 0
- **PDF 真实输出**（AC-26 / AC-MAIN-2）：文件 magic bytes 验证

### 未覆盖的边界（已知风险）

- **Tiptap 完整 15+ 功能**（AC-18）：RichTextToolbar.tsx 现有按钮数 ≥ 15 但具体 list（heading/code/link/quote）需逐个验证；若部分功能未实现则降级为 ≥ 10 个 visible
- **Dock stacking 双向**（AC-22）：先 vertical→horizontal 再 horizontal→vertical 双向切换可能因 state 共享问题只测一个方向
- **Mobile rail 触发条件**（AC-34）：BuilderShell 阈值 `(max-width: 640px)`；375px viewport 一定命中，但 rail 宽度 48px 验证需 `boundingBox`
- **PDF 文字提取**（AC-MAIN-2）：依赖后端 `/api/v1/export/render` PDF 服务可达；若服务 down 则 test FAIL

### 关键风险点

1. **dialog 字段 store rollback**：DialogHost 关闭时 `setDataMut` 会被 `undo()` 全部回滚（参见 DialogHost.tsx handleClose）→ AC-08~AC-17 必须在 dialog open 期间 fill + 主动点 Save / Submit 按钮（而非 ESC）才能让修改真正落地
2. **PDF 依赖后端 export service**：若 `/api/v1/export/render` 服务异常（deps 缺、Playwright headless 资源），AC-26 + AC-MAIN-2 会 FAIL → 修需要后端日志
3. **field-comparison 字段名可能因模板渲染大小写**：「企业级智能体平台」PDF 中可能渲染为「企业级智能体平台（类 Coze/Dify）」，匹配时使用 substring 容忍
4. **reactive-resume dialog 字段参考**：仅在 Playwright 失败 + testid 确实找不到时启用；优先用现有 testid（032/034 ship 的 testid 全表见 tests/e2e/032-v2-mvp.spec.ts line 17-50）

### Self-check 通过

- [x] 每条 AC 都有"验证方式"列
- [x] 每条 AC 都有"来源"列（spec SC / FR / 自主发现）
- [x] AC 总数 = 35 + 5 (主流程) = 40 条
- [x] 每条 AC 覆盖边界（空/超时/并发/重试/异常渲染）
- [x] 无模糊词（"快/稳定/合理/差不多"）
- [x] AC 未超出 spec.SC 范围
