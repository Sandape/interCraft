---
req_id: REQ-034-US3
title: Education + Project + Skill item dialogs (3 × shared SectionItem wrapper)
status: locked
round: 2
locked_at: 260629 1140
locked_by: negotiation
negotiation_rounds: 2
total_acs: 29
moderation_summary: "round1: 15 反例, 15 接受 / 0 部分接受 / 0 驳回; round2: 9 新增 (04c/05c/06c/07b/08b/09b/13b/17b/18b) + 14 行内修订"
moderation_log: "15 反例，15 接受 / 0 部分接受 / 0 驳回；Round 2 预计新增 6-8 AC + 7 修订，25-30 AC 锁定"
parent_spec: specs/034-v2-reactive-resume-parity/spec.md
source_gap: memory/req_032_v2_vs_reactive_resume_gap.md (Gap #4 Education / Project / Skill item dialogs)
---

# Acceptance Matrix for REQ-034-US3 — Education + Project + Skill item dialogs

## SC Gaps

- spec.md 行 32 给出 US3 标题 "Education + Project + Skill item dialogs (3 × shared SectionItem wrapper)"，但 spec §"Acceptance criteria" 段（行 64-66）整体写 TBD，未提供具体 SC 编号供 AC 反向溯源。下表来源以 "行 32 隐含" 标记。
- 隐含 SC（从 Bucket A row 3 + reactive-resume `dialogs/.../{education,project,skill}.tsx` 推导）：
  - SC-3A: 左栏 Sections 面板中 Education / Projects / Skills 3 个 section 行可展开，分别显示对应 items 列表 + add-button
  - SC-3B: 3 个 item dialog 共享同一 SectionItem 包装器（`SectionItemDialog<T>` 泛型 + 字段 schema props），差异在 props schema 而非组件本身
  - SC-3C: Education item dialog 字段覆盖 `EducationItem` 全部 7 个顶层键 + 1 个 `website{url,label,inlineLink}`：`id / hidden / school / degree / area / grade / location / period / description`（`period` free-form，含 startDate/endDate 时 dev 可拆为两个 input 共享验证函数）
  - SC-3D: Project item dialog 字段覆盖 `ProjectItem` 全部 5 个顶层键 + `website{...}`：`id / hidden / name / period / description`（reactive-resume 项目 item 字段集更窄）
  - SC-3E: Skill item dialog 字段覆盖 `SkillItem` 全部 6 个顶层键：`id / hidden / category(name) / level(number 0..5) / keywords[]`（level 范围约束 + NaN 拒绝）
  - SC-3F: Education `period` 与 US2 Experience `period` 同款 free-form 字符串；US3 在 dialog 内可拆为 `startDate` / `endDate` 两个 input 自由格式（"YYYY-MM" 或 "Present"），但落 store 时仍合并为 `period` 字段
  - SC-3G: Project `period` free-form 字符串（"2024-01 ~ Present" 风格），无 startDate/endDate 拆分
  - SC-3H: Skill `level` 数值 0..5 整数（reactive-resume 实际范围），失焦越界 clamp + NaN/Infinity 拒绝（沿用 US1 AC-06 扩展）
  - SC-3I: Education 包含 `courses: string[]`（可编辑 + 拖拽重排，reactive-resume Education dialog 同款）；Project 包含 `highlights: string[]`（项目亮点列表）；Skill 包含 `keywords: string[]`（技能关键词）
  - SC-3J: 3 个 dialog 共享 `SectionItem` list-row wrapper（dnd-kit item drag + 3 inline action: edit/duplicate/delete）
  - SC-3K: 所有写操作经 `useResumeV2Store.setDataMut`，触发 500ms debounce 自动保存，纳入 undoStack
  - SC-3L: dialog 关闭时 ESC + 点遮罩 + Cancel 三路一致；关闭时循环 undo 回到 S0（沿用 US2 AC-13 revised）
  - SC-3M: dialog 内禁止本地 draft state（沿用 US1 AC-08c + US2 AC-14 模式）
  - SC-3N: 项目 `website` 沿用 US2 AC-11 revised URL 白名单（`https?|tel|sms|mailto` + `u` flag + 黑名单 `javascript/vbscript/file/data`）

## AC 矩阵

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-01 | happy | 左栏 Sections 面板中 Education / Projects / Skills 3 个 section 行可展开（或点击 section 标题），分别显示各自 items 列表 + add-button；3 个 list-row 共享同一 `SectionItem` 包装器组件（R7 修订：spec "shared" 含义 = 3 个 SectionList 文件 `import { SectionItem }` 同一路径 + 共享 sub-components + 共享 list-row wrapper，**非** 1 个泛型 dialog 接 type props） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "renders three section lists with shared SectionItem wrapper from same import path"` 期望：(a) 渲染 `[data-testid="education-section-list"]` / `[data-testid="projects-section-list"]` / `[data-testid="skills-section-list"]` 三个容器节点；(b) 每个容器底部有 add-button `education-add-item` / `projects-add-item` / `skills-add-item`；(c) 列表中 item row testid `education-item-row-{id}` 等三组 prefix 存在；(d) `git grep -n "import.*SectionItem" src/modules/resume/v2/editor/left/EducationSectionList.tsx src/modules/resume/v2/editor/left/ProjectsSectionList.tsx src/modules/resume/v2/editor/left/SkillsSectionList.tsx` 期望 3 个文件引用同一路径（`../SectionItem` 或 `../shared/SectionItem`，dev 选定但必须 3 个 list 一致） | 3 个 list 容器 + add-button + 共享 SectionItem wrapper（同 import 路径） | SC-3A + SC-3J + R7 |
| AC-02 | happy | 3 个 add-button 触发 openDialog 对应 type：`'education.create'` / `'projects.create'` / `'skills.create'`；store 中追加空 item，schema 字段与 `data.ts:150-176` 对齐（education 9 字段 / project 5 字段 / skill 6 字段） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "add buttons dispatch correct dialog types and push empty items"` 期望：(a) fire click `education-add-item` → `useDialogStore.active.type === 'education.create'` 且 `data.sections.education.items.length +1`；新 item `school=''/degree=''/area=''/grade=''/location=''/period=''/description=''/website={url:'',label:'',inlineLink:false}`；(b) projects-create 与 skills-create 同款，字段集对应 ProjectItem / SkillItem | store 增加空 item + dialog 打开 | SC-3A + SC-3C + SC-3D + SC-3E |
| AC-03 | happy | 3 个 update dialog 打开后从 store 预填表单（每 input value === store.item 对应字段）；复用 `useItemWriter` 模式（沿用 US2 ExperienceDialog 实现） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "update prefills store state"` + `ProjectsDialog.test.tsx` + `SkillsDialog.test.tsx` 期望：seed education `school='Tsinghua', degree='Bachelor', area='CS', grade='3.8/4.0', location='北京', period='2018-09 ~ 2022-06', description='<p>foo</p>'` 后开 update dialog，断言 `[data-testid="education-school"].value === 'Tsinghua'` 等 8 字段全等；projects/skills 同款（3 字段 / 5 字段） | dialog 表单读 store 状态 | SC-3C + SC-3D + SC-3E |
| AC-04 | happy | Education dialog 字段覆盖 `EducationItem` 全部 9 个顶层键 + website：`school / degree / area / grade / location / period / website.url / website.label / website.inlineLink / hidden / description`；顶层字段编辑经 `setDataMut` 落 store 且 `undoStack` +1；input onChange handler 直接调 setDataMut（无 useState 镜像） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "renders all education top-level fields"` 期望（R12 修订）：(a) snapshot 包含 11 个 input testid（`education-school` / `education-degree` / `education-area` / `education-grade` / `education-location` / `education-period` / `education-website-url` / `education-website-label` / `education-website-inline-link` / `education-hidden` / `education-description`）；(b) 改 5 字段后 `data.sections.education.items[0].{school,degree,area,grade,location}` 全等新值且 `undoStack.length >= 5`；(c) 断言 onChange handler 直接调 setDataMut（无本地 useState 镜像） | education 字段齐全 + 直写 store + undoStack 累加 | SC-3C + SC-3K + R12 |
| AC-05 | happy | Project dialog 字段覆盖 `ProjectItem` 全部 5 个顶层键 + website：`name / period / website.url / website.label / website.inlineLink / hidden / description`；顶层字段编辑经 `setDataMut` 落 store 且 `undoStack` +1；input onChange handler 直接调 setDataMut（无 useState 镜像） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProjectsDialog.test.tsx -t "renders all project top-level fields"` 期望（R12 修订）：(a) snapshot 包含 7 个 input testid（`projects-name` / `projects-period` / `projects-website-url` / `projects-website-label` / `projects-website-inline-link` / `projects-hidden` / `projects-description`）；(b) 改 4 字段后 `data.sections.projects.items[0].{name,period,website.url,website.label}` 全等新值且 `undoStack.length >= 4`；(c) 断言 onChange handler 直接调 setDataMut（无本地 useState 镜像） | project 字段齐全 + 直写 store + undoStack 累加 | SC-3D + SC-3K + R12 |
| AC-06 | happy | Skill dialog 字段覆盖 `SkillItem` 全部 7 个顶层键：`hidden / icon / iconColor / name / proficiency / level / keywords`（R1 修订：`name` 独立字段非 `category` alias + 新增 `proficiency` 自由文本字段如 `Fluent`/`Native`）；`keywords[]` add/remove 沿用 US2 roles[] 模式；顶层字段编辑经 `setDataMut` 落 store 且 `undoStack` +1；input onChange handler 直接调 setDataMut（无 useState 镜像） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/SkillsDialog.test.tsx -t "renders all skill top-level fields with name proficiency level"` 期望：(a) snapshot 包含 6 个 input testid（`skills-icon` / `skills-name` / `skills-proficiency` / `skills-level` / `skills-keywords-add` + 容器 `skills-keywords`）+ 1 个 color picker `skills-icon-color` + 1 个 checkbox `skills-hidden`；(b) 改 5 字段后 `data.sections.skills.items[0].{icon,name,proficiency,level,keywords[0]}` 全等新值且 `undoStack.length >= 5`；(c) 断言 onChange handler 直接调 setDataMut（无本地 useState 镜像） | skill 7 字段齐全 + 直写 store + undoStack 累加 | SC-3E + SC-3I + SC-3K + R1 + R12 |
| AC-07 | happy | 3 个 `string[]` 字段管理（Education `courses` / Project `highlights` / Skill `keywords`）共享同一可重排模式：add 按钮追加新元素（空字符串）/ remove 按钮按 index 移除 / drag-reorder 走 dnd-kit（同 US2 roles[] 模式 + AC-08b 500ms 批处理） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "courses add remove drag-reorder from empty array and 3 element seed"` + `ProjectsDialog.test.tsx -t "highlights add remove drag-reorder from empty array and 3 element seed"` + `SkillsDialog.test.tsx -t "keywords add remove drag-reorder from empty array and 3 element seed"` 期望（R8 修订）：(a) seed `courses=[]`（空数组起点）→ click `education-add-course` → `courses.length === 1 && courses[0] === ''`；**OR** seed 3 courses `id=['c1','c2','c3']` → click add → `courses.length === 4` 且新元素 value === ''；(b) click first row `education-course-remove-c1` → `courses.length === 2` 且 `new Set(ids)` 不含 c1；(c) fire `education-test-reorder-c3-c1` hidden button → `courses.map(c=>c.id) === ['c3','c1','c2']` 且 id 集合不变 | add/remove/reorder 完整（含空数组起点） | SC-3I + R8 + US2 AC-08b 模式 |
| AC-08 | edge | `string[]` 字段的 drag-reorder 500ms 批处理合并为单帧 setDataMut（沿用 US2 AC-08b 模式 + REQ-033 第8轮 L 教训）：500ms 内连续 N 次 onDragEnd 合并为 1 帧 undoStack | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "courses drag batches within 500ms"` 期望：(a) seed 3 courses `id=['c1','c2','c3']` → `vi.advanceTimersByTime(500)` → fire 5 次 `education-test-reorder-*` → `undoStack.length === 1`（合并为单帧）；(b) `undoStack.at(-1).data.sections.education.items[0].courses.map(c=>c.id) === ['c1','c2','c3']`（拖拽前初始顺序）；(c) 单次 `undo()` 后 courses 顺序恢复拖拽前 | 500ms 批处理 + undo 完整恢复 | US2 AC-08b + L (REQ-033 拖拽批处理) |
| AC-09 | edge | `string[]` 字段 add/remove/drag-reorder 后 id 集合保持不变（drag 用 splice swap 不重建数组，沿用 US1 AC-04b + US2 AC-04b 模式） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/SkillsDialog.test.tsx -t "keywords reorder preserves ids"` 期望：seed 3 keywords `id=['k1','k2','k3']` → 模拟 onDragEnd `{active:'k3', over:'k1'}` → `keywords.map(k=>k.id) === ['k3','k1','k2']` 且 `new Set(ids) deep equal {'k1','k2','k3'}` | id 保留规则 | US1 AC-04b + US2 AC-04b |
| AC-10 | edge | Skill `level` 数值字段 0..5 范围约束：dialog 内 slider `min=0 max=5 step=1`（R3 修订：reactive-resume slider step=1 不可能产生小数）；非整数输入（number input '3.7'）显示红框、不写 store、fireToast "warn"；`level=0` 语义为 "Hidden"（与 reactive-resume `Number(field.state.value) === 0 ? 'Hidden' : '${value} / 5'` 一致，dialog 滑块下方显示 "Hidden" 标签）；`level=1..5` 显示 `"1 / 5".."5 / 5"` 标签；`level=0` 仍落 store（与 `hidden` 字段独立） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/SkillsDialog.test.tsx -t "level slider step 1 zero displays hidden label and 1 to 5 displays fraction"` 期望：(a) 拖 slider 至 level=0 → dialog 滑块下方 label 文本 === 'Hidden'（与 reactive-resume 一致）；(b) 拖 slider 至 level=3 → label 文本 === '3 / 5'；(c) level=0 仍落 store `data.sections.skills.items[0].level === 0`（与 hidden=true 独立，hidden checkbox 可独立切换）；(d) 模拟 number input 输入 '3.7' → 红框 + `fireToast('warn')` 且 `data.sections.skills.items[0].level === 初始值`（不写 store） | level slider step=1 + level=0 "Hidden" 语义 | SC-3H + R3 + US1 AC-06 + US2 AC-06 模式 |
| AC-11 | edge | Education `period` 自由格式：dialog 内**单** input（R2 修订：reactive-resume + schema 都用 free-form 字符串，dev 拆 startDate/endDate 是自行扩展；与 US2 Experience period + project period 一致）；placeholder "YYYY-MM ~ YYYY-MM"；无 YYYY-MM 强约束；空字符串合法 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "period free-form single input"` 期望：(a) snapshot 包含 `data-testid="education-period"` 单 input（**无** `education-period-start` / `education-period-end`）；(b) input '2018-09 ~ 2022-06' → `data.sections.education.items[0].period === '2018-09 ~ 2022-06'`；(c) input '2018-09 ~ Present' → period 保留原文 | education period 单 input | SC-3F + R2 + R11 + R14 |
| AC-12 | edge | Project `period` 自由格式：dialog 内单个 input（沿用 US2 Experience `period` 模式，**不**拆 start/end），placeholder "2024-01 ~ Present"；无 YYYY-MM 强约束 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProjectsDialog.test.tsx -t "period free-form single input"` 期望：(a) snapshot 包含 `data-testid="projects-period"` 单 input（**无** `projects-period-start` / `-end`）；(b) input '2024-01 ~ Present' → `data.sections.projects.items[0].period === '2024-01 ~ Present'` | project period 单 input | SC-3G + R11 |
| AC-13 | edge | URL 验证：Education + Project 2 个 dialog 共享 `validateUrl` 函数（沿用 US2 AC-11 revised 模式）：白名单 `^(https?|tel|sms|mailto):` + regex `u` flag，黑名单 `javascript|vbscript|file|data`；空字符串 url 视为合法 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "url scheme whitelist"` + `ProjectsDialog.test.tsx` 期望（R4 修订）：(a) **先断言 `[data-testid="education-website-url"]` / `[data-testid="projects-website-url"]` 存在后再 input URL**；(b) `https://[::1]:8080` / `tel:+86-010-1234` / `mailto:a@b.com` / `https://中文.cn` 接受（无红框 + 写 store）；(c) `javascript:alert(1)` / `data:text/html,...` / `file:///etc/passwd` 触发红框 + `fireToast('warn')` 且不写 store | URL 白名单 + unicode/IPv6 支持 | SC-3N + R4 + US2 AC-11 revised |
| AC-14 | error | XSS 注入：3 个 dialog 字段（education school/degree/area/grade/location/description、project name/description、skill category/keywords[]）注入 `<script>alert(1)</script>` / `<img src=x onerror=alert(1)>` / `javascript:` scheme 渲染时不触发 alert；description 走 RichTextEditor 不渲染 raw HTML 标签 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "xss payloads escaped"` + `ProjectsDialog.test.tsx` + `SkillsDialog.test.tsx` 期望：input payload 后断言渲染层 `[data-testid="education-school"]` 元素 `textContent === payload`（不出现 `<script>` 解析为 DOM 节点）；`window.__xssFired === false` | XSS 转义 | US1 AC-09 + US2 AC-12 模式扩展 |
| AC-15 | state | dialog 关闭（ESC / backdrop / Cancel）三路一致；DialogHost 在打开时记录 snapshot S0，关闭时若 setDataMut 已触发过则**循环 `undo()`** 直到 store 深等于 S0（沿用 US2 AC-13 revised） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "close loops undo to pre-dialog snapshot S0"` + `ProjectsDialog.test.tsx` + `SkillsDialog.test.tsx` 期望（R10 + R14 修订）：(a) 记录 S0 = `JSON.parse(JSON.stringify(useResumeV2Store.getState().data))`；(b) 改 3 字段 + add 1 string[] 元素 + reorder 1 次（5 帧保守估测，**不硬约束** keystroke 颗粒度）；(c) fire ESC；(d) 循环 `undo()` 直到 `useResumeV2Store.getState().data` 深等于 S0，记录调用次数 N；断言 `N >= 1 && data deep equal S0`（**删 N <= 9 硬约束**，AC 不约束 keystroke 节奏） | 循环 undo 到 S0（不约束 N 上限） | SC-3L + R10 + R14 + US2 AC-13 revised |
| AC-16 | state | dialog 内禁止本地 draft state（`useState` / `useReducer` 单独管理表单值再 onSave 一次性提交）；所有字段变更必须直接经 `setDataMut` 写入 `useResumeV2Store`（沿用 US1 AC-08c + US2 AC-14 模式） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "no local draft state, undo restores pre-dialog snapshot"` + `ProjectsDialog.test.tsx` + `SkillsDialog.test.tsx` 期望（R12 修订）：(a) `git grep -n "useState\|useReducer" src/modules/resume/v2/editor/dialogs/EducationDialog.tsx src/modules/resume/v2/editor/dialogs/ProjectsDialog.tsx src/modules/resume/v2/editor/dialogs/SkillsDialog.tsx` 期望 3 个文件全 grep，仅在 inline 红框错误状态（error display）出现，不在 field-level；(b) 改 3 字段 + add 1 course/highlight/keyword → close ESC → undo 1 → `data.sections.{education,projects,skills}.items[0]` deep equal 打开前 | 禁止本地 draft + undo 完整性 | SC-3M + R12 + US1 AC-08c + US2 AC-14 |
| AC-17 | edge | 3 个 SectionList 暴露 inline actions：edit / duplicate / delete；edit 触发 update dialog（`education.update` / `projects.update` / `skills.update`）；duplicate 走 setDataMut 在 items 末尾 push 深拷贝（id 全新 uuid，schema-specific 字段全 deep copy，**不打开** update dialog 沿用 US2 AC-10 revised）；delete 直接 setDataMut splice by id 且 `undoStack` +1 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "row inline actions edit duplicate delete for 3 sections"` 期望：(a) 每行 testid `education-item-edit-{id}` / `-duplicate-{id}` / `-delete-{id}` 等三组 prefix 存在；(b) click edit `e1` → dialog type=`education.update` payload.itemId===`e1`；(c) click duplicate `e1` → `data.sections.education.items.length +1` 且新 item `school deep equal 原 e1.school` 但 `id !== 'e1'`；(d) click delete `e1` → 长度 -1 且 undoStack +1；(e) **duplicate 后 `useDialogStore.getState().active === null`**（不打开 dialog） | 3 个 inline action 行为正确 | SC-3J + US2 AC-10 revised |
| AC-18 | happy | DialogHost dispatcher 扩展 6 个新 case：`'education.create' | 'education.update' | 'projects.create' | 'projects.update' | 'skills.create' | 'skills.update'`；switch 必须覆盖全部（fail loud：default throw Error，**不允许** `default: return null` 静默吞错，沿用 US2 AC-11b-revised + AC-11c）；`DialogType` union 同步扩展 6 case | (1) `git grep -n "openDialog\|DialogType" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 case 字符串集合 `{'basics', 'picture', 'experience.create', 'experience.update', 'education.create', 'education.update', 'projects.create', 'projects.update', 'skills.create', 'skills.update'}`；(2) `git grep -n "default: return null\|default: null" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 0 hits；(3) `npx vitest run src/modules/resume/v2/editor/dialogs/DialogHost.test.tsx -t "type namespace extended for education projects skills and unknown throws"` 期望：openDialog({type:'education.unknown'}) 后 `expect(() => DialogHost render).toThrow(/unknown dialog type/)` | dispatcher 6 case 扩展 + fail loud | US1 AC-11b + US2 AC-11b-revised + AC-11c + R5 |
| AC-19 | happy | 命名导出 + 共享 wrapper：`export function EducationDialog(props)` / `export function ProjectsDialog(props)` / `export function SkillsDialog(props)` + `export function SectionItem(props)` 共享 wrapper；consumer（DialogHost 内部 dispatcher + SectionList）通过 `import { EducationDialog } from "./EducationDialog"` 命名导入；R13 修订：`SectionItem` 路径显式约束为 `src/modules/resume/v2/editor/left/SectionItem.tsx`（与 SectionList 同目录）；`git grep -n "export default function EducationDialog\|export default function ProjectsDialog\|export default function SkillsDialog\|export default function SectionItem" src/modules/resume/v2/editor/` 0 hits；`ls src/modules/resume/v2/editor/dialogs/*.ts` 验证无 shadow（沿用 L008 必避陷阱） | 静态检查：(1) `git grep -n "export default function EducationDialog\|export default function ProjectsDialog\|export default function SkillsDialog\|export default function SectionItem" src/modules/resume/v2/editor/` 期望空输出；(2) `ls src/modules/resume/v2/editor/dialogs/*.ts` 期望空（仅 .tsx 存在，避 L008 shadow）；(3) `find src -name "SectionItem.tsx" | wc -l === 1` 唯一性断言（R13 新增）；(4) `git grep -l "import.*SectionItem" src/modules/resume/v2/editor/left/` 期望 ≥ 3 hits（education/projects/skills 3 list 文件均引用同路径 SectionItem） | 命名导出 + 无 shadow + SectionItem 路径唯一 | L008 + L009 必避陷阱 + R13 |
| AC-20 | happy | Backend round-trip：3 + 6 = 9 个 case `test_legacy_format.py`（R15 扩 6 子 case）：(a) `test_education_full_roundtrip` — PUT 一条 2 item education payload（含 courses[] + website{...}）→ GET 200 → 字段全 deep equal；(b) `test_project_full_roundtrip` — PUT 一条 2 item project payload（含 highlights[] + website{...}）→ GET 200 → 字段全 deep equal；(c) `test_skill_full_roundtrip` — PUT 一条 2 item skill payload（含 keywords[] + level=3）→ GET 200 → 字段全 deep equal；(d) `test_education_description_html_sanitized` — PUT `description='<p>foo</p><script>alert(1)</script>'` → GET 200 → response.data 不含 `<script>` 标签；(e) `test_project_description_html_sanitized` 同款 project；(f) `test_skill_level_zero_roundtrip` — PUT level=0 → GET 200 → level 仍为 0（schema `int = Field(ge=0, le=5)` 接受 0）；(g) `test_education_hidden_field_roundtrip` — PUT hidden=true → GET 200 → hidden 保留；(h) `test_project_highlights_empty_array_roundtrip` — PUT highlights=[] → GET 200 → highlights 不变 null；(i) `test_skill_keywords_empty_array_roundtrip` — PUT keywords=[] → GET 200 → keywords 不变 null | `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py -v -k "education_full_roundtrip or project_full_roundtrip or skill_full_roundtrip or _html_sanitized or _level_zero or _hidden_field or _empty_array_roundtrip"` 期望 pass（9 case） | round-trip 完整 + sanitized + 边界 | SC-3C + SC-3D + SC-3E + L005 教训 + R15 |
| AC-04c | edge | Education `hidden=true` 的 item 在 SectionList 渲染为视觉淡化行（`data-hidden="true"` 属性 + 文本节点保留，不从列表消失；与 US2 AC-12-revised 对齐） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "education hidden true renders as faded row not removed"` 期望：(a) seed `education.items=[{id:'e1', hidden:true, school:'X'}]` → 渲染列表 → row 节点存在 `querySelector('[data-testid="education-item-row-e1"]')` 不为 null；(b) 该 row 含 `data-hidden="true"` 属性（或 `aria-hidden="true"` / `style.opacity < 1` 三选一，dev 自定）；(c) `row.querySelector('[data-testid="education-school-display"]').textContent === 'X'`（仍渲染文本节点，非完全隐藏） | education hidden=true 视觉淡化 + 文本保留 | R6 + SC-3J + US2 AC-12-revised |
| AC-05c | edge | Project `hidden=true` 的 item 在 SectionList 渲染为视觉淡化行（`data-hidden="true"` + 文本节点保留） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "project hidden true renders as faded row not removed"` 期望：(a) seed `projects.items=[{id:'p1', hidden:true, name:'X'}]` → 渲染列表 → row 节点存在；(b) 该 row 含 `data-hidden="true"` 属性；(c) `row.querySelector('[data-testid="projects-name-display"]').textContent === 'X'` | project hidden=true 视觉淡化 + 文本保留 | R6 + SC-3J + US2 AC-12-revised |
| AC-06c | edge | Skill `hidden=true` 的 item 在 SectionList 渲染为视觉淡化行（`data-hidden="true"` + 文本节点保留） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "skill hidden true renders as faded row not removed"` 期望：(a) seed `skills.items=[{id:'s1', hidden:true, name:'X'}]` → 渲染列表 → row 节点存在；(b) 该 row 含 `data-hidden="true"` 属性；(c) `row.querySelector('[data-testid="skills-name-display"]').textContent === 'X'` | skill hidden=true 视觉淡化 + 文本保留 | R6 + SC-3J + US2 AC-12-revised |
| AC-07b | edge | 空数组边界：3 个 `string[]` 字段（Education `courses` / Project `highlights` / Skill `keywords`）在空数组起点的 add/remove/round-trip 行为完整 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "empty courses add remove roundtrip preserves empty string"` + `ProjectsDialog.test.tsx` + `SkillsDialog.test.tsx` 期望（R8 新增）：(a) seed `courses=[]` → click add → `courses.length === 1 && courses[0] === ''`（空字符串合法）；(b) `courses=['']` → click remove first → `courses.length === 0` 且 id 集合不变；(c) PUT payload 含 `courses=['']` → GET 200 → `courses === ['']`（空字符串 round-trip 完整，非变 null 或 422） | string[] 空数组 + 空字符串 round-trip | R8 + SC-3I |
| AC-08b | edge | 空数组 drag-reorder 批处理：3 个 `string[]` 字段空数组时 add 1 元素 + 5 次 500ms 内 drag 仍合并为单帧 undoStack | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "empty courses add then drag batches within 500ms"` + `ProjectsDialog.test.tsx` + `SkillsDialog.test.tsx` 期望（R8 新增）：(a) seed `courses=[]` → add 1 element `id='c1'` → `vi.advanceTimersByTime(500)` → fire 5 次 `education-test-reorder-*`（含 c1 与其他虚拟 id）→ `undoStack.length === 1`（合并为单帧） | 空数组后 drag 批处理 | R8 + US2 AC-08b |
| AC-09b | edge | 空数组 id 保留：3 个 `string[]` 字段在 add 1 元素后 drag 重排，id 集合保持不变 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/SkillsDialog.test.tsx -t "single keyword add then reorder preserves id"` 期望（R8 新增）：seed `keywords=[]` → add 1 element `id='k1'` → 模拟 onDragEnd `{active:'k1', over:'k1'}`（no-op）→ `keywords.map(k=>k.id) === ['k1']` 且 id 集合不变 | 单元素 id 保留 | R8 + US1 AC-04b |
| AC-13b | edge | Skill dialog 不含 website 字段（与 US2 Experience + US3 Project/Education 差异）：静态检查 `git grep "skills-website" src/` 0 hits；SkillItem schema 无 website 顶层键 | `git grep -n "skills-website" src/` 期望 0 hits；`cat backend/app/modules/resumes_v2/schemas.py | grep -A 12 "class SkillItem"` 期望无 `website` 字段；`npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/SkillsDialog.test.tsx -t "skills dialog has no website input"` 期望：snapshot 不含 `skills-website-url` / `skills-website-label` / `skills-website-inline-link` | Skill 无 website 字段 | R4 |
| AC-17b | edge | 跨 section 拖拽隔离：3 个 SectionList（education/projects/skills）的 items drag 通过 `data-dnd-context="education"|"projects"|"skills"` 命名空间隔离；onDragEnd 内 `over.data.current.droppableContainer.dataset.dndContext !== 当前 section` 短路不触发 items 顺序更新（沿用 US2 AC-09b 模式） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "items drag short-circuits when over context is other section"` 期望（R9 新增）：(a) seed education items `id=['e1','e2']` + projects items `id=['p1','p2']`；(b) 模拟 onDragEnd `over={id:'p1', data:{current:{droppableContainer:{dataset:{dndContext:'projects'}}}}}`（active 在 education）→ education items 顺序未变 `=== ['e1','e2']`；(c) 模拟 onDragEnd `over.dataset.dndContext === 'education'` → 正常重排 `['e2','e1']` | 跨 section drag 隔离 | R9 + US2 AC-09b |
| AC-18b | happy | DialogHost dispatcher 共享 helper（dev 自决可维护性 vs 命名空间清晰）：dispatcher 可走共享 helper（如 `case 'education.create': case 'education.update': return <EducationDialog mode={...} />` 同 case 体共享同一组件）或显式 6 case 二选一；US3 接受路径分歧 | `git grep -n "case 'education\|case 'projects\|case 'skills" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望（R5 新增）：(a) 走共享 helper 模式时 ≥ 3 hits（每 section 1 个 case 包含 create/update）；(b) 走显式 6 case 模式时 ≥ 6 hits（每 verb 1 case）；(c) 不论哪种模式，`fallback`/default 必须 throw Error 不静默吞错（沿用 AC-18 约束） | dispatcher 共享 helper 或显式 6 case | R5 |

## Tester 反驳日志

### R1: [AC-06] Skill `name` 字段被遗漏 — AC-06 写 `category(name)` 但 reactive-resume 与 Pydantic schema 都是独立 `name` 字段
- **目标 AC**: AC-06
- **反驳类型**: 覆盖缺失 / 矛盾
- **反例描述**: `backend/app/modules/resumes_v2/schemas.py` 行 208 定义 `SkillItem.name: str`（独立字段，非 category 的 alias）；reactive-resume `dialogs/resume/sections/skill.tsx` 行 41 用 `name` 字段 + `proficiency` 字段 + `level` 数值滑块 + `keywords` 列表。AC-06 描述写"字段覆盖 `SkillItem` 全部 6 个顶层键：`category(name) / level(number) / keywords[]` + `icon` / `iconColor`" — 但 `SkillItem` 实际 7 个顶层键（`hidden / icon / iconColor / name / proficiency / level / keywords`），AC-06 把 `name` 误标为 `category` 的 alias，把 `proficiency` 字段（用户填 `Fluent`/`Native` 自由文本）整个遗漏
- **影响**: blocker
- **验证命令**: `git grep -n "proficiency" src/modules/resume/v2/editor/dialogs/SkillsDialog.tsx`（应 ≥ 1 hit）；`cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py -k "skill_full_roundtrip" -v` PUT payload 缺 `proficiency` 字段将 Pydantic 422 拒收
- **建议**: 修订 AC-06：(a) 改 `category(name)` 为 `name`（独立字段）；(b) 新增 `proficiency` 字段 testid `skills-proficiency`；(c) snapshot 应包含 6 个 input testid（`skills-icon` / `skills-name` / `skills-proficiency` / `skills-level` / `skills-keywords-add` + 容器 `skills-keywords`） + 1 个 `skills-icon-color` color picker + 1 个 `skills-hidden` checkbox

### R2: [AC-11] Education `period` 拆 startDate/endDate 是 dev 自行扩展 — reactive-resume 与 schema 都用 free-form 字符串
- **目标 AC**: AC-11
- **反驳类型**: 矛盾 / 覆盖缺失
- **反例描述**: reactive-resume `dialogs/resume/sections/education.tsx` 行 164 `period` 走 `field.TextField`（**单** TextField free-form 字符串，与 US2 Experience period 同款）；`backend/app/modules/resumes_v2/schemas.py` 行 193 `period: str`（free-form 字符串 schema）。AC-11 写"dialog 内拆为 `startDate` / `endDate` 两个 input" — **reactive-resume 未拆，schema 也无 startDate/endDate 字段**。该拆分是 dev 自行扩展，与 spec "3 × shared SectionItem wrapper" 隐含的"沿用 reactive-resume 行为"矛盾
- **影响**: blocker
- **验证命令**: 对照 `D:/Project/reactive-resume/apps/web/src/dialogs/resume/sections/education.tsx` 行 164（单 TextField）+ `backend/app/modules/resumes_v2/schemas.py` 行 193（无 startDate/endDate 字段）；`git grep -n "startDate\|endDate" backend/app/modules/resumes_v2/schemas.py` 期望 0 hits
- **建议**: 修订 AC-11：dialog 内 `period` 走**单** input（与 reactive-resume 一致 + 与 US2 Experience period 同款 + 与 project period 同款），testid `education-period`；保留自由格式 + "YYYY-MM" 占位提示但不做结构性拆分。删 `education-period-start` / `education-period-end` testid 断言

### R3: [AC-10] Skill `level` 0..5 范围 + 0 语义为 "Hidden" 未约束 — rounding 3.7→3 或 4 模糊
- **目标 AC**: AC-10
- **反驳类型**: 模糊 / 覆盖缺失
- **反例描述**: reactive-resume `dialogs/resume/sections/skill.tsx` 行 244 `Slider min={0} max={5} step={1}`（**滑块 step=1 整数，无小数**）+ 行 255 `Number(field.state.value) === 0 ? t\`Hidden\` : \`${field.state.value} / 5\``（`level=0` 语义为 "Hidden"，level=1..5 显示 `1/5..5/5`）。AC-10 写"level=7 → 5, level=-3 → 0, level=3.7 → 3（截断）或 4（向上舍入，dev 自定但需确定）" — `3.7` 在 reactive-resume 不可能产生（滑块 step=1），AC-10 留 rounding 模糊；**更关键**：未约束 `level=0` 的 "Hidden" 语义（用户 level 滑到 0 时 v2 是否在 dialog 与预览同步显示 "Hidden" label），与 US1 PictureConfig `hidden` 字段独立（level=0 隐藏 vs hidden=true 隐藏是两路）
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/SkillsDialog.test.tsx -t "level 0 displays hidden label and level 1..5 displays fraction"` 期望：(a) level=0 → dialog 显示 "Hidden" label；level=3 → 显示 "3 / 5"；(b) input level='3.7'（模拟 dev 误用 number input 而非滑块）→ 红框 + 拒绝（不写 store）；(c) `data.sections.skills.items[0].level === 0` 仍落 store（与 hidden 独立）
- **建议**: 修订 AC-10：(a) 删 `3.7 → 3 或 4` 模糊（slider step=1 不存在小数）；(b) 改 input 为 number input 仍接受整数；非整数 `fireToast('warn')` + 红框 + 不写 store；(c) 新增 `level=0` 语义：dialog 滑块下方显示 "Hidden" 文案（与 reactive-resume 一致）

### R4: [AC-04] Education `website` 字段 count 与 testid 断言不一致 — 11 inputs 包含 website 3 个 sub-input 但 AC-13 URL 验证未显式覆盖 education.website
- **目标 AC**: AC-04 + AC-13
- **反驳类型**: 矛盾 / 覆盖缺失
- **反例描述**: AC-04 写"snapshot 包含 11 个 input testid（... `education-website-url` / `education-website-label` / `education-website-inline-link` ...）"，但 AC-13 验证 URL 白名单的测试名只列 `EducationDialog.test.tsx -t "url scheme whitelist"` + `ProjectsDialog.test.tsx` + `SkillsDialog.test.tsx`（**注：Skill 没有 website 字段，AC-13 三 case 必有一个假命中**）；更关键：AC-13 步骤 (a) 期望 `https://中文.cn` 接受，但 `education-website-url` 缺 testid 显式断言，dev 若漏写 education website 字段而 AC-04 snapshot 通过（`data-testid` 可被空 div 蒙混），AC-13 测试会因找不到 input 而 silently pass
- **影响**: blocker
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "url scheme whitelist"`（断言 `[data-testid="education-website-url"]` 存在后再 input）；同时验证 Skill dialog 无 website testid（`git grep -n "skills-website" src/modules/resume/v2/editor/dialogs/SkillsDialog.tsx` 期望 0 hits）
- **建议**: 修订 AC-13：步骤 (a) 增加 "断言 `education-website-url` / `projects-website-url` 存在后 input URL"；新增 AC-13b 显式声明 "Skill dialog 不含 website 字段" + 静态检查 `git grep "skills-website" src/` 0 hits；AC-04 的 11 个 testid 清单明确标注 website 3 个 sub-input

### R5: [AC-18] DialogHost dispatcher 6 case 累加至 10 case — 重复 case 体（create vs update）应重构为共享 helper
- **目标 AC**: AC-18
- **反驳类型**: 不可执行 / 矛盾
- **反例描述**: AC-18 写"DialogHost dispatcher 扩展 6 个新 case：`'education.create' | 'education.update' | 'projects.create' | 'projects.update' | 'skills.create' | 'skills.update'`"。US1（2 case）+ US2（2 case）+ US3（6 case）= 10 case 在 switch 中；US5 还要加 14 case，US6 加 2 case，最终 DialogHost switch 将达 26 case，**每对 create/update 体内容 99% 相同**（仅 component 不同）。AC-18 把"6 case 显式列出"当作架构优点（"命名空间一致"），但重复 case 体是 dev 走"3 dialog 共享 wrapper"的最大动机 — 若 dev 走 6 case 显式，未来加 4 case 改 8 处而非 1 处 helper
- **影响**: major
- **验证命令**: `wc -l src/modules/resume/v2/editor/dialogs/DialogHost.tsx`（预期 > 80 行，10 case 体）；`git grep -c "case 'education\|case 'projects\|case 'skills" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 ≥ 6 hits
- **建议**: 修订 AC-18：dispatcher 走 `case 'education.create': return <EducationDialog mode="create" .../>` + `case 'education.update': return <EducationDialog mode="update" .../>` 共享同一组件但 mode 不同；或更优：6 case 合并为 `'education.*' | 'projects.*' | 'skills.*'` 通用匹配 + 内部分发（沿用 US2 的 `{section}.{verb}` 命名空间但 switch 用 regex/分支）；US3 AC 矩阵应明示 dev 可走"3 dialog + 6 case"或"3 dialog + 3 section helper"路径二选一

### R6: [AC-06 + AC-04 + AC-05] `hidden` 字段 checkbox 视觉表现未约束 — 与 US2 AC-12-revised 模式不对齐
- **目标 AC**: AC-04 + AC-05 + AC-06
- **反驳类型**: 覆盖缺失（US2 教训未对齐）
- **反例描述**: US2 AC-12-revised 已锁：`hidden=true` 行渲染为视觉淡化（删除线/灰显）；但 US3 AC-04/05/06 仅断言 snapshot 含 `education-hidden` / `projects-hidden` / `skills-hidden` checkbox，**未约束** dialog 关闭后 list-row 渲染的视觉表现（删除线 vs 隐藏 vs 灰显）。若 dev 实现"hidden=true 时该 row 从列表消失"，与 US2 AC-12-revised "视觉淡化但文本节点仍转义" 矛盾；若 dev 实现"hidden=true 时行完全不渲染"，与 reactive-resume 原版（行保留可恢复）不符
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "hidden true renders as faded row not removed"` 期望：(a) seed `education.items=[{hidden:true, school:'X'}]` → 渲染列表 → row 节点存在但含 `data-hidden="true"` 或 `aria-hidden="true"` 或 `style.opacity < 1`；(b) `row.querySelector('[data-testid="education-school-display"]').textContent === 'X'`（仍渲染文本）
- **建议**: 新增 AC-04c/05c/06c：`hidden=true` 的 item 在 SectionList 渲染为视觉淡化行（`data-hidden="true"` 属性 + 文本节点保留），与 US2 AC-12-revised 对齐；与 US1 AC-02b 模式一致（hidden 字段双向：dialog 内 checkbox + list row 视觉）

### R7: [AC-01] `SectionItem` 共享 wrapper 含义边界 — dev 接受"3 dialog 各自独立 + 内部 sub-components 共享" 与 AC-01 措辞矛盾
- **目标 AC**: AC-01 + AC-19
- **反驳类型**: 矛盾 / 模糊
- **反例描述**: spec 行 32 标题写"3 × shared SectionItem wrapper"，含义模糊：(a) "1 个泛型 SectionItem 组件接 sectionId prop 内部 if/else 渲染"，还是 (b) "3 个独立 dialog + 内部 sub-components 共享"？起草说明行 91 自承"本 AC 矩阵接受'外层 dialog 各自独立 + 内部 sub-components 共享'模式" 与 spec 措辞"3 × shared SectionItem wrapper" 矛盾。AC-01 验证步骤 (d) `git grep -n "function SectionItem\|export.*SectionItem"` 期望至少 1 个 SectionItem 组件被 3 个 SectionList 引用 — 但 dev 若实现"3 个 SectionList 各自硬编码 row JSX" 也满足此要求（每个 list 文件内定义自己的 local SectionItem，不共享），AC-01 (d) 验证过弱
- **影响**: major
- **验证命令**: `git grep -n "import.*SectionItem" src/modules/resume/v2/editor/left/EducationSectionList.tsx src/modules/resume/v2/editor/left/ProjectsSectionList.tsx src/modules/resume/v2/editor/left/SkillsSectionList.tsx` 期望 3 个文件均引用同一 `SectionItem` 路径（如 `../shared/SectionItem`）
- **建议**: 修订 AC-01：明确"3 个 SectionList 共享同一 SectionItem 组件" = 静态检查 3 个 list 文件 `import { SectionItem }` 同一路径；AC-19 增补 SectionItem 命名导出 + 3 list 引用同一路径（避 L008 shadow）；起草说明显式说明 "spec 措辞 shared = 共享 sub-components + 共享 list-row wrapper，非 1 个泛型 dialog"

### R8: [AC-07 + AC-08 + AC-09] string[] 字段 (courses/highlights/keywords) 缺空数组边界 — 3 section × 1 string[] = 3 处
- **目标 AC**: AC-07 + AC-08 + AC-09
- **反驳类型**: 边界 / 覆盖缺失
- **反例描述**: AC-07 步骤 (a) seed 3 courses 后 click `education-add-course` → `courses.length === 4` 且新元素 value === ''（接受空字符串合法）。但缺**纯空数组起点**的边界：seed `courses=[]`（新 item 默认）→ click add-course 1 次 → `courses.length === 1` 且 `courses[0] === ''`；以及**全空 + 移除**：`courses=['']` → click remove → `courses.length === 0`；以及**空字符串 vs undefined**：`courses=[undefined]` PUT 后 Pydantic schema `list[str]` 422。reactive-resume ChipInput 接受空字符串为合法元素（用户填一半可保存）
- **影响**: minor
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "empty courses add remove roundtrip"` 期望：(a) seed `courses=[]` → add → `courses.length === 1 && courses[0] === ''`；(b) `courses=['']` → remove first → `courses.length === 0` 且 id 集合不变；(c) PUT payload 含 `courses=['']` → GET 200 → `courses === ['']`（空字符串 round-trip 完整，非变 null）
- **建议**: 修订 AC-07：步骤 (a) 增加 "seed 0 courses（空数组起点）" path；新增 AC-07b 覆盖"空数组 add/remove 边界 + 空字符串 round-trip" 三 section 各 1 case

### R9: [AC-18] US2 AC-09b 跨 section 拖拽隔离模式未对齐 — 3 个 SectionList items 之间的 drag 跨 section 隔离未约束
- **目标 AC**: AC-17 + AC-18（间接）
- **反驳类型**: 覆盖缺失（US2 教训未对齐）
- **反例描述**: US2 AC-09b 已锁："LayoutPanel column drag 与 ExperienceSectionList item drag 通过 `data-dnd-context` 分属两个 DndContext 命名空间隔离"。US3 涉及 3 个 SectionList（education/projects/skills），若 dev 用全局 DndContext 包裹整个 SectionsPanel，3 个 section 的 items drag handle 共享同一 onDragEnd callback — 用户从 education 拖 item 到 projects 容器时 collision 检测是否短路？AC-17 仅断言"每行 testid 存在 + edit/duplicate/delete 行为正确"，**未约束** items drag-reorder 跨 section 隔离（沿用 US2 AC-09b 模式）
- **影响**: blocker
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "items drag short-circuits when over context is other section"` 期望：(a) seed education items=['e1','e2'] + projects items=['p1','p2']；(b) 模拟 onDragEnd `over={id:'p1', data:{current:{droppableContainer:{dataset:{dndContext:'projects'}}}}}` → education items 顺序未变；(c) 模拟 onDragEnd `over.dataset.dndContext === 'education'` → 正常重排
- **建议**: 新增 AC-17b（沿用 US2 AC-09b 模式）：3 个 SectionList 的 items drag 通过 `data-dnd-context="education"|"projects"|"skills"` 分属独立 DndContext 命名空间；onDragEnd 内 `over.data.current.droppableContainer.dataset.dndContext !== 当前 section` 短路不触发 items 顺序更新

### R10: [AC-15] dialog 关闭循环 undo 到 S0 — 3 dialog 共享验证但 Education `period` 拆 startDate/endDate 后合成 `period` 字符串触发 setDataMut 次数未约束
- **目标 AC**: AC-15
- **反驳类型**: 不可执行 / 矛盾
- **反例描述**: AC-15 步骤 (b) 改 5 字段 + add 3 course/highlight/keyword + reorder 1 次（9 帧）。但若按 R2 修订采用 Education `period` 自由格式单 input（与 reactive-resume 一致），用户连续输入 start='2018-09' + '2018-10' + '2018-11' 触发 3 次 setDataMut（每个字符 keystroke 都写），远多于 5 字段预期；AC-15 步骤 (b) 的 "9 帧" 是 dev 自由发挥输入节奏的估测，实际 9 帧可能变 15+ 帧（每 keystroke 一帧），循环 undo N 次可能 > 9。AC-15 步骤 (d) 断言 `N >= 1 && N <= 9` 实际可能不成立
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/EducationDialog.test.tsx -t "close loops undo to pre-dialog snapshot S0"` 期望：(a) 模拟 dev 行为：fill school='清华' (3 keystroke) + period='2018' (4 keystroke) + description='<p>foo</p>' (11 keystroke) + add 3 courses；(b) fire ESC；(c) 循环 undo 直到 S0，记录 N；(d) 断言 N >= 1（关键是不为 0），不硬约束 N <= 9
- **建议**: 修订 AC-15：步骤 (d) 删 `N <= 9` 硬约束（用户 keystroke 节奏不可预测），改 `N >= 1 && data deep equal S0`（关键是最终回到 S0，N 是 dev 自由发挥）；新增注释 "AC 不约束 keystroke 颗粒度"；可考虑 setDataMut 内部加 200ms debounce 合并 keystroke 帧（dev 自由发挥）

### R11: [AC-12] project `period` 单 input vs Education `period` 拆 start/end 的不一致 — 3 dialog 共享体验受影响
- **目标 AC**: AC-11 + AC-12
- **反驳类型**: 矛盾 / 不可执行
- **反例描述**: AC-12 约束 project `period` 走单 input（与 US2 Experience period 同款），AC-11 约束 Education `period` 拆 start/end 两个 input（reactive-resume 未拆，dev 自行扩展）。3 个 dialog 共享 sub-components 时，Education period 走 `<FieldPeriod mode="split" />` 而 Project period 走 `<FieldPeriod mode="single" />` 模式分支，sub-component 共享反而难；若 dev 走 R2 修订（Education period 改单 input），3 个 dialog 完全一致体验
- **影响**: major
- **验证命令**: 实施后 `git grep -n "FieldPeriod\|FieldPeriodSplit" src/modules/resume/v2/editor/dialogs/` 期望 dev 实现路径
- **建议**: 接受 R2 修订后 AC-11（Education period 改单 input），AC-11 与 AC-12 完全一致：3 个 dialog 共享同一 `<FieldPeriod>` 单 input sub-component；reactive-resume 原版行为 100% 对齐；spec 措辞"3 × shared SectionItem wrapper" → 共享 sub-components 真正落地

### R12: [AC-04 + AC-05] field-level 直写 vs useState 镜像 — US2 AC-14 (no local draft state) 模式未在 US3 显式 cast
- **目标 AC**: AC-04 + AC-05 + AC-06 + AC-16
- **反驳类型**: 覆盖缺失（US2 教训未对齐）
- **反例描述**: US2 AC-14 已锁："dialog 内禁止本地 draft state（`useState` / `useReducer` 单独管理表单值再 onSave 一次性提交）；所有字段变更必须直接经 `setDataMut` 写入 `useResumeV2Store`"。US3 AC-16 复述同款约束但 AC-04/05/06 字段映射表未显式 cast "field-level 写 store 路径 = onChange 直接调 setDataMut"。dev 若实现"input onChange → setLocalFormState(...) → onBlur 时一次性 setDataMut"（debounce 模式），US2 AC-14 模式违反
- **影响**: major
- **验证命令**: `git grep -n "useState" src/modules/resume/v2/editor/dialogs/EducationDialog.tsx src/modules/resume/v2/editor/dialogs/ProjectsDialog.tsx src/modules/resume/v2/editor/dialogs/SkillsDialog.tsx` 期望仅在 error display（红框 inline state）出现；每个 input onChange handler 必须直接调 setDataMut 而非 setLocal + debounce
- **建议**: 修订 AC-04/05/06：每个 input 的 "验证步骤" 增加一行 "断言 input onChange handler 直接调 setDataMut（无本地 useState 镜像）"；AC-16 步骤 (a) 扩展为 3 个 dialog 文件全 grep

### R13: [AC-19] `SectionItem` 命名导出 + 无 shadow + US2 AC-12b 模式对齐 — 但 `SectionItem` 路径未明
- **目标 AC**: AC-19
- **反驳类型**: 不可执行 / 模糊
- **反驳类型补充**: 反例描述
- **反例描述**: AC-19 步骤 (1) grep 验证无 `export default function SectionItem`；但 `SectionItem` 组件应放哪个文件未约束（沿用 US2 AC-12b 模式：dialogs/SectionItem.tsx？left/SectionItem.tsx？shared/SectionItem.tsx？）。dev 可能：(a) 放 `src/modules/resume/v2/editor/left/SectionItem.tsx`（与 SectionList 同目录）；(b) 放 `src/modules/resume/v2/editor/shared/SectionItem.tsx`；(c) 放 `src/modules/resume/v2/editor/dialogs/SectionItem.tsx`（与 Dialog 同目录）。3 种路径都满足 AC-19 grep 0 hits + 命名导出，但**未来 US4-US6 的 7 个 SectionList 都要引用此 SectionItem**，路径不一致会导致 dev 在 US5 阶段又改路径
- **影响**: minor
- **验证命令**: 实施后 `find src/modules/resume/v2/editor -name "SectionItem.tsx"` 应有唯 1 个文件；`git grep -l "import.*SectionItem" src/modules/resume/v2/editor/left/` 期望 3 hits（education/projects/skills SectionList）
- **建议**: 修订 AC-19：显式约束 `SectionItem` 路径 = `src/modules/resume/v2/editor/left/SectionItem.tsx`（与 SectionList 同目录，最自然）；US4-US6 7 个 SectionList 沿用同路径；AC-19 步骤 (3) 增加 `find src -name "SectionItem.tsx" | wc -l === 1` 唯一性断言

### R14: [AC-15] dialog 关闭循环 undo 到 S0 — Education `period` 拆 start/end 时合成 `period` 字符串导致 setDataMut 次数与 AC-15 预期不匹配
- **目标 AC**: AC-15（与 R10 重叠但不同角度）
- **反驳类型**: 矛盾
- **反例描述**: 若保留 AC-11 的 Education `period` 拆 start/end 模式：用户输入 start='2018' (4 keystroke) + end='2022' (4 keystroke) → 每次 keystroke 触发 startDate setDataMut + 失焦时合成 period 触发另一次 setDataMut → 实际帧数 = 4 + 4 + 1 = 9 帧（仅 period 字段）。若 dev 错误实现"start/end 任一变更即 setDataMut + 合成 period 同步 setDataMut" = 每 keystroke 触发 2 帧（startDate + period 同步）→ 实际 16 帧；AC-15 步骤 (b) 改 5 字段 + add 3 + reorder 1 = 9 帧是 AC 起草时估测，与实际 keystroke 节奏严重不匹配
- **影响**: major
- **验证命令**: 模拟 dev 实际 keystroke 节奏后断言 undoStack 长度；若 > 9 步，AC-15 步骤 (d) `N <= 9` 必失败
- **建议**: 与 R2 + R10 + R11 联动：接受 Education `period` 改单 input（与 reactive-resume 一致），3 dialog 体验一致 + 帧数可预测；AC-15 步骤 (b) 改 "改 3 字段 + add 1 string[] 元素 + reorder 1 次"（5 帧保守估测，步数小更稳）；AC-15 步骤 (d) 删 `N <= 9` 硬约束

### R15: [AC-20] Backend round-trip 3 case 缺 v2 Pydantic 实际字段一致性验证 — `description` HTML sanitized 路径未覆盖
- **目标 AC**: AC-20
- **反驳类型**: 覆盖缺失（US2 AC-15-revised 教训未对齐）
- **反例描述**: US2 AC-15-revised 已锁："PUT `description='<p>foo</p><script>alert(1)</script>'` → GET 200 → response.data 不含 `<script>` 标签（bleach/dompurify 净化后仅保留 `<p>foo</p>`）"。US3 AC-20 仅断言"PUT 一条 2 item payload → GET 200 → 字段全 deep equal"（含 courses[] / highlights[] / keywords[] + website{...} + level=3），**未约束**：(a) `description='<p>foo</p><script>alert(1)</script>'` 在 3 dialog 各自的 round-trip sanitized 行为；(b) `hidden=true` 字段保留；(c) `level=0` 边界（schema `int = Field(ge=0, le=5)` 接受 0，round-trip 后保留）；(d) 空 courses/highlights/keywords array round-trip 不变 null
- **影响**: major
- **验证命令**: `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py -k "education_full_roundtrip or project_full_roundtrip or skill_full_roundtrip" -v` 后扩 6 子 case：(a) `test_education_description_html_sanitized`；(b) `test_project_description_html_sanitized`；(c) `test_skill_level_zero_roundtrip`（level=0 保留）；(d) `test_education_hidden_field_roundtrip`；(e) `test_project_highlights_empty_array_roundtrip`；(f) `test_skill_keywords_empty_array_roundtrip`
- **建议**: 修订 AC-20：扩 6 子 case 覆盖 description sanitized × 2 section（education/project；skill 无 description 字段跳过）+ hidden × 1 + level 边界 × 1 + 空数组 × 2；与 US2 AC-15-revised 对齐

### Red-team 汇总：15 / blocker=5 / major=9 / minor=1

最严重的 3 条反例：
- **R1 (blocker)** — Skill `proficiency` 字段 + `name` vs `category` 误标，整个 Skill 字段映射不完整
- **R2 (blocker)** — Education `period` 拆 startDate/endDate 是 dev 自行扩展，违反 reactive-resume + schema 实际定义
- **R4 (blocker)** — AC-04 列 11 testid 含 education website 但 AC-13 URL 验证步骤缺 testid 存在性断言，Skill 无 website 字段但 AC-13 仍三 case 必假命中 1

## Moderation Log (main-agent 裁判)

| 反例 | 判定 | 理由 |
|------|------|------|
| R1 [AC-06] | **接受** | blocker 命中：Skill schema 实际 7 字段（`hidden / icon / iconColor / name / proficiency / level / keywords`），AC-06 漏 `proficiency` + 误标 `name` 为 `category` alias。修订 AC-06：补 `proficiency` + 改 `name` 独立 + 6 input testid 清单。 |
| R2 [AC-11] | **接受** | blocker 命中：reactive-resume + Pydantic schema 都用 free-form `period` 单 input；Education 拆 startDate/endDate 是 dev 自行扩展，违反"沿用 reactive-resume 行为"。修订 AC-11 改单 input + testid `education-period`。 |
| R3 [AC-10] | **接受** | major 命中：reactive-resume slider step=1 不可能产生小数；`level=0` 语义为 "Hidden" 未约束。修订 AC-10：删 `3.7` 模糊 + 改 number input 仍接受整数 + 新增 `level=0` 显示 "Hidden" label。 |
| R4 [AC-04/13] | **接受** | blocker 命中：AC-13 三 case 中 Skill 无 website 必假命中 1。修订 AC-13 步骤 (a) 显式断言 education/projects website-url 存在；新增 AC-13b 显式声明 Skill dialog 不含 website 字段。 |
| R5 [AC-18] | **接受** | major 命中：10 case 累加后每对 create/update 体 99% 重复。修订 AC-18：dev 走"3 dialog + 6 case"或"3 dialog + 3 section helper"二选一；AC-18b 显式允许路径分歧（dev 自决可维护性 vs 命名空间清晰）。 |
| R6 [AC-04/05/06] | **接受** | major 命中：与 US2 AC-12-revised 不对齐。新增 AC-04c/05c/06c：`hidden=true` 的 item 在 SectionList 渲染为视觉淡化行（`data-hidden="true"` + 文本节点保留）。 |
| R7 [AC-01] | **接受** | major 命中：spec 措辞"3 × shared SectionItem wrapper"含义模糊，AC-01 验证过弱。修订 AC-01：3 个 SectionList 文件 `import { SectionItem }` 同一路径 + 起草说明显式"shared = 共享 sub-components + list-row wrapper，非 1 个泛型 dialog"。 |
| R8 [AC-07/08/09] | **接受** | minor 但补全便宜：空数组起点 + 全空 + 空字符串 round-trip 三 case 缺。扩 AC-07/08/09 步骤 (a) 增加"空数组起点"path；新增 AC-07b/08b/09b 三 section × 1 case 覆盖空数组边界。 |
| R9 [AC-17/18] | **接受** | blocker 命中：US2 AC-09b 跨 section 拖拽隔离模式未对齐 US3。新增 AC-17b：3 个 SectionList items drag 通过 `data-dnd-context="education"|"projects"|"skills"` 命名空间隔离。 |
| R10 [AC-15] | **接受** | major 命中：keystroke 节奏不可预测，N <= 9 硬约束易失败。修订 AC-15：删 `N <= 9` 硬约束 + 改 `N >= 1 && data deep equal S0`；新增注释"AC 不约束 keystroke 颗粒度"。 |
| R11 [AC-11/12] | **接受** | major 命中：与 R2 联动 — Education period 改单 input 后 AC-11 与 AC-12 完全一致，3 dialog 共享 `<FieldPeriod>` 单 input sub-component。 |
| R12 [AC-04/05/06/16] | **接受** | major 命中：US2 AC-14 模式未在 US3 显式 cast。修订 AC-04/05/06：每个 input "验证步骤" 增加"断言 onChange handler 直接调 setDataMut（无 useState 镜像）"；AC-16 步骤 (a) 扩展为 3 个 dialog 文件全 grep。 |
| R13 [AC-19] | **接受** | minor 命中：SectionItem 路径未明。修订 AC-19：显式路径 `src/modules/resume/v2/editor/left/SectionItem.tsx` + `find src -name "SectionItem.tsx" \| wc -l === 1` 唯一性断言。 |
| R14 [AC-15] | **接受** | major 命中：与 R2 + R10 + R11 联动 — Education period 改单 input 后帧数可预测；AC-15 步骤 (b) 改"改 3 字段 + add 1 string[] 元素 + reorder 1 次"（5 帧保守估测）。 |
| R15 [AC-20] | **接受** | major 命中：US2 AC-15-revised 教训未对齐。修订 AC-20：扩 6 子 case（description sanitized × 2 + hidden × 1 + level=0 × 1 + 空 array × 2）。 |

**汇总**：15 接受 / 0 部分接受 / 0 驳回

**Round 2 必走**：派 dev 修订 ac-matrix.md，预计新增 6-8 条 AC（04c/05c/06c/07b/08b/09b/13b/17b/18b）+ 7 条修订（01/06/10/11/13/15/19/20），目标 25-30 AC 锁定。

## Round 2 修订说明 (dev)

本轮 dev 修订：frontmatter round 1 → 2，negotiation_rounds 1 不变（main-agent 跑完 round 2 后再 increment）。AC 矩阵共 20 既有 AC + 9 新增 AC = **29 AC**。

### 修订 AC（10 条既有 AC 重写，吸收 R1/R2/R3/R4/R5/R7/R8/R10/R11/R12/R13/R14/R15 反馈）

- **AC-01** (R7): "shared SectionItem wrapper" 含义明确为 3 个 list 文件 `import { SectionItem }` 同一路径；验证步骤 (d) 改为 grep 3 个 list 文件 import 路径一致性。
- **AC-04** (R12): 每个 input 验证步骤增加"断言 onChange handler 直接调 setDataMut（无 useState 镜像）"。
- **AC-05** (R12): 同 AC-04 模式，project 字段直写 store 显式 cast。
- **AC-06** (R1 + R12): `category(name)` 误标改为 `name` 独立字段 + 新增 `proficiency` 自由文本字段；snapshot 6 input testid（`skills-icon` / `skills-name` / `skills-proficiency` / `skills-level` / `skills-keywords-add` + 容器 `skills-keywords`）+ 1 color picker `skills-icon-color` + 1 checkbox `skills-hidden`。
- **AC-07** (R8): 步骤 (a) 增加"seed 0 courses（空数组起点）" path。
- **AC-10** (R3): 删 `3.7 → 3 或 4` 模糊；改 slider step=1 整数；非整数 `fireToast('warn')` + 红框 + 不写 store；新增 `level=0` 显示 "Hidden" label 语义（与 reactive-resume 一致）。
- **AC-11** (R2 + R11 + R14): Education `period` 改**单** input（与 reactive-resume + schema + US2 Experience + project period 一致）；删 `education-period-start` / `education-period-end` testid；保留自由格式 + placeholder。
- **AC-12** (R11): project period 单 input 验证步骤保留（与 AC-11 修订后 3 dialog 完全一致）。
- **AC-13** (R4): 步骤 (a) 显式断言 `education-website-url` / `projects-website-url` 存在后再 input URL；2 case（education + project）替代原 3 case 假命中。
- **AC-15** (R10 + R14): 步骤 (b) 改"改 3 字段 + add 1 string[] 元素 + reorder 1 次"（5 帧保守估测）；步骤 (d) 删 `N <= 9` 硬约束 + 改 `N >= 1 && data deep equal S0`；新增注释"AC 不约束 keystroke 颗粒度"。
- **AC-16** (R12): 步骤 (a) 显式扩展为 3 个 dialog 文件全 grep `useState` / `useReducer`。
- **AC-18** (R5): 来源列加 R5 标注；AC-18b 单独承载"3 dialog + 6 case vs 共享 helper"二选一说明。
- **AC-19** (R13): 显式路径 `src/modules/resume/v2/editor/left/SectionItem.tsx`（与 SectionList 同目录）；步骤 (3) 增加 `find src -name "SectionItem.tsx" | wc -l === 1` 唯一性断言 + 步骤 (4) `git grep -l "import.*SectionItem" src/modules/resume/v2/editor/left/` 期望 ≥ 3 hits。
- **AC-20** (R15): 扩 6 子 case（description sanitized × 2 + hidden × 1 + level=0 × 1 + 空 array × 2）；共 9 个 pytest case 替代原 3 case。

### 新增 AC（9 条）

- **AC-04c** (R6): Education `hidden=true` 视觉淡化行（`data-hidden="true"` + 文本节点保留）。
- **AC-05c** (R6): Project `hidden=true` 视觉淡化行。
- **AC-06c** (R6): Skill `hidden=true` 视觉淡化行。
- **AC-07b** (R8): 3 个 `string[]` 字段空数组 add/remove/round-trip 边界（空数组起点 + 全空 + 空字符串 round-trip）。
- **AC-08b** (R8): 空数组后 drag 批处理（5 次 drag 合并为单帧）。
- **AC-09b** (R8): 单元素 id 保留（drag no-op）。
- **AC-13b** (R4): Skill dialog 不含 website 字段（schema + 静态检查 + testid 不存在）。
- **AC-17b** (R9): 3 个 SectionList items drag 通过 `data-dnd-context` 命名空间隔离（沿用 US2 AC-09b 模式）。
- **AC-18b** (R5): dispatcher 共享 helper vs 显式 6 case 二选一（dev 自决可维护性 vs 命名空间清晰）。

### 起草说明同步更新要点

- 共享模式：spec "3 × shared SectionItem wrapper" 含义 = 共享 sub-components + 共享 list-row wrapper（`SectionItem` 同 import 路径），**非** 1 个泛型 dialog 接 type props（沿用 R7 修订）。
- Skill `level` slider：step=1 整数 + level=0 "Hidden" label 语义（与 reactive-resume `Number(field.state.value) === 0 ? t\`Hidden\` : '${value} / 5'` 一致，R3 修订）。
- Education `period` 单 input：reactive-resume + schema 都用 free-form 字符串，dev 拆 startDate/endDate 是自行扩展（R2 修订），与 US2 Experience period + project period 一致。
- dispatcher 二选一：6 case 显式 vs 共享 helper 模式（dev 自决可维护性 vs 命名空间清晰，R5 修订）。
- US3 范围不含 Profile / Language / Interest / Award / Certification / Publication / Volunteer / Reference（US4 + US5 覆盖）。


## 起草说明（写给 tester）

**设计意图**：
- US3 范围限定 Education / Projects / Skills 3 个 section 的 item dialog + 列表 + add-button；不触碰 Profile / Language / Interest / Award / Certification / Publication / Volunteer / Reference 等其他 7 个 section（US4 + US5 覆盖）。
- **共享 SectionItem wrapper**：3 个 SectionList + 3 个 item dialog 复用同一 `SectionItem` 包装器（dev 实现可统一为 `<SectionItem sectionId="education" item={item} onEdit/onDuplicate/onDelete=... />`）；字段差异在 props schema 而非组件本身。SectionItem 内部根据 `sectionId` 走 generic 化渲染：显示 title (school/name/category) + subtitle (degree/period/level) + 3 inline action。
- **共享 3 dialog 模式**：3 个 dialog 内部字段组件可拆为共享 `<FieldText>` / `<FieldUrl>` / `<FieldTextList>`（含 dnd-kit 重排）等 sub-component，但**外层 dialog 各自独立**（EducationDialog / ProjectsDialog / SkillsDialog），不强制 1 个 dialog 接 generic type props。原因：3 个 section 字段集差异大（education 11 字段 / project 7 字段 / skill 4 字段），泛型 dialog 内部 if/else 分支膨胀反而难维护。spec 接受"3 个 dialog 共享 list-row wrapper + 共享 sub-components + 共享 validateUrl / setDataMut 模式"，不强求 1 个 generic dialog。
- **dispatcher 仍按 section 分发**：`'education.create' | 'education.update' | 'projects.create' | 'projects.update' | 'skills.create' | 'skills.update'` 6 case（沿用 US2 `{section}.{verb}` 命名空间）。不共享 `'item.create' | 'item.update'` 简化（会破坏 future US4-US6 命名空间一致性）。
- 复用 US2 `useResumeV2Store.setDataMut` 模式，所有写操作自动获得 500ms debounce autosave + undoStack + redoStack + 30min TTL。
- `string[]` 字段（courses / highlights / keywords）走 dnd-kit drag-reorder + 500ms 批处理（沿用 US2 AC-08b + REQ-033 第8轮 L 教训）。
- Skill `level` 数值字段沿用 US1 AC-06 扩展（0..5 clamp + NaN/Infinity 拒绝）。
- Education `period` 自由格式：dialog 内拆为 `startDate` / `endDate` 两个 input 自由格式（沿用 reactive-resume Education dialog 行为），落 store 时合并为 `period` 字段。Project `period` 沿用 US2 Experience `period` 单 input 模式（不拆 start/end）。
- dialog 关闭走 DialogHost 循环 undo 到 S0（沿用 US2 AC-13 revised）；禁止本地 draft state（沿用 US2 AC-14）。
- Backend round-trip 在 `test_legacy_format.py` 新增 3 case（沿用 US1 AC-15 + US2 AC-15 模式）；`ResumeDataV2Pydantic` 已支持（spec 行 73-74 隐含），无 backend 代码变更。

**已覆盖的边界**：
- 3 个 SectionList 共享 SectionItem wrapper + add-button（AC-01, AC-17）
- 3 个 dialog 字段映射完整（AC-04, AC-05, AC-06）
- string[] 字段 add/remove/reorder 完整 + 500ms 批处理（AC-07, AC-08, AC-09）
- Skill level 0..5 clamp + NaN 拒绝（AC-10）
- period 自由格式差异（education 拆 start/end vs project 单 input）（AC-11, AC-12）
- URL 白名单 + unicode/IPv6（AC-13）
- XSS 注入（AC-14）
- 关闭循环 undo + 禁止本地 draft（AC-15, AC-16）
- dispatcher 6 case 扩展 + fail loud（AC-18）
- 命名导出 + 无 shadow（AC-19）
- Backend round-trip 3 case（AC-20）

**未覆盖的边界（已知风险）**：
- 3 个 dialog 共享 SectionItem wrapper vs 各自独立的 trade-off：本 AC 矩阵**接受"外层 dialog 各自独立 + 内部 sub-components 共享"**模式（理由：3 个 section 字段集差异大，泛型 dialog 内部 if/else 分支膨胀反难维护；spec 措辞"3 × shared SectionItem wrapper"指 list-row + 共享 sub-components，非强制 1 个 generic dialog）。若 tester 反驳"必须 1 个 generic dialog"，需 dev 重构。
- dispatcher 6 case vs 共享 1 case 的可维护性：6 case 显式列出会让 DialogHost switch 变长（10 case 总），但与 US4-US6 命名空间一致；共享 1 case `'item.create' | 'item.update'` 会破坏 future 扩展性（不同 section 字段 schema 不同）。本 AC 矩阵**接受 6 case 显式**。
- `string[]` 字段（courses/highlights/keywords）的空字符串验证未在 AC 约束：reactive-resume 接受空字符串为合法（用户可能填一半），dev 沿用 US2 roles[] 模式即可。
- 3 个 section 各自的 `icon` 字段（SkillItem.icon / SkillItem.iconColor）未在本 AC 约束：spec 未提，留 dev 沿用 data.ts 字段集做 picker（US5 P1 范围外，US3 不强求 UI）。
- Education `website` 字段：data.ts 行 157 包含 `website: ItemWebsite` 但本 AC 矩阵未为 Education 添加 website testid 显式断言（与 Project 共享同款模式 AC-13 覆盖 URL 验证）。
- 拖拽批处理的 undoStack 边界：500ms 内连续 drag 合并为 1 帧（与 US2 一致），但若 dev 错误实现 skipHistory（首次 drag 也 skip）会导致拖拽前快照丢失，AC-08 已断言"单次 undo 恢复拖拽前初始顺序"。

**必避陷阱已在 AC 中显式 cast 死**：
- L008（module shadow）：AC-19 显式 `ls src/modules/resume/v2/editor/dialogs/*.ts` 验证无 shadow
- L009（default vs named export）：AC-19 静态检查
- L005（ship HTTP probe）：AC-20 触发真实 backend pytest round-trip
- US1 AC-08b（关闭撤销）：AC-15 复用
- US1 AC-08c（禁止本地 draft）：AC-16 复用
- US1 AC-11b（type 命名空间）：AC-18 复用
- US2 AC-08b（拖拽批处理）：AC-08 复用
- US2 AC-09c（键盘可达性）：未在 US3 AC 矩阵中显式覆盖，建议 dev 沿用 US2 模式（list-row Space 抓取 + ArrowUp/Down 移动 + Space 确认），待 tester round 1 反驳时补
- US2 AC-11b-revised（default throw）：AC-18 复用
- US2 AC-11c（grep 验证无 default: return null）：AC-18 复用
- US2 AC-13-revised（循环 undo 到 S0）：AC-15 复用
- US2 AC-14（无本地 draft state）：AC-16 复用
- US1 AC-04b / US2 AC-04b（id 保留规则）：AC-09 复用
- US1 AC-06 / US2 AC-06（数值字段 clamp + NaN 拒绝）：AC-10 复用
- US2 AC-11-revised（URL 白名单 + u flag）：AC-13 复用
- US1 AC-09 / US2 AC-12（XSS 转义）：AC-14 复用
- REQ-033 第8轮 L 教训（拖拽批处理 skipHistory 锚定）：AC-08 复用

**潜在风险**：
- **3 dialog 共享 SectionItem wrapper vs 各自独立的 trade-off**：本 AC 接受"外层 dialog 各自独立 + 内部 sub-components 共享"模式（理由：3 个 section 字段集差异大），但若 tester 反驳"spec 措辞 3 × shared SectionItem wrapper 必须是 1 个 generic dialog 接 type props"，需 dev 重构。dev 在实施前可先 grep spec 措辞含义。
- **dispatcher 6 case vs 共享 1 case 的可维护性**：6 case 显式列出会让 DialogHost switch 变长（US1 + US2 + US3 共 10 case），但与 US4-US6 命名空间一致；共享 1 case 会破坏 future 扩展性。本 AC 接受 6 case 显式。
- **`string[]` 字段的 drag-reorder 测试覆盖**：3 个 section × 1 个 string[] 字段 = 3 处需要测。AC-07 拆为 3 个子 case（courses/highlights/keywords），AC-08/AC-09 复用 US2 同款模式。
- **Education `period` 拆 start/end 的实现细节**：dialog 内部 input 设计自由度较高（单 input 字符串 vs 双 input 拆分），本 AC 显式约束拆分为 start/end 两个 input（AC-11），与 reactive-resume Education dialog 行为一致。
- **US3 与 US4（Profile）边界**：US3 范围不含 Profile section（社交链接图标选择器），US4 单独处理。
- **US3 与 US5（Language/Interest/Award/Certification/Publication/Volunteer/Reference）边界**：US3 范围仅含 Education/Project/Skill 3 个 section，US5 处理剩余 7 个 section。本 AC 矩阵 dispatcher 仅扩展 6 case，US5 时再扩展。
- **3 个 SectionList 移动端响应式**：未在 AC 约束（沿用 US1 AC-01b 模式 + 移动端 375px 不溢出），留 dev 沿用现有 SectionsPanel 响应式实现。
