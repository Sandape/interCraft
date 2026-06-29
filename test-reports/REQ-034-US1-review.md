# 审查报告 REQ-034-US1

## 第 1 次审查

### 判定：PASS

### L 验证（静态）

| ID | 命令 | 命中 |
|----|------|------|
| L006 | `git status` 检 stray files | 无 REQ-034 引入的 .md/.py/stray（已存在 033/032 噪音不在本批范围） |
| L008 | `git grep "src/modules/resume/v2/editor/dialogs/dialogs"` | 0 hits |
| L009 | `git grep -n "export default function BasicsDialog\|export default function PictureDialog" src/modules/resume/v2/editor/dialogs/` | 0 hits |

### AC 反例验证

| AC | 检查 | 结论 |
|----|------|------|
| AC-04b | `BasicsDialog.moveCustomField` 行 146-157 — swap id-positions 无 splice 重建数组 | 实现正确，注释明确 `// Swap id-positions WITHOUT changing id set (AC-04b).` |
| AC-05b | `PictureDialog.tsx:29` `import { uploadAvatar } from "@/api/avatar"` — 复用 v1 avatar；client 端 mime ∈ {png,jpeg,webp} + size ≤ 5MB 校验在 `handleFileChange` 行 152-162；`src/services/storage/picture` 不存在（项目使用 `src/api/avatar.ts`） | 通过 |
| AC-08b | `DialogHost.handleClose` 行 81-88 — 关闭时按 `undoStack` 深度差逐次调用 `undo()` 回滚所有 dialog 内 `setDataMut`，pending debounce timer 此时 no-op（store 已回到 pre-dialog 快照） | 通过 |
| AC-08c | `BasicsDialog` 内 `useState` 仅用于 `fieldErrors`（内联红框显示态），所有字段值都直接 `setDataMut`；`PictureDialog` `fieldErrors` + `uploading` 同理；`NumberField` 局部 draft 是 UI 缓冲（避免每次按键 clamp），`onCommit` 在 blur 时落 store | 通过 |
| AC-11b | `DialogHost` switch 仅覆盖 `'basics' \| 'picture'` 两个 case；`git grep "'basics\.create'\|..."` 0 hits；type 联合 `DialogType = "basics" \| "picture"` 严格，无 `.create/.update/.delete` 命名 | 通过 |

### 代码风格

- `export function` + `export default` 双重导出与 032 TypographyPanel/PagePanel 一致
- `useState` 风格、`setDataMut` + immer draft 模式与 032 batch 一致
- SectionRow 复用现有 `Row` 视觉样式（`rounded border border-surface-border bg-surface-base`），DOM 顺序 `[basics, picture, summary-placeholder, ...sections]` 满足 AC-01b

### L010 / 安全 / 类型

- `git grep "src/services/storage"` 全仓 0 hits（项目用 `src/api/avatar.ts`，非规范路径但实际正确）
- 所有写入走 `setDataMut` immer draft，无字符串拼接 SQL / f-string 风险
- 类型注解完整，`BasicsDialogProps` / `PictureDialogProps` / `DialogSpec` 显式接口
- URL scheme 黑名单 + length 校验双重防御 XSS/data: 注入（AC-09b）

### 轻微建议（不阻塞）

- `PictureDialog.NumberField` 行 405-408 在 render 内 `setTimeout(setDraft, 0)` 是 anti-pattern；建议提取到 `useEffect`
- `BasicsDialog.tsx:441` `export default BasicsDialog` 是冗余（仅 DialogHost 命名导入），可移除以保持 L009 grep 一致性

### 下一步

调用 code-simplification 做精简重构（处理上述两点），简化完成后由主 Agent 统一 commit。

### 修改建议（供主 Agent）

```json
{
  "category": "review-pattern",
  "title": "NumberField setTimeout-in-render anti-pattern",
  "problem": "PictureDialog.NumberField 在 render 内 setTimeout + setDraft 触发 setState，会造成 React warning 并可能与并发渲染冲突",
  "fix_hint": "提取到 useEffect(() => { if (value !== parsedDraft && !focused) setDraft(String(value)); }, [value])"
}
```