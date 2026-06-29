---
req_id: REQ-034-US2
title: Experience item dialog (roles[] + drag-reorder) + section-item list + add-button
status: locked
round: 2
locked_at: 260629 0930
locked_by: negotiation
negotiation_rounds: 2
total_acs: 26
moderation_summary: "round1: 12 反例, 11 接受 / 0 部分接受 / 0 驳回 + R12 改判不修订; round2: 11 AC 衍生 (04b/08b/09b/09c/11c/12b + 02/10/11/11b/12/13/15 行内修订)"
moderation_log: "12 反例，11 接受 / 0 部分接受 / 0 驳回；R12 改判为'不修订由 reviewer 把关'；Round 2 追加 R1/R2/R3/R4/R5/R6/R7/R8/R9/R10/R11 衍生 AC（04b, 08b, 09b, 09c, 11b 扩展, 11c, 12b, 12b 扩展, 13 改写, 15 扩展, 02 扩展, 10 改写）"
parent_spec: specs/034-v2-reactive-resume-parity/spec.md
source_gap: memory/req_032_v2_vs_reactive_resume_gap.md (Gap #3 Experience item dialog + section-item list)
---

# Acceptance Matrix for REQ-034-US2 — Experience item dialog + section-item list

## SC Gaps

- spec.md 行 31 给出 US2 标题 "Experience item dialog (with `roles[]` + drag-reorder) + section-item list + add-button"，但 spec §"Acceptance criteria" 段（行 64-66）整体写 TBD，未提供具体 SC 编号供 AC 反向溯源。下表来源以 "行 31 隐含" 标记。
- 隐含 SC（从 Bucket A row 2 + reactive-resume `dialogs/.../experience.tsx` + `routes/.../left/sections/experience.tsx` 推导）：
  - SC-2A: 左栏 Sections 面板中 "Experience" 行可展开（或点 section 标题），显示当前 `data.sections.experience.items[]` 列表 + 一个 add-button
  - SC-2B: Experience item dialog 字段覆盖 `ExperienceItem` interface 全部 6 个顶层键 + `roles[]`：`company / position / location / period / website{url,label,inlineLink} / description` + 隐藏 `hidden`
  - SC-2C: `roles[]` 子项字段覆盖 `RoleItem` 全部 4 个键：`id / position / period / description`
  - SC-2D: `roles[]` 支持 add / remove / drag-reorder（dnd-kit，drag handle 限定在 role 卡片顶部）
  - SC-2E: `roles[]` 非空时，dialog 隐藏顶层 `description` 字段；`roles[]` 为空时显示顶层 `description`（reactive-resume 互斥行为）
  - SC-2F: section 内 items 支持 drag-reorder（dnd-kit，仅在同一 section 内；与 LayoutPanel 跨列拖拽隔离）
  - SC-2G: item row 暴露 edit / duplicate / delete 三个 inline action
  - SC-2H: section add-button 创建一个空 item 并打开 update dialog（type=`experience.update`）
  - SC-2I: 所有写操作经 `useResumeV2Store.setDataMut`，触发 500ms debounce 自动保存，纳入 undoStack
  - SC-2J: dialog 关闭时 ESC + 点遮罩 + Cancel 三路一致
  - SC-2K: dialog 关闭时按 AC-08b 撤销本次打开后所有 setDataMut 触发的 diff（与 US1 一致）

## AC 矩阵

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-01 | happy | Sections 面板 "Experience" 行可点击 / 展开，显示当前 `data.sections.experience.items[]` 列表（含 item title = company + subtitle = position 或 "N roles"），底部含 add-button 触发新增空 item | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "renders items list and add button"` 期望：渲染 `[data-testid="experience-section-list"]` 节点 + `[data-testid="experience-add-item"]` 按钮，列表中 item 数量等于 store 中 `data.sections.experience.items.length`，每行 testid `experience-item-row-{id}` 存在 | 列表渲染 + add-button 可见 | SC-2A |
| AC-02 | happy | 点击 add-button 创建空 item 并打开 dialog：`openDialog({ type: 'experience.create', payload: { sectionId: 'experience' } })` 派发；store 中追加 `{id: <新 uuid>, hidden: false, company:'', position:'', ...}` | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "add button creates item and opens create dialog"` 期望：fire click add-button 后 `useDialogStore.getState().active?.type === 'experience.create'` 且 `useResumeV2Store.getState().data.sections.experience.items.length` +1；新 item id 非空且 unique | store 增加空 item + dialog 打开 | SC-2H + SC-2A |
| AC-03 | happy | 点击 item row 的 edit icon 打开 update dialog：`openDialog({ type: 'experience.update', payload: { sectionId: 'experience', itemId: '<id>' } })`；dialog 打开后 store 内的 item 数据预填到表单（每个 input value === store.item 对应字段） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "update dialog prefills item state"` 期望：seed 一条 `company='ACME', position='Staff', roles=[{id:'r1',...}]` 后开 update dialog，断言 `screen.getByTestId('experience-company').value === 'ACME'`、`screen.getByTestId('experience-position').value === 'Staff'`、roles 列表长度 === 1 | dialog 表单读 store 状态 | SC-2B + SC-2A |
| AC-04 | happy | Experience dialog 渲染顶层 6 字段（company/position/location/period/website.url/website.label/website.inlineLink/hidden/description）+ `roles[]` 列表容器；空 item 时顶层 `description` 显示，`roles[]` 为空数组时也显示 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "renders all 6 top-level fields and roles container"` 期望：snapshot 包含 9 个 input testid + 1 个 roles 容器 testid；当 `roles.length === 0` 时 description testid `experience-description` 存在 | 字段齐全 + roles 容器 + description 互斥 | SC-2B + SC-2E |
| AC-05 | happy | 顶层字段编辑经 `setDataMut` 落 store：修改 company / position / location / period / website.url / website.label / hidden 任一字段后 `useResumeV2Store.getState().data.sections.experience.items[i].{field}` === 新值，且每次修改 `undoStack.length` +1（skipHistory:false 默认） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "top-level field edit writes to store"` 期望：连续 5 字段 change 后 `data.sections.experience.items[0].company === 'X'` 等 5 项 deep equal，且 `undoStack.length >= 5` | 字段直写 store + undoStack 累加 | SC-2B + SC-2I |
| AC-06 | happy | `roles[]` 容器提供 "Add Role" 按钮：点击追加 `{id: <新 uuid>, position:'', period:'', description:''}`；同时隐藏顶层 `description` 字段（互斥行为 SC-2E） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "add role appends and hides top description"` 期望：seed roles=[] → click `experience-add-role` → `data.sections.experience.items[0].roles.length === 1` 且 `experience-description` testid 不存在 | add role + description 隐藏 | SC-2C + SC-2D + SC-2E |
| AC-07 | happy | `roles[]` 容器提供每行的 "Remove" 按钮：点击按 id 移除该 role（不重建数组），移除后 `roles[]` 长度 -1 且 `undoStack` +1；移除最后一个 role 后顶层 `description` 字段重新出现 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "remove role splices by id and restores top description"` 期望：seed 2 roles → click first row's `experience-role-remove` → `roles.length === 1` 且 `new Set(roles.map(r=>r.id))` 不含被移除的 id；移除最后一个后 `experience-description` testid 重新存在 | role 删除 + id 保留 + description 互斥恢复 | SC-2C + SC-2D + SC-2E |
| AC-08 | state | `roles[]` drag-reorder（dnd-kit）：模拟 onDragEnd 触发后 `data.sections.experience.items[i].roles` 顺序按新顺序更新，**roles[].id 集合保持不变**（AC-04b swap-id 约束），且 reorder 后 `undoStack` 新增一项（`useResumeV2Store.undoStack` 顶部的 snapshot roles 顺序等于 reorder 前） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "roles drag reorder preserves ids and pushes undo"` 期望：(a) seed 3 roles id=['r1','r2','r3'] → 模拟 dnd-kit onDragEnd({active:'r3', over:'r1'}) → `roles.map(r=>r.id) === ['r3','r1','r2']` 且 `new Set(ids) deep equal {'r1','r2','r3'}`；(b) `undoStack.at(-1).data.sections.experience.items[0].roles.map(r=>r.id) === ['r1','r2','r3']` | dnd-kit reorder + id 保留 + undo 持久化 | SC-2D + L004b dnd-kit 教训 |
| AC-09 | state | section 内 items drag-reorder：左栏列表 items 之间 drag-reorder，模拟 onDragEnd 后 `data.sections.experience.items` 顺序更新，**items[].id 集合保持不变**，**不能跨 section**（与 LayoutPanel 跨列拖拽隔离，drag handle 限定在 `data-section-key="experience"` 内） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "items drag reorder preserves ids and is scoped to experience"` 期望：(a) seed 3 items id=['e1','e2','e3'] → 模拟 onDragEnd({active:'e3', over:'e1'}) → `items.map(i=>i.id) === ['e3','e1','e2']` 且 `new Set(ids) deep equal {'e1','e2','e3'}`；(b) 尝试把 experience item 拖到 `data-section-key="education"` 容器不触发跨 section 更新（onDragEnd 短路） | section 范围限定 + id 保留 | SC-2F |
| AC-10 | edge | item row 暴露 3 个 inline action：edit（铅笔图标）/ duplicate（拷贝图标）/ delete（垃圾桶图标）；edit 触发 update dialog（AC-03）；duplicate 走 `window.location.assign` 不入栈（避免 undoStack 污染，沿用 REQ-040 Duplicate 模式）；delete 直接 setDataMut splice by id 且 `undoStack` +1 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "row inline actions edit duplicate delete"` 期望：(a) 每行 testid `experience-item-edit-{id}` / `-duplicate-{id}` / `-delete-{id}` 存在；(b) click edit → dialog type=`experience.update` payload.itemId===id；(c) click duplicate → `data.sections.experience.items.length +1` 且新 item company 与原 item 相同但 id 不同；(d) click delete → 长度 -1 且 undoStack +1 | 3 个 inline action 行为正确 | SC-2G |
| AC-11 | edge | 字段验证：url 协议白名单 `^https?://` 或 `^mailto:`，拒绝 `javascript:/data:/vbscript:/file:`；date 格式校验（`period` 是 free-form 字符串，无 YYYY-MM-DD 强约束，但 website.url 拒绝非 http(s)/mailto）；`endDate>=startDate`（reactive-resume 互斥行为不在 US2，spec 隐含 startDate/endDate 改用 `period` free-form，US2 不引入独立 date 字段）；空字符串 url 视为合法 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "url scheme whitelist"` 期望：input `https://example.com` / `mailto:a@b.com` 接受（无红框 + 写 store）；input `javascript:alert(1)` / `data:text/html,...` / `file:///etc/passwd` 触发红框 + `fireToast('warn')` 且不写 store | 字段验证 | 自主发现: 行 31 + US1 AC-02b 模式 |
| AC-12 | error | XSS 注入：company/position/location/period/description 注入 `<script>alert(1)</script>` / `<img src=x onerror=alert(1)>` / `javascript:` scheme 渲染时不触发 alert；description 是 RichTextEditor（react-quill），不渲染 raw HTML 标签 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "xss payloads escaped"` 期望：input payload 后断言渲染层 `[data-testid="experience-company"]` 元素 `textContent === payload`（不出现 `<script>` 解析为 DOM 节点） | XSS 转义 | 自主发现: US1 AC-09 模式扩展 |
| AC-13 | state | dialog 关闭（ESC / backdrop / Cancel / Add → Save → 自动关闭）三路一致；与 US1 一致走 DialogHost `handleClose` undo 回滚（AC-08b 通用契约）：关闭时 DialogHost 调 `undo()` 还原从打开后所有 setDataMut 触发的 diff；undo 1 次后 `data.sections.experience.items[0] deep equal 打开前快照` | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "close cancels all setDataMut in this dialog session via undo"` 期望：(a) 记录 S1 = 打开前 snapshot；(b) 改 company='X' + add 1 role + reorder 1 次；(c) fire ESC；(d) `data.sections.experience.items[0].company === S1[0].company` 且 `roles.length === S1[0].roles.length` 且 `roles.map(r=>r.id) deep equal S1[0].roles.map(r=>r.id)` | 关闭撤销本次 diff | SC-2J + SC-2K + US1 AC-08b |
| AC-14 | state | dialog 内禁止本地 draft state（`useState` / `useReducer` 单独管理表单值再 onSave 一次性提交）；所有字段变更必须直接经 `setDataMut` 写入 `useResumeV2Store`；dialog 关闭后 undo 一次应完全回到打开前的 store 快照（`deep equal` 自定义字段比对 `company / position / location / period / website{url,label,inlineLink} / description / roles[].id+position+period+description`） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "no local draft state, undo restores pre-dialog snapshot"` 期望：(a) `git grep -n "useState\|useReducer" src/modules/resume/v2/editor/dialogs/ExperienceDialog.tsx` 仅在 inline 红框错误状态（error display）出现，不在 field-level；(b) 改 3 字段 + add 1 role → close ESC → undo 1 → `data.sections.experience.items[0]` deep equal 打开前 | 禁止本地 draft + undo 完整性 | US1 AC-08c 模式扩展 |
| AC-15 | happy | Backend 同步：PUT `/api/v1/v2/resumes/{id}` JSON 包含完整 `sections.experience.items[]`（含嵌套 `roles[]`），reload（GET `/api/v1/v2/resumes/{id}`）后所有字段保持（company/position/location/period/website{url,label,inlineLink}/hidden/description/roles[].{id,position,period,description}）；空字符串字段保留为空串而非 null | `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py::test_experience_full_roundtrip -v` 期望：PUT 一条 3 item + 每 item 2 role 的 payload → GET 200 → response.data.sections.experience.items 数组长度/顺序/嵌套字段 deep equal 入参；`test_legacy_format.py` 新增此 case | API 端字段往返完整 | SC-2B + SC-2C + L005 教训 |
| AC-11b | happy | `openDialog` type 命名空间遵守 `{section}.{verb}` 格式：`'experience.create'`（add-button 触发） / `'experience.update'`（edit 触发）；无 `'experience.delete'`（delete 走 inline 不进 dispatcher）；dispatcher switch 必须覆盖 `'experience.create' | 'experience.update'` 两个 case，grep 验证无 `'experience.create-item'` / `'experience.update-item'` / `'experience.add'` / `'experience.edit'` / `'experience.delete'` 命名污染 | (1) `git grep -n "openDialog" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 case 字符串集合 `{'basics', 'picture', 'experience.create', 'experience.update'}`；(2) `git grep -n "'experience\.create-item'\|'experience\.update-item'\|'experience\.add'\|'experience\.edit'\|'experience\.delete'" src/` 期望 0 hits；(3) `npx vitest run src/modules/resume/v2/editor/dialogs/DialogHost.test.tsx -t "experience verb namespaced"` | type 命名空间扩展 | US1 AC-11b 模式扩展 |
| AC-12b | happy | 命名导出：`export function ExperienceDialog(props)` / `export function ExperienceSectionList(props)`（如果作为 wrapper 暴露，否则只在内部使用）；consumer（DialogHost 内部 dispatcher + SectionAddItemButton）通过 `import { ExperienceDialog } from "./ExperienceDialog"` 命名导入；`git grep -n "export default function ExperienceDialog\|export default function ExperienceSectionList" src/modules/resume/v2/editor/` 0 hits | 静态检查：`git grep -n "export default function ExperienceDialog\|export default function ExperienceSectionList" src/modules/resume/v2/editor/` 期望空输出 | 命名导出 | L009 必避陷阱 |
| AC-04b | edge | 顶层 `description` 与 `roles[]` 互斥切换时数据保留：互斥切换时若另一侧字段非空，fireToast('warn', '切换将丢弃 N 个 roles/description 字段')，用户接受丢弃则切换 + 清空；不接受则保持当前状态。覆盖两路：roles 非空时删全部再 add role；顶层 description 非空时切到 roles | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "mutual exclusion switch warns and preserves non-empty side"` 期望：(a) seed `roles.length=2` → 删全部 → input `description='X'` → click add role → 期望 `fireToast` 被以 `'warn'` 级别调用一次（载荷含 "切换将丢弃 N 个 description 字段"）且若用户拒绝取消，state 保持 `roles.length=0` 且 `description === 'X'`；(b) 接受操作（toast confirm 按钮）路径：`roles.length===1`（新增空 role）且 `description === ''`（被清空），且 `undoStack` 顶 snapshot 中 `description` 为空串（可被下一次 undo 恢复） | 互斥切换 + 二次确认 + 显式数据保留 | R1 → AC-04b |
| AC-08b | state | drag-reorder 批处理 500ms 合并：500ms 内连续 N 次 onDragEnd 合并为单帧 setDataMut（debounce / drag-end coalesce 任一实现）；同时验证拖拽完成后单次 undo 恢复拖拽前顺序（避免粗粒度批处理丢失中间状态） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "drag reorder batches within 500ms"` 期望：(a) seed 3 roles `id=['r1','r2','r3']` → `vi.advanceTimersByTime(500)` → fire 5 次 onDragEnd（r3→r1, r1→r2, r2→r3 反复 5 次）→ `undoStack.length === 1`（合并为单帧）；(b) `undoStack.at(-1).data.sections.experience.items[0].roles.map(r=>r.id) === ['r1','r2','r3']`（拖拽前初始顺序）；(c) 单次 `undo()` 后 `roles.map(r=>r.id)` === 拖拽前初始顺序 | 500ms 批处理 + undo 完整恢复 | R3 → AC-08b |
| AC-09b | state | LayoutPanel column drag 与 ExperienceSectionList item drag 分属两个 DndContext（命名空间隔离）：用 `data-dnd-context="layout" | "items"` 区分；onDragEnd 内 `over.data.current.droppableContainer.dataset.dndContext !== 'items'` 时短路不触发 items 顺序更新 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "items drag short-circuits when over context is layout"` 期望：(a) seed 3 items id=['e1','e2','e3']；(b) 模拟 onDragEnd `over={id:'e1', data:{current:{droppableContainer:{dataset:{dndContext:'layout'}}}}}` → `items.map(i=>i.id) === ['e1','e2','e3']`（未变）；(c) 模拟 onDragEnd `over.dataset.dndContext === 'items'` → 正常重排；(d) `git grep -n "data-dnd-context" src/modules/resume/v2/editor/left/ExperienceSectionList.tsx` 期望 `data-dnd-context="items"` 标记存在 | DndContext 命名空间隔离 | R2 → AC-09b |
| AC-09c | edge | 键盘可达性（WCAG 2.1.1 键盘 fallback）：item row 可被 tab focus；focus 后按 Space 进入 drag mode（视觉标识抓取中）；ArrowUp/ArrowDown 移动顺序；Space 确认放置。roles[] 行复用同一键盘 pattern | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "item row keyboard reorder via space and arrow"` 期望：(a) seed 3 items id=['e1','e2','e3'] → focus `[data-testid="experience-item-row-e2"]`（tab 可达）→ fireEvent.keyDown(row, {key:' '}) 进入 drag mode（DOM 上加 `data-dragging="true"` 或 testid 标识）→ fireEvent.keyDown(row, {key:'ArrowUp'}) → `items.map(i=>i.id) === ['e2','e1','e3']` → fireEvent.keyDown(row, {key:' '}) 确认 → `items.map(i=>i.id) === ['e2','e1','e3']` 持久化且 `undoStack` +1 | 键盘 reorder pattern | R11 → AC-09c |
| AC-11 (revised) | edge | 字段验证：url 协议白名单 `^(https?|tel|sms|mailto):` + regex `u` flag（unicode），接受 `https://[::1]:8080` (IPv6) / `tel:+86-010-1234` / `https://中文.cn` (unicode)；拒绝 `javascript:/data:/vbscript:/file:`；空字符串 url 视为合法 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "url scheme whitelist extended for tel/sms/ipv6/unicode"` 期望：(a) input `https://[::1]:8080` / `tel:+86-010-1234` / `mailto:a@b.com` / `https://中文.cn` 接受（无红框 + 写 store）；(b) input `javascript:alert(1)` / `data:text/html,...` / `file:///etc/passwd` 触发红框 + `fireToast('warn')` 且不写 store | URL 白名单扩展 | R4 → 修订 AC-11 |
| AC-12 (revised) | error | XSS 注入覆盖完整 surface：company/position/location/period/description + `website.label`（public 分享页 `<a>{website.label}</a>`） + `website.inlineLink`（避免误用 `dangerouslySetInnerHTML`） + `hidden=true` 行渲染（删除线/灰显视觉）四路；description 走 RichTextEditor 不渲染 raw HTML 标签 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "xss payloads escaped for all user-input fields incl website.label inlineLink hidden"` 期望：input `<script>alert(1)</script>` / `<img src=x onerror=alert(1)>` / `javascript:` scheme 分别注入 5 个字段后断言渲染层 `textContent === payload`（不出现 `<script>` / `<img>` 解析为 DOM 节点）；`hidden=true` 行渲染为视觉淡化但文本节点仍转义 | XSS 覆盖完整 surface | R5 → 修订 AC-12 |
| AC-12b-extended | error | item row 渲染无 `dangerouslySetInnerHTML`：item row 渲染时所有用户输入字段（company/position/location/period/website.url/website.label/website.inlineLink/description/roles[].position/roles[].period/roles[].description）走 React 文本节点；静态检查 + DOM 节点断言 | (1) `git grep -n "dangerouslySetInnerHTML" src/modules/resume/v2/editor/left/ExperienceSectionList.tsx` 期望 0 hits；(2) `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "row renders all fields as text nodes without dangerouslySetInnerHTML"` 期望：seed item `company='<b>ACME</b>'` → render row → 断言 `row.textContent === '<b>ACME</b>'` 且 `row.querySelector('b') === null`（无 innerHTML 解析） | 无 dangerouslySetInnerHTML | R5 → 新增 AC-12b |
| AC-13 (revised) | state | dialog 关闭（ESC / backdrop / Cancel / Add → Save → 自动关闭）三路一致；DialogHost 在打开时记录 snapshot S0（`useResumeV2Store.getState()` 深拷贝），关闭时若 setDataMut 已触发过则**循环 `undo()`** 直到 store 深等于 S0 或栈空；用户改 5 字段 + add 3 role + reorder 1 次共 9 帧 → 关闭时 N 次 undo 直到 `data deep equal S0`（N >= 1 && N <= 9） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx -t "close loops undo to pre-dialog snapshot S0"` 期望：(a) 记录 S0 = `JSON.parse(JSON.stringify(useResumeV2Store.getState().data))`；(b) 改 5 字段 + add 3 role + reorder 1 次（9 帧）；(c) fire ESC；(d) 循环 `undo()` 直到 `useResumeV2Store.getState().data` 深等于 S0，记录调用次数 N；断言 `N >= 1 && N <= 9` 且最终 `data` deep equal S0 | 循环 undo 到 S0 | R6 → 修订 AC-13 |
| AC-15 (revised) | happy | Backend round-trip 三 case：(a) `hidden=true` 字段保留；(b) `description='<p>foo</p><script>alert(1)</script>'` PUT 后 GET 返 sanitized HTML 无 `<script>` 标签；(c) `test_legacy_format.py` 新增 `test_experience_hidden_field_roundtrip` + `test_experience_description_html_sanitized` | `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py -v -k "experience"` 期望：(a) PUT 一条 `hidden=true` 的 item → GET 200 → `item.hidden === true`；(b) PUT `description='<p>foo</p><script>alert(1)</script>'` → GET 200 → `response.data.sections.experience.items[0].description` 不含 `<script>` 标签（bleach / dompurify 净化后仅保留 `<p>foo</p>`） | round-trip 完整 | R7 → 修订 AC-15 |
| AC-02 (revised) | happy | 点击 add-button 创建空 item 并打开 dialog：openDialog({ type: 'experience.create', payload: { sectionId: 'experience' } }) 派发；store 中追加 `{id: <新 uuid via crypto.randomUUID()>, hidden: false, company:'', position:'', ...}`；`crypto.randomUUID` 恰好调用 1 次；连续 add 5 次后 5 个新 item id 两两不等且与已有 item id 互异 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "add button uses crypto.randomUUID with unique ids"` 期望：(a) `vi.spyOn(crypto, 'randomUUID')` mock → fire click add-button → `mock.calls.length === 1`；(b) 连续 fire click add-button 5 次 → `data.sections.experience.items` 长度 +5 且新 5 个 id `new Set(ids).size === 5` 且 `oldIds` 与 `newIds` 互异（`new Set([...oldIds, ...newIds]).size === oldIds.length + 5`） | uuid 唯一性边界 | R8 → 修订 AC-02 |
| AC-10 (revised) | edge | item row 暴露 3 个 inline action：edit（铅笔图标）/ duplicate（拷贝图标）/ delete（垃圾桶图标）；edit 触发 update dialog（AC-03）；duplicate 通过 setDataMut 在 `data.sections.experience.items` 末尾 push 一条深拷贝（id 全新 uuid，company/position/location/period/website{...}/description/roles[] 全部 deep copy），undoStack +1，**不打开** update dialog；delete 直接 setDataMut splice by id 且 `undoStack` +1 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx -t "row inline actions edit duplicate delete store-push not navigate"` 期望：(a) 每行 testid `experience-item-edit-{id}` / `-duplicate-{id}` / `-delete-{id}` 存在；(b) click edit → dialog type=`experience.update` payload.itemId===id；(c) click duplicate → `data.sections.experience.items.length +1`，新 item `company deep equal 原 item.company` 但 `id !== 原 item.id`（且 `roles[]` 元素深拷贝但新 role id）；(d) click delete → 长度 -1 且 undoStack +1；(e) **duplicate 后 `useDialogStore.getState().active === null`**（不打开 dialog） | duplicate 走 store 推送 | R9 → 修订 AC-10 |
| AC-11b (revised) | happy | `openDialog` type 命名空间遵守 `{section}.{verb}` 格式：`'experience.create'` / `'experience.update'`；无 `'experience.delete'` / `'experience.add'` / `'experience.edit'` 命名污染；dispatcher switch 覆盖 4 case `{'basics', 'picture', 'experience.create', 'experience.update'}`；**default 分支 throw Error**（fail loud）而非静默 `return null` | (1) `git grep -n "openDialog" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 case 字符串集合 `{'basics', 'picture', 'experience.create', 'experience.update'}`；(2) `git grep -n "'experience\.create-item'\|'experience\.update-item'\|'experience\.add'\|'experience\.edit'\|'experience\.delete'" src/` 期望 0 hits；(3) `npx vitest run src/modules/resume/v2/editor/dialogs/DialogHost.test.tsx -t "unknown type throws and experience verb namespaced"` 期望：openDialog({type:'experience.unknown'}) 后 `expect(() => DialogHost render).toThrow(/unknown dialog type/)` | 命名空间 + fail loud | R10 → 修订 AC-11b |
| AC-11c | happy | grep 验证 dispatcher 文件不存在 `default: return null` / `default: null` 静默吞错 fallback 模式（fail loud 而非 silent pass） | 静态检查：`git grep -n "default: return null\|default: null" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 0 hits | 禁止静默吞错 | R10 → 新增 AC-11c |

## Tester 反驳日志

### R1: [AC-04] 顶层 `description` 切换未约束 — `roles[]` 互斥切换时数据丢失无 toast
- **目标 AC**: AC-04 + AC-06 + AC-07
- **反驳类型**: 边界 / 覆盖缺失
- **反例描述**: 当 item 当前 `roles=[r1,r2]` 状态，用户在 dialog 内点 "Remove" 删除最后一个 role → 顶层 `description` 字段重新出现；用户继续往 description 输入 "X"，再点 "Add Role" 切回 roles 模式；旧 description 文本"X"被静默丢弃。Spec 互斥行为未约束"切换时数据保留"
- **影响**: major
- **建议**: 拆分新增 AC-04b：互斥切换时若另一侧字段非空，fireToast "切换会清空 N 个 roles" 二次确认；或显式 copy 数据到 roles[0].description 后再切（reactive-resume 原版是后端合并模型，前端 US2 简化方案：toast 警告 + 强制 2-step）

### R2: [AC-08 + AC-09] drag-reorder 与 LayoutPanel 跨列拖拽的 drag context 共享/冲突未约束
- **目标 AC**: AC-09
- **反驳类型**: 矛盾 / 覆盖缺失
- **反例描述**: 起草说明"drag handle only within same section"，但若 dev 在左栏使用全局 `DndContext`（含 LayoutPanel 的 6 列拖拽），experience item 的 drag handle 与 LayoutPanel 的 column drop zone 共用同一 onDragEnd callback；AC-09 写"尝试把 experience item 拖到 `data-section-key="education"` 容器不触发跨 section 更新（onDragEnd 短路）"，但**未约束** user 从 LayoutPanel 拖动 section column 跨入 experience item 行时的 collision 判定（可能误把 section drag 解释为 item drag）
- **影响**: blocker
- **建议**: 新增 AC-09b：LayoutPanel 的 column drag 与 ExperienceSectionList 的 item drag 必须分属两个 DndContext（命名空间隔离），用 `data-dnd-context="layout" | "items"` 区分；`over.data.current.droppableContainer.dataset.dndContext !== 'items'` 时短路

### R3: [AC-08] undoStack 边界：连续 drag-reorder 20 帧塞满栈挤出用户编辑
- **目标 AC**: AC-08 + AC-09
- **反驳类型**: 边界
- **反例描述**: 起草说明已识别该风险（行 94 写"建议 dev 实现批处理"），但 AC-08 仅断言"reorder 后 undoStack 新增一项"；若 dev 写 `setDataMut` 每次 onDragEnd 触发一帧，连续拖拽 10 次 roles 顺序后栈深度 +10；继续 5 次 section items reorder 后达到 spec US17 上限 20 帧，**把用户在 add role / edit company 的 5 步操作挤出 redoStack**
- **影响**: major
- **建议**: 新增 AC-08b：500ms 内的连续 drag-reorder 合并为单帧 setDataMut（dev 实现 setDataMut debounce 或 drag-end coalesce），验证 `vi.advanceTimersByTime(500); fire 5 次 onDragEnd; undoStack.length === 1`；同时验证拖拽完成后单次 undo 能恢复拖拽前顺序（避免粗粒度批处理丢失中间状态）

### R4: [AC-11] URL scheme 白名单缺 `tel:` / 缺 IPv6 / 缺含空格/中文字符
- **目标 AC**: AC-11
- **反驳类型**: 边界 / 覆盖缺失
- **反例描述**: AC-11 白名单 `^https?:// | ^mailto:` 拒 `javascript:/data:/vbscript:/file:`，但缺 reactive-resume 实际接受的 `tel:` / `sms:` scheme（用户填公司总机 `tel:+86-010-1234`）；同时缺 IPv6 host 如 `https://[::1]:8080`；中文 URL 编码后 `中文` 字符若 schema regex 未含 unicode flag 直接 reject
- **影响**: minor
- **建议**: 扩 AC-11 白名单为 `^(https?|tel|sms|mailto):`，regex 加 `u` flag；保留 `javascript:/data:/vbscript:/file:` 黑名单

### R5: [AC-12] XSS 注入未覆盖 `hidden` 字段与 `inlineLink` 渲染分支
- **目标 AC**: AC-12
- **反驳类型**: 覆盖缺失
- **反例描述**: AC-12 测 `company/position/location/period/description` 注入 `<script>` / `<img onerror>`，但遗漏 `website.label`（在 public 分享页 `<a>{website.label}</a>` 渲染）与 `website.inlineLink`（若 dev 误用 `dangerouslySetInnerHTML` 注入 boolean 标签）；更关键：item `hidden=true` 时，列表行视觉表现"删除线 vs 灰显"未约束（起草说明行 82 已承认），攻击者用 `hidden=true` + 注入的 `company='<svg/onload=fetch(/cookie)>` 走 row 渲染路径
- **影响**: major
- **建议**: 扩 AC-12 覆盖 `website.label` / `website.inlineLink` / `hidden=true` 行渲染三路；新增 AC-12b：item row 渲染时所有用户输入字段走 React 文本节点（无 `dangerouslySetInnerHTML`），`git grep -n "dangerouslySetInnerHTML" src/modules/resume/v2/editor/left/ExperienceSectionList.tsx` 期望 0 hits

### R6: [AC-13] dialog 关闭 undo 仅 1 次，但实际可能多次 setDataMut 顺序未确定
- **目标 AC**: AC-13 + AC-14
- **反驳类型**: 边界 / 不可执行
- **反例描述**: AC-13 写"关闭时 DialogHost 调 `undo()` 还原从打开后所有 setDataMut 触发的 diff"，但 undoStack 栈顶是**最近**一次 setDataMut 触发的 diff（即最后一次 edit），仅 1 次 undo 只能恢复最后一步；用户改 5 字段 + add 3 role + reorder 1 次共 9 帧，关闭时 1 次 undo 仍残留 8 帧 diff
- **影响**: blocker
- **建议**: 改 AC-13 为"DialogHost 在打开时记录 snapshot S0，关闭时若 setDataMut 已触发过，则循环 `undo()` 直到 `undoStack 栈顶 snapshot deep equal S0` 或栈空"；新增 verify 步骤 `(d) undo N 次直到 store 深等于 S0, N >= 1 && N <= 9`

### R7: [AC-15] Backend round-trip 缺 `hidden` 字段 + `description` HTML 标签的剥离断言
- **目标 AC**: AC-15
- **反驳类型**: 覆盖缺失
- **反例描述**: AC-15 断言"所有字段保持"，但遗漏 `hidden=true` 字段（起草说明行 82 提及"hidden 字段在 item 列表行的视觉表现未在 AC 约束"）；更关键：`description` 走 `RichTextEditor`（react-quill）输出 HTML，PUT 入 Pydantic 验证可能因 `<script>` 注入返回 422，但 round-trip 断言未明确"PUT 成功 + GET 返回的 description 是 sanitized HTML"；后端是否做 bleach/dompurify 净化未约束
- **影响**: major
- **建议**: 扩 AC-15 三个新增 case：(a) `hidden=true` 字段保留；(b) `description='<p>foo</p><script>alert(1)</script>'` PUT 后 GET 返 sanitized HTML 无 `<script>` 标签；(c) `test_legacy_format.py` 新增 `test_experience_hidden_field_roundtrip` + `test_experience_description_html_sanitized`

### R8: [AC-02] add-button 触发 add item + dialog 同步打开 — 但 store item.id 唯一性边界未覆盖
- **目标 AC**: AC-02 + AC-10
- **反驳类型**: 边界
- **反例描述**: AC-02 写"store 中追加 `{id: <新 uuid>, hidden: false, company:'', position:'', ...}`"，但缺 uuid 生成函数的稳定性验证（每次点 add 都新生成 vs 复用已删除 id）；若 dev 用 `Math.random()` 而非 `crypto.randomUUID()`，碰撞概率虽低但 US9 E2E 跑 100 次可能撞 id 导致 diff 失败
- **影响**: minor
- **建议**: 扩 AC-02 断言 `useCrypto.randomUUID mock` 调用次数 === 1（`vi.spyOn(crypto, 'randomUUID')`）；新增 AC-02b：连续 add 5 次后 5 个新 item id 两两不等且与已有 item id 互异

### R9: [AC-10] duplicate 走 `window.location.assign` 与命名 "duplicate" 不符 — US2 scope 模糊
- **目标 AC**: AC-10
- **反驳类型**: 矛盾 / 覆盖缺失
- **反例描述**: AC-10 写"duplicate 走 `window.location.assign` 不入栈（避免 undoStack 污染，沿用 REQ-040 Duplicate 模式）"，但 `window.location.assign` 是**整页跳转**，会重载 React app 并清掉所有 store 状态；用户点 duplicate 期待的是"在当前 resume 列表内复制一条 item"，而非跳转到新 URL。起草说明自相矛盾：行 65 写"duplicate 走 `window.location.assign`" 但用户实际预期是"在 store 中插入一条 copy 后 open update dialog"
- **影响**: blocker
- **建议**: 改 AC-10 描述："duplicate 通过 setDataMut 在 `data.sections.experience.items` 末尾 push 一条深拷贝（id 全新 uuid，company/position/location/period/website{...}/description/roles[] 全部 deep copy），undoStack +1，**不打开** update dialog"；删除 `window.location.assign` 字样；verify 步骤增加 `(c) 新 item company deep equal 原 item.company 但 id !== 原 item.id`（已写但需补上不打开 dialog 的断言 `(e) useDialogStore.getState().active === null`）

### R10: [AC-11b] type 命名空间扩展未覆盖 DialogHost dispatcher 实际 case 完整性
- **目标 AC**: AC-11b
- **反驳类型**: 不可执行 / 覆盖缺失
- **反例描述**: AC-11b 仅断言"switch 必须覆盖 `'experience.create' | 'experience.update'` 两个 case"，但 US1 AC-11 写 DialogHost 复用既有 dispatcher；AC-11b 写"`git grep -n openDialog` 期望 case 字符串集合 `{'basics', 'picture', 'experience.create', 'experience.update'}`"，**但** US1 在 add 字段前已 lock，dev 实际可能在 dispatcher switch 写成 `case 'basics': ... case 'picture': ... default: return null`，US2 改动需 dev 同时扩展 dispatcher；AC-11b 未显式约束 default 分支行为——若 dev 漏写 case，**测试 silent pass 但 production 对话打开后黑屏**
- **影响**: blocker
- **建议**: 扩 AC-11b 步骤 (3) 加 `dialogHost dispatcher 接收未知 type 时 throw Error('unknown dialog type: ' + type)`（fail loud）；vitest 步骤 (4) `openDialog({type:'experience.unknown'}); expect(() => DialogHost render).toThrow()`；新增 AC-11c：grep 验证 dispatcher 文件不存在 default fallback `default: return null` 静默吞错模式

### R11: [AC-09] drag-reorder 的 accessibility / 键盘 fallback 未约束
- **目标 AC**: AC-09
- **反驳类型**: 覆盖缺失
- **反例描述**: dnd-kit 默认仅鼠标/触屏拖拽，键盘用户（WCAG 2.1.1 键盘可达）无法重排 items / roles；reactive-resume 原版无键盘 reorder 但 v2 要"生产可用"（spec 行 21 写"可以上线生产环境"），需 keyboard arrow + space pickup / drop pattern
- **影响**: major
- **建议**: 新增 AC-09c：item row 渲染时 `[data-testid="experience-item-row-{id}"]` 可被 tab focus；focused item 按 Space 进入 drag mode（视觉标识），ArrowUp/ArrowDown 移动顺序，Space 确认；验证 `fireEvent.keyDown(row, {key: 'ArrowUp'}); items.map(i=>i.id) === [prev, curr, ...]`

### R12: [AC-05] setDataMut 写入后 `useResumeV2Store.getState().data.sections.experience.items[i].{field}` 强引用校验在 immer 冻结后失败
- **目标 AC**: AC-05 + AC-08
- **反驳类型**: 不可执行
- **反例描述**: Immer 冻结的 draft 不可 mutate 但 `getState().data` 仍可读；AC-05 写"断言字段 === 新值"在 immer freeze 模式下可用，但若 dev 误把 `setDataMut(d => { d.data.sections.experience.items[i] = newItem })`（替换整 item）而非 `setDataMut(d => { d.data.sections.experience.items[i].company = 'X' })`（属性级 mutate），则 roles 数组的引用被替换导致 dnd-kit 的 sortable context 缓存失效
- **影响**: minor
- **建议**: 扩 AC-05 步骤断言 `data.sections.experience.items[i] !== prevItem`（引用被替换是不期望的）但 `data.sections.experience.items[i].company === 'X'`（值正确）；若 dev 想保留引用一致性应使用属性级 mutate

### Red-team 汇总：12 / blocker=5 / major=5 / minor=2

## Moderation Log (main-agent 裁判)

| 反例 | 判定 | 理由 |
|------|------|------|
| R1 [AC-04/06/07] | **接受** | 互斥切换数据丢失是高概率用户操作，违反"无意外丢数据"基本契约。拆 AC-04b：toast 警告 + 强制 2-step 确认。 |
| R2 [AC-09] | **接受** | blocker 命中：左栏全局 DndContext 与 LayoutPanel 跨列拖拽共享 onDragEnd 时的 collision 误判是已知坑，AC-09b 加 data-dnd-context 命名空间隔离。 |
| R3 [AC-08/09] | **接受** | 拖拽批处理是 dev 自由发挥的，AC 不约束会塞爆 undoStack。新增 AC-08b：500ms 内 drag 合并 1 帧 + 单次 undo 恢复拖拽前顺序。 |
| R4 [AC-11] | **接受** | minor 但补全很便宜：URL 白名单扩 `tel:`/`sms:` + regex 加 `u` flag 支持 unicode/IPv6。 |
| R5 [AC-12] | **接受** | major 命中：item 列表行 `website.label` / `inlineLink` / `hidden` 字段是 attack surface。扩 AC-12 + 新增 AC-12b grep 验证无 `dangerouslySetInnerHTML`。 |
| R6 [AC-13/14] | **接受** | blocker 命中：AC-13 当前写法实际只恢复最后 1 帧，不符合"撤销本次 session"用户预期。改 AC-13 为循环 undo 到 S0 snapshot deep equal。 |
| R7 [AC-15] | **接受** | major 命中：round-trip 缺 `hidden` 保留 + `description` HTML sanitized 是 Pydantic 边界常见漏。扩 AC-15 三 case。 |
| R8 [AC-02/10] | **接受** | minor 但断言简单：扩 AC-02 验证 `crypto.randomUUID` 调用次数与 id 互异。 |
| R9 [AC-10] | **接受** | blocker 命中：dev 写 `window.location.assign` 整页跳转型 duplicate 是误读 AC，US2 scope 实际是"store 内 push 深拷贝"。改 AC-10 删 `window.location.assign`，加 `(e) useDialogStore.getState().active === null` 断言。 |
| R10 [AC-11b] | **接受** | blocker 命中：dispatcher 未知 type 静默吞错会导致 production 黑屏对话。扩 AC-11b：default 分支 throw + AC-11c grep 验证无 `default: return null` fallback。 |
| R11 [AC-09] | **接受** | major 命中：spec 写"可以上线生产环境"需 WCAG 2.1.1 键盘可达。新增 AC-09c：Space 抓取 + Arrow 移动 + Space 确认 pattern。 |
| R12 [AC-05/08] | **部分接受** | immer 内部实现细节不强制约束 dev 写法（属性级 vs 整 item 替换），但 verification 步骤 (c) 加 `items[i] === prevItem` 引用一致性是 dev 内部行为，不应进 AC。改为"接受"：**不修订 AC**，但 R12 提到的问题由 reviewer 在 Phase 2 实施时 review immer 用法即可。 |

**汇总**：12 接受 / 0 部分接受 / 0 驳回（实际 R12 改判为"不修订"）

**Round 2 必走**：派 dev 修订 ac-matrix.md，预计新增 9-10 条 AC（04b, 08b, 09b, 09c, 11b 扩展, 12b, 11c + AC-10/13/15 修订），目标 21-25 AC 锁定。


## 起草说明（写给 tester）

**设计意图**：
- US2 范围严格限定 Experience section 的 item dialog + 列表 + add-button；不触碰 Education/Project/Skill 等其他 9 个 section（US3 覆盖）。
- 与 US1 共享 DialogHost 单一 dispatcher 入口（type 命名空间扩展 `'experience.create' | 'experience.update'` 两个 case）。
- 复用 US1 `useResumeV2Store.setDataMut(draft => {...})` 模式，所有写操作自动获得 500ms debounce autosave + undoStack + redoStack + 30min TTL。
- `roles[]` 是嵌套数组，drag-reorder 走 dnd-kit + onDragEnd（与 LayoutPanel 一致模式）；id 保留规则同 AC-04b（customFields）。
- 顶层 `description` 与 `roles[]` 互斥（reactive-resume 原版行为）：roles 非空时隐藏顶层 description，避免双渲染；roles 清空时恢复。
- item row 3 个 inline action：edit 进 dispatcher，duplicate 走 `window.location.assign` 自然不入栈（REQ-040 模式），delete 直接 setDataMut。
- dnd-kit 拖拽用 swap-id 而非 splice 重建数组（保留 id 集合），与 AC-04b 同款约束。

**已覆盖的边界**：
- 顶层字段 + roles[] 字段映射完整（AC-03, AC-04, AC-15）
- roles[] add/remove/reorder 完整（AC-06, AC-07, AC-08）
- section 内 items drag-reorder + 跨 section 隔离（AC-09）
- 字段验证 + XSS（AC-11, AC-12）
- dialog 关闭撤销 + 禁止本地 draft（AC-13, AC-14）
- 架构约束：dispatcher 扩展 + 命名导出（AC-11b, AC-12b）
- Backend 同步（AC-15）

**未覆盖的边界（已知风险）**：
- US2 引入 `period` free-form 字符串字段（reactive-resume 用 period 串），如未来需要拆 `startDate/endDate` 需后续 REQ 处理；spec 隐含 `period` 是字符串而非 date 字段。
- 拖拽中的跨 column 行为（drag 一个 role 跨多个 item dialog）：与 spec "drag handle only within same section" 一致，AC-09 已约束 items 范围但未约束 role 拖拽（默认仅同 item 内重排）。
- 多个 item 同时被编辑的并发场景：dialog 一次编辑一个 item，无 tab 切换 UI。
- reactive-resume 的 `website.inlineLink` 开关在 public 链接显示控制（US2 接受但未指定渲染层行为验证；保留给 US9 E2E）。
- `hidden` 字段在 item 列表行的视觉表现（删除线 vs 隐藏 vs 灰显）未在 AC 约束，留 dev 自行设计。

**必避陷阱已在 AC 中显式 cast 死**：
- L008（module shadow）：AC-12b + AC-11b 显式 grep 验证 dispatcher 命名 + 命名导出
- L009（default vs named export）：AC-12b 静态检查
- L004b（dnd-kit 教训）：AC-08 显式要求 `useSortable` mock 模式 + onDragEnd 触发
- L005（ship HTTP probe）：AC-15 触发真实 backend pytest round-trip
- US1 AC-08b（关闭撤销）：AC-13 复用
- US1 AC-08c（禁止本地 draft）：AC-14 复用
- US1 AC-11b（type 命名空间）：AC-11b 复用

**潜在风险**：
- **roles[] drag-reorder 的 undoStack 边界**：每次 reorder 触发 1 次 setDataMut，连续拖拽 5 次会塞 5 帧进 undoStack。spec US17 上限 20，但若与 customFields drag 混在同一 undoStack（共享），可能把用户的真实编辑操作挤出栈外。建议 dev 实现：`setDataMut` 内部检测连续 drag 操作的"批处理"语义（如 500ms 内的多个 drag 合并为 1 帧），但 spec 未要求，留 dev 自决。
- **字段必填 vs 选填的歧义**：spec 未明示 company / position / period / location / website.url / website.label / hidden 哪些必填。reactive-resume 实际全部选填（空字符串合法），建议 US2 同样接受空字符串（schema 已是 `str` 无 validator）。如 dev 引入必填，需在 AC 后续 round 补充。
- **顶层 `description` 与 `roles[]` 互斥的边缘**：用户在 roles 列表中有内容时切回顶层 description，会丢失 roles 数据。需 dev 在切换时 toast 警告"切换会清空 N 个 roles"，本 AC 未覆盖（建议 round 2 补）。
- **drag handle only within same section**：AC-09 已约束 experience items 不能拖到 education 容器，但若 dev 用全局 dnd-kit DndContext 包装整个左栏，需手动在 onDragEnd 内 `over.container.dataset.sectionKey` 判定。LayoutPanel 已实现该模式（AC-08b 教训），US2 可复用其 helper。

## Round 2 修订说明 (dev)

**轮次**：round 2
**触发**：Moderation Log 12 接受，R1-R11 全部需要 AC 衍生
**AC 总数变化**：15 → 26（+11 条）

**新增 AC**：
- **AC-04b** (R1) — 顶层 `description` 与 `roles[]` 互斥切换时数据保留（toast 警告 + 二次确认）
- **AC-08b** (R3) — drag-reorder 500ms 批处理合并为单帧 setDataMut + 单次 undo 恢复拖拽前顺序
- **AC-09b** (R2) — LayoutPanel column drag 与 item drag 通过 `data-dnd-context` 分属两个 DndContext 命名空间隔离
- **AC-09c** (R11) — item row 键盘可达性：tab focus + Space 抓取 + ArrowUp/Down 移动 + Space 确认（WCAG 2.1.1）
- **AC-11c** (R10) — grep 验证 DialogHost dispatcher 无 `default: return null` / `default: null` 静默吞错 fallback
- **AC-12b-extended** (R5) — item row 渲染无 `dangerouslySetInnerHTML`（`git grep` 静态检查 + DOM `querySelector('b')` 断言）

**修订 AC**（行内重写，编号不变）：
- **AC-02** (R8) — 扩 `crypto.randomUUID` mock 调用次数 === 1 + 连续 add 5 次后 5 个新 id 两两不等且与已有 id 互异
- **AC-10** (R9) — 删 `window.location.assign` 字样；duplicate 改为 store 内 push 深拷贝（id 全新 uuid，roles[] 元素深拷贝但新 role id）；新增 (e) `useDialogStore.getState().active === null` 断言
- **AC-11** (R4) — URL 白名单扩 `tel:` / `sms:` + regex 加 `u` flag（unicode / IPv6 支持）
- **AC-11b** (R10) — 步骤 (3) 加 `dialogHost dispatcher 接收未知 type 时 throw Error('unknown dialog type: ' + type)`（fail loud）
- **AC-12** (R5) — 扩覆盖 `website.label` / `website.inlineLink` / `hidden=true` 行渲染三路 XSS
- **AC-13** (R6) — 改 "1 次 undo" 为 "循环 undo 到 S0 deep equal"；验证步骤 (d) `N >= 1 && N <= 9`；注释 S0 是打开时记录的 snapshot
- **AC-15** (R7) — 扩三 case：(a) `hidden=true` 保留；(b) `description` PUT 后 GET 返 sanitized HTML 无 `<script>`；(c) `test_legacy_format.py` 新增 `test_experience_hidden_field_roundtrip` + `test_experience_description_html_sanitized`

**未修订 AC**：AC-01 / AC-03 / AC-04 / AC-05 / AC-06 / AC-07 / AC-08 / AC-09 / AC-12b / AC-14（R12 改判为"不修订由 reviewer 把关"，immer 引用一致性由 Phase 2 review 验证）

**目标 AC 锁定数**：26 条（AC-01..AC-15 + AC-02/04b/08b/09/09b/09c/10/11/11b/11c/12/12b/12b-extended/13/15 修订与新增）

**避坑自检**：
- [x] 所有新 AC 编号接续现有（无重复编号）
- [x] 每条新 AC 来源列填 "R{n} → AC-{xxx}" 格式
- [x] 未触碰 US1 的 BasicsDialog / PictureDialog 逻辑（无 import / 无修改）
- [x] 未触碰 DialogHost 已有的 `'basics'` / `'picture'` case
- [x] 沿用现有 `'experience.create'` / `'experience.update'` 命名（无 `.create` / `.update` 简写污染）
- [x] Moderation Log 段未修改（main-agent 写入区域）
- [x] 现有 AC-01..AC-15 仅 AC-02/AC-10/AC-11/AC-11b/AC-12/AC-13/AC-15 七条行内重写，其余不动

