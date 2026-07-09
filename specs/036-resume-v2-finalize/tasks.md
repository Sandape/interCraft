---
description: "Task list for 036 Resume v2 Finalize — 全面弃用 v1 + 脏数据清理 + Playwright 成品验收"
---

# Tasks: 036 Resume v2 Finalize

**Input**: Design documents from `specs/036-resume-v2-finalize/`
- spec.md (7 US + 35 FR + 12 SC)
- plan.md (Phase A/B/C + 三阶段实施)
- research.md (7 决策)
- data-model.md (4 张表 + cleanup script + alembic)
- contracts/ (cleanup-script / playwright-spec / route-redirect)
- quickstart.md (端到端运行手册)

**Prerequisites**: 032 v2 MVP (ship) + 034 reactive-resume parity (ship)
**Reference**: `D:\Project\reactive-resume\apps\artboard\src\dialogs\resume\sections\` (实施时问题修复参考)
**Resume sample**: `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`

**Organization**: 任务按 US 拆分（US1→US7 优先级排序）；上层结构沿用 plan.md 的 Phase A（清理+下线）/ Phase B（端到端）/ Phase C（Playwright 验收）。
**Tests**: 必含 — Constitution III 强制；Phase C 验收脚本本身就是 35 个 Playwright `test()`。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件，无依赖）
- **[Story]**: 任务归属 US（[US1]~[US7]）
- **[Phase]**: A=清理+下线 / B=端到端 / C=Playwright 验收
- 含具体文件路径

---

## Phase 1: Setup（共享基础设施）

**目的**: 准备 036 所需目录、脚本骨架、evidence 目录约定。

- [x] T001 [P] 创建 evidence 目录占位 `docs/evidence/036-data-cleanup-README.md`（说明后续 cleanup + Playwright 产物落点）
- [x] T002 [P] 创建 `backend/app/scripts/__init__.py`（若不存在）让 `python -m app.scripts.cleanup_resume_data` 可运行
- [x] T003 [P] 创建 `backend/tests/scripts/__init__.py`（若不存在）让 cleanup 脚本单测可运行
- [x] T004 [P] 创建 `backend/tests/scripts/test_cleanup_resume_data.py` 骨架（dry-run + 行数断言 占位测试）
- [ ] T005 [P] 创建 `tests/e2e/036-resume-v2-finalize.spec.ts` 骨架（35 个 `test()` 占位）

---

## Phase 2: Foundational（阻塞前置）

**目的**: 清理脚本 + alembic 迁移就位；DB 备份链路可用；mcp__postgres__query 验收工具就绪。

**⚠️ CRITICAL**: US3 实施前必须完成本阶段。

- [x] T006 [Phase A] [P] 实现 `backend/app/scripts/cleanup_resume_data.py` CLI 骨架（`--dry-run` / `--execute` / `--backup` / `--verify` / `--json` / `--output-dir` 参数解析 + 退出码 0/1/2/3）
- [x] T007 [Phase A] [P] 实现 cleanup 脚本 `count_rows_before()` 函数（查 4 张表 + outbox 行数，返回 dict）
- [x] T008 [Phase A] [P] 实现 cleanup 脚本 `dump_backup()` 函数（`pg_dump --data-only` 输出到 `docs/evidence/036-data-cleanup-<ts>/db-backup.sql`）
- [x] T009 [Phase A] 实现 cleanup 脚本 `execute_cleanup()` 函数（事务包裹 + TRUNCATE CASCADE + outbox DELETE，per data-model.md 清理方式）
- [x] T010 [Phase A] [P] 实现 cleanup 脚本 `safety_check()` 函数（检测 `APP_ENV` / DB name；非 dev/test 退出码 3）
- [x] T011 [Phase A] 实现 cleanup 脚本 `verify_after()` 函数（清理后查行数 = 0 断言）
- [x] T012 [Phase A] [P] 写 alembic 迁移 `backend/alembic/versions/0026_036_cleanup_resume_data.py`（幂等；downgrade 抛 NotImplementedError；环境检测；per data-model.md 迁移代码）
- [x] T013 [Phase A] 写 cleanup 单测 — dry-run 模式不修改 DB：`backend/tests/scripts/test_cleanup_resume_data.py::test_dry_run_no_side_effects`
- [x] T014 [Phase A] 写 cleanup 单测 — execute 模式清空 4 张表：`backend/tests/scripts/test_cleanup_resume_data.py::test_execute_truncates_all_tables`
- [x] T015 [Phase A] 写 cleanup 单测 — execute 在 prod 环境退出码 3：`backend/tests/scripts/test_cleanup_resume_data.py::test_prod_env_blocked`

**Checkpoint**: 基础设施就绪 — US3 可开始

---

## Phase 3: User Story 3 — 数据清理 v1+v2 整表清空（Priority: P1）🎯

**Goal**: 跑 cleanup 脚本，4 张关键表行数 = 0；outbox 悬挂行清空；evidence 产物落盘。
**Independent Test**: `mcp__postgres__query` 实查 4 张表行数 = 0；evidence 目录含 `db-backup.sql` + `cleanup.log` + `summary.json`。

### Implementation for User Story 3

- [x] T016 [US3] [Phase A] 跑 cleanup 脚本 dry-run 模式：`cd backend && uv run python -m app.scripts.cleanup_resume_data --dry-run --json`（输出 before 行数）
- [x] T017 [US3] [Phase A] 用 `mcp__postgres__query` 实查落库（per `feedback_postgres_mcp_validation`）：SELECT COUNT(*) FROM resume_branches/resumes_v2/resume_statistics_v2/resume_analysis_v2
- [x] T018 [US3] [Phase A] 跑 cleanup 脚本 backup + execute：`uv run python -m app.scripts.cleanup_resume_data --backup --execute --yes`
- [x] T019 [US3] [Phase A] 再次用 `mcp__postgres__query` 实查 4 张表行数（期望全部 = 0）+ outbox 残留（期望 = 0）
- [x] T020 [US3] [Phase A] 验证 evidence 目录产物：`docs/evidence/036-data-cleanup-<ts>/{db-backup.sql, cleanup.log, summary.json}` 都存在且非空
- [x] T021 [US3] [Phase A] 跑 alembic 迁移确认幂等：`cd backend && uv run alembic upgrade head`（重复 2 次应均成功）

**Checkpoint**: US3 完成 — DB 处于干净起点；US2/US1/US4/US5 可继续

---

## Phase 4: User Story 2 — 路由收口重定向（Priority: P1）

**Goal**: `/resume-v2*` 与 `/resume/v2/*` 老路径全部 Navigate replace 到规范路径；`/resume/:branchId` v1 路由完全删除；`ResumeListV2` / `ResumeV2New` / `ResumeEditor` 全部下线。
**Independent Test**: Playwright 访问 3 种老 URL → 跳规范路径；`App.tsx` grep 无 `ResumeListV2` / `ResumeV2New`。

### Tests for User Story 2

- [ ] T022 [P] [US2] [Phase A] 写路由重定向单测 `tests/unit/route-redirects.test.tsx`（3 个 case：/resume-v2 → /resume / /resume-v2/new → /resume?new=true / /resume/v2/:id → /resume/:id）

### Implementation for User Story 2

- [ ] T023 [US2] [Phase A] 编辑 `src/App.tsx`：删除 `ResumeListV2` / `ResumeV2New` 的 `lazy import` 与路由条目
- [ ] T024 [US2] [Phase A] 编辑 `src/App.tsx`：删除 `path="/resume-v2"`、`path="/resume-v2/new"`、`path="/resume/v2/:id"` 路由条目
- [ ] T025 [US2] [Phase A] 编辑 `src/App.tsx`：添加 3 条 `Route` 元素用 `<Navigate to={...} replace />` 实现重定向（per route-redirect-contract.md）
- [ ] T026 [US2] [Phase A] 编辑 `src/App.tsx`：删除 `path="/resume/:branchId"` 路由条目（v1 已弃用，不再挂 v1 editor 路由）
- [ ] T027 [US2] [Phase A] 编辑 `src/App.tsx`：把 v2 编辑器挂到 `path="/resume/:id"`（`element={<ResumeEditorV2 />}`）
- [ ] T028 [P] [US2] [Phase A] 删除 `src/pages/ResumeListV2.tsx`（先 grep import 引用，确保无引用后再删）
- [ ] T029 [P] [US2] [Phase A] 删除 `src/pages/ResumeV2New.tsx`（先 grep import 引用）
- [ ] T030 [P] [US2] [Phase A] 删除 `src/pages/ResumeEditor.tsx`（v1 编辑器入口，先 grep import 引用）
- [ ] T031 [US2] [Phase A] 编辑后端 `backend/app/modules/resumes/`：移除 v1 API endpoints（保留 `resume_branches` 表 schema）
- [ ] T032 [US2] [Phase A] 跑路由重定向单测 + 后端 pytest 100% 通过
- [ ] T033 [US2] [Phase A] 全仓 grep 验证：`grep -rn "/resume-v2\|/resume/v2/" src/ --include="*.tsx" --include="*.ts"` 仅重定向规则与测试 fixture 命中

**Checkpoint**: US2 完成 — 路由表收口；v1 触点全部下线；US1 可继续

---

## Phase 5: User Story 1 — 侧边栏只有 1 个"简历中心"入口（Priority: P1）🎯

**Goal**: 侧边栏主导航只 1 个简历菜单项；Topbar "+" 下拉只 1 项"新建简历"；用户可见中文文案中无 "v2 简历"。
**Independent Test**: 启动 dev server → 登录 → 截图侧边栏；断言只有 1 个简历相关菜单项；DOM grep "v2 简历" = 0 命中。

### Tests for User Story 1

- [ ] T034 [P] [US1] [Phase B] 写菜单结构单测 `tests/unit/sidebar-resume-entry.test.tsx`（断言 `primaryNav` 中简历相关项 = 1）

### Implementation for User Story 1

- [ ] T035 [US1] [Phase B] 编辑 `src/components/layout/Sidebar.tsx`：删除"v2 简历"菜单项（保留 `简历中心` + FileText 图标 + `/resume` 路由）
- [ ] T036 [US1] [Phase B] 编辑 `src/components/layout/Topbar.tsx`：删除"+" 下拉中"空白创建" + "新建 v2 简历"两个独立项；合并为单"新建简历"
- [ ] T037 [US1] [Phase B] 编辑 `src/components/layout/Sidebar.tsx`：移除 `Sparkles` 图标 import（若仅服务已移除菜单项）
- [ ] T038 [US1] [Phase B] 编辑 `src/components/layout/Topbar.tsx`：单"新建简历"点击 → 触发 Template Gallery modal（详见 US4）
- [ ] T039 [US1] [Phase B] 跑菜单结构单测 + 前端 `npm run typecheck` + `npm run test` 全绿
- [ ] T040 [US1] [Phase B] 启动 dev server → 登录 → 截图侧边栏（人工验证 OR 写 Playwright 截图存 evidence `docs/evidence/036-ui-sidebar.png`）

**Checkpoint**: US1 完成 — 单一入口可见；US5/US4 可继续

---

## Phase 6: User Story 5 — 简化列表页（Priority: P1）

**Goal**: `/resume` 只显示 v2 简历（清理后空状态）；无"历史简历"折叠组；空状态显示 CTA + 2-3 个推荐模板缩略图。
**Independent Test**: 登录 → 访问 `/resume` → 主区显示空状态 + CTA（清理后）→ 点 CTA 触发 US4 流程。

### Tests for User Story 5

- [x] T041 [P] [US5] [Phase B] 写列表页单测 `tests/unit/resume-list-empty-state.test.tsx`（空状态 CTA 渲染 + 2-3 个推荐模板缩略图）

### Implementation for User Story 5

- [x] T042 [US5] [Phase B] 编辑 `src/pages/ResumeList.tsx`：删除 v1 混用逻辑（v1 historical folder / v1 branch card）
- [x] T043 [US5] [Phase B] 编辑 `src/pages/ResumeList.tsx`：主区仅渲染 v2 简历（更新时间倒序）
- [x] T044 [US5] [Phase B] 编辑 `src/pages/ResumeList.tsx`：空状态显示 CTA"创建你的第一份简历" + 2-3 个推荐模板缩略图（per FR-021）
- [x] T045 [US5] [Phase B] 编辑 `src/pages/ResumeList.tsx`：搜索框仅匹配 v2 简历（v1 已被清空，无需 fallback）
- [x] T046 [US5] [Phase B] 编辑 `src/pages/ResumeList.tsx`：卡片点击 → 跳 `/resume/:id`（per FR-019）
- [x] T047 [US5] [Phase B] 跑列表页单测 + 前端 typecheck + vitest 全绿

**Checkpoint**: US5 完成 — 列表页简化；US4 可继续

---

## Phase 7: User Story 4 — 新建流程走模板选择（Priority: P2）

**Goal**: Topbar "+" → "新建简历" 弹出 Template Gallery modal（复用 032 Gallery）；用户选模板后 POST `/api/v1/v2/resumes` 创建并跳 `/resume/:newId`。
**Independent Test**: 点 Topbar "+" → 选 Pikachu → 编辑器加载并使用 Pikachu；返回重选 Onyx → 编辑器切换。

### Tests for User Story 4

- [ ] T048 [P] [US4] [Phase B] 写新建流程单测 `tests/unit/topbar-new-resume-flow.test.tsx`（点 "+" 触发 modal；选模板后跳转；取消不创建）

### Implementation for User Story 4

- [x] T049 [P] [US4] [Phase B] 复用 032 Template Gallery 组件（`src/modules/resume/v2/components/TemplateGallery.tsx`）— 确认存在并可用
- [x] T050 [US4] [Phase B] 编辑 `src/components/layout/Topbar.tsx`：单"新建简历" → 触发 Template Gallery modal
- [x] T051 [US4] [Phase B] 编辑 Template Gallery：选模板确认 → POST `/api/v1/v2/resumes`（body `{ template, source: "template-picker" }`）
- [x] T052 [US4] [Phase B] 编辑 Template Gallery：创建成功 → 跳 `/resume/:newId`
- [x] T053 [US4] [Phase B] 编辑 Template Gallery：创建失败 → toast 错误 + 停留 modal（per FR-016）
- [x] T054 [US4] [Phase B] 编辑 Template Gallery：取消 modal → 不创建任何简历（per FR-017）
- [x] T055 [US4] [Phase B] 编辑 Template Gallery：含"空白模板" + 8-10 套精选模板（per FR-014）
- [x] T056 [US4] [Phase B] 跑新建流程单测 + 前端 typecheck + vitest 全绿

**Checkpoint**: US4 完成 — 新建流程连贯；US6 可继续

---

## Phase 8: User Story 6 — 体验补强 + 跨模块引用收口（Priority: P2）

**Goal**: 跨模块引用全部走 `/resume` 规范路径；tab title / 文案无 "v2"；browser tab title 仅显示简历名。
**Independent Test**: 全仓 grep `/resume-v2` / `/resume/v2/` / "v2" 业务代码命中数 = 0（仅重定向规则与测试 fixture 可保留）。

### Implementation for User Story 6

- [x] T057 [US6] [Phase B] 全仓 grep：`grep -rn "/resume-v2\|/resume/v2/" src/ --include="*.tsx" --include="*.ts"` 列出全部业务引用
- [x] T058 [US6] [Phase B] 修复 `src/modules/interview/`（模拟面试）："我的简历"链接 → 规范路径
- [x] T059 [US6] [Phase B] 修复 `src/modules/ability/`（能力画像）："我的简历"链接 → 规范路径
- [x] T060 [US6] [Phase B] 修复 `src/modules/jobs/`（求职追踪）："我的简历"链接 → 规范路径
- [x] T061 [US6] [Phase B] 修复 `src/modules/settings/`（Settings）：简历相关链接 → 规范路径
- [x] T062 [US6] [Phase B] 编辑 `src/pages/ResumeEditorV2.tsx`：browser tab title 仅为简历名（如"李祖荫的简历"），不含 "v2"
- [x] T063 [US6] [Phase B] 编辑 `src/pages/ResumeList.tsx`：page title 不含 "v2"
- [x] T064 [US6] [Phase B] 全仓 grep 业务代码 "v2" 关键字：菜单 / 按钮 / modal title / toast / 空状态文案（除 data-testid 与 console 调试日志）命中数 = 0
- [x] T065 [US6] [Phase B] 跑前端 typecheck + vitest 全绿

**Checkpoint**: US6 完成 — 跨模块引用收口；US7 可开始

---

## Phase 9: User Story 7 — Playwright 实操验收 + 两份清单（Priority: P1）🎯 关键验收关卡

**Goal**: 用 Playwright UI 实操（禁止 API 注入）在 v2 编辑器制作一份成品简历（参照 `大模型应用开发简历v1.md`）；≥ 35 个 `test()` 覆盖每个细分功能点；产出 `incomplete-features.md` + `accepted-features.md` 两份清单。
**Independent Test**: 跑 `tests/e2e/036-resume-v2-finalize.spec.ts` → 35/35 通过 → evidence 目录含 ≥ 6 张截图 + final PDF + 字段对比 + 两份清单。

### Tests for User Story 7（35 个 test() 拆解 per playwright-spec-contract.md）

#### 入口 + 新建流程（test 1-4）

- [ ] T066 [P] [US7] [Phase C] test #1: login + access /resume + empty state — `tests/e2e/036-resume-v2-finalize.spec.ts::test_01_login_and_empty_state`
- [ ] T067 [P] [US7] [Phase C] test #2: topbar + dropdown shows single "新建简历" — `tests/e2e/036-resume-v2-finalize.spec.ts::test_02_topbar_single_new_entry`
- [ ] T068 [P] [US7] [Phase C] test #3: template gallery modal opens — `tests/e2e/036-resume-v2-finalize.spec.ts::test_03_template_gallery_opens`
- [ ] T069 [P] [US7] [Phase C] test #4: select template + create + navigate to /resume/:id — `tests/e2e/036-resume-v2-finalize.spec.ts::test_04_create_via_template`

#### 编辑器顶部 + 左侧 Section 列表（test 5-7）

- [ ] T070 [P] [US7] [Phase C] test #5: editor header / breadcrumb / sidebar toggle — `tests/e2e/036-resume-v2-finalize.spec.ts::test_05_editor_header`
- [ ] T071 [P] [US7] [Phase C] test #6: left section list 13 built-in sections expand/collapse — `tests/e2e/036-resume-v2-finalize.spec.ts::test_06_left_sections`
- [ ] T072 [P] [US7] [Phase C] test #7: right settings 12 sub-panels expand/collapse — `tests/e2e/036-resume-v2-finalize.spec.ts::test_07_right_settings`

#### Section item dialog（10 类 test 8-17）

- [ ] T073 [P] [US7] [Phase C] test #8: experience item dialog create/edit/delete — `tests/e2e/036-resume-v2-finalize.spec.ts::test_08_experience_dialog`
- [ ] T074 [P] [US7] [Phase C] test #9: education item dialog — `tests/e2e/036-resume-v2-finalize.spec.ts::test_09_education_dialog`
- [ ] T075 [P] [US7] [Phase C] test #10: projects item dialog — `tests/e2e/036-resume-v2-finalize.spec.ts::test_10_projects_dialog`
- [ ] T076 [P] [US7] [Phase C] test #11: skills item dialog (with level) — `tests/e2e/036-resume-v2-finalize.spec.ts::test_11_skills_dialog`
- [ ] T077 [P] [US7] [Phase C] test #12: profiles item dialog (network picker) — `tests/e2e/036-resume-v2-finalize.spec.ts::test_12_profiles_dialog`
- [ ] T078 [P] [US7] [Phase C] test #13: languages item dialog — `tests/e2e/036-resume-v2-finalize.spec.ts::test_13_languages_dialog`
- [ ] T079 [P] [US7] [Phase C] test #14: interests item dialog — `tests/e2e/036-resume-v2-finalize.spec.ts::test_14_interests_dialog`
- [ ] T080 [P] [US7] [Phase C] test #15: awards item dialog — `tests/e2e/036-resume-v2-finalize.spec.ts::test_15_awards_dialog`
- [ ] T081 [P] [US7] [Phase C] test #16: certifications item dialog — `tests/e2e/036-resume-v2-finalize.spec.ts::test_16_certifications_dialog`
- [ ] T082 [P] [US7] [Phase C] test #17: references item dialog — `tests/e2e/036-resume-v2-finalize.spec.ts::test_17_references_dialog`

#### Tiptap 富文本 + Dock 按钮（test 18-25）

- [ ] T083 [P] [US7] [Phase C] test #18: Tiptap rich text toolbar 15+ features — `tests/e2e/036-resume-v2-finalize.spec.ts::test_18_tiptap_toolbar`
- [ ] T084 [P] [US7] [Phase C] test #19: dock button zoom in — `tests/e2e/036-resume-v2-finalize.spec.ts::test_19_dock_zoom_in`
- [ ] T085 [P] [US7] [Phase C] test #20: dock button zoom out — `tests/e2e/036-resume-v2-finalize.spec.ts::test_20_dock_zoom_out`
- [ ] T086 [P] [US7] [Phase C] test #21: dock button center view — `tests/e2e/036-resume-v2-finalize.spec.ts::test_21_dock_center`
- [ ] T087 [P] [US7] [Phase C] test #22: dock button toggle page stacking — `tests/e2e/036-resume-v2-finalize.spec.ts::test_22_dock_stacking`
- [ ] T088 [P] [US7] [Phase C] test #23: dock button open AI agent — `tests/e2e/036-resume-v2-finalize.spec.ts::test_23_dock_ai_agent`
- [ ] T089 [P] [US7] [Phase C] test #24: dock button copy URL — `tests/e2e/036-resume-v2-finalize.spec.ts::test_24_dock_copy_url`
- [ ] T090 [P] [US7] [Phase C] test #25: dock button download JSON — `tests/e2e/036-resume-v2-finalize.spec.ts::test_25_dock_json`

#### Settings 面板（test 26-30）

- [ ] T091 [P] [US7] [Phase C] test #26: dock button download PDF — `tests/e2e/036-resume-v2-finalize.spec.ts::test_26_dock_pdf`
- [ ] T092 [P] [US7] [Phase C] test #27: settings panel template gallery switch — `tests/e2e/036-resume-v2-finalize.spec.ts::test_27_settings_template`
- [ ] T093 [P] [US7] [Phase C] test #28: settings panel typography (body/heading) — `tests/e2e/036-resume-v2-finalize.spec.ts::test_28_settings_typography`
- [ ] T094 [P] [US7] [Phase C] test #29: settings panel design (colors + level) — `tests/e2e/036-resume-v2-finalize.spec.ts::test_29_settings_design`
- [ ] T095 [P] [US7] [Phase C] test #30: settings panel page (format/margins) — `tests/e2e/036-resume-v2-finalize.spec.ts::test_30_settings_page`

#### 分享 + 历史 + 移动 + 跨模块（test 31-35）

- [ ] T096 [P] [US7] [Phase C] test #31: settings panel sharing + statistics — `tests/e2e/036-resume-v2-finalize.spec.ts::test_31_settings_sharing`
- [ ] T097 [P] [US7] [Phase C] test #32: undo/redo (Ctrl+Z / Ctrl+Shift+Z) — `tests/e2e/036-resume-v2-finalize.spec.ts::test_32_undo_redo`
- [ ] T098 [P] [US7] [Phase C] test #33: auto-save 500ms debounce — `tests/e2e/036-resume-v2-finalize.spec.ts::test_33_auto_save`
- [ ] T099 [P] [US7] [Phase C] test #34: mobile sidebar collapse — `tests/e2e/036-resume-v2-finalize.spec.ts::test_34_mobile_sidebar`
- [ ] T100 [P] [US7] [Phase C] test #35: public URL `/r/:u/:slug` access + cross-module link — `tests/e2e/036-resume-v2-finalize.spec.ts::test_35_public_url_and_cross_module`

#### 主流程：成品简历制作（端到端贯穿）

- [ ] T101 [US7] [Phase C] 主流程 e2e：在 v2 编辑器按 `大模型应用开发简历v1.md` 填字段（Basics 姓名/邮箱/电话/地址/GitHub + Summary 6 条亮点 + Profiles + Experience 浩鲸云 + Projects 4 段 + Skills 4 分组）— `tests/e2e/036-resume-v2-finalize.spec.ts::test_main_resume_creation`
- [ ] T102 [US7] [Phase C] 主流程 e2e：保存 + 导出 PDF — `tests/e2e/036-resume-v2-finalize.spec.ts::test_main_export_pdf`

### Implementation for User Story 7

- [ ] T103 [US7] [Phase C] 编辑 `playwright.config.ts`：启用 webServer 配置（backend 8000 + arq 8001 + frontend 5173）
- [ ] T104 [US7] [Phase C] 编写 `tests/e2e/036-resume-v2-finalize.spec.ts` 的 `test.beforeAll` 钩子：mkdir `docs/evidence/036-playwright-<ts>/` + 初始化 storageState
- [ ] T105 [US7] [Phase C] 编写 `tests/e2e/036-resume-v2-finalize.spec.ts` 的 `test.afterAll` 钩子：调 `generateIncompleteList()` + `generateAcceptedList()`
- [ ] T106 [US7] [Phase C] 编写 helper 函数 `generateIncompleteList(evidenceDir)`：扫描所有 test() PASS/FAIL，输出 `incomplete-features.md`（格式 per playwright-spec-contract.md）
- [ ] T107 [US7] [Phase C] 编写 helper 函数 `generateAcceptedList(evidenceDir)`：扫描所有 test() PASS/FAIL，输出 `accepted-features.md`（格式 per playwright-spec-contract.md）
- [ ] T108 [US7] [Phase C] 编写 helper 函数 `compareFieldsToReference()`：读 `大模型应用开发简历v1.md` 与最终 PDF 内容对比，输出 `field-comparison.md`
- [ ] T109 [US7] [Phase C] 启动 backend + arq + frontend 三个 server（per quickstart.md Phase B.1）
- [ ] T110 [US7] [Phase C] 跑 Playwright 全部 35 个 test()：`npm run e2e -- tests/e2e/036-resume-v2-finalize.spec.ts --reporter=list`
- [ ] T111 [US7] [Phase C] 若 test() 失败：参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 修复 v2 对应组件，重跑至 100% 通过
- [ ] T112 [US7] [Phase C] 验证 evidence 产物：`docs/evidence/036-playwright-<ts>/{step-*.png ≥ 6 张, final-resume.pdf, field-comparison.md, incomplete-features.md, accepted-features.md}`
- [ ] T113 [US7] [Phase C] 验证 `incomplete-features.md` 中 P1 项 = 0（剩余 P2/P3 可接受）
- [ ] T114 [US7] [Phase C] 验证 `accepted-features.md` 中所有 P1 项 ✅
- [ ] T115 [US7] [Phase C] 验证 `field-comparison.md`：关键字段（姓名/邮箱/学校/公司/项目名/技能分类）与 `大模型应用开发简历v1.md` 一致

**Checkpoint**: US7 完成 — Playwright 验收通过 + 两份清单齐备 + 036 完成

---

## Phase 10: Polish & Cross-Cutting Concerns

**目的**: 跨 US 收尾 + 全栈回归 + 文档。

- [ ] T116 [P] [Phase C] 跑后端全量测试：`cd backend && uv run pytest -q`（期望 100% 通过）
- [ ] T117 [P] [Phase C] 跑前端 typecheck：`npm run typecheck`（期望 clean）
- [ ] T118 [P] [Phase C] 跑前端 vitest：`npm run test`（期望全绿）
- [ ] T119 [P] [Phase C] 跑后端 alembic 迁移最终验证：`cd backend && uv run alembic current` 显示 036 head
- [ ] T120 [P] [Phase C] 跑 frontend 单元测试 `npm run test -- tests/unit/route-redirects.test.tsx sidebar-resume-entry.test.tsx resume-list-empty-state.test.tsx topbar-new-resume-flow.test.tsx` 全绿
- [ ] T121 [Phase C] 更新 `specs/README.md` 中 036 状态为 ship（从 draft 移入 Done）+ 标注 Playwright 验收证据路径
- [ ] T122 [Phase C] 写 `specs/036-resume-v2-finalize/handoff.md`：记录 US1-US7 完成情况 + evidence 路径 + reactive-resume 参考修复点
- [ ] T123 [P] [Phase C] 同步更新 `AGENTS.md` 路由表：删除 v1 简历相关路由
- [ ] T124 [P] [Phase C] 同步更新 `.claude/agent-memory/` 中相关 memory（删除 v1 残留记忆条目）
- [ ] T125 [Phase C] git commit 整套 036 改动（per reviewer 流程：PASS → code-simplification → commit）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖 — 立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1 — **BLOCKS** Phase 3+（US3 实施前必须完成 cleanup 脚本 + alembic）
- **Phase 3 (US3)**: 依赖 Phase 2 — Phase 4+ 间接依赖（DB 干净起点后写 e2e）
- **Phase 4 (US2)**: 依赖 Phase 3（删文件前先确认 DB 无依赖）— Phase 5+ 依赖
- **Phase 5 (US1)**: 依赖 Phase 4（路由表收口后才好改 Sidebar/Topbar 引用） — Phase 6+ 依赖
- **Phase 6 (US5)**: 依赖 Phase 5（菜单单入口后列表页入口一致）— 可与 Phase 7 并行
- **Phase 7 (US4)**: 依赖 Phase 5（Topbar 单"新建简历"后才好挂 modal）— 可与 Phase 6 并行
- **Phase 8 (US6)**: 依赖 Phase 4+5+7（跨模块引用需菜单/路由/新建流程都就位后）— Phase 9 前置
- **Phase 9 (US7)**: 依赖 Phase 3+4+5+6+7+8（Playwright 验收时全部功能已就位）
- **Phase 10 (Polish)**: 依赖全部 US 完成

### User Story Dependencies

- **US3 (P1)**: Phase 2 完成后即可 — 无其他 US 依赖
- **US2 (P1)**: Phase 3（DB 清理）后 — 与 US3 工程上独立，但实施顺序上 US3 先（避免误删正在开发的代码引用）
- **US1 (P1)**: US2 后（路由收口后改 Sidebar/Topbar 才有意义）
- **US5 (P1)**: US1 后（菜单单入口后列表页入口一致）
- **US4 (P2)**: US1 后（Topbar 单"新建简历"后才好挂 modal）
- **US6 (P2)**: US2+US1+US4+US5 后（跨模块引用需多 US 都就位）
- **US7 (P1)**: 全部 US 后（Playwright 验收时全部功能已就位）

### Within Each User Story

- 测试（若包含）MUST 先写并 FAIL 再实现
- Models 在 Services 之前
- Services 在 Endpoints 之前
- 核心实现先于集成
- 单 US 完成后进入下一优先级

### Parallel Opportunities

- Phase 1 全部 [P] 任务可并行
- Phase 2 全部 [P] 任务可并行（除 T009 实现依赖 T006/T007/T008）
- Phase 3 全部任务串行（DB 状态依赖）
- Phase 4 中 T028/T029/T030 文件删除可并行
- Phase 6（US5）+ Phase 7（US4）可并行（不同文件无依赖）
- **Phase 9（US7）35 个 Playwright test() 全部 [P] 可并行**（独立截图证据）

---

## Parallel Example: User Story 7（关键并行场景）

```bash
# Phase 9 的 35 个 Playwright test() 可全部并发跑（Playwright 自身调度）
npx playwright test tests/e2e/036-resume-v2-finalize.spec.ts --workers=4
# 每个 test() 输出到 evidence/036-playwright-<ts>/<feature>/step-*.png
```

---

## Implementation Strategy

### MVP First（US3 + US2 + US1 + US5）

1. Phase 1: Setup
2. Phase 2: Foundational（cleanup 脚本 + alembic）
3. Phase 3: US3 数据清理（P1 必做）
4. Phase 4: US2 路由收口（P1 必做）
5. Phase 5: US1 单一菜单入口（P1 必做）
6. **STOP and VALIDATE**: 启动 dev server 验证单一入口 + 路由收口 + DB 干净
7. Demo 截图（侧边栏 / Topbar / 空状态）

### Incremental Delivery

1. Setup + Foundational → 基础设施 ready
2. + US3 → DB 干净起点（Demo: 列表页空状态）
3. + US2 → 路由表收口（Demo: 访问 `/resume-v2` 跳 `/resume`）
4. + US1 → 单一菜单（Demo: 侧边栏只有 1 个简历入口）
5. + US5 → 列表页简化（Demo: 空状态 CTA + 推荐模板缩略图）
6. + US4 → 新建流程（Demo: Topbar + → 选模板 → 进入编辑器）
7. + US6 → 体验补强（Demo: 跨模块引用全部走规范路径）
8. + US7 → Playwright 验收（Demo: 35 test() 100% 通过 + 成品 PDF）

### Parallel Team Strategy

- 主 Agent（Team Lead）：派发任务 + 监督 + 写日志
- Dev 子代理：实现 US2/US1/US4/US5/US6 的代码改动
- Test 子代理：实现 Phase 2 cleanup 单测 + Phase 9 Playwright 35 test()
- Reviewer 子代理：审查每批完成 + code-simplification + git commit
- 主 Agent：在 US7 失败时参考 reactive-resume 源码 + 重派 dev 修复

---

## Notes

- [P] 任务 = 不同文件，无依赖
- [Story] 标签映射任务到具体 US（[US1]~[US7]）以追踪
- [Phase] 标签映射任务到 Phase A/B/C 以匹配 plan.md 实施三阶段
- 每个 US 独立可完成 + 独立可测
- 测试 FAIL 后才能写实现（Constitution III）
- 任务或逻辑组完成后 commit
- 在任何 checkpoint 停下来独立验证 US
- 避免：模糊任务、同一文件冲突、跨 US 依赖破坏独立性
- 关键参考：`D:\Project\reactive-resume\apps\artboard\src\dialogs\resume\sections\`（实施 US7 时问题修复）
- 关键资源：`C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`（Playwright 主流程数据源）
