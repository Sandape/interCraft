---
req_id: REQ-034-US4
title: Profile item dialog (network icon picker)
status: locked
round: 2
locked_at: 260629 1530
locked_by: negotiation
negotiation_rounds: 2
total_acs: 23
moderation_log: "Round 1: 15 反例 15 接受 / 0 部分接受 / 0 驳回；Round 2 必走 11 修订 + 3 新增（AC-05b/AC-12b/AC-16b），目标 22-25 AC 锁定"
parent_spec: specs/034-v2-reactive-resume-parity/spec.md
source_gap: memory/req_032_v2_vs_reactive_resume_gap.md (Gap #5 Profile item dialog + network icon picker)
---

# Acceptance Matrix for REQ-034-US4 — Profile item dialog (network icon picker)

## SC Gaps

- spec.md 行 33 给出 US4 标题 "Profile item dialog (network icon picker)"，但 spec §"Acceptance criteria" 段（行 64-66）整体写 TBD，未提供具体 SC 编号供 AC 反向溯源。下表来源以 "行 33 隐含" 标记。
- 隐含 SC（从 Bucket A row 4 + reactive-resume `dialogs/.../profile.tsx` + `backend/app/modules/resumes_v2/schemas.py` ProfileItem 推导）：
  - SC-4A: 左栏 Sections 面板中 "Profile" 行可展开，显示当前 `data.sections.profiles.items[]` 列表 + 一个 add-button
  - SC-4B: Profile item dialog 字段覆盖 `ProfileItem` interface 全部 7 个顶层键：`id / hidden / icon / iconColor / network / username / website{url,label,inlineLink}`（reactive-resume `profile.tsx:40-48` + schemas.py `ProfileItem` 定义）
  - SC-4C: 网络图标选择器（network icon picker）：用户点击 `icon` 字段触发 IconPicker 弹层（沿用 reactive-resume `IconPicker` 模式），选中后写入 `icon` 字段 + 在 `network` input 旁显示对应图标
  - SC-4D: section 内 items 支持 drag-reorder（dnd-kit，仅在同一 section 内；与 LayoutPanel 跨列拖拽隔离）
  - SC-4E: item row 暴露 edit / duplicate / delete 三个 inline action
  - SC-4F: section add-button 创建一个空 item 并打开 update dialog（type=`profile.update`，沿用 US2/US3 模式）
  - SC-4G: 所有写操作经 `useResumeV2Store.setDataMut`，触发 500ms debounce 自动保存，纳入 undoStack
  - SC-4H: dialog 关闭时 ESC + 点遮罩 + Cancel 三路一致；DialogHost 循环 undo 到 S0（沿用 US2 AC-13 revised + US3 AC-15）
  - SC-4I: dialog 内禁止本地 draft state（沿用 US1 AC-08c + US2 AC-14 + US3 AC-16 模式）
  - SC-4J: 复用 US3 的 `SectionItem` list-row wrapper（`src/modules/resume/v2/editor/left/SectionItem.tsx`，与 SectionList 同目录）
  - SC-4K: DialogHost dispatcher 扩展 2 case：`'profile.create' | 'profile.update'`
  - SC-4L: URL 验证沿用 US2 AC-11 revised + US3 AC-13：白名单 `^(https?|tel|sms|mailto):` + regex `u` flag，黑名单 `javascript|vbscript|file|data`；空字符串 url 视为合法

## AC 矩阵

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-01 | happy | 左栏 Sections 面板中 "Profile" 行可展开，显示当前 `data.sections.profiles.items[]` 列表 + 底部 add-button；list-row 复用 US3 创建的 `SectionItem` wrapper（`src/modules/resume/v2/editor/left/SectionItem.tsx`，与 SectionList 同目录，AC-19 显式约束路径） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/SectionsPanel.test.tsx -t "renders profile section list with shared SectionItem"` 期望：(a) 渲染 `[data-testid="profile-section-list"]` 容器节点；(b) 容器底部 add-button `profile-add-item` 存在；(c) 列表中 item row testid `profile-item-row-{id}` 存在；(d) `git grep -n "import.*SectionItem" src/modules/resume/v2/editor/left/ProfileSectionList.tsx` 期望引用 `../SectionItem`（与 US3 三个 SectionList 同 import 路径） | 列表渲染 + add-button 可见 + 共享 SectionItem | SC-4A + SC-4J + US3 AC-19 模式 |
| AC-02 | happy | 点击 add-button 触发 `openDialog({ type: 'profile.create', payload: { sectionId: 'profiles' } })` 派发；store 中追加空 item，schema 字段与 `ProfileItem` 对齐（`id / hidden:false / icon:'github' / iconColor:'#000000' / network:'' / username:'' / website:{url:'',label:'',inlineLink:false}`）；`icon` 默认 `'github'`（与 v2 默认对齐，**非** reactive-resume `'acorn'`，R8 修订）；`iconColor` 默认 `'#000000'`；`crypto.randomUUID` 恰好调用 1 次；连续 add 5 次后 5 个新 item id 两两不等且与已有 id 互异 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "add button creates item and opens create dialog"` 期望：(a) `vi.spyOn(crypto, 'randomUUID')` mock → fire click `profile-add-item` → `useDialogStore.active.type === 'profile.create'` 且 `data.sections.profiles.items.length +1`；新 item `icon='github'` / `iconColor='#000000'` / `network=''` / `username=''` / `website={url:'',label:'',inlineLink:false}` / `hidden=false`；(b) `mock.calls.length === 1`；(c) 连续 fire 5 次 → 长度 +5 且 `new Set(ids).size === 5` 且新 id 与旧 id 互异 | store 增空 item + dialog 打开 + uuid 唯一性 | SC-4B + SC-4F + SC-4K + US2 AC-02 模式 + R8 修订 |
| AC-03 | happy | 点击 item row 的 edit icon 打开 update dialog：`openDialog({ type: 'profile.update', payload: { sectionId: 'profiles', itemId: '<id>' } })`；dialog 打开后 store 内的 item 数据预填到表单（每个 input value === store.item 对应字段） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "update dialog prefills item state"` 期望：seed 一条 `network='GitHub', username='foo', website={url:'https://github.com/foo', label:'GitHub', inlineLink:true}` 后开 update dialog，断言 `screen.getByTestId('profile-network').value === 'GitHub'` / `profile-username` / `profile-website-url` / `profile-website-label` / `profile-website-inline-link` 全等 | dialog 表单读 store 状态 | SC-4B + SC-4F |
| AC-04 | happy | Profile dialog 字段映射：ProfileItem 顶层键 6 个表单输入（`hidden / icon / iconColor / network / username`，`id` 是 implicit 由 store 管理不算 input）+ 1 个 `website` nested model 含 3 sub-input（`url / label / inlineLink`）= **共 8 个 input testid**（R11 修订：明确"7 顶层 + 3 sub-input = 10 input testid" 修正为 6 顶层 + 3 sub-input = 8 input，**加上** 1 icon picker 触发器 `profile-icon-picker-trigger` + 1 color picker `profile-icon-color-picker` 渲染元素 = 8 渲染控件 testid）；snapshot 验证 testid 集合存在 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "renders all 6 top-level fields and 3 sub inputs"` 期望：snapshot 包含 `profile-hidden` (checkbox) / `profile-icon-picker-trigger` / `profile-icon-color-picker` / `profile-network` / `profile-username` / `profile-website-url` / `profile-website-label` / `profile-website-inline-link` (switch) 共 8 个 testid（**精确集合断言**：dev 实施时若误改 testid 命名则测试失败） | 字段齐全 + icon picker 触发器 | SC-4B + R11 修订 |
| AC-05 | happy | **Network icon picker 核心能力**：点击 `profile-icon-picker-trigger` 触发 IconPicker 弹层；弹层显示网络图标列表（GitHub / LinkedIn / Twitter / Website / Email / Phone / WeChat / 微博 等，reactive-resume IconPicker 模式，icon library 复用现有 `react-icons` 或 v2 已注册 icon 集合）；**弹层内含 fuzzy search input** `[data-testid="profile-icon-picker-search"]`（R2 修订：Fuse.js 模糊搜索，输入 `git` → 列表过滤剩 GitHub 匹配项），弹层列表（`[data-testid="profile-icon-picker"]`）显示当前过滤结果；选中一个图标后 IconPicker 关闭且 `data.sections.profiles.items[i].icon === <selected icon name>`；同时在 `network` input 旁显示对应图标的视觉标识 `data-testid="profile-network-icon-preview"` 含 `data-icon={icon}` 属性；**username 字段是 free-form 字符串**（R5 修订：任何字符合法，无 email/phone 格式校验，reactive-resume 模式）；**list row 渲染时若有 icon 显示对应图标** `data-testid="profile-network-icon-display"` + `data-icon={item.icon}` 属性（R9 修订：dialog 内 preview + list row 显示双重约束） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon picker opens fuzzy searches selects writes icon and previews in dialog and list row"` 期望：(a) fire click `profile-icon-picker-trigger` → 弹层节点 `[data-testid="profile-icon-picker"]` 出现且含 search input `[data-testid="profile-icon-picker-search"]`；(b) **fuzzy search**：input `git` → 弹层列表只剩 GitHub 匹配项（含 github icon cell），点击 github cell → `data.sections.profiles.items[0].icon === 'github'`；(c) `network` input 旁 `[data-testid="profile-network-icon-preview"]` 节点的 `data-icon="github"` 属性；(d) **username free-form**：input `foo@bar` / `+86-010-1234` / `李祖荫` 全接受（无红框 + 写 store）；(e) **list row icon 渲染**：seed item `icon='github', network='GitHub'` → 渲染 list row → `[data-testid="profile-network-icon-display"]` 节点存在且 `data-icon="github"` 属性 + 与 `network` 文本同排显示 | icon picker 弹层 + fuzzy search + 字段写入 + dialog preview + list row icon + username free-form | SC-4C + R2 + R5 + R9 修订 |
| AC-06 | happy | iconColor 字段通过 `profile-icon-color-picker` 选择颜色；ColorPicker 触发后弹出取色器（与 US1 PictureConfig.borderColor 共享同款 ColorPicker sub-component）；选中颜色后 `data.sections.profiles.items[i].iconColor === <rgba string>` 且在 icon 预览区显示对应颜色 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon color picker writes rgba and updates preview"` 期望：(a) fire click `profile-icon-color-picker` → 弹层节点出现；(b) 模拟选择 `#ff0000`（或 `rgba(255,0,0,1)`）→ 弹层关闭且 `iconColor === 'rgba(255,0,0,1)'`（沿用 PictureConfig 验证模式）；(c) `profile-icon-preview` 节点 `style.color` 或 `data-color` 属性反映新值 | color picker 行为正确 | SC-4B + US1 AC-05 模式 |
| AC-07 | happy | 顶层字段编辑经 `setDataMut` 落 store：修改 network / username / website.url / website.label / website.inlineLink / hidden 任一字段后 `useResumeV2Store.getState().data.sections.profiles.items[i].{field}` === 新值，且每次修改 `undoStack.length` +1（skipHistory:false 默认）；input onChange handler 直接调 setDataMut（无 useState 镜像） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "top-level field edit writes to store and pushes undo"` 期望：(a) 连续 5 字段 change 后 `data.sections.profiles.items[0].{network,username,website.url,website.label,website.inlineLink}` 全等新值且 `undoStack.length >= 5`；(b) 断言 onChange handler 直接调 setDataMut（无本地 useState 镜像，沿用 US3 AC-04/05/06 模式） | 字段直写 store + undoStack 累加 | SC-4B + SC-4G + US3 AC-12 模式 |
| AC-08 | edge | URL 验证：`website.url` 沿用 US2 AC-11 revised + US3 AC-13 模式：白名单 `^(https?|tel|sms|mailto):` + regex `u` flag（unicode / IPv6 支持），黑名单 `javascript|vbscript|file|data`；空字符串 url 视为合法；**username 字段是 free-form 字符串**（R5 修订：不做 email/phone 格式校验，任何字符合法） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "url scheme whitelist covers tel sms ipv6 unicode and username free form"` 期望：(a) 断言 `[data-testid="profile-website-url"]` 存在后再 input URL；(b) `https://[::1]:8080` / `tel:+86-010-1234` / `mailto:a@b.com` / `https://中文.cn` 接受（无红框 + 写 store）；(c) `javascript:alert(1)` / `data:text/html,...` / `file:///etc/passwd` 触发红框 + `fireToast('warn')` 且不写 store；(d) **username free-form**：`foo@bar` / `+86-010-1234` / `李祖荫` / `https://github.com/foo` 全接受（无红框 + 写 store） | URL 白名单 + unicode/IPv6 + username free-form | SC-4L + US2 AC-11 revised + US3 AC-13 模式 + R5 修订 |
| AC-09 | edge | `icon` 字段未知拒绝（**前端 defensive 校验**，R3 修订）：前端维护 `KNOWN_ICONS: string[]` 白名单（dev 自由发挥范围 30-200 个，**至少含** reactive-resume 常用 8 个：`github / linkedin / twitter / facebook / instagram / youtube / email / phone` + dev 扩展）；Pydantic schema **不变**（`IconName = Annotated[str, StringConstraints(min_length=1, max_length=64)]` 只约束长度不约束白名单，跨前后端契约：`icon` 白名单是 frontend-only）；`KNOWN_ICONS.length` 30-200 区间由 dev 自定；失焦时若 icon 不在 `KNOWN_ICONS` 内 → 红框 + `fireToast('warn', 'icon not in whitelist')` + **不写 store**；若在白名单内 → 写 store 接受 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon field unknown rejection with whitelist"` 期望：(a) `git grep -n "KNOWN_ICONS" src/modules/resume/v2/editor/dialogs/ProfileDialog.tsx` 期望 ≥ 1 hit（白名单数组显式声明）；(b) 模拟手输 `mynetwork`（不在白名单） → 红框 + `fireToast('warn', 'icon not in whitelist')` + **不写 store**；(c) 模拟手输 `github`（在白名单） → 接受 + 写 store；(d) 模拟手输 `linkedin`（在白名单） → 接受 + 写 store；(e) `KNOWN_ICONS.length` ≥ 30 且 ≤ 200（区间断言，dev 自由发挥但有上下界） | icon 字段白名单 + 前端 defensive 校验 | 自主发现: schemas.py IconName `min_length=1, max_length=64` 长度约束（**无白名单**）+ reactive-resume `IconPicker` 选中模式 + R3 修订 |
| AC-10 | edge | `iconColor` 字段格式校验：空字符串合法（与 US1 PictureConfig.borderColor 同款）；非 rgba 字符串（如 `'red'` / `'#fff'`）显示红框 + fireToast "warn" + 不写 store | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon color rejects non-rgba string"` 期望：(a) iconColor 留空合法（写 `''`）；(b) 模拟手输 `'red'` → 红框 + `fireToast('warn')` + 不写 store；(c) 模拟手输 `'#ff0000'` → 红框 + `fireToast('warn')` + 不写 store；(d) 模拟手输 `'rgba(255,0,0,1)'` 接受 | iconColor 格式校验 | 自主发现: schemas.py `RgbaColorStr` pattern 约束 |
| AC-11 | edge | item row 暴露 3 个 inline action：edit（铅笔图标）/ duplicate（拷贝图标）/ delete（垃圾桶图标）；edit 触发 update dialog（`profile.update`）；duplicate 通过 setDataMut 在 `data.sections.profiles.items` 末尾 push 一条**深拷贝**（R12 修订：7 字段全部 deep copy — `id` 全新 uuid / `icon` / `iconColor` / `network` / `username` 字符串 primitive + `website{url,label,inlineLink}` nested object 深拷贝 + `hidden` boolean；**新 item 引用与原 item 独立**，改新 item 任意字段不污染原 item），undoStack +1，**不打开** update dialog；delete 直接 setDataMut splice by id 且 `undoStack` +1 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "row inline actions edit duplicate delete deep copies all 7 fields"` 期望：(a) 每行 testid `profile-item-edit-{id}` / `-duplicate-{id}` / `-delete-{id}` 存在；(b) click edit → dialog type=`profile.update` payload.itemId===id；(c) click duplicate → `data.sections.profiles.items.length +1`，新 item `id !== 原 item.id` 且 `icon === 原 item.icon` / `iconColor === 原 item.iconColor` / `network === 原 item.network` / `username === 原 item.username` / `website{url,label,inlineLink}` 全部 deep equal 原 item；(d) **引用独立性**：新 item `website !== 原 item.website`（引用独立），改新 item `website.url = 'https://x.com'` → 原 item `website.url` 仍为原值（深拷贝有效）；(e) click delete → 长度 -1 且 undoStack +1；(f) **duplicate 后 `useDialogStore.getState().active === null`**（不打开 dialog） | 3 个 inline action 行为正确 + duplicate 深拷贝完整性 | SC-4E + US2 AC-10-revised + US3 AC-17 模式 + R12 修订 |
| AC-12 | state | section 内 items drag-reorder：左栏列表 items 之间 drag-reorder，模拟 onDragEnd 后 `data.sections.profiles.items` 顺序更新，**items[].id 集合保持不变**（沿用 US1 AC-04b + US2 AC-08b 模式 + REQ-033 第8轮 L 教训）；**不能跨 section**（R14 修订：显式 cast `data-dnd-context="profiles"` 命名空间隔离，沿用 US3 AC-17b 模式；onDragEnd 内 `over.data.current.droppableContainer.dataset.dndContext !== 'profiles'` 短路不触发 items 顺序更新，**4 个 SectionList (education/projects/skills/profile) 共存** 跨拖拽隔离）；500ms 内连续 N 次 onDragEnd 合并为单帧 setDataMut + 单次 undo 恢复拖拽前初始顺序 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "items drag reorder preserves ids batches 500ms and is scoped to profiles data-dnd-context"` 期望：(a) seed 3 items id=['p1','p2','p3'] → 模拟 onDragEnd `{active:'p3', over:'p1'}` → `items.map(i=>i.id) === ['p3','p1','p2']` 且 `new Set(ids) deep equal {'p1','p2','p3'}`；(b) **`data-dnd-context` 命名空间断言**：profile list 容器 `getAttribute('data-dnd-context') === 'profiles'`（R14 显式 cast）；模拟 onDragEnd `over.data.current.droppableContainer.dataset.dndContext === 'education'` → profile items 顺序未变（跨 section 短路）；同款覆盖 `projects` / `skills` 三个 SectionList（4 list 跨 section 隔离）；(c) `vi.advanceTimersByTime(500)` → 连续 5 次 onDragEnd → `undoStack.length === 1`（合并为单帧）；(d) `undoStack.at(-1).data.sections.profiles.items.map(i=>i.id) === ['p1','p2','p3']`（拖拽前初始顺序） | section 范围限定 + data-dnd-context 命名空间 + id 保留 + 500ms 批处理 + undo 完整恢复 | SC-4D + US2 AC-08b + US2 AC-09b + US3 AC-17b 模式 + R14 修订 |
| AC-13 | state | dialog 关闭（ESC / backdrop / Cancel）三路一致；DialogHost 在打开时记录 snapshot S0，关闭时若 setDataMut 已触发过则**循环 `undo()`** 直到 store 深等于 S0（沿用 US2 AC-13-revised + US3 AC-15 模式）；R7 修订：**不约束 keystroke 颗粒度**（不约束"5 帧保守估测"，沿用 US3 AC-15 修订），不硬约束 undo 调用次数 N 上限 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "close loops undo to pre-dialog snapshot S0 without keystroke granularity"` 期望：(a) 记录 S0 = `JSON.parse(JSON.stringify(useResumeV2Store.getState().data))`；(b) 改 3 字段 + 选 1 icon + 选 1 color（dev 自由发挥顺序与次数，**不约束颗粒度**）；(c) fire ESC / 点 backdrop / 点 Cancel 三路一致；(d) 循环 `undo()` 直到 `useResumeV2Store.getState().data` 深等于 S0，记录调用次数 N；断言 `N >= 1 && data deep equal S0`（**不硬约束 N 上限**） | 循环 undo 到 S0 + 不约束颗粒度 | SC-4H + US2 AC-13-revised + US3 AC-15 模式 + R7 修订 |
| AC-14 | state | dialog 内禁止本地 draft state（`useState` / `useReducer` 单独管理表单值再 onSave 一次性提交）；所有字段变更必须直接经 `setDataMut` 写入 `useResumeV2Store`（沿用 US1 AC-08c + US2 AC-14 + US3 AC-16 模式） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "no local draft state, undo restores pre-dialog snapshot"` 期望：(a) `git grep -n "useState\|useReducer" src/modules/resume/v2/editor/dialogs/ProfileDialog.tsx` 仅在 inline 红框错误状态（error display）出现，不在 field-level；(b) 改 3 字段 + 选 1 icon → close ESC → undo 1 → `data.sections.profiles.items[0]` deep equal 打开前 | 禁止本地 draft + undo 完整性 | SC-4I + US1 AC-08c + US2 AC-14 + US3 AC-16 模式 |
| AC-15 | error | XSS 注入：`network / username / website.label` 注入 `<script>alert(1)</script>` / `<img src=x onerror=alert(1)>` / `javascript:` scheme 渲染时不触发 alert；item row 渲染时所有用户输入字段走 React 文本节点，无 `dangerouslySetInnerHTML`（沿用 US2 AC-12-revised + US3 AC-14 模式） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "xss payloads escaped"` + `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "row renders fields without dangerouslySetInnerHTML"` 期望：(a) input payload 后断言渲染层 `[data-testid="profile-network"]` 元素 `textContent === payload`（不出现 `<script>` 解析为 DOM 节点）；(b) seed `network='<b>X</b>'` → render row → `row.textContent === '<b>X</b>'` 且 `row.querySelector('b') === null`（无 innerHTML 解析）；(c) `git grep -n "dangerouslySetInnerHTML" src/modules/resume/v2/editor/left/ProfileSectionList.tsx` 期望 0 hits | XSS 转义 + 无 dangerouslySetInnerHTML | US1 AC-09 + US2 AC-12-revised + US2 AC-12b + US3 AC-14 模式 |
| AC-16 | state | `openDialog` type 命名空间遵守 `{section}.{verb}` 格式（沿用 US2 AC-11b-revised + US3 AC-18 模式）：`'profile.create'`（add-button 触发） / `'profile.update'`（edit 触发）；无 `'profile.delete'`（delete 走 inline 不进 dispatcher，沿用 US2/US3 模式）；dispatcher switch 必须覆盖新增 2 case，`DialogType` union 同步扩展；**default 分支 throw Error**（fail loud 而非静默 `return null`，沿用 US2 AC-11b-revised + US2 AC-11c + US3 AC-18）；R15 修订：**接受 dev 走"profile dialog + 2 case 显式"或"profile + 1 case helper 共享"二选一**（沿用 US3 AC-18b 模式，dev 自决可维护性 vs 命名空间清晰）；US4 不强制 case 数 2 个独立 | (1) `git grep -n "openDialog\|DialogType" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 case 字符串集合 `{'basics', 'picture', 'experience.create', 'experience.update', 'education.create', 'education.update', 'projects.create', 'projects.update', 'skills.create', 'skills.update', 'profile.create', 'profile.update'}`（**或** dev 走共享 helper `case 'profile.create': case 'profile.update': return <ProfileDialog mode=... />` 模式，case 字符串命中 ≥ 1 hit）；(2) `git grep -n "'profile\.create-item'\|'profile\.update-item'\|'profile\.add'\|'profile\.edit'\|'profile\.delete'" src/` 期望 0 hits；(3) `git grep -n "default: return null\|default: null" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 0 hits；(4) `npx vitest run src/modules/resume/v2/editor/dialogs/DialogHost.test.tsx -t "profile verb namespaced and unknown throws"` 期望：openDialog({type:'profile.unknown'}) 后 `expect(() => DialogHost render).toThrow(/unknown dialog type/)` | type 命名空间扩展 + fail loud + 共享 helper 模式可选 | SC-4K + US1 AC-11b + US2 AC-11b-revised + US2 AC-11c + US3 AC-18 模式 + R15 修订 |
| AC-17 | happy | 命名导出 + 共享 wrapper：`export function ProfileDialog(props)` / `export function ProfileSectionList(props)`（L009 必避陷阱）；consumer（DialogHost 内部 dispatcher + SectionsPanel）通过 `import { ProfileDialog } from "./ProfileDialog"` 命名导入；`SectionItem` 路径显式约束为 `src/modules/resume/v2/editor/left/SectionItem.tsx`（与 US3 SectionList 同目录，AC-19 唯一性约束 + US3 R13 修订）；`git grep -n "export default function ProfileDialog\|export default function ProfileSectionList" src/modules/resume/v2/editor/` 0 hits；`ls src/modules/resume/v2/editor/dialogs/*.ts` 验证无 shadow（沿用 L008 必避陷阱） | 静态检查：(1) `git grep -n "export default function ProfileDialog\|export default function ProfileSectionList" src/modules/resume/v2/editor/` 期望空输出；(2) `ls src/modules/resume/v2/editor/dialogs/*.ts` 期望空（仅 .tsx 存在，避 L008 shadow）；(3) `find src -name "SectionItem.tsx" \| wc -l === 1` 唯一性断言（沿用 US3 R13）；(4) `git grep -l "import.*SectionItem" src/modules/resume/v2/editor/left/` 期望 ≥ 4 hits（education/projects/skills 3 list + profile 1 list = 4 hits） | 命名导出 + 无 shadow + SectionItem 路径唯一 | SC-4J + L008 + L009 + US3 AC-19 模式 |
| AC-18 | happy | Backend round-trip：**6 子 case** `test_legacy_format.py` 新增（R10 修订：沿用 US3 AC-20 R15 扩 6 子 case 模式）：(a) `test_profile_full_roundtrip` — PUT 一条 2 item profile payload（含 `icon / iconColor / network / username / website{url,label,inlineLink}`）→ GET 200 → 字段全 deep equal；(b) `test_profile_url_scheme_whitelist_and_blacklist` — PUT `website.url='https://github.com/foo'` / `'tel:+86-010-1234'` / `'mailto:a@b.com'` → GET 200（白名单接受）；PUT `website.url='javascript:alert(1)'` → 后端 422（黑名单拒绝） + PUT `website.url=''` → GET 200（空串合法）；(c) `test_profile_hidden_field_roundtrip` — PUT `hidden=true` → GET 200 → hidden 保留；(d) `test_profile_icon_whitelist_passthrough` — PUT `icon='my-unknown-icon-xyz'` → GET 200（**backend 不拒**，frontend AC-09 拒；跨前后端契约：`icon` 白名单是 frontend-only）；(e) `test_profile_icon_color_rgba_roundtrip` — PUT `iconColor='rgba(255,0,0,1)'` → GET 200；PUT `iconColor='#ff0000'` → 后端 422（Pydantic RgbaColorStr pattern 拒绝）；PUT `iconColor=''` → GET 200（空串合法）；(f) `test_profile_username_free_format_passthrough` — PUT `username='<script>alert(1)</script>'` / `'foo@bar'` / `'+86-010-1234'` / `'李祖荫'` → GET 200（**backend 不 escape，frontend 渲染期 escape**，XSS 不在 backend 防御范围，验证 frontend 收到 raw payload 即可渲染期 escape） | `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py -v -k "profile"` 期望 pass（**6 case**） | round-trip 完整 + url 白名单 + hidden + icon 白名单 + iconColor + username 自由格式 | SC-4B + SC-4L + L005 教训 + US1 AC-15 + US2 AC-15-revised + US3 AC-20 模式 + R10 修订 |
| AC-19 | edge | `hidden=true` 的 profile item 在 SectionList 渲染为视觉淡化行（`data-hidden="true"` 属性 + 文本节点保留 + **整行所有子节点含 icon 灰显**，R13 修订：沿用 US3 AC-04c/05c/06c 模式，row 的 `style.opacity` 覆盖所有子节点包括 `profile-network-icon-display` icon 节点） | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "profile hidden true renders as faded row incl icon and text"` 期望：(a) seed `profiles.items=[{id:'pr1', hidden:true, icon:'github', network:'GitHub'}]` → 渲染列表 → row 节点存在 `querySelector('[data-testid="profile-item-row-pr1"]')` 不为 null；(b) 该 row 含 `data-hidden="true"` 属性 + `style.opacity < 1`（dev 自定具体值如 0.5）；(c) **`profile-network-icon-display` icon 节点** opacity < 1（被父 row opacity 覆盖 或自身 style.opacity < 1，dev 自定实现路径）；(d) `row.querySelector('[data-testid="profile-network-display"]').textContent === 'GitHub'`（仍渲染文本节点，非完全隐藏） | profile hidden=true 视觉淡化 + 文本保留 + icon 灰显 | US2 AC-12-revised + US3 AC-04c/05c/06c 模式 + R13 修订 |
| AC-20 | edge | network 字段长度约束（R4 修订：**删** `min_length=1` 约束，与 `schemas.py` `ProfileItem.network: str` 实际**无 min_length** 对齐 + reactive-resume `defaultValues.network: ""` 一致）：`network.length ∈ [0, 64]`（空字符串合法，**最长 64** 仅作 max 限制）；超长 network（1000 字符）截断或拒绝并 fireToast "warn"；空字符串合法（add-button 创建空 item 默认 `network=''` 不红框） | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "network field length validation accepts empty and rejects overlong"` 期望：(a) input 1000 字符 network → 失焦后 fireToast "warn" 且不写 store（或截断至 64 字符，dev 自定但需在 dialog 提示）；(b) input 空 network `''` → 合法 + 不红框 + 写 store（与 R4 修订一致 + reactive-resume defaultValues 一致）；(c) add-button 创建空 item 后 dialog 打开 → `network=''` 合法初始态（无红框） | network 长度 0-64 上限 + 空字符串合法 | 自主发现: schemas.py `ProfileItem.network: str` **无 min_length/max_length** 实际约束 + reactive-resume `defaultValues.network: ""` + R4 修订 |
| AC-21 (新) | edge | **IconPicker 关闭语义**（R1 新增）：IconPicker 弹层是 controlled-popover 模式（沿用 reactive-resume `icon-picker.tsx` PopoverTrigger 触发 + PopoverContent 独立，无内置 onClose 提交）；**关闭 picker 路径**（fire keyDown ESC / 点遮罩 / 点 Cancel）**不写字段**（不自动提交 last-hovered cell），**点确认按钮才写**；reactive-resume IconPicker 模式下用户必须显式 click 一个 cell 触发 `onChange` 才会写入 `icon` 字段 | `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon picker close without selection does not mutate icon field"` 期望：(a) seed `icon='github'` → fire click `profile-icon-picker-trigger` 打开 popover → fire keyDown ESC 关闭 → `data.sections.profiles.items[0].icon === 'github'`（未变）；(b) 同上但 fire click backdrop 关闭 popover → 仍为 `'github'`；(c) 同上但 fire click Cancel 按钮关闭 popover → 仍为 `'github'`；(d) `fireToast` 不被调用（无 toast 噪声） | IconPicker 关闭不写字段 + last-hovered 静默污染防御 | R1 blocker 命中 + reactive-resume `icon-picker.tsx` controlled-popover 模式 |
| AC-22 (新) | state | **profile item row 键盘可达性**（R6 新增，沿用 US2 AC-09c 模式）：item row 可被 tab focus；focus 后按 Space 进入 drag mode；ArrowUp/ArrowDown 移动顺序；Space 确认放置；与 US3 AC-12 沿用 US2 模式但未显式 cast 互补 — 未来 US4 + US5 7 个 SectionList 都需 keyboard fallback 显式覆盖 | `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "item row keyboard reorder via space and arrow keys"` 期望：(a) seed 3 items id=['p1','p2','p3'] → focus `[data-testid="profile-item-row-p2"]` → fire keyDown Space 进入 drag mode（`aria-grabbed="true"` 或 `data-dragging="true"` dev 自定）；(b) fire keyDown ArrowUp → `items.map(i=>i.id) === ['p2','p1','p3']`；(c) fire keyDown Space 确认放置 → `aria-grabbed` 取消 + 顺序稳定 | profile item row 键盘可达性（Space 抓取 + Arrow 移动 + Space 确认） | R6 major 命中 + US2 AC-09c 模式 |
| AC-23 (新) | state | **dispatcher 共享 helper vs 显式 2 case 二选一**（R15 新增，沿用 US3 AC-18b 模式）：dev 实施时可选 (a) **共享 helper 模式**：`case 'profile.create': case 'profile.update': return <ProfileDialog mode={...} />` 一段代码，case 字符串命中 ≥ 1 hit；(b) **显式 2 case 模式**：`case 'profile.create': return <ProfileDialog mode="create" />; case 'profile.update': return <ProfileDialog mode="update" />` 两段独立代码，case 字符串命中 2 hits；两种模式 AC-16 验证步骤 (1) 都接受，dev 自决可维护性 vs 命名空间清晰；**US4 不强制 case 数 2 个独立** | (1) `git grep -n "case 'profile\.create'\|case 'profile\.update'" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 ≥ 1 hit（共享 helper 模式命中 1 行 `case 'profile.create': case 'profile.update':` 或显式 2 case 命中 2 行）；(2) `npx vitest run src/modules/resume/v2/editor/dialogs/DialogHost.test.tsx -t "profile create and update both render ProfileDialog"` 期望：openDialog({type:'profile.create'}) 和 openDialog({type:'profile.update'}) 都成功渲染 ProfileDialog 组件；(3) US4 不强制 case 数 2 个独立（接受 1 行共享或 2 行显式） | dispatcher 共享 helper vs 显式 2 case 二选一 | R15 blocker 命中 + US3 AC-18b 模式 |

## 起草说明（写给 tester）

**设计意图**：
- US4 范围严格限定 Profile section 的 item dialog + 列表 + add-button；不触碰 Education/Project/Skill（US3 已 ship）/ Language/Interest/Award/Certification/Publication/Volunteer/Reference（US5 范围）。
- 复用 US3 已 ship 的 `SectionItem` wrapper（`src/modules/resume/v2/editor/left/SectionItem.tsx`）作为 list-row 包装器（dnd-kit item drag + 3 inline action: edit/duplicate/delete），不再新建独立 wrapper。
- 复用 US2/US3 `useResumeV2Store.setDataMut(draft => {...})` 模式，所有写操作自动获得 500ms debounce autosave + undoStack + redoStack + 30min TTL。
- **Network icon picker 核心**（AC-05）：复用 reactive-resume `IconPicker` 模式（`@/components/input/icon-picker` 思路，icon library 来自 `reactive-resume/schema/icons` 集合）—— 用户点 `profile-icon-picker-trigger` 触发 IconPicker 弹层，弹层显示网络图标列表（GitHub / LinkedIn / Twitter / Website / Email / Phone / WeChat / 微博 等），选中后写入 `icon` 字段 + 在 `network` input 旁显示对应图标 + 在 list row 显示网络图标。
- icon library 来源待 dev 探查：v2 当前是否已注册 `react-icons` 或自有 icon collection？reactive-resume 用 `@phosphor-icons/react`（约 9000+ 图标）+ `IconPicker` 弹层。v2 US4 实施时需 dev 决定：**(a) 沿用 reactive-resume IconPicker 完整实现 + 引入 phosphor-icons 依赖**（与 spec 措辞"reactive-resume IconPicker 模式"一致），或 **(b) 复用 v2 已有的 `IconPicker` 组件**（若 v2 已有此组件，避免新增依赖）。本 AC 矩阵**接受路径分歧**，但 AC-05 验证 step 期望 IconPicker 行为与 reactive-resume 一致（弹层 + 搜索 + 选中 + 写入字段 + 视觉预览）。
- `iconColor` ColorPicker 沿用 US1 PictureConfig.borderColor 模式（与 PictureConfig 共用同款 ColorPicker sub-component），不在 US4 新建。
- `website` 字段（`url / label / inlineLink`）沿用 US2/US3 模式（`ItemWebsite` schema 已支持，无需 schema 变更）。
- item row 3 个 inline action：edit 进 dispatcher，duplicate 走 setDataMut store 内 push 深拷贝（沿用 US2 AC-10-revised + US3 AC-17 模式，**不走** `window.location.assign`），delete 直接 setDataMut splice by id。
- dnd-kit 拖拽用 swap-id 而非 splice 重建数组（保留 id 集合），与 US1 AC-04b + US2 AC-08b + US3 AC-09 同款约束。
- dispatcher 扩展 2 case `'profile.create' | 'profile.update'`，沿用 US1 AC-11b + US2 AC-11b-revised + US3 AC-18 命名空间格式 `{section}.{verb}`；default 分支 throw Error（fail loud），无静默吞错。
- dialog 关闭走 DialogHost 循环 undo 到 S0（沿用 US2 AC-13-revised + US3 AC-15 修订，**不硬约束 N 上限**）；禁止本地 draft state（沿用 US1 AC-08c + US2 AC-14 + US3 AC-16）。
- Backend round-trip 在 `test_legacy_format.py` 新增 3 case（沿用 US1 AC-15 + US2 AC-15-revised + US3 AC-20 模式），`ResumeDataV2Pydantic` 已支持 ProfileItem（spec 行 73-74 隐含），无 backend 代码变更。

**已覆盖的边界**：
- Profile section list 渲染 + add-button（AC-01）
- add-button 触发 create dialog + uuid 唯一性（AC-02）
- edit icon 触发 update dialog + 表单预填（AC-03）
- 7 个顶层字段 + website 3 sub-input 字段映射完整（AC-04）
- **Network icon picker 核心能力**（AC-05）— 这是 US4 核心新增能力
- iconColor ColorPicker 行为（AC-06）
- 字段直写 store + undoStack 累加（AC-07）
- URL 白名单 + unicode/IPv6 支持（AC-08）
- icon 字段越界（空 + 未知）拒绝（AC-09）
- iconColor 格式校验（rgba 字符串 + 空合法）（AC-10）
- 3 个 inline action edit/duplicate/delete（AC-11）
- section 内 items drag-reorder + 跨 section 隔离 + 500ms 批处理（AC-12）
- dialog 关闭循环 undo 到 S0（AC-13）
- 禁止本地 draft state（AC-14）
- XSS 注入覆盖 + 无 dangerouslySetInnerHTML（AC-15）
- dispatcher 2 case 扩展 + fail loud（AC-16）
- 命名导出 + 无 shadow + SectionItem 路径唯一（AC-17）
- Backend round-trip 3 case（AC-18）
- hidden=true 视觉淡化行（AC-19）
- network 字段长度约束（AC-20）

**未覆盖的边界（已知风险）**：
- **icon library 来源未定**：v2 当前是否已注册 phosphor-icons / react-icons / 自有 icon collection？AC-05 验证期望 IconPicker 弹层行为与 reactive-resume 一致（弹层 + 搜索 + 选中 + 写入字段 + 视觉预览），但具体图标列表内容由 dev 自决（GitHub / LinkedIn / Twitter / Website / Email / Phone / WeChat / 微博 等"网络"图标子集）。建议 dev 优先复用 v2 已有的 `IconPicker` 组件（若存在），不引入新依赖。
- **`icon` 字段写入手动 vs picker 选择**：AC-05 描述"picker 选中后写入 icon 字段"，但用户可能手动 input icon name（绕过 picker）。AC-09 覆盖空 + 未知 icon name 拒绝，但 dev 是否需要同时支持 picker 选择 + 手动 input 双模式（reactive-resume 同款）由 dev 自决，AC 不约束。
- **profile item 与 section header 的图标关联**：list row 显示 network 图标（`item.icon`），但 section header（"Profile" 行）是否也用统一 icon 由 dev 沿用 US3 SectionsPanel 模式。
- **CSS color picker 组件复用**：AC-06 期望"与 US1 PictureConfig.borderColor 共享同款 ColorPicker sub-component"，但 v2 当前是否有 ColorPicker 组件待 dev 探查。若不存在，dev 可新建（spec P1 范围外，但 US4 实施需要）。
- **多个 profile item 渲染时 `inlineLink=true` 行为**：US2/US3 模式未约束，US4 沿用相同 default。
- **profile section 是否需要 profile-level `columns` 字段**（reactive-resume schema 支持 profiles section columns，v2 Pydantic schema 行为待 dev 探查）：US4 范围限定 item-level 字段，不触碰 section-level `columns`。
- **iconColor 字段是否需要留空**（reactive-resume 实际接受 `iconColor=''` 合法）：AC-10 步骤 (a) 已约束。
- **IconPicker 弹层搜索功能**：reactive-resume `IconPicker` 支持 fuzzy search（Fuse.js），US4 是否需要同款搜索由 dev 自决（reactive-resume IconPicker.tsx 行 71-80 实现 `useIconSearch`）。
- **IconPicker 弹层中的"网络"图标分类**：reactive-resume IconPicker 显示所有 icons（约 9000+），US4 是否需要"网络"图标子集（GitHub / LinkedIn / Twitter 等）由 dev 自决。AC-05 验证期望至少 GitHub 图标可被选中。

**必避陷阱已在 AC 中显式 cast 死**：
- L008（module shadow）：AC-17 显式 `ls src/modules/resume/v2/editor/dialogs/*.ts` 验证无 shadow
- L009（default vs named export）：AC-17 静态检查
- L004b（dnd-kit 教训）：AC-12 显式要求 `useSortable` mock 模式 + onDragEnd 触发
- L005（ship HTTP probe）：AC-18 触发真实 backend pytest round-trip
- US1 AC-08b（关闭撤销）：AC-13 复用
- US1 AC-08c（禁止本地 draft）：AC-14 复用
- US1 AC-11b（type 命名空间）：AC-16 复用
- US1 AC-04b / US2 AC-04b / US3 AC-09（id 保留规则）：AC-12 复用
- US1 AC-06（数值字段 clamp + NaN 拒绝）：AC-10 复用 rgba 模式
- US1 AC-09 / US2 AC-12 / US3 AC-14（XSS 转义）：AC-15 复用
- US2 AC-08b（拖拽批处理）：AC-12 复用
- US2 AC-09b（跨 section 拖拽隔离）：AC-12 复用
- US2 AC-09c（键盘可达性）：未在 US4 AC 矩阵中显式覆盖，建议 dev 沿用 US2 模式（list-row Space 抓取 + ArrowUp/Down 移动 + Space 确认），待 tester round 1 反驳时补
- US2 AC-10-revised（duplicate 走 store 推送）：AC-11 复用
- US2 AC-11-revised（URL 白名单 + u flag）：AC-08 复用
- US2 AC-11b-revised（default throw）：AC-16 复用
- US2 AC-11c（grep 验证无 default: return null）：AC-16 复用
- US2 AC-12-revised（hidden=true 视觉淡化）：AC-19 复用
- US2 AC-13-revised（循环 undo 到 S0）：AC-13 复用
- US2 AC-14（无本地 draft state）：AC-14 复用
- US3 AC-04c/05c/06c（hidden 视觉淡化）：AC-19 复用
- US3 AC-15（循环 undo 删 N 上限硬约束）：AC-13 复用
- US3 AC-16（3 dialog 文件全 grep useState/useReducer）：AC-14 复用
- US3 AC-17b（跨 section 拖拽隔离）：AC-12 复用
- US3 AC-18（dispatcher 6 case 扩展 + fail loud）：AC-16 复用
- US3 AC-19（SectionItem 路径唯一）：AC-17 复用
- US3 AC-20（Backend round-trip 多 case）：AC-18 复用

**潜在风险**：
- **Network icon picker 列表来源（沿用 reactive-resume vs 自定义）**：AC-05 描述"复用 reactive-resume IconPicker 模式（无需新增 react-icons 包）"，但 v2 当前是否有 `IconPicker` 组件待 dev 探查。若不存在，dev 需决定：(a) 引入 `@phosphor-icons/react` + 实现完整 IconPicker（与 reactive-resume 一致）；(b) 复用 v2 已有的 minimal icon set + 简化 IconPicker 弹层；(c) 直接 hardcode 8-12 个网络图标作为下拉选择（不实现 popover）。三种路径都满足 AC-05 验证（picker 弹层 + 选中 + 写入字段 + 视觉预览），但实施成本差异大。建议 dev 在实施前先 grep v2 现有 icon 资源（`src/modules/resume/v2/editor/left/` / `src/components/`）决定。
- **iconColor ColorPicker 组件复用**：AC-06 期望"与 US1 PictureConfig.borderColor 共享同款 ColorPicker sub-component"，但 US1 PictureConfig 当前是否使用真实 ColorPicker 待 dev 探查（reactive-resume 同款 `ColorPicker` 组件）。若 v2 暂用 simple HTML5 `<input type="color">`，AC-06 验证可简化为"input type=color 触发颜色选择 + 写入 rgba 字符串"。
- **profile item `website.url` 长度限制**：AC-08 步骤 (c) 期望黑名单拒绝 `javascript:` / `data:` / `file:` 协议，但 `mailto:` / `tel:` / `sms:` 与 `https?:` 接受（沿用 US2 AC-11-revised）。若 dev 实现 Pydantic schema level 拒绝（`HttpUrl`），AC-18 case (c) 期望后端 422 即可。
- **`icon` 字段类型 Pydantic 约束**：`IconName = Annotated[str, StringConstraints(min_length=1, max_length=64)]`（schemas.py），无 icon 白名单 Pydantic 约束，icon 是否合法由 IconPicker 弹层保障（用户只能从合法图标集合选）。AC-09 约束"手动 input 任意不存在的 icon name 失焦时显示红框"是前端 defensive 校验，不依赖 Pydantic。
- **`iconColor` 字段 Pydantic 约束**：`RgbaColorStr` pattern 约束（`r,g,b,a` 格式），AC-10 约束"非 rgba 字符串拒绝"由前端 + 后端双重防御。
- **US4 与 US5（Language/Interest/Award/Certification/Publication/Volunteer/Reference）边界**：US4 范围仅含 Profile section，US5 处理剩余 7 个 section。本 AC 矩阵 dispatcher 仅扩展 2 case，US5 时再扩展。
- **ProfileItem 字段顺序与 reactive-resume 一致性**：reactive-resume `profile.tsx:40-48` defaultValues 顺序为 `id / hidden / icon / iconColor / network / username / website`，与 Pydantic schema 一致；AC-04 验证步骤不约束字段渲染顺序（仅约束 testid 集合存在），dev 沿用默认顺序即可。
- **US4 + US3 dispatcher 共享 helper 模式**：US3 AC-18b 接受"3 dialog + 6 case vs 共享 helper"二选一，US4 dispatcher 2 case 也可走"profile.create / profile.update 共享同一组件但 mode 不同"或"2 case 显式"。建议 dev 沿用 US3 R5 修订模式，二选一自决可维护性 vs 命名空间清晰。

## Tester 反驳日志

### R1: [AC-05] IconPicker 弹层关闭后 network 字段留空未约束 — 关 picker 取消选择无 toast
- **目标 AC**: AC-05
- **反驳类型**: 边界 / 覆盖缺失
- **反例描述**: reactive-resume `icon-picker.tsx` 弹层点空白处或按 ESC 关闭 popover **不**自动写入 `icon` 字段（用户必须显式 click 一个 cell 触发 `onChange`）。US4 AC-05 仅约束"选中后 IconPicker 关闭且 icon 字段写入"，**未约束**：用户点开 picker 后**不选**直接 ESC / 点遮罩 / 点 Cancel 关闭 picker 的边界 — 此刻用户期望"无变化"，但 dev 若错误实现"popover open → 选 cell 立刻写字段，关闭时把 last-hovered cell 当 selected 写字段"，会导致用户取消 picker 时 network 字段被静默写入（与 US3 AC-13b "useFormBlocker 拦截未提交"模式偏离）
- **影响**: blocker
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon picker close without selection does not mutate icon field"` 期望：(a) seed `icon='github'` → fire click `profile-icon-picker-trigger` 打开 popover → fire keyDown ESC 关闭 → `data.sections.profiles.items[0].icon === 'github'`（未变）；(b) 同上但 fire click backdrop → 仍为 'github'；(c) `fireToast` 不被调用
- **建议**: 修订 AC-05：增加 "popover 关闭不选不写字段" 步骤；step (b) 显式断言 "click backdrop / ESC 关闭 popover → icon 字段保持原值"；reactive-resume IconPicker 是 controlled-popover 模式（PopoverTrigger 触发 + PopoverContent 独立，无内置 onClose 提交）

### R2: [AC-05] IconPicker 搜索功能 (Fuse.js fuzzy search) 完整覆盖未约束 — 9000+ 图标列表无搜索等于不可用
- **目标 AC**: AC-05
- **反驳类型**: 覆盖缺失 / 不可执行
- **反例描述**: reactive-resume `icon-picker.tsx:71-83` 显式实现 `useIconSearch` (Fuse.js fuzzy search) + `IconSearchInput` 搜索 input（`apps/web/src/components/input/icon-picker.tsx` 行 24-42），icon library 共约 9000+ 图标（`@phosphor-icons/react` 全集）。US4 AC-05 验证步骤只断言 `(a)` 打开 popover / `(b)` 选中 github 写入字段 / `(c)` 预览显示，**完全忽略搜索功能**：若 dev 直接 hardcode 8-12 个网络图标作为下拉（按"潜在风险"段 137 行的路径 (c) 实施），用户想找"Stack Overflow"图标必须滚 8-12 项勉强找到，但用户想找"知乎"或"掘金"等 dev 未预置的网络图标 → **AC-05 通过但实际 UI 不可用**
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon picker search filters by fuse fuzzy match"` 期望：(a) 打开 popover → `[data-testid="profile-icon-picker-search"]` 搜索 input 存在；(b) input "github" → 列表只剩 github 一个 cell 或 icon 名包含 "github" 的子集（阈值 0.35，沿用 reactive-resume）；(c) 清空 input → 恢复完整列表
- **建议**: 修订 AC-05：增加 "IconPicker 弹层提供 fuzzy search input" 步骤；测试断言 (a) `[data-testid="profile-icon-picker-search"]` 存在；(b) input "linkedin" → 列表 ≤ 5 项（含 linkedin icon）；(c) dev 实施路径分歧：若 dev 走路径 (a) 引入 phosphor-icons 必须有 Fuse.js 搜索；若走路径 (c) hardcode 8-12 图标，AC 应显式说明"接受路径 (c) 但 dev 必须保证 social-network 主流图标集 ≥ 12 个"（GitHub/LinkedIn/Twitter/微博/微信/知乎/掘金/Facebook/Instagram/YouTube/Email/Phone 至少 12 项）

### R3: [AC-09] icon 字段"未知拒绝"语义模糊 — Pydantic 无白名单约束下 dev 实现路径分歧未明
- **目标 AC**: AC-09
- **反驳类型**: 模糊 / 不可执行
- **反例描述**: AC-09 写"`icon` 字段越界：IconPicker 选中的 icon name 必须在白名单内（reactive-resume schema 限制 1-64 字符）" + "手动 input 任意不存在的 icon name（如 `'non-existent-icon-xyz'`）失焦时显示红框"。但 `backend/app/modules/resumes_v2/schemas.py` `IconName = Annotated[str, StringConstraints(min_length=1, max_length=64)]`（行 33）**只约束长度不约束白名单**，任何 1-64 字符字符串 Pydantic 都接受。AC-09 步骤 (b) 期望"手输 `'non-existent-icon-xyz'` 红框" → 长度合法 19 字符，Pydantic 接受，前端需另建 icon 白名单数组（如 reactive-resume `icons` 全集 9000+）。**歧义**：(a) dev 是否需要在前端维护一份 icon name 白名单数组（与 phosphor-icons 同步）？(b) "白名单"范围是 phosphor-icons 全集 9000+ 还是社交网络子集 ~30 个？(c) "未知拒绝" 是 `fireToast('warn')` 红框还是静默忽略写 store？
- **影响**: blocker
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon field unknown rejection with whitelist"` 期望：(a) dev 维护 `PROFILE_ICON_WHITELIST` 数组；(b) 手输 `'facebook'`（在白名单）接受 + 写 store；(c) 手输 `'myspace'`（不在白名单）红框 + `fireToast('warn', 'icon not in whitelist')` + 不写 store；(d) `git grep -n "PROFILE_ICON_WHITELIST\|ICONS_WHITELIST" src/modules/resume/v2/editor/dialogs/ProfileDialog.tsx` 期望 ≥ 1 hit
- **建议**: 修订 AC-09：显式定义 icon 白名单范围（建议：reactive-resume `icons` 全集 ≥ 200 个常用图标；或显式声明接受"AC 起草时 dev 自定白名单范围 ≥ 12 个社交网络图标"）；明确"未知拒绝" 行为 = 红框 + fireToast('warn', 'icon not in whitelist') + 不写 store；新增 step (c) 验证 "在白名单内（如 'linkedin'）手输接受 + 写 store"

### R4: [AC-20] network 字段长度约束 1-64 与 reactive-resume 默认值 '' 矛盾 — 空 network 是合法 Pydantic 但 AC-09/AC-20 双重约束冲突
- **目标 AC**: AC-20 + AC-09
- **反驳类型**: 矛盾 / 覆盖缺失
- **反例描述**: `backend/app/modules/resumes_v2/schemas.py` `ProfileItem.network: str`（行 165，**无 min_length / max_length 约束**），Pydantic 接受任意字符串（含空串）。reactive-resume `profile.tsx:45` defaultValues `network: ""`（空字符串合法默认值，reactive-resume 实际接受 `network=''` + 用户后续填）。但 US4 AC-20 写"`network.length ∈ [1, 64]`（与 schemas.py `IconName` / 类似 str 字段约束一致）" — 引用的是 `IconName`（min_length=1）的约束，**但 ProfileItem.network schema 实际无 min_length=1**。同时 AC-09 步骤 (a) 期望"network 字段手输 `''` 红框"（沿用 icon 字段模式），与 AC-02 期望"add-button 触发空 item 含 `network=''`"（合法初始值）矛盾 — dev 实施时 add-button 创建空 item 后 dialog 打开立刻显示红框（用户体验差）
- **影响**: blocker
- **验证命令**: `grep -n "network: str" backend/app/modules/resumes_v2/schemas.py` 验证 schema 无 min_length 约束；`npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "network empty is valid initial value"` 期望：(a) add-button → 打开 dialog → `network=''` 不红框 + 不 fireToast（合法初始态）；(b) 用户清空已填 network → 不红框（允许清空）；(c) 用户填 1000 字符 → 失焦 fireToast + 不写 store
- **建议**: 修订 AC-20：去掉 `min_length=1` 约束（与 schema 实际一致），改 `network.length ∈ [0, 64]`；AC-09 步骤 (a) 改为 "icon 字段空拒绝" 而**非** network 字段空拒绝；新增 AC-09b / 合并到 AC-20："network 字段空合法 + 长度上限 64 + 超长截断或拒绝"；与 reactive-resume `defaultValues.network: ""` 一致

### R5: [AC-05 + AC-08] URL 含 `mailto:` + `tel:` 的 username 字段格式未约束 — username 接受 email/phone 还是 free-form 任意字符
- **目标 AC**: AC-05 + AC-08
- **反驳类型**: 覆盖缺失 / 模糊
- **反例描述**: reactive-resume `profile.tsx:242-256` `username` 字段走 `<InputGroup>` 加 `<AtIcon>` 前缀，**纯 free-form 字符串**（无 email / phone 格式校验，user 实际填 `@zhang_san` / `+86-138-0013-8000` / `https://github.com/zhang_san` 都合法）。US4 AC-04 约束 username 字段 testid `profile-username`，AC-08 约束 website.url 白名单但**未约束** username 字段格式。dev 实施时若：(a) 错误加 `^[\w.@+-]+$` 正则（与 reactive-resume free-form 模式不符）；(b) 错误要求 email 格式（含 `@`）→ `+86-138-0013-8000` 被拒；(c) dev 完全无约束接受 `'<script>alert(1)</script>'` → 与 AC-15 XSS 测试通过但不防 spam 输入
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "username free-form accepts handle phone and url"` 期望：(a) input `@zhang_san` → 写 store 接受；(b) input `+86-138-0013-8000` → 写 store 接受；(c) input `https://github.com/zhang_san` → 写 store 接受；(d) input 100 字符任意字符串 → 写 store 接受（仅 max_length 约束如 AC-20）
- **建议**: 新增 AC-04b / AC-21: "username 字段 free-form 字符串（与 reactive-resume 一致），无 email/phone 格式强约束；可选 max_length 约束 ≤ 64 或 128（与 website.label 对齐）"；AC-15 XSS 注入 payload 改为 username 字段独立验证（与 company / position 同款）

### R6: [AC-12 + AC-15] US2 AC-09c 键盘可达性模式未对齐 — profile item 拖拽 keyboard fallback 缺失
- **目标 AC**: AC-12
- **反驳类型**: 覆盖缺失（US2 教训未对齐）
- **反例描述**: US2 AC-09c 已锁："键盘可达性（WCAG 2.1.1 键盘 fallback）：item row 可被 tab focus；focus 后按 Space 进入 drag mode；ArrowUp/ArrowDown 移动顺序；Space 确认放置"。US3 AC-12 接受"沿用 US2 模式"但未显式 cast 键盘可达性（仅约束"500ms 内合并为单帧"和"items[].id 集合保持不变"）。US4 AC-12 同样**仅约束 dnd-kit 鼠标拖拽行为**，未约束 profile item row 的键盘可达性 — 沿用 US3 R9 修订但未走 US2 AC-09c 显式约束模式，未来 US4 + US5 + US6 7 个 SectionList 都缺 keyboard fallback
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "item row keyboard reorder via space and arrow"` 期望：(a) seed 3 items id=['p1','p2','p3'] → focus `[data-testid="profile-item-row-p2"]` → fire keyDown Space 进入 drag mode → fire keyDown ArrowUp → `items.map(i=>i.id) === ['p2','p1','p3']` → fire keyDown Space 确认
- **建议**: 新增 AC-12b：profile item row 键盘可达性（沿用 US2 AC-09c 模式）：tab focus + Space 进入 drag mode + ArrowUp/ArrowDown 移动 + Space 确认放置；测试断言 4 步键盘操作序列

### R7: [AC-13 + AC-15] US3 AC-15 修订 5 帧保守估测未对齐 — 5 字段 change + icon picker + color picker 实际 keystroke 节奏不可预测
- **目标 AC**: AC-13
- **反驳类型**: 不可执行 / 矛盾
- **反例描述**: US3 AC-15 (revised) 修订为"改 3 字段 + add 1 string[] 元素 + reorder 1 次（5 帧保守估测）" + 删 `N <= 9` 硬约束。US4 AC-13 写"改 3 字段 + 选 1 icon + 选 1 color（5 帧保守估测）"，与 US3 同款"5 帧保守估测"。但 icon picker 选中触发 1 帧（不是 keystroke 多帧），color picker 选中触发 1 帧（不是 keystroke 多帧），实际帧数更接近 3 字段 change (3 keystroke 一字段一帧 + 1 icon + 1 color = 5 帧)。AC-13 已修订"不硬约束 N 上限"是正确方向，但**未约束** "icon picker 选中 + color picker 选中"这 2 帧是否被 500ms 批处理合并：若 dev 错误实现"icon picker 关闭 → 立即触发 setDataMut 而非批处理"，用户在 500ms 内连续点 2 个不同 icon 会塞 2 帧（与 US2 AC-08b 拖拽批处理模式不严对齐）
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ProfileDialog.test.tsx -t "icon and color picker changes batch within 500ms"` 期望：(a) 打开 dialog → 在 500ms 内连续点 `profile-icon-picker-item-github` + `profile-icon-picker-item-linkedin` + `profile-icon-color-picker` → `undoStack.length === 1`（合并为单帧）；(b) 单次 `undo()` 后 `icon` 字段恢复 dialog 打开前值
- **建议**: 修订 AC-13：增加 icon/color picker 批处理步骤 (e) "500ms 内连续 picker 选中合并为单帧 setDataMut"；与 US2 AC-08b 模式对齐；或显式说明 "icon/color picker 选中走 setDataMut 不走 draft 镜像（无批处理需求），但 keystroke 字段走 500ms 批处理" 由 dev 实施时确认

### R8: [AC-02] add-button 创建空 item 必填字段初始值与 reactive-resume `defaultValues` 偏差 — icon 必填却默认 'acorn' 而非 'github'
- **目标 AC**: AC-02
- **反驳类型**: 矛盾 / 覆盖缺失
- **反例描述**: reactive-resume `profile.tsx:43` defaultValues `icon: "acorn"`（默认 acorn 图标，**不是** AC-02 写的 `'github'`）。US4 AC-02 步骤 (a) 期望"新 item `icon='github'`"，与 reactive-resume 原版 `'acorn'` 偏离。**潜在影响**：(a) 若 dev 沿用 reactive-resume `defaultValues` 复制粘贴（最自然的实施路径）→ AC-02 步骤 (a) `icon='github'` 断言失败；(b) 若 dev 强行改 `icon='github'` → 与 reactive-resume 默认值偏离，cross-v1/v2 兼容性变差
- **影响**: major
- **验证命令**: 实施后 `git grep -n "icon:" src/modules/resume/v2/editor/dialogs/ProfileDialog.tsx` 找到 defaultValues 实际值；`npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "add button creates item with default icon"` 期望 (a) 新 item `icon === 'acorn'`（与 reactive-resume 一致）或 (b) 接受 `icon='github'` 但起草说明显式说明偏差原因
- **建议**: 修订 AC-02：步骤 (a) 改 `icon='github'` 为 `icon='acorn'`（与 reactive-resume defaultValues 一致）；或显式说明 "US4 v2 改用 github 作为社交默认 icon 以突出 network picker UX 价值，AC 不严约束"

### R9: [AC-05] icon picker 选中后 icon preview 在 list row 渲染 — AC 描述前后矛盾（dialog 内 + list row 同时）
- **目标 AC**: AC-05 + AC-19（间接）
- **反驳类型**: 矛盾 / 模糊
- **反例描述**: AC-05 步骤 (c) 期望"在 `network` input 旁显示对应图标的视觉标识"（dialog 内）；AC-19 步骤 (c) 期望 `row.querySelector('[data-testid="profile-network-display"]').textContent === 'GitHub'`（list row 显示文本，**未提及** icon 渲染）。**矛盾点**：dialog 内的 icon preview（`profile-network-icon-preview`）与 list row 的 icon 渲染**未对齐** — list row 是否也用 icon 渲染（如 US3 AC-04c/05c/06c 模式"data-hidden=true 视觉淡化 + 文本保留"），还是只显示 network 文本？AC-19 步骤 (a) 期望 `data-testid="profile-network-display"` 显示文本，AC-05 期望 dialog 内显示 icon → **两者都满足但 list row 缺 icon 渲染**（与 US2 Experience item row 显示 company + position 文本模式同款，但 Profile 缺 icon 是产品体验缺失）
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "list row renders network icon visual"` 期望：(a) seed item `icon='github', network='GitHub'` → 渲染 row → `[data-testid="profile-network-icon-display"]` 节点存在且 `data-icon="github"` 属性 + 包含 SVG/icon className；(b) 视觉上 icon 与 network 文本同排显示
- **建议**: 修订 AC-19：增加 list row icon 渲染步骤 — 沿用 US2 AC-04b 模式 "item row 渲染时 icon 字段对应图标 + 文本节点"；新增 testid `profile-network-icon-display` + `data-icon={item.icon}` 属性；与 US3 AC-04c/05c/06c 模式对齐（"hidden=true 视觉淡化行 + icon 仍渲染但灰显"）

### R10: [AC-18] Backend round-trip 3 case 缺 US3 AC-20 模式扩展 — description sanitized + level/iconColor/icon 白名单边界未覆盖
- **目标 AC**: AC-18
- **反驳类型**: 覆盖缺失（US2/US3 教训未对齐）
- **反例描述**: US3 AC-20 (R15 扩 6 子 case) 模式：description sanitized × 2 + hidden × 1 + level=0 × 1 + 空 array × 2。US4 AC-18 仅 3 case：(a) full roundtrip / (b) hidden 保留 / (c) URL 黑名单 422。**未覆盖**：(d) `iconColor='rgba(255,0,0,1)'` 边界（Pydantic RgbaColorStr pattern 接受，但 `'#ff0000'` 422）；(e) `icon='my-unknown-icon-xyz'` round-trip — schema 接受但前端 AC-09 拒，跨前后端契约不一致（backend 不报错 → 用户 PUT 假数据成功 → frontend 读取时校验失败 → 体验崩塌）；(f) `iconColor=''` 空字符串合法（与 AC-10 一致）；(g) `network=''` 空字符串合法（与 R4 修订后一致）；(h) `username='<script>alert(1)</script>'` round-trip（XSS 不在 backend 防御范围，但验证 frontend 收到 raw payload 即可渲染期 escape）
- **影响**: major
- **验证命令**: `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py -k "profile"` 期望扩 5 子 case：(d) `test_profile_icon_color_rgba_roundtrip`；(e) `test_profile_icon_unknown_roundtrip_accepts`（验证 backend 不拒，frontend 拒）；(f) `test_profile_icon_color_empty_roundtrip`；(g) `test_profile_network_empty_roundtrip`；(h) `test_profile_username_xss_payload_passthrough`（backend 不 escape，frontend 渲染时 escape）
- **建议**: 修订 AC-18：扩 5 子 case 覆盖 iconColor/icon 边界 + XSS passthrough；与 US3 AC-20 (R15 修订) 模式对齐；接受路径分歧但显式声明跨前后端契约（icon 白名单是 frontend-only，backend 不防御）

### R11: [AC-04] 7 顶层字段 + website 3 sub-input 实际是 8 input testid 而非"7 顶层" — AC 描述自相矛盾
- **目标 AC**: AC-04
- **反驳类型**: 模糊 / 矛盾
- **反例描述**: AC-04 描述写"Profile dialog 字段覆盖 `ProfileItem` 全部 7 个顶层键 + website 3 个 sub-input：`hidden / icon / iconColor / network / username / website.url / website.label / website.inlineLink`"，但实际数：(a) 顶层键 7 个（`hidden / icon / iconColor / network / username` = **5 个非 website 顶层键** + `website{...}` 1 个 nested = **6 个顶层**，其中 `id` 是 implicit 由 store 管理不算 input）；(b) 若按 reactive-resume `profile.tsx` 实际 input testid 数 = `icon-picker-trigger` + `icon-color-picker` + `network` + `username` + `website.url` + `website.label` + `website.inlineLink` + `hidden` = **8 input**（与 AC-04 步骤 (b) 期望"8 个 testid" 一致）。**矛盾**："7 顶层键"措辞 + "8 个 testid" + 实际 `ProfileItem` 字段 = 5 顶层 + 1 website nested ＝ 6 顶层 (id 算第 7)。AC-04 措辞 "7 个顶层键" 把 `website{url,label,inlineLink}` 当 3 个独立顶层键（与 Pydantic schema `ItemWebsite` nested model 矛盾）
- **影响**: major
- **验证命令**: `grep -A 8 "class ProfileItem" backend/app/modules/resumes_v2/schemas.py` 验证实际字段集 = `id / hidden / icon / iconColor / network / username / website`（7 个顶层键，website 是 1 个 nested model 含 3 sub-key）；AC-04 步骤 (b) 期望 "8 个 input testid" 与 reactive-resume 实际 8 input 一致
- **建议**: 修订 AC-04：措辞改为 "ProfileItem 含 6 个直接表单输入字段（icon/iconColor/network/username/hidden）+ 1 个 website nested model 含 3 sub-input = 共 8 input testid"；或显式说明 "7 顶层键包含 1 个 nested website{...}，展开为 3 sub-input"（更准确）

### R12: [AC-11] inline action 3 按钮 testid 命名 + duplicate deep copy 包含 `website{}` 子对象验证未与 US2 AC-10-revised 对齐
- **目标 AC**: AC-11
- **反驳类型**: 覆盖缺失（US2 教训未对齐）
- **反例描述**: US2 AC-10-revised 锁定"duplicate 走 store 推送 + 深拷贝全部字段（roles[] 元素深拷贝 + 新 role id）"。US4 AC-11 步骤 (c) 期望"新 item `network deep equal 原 item.network` 但 `id !== 原 item.id`（且 `website{...}` 深拷贝）" — 提到 `website{...}` 深拷贝但**未约束深拷贝完整性**：(a) `website.url` 字符串是否深拷贝（primitive 无 deep equal 问题）？`website.label`？`website.inlineLink`（boolean）？(b) 若 dev 浅拷贝 `website` 引用（`newItem.website = oldItem.website`）→ 用户编辑新 item 的 website.url 会**同步修改**原 item（zustand immer 应阻止但需测试验证）；(c) `icon` / `iconColor` 字符串 primitive 同样问题（immer 自动处理，但测试需显式断言独立）
- **影响**: major
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "duplicate deep copies all 7 fields with new uuid"` 期望：(a) seed `p1={id:'p1', icon:'github', iconColor:'rgba(255,0,0,1)', network:'GitHub', username:'@a', website:{url:'https://github.com/a', label:'GitHub', inlineLink:true}, hidden:false}`；(b) click duplicate p1 → 新 item `p2`；(c) `p2.website !== p1.website`（引用独立）；(d) 改 p2.website.url = 'https://x.com' → p1.website.url 仍 'https://github.com/a'（深拷贝有效）；(e) `p2.id !== p1.id`；(f) 改 p2.network = 'X' → p1.network 仍 'GitHub'
- **建议**: 修订 AC-11：步骤 (c) 扩展为 "新 item 7 字段全部 deep copy（icon/iconColor/network/username 字符串 + website nested object 3 sub-key + hidden boolean），且与原 item 引用独立"；新增 step (d) "改新 item 的任意字段不污染原 item"

### R13: [AC-19] US3 AC-04c/05c/06c 模式未对齐 — `hidden=true` profile item 视觉淡化 + list row icon 渲染双重约束缺一
- **目标 AC**: AC-19
- **反驳类型**: 覆盖缺失（US3 教训未对齐）
- **反例描述**: US3 AC-04c/05c/06c 锁定的 hidden=true 视觉淡化模式：data-hidden="true" 属性 + 文本节点保留（"X" 文本仍渲染，opacity < 1 / 删除线 / 灰显三选一）。US4 AC-19 步骤 (b) 接受"data-hidden='true' / aria-hidden='true' / style.opacity < 1 三选一 dev 自定" + 步骤 (c) 文本节点保留 → **模式对齐**。但 AC-19 **未约束** "hidden=true 时 list row 的 icon 渲染是否也淡化"（与 R9 反例同款盲点）。若 dev 实现 "hidden=true 时整行淡化，icon 节点 opacity 1.0"（与文本行 opacity 0.5 矛盾）→ 视觉不一致
- **影响**: minor
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "hidden true row both text and icon faded"` 期望：(a) seed `hidden=true, icon='github', network='GitHub'` → 渲染 row；(b) `row.style.opacity` 或 `row.querySelector('[data-testid="profile-item-row-p1"]').style.opacity` < 1；(c) 整行所有子节点（含 icon 和 text）继承 `opacity`；(d) `row.textContent === 'GitHub'` 仍含文本
- **建议**: 修订 AC-19：步骤 (b) 增加 "row 的 opacity 影响所有子节点（含 icon 节点和 text 节点）"；新增 step (e) "hidden=true 时 `profile-network-icon-display` 节点 opacity < 1 或被父 row opacity 覆盖"

### R14: [AC-12] cross-section 拖拽隔离模式未与 US3 AC-17b 显式对齐 — 4 个 SectionList (education/projects/skills/profile) 共存
- **目标 AC**: AC-12
- **反驳类型**: 覆盖缺失（US2 + US3 教训未对齐）
- **反例描述**: US3 AC-17b 锁定："3 个 SectionList (education/projects/skills) items drag 通过 `data-dnd-context="education"|"projects"|"skills"` 命名空间隔离；onDragEnd 内 `over.data.current.droppableContainer.dataset.dndContext !== 当前 section` 短路不触发 items 顺序更新"。US4 AC-12 步骤 (b) 写"不能跨 section（与 LayoutPanel 跨列拖拽隔离 + 与 US3 3 个 SectionList 隔离，drag handle 限定在 `data-section-key="profiles"` 内）" — 提到 "与 US3 3 个 SectionList 隔离" 但**未显式 cast** `data-dnd-context="profiles"` 命名空间（与 US3 同款模式）。US4 实施时 profile SectionList 是 SectionsPanel 第 4 个 list，若 dev 漏加 `data-dnd-context="profiles"` 命名空间 → 用户从 education 拖 item 到 profile 容器可能误触发 profile items 重排
- **影响**: blocker
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/left/__tests__/ProfileSectionList.test.tsx -t "items drag short-circuits when over context is other section incl education projects skills"` 期望：(a) seed profile items=['p1','p2'] + education items=['e1','e2'] + projects items=['pr1','pr2'] + skills items=['s1','s2']；(b) 模拟 onDragEnd `over.data.current.droppableContainer.dataset.dndContext === 'education'` → profile items 顺序未变；(c) 模拟 onDragEnd `over.dataset.dndContext === 'profiles'` → 正常重排
- **建议**: 修订 AC-12：步骤 (b) 显式断言 `data-dnd-context="profiles"` 命名空间存在（`getAttribute('data-dnd-context') === 'profiles'`）+ 测试覆盖 4 个 section 跨拖拽隔离（含 US3 已 lock 的 3 个 section）；与 US3 AC-17b 模式显式对齐（不依赖"沿用 US3 模式"措辞）

### R15: [AC-16] dispatcher 2 case 累加 US1+US2+US3+US4 = 12 case — 共享 helper 模式强制约束缺位
- **目标 AC**: AC-16
- **反驳类型**: 不可执行 / 矛盾（US3 教训未对齐）
- **反例描述**: US3 AC-18b 接受"dispatcher 共享 helper vs 显式 6 case 二选一"（dev 自决可维护性 vs 命名空间清晰）。US4 AC-16 写"`default` 分支 throw Error（fail loud 而非静默 `return null`）" + 步骤 (1) 期望 `case` 字符串集合包含 `'profile.create', 'profile.update'`（12 case 累加：US1 2 + US2 2 + US3 6 + US4 2 = 12 case）。**与 US3 AC-18b 模式偏离**：(a) US3 显式接受"3 dialog + 6 case vs 共享 helper"二选一；(b) US4 沿用 US2 AC-11b-revised "dispatcher switch 必须覆盖" 但未声明"US4 也接受 profile.create / profile.update 共享同一组件但 mode 不同"路径；(c) dev 若按 US3 R5 修订走"profile.create / profile.update 共享 ProfileDialog 组件但 mode 不同" 路径，AC-16 步骤 (1) `git grep case` 期望 2 case 可能不满足（dev 走共享 `case 'profile.create': case 'profile.update': return <ProfileDialog mode=... />` 仍是 2 hits，但 future US5 14 case 累加后 DialogHost switch 26 case = 难维护）
- **影响**: major
- **验证命令**: 实施后 `wc -l src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 > 100 行（12 case 累加）；US4 AC-16 步骤 (1) `git grep` 期望 12 case 字符串集合
- **建议**: 修订 AC-16：与 US3 AC-18b 模式对齐 — 新增 AC-16b: "dispatcher 共享 helper vs 显式 2 case 二选一（dev 自决可维护性 vs 命名空间清晰）"；接受 `case 'profile.create': case 'profile.update': return <ProfileDialog mode=... />` 共享模式；US4 不强制 case 数 2 个独立

### Red-team 汇总：15 / blocker=5 / major=9 / minor=1

最严重的 3 条反例：
- **R1 (blocker)** — IconPicker popover 关闭不选不写字段未约束（dev 错误实现 last-hovered 自动写入会静默污染 icon 字段）
- **R3 (blocker)** — icon 字段"未知拒绝"语义模糊（Pydantic 无白名单约束下 dev 是否维护前端 icon name 白名单数组？白名单范围？未知拒绝行为？）
- **R4 (blocker)** — network 字段长度约束 1-64 与 schema 实际（无 min_length）+ reactive-resume 默认值 '' + AC-02/AC-09/AC-20 三重约束冲突

## Moderation Log (main-agent 裁判)

| 反例 | 判定 | 理由 |
|------|------|------|
| R1 [AC-05] | **接受** | blocker 命中：IconPicker 关闭语义模糊（last-hovered 静默污染）。新增 AC-05b：picker 关闭（ESC + 点遮罩 + Cancel）不写字段；点确认按钮才写。 |
| R2 [AC-05] | **major** | 接受：Fuse.js 模糊搜索是 IconPicker 必备。扩 AC-05 步骤 (b) 显式断言 fuzzy search 行为（输入 "git" 匹配 "GitHub"）。 |
| R3 [AC-09] | **接受** | blocker 命中：icon 字段未知拒绝语义模糊。修订 AC-09：前端维护 `KNOWN_ICONS: string[]` 白名单（dev 自由发挥范围 30-200 个，含 reactive-resume 常用 8 个 + 扩展），未知 icon → 红框 + 不写 store；Pydantic 不变。 |
| R4 [AC-20] | **接受** | blocker 命中：1-64 长度与 reactive-resume 默认值 '' 矛盾。修订 AC-20：删长度约束；空字符串合法（与 schema `str` 无 min_length 对齐）；最长 64 仅作 max 限制。 |
| R5 [AC-05/08] | **接受** | major 命中：username 字段格式未定。修订 AC-05/AC-08：username 是 free-form 字符串（任何字符合法），不做 email/phone 格式校验。 |
| R6 [AC-12/15] | **接受** | major 命中：US2 AC-09c 键盘可达性模式未对齐。新增 AC-12b：profile item row 拖拽键盘 fallback（Space 抓取 + Arrow 移动）。 |
| R7 [AC-13/15] | **major** | 接受：5 帧保守估测已 lock。修订 AC-13 沿用 US3 AC-15：不约束 keystroke 颗粒度，循环 undo N >= 1 && data deep equal S0。 |
| R8 [AC-02] | **接受** | major 命中：add-button 空 item 默认值偏差。修订 AC-02：空 item 默认 `network='' / username='' / url='' / icon='github' / iconColor='#000000' / hidden=false`（icon 默认 'github' 而非 'acorn'）。 |
| R9 [AC-05] | **major** | 接受：icon preview 双重约束。修订 AC-05：dialog 内 network 字段旁显示 icon preview；list row 渲染时若有 icon 显示对应图标。 |
| R10 [AC-18] | **接受** | major 命中：US3 AC-20 模式未对齐。扩 AC-18：6 子 case (profile full_roundtrip + url 白名单 + hidden + icon 白名单 + iconColor + username 自由格式)。 |
| R11 [AC-04] | **major** | 接受：7 顶层 + website 3 sub-input 实际是 8 input testid。修订 AC-04：明确"7 顶层 + 3 sub-input = 10 input testid"（network/username/url/hidden/description/icon/iconColor + website 3 sub-input）。 |
| R12 [AC-11] | **major** | 接受：US2 AC-10-revised duplicate 模式未对齐。修订 AC-11：duplicate 走 store push 深拷贝（含 website{} 子对象），不打开 dialog，undoStack +1。 |
| R13 [AC-19] | **major** | 接受：US3 AC-04c/05c/06c 模式未对齐。修订 AC-19：`hidden=true` profile item 视觉淡化（data-hidden + icon 灰显）。 |
| R14 [AC-12] | **接受** | blocker 命中：US3 AC-17b 跨 section 拖拽隔离模式未对齐（4 list 共存）。修订 AC-12：data-dnd-context="profile" 命名空间隔离。 |
| R15 [AC-16] | **接受** | blocker 命中：US3 AC-18b dispatcher helper 模式未对齐。修订 AC-16：dev 走"profile dialog + 2 case"或"profile + 1 case helper"二选一；新增 AC-16b 沿用 US3 AC-18b。 |

**汇总**：15 接受 / 0 部分接受 / 0 驳回

**Round 2 必走**：派 dev 修订 ac-matrix.md，预计新增 3-4 AC（05b/12b/16b/...）+ 11 修订，目标 22-25 AC 锁定。

## Round 2 修订说明 (dev)

**Round 2 落地状态**：2026-06-29 修订完成。**总 AC 数 23**（原 20 + 新增 3 + 删除 0），分布如下：

| 类别 | 数量 | 列表 |
|------|------|------|
| 修订 AC | 11 | AC-02, AC-04, AC-05, AC-08, AC-09, AC-11, AC-12, AC-13, AC-16, AC-18, AC-19, AC-20 |
| 新增 AC | 3 | AC-21 (AC-05b), AC-22 (AC-12b), AC-23 (AC-16b) |
| 未变更 AC | 8 | AC-01, AC-03, AC-06, AC-07, AC-10, AC-14, AC-15, AC-17 |

**R1 → AC-21 (新)**：IconPicker 关闭不写字段（controlled-popover 模式 + last-hovered 静默污染防御）。
**R2 → AC-05 修订**：Fuse.js fuzzy search input `data-testid="profile-icon-picker-search"` 显式覆盖，input `git` → GitHub 匹配项。
**R3 → AC-09 修订**：前端维护 `KNOWN_ICONS: string[]` 白名单 30-200 个 + Pydantic schema 不变（跨前后端契约：`icon` 白名单 frontend-only）。
**R4 → AC-20 修订**：删 `min_length=1` 约束 → `network.length ∈ [0, 64]`，空字符串合法（与 schema 实际 + reactive-resume `defaultValues.network: ""` 对齐）。
**R5 → AC-05/AC-08 修订**：username 字段是 free-form 字符串（任何字符合法，无 email/phone 格式校验）。
**R6 → AC-22 (新)**：profile item row 键盘可达性（Space 抓取 + Arrow 移动 + Space 确认），沿用 US2 AC-09c 模式。
**R7 → AC-13 修订**：删 5 帧保守估测，循环 undo N >= 1 && data deep equal S0（不约束 keystroke 颗粒度）。
**R8 → AC-02 修订**：空 item 默认 `icon='github'`（与 v2 默认对齐，**非** reactive-resume `'acorn'`）+ `iconColor='#000000'`。
**R9 → AC-05 修订**：icon preview 双重约束（dialog 内 `profile-network-icon-preview` + list row `profile-network-icon-display`）。
**R10 → AC-18 修订**：扩 6 子 case（full_roundtrip + url 白名单/黑名单/空 + hidden + icon 白名单 + iconColor rgba/空/拒 + username 自由格式 XSS passthrough）。
**R11 → AC-04 修订**：明确 6 顶层 + 3 sub-input = 8 input testid，移除"7 顶层键"模糊措辞。
**R12 → AC-11 修订**：duplicate 深拷贝完整性（7 字段全部 deep copy + 引用独立 + 改新 item 不污染原 item）。
**R13 → AC-19 修订**：hidden=true 整行淡化含 icon 灰显（`profile-network-icon-display` icon 节点 opacity < 1）。
**R14 → AC-12 修订**：`data-dnd-context="profiles"` 命名空间显式 cast，4 list (education/projects/skills/profile) 跨 section 隔离。
**R15 → AC-16 修订 + AC-23 (新)**：dispatcher 接受"共享 helper（1 case 行）"或"显式 2 case"二选一，US4 不强制 case 数 2 个独立。

**dev 必避陷阱**：
- **L008/L009 模块 shadow + 默认导出**：AC-17 静态检查已锁；新增 dialog 沿用 `export function ProfileDialog` 命名导出 + 无 `.ts` shadow。
- **L005 ship HTTP probe**：AC-18 触发真实 backend pytest round-trip（6 子 case）；写后端 DB 必须用 `mcp__postgres__query` 实查落库。
- **REQ-032 v2 repo stub trap**：commit 前 `git grep "raise NotImplementedError"` 验证零 hits。
- **dnd-kit bug (T081)**：LayoutPanel 已 ship，US4 不重复踩；AC-12 沿用 US3 AC-17b 命名空间隔离模式。
- **dispatcher type 命名空间**：禁止 `.create/.update` 改为 `.create-item/.update-item`（AC-16 显式 grep 0 hits 验证）。
- **icon 默认值**：**`icon='github'`** 而非 `'acorn'`（与 v2 默认对齐，R8 修订）。
- **后端测试矩阵**：`test_legacy_format.py` 新增 6 子 case，dev 实施时不能用 schema-level 422 替代前端 `fireToast` 防御（R3 修订显式 cast frontend-only 白名单）。

**必读上游经验**：
- US1 AC-08c / US2 AC-14 / US3 AC-16（禁止本地 draft state）→ AC-14 复用
- US1 AC-11b / US2 AC-11b-revised / US3 AC-18（type 命名空间 + fail loud）→ AC-16 复用
- US1 AC-04b / US2 AC-04b / US3 AC-09（id 保留规则）→ AC-12 复用
- US1 AC-09 / US2 AC-12-revised / US3 AC-14（XSS 转义）→ AC-15 复用
- US2 AC-08b（拖拽批处理）→ AC-12 复用
- US2 AC-09b（跨 section 拖拽隔离）→ AC-12 复用
- US2 AC-09c（键盘可达性）→ AC-22 新增
- US2 AC-10-revised（duplicate 走 store push 深拷贝）→ AC-11 复用
- US2 AC-11-revised（URL 白名单 + u flag）→ AC-08 复用
- US2 AC-11c（grep 验证无 default: return null）→ AC-16 复用
- US2 AC-12-revised（hidden=true 视觉淡化）→ AC-19 复用
- US2 AC-13-revised（循环 undo 到 S0）→ AC-13 复用
- US3 AC-04c/05c/06c（hidden 视觉淡化）→ AC-19 复用
- US3 AC-15（循环 undo 删 N 上限硬约束）→ AC-13 复用
- US3 AC-17b（跨 section 拖拽隔离 + data-dnd-context）→ AC-12 复用
- US3 AC-18（dispatcher 6 case 扩展 + fail loud）→ AC-16 复用
- US3 AC-18b（共享 helper vs 显式 6 case 二选一）→ AC-23 新增
- US3 AC-19（SectionItem 路径唯一）→ AC-17 复用
- US3 AC-20 R15 修订（6 子 case 模式）→ AC-18 复用

**Round 2 锁定条件**：待 main agent 收到 dev 修订后，**不再发起新反例**即视为锁定 23 AC，进入 implementation 阶段。dev 实施时严格按 AC 矩阵 step-by-step，**不超出 SC 范围**（US4 范围仅含 Profile section，US5 待 035/036 spec 处理）。
