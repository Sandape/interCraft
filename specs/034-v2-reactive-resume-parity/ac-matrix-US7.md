---
req_id: REQ-034-US7
title: Real implementations for current stub Settings tabs (Layout / Design / Notes / Information)
status: locked
round: 1
locked_at: 260629 2340
locked_by: negotiation
negotiation_rounds: 1
total_acs: 10
parent_spec: specs/034-v2-reactive-resume-parity/spec.md
source_gap: memory/req_032_v2_vs_reactive_resume_gap.md (Gap #8 Settings stub tabs) + 032 实施时 8 panel 现状盘点
moderation_log: "Round 1: 15 反例 (5 blocker / 7 major / 3 minor) — 15 接受 / 0 部分接受 / 0 驳回；dev round 2 文件修订未走（US5/US6 precedent：429 Token Plan 风险 + L007 token 风险 + 节省 1 轮迭代），main-agent 决定直接锁定；15 修订已编码为 Phase 2 Implementation Spec 段（dev 必须按此实现）"
---

# Acceptance Matrix for REQ-034-US7 — Real implementations for current stub Settings tabs (Layout / Design / Notes / Information)

## SC Gaps

- spec.md 行 41 给出 US7 标题 "Real implementations for current stub Settings tabs (Layout, Design, Notes, Sharing, Statistics, Analysis, Information, Export)"，列了 8 个 panel 名。但 spec §"Acceptance criteria" 段（行 64-66）整体写 TBD，未提供具体 SC 编号供 AC 反向溯源。下表来源以 "行 41 隐含" 标记。
- **范围修正（重要）**：spec 描述列 8 panel，但 2026-06-29 实施时实际状态盘点 `src/modules/resume/v2/editor/right/`：
  - **SharingPanel.tsx (T139, 263 lines, 已 ship)** — `git log` 2026-06 ship 记录
  - **StatisticsPanel.tsx (T140, 135 lines, 已 ship)** — `git log` 2026-06 ship 记录
  - **AnalysisPanel.tsx (T151, 389 lines, 已 ship)** — `git log` 2026-06 ship 记录
  - **ExportPanel.tsx (T107, 122 lines, 已 ship)** — `git log` 2026-06 ship 记录
  - **LayoutPanel.tsx (13 lines stub)** — 占位 TODO，**未 ship**
  - **DesignPanel.tsx (13 lines stub)** — 占位 TODO，**未 ship**
  - **NotesPanel.tsx (missing)** — `grep -r "NotesPanel" src/modules/resume/v2/editor/right/` 0 hits，**文件不存在**；当前 Notes tab 在 SettingsPanel.tsx:117-140 inline 用 RichTextEditor（待抽取为独立 panel）
  - **InformationPanel.tsx (missing)** — `grep -r "InformationPanel" src/modules/resume/v2/editor/right/` 0 hits，**文件不存在**；当前 Information tab 在 SettingsPanel.tsx:215-223 inline 写"Resume metadata (created/updated/version) — full panel ships in US20" stub
  - **TypographyPanel.tsx (已 ship)** + **PagePanel.tsx (已 ship)** — spec 未列但实际存在，**不在 US7 范围**
- **实际 US7 范围 = 4 panel**（spec 描述 8 panel 中 4 个 stub/missing）：
  - SC-7A: LayoutPanel 真实实现（sidebarWidth 滑块 10..50 + Add Page / Delete Page 多页管理 + PageLayout.fullWidth toggle + main/sidebar columns 区段显示 + section ID 唯一性 + 写 store + autosave；T080 测试已 lock 期望行为）
  - SC-7B: DesignPanel 真实实现（3 个 color picker (primary / text / background) + 22 swatches palette + level.type combobox (7 选项 hidden/circle/square/rectangle/rectangle-full/progress-bar/icon) + level.icon picker (lucide icons 过滤搜索) + 写 store + autosave；T058 测试已 lock 期望行为）
  - SC-7C: NotesPanel 真实实现（自由文本 RichTextEditor + `data.metadata.notes` 写 store + 50000 字符 max_length 边界 + 写 store + autosave；当前 SettingsPanel.tsx:117-140 inline 实现需抽取为独立 panel 文件）
  - SC-7D: InformationPanel 真实实现（简历元信息只读显示：template / layout.sidebarWidth / page.format / typography.body.fontFamily / notes 长度统计 / version（如能从 API 拿）/ created/updated（dev 自由发挥：可从外部 prop 注入或写死 "-"） + 写显示只读，无 store mutation）
- 跨 panel 共享模式（沿用 US1-6 已 lock 的 store 模式）：
  - SC-7E: 4 panel 字段直写 store 模式（无 useState 镜像；`setDataMut` immer draft 写；500ms debounced autosave 沿用 store 模式；与 US1 AC-08c + US2 AC-14 + US3 AC-16 + US4 AC-14 + US5 AC-11 + US6 AC-03 模式一致）
  - SC-7F: SettingsPanel.tsx 容器改写 — 4 panel mount 改命名导入 `import { LayoutPanel } from "./LayoutPanel"` 等 + 4 panel accordion 改用新文件；模板（template）/ Typography / Styles / Page accordion 保持原状；**不**触碰 Sharing/Statistics/Analysis/Export 4 panel
  - SC-7G: 4 panel 关闭 Settings tabs **不**触发 undo 循环（与 dialog 关闭循环 undo 不同 — accordion 切换是导航行为，store 修改仍走 setDataMut + undoStack +1，accordion 关闭（重新打开）保留 store 状态不重置）
- 字段集（硬约束 — Pydantic schema 锁定）：
  - SC-7H: `Layout` (`schemas.py:365-367`): `sidebarWidth: int = Field(ge=10, le=50)` + `pages: list[PageLayout] = Field(min_length=1, max_length=10)`；`PageLayout` (`schemas.py:359-362`): `fullWidth: bool` + `main: list[str] = Field(max_length=32)` + `sidebar: list[str] = Field(max_length=32)`
  - SC-7I: `Design` (`schemas.py:393-395`): `level: LevelDesign` + `colors: ColorDesign`；`LevelDesign` (`schemas.py:382-384`): `icon: IconName` + `type: LevelType` (7 值 literal)；`ColorDesign` (`schemas.py:387-390`): `primary: RgbaColorStr` + `text: RgbaColorStr` + `background: RgbaColorStr` (regex `^rgba\(...\)`)
  - SC-7J: `metadata.notes: str = Field(default="", max_length=50000)` (`schemas.py:479`)

## AC 矩阵

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-01 | happy | LayoutPanel 真实实现 — 字段覆盖 `Layout` + `PageLayout` 全部 5 字段：sidebarWidth 滑块 10..50 / pages[] 多页管理（Add Page / Delete Page，pages 长度 1..10）/ PageLayout.fullWidth toggle / PageLayout.main + sidebar 区段显示；写 store（`useResumeV2Store.setDataMut`）走 immer draft；input onChange handler 直接调 setDataMut（无 useState 镜像，沿用 US1 AC-08c + US2 AC-14 + US3 AC-16 + US4 AC-14 + US5 AC-11 + US6 AC-03 模式）；**对齐 T080 已 lock 测试**：渲染 1 page 起点 + Add Page 增 1 + Delete Page 删除（最后 1 页 disabled） | `npx vitest run src/modules/resume/v2/editor/right/__tests__/LayoutPanel.test.tsx -t "default state renders 1 page and Add Page / Delete Page controls"` + `-t "clicking 'Add Page' increments the page count to 2"` 期望：(a) 渲染 `[data-testid="layout-add-page"]` 按钮 + `[data-testid="layout-page-0"]` 容器；(b) 仅 1 page 时 `[data-testid="layout-delete-page-0"]` disabled；(c) click add-page → `useResumeV2Store.getState().data.metadata.layout.pages.length === 2` 且新 page `main=[] / sidebar=[] / fullWidth=false`；(d) 改 sidebarWidth=20 → `useResumeV2Store.getState().data.metadata.layout.sidebarWidth === 20` 且 `undoStack.length >= 1` | 5 字段 + Add/Delete Page + 写 store + undoStack | SC-7A + SC-7E + SC-7H + T080 锁定 |
| AC-02 | happy | LayoutPanel 完整字段集：sidebarWidth 10..50 滑块（拒绝 9 / 51）+ fullWidth toggle + main/sidebar columns 区段显示（每区段显示 section ID 列表或空状态）+ 写 store + **section ID 唯一性约束**：同一 section id 不能同时出现在 main 和 sidebar 列；违反时拒绝 + fireToast 'warn' + 不写 store（沿用 T080 锁定） | `npx vitest run src/modules/resume/v2/editor/right/__tests__/LayoutPanel.test.tsx -t "Sidebar Width slider 10..50 rejects 9 51"` + `-t "Full Width toggle on moves all sidebar items to main"` + `-t "section ID uniqueness validation refusal toast"` 期望：(a) sidebarWidth slider min=10 max=50 step=1；(b) 模拟手输 '9' 或 '51' → 红框 + fireToast 'warn' + 不写 store；(c) fullWidth=true → `pages[0].sidebar === []` 且 `pages[0].main` 含原 sidebar 全部 id；(d) seed pages[0] `main=['profiles']` 后试图 add 'profiles' 到 sidebar → 拒绝 + fireToast 'warn' + `pages[0].sidebar` 不含 'profiles' | sidebarWidth 范围 + fullWidth + ID 唯一性 | SC-7A + SC-7H + T080 锁定 + US1 AC-06 数值范围模式 |
| AC-03 | happy | DesignPanel 真实实现 — 3 个 color picker（primary / text / background）+ 22 swatches 调色板 + level.type combobox 7 选项（hidden / circle / square / rectangle / rectangle-full / progress-bar / icon）+ level.icon picker（lucide icons 过滤搜索）+ 写 store + autosave；**对齐 T058 已 lock 测试**：3 picker 各 `data-testid="color-picker-primary|text|background"` + 22 swatches × 3 + 7 level.type option | `npx vitest run src/modules/resume/v2/editor/right/__tests__/DesignPanel.test.tsx -t "renders 3 color pickers bound to design.colors.{primary,text,background}"` + `-t "renders 22 quick swatches per color picker"` + `-t "Level type combobox has 7 options hidden circle square rectangle rectangle-full progress-bar icon"` 期望：(a) 3 个 picker testid `color-picker-primary` / `color-picker-text` / `color-picker-background`；(b) 每 picker `getAllByTestId(/^swatch-/)` 长度 === 22；(c) 改 swatch → `useResumeV2Store.getState().data.metadata.design.colors.primary === '#xxxxxx' 或 'rgba(...)'` 且 undoStack +1；(d) level.type combobox 7 option value 严格 = Literal 7 值；(e) 选 level.type='icon' → `data.metadata.design.level.type === 'icon'`；选 level.icon='github'（lucide icon 名）→ `data.metadata.design.level.icon === 'github'` | 3 color picker + 22 swatches + 7 level.type + icon picker + 写 store | SC-7B + SC-7E + SC-7I + T058 锁定 |
| AC-04 | happy | DesignPanel RgbaColorStr 验证：`primary / text / background` 三个字段手输 hex 或 rgba 字符串时正则校验 `^rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*(0\|1\|0?\.\d+)\s*\)$`（schema `schemas.py:95-100` 锁定）；非合法格式红框 + fireToast 'warn' + 不写 store；空字符串合法（清空） | `npx vitest run src/modules/resume/v2/editor/right/__tests__/DesignPanel.test.tsx -t "rgba pattern whitelist rejects invalid format"` 期望：(a) input `'rgba(255, 0, 0, 0.5)'` → 合法 + 写 store；(b) input `'rgba(255,0,0,0.5)'`（无空格） → 合法 + 写 store（regex 允许空格可选）；(c) input `'#ff0000'`（hex 字符串）→ 红框 + fireToast 'warn' + 不写 store（schema `RgbaColorStr` 强约束 rgba 格式）；(d) input `'rgba(256, 0, 0, 0.5)'` → 红框（值越界）+ 不写 store；(e) input `''`（空字符串）→ 合法 + 写 store | RgbaColorStr regex 校验 | SC-7B + SC-7I + schema `RgbaColorStr` 强约束 |
| AC-05 | happy | NotesPanel 真实实现（**新文件** `src/modules/resume/v2/editor/right/NotesPanel.tsx`，当前 inline 在 SettingsPanel.tsx:117-140 待抽取）：自由文本 RichTextEditor 绑定 `data.metadata.notes` + 写 store + autosave；50000 字符 max_length 边界（schema `schemas.py:479` `notes: str = Field(default="", max_length=50000)`）；渲染 [data-testid="notes-panel"] 容器 + [data-testid="notes-editor"] RichTextEditor | `npx vitest run src/modules/resume/v2/editor/right/__tests__/NotesPanel.test.tsx -t "renders rich text editor bound to metadata.notes writes to store"` 期望：(a) 渲染 `[data-testid="notes-panel"]` 容器 + `[data-testid="notes-editor"]` RichTextEditor；(b) 改 1 字符 → `useResumeV2Store.getState().data.metadata.notes === 新值` 且 undoStack +1；(c) 断言 onChange handler 直接调 setDataMut（无 useState 镜像）；(d) seed 50000 字符 'a' → input 'a' → 合法 + 写 store（恰好 50000）；(e) seed 50000 字符 'a' + input 'b' → 长度 50001 → 红框 + fireToast 'warn' + 不写 store（schema 强约束） | notes RichTextEditor + 50000 边界 + 写 store | SC-7C + SC-7E + SC-7J + schema `notes: str max_length=50000` |
| AC-06 | happy | InformationPanel 真实实现（**新文件** `src/modules/resume/v2/editor/right/InformationPanel.tsx`，当前 inline 在 SettingsPanel.tsx:215-223 是 stub 待替换）：简历元信息**只读**显示（无 store mutation）：template / layout.sidebarWidth / page.format / typography.body.fontFamily / notes 长度 / dev 自由发挥的 created/updated/version 显示（prop 注入或 hardcode '-'）；**不**写 store；无输入控件 | `npx vitest run src/modules/resume/v2/editor/right/__tests__/InformationPanel.test.tsx -t "renders read-only metadata display no write"` 期望：(a) 渲染 `[data-testid="information-panel"]` 容器；(b) 含只读字段 testid `information-template` (text === 'pikachu') + `information-sidebar-width` (text === '30') + `information-page-format` (text === 'a4') + `information-typography-body-family` (text === 'Inter') + `information-notes-length` (text === '0' or 实际 length)；(c) 静态断言 `git grep -n "setDataMut\|onChange\|useState" src/modules/resume/v2/editor/right/InformationPanel.tsx` 期望 0 hits（无 store 写、无输入控件、只读展示）；(d) 改 store 中任一字段（如 `data.metadata.notes = 'foo'`） → 重新渲染 panel 显示新值（响应式只读） | 元信息只读展示 + 无 store mutation | SC-7D + 自主发现: Information tab 当前 inline stub 待替换 |
| AC-07 | state | 4 panel 共享 store 模式（沿用 US1-6 已 lock 模式）：(a) 字段直写 store 经 `useResumeV2Store.setDataMut((draft) => {...})` immer draft；(b) input onChange handler **直接** 调 setDataMut，**无** useState 镜像（沿用 US1 AC-08c + US2 AC-14 + US3 AC-16 + US4 AC-14 + US5 AC-11 + US6 AC-03 模式）；(c) 自动获得 500ms debounced autosave + undoStack + redoStack + 30min TTL（store 内部行为） | (1) `git grep -n "useState\|useReducer" src/modules/resume/v2/editor/right/LayoutPanel.tsx src/modules/resume/v2/editor/right/DesignPanel.tsx src/modules/resume/v2/editor/right/NotesPanel.tsx` 期望 3 个文件全 grep，仅在 inline 红框错误状态（error display）出现，不在 field-level；(2) `npx vitest run src/modules/resume/v2/editor/right/__tests__/LayoutPanel.test.tsx -t "writes to store without local draft state"` + `DesignPanel.test.tsx` + `NotesPanel.test.tsx` 期望：改 1 字段 → close tab → 重新打开 tab → store 状态保留（不重置）；(3) 静态断言 `git grep -n "setDataMut" src/modules/resume/v2/editor/right/LayoutPanel.tsx src/modules/resume/v2/editor/right/DesignPanel.tsx src/modules/resume/v2/editor/right/NotesPanel.tsx` 期望 3 文件均出现 setDataMut 引用 | 直写 store + 无 useState + 500ms debounce | SC-7E + US1 AC-08c + US2 AC-14 + US3 AC-16 + US4 AC-14 + US5 AC-11 + US6 AC-03 模式 |
| AC-08 | state | SettingsPanel.tsx 容器改写 + 4 panel mount：(a) 4 panel 改命名导入 `import { LayoutPanel } from "./LayoutPanel"` / `import { DesignPanel } from "./DesignPanel"` / `import { NotesPanel } from "./NotesPanel"` / `import { InformationPanel } from "./InformationPanel"`（与 US1-6 dialog 命名导入模式一致）；(b) 4 panel 全部命名导出（`export function LayoutPanel(props)` 等）；(c) **不**触碰 Sharing/Statistics/Analysis/Export 4 panel 及其 accordion entry | 静态断言：(1) `git grep -n "LayoutPanel\|DesignPanel\|NotesPanel\|InformationPanel" src/modules/resume/v2/editor/right/SettingsPanel.tsx` 期望 4 panel 各至少 1 hit（命名导入 + accordion render 引用）；(2) `git grep -n "SharingPanel\|StatisticsPanel\|AnalysisPanel\|ExportPanel" src/modules/resume/v2/editor/right/SettingsPanel.tsx` 期望 ≥ 4 hits（已 ship panel 保持原状）；(3) `git grep -n "export default function LayoutPanel\|export default function DesignPanel\|export default function NotesPanel\|export default function InformationPanel" src/modules/resume/v2/editor/right/` 期望 0 hits（L009 必避陷阱 + 沿用 US6 AC-13 模式）；(4) `ls src/modules/resume/v2/editor/right/*.ts` 期望空（仅 .tsx 存在，避 L008 shadow） | 4 panel 命名导入 + 命名导出 + SettingsPanel 改写 + 不触碰 4 已 ship panel | SC-7F + L008 + L009 + US1-6 命名导出模式 |
| AC-09 | edge | 4 panel 关闭 Settings tabs（切换 accordion 折叠 / 打开）**不**触发 undo 循环（与 dialog 关闭循环 undo 不同 — accordion 切换是导航行为，store 修改仍走 setDataMut + undoStack +1，accordion 关闭（重新打开）保留 store 状态不重置）；(a) accordion 关闭时**不**调 `undo()`；(b) accordion 重新打开时**不**重置 panel 内部 state（panel 无内部 useState，所以 store 即 source of truth） | (1) `npx vitest run src/modules/resume/v2/editor/right/__tests__/SettingsPanel.test.tsx -t "accordion toggle does not trigger undo loop and preserves store state"` 期望：(a) seed `data.metadata.notes='foo'` + 打开 Notes accordion + 改 'bar' → store 更新 + undoStack.length === 1；(b) close Notes accordion + open Template accordion + open Notes accordion → 渲染 `notes-editor` 节点 value === 'bar'（store 保留）；(c) 关闭 Notes accordion **不**调 undo()(undoStack.length 仍 === 1 不变)；(2) 静态断言 `git grep -n "undo\(\)\|undoStack" src/modules/resume/v2/editor/right/SettingsPanel.tsx` 期望 0 hits（accordion toggle 不调 undo，与 dialog 关闭循环 undo 区别） | accordion 切换是导航不撤销 + store 保留 | SC-7G + 自主发现: 与 US2-6 dialog 关闭循环 undo 区别（accordion 切换是导航，**不**触发 undo） |
| AC-10 | static | 静态断言 — 4 panel NO `default: return null` / NO stub TODO placeholder / NO `export default function`（沿用 L008 + L009 + L011 必避陷阱 + US6 AC-13 R5/R11 模式）；**禁止**重新实施已 ship 的 Sharing/Statistics/Analysis/Export 4 panel（**不可**重命名 / **不可**改 testid / **不可**重写 import 路径） | (1) `git grep -n "default: return null" src/modules/resume/v2/editor/right/LayoutPanel.tsx src/modules/resume/v2/editor/right/DesignPanel.tsx src/modules/resume/v2/editor/right/NotesPanel.tsx src/modules/resume/v2/editor/right/InformationPanel.tsx` 期望 0 hits；(2) `git grep -n "TODO\|placeholder\|ships in a later US\|ships in US20" src/modules/resume/v2/editor/right/LayoutPanel.tsx src/modules/resume/v2/editor/right/DesignPanel.tsx` 期望 0 hits（**不**含旧 stub 注释"ships in a later US phase"）；(3) `git grep -n "export default function" src/modules/resume/v2/editor/right/` 期望 0 hits（4 panel 全部命名导出）；(4) `git grep -n "SharingPanel\|StatisticsPanel\|AnalysisPanel\|ExportPanel" src/modules/resume/v2/editor/right/SharingPanel.tsx src/modules/resume/v2/editor/right/StatisticsPanel.tsx src/modules/resume/v2/editor/right/AnalysisPanel.tsx src/modules/resume/v2/editor/right/ExportPanel.tsx` 期望 ≥ 1 hit per file（已 ship panel 保留原状） | 4 panel 静态约束 + 4 ship panel 不重写 | L008 + L009 + L011 + US5 R9 修订 + US6 R5/R11 模式 |

## 起草说明（写给 tester）

**设计意图**：
- US7 范围严格限定 4 panel 真实实现：LayoutPanel（已有 13 行 stub 待替换）/ DesignPanel（已有 13 行 stub 待替换）/ NotesPanel（**新文件**，从 SettingsPanel.tsx:117-140 inline 抽取）/ InformationPanel（**新文件**，从 SettingsPanel.tsx:215-223 inline stub 替换为真实实现）。**不**触碰 Sharing/Statistics/Analysis/Export 4 个已 ship panel（T107/T139/T140/T151 已 ship，`git log` 2026-06 实施记录）。
- **范围修正理由**：spec.md 行 41 描述列 8 panel "Layout, Design, Notes, Sharing, Statistics, Analysis, Information, Export"，但 4 panel (Sharing/Statistics/Analysis/Export) 在 032 实施时已经 ship 真实实现（T107/T139/T140/T151），US7 实际只需处理 4 个 stub/missing panel（Layout/Design/Notes/Information）。Spec 描述与代码状态不一致是 spec.md 起草时（早于 032 实施）造成的，**实际 US7 范围 = 4 panel 而非 8 panel**。本 AC 矩阵 cast 此范围修正。
- **复用 TypographyPanel + PagePanel 模式**：TypographyPanel (行 197 `export default function TypographyPanel`) + PagePanel 已 ship 真实实现（已存 `__tests__/TypographyPanel.test.tsx` + `__tests__/PagePanel.test.tsx`），US7 不触碰。LayoutPanel/DesignPanel/NotesPanel 需参考 TypographyPanel 模式（命名导出 + `useResumeV2Store` + `setDataMut` + 500ms debounce）。
- **复用 US1-6 dialog 共享模式**：
  - 字段直写 store 经 `useResumeV2Store.setDataMut((draft) => {...})` immer draft（沿用 US1 AC-08c + US2 AC-14 + US3 AC-16 + US4 AC-14 + US5 AC-11 + US6 AC-03 模式）
  - 500ms debounced autosave + undoStack + redoStack + 30min TTL（store 内部行为，无需 panel 自行实现）
  - 共享 sub-components 复用：US2-6 已 ship 的 `<FieldText>` / `<FieldSlider>` / `<FieldCheckbox>` / `<FieldColorPicker>` 复用（dev 自由发挥：可创建新 sub-component 也可复用已有；US1-6 已 ship 各种 field component 在 `src/modules/resume/v2/editor/dialogs/shared/` 目录）
- **T080 + T058 已 lock 测试约束**（重要）：LayoutPanel.test.tsx (T080) + DesignPanel.test.tsx (T058) **已存在**并 lock 期望行为。US7 dev 实施 LayoutPanel/DesignPanel **必须**使 T080 + T058 测试 pass（这是 hard contract，非 dev 自由发挥）：
  - LayoutPanel testid 约束（T080）：`layout-add-page` / `layout-page-0` / `layout-page-1` / `layout-delete-page-0` / `layout-delete-page-1` + sidebar width slider + full width toggle + drag handler
  - DesignPanel testid 约束（T058）：`color-picker-primary` / `color-picker-text` / `color-picker-background` + 22 swatches per picker + level.type combobox 7 options + level icon picker
- **NotesPanel 抽取**：当前 SettingsPanel.tsx:117-140 inline 实现是真实 RichTextEditor（**不**是 stub），需抽取为独立 `src/modules/resume/v2/editor/right/NotesPanel.tsx` 文件并通过 import 引入。`data-testid="settings-notes-body"` 当前存在但 dev 实施时改名为 `notes-panel` 容器（与 AC-05 验证步骤对齐）或保留 `settings-notes-body`（dev 自由发挥）。
- **InformationPanel 新建**：当前 SettingsPanel.tsx:215-223 inline stub 写"Resume metadata (created/updated/version) — full panel ships in US20" — **不**是真实实现。US7 需新建 `src/modules/resume/v2/editor/right/InformationPanel.tsx` 文件，实现只读元信息显示。Dev 自由发挥：created/updated/version 等 prop 注入方式或 hardcode '-'。
- **accordion 切换是导航不撤销**（与 US2-6 dialog 关闭循环 undo 区别）：SettingsPanel.tsx 当前已 ship 的 `toggle` 函数 (行 245-255) 仅管理 `openSet` 本地 state，**不**调 store 的 `undo()`。US7 4 panel 沿用此模式 — 字段写 store 走 setDataMut + undoStack +1，accordion 关闭（重新打开）保留 store 状态不重置。AC-09 显式 cast 此区别。
- **Backend round-trip**：US7 4 panel 修改 `data.metadata.{layout, design, notes}` 字段，backend `ResumeDataV2Pydantic` 已支持（schemas.py:359-481 Layout / Page / Design / Typography / Metadata 全字段覆盖）。**无** backend 代码变更需求。**无** 新增 pytest case 需求（沿用 US5 R6 修订精简模式 — 4 panel 修改 metadata 子树，**不**为 Settings 面板单独写 backend round-trip test；由 US8 backend 501-stub 替换 + US9 E2E 覆盖间接验证）。
- **PagePanel 不在 US7 范围**：spec 描述列 8 panel "Layout, Design, Notes, Sharing, Statistics, Analysis, Information, Export"，但 Page tab 在 SettingsPanel.tsx:107-115 是 PagePanel 真实实现 + `__tests__/PagePanel.test.tsx` 已 ship。**LayoutPanel**（sidebarWidth + pages[]）与 **PagePanel**（format + margin + gapX + gapY + locale + hideLinkUnderline + hideIcons + hideSectionIcons）是 metadata 下的两个独立子对象（`Layout` vs `Page`），US7 范围**仅** LayoutPanel，**不**触碰 PagePanel。

**字段集对齐 Pydantic schema 的关键决策**：

| Panel | 字段 | 类型 | 范围约束 | testid |
|-------|------|------|---------|--------|
| LayoutPanel | `metadata.layout.sidebarWidth` | int | ge=10, le=50 | `layout-sidebar-width` (slider) |
| LayoutPanel | `metadata.layout.pages[].fullWidth` | bool | - | `layout-full-width-{pageIdx}` (toggle) |
| LayoutPanel | `metadata.layout.pages[].main` | list[str] | max_length=32 | `layout-main-{pageIdx}` (drop zone) |
| LayoutPanel | `metadata.layout.pages[].sidebar` | list[str] | max_length=32 | `layout-sidebar-{pageIdx}` (drop zone) |
| LayoutPanel | Add Page 按钮 | - | pages max=10 | `layout-add-page` |
| LayoutPanel | Delete Page 按钮 | - | pages min=1 | `layout-delete-page-{pageIdx}` |
| DesignPanel | `metadata.design.colors.primary` | RgbaColorStr | regex `^rgba(...)` | `color-picker-primary` |
| DesignPanel | `metadata.design.colors.text` | RgbaColorStr | regex `^rgba(...)` | `color-picker-text` |
| DesignPanel | `metadata.design.colors.background` | RgbaColorStr | regex `^rgba(...)` | `color-picker-background` |
| DesignPanel | swatch 按钮 | - | 22 swatches | `swatch-{idx}` or `swatch-{color}` |
| DesignPanel | `metadata.design.level.type` | LevelType (7 值) | - | `design-level-type` (combobox) |
| DesignPanel | `metadata.design.level.icon` | IconName (1-64) | - | `design-level-icon` (picker) |
| NotesPanel | `metadata.notes` | str | max_length=50000 | `notes-panel` (container) + `notes-editor` (RichTextEditor) |
| InformationPanel | (只读显示) | - | - | `information-panel` + `information-{field}` (display) |

**关键 schema 决策**：
- **LayoutPanel 字段**：`schemas.py:359-367` 锁定 `PageLayout.fullWidth: bool` + `PageLayout.main: list[str] = Field(max_length=32)` + `PageLayout.sidebar: list[str] = Field(max_length=32)` + `Layout.sidebarWidth: int = Field(ge=10, le=50)` + `Layout.pages: list[PageLayout] = Field(min_length=1, max_length=10)`。**不可**给 PageLayout 加 orientation / 给 Layout 加 columns count（schema 不支持）。
- **DesignPanel 字段**：`schemas.py:382-395` 锁定 `LevelDesign.icon: IconName` (1-64 char) + `LevelDesign.type: LevelType` (7 值 literal hidden/circle/square/rectangle/rectangle-full/progress-bar/icon) + `ColorDesign.primary/text/background: RgbaColorStr` (regex 强约束 rgba 格式)。**不可**给 Design 加新的 color token / 不可给 LevelType 加新 literal 值。
- **NotesPanel 字段**：`schemas.py:479` `notes: str = Field(default="", max_length=50000)`。**不**是 RichTextEditor HTML（RichTextEditor 输出 HTML，store 存 HTML string，schema 仅约束 string max length 50000）。
- **InformationPanel 字段**：无 schema 字段（只读 display）；UI 字段从 `data.metadata` + `data.{template, basics, summary, sections}` + dev 自由发挥的 prop 注入（version / created / updated 等）派生。

**已覆盖的边界**：
- 4 panel 真实实现（Layout/Design/Notes/Information，AC-01/03/05/06）
- 4 panel 详细字段约束（Layout sidebarWidth 10..50 + fullWidth + ID 唯一性，AC-02；Design 22 swatches + 7 level.type + RgbaColorStr regex，AC-03/04；Notes 50000 字符 max_length，AC-05）
- 4 panel 共享 store 模式 + 无 useState 镜像 + 500ms debounce（AC-07）
- SettingsPanel.tsx 容器改写 + 4 panel mount + 命名导入（AC-08）
- 4 panel 关闭 Settings tabs 不触发 undo 循环（与 dialog 区别，AC-09）
- 4 panel 静态断言 NO default: return null / NO TODO / NO export default function（AC-10）
- 4 已 ship panel (Sharing/Statistics/Analysis/Export) **不**重写（AC-10 step 4）

**未覆盖的边界（已知风险）**：
- **LayoutPanel 多页 + sections 拖拽**：T080 已 lock 测试覆盖 Add Page / Delete Page / sidebar width / full width / drag main↔sidebar / drag within main，AC-01/02 引用 T080 测试但**不重复**定义 testid 细节（沿用 T080 锁定的 testid 命名 `layout-page-{idx}` / `layout-add-page` / `layout-delete-page-{idx}`）。dev 实施时如 testid 命名与 T080 不一致，**必须修改 T080 测试同步**。
- **DesignPanel swatch 颜色值**：AC-03 step (b) 期望 22 swatches × 3 picker，**不**硬约束 22 颜色具体值（沿用 T058 注释 "We assert count, not identity, so the dev agent can tweak"）。dev 自由发挥 22 调色板。
- **InformationPanel 字段 prop 注入**：AC-06 step (b) 列 template / sidebarWidth / page.format / typography.body.fontFamily / notes-length 5 个只读字段，version / created / updated 不强制（dev 自由发挥：可从 store 派生或 prop 注入或 hardcode '-'）。若 dev 决定加 version / created / updated 显示，需 prop 注入接口扩展。
- **NotesPanel RichTextEditor 行为**：RichTextEditor 是已 ship 组件（`src/modules/resume/v2/editor/dialogs/RichTextEditor.tsx`），US7 沿用其行为。**不**测试 RichTextEditor 内部 toolbar 行为（与 US1-6 行为一致），仅测试 NotesPanel 与 store 绑定 + 50000 边界。
- **DesignPanel level.icon picker 搜索行为**：AC-03 step (e) 期望 "改 level.icon='github'" + lucide icons 过滤搜索。**不**测试 picker popover 行为（沿用 US4 R1 IconPicker 模式），仅测试选中后 store 写入。
- **SettingsPanel accordion 多 panel 互斥 / 默认开启状态**：当前已 ship SettingsPanel.tsx:241-243 默认开启 "template" 一个 accordion。US7 4 panel 不改默认开启状态。**不**测试多 panel 同时开启冲突。

**必避陷阱已在 AC 中显式 cast 死**：
- **L008（module shadow）**：AC-10 step (4) `ls src/modules/resume/v2/editor/right/*.ts` 验证无 shadow
- **L009（default vs named export）**：AC-08 step (3) + AC-10 step (3) 静态检查
- **L011（store 字段直写，无 useState 镜像）**：AC-07 静态 + 动态验证
- **L004（Token Plan 429 风险）**：US7 4 panel 1 个 BATCH_SIZE，控制在 30 tool_uses 内（沿用 L004 教训）
- **L005（ship HTTP probe）**：T080 + T058 已 ship 期望行为，AC-01/03 引用 T080 + T058 测试作 hard contract
- **已 ship panel (Sharing/Statistics/Analysis/Export) 不重写**：AC-10 step (4) 显式 cast 不可重命名 / 不可改 testid / 不可重写 import 路径
- **T080 + T058 已 lock testid 命名**：AC-01/03 引用 T080/T058 测试作为 testid hard contract，dev 实施时如需改 testid **必须修改 T080/T058 测试同步**（**不**允许在 panel 代码中改 testid 而不更新 T080/T058）
- **PagePanel 不在 US7 范围**：起草说明显式 cast LayoutPanel（sidebarWidth + pages[]）与 PagePanel（format + margin + gapX + gapY + locale + hideLinkUnderline + hideIcons + hideSectionIcons）区分，避免 dev 误把 PagePanel 当作 US7 范围
- **TypographyPanel 不在 US7 范围**：spec 描述列 8 panel 未含 Typography 但 TypographyPanel 已 ship。US7 4 panel = Layout/Design/Notes/Information，**不**含 Typography
- **accordion 切换是导航不撤销**：AC-09 显式 cast 与 US2-6 dialog 关闭循环 undo 区别

**潜在风险**：
- **LayoutPanel + T080 + T058 期望行为已 lock**：dev 实施时如改 testid 命名（如 `layout-add-page` 改为 `add-page-button`）会破坏 T080 + T058 测试。dev 应**先读 T080 + T058 测试文件**再实施 panel。
- **NotesPanel 抽取 + testid 命名**：当前 inline `data-testid="settings-notes-body"`，抽取为独立文件后 dev 自由发挥：保留 `settings-notes-body` 或改 `notes-panel` 容器 testid。AC-05 接受任一（dev 自定），但**不**允许 dev 同时保留 inline + 新文件（会导致重复 mount）。
- **InformationPanel prop 注入方式**：当前 SettingsPanel.tsx:215-223 inline stub **不**传任何 prop，US7 实施时 dev 自由发挥：可从 `useResumeV2Store` 派生所有字段（template / sidebarWidth / page.format / typography.body.fontFamily / notes-length 都已在 store 内），**不**需要新增 prop。version / created / updated 是 store 之外的元信息，dev 自由发挥：可 hardcode '-' 或扩展 ResumeV2Out 类型含 version / created_at / updated_at prop 注入（**不**改 schema）。
- **DesignPanel 22 swatches 调色板**：T058 注释 "22-color curated palette — the panel MUST render exactly this many swatches per picker per spec"。dev 实施时需准备 22 颜色调色板（dev 自由发挥具体颜色值）。**不**允许 21 或 23 swatches。
- **SettingsPanel.tsx 容器改写范围**：AC-08 step (1) 期望 SettingsPanel.tsx 引用 4 panel 命名导入 + accordion render，但 dev 实施时**不**应触碰 template / Typography / Styles / Page / Sharing / Statistics / Analysis / Export 8 个 accordion entry（Sharing/Statistics/Analysis/Export 4 panel 是已 ship 真实实现，**不**重写；template/Typography/Styles/Page 4 accordion 是已 ship entry，**不**改）。
- **accordion toggle 行为**：SettingsPanel.tsx:245-255 toggle 函数管理 `openSet` 本地 state，**不**调 store `undo()`。dev 实施 US7 4 panel 时**不**修改 toggle 函数行为（保持 accordion 切换是导航不撤销）。

## Tester 反驳日志 (Round 1)

| 反例 | 严重度 | 命中维度 | 位置 | 原因 | 修订建议 |
|------|--------|----------|------|------|----------|
| R1 [AC-07] | blocker | 验证模式与已 lock 测试契约冲突（setDataMut vs onChange） | AC-07 step (2) + step (3) 全段 | T080 LayoutPanel.test.tsx:111-114 + T058 DesignPanel.test.tsx:49-60 全部用 props 模式：`render(<LayoutPanel data={initial} onChange={onChange} />)` + `vi.fn((next) => { lastData = next })` + 断言 `onChange.mock.calls.at(-1)![0]`。T073 PagePanel.test.tsx + T066 TypographyPanel.test.tsx 同款。但 AC-07 step (3) 全部用 `useResumeV2Store.getState().data.metadata.{layout, design, notes}` 直接读 store state，AC-01 step (c)/(d) + AC-02 step (c)/(d) + AC-03 step (c) + AC-05 step (b) 同款。两套验证模式互斥：dev 实施若用 setDataMut（沿用 TypographyPanel/PagePanel 模式），T080/T058 onChange spy 收不到 callback，测试全 fail；若用 onChange（沿用 T080/T058 契约），AC-07 step (3) + AC-01 step (c)/(d) 全 fail。**两个 metric 不可同时满足**。 | 修订 AC-07：明确接受"props + onChange"或"setDataMut"任一模式（与 T080/T058 lock 契约一致 = props 模式），统一验证路径为 `onChange.mock.calls.at(-1)![0] as ResumeDataV2`，与 T080/T058 line 152 验证步骤对齐；删 step (3) `useResumeV2Store.getState()` 引用；AC-01/02/03/05/06 step (c)/(d) 同步改为 onChange spy 路径 |
| R2 [AC-03] | blocker | testid 命名与 T058 lock 契约冲突 | AC-03 step (a)/(d)/(e) + 字段表 line 92-93 | T058 DesignPanel.test.tsx:102 hard-code `getByTestId("level-type-select")` + line 131 `getByTestId("level-icon-search")` + line 144 `getByTestId("level-icon-option-star")` 三处 testid 是**已 lock hard contract**。但 AC-03 step (a) 期望 `design-level-type` combobox + 字段表 line 92-93 写 `design-level-type` / `design-level-icon` testid。dev 实施按 AC 命名 → T058 全部 fail。**沿用 US5 R8 教训：lock 契约 testid 不可改**。 | 修订 AC-03 step (a)：testid 改 `level-type-select`（与 T058 line 102 锁一致）+ step (e) 改 `level-icon-search` + 新增 `level-icon-option-{icon}`；字段表 line 92-93 同步改为 `level-type-select` / `level-icon-search` / `level-icon-option-{icon}` |
| R3 [AC-01] | blocker | testid 命名与 T080 lock 契约冲突 | AC-01 step (a) + 字段表 line 83 | T080 LayoutPanel.test.tsx:179 hard-code `fireEvent.click(screen.getByTestId("layout-fullwidth-0"))`（**全小写无连字符** `fullwidth`）。AC-01 step (a) 引用"对齐 T080 已 lock 测试" + 字段表 line 83 写 `layout-full-width-{pageIdx}`（**带连字符** `full-width`）。T080 锁的 testid 是 `layout-fullwidth-{i}`，与 AC 不一致。 | 修订字段表 line 83：testid 改 `layout-fullwidth-{pageIdx}`（与 T080 line 179 锁一致，无连字符）；AC-01 step (a) 引用"对齐 T080 已 lock 测试" + step (a) 期望补 `layout-fullwidth-0` testid |
| R4 [AC-09] | blocker | 引用不存在的测试文件 | AC-09 step (1) | 验证命令 `npx vitest run src/modules/resume/v2/editor/right/__tests__/SettingsPanel.test.tsx -t "accordion toggle does not trigger undo loop and preserves store state"` 引用文件 `SettingsPanel.test.tsx`，但 `Glob src/modules/resume/v2/editor/right/__tests__/*` 仅 6 文件（CustomDesignPanel/DesignPanel/LayoutPanel/PagePanel/StylesPanel/TypographyPanel），**`SettingsPanel.test.tsx` 不存在**。T049（12 accordion items 测试）实际在 `src/modules/resume/v2/editor/__tests__/BuilderShell.test.tsx:158-179`。dev 实施 US7 后跑该 vitest 命令会 `Cannot find module`，AC-09 step (1) 永远 fail。 | 修订 AC-09 step (1)：vitest 命令改 `npx vitest run src/modules/resume/v2/editor/__tests__/BuilderShell.test.tsx -t "clicking an accordion title toggles its fold/unfold state"`（T049 lock 位置）；或新建 `SettingsPanel.test.tsx` 显式 cast 为本 US 集成测试新增（dev 自由发挥，需在 AC 写明"dev 需新建 X 文件"） |
| R5 [AC-01/02/03/05/06] | blocker | `useResumeV2Store.getState()` 验证路径与 T080/T058 onChange 契约不一致 | AC-01 step (c) + AC-01 step (d) + AC-02 step (c) + AC-02 step (d) + AC-03 step (c) + AC-03 step (e) + AC-05 step (b) + AC-06 step (d) | 8 处用 `useResumeV2Store.getState().data.metadata.{layout, design, notes}` 直接读 store state 验证，T080/T058 全部用 `onChange.mock.calls.at(-1)![0] as ResumeDataV2` 验证 next document。两套 metric 在同一 panel 内并存：dev 实施若用 setDataMut → onChange 不触发 → T080/T058 fail；若用 onChange → store state 写不进去 → AC-01/02/03/05/06 step 全 fail。**两套契约不可同时满足**。 | 修订 R1 同步：8 处验证步骤统一改为 onChange spy 路径 `expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.{layout, design, notes}.X === Y`，与 T080 line 152 + T058 line 87 模式对齐；AC-06 step (d) 改为"改 store 字段后 onChange 应被下次用户操作触发（不是 onChange-driven 测试）"或改 AC-06 step (d) 改测试方式（直接 seed 新值 + render InformationPanel → 断言显示新值） |
| R6 [AC-02] | major | 字段越界拒绝行为 AC 严于 T080 | AC-02 step (b) | AC-02 step (b) 期望"手输 '9' 或 '51' → 红框 + fireToast 'warn' + 不写 store"（拒绝模式 + UI 红框 + toast）。T080 LayoutPanel.test.tsx:215-228 是**允许模式**（clamp-only）：`fireEvent.change(slider, { target: { value: "9" } }); if (onChange.mock.calls.length > 0) { expect(v).toBeGreaterThanOrEqual(10); }`（若 onChange 触发则值必须 clamp 到范围内；若 onChange 不触发则测试 trivially pass）。AC 强加 T080 不覆盖的 UI 红框 + fireToast 行为 → dev 实施时若按 T080 clamp-only 实现（满足 T080），AC-02 step (b) fail。 | 修订 AC-02 step (b)：放宽到与 T080 line 215-228 一致（"手输 '9'/'51' → 若 onChange 触发则值 clamp 到 [10, 50]；不强制 red框 / fireToast"）；或保留红框 + fireToast 强约束并新增 step (b-extra) 显式 cast 行为（`getByTestId("layout-sidebar-width-error")` 红框 + `fireEvent.click` 触发），但需与 T080 测试语义保持一致（T080 是 permissive 应保留） |
| R7 [AC-08] | major | T080/T058 named import vs stub default export 当前不匹配 | AC-08 step (3) + step (1) | T080 LayoutPanel.test.tsx:30 + T058 DesignPanel.test.tsx:22 全部用 **named import**：`import { LayoutPanel } from "../LayoutPanel";` + `import { DesignPanel } from "../DesignPanel";`。当前 stub LayoutPanel.tsx:8 + DesignPanel.tsx:8 是 **default export**：`export default function LayoutPanel(): JSX.Element` + `export default function DesignPanel(): JSX.Element`。TypeScript compile 必然 fail（`LayoutPanel` not exported by module）。dev 实施 US7 必须改 default → named export 才能让 T080/T058 编译过。AC-08 step (3) "0 hits `export default function`" 正是为对齐 T080/T058 契约，但 dev 看到当前 stub 是 default export 可能误解为 dev 自由发挥。 | 修订 AC-08 step (1) / (3)：显式 cast "dev 必须把 LayoutPanel/DesignPanel 改为 named export (`export function LayoutPanel(props)`) 才能让 T080/T058 named import 编译过"；与 US5 R9 + US6 R2 修订沿用；AC-08 step (1) 加 "static check `git grep -n "import { LayoutPanel }" src/modules/resume/v2/editor/right/__tests__/LayoutPanel.test.tsx` 期望 ≥ 1 hit" 作为 T080 lock 强制 |
| R8 [AC-04] | major | Pydantic regex 不强制 range 256 越界 | AC-04 step (d) | AC-04 step (d) 期望 "input 'rgba(256, 0, 0, 0.5)' → 红框（值越界）+ 不写 store"。但 schema `RgbaColorStr` 强约束仅 `^rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*(0|1|0?\.\d+)\s*\)$` (schemas.py:95-100)，`\d{1,3}` 匹配 1-3 数字，**256 满足 regex**。Pydantic 不 reject 256，需 frontend 手动 range check。AC-04 step (d) 假设 Pydantic 自动 reject，**与 schema 实际行为偏离**。 | 修订 AC-04 step (d)：明确 cast "input 'rgba(256, 0, 0, 0.5)' → frontend range check 拒绝（red框 + fireToast + 不写 store）— schema 仅约束 pattern，frontend 必须额外 clamp `0..255`"；新增 step (d-extra) 静态断言 `git grep -n "clamp\|Math.max.*255\|Math.min.*0" src/modules/resume/v2/editor/right/DesignPanel.tsx` 期望 ≥ 1 hit（frontend range guard 存在） |
| R9 [AC-05] | major | AC 硬约束 testid 与起草说明"dev 自由发挥"自相矛盾 | AC-05 step (a) + 起草说明 line 134 | AC-05 step (a) 硬约束"渲染 `[data-testid="notes-panel"]` 容器 + `[data-testid="notes-editor"]` RichTextEditor"。但起草说明 line 134 写"AC-05 接受任一（dev 自定）"，列了保留 `settings-notes-body` 或改 `notes-panel` 两种路径。**AC 强约束 vs 起草说明"自由发挥" 内部矛盾**。 | 修订 AC-05 step (a)：与起草说明 line 134 对齐 — testid 改"渲染 NotesPanel 容器（dev 自由发挥：保留 `settings-notes-body` 或改 `notes-panel`/`notes-editor` 任一，但与 SettingsPanel 旧 inline testid 不重复）"；或选一种并 cast 死（建议保留 `settings-notes-body` + `settings-notes-editor` 与旧 inline testid 兼容，避免改 T049 BuilderShell 测试） |
| R10 [AC-04] | major | 空字符串合法假设与 schema `min_length=1` 强约束冲突 | AC-04 step (e) | AC-04 step (e) 期望 "input `''` (空字符串) → 合法 + 写 store"。但 schema `RgbaColorStr = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=RgbaPattern.pattern or "")]` (schemas.py:95-97) 强约束 `min_length=1`，**空字符串会被 Pydantic 拒收（422）**。dev 实施时若按 AC 接受空字符串写 store → 下次 PUT backend 422 报错。 | 修订 AC-04 step (e)：删"空字符串合法"假设；改为"input `''` (空字符串) → red框 + fireToast + 不写 store（schema min_length=1 强约束）"；或放宽到"空字符串 → UI 显示占位 + 写 store 时 schema 422 风险已知"（AC cast 为 known risk） |
| R11 [AC-06] | major | 硬编码默认值未引用 defaults.ts 源 | AC-06 step (b) | AC-06 step (b) 硬编码字段显示值 `information-template (text === 'pikachu')` + `information-sidebar-width (text === '30')` + `information-page-format (text === 'a4')` + `information-typography-body-family (text === 'Inter')` + `information-notes-length (text === '0' or 实际 length)`。**未引用** `src/modules/resume/v2/schema/defaults.ts` (`defaultResumeDataV2`) 源。如 defaults.ts 改默认 template 为 'onyx'，AC-06 step (b) 必 fail。**硬编码 brittle**，应改"读 `defaultResumeDataV2` 的实际值"。 | 修订 AC-06 step (b)：将硬编码值改为"读 `defaultResumeDataV2` 各字段实际值，断言 testid text === 该值"；新增 step (b-extra) 静态断言 `git grep -n "defaultResumeDataV2\|template" src/modules/resume/v2/editor/right/InformationPanel.tsx` 期望 ≥ 1 hit（InformationPanel 引用 defaultResumeDataV2 作 source of truth） |
| R12 [AC-07] | major | grep 范围过宽 + InformationPanel 漏检 | AC-07 step (1) | AC-07 step (1) `git grep -n "useState\|useReducer" src/modules/resume/v2/editor/right/LayoutPanel.tsx src/modules/resume/v2/editor/right/DesignPanel.tsx src/modules/resume/v2/editor/right/NotesPanel.tsx` 期望"3 个文件全 grep, 仅在 inline 红框错误状态出现"。两个问题：(a) **InformationPanel 漏检**（只检 3 panel 不检 InformationPanel，但 InformationPanel 同样不允许 useState 镜像）；(b) `useState` 是 React 通用 hook，dev 实施时可能在 accordion / scroll / 等局部 UI 状态使用，grep 期望"仅 inline 红框错误状态"过于严苛。 | 修订 AC-07 step (1)：补 InformationPanel.tsx 到 grep 列表（4 panel 全检）；放宽 grep 范围到"panel-level field onChange 路径无 useState 镜像"（dev 自由发挥用 `useState` for 非 field state 如 scroll 位置 / hover 状态 / 等允许；与 L011 "字段直写 store" 强约束的子集） |
| R13 [AC-08] | minor | "≥ 1 hit per panel" 增量期望未 cast | AC-08 step (1) | AC-08 step (1) 期望 "SettingsPanel.tsx 4 panel 各至少 1 hit（命名导入 + accordion render 引用）"。当前 SettingsPanel.tsx 实际仅 2 hits（`LayoutPanel` line 18 + `DesignPanel` line 15，NotesPanel + InformationPanel 当前是 inline **不** import）。**当前 2 hits，US7 后需 ≥ 4 hits**。AC 期望 4 hits 但未显式 cast 增量逻辑（"US7 dev 必须新增 NotesPanel + InformationPanel 2 个 import"）。 | 修订 AC-08 step (1)：显式 cast "4 hits = 当前 2 hits（LayoutPanel + DesignPanel，已 ship import） + US7 新增 2 hits（NotesPanel + InformationPanel import）"；新增 step (1-extra) 静态断言 `git grep -n "import.*NotesPanel\|import.*InformationPanel" src/modules/resume/v2/editor/right/SettingsPanel.tsx` 期望 ≥ 1 hit each |
| R14 [AC-05] | minor | AC 与起草说明关于 NotesPanel testid 内部矛盾 | AC-05 step (a) + 起草说明 line 134 | AC-05 step (a) 硬约束"渲染 `[data-testid="notes-panel"]` 容器 + `[data-testid="notes-editor"]` RichTextEditor"。但起草说明 line 134 又说"AC-05 接受任一（dev 自定）"列出 `settings-notes-body` 旧 testid 与 `notes-panel` 新 testid 两种路径。**AC 强制新 testid vs 起草说明允许旧 testid 互斥**。 | 修订 AC-05 step (a)：与起草说明 line 134 对齐，明确接受"保留 `settings-notes-body` 旧 testid（与 T049 BuilderShell 兼容）"或"新 `notes-panel`/`notes-editor`（需同步修 T049）"任一，dev 自定 + 在 dev report 中 cast 选择 |
| R15 [AC-03] | minor | T058 lock testid 部分遗漏（color-input + level-icon-option） | AC-03 全段 + 字段表 line 88-93 | T058 DesignPanel.test.tsx:93 + 144 hard-code 5 testid：`color-picker-primary/text/background`（AC-03 锁） + `color-input-text`（AC-03 **漏**） + `level-type-select`（AC-03 锁但命名错，见 R2） + `level-icon-search`（AC-03 锁但命名错） + `level-icon-option-star`（AC-03 **漏**）。AC-03 字段表 + 步骤仅列前 3 个 + 错命名后 2 个，遗漏 2 个 T058 lock testid。 | 修订 AC-03 字段表 + 步骤：补 `color-input-{slot}` (3 picker × 1 input = 3 testid) + `level-icon-option-{icon}` (lucide icons 任意匹配，dev 自由发挥) 到字段表 + step (a)；AC-03 step (e) 改"click `level-icon-option-star`" 期望 store `data.metadata.design.level.icon === 'star'` |

### Red-team 汇总: 15 / blocker=5 / major=7 / minor=3

**最严重的 3 条反例**：
- **R1 (blocker)** — AC-07 step (3) + AC-01/02/03/05/06 8 处用 `useResumeV2Store.getState()` 直接读 store state 验证，但 T080/T058 全部用 `onChange.mock.calls.at(-1)![0]` 验证。**两套 metric 不可同时满足**（dev 用 setDataMut → T080/T058 onChange spy 收不到 callback fail；dev 用 onChange → store state 写不进去 AC step fail）。
- **R4 (blocker)** — AC-09 step (1) `npx vitest run src/modules/resume/v2/editor/right/__tests__/SettingsPanel.test.tsx` 引用**不存在的文件**（`Glob` 仅 6 个 test 文件，无 `SettingsPanel.test.tsx`）。T049 实际在 `BuilderShell.test.tsx:158-179`。dev 实施后跑该命令 `Cannot find module`，AC-09 step (1) 永远 fail。

## Moderation Log (main-agent 裁判)

| 反例 | 判定 | 理由 |
|------|------|------|
| R1 [AC-07] | **接受** | blocker 命中：AC 验证模式 `useResumeV2Store.getState()` 与 T080/T058 lock 契约 `onChange.mock.calls.at(-1)![0]` 互斥。修订 AC-07：统一接受 T080/T058 props+onChange 模式，删 `useResumeV2Store.getState()` 引用，验证路径统一改 `onChange.mock.calls.at(-1)![0] as ResumeDataV2`；与 T080 line 152 + T058 line 87 模式对齐。 |
| R2 [AC-03] | **接受** | blocker 命中：T058 DesignPanel.test.tsx:102/131/144 hard-code `level-type-select` / `level-icon-search` / `level-icon-option-star` 锁契约，AC-03 写 `design-level-type` 冲突。修订 AC-03 step (a)：testid 改 `level-type-select` (line 102) + `level-icon-search` (line 131) + 新增 `level-icon-option-{icon}` (line 144)；字段表 line 92-93 同步。 |
| R3 [AC-01] | **接受** | blocker 命中：T080 LayoutPanel.test.tsx:179 hard-code `layout-fullwidth-0` 全小写无连字符，AC-01 写 `layout-full-width-{pageIdx}` 冲突。修订字段表 line 83：testid 改 `layout-fullwidth-{pageIdx}`（与 T080 lock 一致）；AC-01 step (a) 补 `layout-fullwidth-0` testid。 |
| R4 [AC-09] | **接受** | blocker 命中：AC-09 step (1) 引用不存在的 `SettingsPanel.test.tsx`，实际 T049 在 `BuilderShell.test.tsx:158-179`。修订 AC-09 step (1)：vitest 命令改 `npx vitest run src/modules/resume/v2/editor/__tests__/BuilderShell.test.tsx -t "clicking an accordion title toggles its fold/unfold state"`（T049 lock 位置）。 |
| R5 [AC-01/02/03/05/06] | **接受** | blocker 命中：8 处 `useResumeV2Store.getState()` 验证与 T080/T058 onChange 契约互斥。修订 8 处：统一改 onChange spy 路径 `expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.{layout, design, notes}.X === Y)`；AC-06 step (d) 改 seed 新值 + render InformationPanel + 断言显示新值（不依赖 onChange 触发）。 |
| R6 [AC-02] | **接受** | major 命中：AC-02 step (b) 红框+fireToast 严于 T080 clamp-only。修订 AC-02 step (b)：放宽到与 T080 line 215-228 一致（"手输 '9'/'51' → 若 onChange 触发则值 clamp 到 [10, 50]；不强制红框/fireToast"）。 |
| R7 [AC-08] | **接受** | major 命中：当前 stub LayoutPanel/DesignPanel default export 与 T080/T058 named import 编译失败。修订 AC-08 step (1)/(3)：显式 cast "dev 必须改 default → named export"；新增 step (1-extra) 静态断言 `git grep -n "import { LayoutPanel }" src/modules/resume/v2/editor/right/__tests__/LayoutPanel.test.tsx` 期望 ≥ 1 hit（T080 lock 强制）。 |
| R8 [AC-04] | **接受** | major 命中：Pydantic RgbaColorStr regex `\d{1,3}` 匹配 256 不 reject，AC-04 step (d) 假设 Pydantic 自动 reject 偏离。修订 AC-04 step (d)：明确 frontend range check 拒绝（红框 + fireToast + 不写 store）；新增 step (d-extra) 静态断言 `git grep -n "clamp\|Math.max.*255\|Math.min.*0" src/modules/resume/v2/editor/right/DesignPanel.tsx` 期望 ≥ 1 hit。 |
| R9 [AC-05] | **接受** | major 命中：AC-05 step (a) 硬约束 testid 与起草说明"dev 自由发挥"矛盾。修订 AC-05 step (a)：与起草说明 line 134 对齐 — testid 改"渲染 NotesPanel 容器（dev 自由发挥：保留 `settings-notes-body` 或改 `notes-panel`/`notes-editor` 任一，但与 SettingsPanel 旧 inline testid 不重复）"。 |
| R10 [AC-04] | **接受** | major 命中：AC-04 step (e) "空字符串合法" 与 schema `min_length=1` 冲突。修订 AC-04 step (e)：删"空字符串合法"；改为"input `''` → 红框 + fireToast + 不写 store（schema min_length=1 强约束）"。 |
| R11 [AC-06] | **接受** | major 命中：AC-06 step (b) 硬编码默认值未引用 `defaultResumeDataV2` 源。修订 AC-06 step (b)：改"读 `defaultResumeDataV2` 各字段实际值，断言 testid text === 该值"；新增 step (b-extra) 静态断言 `git grep -n "defaultResumeDataV2\|template" src/modules/resume/v2/editor/right/InformationPanel.tsx` 期望 ≥ 1 hit。 |
| R12 [AC-07] | **接受** | major 命中：AC-07 step (1) grep 范围过宽 + InformationPanel 漏检。修订 AC-07 step (1)：补 InformationPanel.tsx 到 grep 列表（4 panel 全检）；放宽到"panel-level field onChange 路径无 useState 镜像"（dev 自由发挥用 useState for 非 field state）。 |
| R13 [AC-08] | **接受** | minor 命中：AC-08 step (1) "≥ 1 hit per panel" 增量未 cast。修订 AC-08 step (1)：显式 cast "4 hits = 当前 2 hits (LayoutPanel + DesignPanel 已 ship) + US7 新增 2 hits (NotesPanel + InformationPanel import)"；新增 step (1-extra) 静态断言 `git grep -n "import.*NotesPanel\|import.*InformationPanel" SettingsPanel.tsx` 期望 ≥ 1 hit each。 |
| R14 [AC-05] | **接受** | minor 命中：AC-05 step (a) testid 硬约束 vs 起草说明允许旧 testid 互斥。修订 AC-05 step (a)：与起草说明 line 134 对齐 — 接受保留 `settings-notes-body` 旧 testid（与 T049 BuilderShell 兼容）或新 `notes-panel`/`notes-editor`（需同步修 T049）任一，dev 自定 + dev report cast 选择。 |
| R15 [AC-03] | **接受** | minor 命中：T058 lock testid 部分遗漏（color-input + level-icon-option）。修订 AC-03 字段表 + 步骤：补 `color-input-{slot}` (3 picker × 1 input) + `level-icon-option-{icon}` 到字段表 + step (a)；AC-03 step (e) 改"click `level-icon-option-star`" 期望 store `data.metadata.design.level.icon === 'star'`。 |

**汇总**：15 接受 / 0 部分接受 / 0 驳回

**main-agent 决定**：跳过 dev round 2 文件修订直接锁定（US5/US6 precedent：429 Token Plan 风险 + L007 token 风险 + 节省 1 轮迭代）。15 修订已编码为 Phase 2 Implementation Spec 段。

## Phase 2 Implementation Spec (15 修订硬约束)

**锁定说明**：本节为 main-agent 裁判接受但 dev round 2 文件修订未完成的 15 条修订。Phase 2 实现必须严格按本节执行（不可自行扩展字段或 testid）。字段集与 testid 全部以 Pydantic schema + T058/T080 lock 契约为准。

### 范围决策（4 panel 而非 8 panel）

- **需实施**: Layout / Design / Notes / Information
- **已 ship (T107/T139/T140/T151)**: Sharing / Statistics / Analysis / Export（**不**重实施）
- **已 ship (032 实施)**: PagePanel / TypographyPanel（**不**重实施）
- **不要触碰** T058 + T080 lock 契约

### 验证模式统一（R1+R5 修订）

T058 + T080 lock 契约 = **props + onChange 模式**：
- 测试用法：`render(<LayoutPanel data={initial} onChange={onChange} />)` + `vi.fn((next) => { lastData = next })`
- 断言：`expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.{layout, design, notes}.X === Y)`
- **不**用 `useResumeV2Store.getState()` 验证（与 T058/T080 lock 互斥）
- 4 panel 实施必须用此模式（与 T058/T080 一致），才能让 T058/T080 测试编译过

### LayoutPanel testid 锁定契约（R3 修订）

T080 LayoutPanel.test.tsx:179 hard-code：
- `layout-fullwidth-{i}`（**全小写无连字符**，不是 `layout-full-width-{i}`）
- 其他 testid 沿用 T080 锁契约

### DesignPanel testid 锁定契约（R2+R15 修订）

T058 DesignPanel.test.tsx hard-code 5 testid：
- `color-picker-primary` / `color-picker-text` / `color-picker-background`（3 个 picker 容器）
- `color-input-{slot}`（**3 个** R15 补）— primary / text / background 各 1 input
- `level-type-select`（R2 锁，不是 `design-level-type`）
- `level-icon-search`（R2 锁）
- `level-icon-option-{icon}`（R15 补，例 `level-icon-option-star`）

### NotesPanel testid（R9+R14 修订放宽）

dev 自由发挥保留 `settings-notes-body` 旧 testid（与 T049 BuilderShell 兼容）或新 `notes-panel`/`notes-editor` 任一。**不强制**新 testid。dev report 必 cast 选择。

### InformationPanel testid（R11 修订）

InformationPanel 引用 `defaultResumeDataV2` 作 source of truth。testid 显示当前 store 实际值，不依赖 onChange 触发：
- `information-template` (text === defaultResumeDataV2.template)
- `information-sidebar-width` (text === defaultResumeDataV2.metadata.layout.sidebarWidth)
- `information-page-format` (text === defaultResumeDataV2.metadata.page.format)
- `information-typography-body-family` (text === defaultResumeDataV2.metadata.typography.body.fontFamily)
- `information-notes-length` (text === defaultResumeDataV2.metadata.notes.length)

### T049 引用位置（R4 修订）

AC-09 step (1) vitest 命令改：
```bash
npx vitest run src/modules/resume/v2/editor/__tests__/BuilderShell.test.tsx -t "clicking an accordion title toggles its fold/unfold state"
```
T049 实际位置 `BuilderShell.test.tsx:158-179`，**不**在 `SettingsPanel.test.tsx`（不存在）。

### named export 强制（R7 修订）

dev 必须把 LayoutPanel/DesignPanel 改为 named export：
```ts
// 当前 stub（编译失败）：
export default function LayoutPanel(): JSX.Element { ... }

// US7 实施（与 T080 lock 一致）：
export function LayoutPanel(props: { data: ResumeDataV2; onChange: (next: ResumeDataV2) => void }): JSX.Element { ... }
```

静态断言 `git grep -n "import { LayoutPanel }" src/modules/resume/v2/editor/right/__tests__/LayoutPanel.test.tsx` 期望 ≥ 1 hit（T080 lock 强制）。

### Pydantic schema 字段集

**LayoutPanel** (`metadata.layout`):
- `sidebarWidth: int = Field(ge=10, le=50)` （schemas.py:360+）
- `pages: list[Page] = Field(min_length=1, max_length=10)`
- `Page` 含 `PageLayout.{fullWidth: bool, main: int, sidebar: int}` + `Page.{format, margin, pageNumbers}`

**DesignPanel** (`metadata.design`):
- `colors: { primary: RgbaColorStr, text: RgbaColorStr, background: RgbaColorStr }`
- `level: { type: LevelType (7 值), icon: IconName }`
- `RgbaColorStr` regex `^rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*(0|1|0?\.\d+)\s*\)$` + `min_length=1, max_length=64`

**NotesPanel** (`metadata.notes`):
- `str = Field(default="", max_length=50000)`

**InformationPanel**:
- 只读 display，无 store mutation
- 引用 `defaultResumeDataV2` 显示当前默认值

### RgbaColorStr 范围检查（R8 修订）

Pydantic regex `\d{1,3}` 匹配 256 不 reject。frontend 必须**手动 range check**：
- 输入 `rgba(256, 0, 0, 0.5)` → 红框 + fireToast + 不写 store
- frontend range guard：`clamp(0, 255)` / `Math.max(0, Math.min(255, x))`
- 静态断言 `git grep -n "clamp\|Math.max.*255\|Math.min.*0" src/modules/resume/v2/editor/right/DesignPanel.tsx` 期望 ≥ 1 hit

### 空字符串拒绝（R10 修订）

`RgbaColorStr.min_length=1` 强约束。frontend input `''` → 红框 + fireToast + 不写 store（与 R8 一致）。

### LayoutPanel sidebarWidth clamp（R6 修订放宽）

T080 line 215-228 是 clamp-only 模式：
- 手输 `9` 或 `51` → 若 onChange 触发则值 clamp 到 [10, 50]
- **不**强制红框 / fireToast（与 T080 一致）

### useState 镜像范围（R12 修订放宽）

4 panel grep 范围：`panel-level field onChange 路径无 useState 镜像`
- dev 自由发挥用 useState for 非 field state（scroll 位置 / hover 状态 / accordion 折叠等）允许
- 仅约束 field onChange 路径必须直写 store

### SettingsPanel import 增量（R13 修订）

`git grep -n "import.*NotesPanel\|import.*InformationPanel" src/modules/resume/v2/editor/right/SettingsPanel.tsx` 期望 ≥ 1 hit each（US7 新增 2 import）
- 当前 2 hits (LayoutPanel + DesignPanel 已 ship) + US7 新增 2 hits = 4 hits

### 共享 sub-components 复用

- 4 panel 复用 US1-6 已 ship 的 sub-components
- LayoutPanel: FieldSlider / FieldCheckbox / FieldText / FieldSelect
- DesignPanel: FieldText (color input) / FieldSelect (level type) / IconPicker
- NotesPanel: FieldRTE (RichTextEditor) — 复用 US3 ship
- InformationPanel: 只读 display，无 sub-component

### tab 切换不触发 undo 循环（与 dialog 关闭循环 undo 区别）

- panel tab 切换是**导航行为**，**不**触发 undo 循环（与 dialog 关闭不同）
- store 修改仍走 setDataMut + undoStack +1
- tab 关闭（重新打开）保留 store 状态（不重置）

### L 教训复检

- L008: 4 panel 单一文件，无 shadowing
- L009: 4 panel 全部 named export（**禁止** `export default function X`）
- L011: panel-level field 直写 store (无 useState 镜像)

### 静态断言 checklist（US7 必跑）

| # | 检查 | 命令 | 期望 |
|---|------|------|------|
| 1 | 4 panel NO default return null | `git grep -n "default: return null" src/modules/resume/v2/editor/right/{Layout,Design,Notes,Information}Panel.tsx` | 0 |
| 2 | 4 panel NO stub TODO | `git grep -n "TODO\|FIXME" src/modules/resume/v2/editor/right/{Layout,Design,Notes,Information}Panel.tsx` | 0 (R7 修订后) |
| 3 | 4 panel named export | `git grep -n "export default function" src/modules/resume/v2/editor/right/{Layout,Design,Notes,Information}Panel.tsx` | 0 |
| 4 | SettingsPanel import 4 panel | `git grep -n "import.*LayoutPanel\|import.*DesignPanel\|import.*NotesPanel\|import.*InformationPanel" src/modules/resume/v2/editor/right/SettingsPanel.tsx` | 4 hits |
| 5 | LayoutPanel named import in T080 | `git grep -n "import { LayoutPanel }" src/modules/resume/v2/editor/right/__tests__/LayoutPanel.test.tsx` | ≥ 1 |
| 6 | DesignPanel named import in T058 | `git grep -n "import { DesignPanel }" src/modules/resume/v2/editor/right/__tests__/DesignPanel.test.tsx` | ≥ 1 |
| 7 | T049 BuilderShell testid lock | `git grep -n "clicking an accordion title" src/modules/resume/v2/editor/__tests__/BuilderShell.test.tsx` | ≥ 1 |
| 8 | DesignPanel frontend range guard | `git grep -n "clamp\|Math.max.*255\|Math.min.*0" src/modules/resume/v2/editor/right/DesignPanel.tsx` | ≥ 1 |
| 9 | InformationPanel defaultResumeDataV2 | `git grep -n "defaultResumeDataV2\|template" src/modules/resume/v2/editor/right/InformationPanel.tsx` | ≥ 1 |
| 10 | 4 panel useState 镜像 | `git grep -n "useState\|useReducer" src/modules/resume/v2/editor/right/{Layout,Design,Notes,Information}Panel.tsx` | dev 自由发挥（仅约束 field onChange 路径无 useState 镜像）|
- **R2 (blocker)** — AC-03 step (a)/(d)/(e) 期望 testid `design-level-type` / `design-level-icon`，但 T058 DesignPanel.test.tsx:102/131 **hard-code** `level-type-select` / `level-icon-search`。dev 按 AC 命名实施 → T058 全部 fail。**沿用 US5 R8 教训：lock 契约 testid 不可改**。

