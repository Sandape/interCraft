---
req_id: REQ-034-US1
title: Basics form + Picture picker
status: locked
locked_at: 260629 0820
locked_by: negotiation
negotiation_rounds: 2
parent_spec: specs/034-v2-reactive-resume-parity/spec.md
source_gap: memory/req_032_v2_vs_reactive_resume_gap.md (Gap #1 Basics + Gap #2 Picture)
---

# Acceptance Matrix for REQ-034-US1 — Basics form + Picture picker

## SC Gaps

- spec.md 行 22-30 给出 US1 标题 "Basics form + Picture picker"，但 spec §"Acceptance criteria" 段（行 64-66）整体写 TBD，未提供具体 SC 编号供 AC 反向溯源。下表来源以 "行 22-30 隐含" 标记。
- 隐含 SC（从 Bucket A row 1 推导）：
  - SC-1A: 左栏 "Sections" 暴露 "Basics" 与 "Picture" 行入口；点击打开 modal dialog
  - SC-1B: Basics dialog 字段覆盖 `Basics` interface 全部键：`name / headline / email / phone / location / website.url / website.label / customFields[]`
  - SC-1C: `customFields` 支持 add / remove / re-order
  - SC-1D: Picture dialog 字段覆盖 `PictureConfig` 全部键：`hidden / url / size(32-512) / rotation(0-360) / aspectRatio(0.5-2.5) / borderRadius(0-100) / borderColor / borderWidth / shadowColor / shadowWidth`
  - SC-1E: Picture `url` 复用 storage S3 上传逻辑（v1 avatar 已有），上传成功后即时回写
  - SC-1F: 修改通过 `useResumeV2Store.setDataMut` 落地，触发 500ms debounce 自动保存，纳入 undoStack
  - SC-1G: dialog 关闭时 ESC + 点遮罩 + Cancel 三路一致
  - SC-1H: dialog 样式 / 动效 / 字段组件与已有 `RichTextEditor` dialog 同源（视觉一致性）

## AC 矩阵

| AC-ID | 描述 | 验证方式（命令/测试名/可观测指标） | 来源 |
|-------|------|-----------------------------------|------|
| AC-01 | 左栏 Sections 面板中 "Basics" 与 "Picture" 行可点击，分别打开 `BasicsDialog` 与 `PictureDialog` | `npm run test -- --run src/modules/resume/v2/editor/left/SectionsPanel.test.tsx -t "opens basics"` 与 `t "opens picture"` 期望：点击后 DialogHost 渲染 `<BasicsDialog>` / `<PictureDialog>` 子树（按 `data-testid="basics-dialog"` / `data-testid="picture-dialog"` 断言存在） | SC-1A 自主发现: 行 22-30 隐含 + 032 SectionsPanel 现有 entries 缺 basics/picture |
| AC-02 | BasicsDialog 字段映射 `Basics` interface 全部 7 个顶层键 + 1 个 `customFields[]`，字段名与 `data.ts:101-109` 一一对应；提交后 PUT 回 `/api/v1/v2/resumes/{id}` 200 且 `data.basics` 全字段 round-trip 完整 | `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py::test_basics_full_roundtrip -v` 期望 pass；前端 vitest `BasicsDialog.test.tsx` 用 `fillAll('name', '李祖荫')` + click save，spy `useResumeV2Store.getState().data.basics.name === '李祖荫'` 7 字段全 assert | SC-1B 自主发现: data.ts 字段清单 |
| AC-03 | BasicsDialog 接受空值（`name=''` / `email=''` / `customFields=[]`）保存不报错；超长 `name` (1000 字符) 截断或拒绝并 toast；`email` 非 RFC 5322 格式在失焦时显示内联错误（红框 + helper text） | vitest 三个 case：`empty`、`longName`、`badEmail`；期望 empty → 200 / 字段保留为空串，longName → toast "字段超长" 且不写 store，badEmail → 红框 + 不允许 save | 自主发现: 边界（empty/超长/格式） |
| AC-04 | `customFields` 行 add / remove / 上移 / 下移 通过 `setDataMut` 落地；4 项操作均入 `undoStack`（undo 后可还原） | vitest 顺序：`add → assert length=1 → undo → length=0` × 4 路径；外加 `setDataMut` spy 验证调用次数 4 且 prev snapshot 形状正确（手动 verify stack head.data.basics.customFields.length 等于操作前 length） | SC-1C + SC-1F 自主发现: undoStack 行为契约 |
| AC-05 | PictureDialog 字段覆盖 `PictureConfig` 10 个键；`url` 通过 storage S3 上传复用（v1 avatar client API 路径） | 1) `PictureDialog.test.tsx` snapshot 包含 10 input；2) mock `src/services/storage/avatar.ts` 的 `uploadAvatar(file)` 期望被调用一次且返回值写回 `data.picture.url`；3) `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py::test_picture_full_roundtrip -v` 期望 pass | SC-1D + SC-1E 自主发现: S3 复用点 |
| AC-06 | Picture 数值字段越界在失焦时 clamp + toast：`size` 输入 1024 → clamp 到 512；`rotation` 输入 -10 → clamp 到 0；`aspectRatio` 输入 3.0 → clamp 到 2.5；`borderRadius` 输入 150 → clamp 到 100 | vitest 4 个 case，期望 onBlur 后 `useResumeV2Store.getState().data.picture.{size/rotation/aspectRatio/borderRadius}` 分别为 `512 / 0 / 2.5 / 100` 且 spy `fireToast` 被以 `"warn"` 类型调用 | 自主发现: data.ts 行 67-80 边界约束 + wave16_fireToast_signature 签名约束 |
| AC-07 | Picture 上传失败（mock S3 抛 500）时弹 error toast，store 不写脏数据；网络断开（mock `uploadAvatar` reject AbortError）时弹 error toast，原 url 保留 | vitest `uploadError` + `networkAbort` 两 case；spy `setDataMut` 未被调用，`data.picture.url === 初始值` | 自主发现: 边界（上传失败 / 网络断开） |
| AC-08 | ESC 键 / 点击遮罩 / Cancel 按钮三路关闭 dialog，未保存修改不入 store（不触发 PUT） | vitest 三 case `closeEsc / closeBackdrop / closeCancel`；`useResumeV2Store.getState().data.basics === 打开前快照` 且 `updateResume` spy 调用次数 = 0 | SC-1G 自主发现: dialog 行为契约 |
| AC-09 | XSS 注入：`name` / `headline` / `customFields[].text` 注入 `<script>alert(1)</script>` 渲染时必须转义（react-quill / React 文本节点默认转义），不触发 alert | vitest `xssPayload` case + Playwright `tests/e2e/034-v2-content-editing.spec.ts` 加 `t "renders basics name without script execution"` 期望：page.evaluate('window.__xssFired') === false | 自主发现: 安全边界 |
| AC-10 | Picture url 指向非图片资源（如 `https://example.com/file.pdf`）保存后渲染层不崩：基础 3-panel 编辑器内 Picture 缩略图 fallback 到 broken-image 占位符，刷新页面后 URL 仍保留 | Playwright `tests/e2e/034-v2-content-editing.spec.ts` workers=1（L010 必避），case `t "picture non-image url graceful fallback"` 期望：re-fetch 简历后 `data.picture.url === pdf URL` 且缩略图节点 `[data-testid="picture-thumb"]` 存在 | 自主发现: 边界（坏 URL） |
| AC-11 | DialogHost 是单一 dispatcher 入口：basics dialog 不新建独立 modal 容器，复用 `editor/dialogs/DialogHost.tsx` 的 `openDialog({type:'basics', payload})` 派发 | `npm run test -- --run src/modules/resume/v2/editor/dialogs/DialogHost.test.tsx -t "dispatches basics"` 期望：调用 `useDialogStore.getState().open({type:'basics', payload:{resumeId:'x'}})` 后渲染 BasicsDialog；不存在 `editor/dialogs/dialogs.ts` 或 `editor/dialogs/dialogs/index.ts`（grep 0 hits） | 自主发现: 行 75 架构约束 + L008 避坑 |
| AC-12 | `BasicsDialog` / `PictureDialog` 命名导出 `export function BasicsDialog(props)` / `export function PictureDialog(props)`，consumer（DialogHost 内部 dispatcher）通过 `import { BasicsDialog } from "./BasicsDialog"` 命名导入；`grep -rn "export default function BasicsDialog\|export default function PictureDialog" src/modules/resume/v2/editor/dialogs/` 0 hits | 静态检查：`git grep -n "export default function BasicsDialog\|export default function PictureDialog" src/modules/resume/v2/editor/dialogs/` 期望空输出 | L009 必避陷阱 |
| AC-01b | SectionsPanel DOM 顺序锁定为 `[basics, picture, ...sections.*]`，两入口行 icon/title 与 sections.* 行共用同款 Row 组件但 group 视觉标识（顶部 `data-section-group="metadata"`）；移动端 viewport 375px 单列布局下两行不重叠、不溢出水平滚动；后续 US3 summary 入口在 picture 之后、sections.* 之前追加 | `npx vitest run src/modules/resume/v2/editor/left/SectionsPanel.test.tsx -t "basics picture entry position"` 期望：(a) `document.querySelectorAll('[data-section-group="metadata"]').length === 2` 且前两个元素 testid 顺序为 `basics` → `picture`；(b) Playwright `tests/e2e/034-v2-content-editing.spec.ts` 切 viewport 375x800 断言 `getBoundingClientRect().right <= viewport.width`；(c) snapshot 包含 `summary` placeholder（US3 hook） | R8 反驳 |
| AC-02b | phone 字段失焦校验 `^[+0-9()\-\s]{5,30}$`，非法字符实时显示内联红框且 toast；website.url 拒绝 `javascript:/data:/vbscript:/file:` scheme（前端 + 后端 `HttpUrl` schema 双重拒绝）；location / headline / customFields[].text 与 name 共享 XSS escape 回归（写入 `<script>alert(1)</script>`、`javascript:` scheme、`data:text/html,<img onerror=alert(1)>` 渲染时不触发 alert） | 1) `npx vitest run src/modules/resume/v2/editor/dialogs/BasicsDialog.test.tsx -t "phone regex rejects"` + `t "url scheme rejects javascript"` + `t "xss escape regression"` 期望非法输入 fireToast "warn" 且 store 不写；(2) `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py -k "phone_format or url_scheme_blacklist or xss_basics" -v` 期望后端 Pydantic 422 含 `javascript:` URL；(3) Playwright `tests/e2e/034-v2-content-editing.spec.ts -g "xss escape regression" --workers=1` 断言 `window.__xssFired === false` | R1 反驳 |
| AC-04b | `customFields` 行 add / remove / drag-reorder 经 `setDataMut` 落地后 `customFields[].id` 集合保持不变（仅顺序变化），dev 必须通过 swap id 顺序实现 reorder 而非 splice 重建数组；4 项操作外加连续 10 次 `setDataMut` 后 undoStack depth ≤ spec US17 锁定上限 20（已知 v1 上限文档化） | `npx vitest run src/modules/resume/v2/editor/dialogs/BasicsDialog.test.tsx -t "customFields reorder preserves ids"` + `t "undoStack depth bounded after 10 mutations"` 期望：(a) reorder 后 `new Set(idsBefore) deep equal new Set(idsAfter)`；(b) 第 11 次 undo 应报错或 noop（depth cap 生效）；(c) `undoStack.length <= 20` 断言 | R2 反驳 |
| AC-05b | Picture 上传前 client 端校验 mime ∈ `{image/png, image/jpeg, image/webp}` 且 size ≤ 5MB，越界拒绝且无 network 请求；后端响应 S3 key 走 v2 RLS 上下文（`app.user_id === resume.owner_id` 才返回 presigned URL）；`src/services/storage/avatar.ts` 必须被复用（v2 picture 走 `uploadAvatar` 函数）而非新建 `src/services/storage/picture.ts` | (1) `npx vitest run src/modules/resume/v2/editor/dialogs/PictureDialog.test.tsx -t "upload rejects oversized or wrong mime"` 期望 fetch spy 调用次数 = 0；(2) `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_export.py -k "upload rls owner mismatch" -v` 期望 user-B 请求 user-A resume picture upload 返回 403；(3) `git grep -n "uploadAvatar\|src/services/storage/avatar" src/modules/resume/v2/editor/dialogs/PictureDialog.tsx` 期望至少 1 hit；(4) `git grep -n "src/services/storage/picture" src/` 期望 0 hits | R3 反驳 |
| AC-06 (扩展) | Picture 数值字段越界 + 非数字输入在失焦时 clamp + 内联红框 + toast：`size ∈ [32,512]` / `rotation ∈ [0,360]` / `aspectRatio ∈ [0.5,2.5]` / `borderRadius ∈ [0,100]` / **`borderWidth ∈ [0,40]`** / **`shadowWidth ∈ [0,40]`**；非数字 / NaN / Infinity 输入显示红框、不写 store、fireToast "warn"；clamp 后值必须是合法 `number` 且 `!isNaN && isFinite`；负数下界同正数越界走 clamp | `npx vitest run src/modules/resume/v2/editor/dialogs/PictureDialog.test.tsx -t "clamp covers all six numeric fields and rejects NaN"` 期望：(a) size=1024 → 512, rotation=-10 → 0, aspectRatio=3.0 → 2.5, borderRadius=150 → 100, borderWidth=-5 → 0, borderWidth=999 → 40, shadowWidth=-1 → 0, shadowWidth=100 → 40；(b) size='abc' / rotation=NaN / aspectRatio=Infinity 触发红框 + toast 且 `useResumeV2Store.getState().data.picture.{size,rotation,aspectRatio} === 初始值`；(c) 所有 clamp 后值断言 `typeof === 'number' && !isNaN(value) && isFinite(value)` | 自主发现 + R5 反驳 + R9 反驳 |
| AC-08b | dialog 关闭（ESC / backdrop / Cancel）触发后 500ms debounce 窗口内取消 pending setDataMut 触发的 autosave timer；1500ms 后 `updateResume` spy 调用次数 = 0，`store.data.basics.{modifiedField} === 打开前快照`；与 AC-08 "未保存修改不入 store" 闭合（不与 AC-02 实时落 store 矛盾：dialog 内 setDataMut 落 store 但关闭即视为撤销，autosave 必走显式 Save 按钮） | `npx vitest run src/modules/resume/v2/editor/dialogs/BasicsDialog.test.tsx -t "close during debounce window cancels autosave"` 期望：(a) fill name='X' → fire ESC → `vi.advanceTimersByTime(500)` → 断言 `updateResume` spy = 0；(b) `vi.advanceTimersByTime(1500)` 仍 = 0；(c) `store.data.basics.name === originalValue` | R4 反驳 |
| AC-08c | dialog 内禁止本地 draft state（`useState` / `useReducer` 单独管理表单值再 onSave 一次性提交）；所有字段变更必须直接经 `setDataMut` 写入 `useResumeV2Store`；dialog 关闭后 undo 一次应完全回到打开前的 store 快照（`deep equal` 自定义字段比对 `name / email / phone / customFields[].id+text+icon`） | `npx vitest run src/modules/resume/v2/editor/dialogs/BasicsDialog.test.tsx -t "undo after dialog close restores pre-dialog snapshot"` 期望：(a) `git grep -n "useState\|useReducer" src/modules/resume/v2/editor/dialogs/BasicsDialog.tsx` 仅在 DialogHost 容器层（开/关状态）出现，不在 field-level；(b) 加 2 customField → close ESC → undo 1 → `store.data.basics.customFields.length === 打开前长度` 且每个 customField 字段 deep equal | R10 反驳 |
| AC-09b | XSS 与坏 URL 回归覆盖 `customFields[].icon` / `customFields[].text` / `headline` / `picture.url` / `location`，payload 包括 `<script>` / `<img onerror>` / `javascript:` / `data:text/html`；`picture.url` 长度 ≤ 2048 且必须 `http(s):` 或 `data:image/{png,jpeg,webp}` scheme；空字符串 url 视为合法（用户清空） | (1) `npx vitest run src/modules/resume/v2/editor/dialogs/BasicsDialog.test.tsx -t "xss covers all text fields"` 期望所有注入 payload 渲染时 `dangerouslySetInnerHTML` 不出现且 `window.__xssFired === false`；(2) `npx vitest run src/modules/resume/v2/editor/dialogs/PictureDialog.test.tsx -t "url length and scheme validation"` 期望 url=2049 字符触发红框+toast；url=`javascript:alert(1)` 拒绝；(3) Playwright `tests/e2e/034-v2-content-editing.spec.ts -g "xss in customFields text and headline" --workers=1` 端到端断言 | R6 反驳 |
| AC-11b | `openDialog` type 命名空间文档化为 `{section}.{verb}`（如 `'experience.create'` / `'experience.update'`），但 US1 basics / picture 是单实例编辑无 create/update 区分，**走 `{section}` 直接命名**（`'basics'` / `'picture'`，无 verb 后缀）；delete 操作走 inline（customField 行 × 按钮直接 setDataMut 删除）**不进 dispatcher**；dispatcher switch 必须覆盖 `'basics' | 'picture'` 两个 case，grep 验证无 `'basics.create'` / `'basics.update'` / `'basics.delete'` 命名污染 | (1) `git grep -n "openDialog" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` 期望 case 字符串集合 `{'basics', 'picture'}`；(2) `git grep -n "'basics\.create'\|'basics\.update'\|'basics\.delete'\|'picture\.create'\|'picture\.update'\|'picture\.delete'" src/` 期望 0 hits；(3) `npx vitest run src/modules/resume/v2/editor/dialogs/DialogHost.test.tsx -t "type namespace uses bare section name for single-instance"` | R7 反驳 |

## Tester 反驳日志

### R1: [AC-02] 缺 phone/URL/website 格式校验边界 — SC-1B 未覆盖特殊字符
- **反例场景**: `phone='+86 138-0013-8000 ext.5'` / `website.url='javascript:alert(1)'` / `location='<svg/onload=x>'` 提交后直接落 store + PUT 后端；后端 Pydantic 仅校验 URL 是否 `HttpUrl`，`javascript:` 在某些浏览器仍可点击触发
- **验证命令**: `cd backend && uv run pytest -q backend/app/modules/resumes_v2/tests/test_legacy_format.py -k "phone_format or url_scheme or location_xss" -v`
- **复现步骤**: 1) 打开 BasicsDialog；2) phone 填 `+86 (138) 0013-8000`；3) website.url 填 `javascript:fetch('/api/v1/v2/resumes/'+document.cookie)`；4) save；5) GET 回来发现 url 原样保留；6) 在公开分享页 `<a href={basics.website.url}>` 渲染时触发 XSS
- **严重度**: blocker
- **建议 AC 修订**: 新增 AC-02b：phone 必须匹配 `^[+0-9()\-\s]{5,30}$`；website.url 拒绝 `javascript:/data:/vbscript:` scheme（前端 schema + 后端 HttpUrl 双重拒绝）；location/headline 同 AC-09 XSS 转义回归

### R2: [AC-02] customFields id 唯一性 + drag-reorder 与 undoStack 的连续操作回放未被覆盖
- **反例场景**: `customFields[]` 拖拽 reorder 时，dev 若直接 splice 修改数组索引（而非 swap id 顺序），undo 后 id 重新洗牌导致后续 PUT 与 v1 数据不兼容；且拖拽中 4 个连续 `setDataMut` 调用塞满 undoStack 把之前 5 步用户操作挤出栈外
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/BasicsDialog.test.tsx -t "customFields reorder preserves ids"`
- **复现步骤**: 1) add 3 个 customField；2) 连续拖拽上移→下移→上移 3 次；3) undo 4 次；4) 检查栈头 customFields[].id 集合等于初始 3 个 id（顺序可恢复），且 undoStack 长度 ≤ spec 限定（查 US17 undo TTL 文档）
- **严重度**: major
- **建议 AC 修订**: 新增 AC-04b：drag-reorder 后 customFields[].id 集合不变，仅顺序变化；连续 10 次 setDataMut 后 undoStack depth 仍可还原最早 5 步

### R3: [AC-05] S3 上传 size/type 边界 + 与 v1 avatar 复用的 RLS/owner 隔离风险
- **反例场景**: v1 avatar 上传路径可能仅校验 `image/*` MIME 与 size ≤ 5MB；v2 Picture 可能允许非图片 URL（AC-10 允许 PDF）；若 v1 上传校验是 client-side only，恶意用户 POST 一个 100MB 文件绕过；更严重：v1 avatar 的 S3 key 前缀按 `user_id/` 分桶，复用上传函数时 v2 可能错把 v2 picture 上传到 v1 avatar 桶导致 RLS 跨表读取
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/PictureDialog.test.tsx -t "upload rejects >5MB"` + `curl -i -X POST -H "Authorization: Bearer $TOKEN" -F "file=@/tmp/big.bin" /api/v1/storage/avatar`
- **复现步骤**: 1) mock `uploadAvatar` 接收 100MB Blob；2) 断言 upload 前 client 拒绝且无 network 请求；3) 检查 `src/services/storage/avatar.ts` 是否复用 v1 RLS owner 校验，v2 缺 RLS 可能把别人 S3 key 返回给当前用户
- **严重度**: blocker
- **建议 AC 修订**: 新增 AC-05b：上传前 client 端校验 mime ∈ {image/png,image/jpeg,image/webp} 且 size ≤ 5MB；后端响应 S3 key 必须用 v2 RLS 上下文（`app.user_id` 与 resume.owner_id 匹配）；grep `src/services/storage/avatar.ts` 验证其复用而非复制

### R4: [AC-04 + AC-08] autosave 触发时序与 dialog 关闭竞态 — 500ms debounce 窗口内关闭 dialog 导致 PUT 包含未确认数据
- **反例场景**: 用户在 BasicsDialog 改 name → 立即 ESC 关闭；500ms debounce 计时器仍在；setDataMut 已调但 dialog 已 unmount；autosave PUT 触发写入"未确认修改"，与 AC-08 "未保存修改不入 store" 矛盾
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/BasicsDialog.test.tsx -t "close during debounce window"`
- **复现步骤**: 1) mock `setDataMut` spy；2) fill name='X'；3) fire ESC（无 save click）；4) advance timers by 500ms；5) 断言 updateResume spy 调用次数 = 0；6) 断言 store.data.basics.name 仍为原始值
- **严重度**: blocker
- **建议 AC 修订**: 新增 AC-08b：dialog 关闭后 500ms 内撤销任何 pending setDataMut（取消 debounce timer）；AC-08 改为 spy `updateResume` 调用次数 = 0 在 1500ms 后仍成立

### R5: [AC-06] Picture 数值 clamp 后未校验类型/NaN 输入
- **反例场景**: `size='abc'` / `rotation=undefined` / `aspectRatio=null` 失焦后 `Number(value)` 返回 NaN，clamp 后 `data.picture.size === NaN`，Pydantic backend 校验失败 PUT 500
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/PictureDialog.test.tsx -t "non-numeric clamp yields number"`
- **复现步骤**: 1) size 输入 `'abc'` 失焦；2) 断言 useResumeV2Store.data.picture.size 是合法 number ∈ [32,512] 且非 NaN；3) 同样测 rotation/aspectRatio/borderRadius/borderWidth/shadowWidth
- **严重度**: major
- **建议 AC 修订**: 新增 AC-06b：非数字 / NaN / Infinity 输入显示内联红框 + 不写 store + toast；clamp 仅对合法 number 生效

### R6: [AC-09 + AC-10] XSS 与坏 URL 的回归只测了 basics.name，未覆盖 picture.url/customFields[].text/headline
- **反例场景**: AC-09 case 只测 name，遗漏 `customFields[].icon`（注入 react component name）、`customFields[].text`、`headline`、`summary.content`（虽然 summary 不在 US1，但与 basics 共存时渲染层遍历）；AC-10 坏 URL 只测 PDF，未测 `data:` URI / 空字符串 / `http://` 无 host / 超长 URL（>2048 字符，浏览器 URL 长度上限）
- **验证命令**: `npx playwright test tests/e2e/034-v2-content-editing.spec.ts --project=chromium -g "xss in customFields text" --workers=1`
- **复现步骤**: 1) PUT 注入 payload 包含 `<img src=x onerror=alert(1)>` 在 `customFields[0].text` 与 `headline`；2) 打开 preview panel；3) page.evaluate `window.__xssFired` 必须 false；4) 测 picture.url = 'data:text/html,<script>alert(1)</script>' 渲染层
- **严重度**: blocker
- **建议 AC 修订**: 新增 AC-09b：case 覆盖 customFields[].icon/text/headline/picture.url；新增 AC-10b：picture.url 长度 ≤ 2048 且必须 http(s)/data:image scheme

### R7: [AC-11] DialogHost 单一 dispatcher 验证不充分 — 未约束 delete/edit/create 三态 type 命名空间
- **反例场景**: spec 架构约束行 75 写 `openDialog({type: 'experience.create' | 'experience.update'})`，但 US1 的 basics/picture 是单实例编辑，无 create/update 区分；dev 可能写出 `type: 'basics' | 'picture'`，与未来 US2 的 `experience.create/update` 命名空间不一致，导致 DialogHost switch 漏 case；同样 delete 操作（删除 basics 自定义行）走哪条路径未定义
- **验证命令**: `git grep -n "openDialog\|type: 'basics'\|type: 'picture'" src/modules/resume/v2/editor/dialogs/`
- **复现步骤**: 1) DialogHost.test 验证 openDialog 调用 type 字符串集合包含 `'basics'` `'picture'` `'basics.delete'` `'picture.delete'`；2) 验证 dispatcher switch 覆盖全部 type；3) grep 防止命名空间混用
- **严重度**: major
- **建议 AC 修订**: 新增 AC-11b：openDialog type 命名空间文档化为 `{section}.{verb}`，basics/picture 当前为单实例无 create 但 delete 操作走 `basics.delete` 或 inline 不进 dispatcher；二选一必须明示

### R8: [AC-01] SectionsPanel 入口位置冲突 — basics/picture 与已有 entries 排序如何处理
- **反例场景**: 032 SectionsPanel 已暴露 sections.* 的 title/icon 编辑入口；basics/picture 是顶层非 section 字段，dev 必须在 SectionsPanel 顶部插入两组 entry，与 summary（也在 metadata 外）位置关系未定义；移动端响应式下两组合并显示冲突
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/left/SectionsPanel.test.tsx -t "basics picture entry position"`
- **复现步骤**: 1) 渲染 SectionsPanel；2) 断言前两行是 basics + picture（而非塞到 sections 列表内）；3) 移动端 viewport 375px 下两行不重叠；4) 验证 summary 入口（US3 后）位置不冲突
- **严重度**: minor
- **建议 AC 修订**: 新增 AC-01b：SectionsPanel DOM 顺序 `[basics, picture, ...sections]`，移动端 < 640px 单列布局不溢出

### R9: [AC-05] PictureConfig.borderWidth/shadowWidth 下界 ≥0 约束未在 AC 覆盖（与 size/rotation 同源）
- **反例场景**: data.ts 行 75/79 注释 `/** >=0 */`，但 AC-06 只测了 size/rotation/aspectRatio/borderRadius 四个 clamp；borderWidth/shadowWidth 允许负数将导致 CSS box-shadow 渲染异常（浏览器默认渲染但 PDF 导出可能崩）
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/PictureDialog.test.tsx -t "borderWidth shadowWidth negative clamp"`
- **复现步骤**: 1) borderWidth 输入 -5；2) 失焦后断言 store 值为 0；3) shadowWidth 同；4) PDF export 端不崩（后端 pdf 渲染对负 box-shadow 可能 raise）
- **严重度**: major
- **建议 AC 修订**: 扩展 AC-06 包含 borderWidth/shadowWidth 越界 clamp；新增 AC-06c：clamp 后值必须是合法 number 非 NaN

### R10: [AC-02 + AC-08] Dialog 关闭后 useResumeV2Store 历史快照污染 — undo 还原被 dialog 干预的数据
- **反例场景**: 打开 dialog 前 store 处于状态 S1；用户改字段触发 4 次 setDataMut（AC-04 add/remove/reorder 测试），dialog 关闭后 undo 一次应回到 S1 但 dev 实现若 dialog 内手动管理 draft state 而非直接 setDataMut，undoStack 与 form draft 不一致
- **验证命令**: `npx vitest run src/modules/resume/v2/editor/dialogs/BasicsDialog.test.tsx -t "undo after dialog close restores pre-dialog snapshot"`
- **复现步骤**: 1) 记录 S1 = useResumeV2Store.getState().data.basics；2) 打开 dialog 加 2 customField；3) close ESC；4) undo 1 次；5) 断言 store.data.basics deep equal S1（customFields 长度回到原值）
- **严重度**: major
- **建议 AC 修订**: 新增 AC-08c：dialog 内所有写操作必须经 setDataMut（不允许 dialog-local draft state），关闭后 undo 行为与未打开 dialog 时一致

---

## 起草说明（写给 tester）

**设计意图**：
- US1 范围严格限定 Basics + Picture 两个 dialog，不触碰 Experience/Education 等其他 9 个 section（见 spec Bucket A row 2-6）。
- 所有写操作统一走 `useResumeV2Store.setDataMut(draft => {...})`，自动获得 500ms debounce autosave + undoStack + redoStack + 30min TTL，无需 dialog 内重复实现。
- Picture 上传复用 v1 avatar S3 client（路径待 dev 探查 `src/services/storage/avatar.ts`），不引入新 SDK。
- DialogHost 单一入口派发，避免 L008 的 `<name>.ts` + `<name>/index.ts` shadowing 复发。

**已覆盖的边界**：
- 空值 / 超长 / 格式非法 / XSS 注入（AC-03, AC-09）
- Picture 数值越界 clamp（AC-06）
- 上传失败 / 网络断开 / 坏 URL（AC-07, AC-10）
- dialog 三路关闭一致（AC-08）
- 命名导出 / 单一 dispatcher 架构正确性（AC-11, AC-12）

**未覆盖的边界（已知风险）**：
- Picture `borderColor` / `shadowColor` rgba 字符串的合法值校验（接受任意 `rgba(r,g,b,a)` 字符串，无 alpha 上界）。spec 未提，留 dev 用 Pydantic schema 兜底。
- 多个 tab 同时打开同 resume 的并发场景（由 032 SSE + 409 路径处理，不在 US1 范围）。
- i18n / 中英双语字段标签（v2 当前 zh-CN only，spec 未要求多语言）。
- Picture 拖拽上传（v1 avatar 走 file picker，未实现 drop zone；reactive-resume 同）。

**必避陷阱已在 AC 中显式 cast 死**：
- L008（module shadow）：AC-11 grep 验证
- L009（default vs named export）：AC-12 静态检查
- L010（Playwright workers）：AC-10 显式 workers=1
- L004（dev 范围）：US1 单 US，本 AC 矩阵已 < 50 tool_uses 即可完成实现
- L005（ship HTTP probe）：AC-02 + AC-05 各加一条 backend pytest 触发真实 PUT/GET

---

## Moderation Log

裁判：main-agent @ 260629 0815
读 tester 反例段（10 条，4 blocker / 5 major / 1 minor），逐条判接受/驳回/主动探索。

| # | 类型 | 严重度 | 判定 | 理由 |
|---|------|--------|------|------|
| R1 | phone/URL/XSS 边界 | blocker | **接受** | 反例具体 + 命令可执行 + 与生产安全强相关；新增 AC-02b（phone regex + URL scheme blacklist + XSS escape 回归） |
| R2 | customFields drag-reorder id + undoStack depth | major | **部分接受** | id 保留规则接受（新增 AC-04b）；undoStack depth cap 推后到 US17 文档化（spec 已实现 undoStack max 20） |
| R3 | S3 size/RLS/跨表 | blocker | **接受** | 反例具体 + L005 教训直接对应；新增 AC-05b（client mime+size 5MB + 后端 RLS owner 校验 + 复用 src/services/storage/avatar.ts 而非复制） |
| R4 | dialog 关闭 vs autosave debounce 竞态 | blocker | **接受** | 反例具体 + 现实高频；新增 AC-08b（关闭取消 pending debounce timer + 1500ms 后 updateResume spy = 0） |
| R5 | 非数字 clamp NaN/Infinity | major | **接受** | 反例具体；扩展 AC-06 含 size/rotation/aspectRatio/borderRadius/borderWidth/shadowWidth + NaN 检测 |
| R6 | XSS regression 范围不全 | blocker | **接受** | 反例具体 + 命令可执行；扩展 AC-09 覆盖 customFields[].icon/text/headline/picture.url；新增 AC-09b（data: URI / 空 / >2048 URL / http:// 无 host） |
| R7 | DialogHost type 命名空间 | major | **部分接受** | 接受命名空间文档化（新增 AC-11b），但 basic/picture 是单实例无 create/update，命名走 `{section}` 直接命名（无 verb）；delete 走 inline 不进 dispatcher |
| R8 | SectionsPanel 入口位置 | minor | **接受** | 反例明确；新增 AC-01b（DOM 顺序 [basics, picture, ...sections] + 移动端 < 640px 单列不溢出） |
| R9 | borderWidth/shadowWidth clamp | major | **接受** | 反例具体；扩展 AC-06 含 borderWidth/shadowWidth 越界 clamp |
| R10 | undoStack 快照一致性 | major | **接受** | 反例具体 + 与 US17 undoStack 直接相关；新增 AC-08c（dialog 内禁止本地 draft state，所有写经 setDataMut） |

**总评**：8 接受 + 2 部分接受 + 0 驳回。
**下一步**：派 dev 修订 AC（针对接受的 8 + 部分接受 2），进入 round 2。
**预计新增 AC**：AC-01b, AC-02b, AC-04b, AC-05b, AC-06 扩展, AC-08b, AC-08c, AC-09b, AC-11b。
