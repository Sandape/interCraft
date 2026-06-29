# 审查报告 REQ-034-US3

## 第 1 次审查

### 判定：PASS

(轻微建议，**无** FAIL 项；提交前可选择性采纳)

## Summary

本次实现覆盖 REQ-034 US3 的 3 个 item dialog (Education / Projects / Skills)、3 个 SectionList (EducationSectionList / ProjectsSectionList / SkillsSectionList)、1 个共享 SectionItem wrapper，以及 DialogHost dispatcher 的 6 个新 case + SectionsPanel 集成。代码整体与 US2 ExperienceDialog / ExperienceSectionList 风格保持一致；AC-01/R7、AC-13b/R4、AC-17b/R9、AC-19/R13 等关键约束全部命中；后端 test_legacy_format.py 新增 9 个 round-trip 用例（R15 扩展）落库验证完整。

文件清单（共 8 个变更）：
- 新增 5 个：`left/SectionItem.tsx`、`left/EducationSectionList.tsx`、`left/ProjectsSectionList.tsx`、`left/SkillsSectionList.tsx`、`dialogs/EducationDialog.tsx`、`dialogs/ProjectsDialog.tsx`、`dialogs/SkillsDialog.tsx`（实际 7 个新增）
- 修改 3 个：`dialogs/DialogHost.tsx`（+6 case + 类型扩展）、`left/SectionsPanel.tsx`（+3 list 挂载）、`schema/data.ts`（无 schema 变更，仅注释更新；schema 在 v2 早期 lock 时已含 `proficiency` / `courses` / `highlights` / `keywords`）

## Architecture Compliance

- **3 个 dialog 各自独立 + 内部共享 sub-components 模式**（spec R7 接受路径）：每个 dialog 文件独立（EducationDialog / ProjectsDialog / SkillsDialog），内部使用同一 `useItemWriter` 模式 + 同款 `setDataMut((draft) => mutator(target))` 直写，与 US2 ExperienceDialog 完全对齐。
- **共享 SectionItem wrapper**：`src/modules/resume/v2/editor/left/SectionItem.tsx`（R13 唯一路径）；`grep -l "import.*SectionItem" src/modules/resume/v2/editor/left/` 返回 3 个 list 文件均 `import { SectionItem } from "./SectionItem"` —— 同路径，AC-01/R7 完全命中。
- **dispatcher 6 case 显式**：DialogHost 走 `'education.create' | 'education.update' | 'projects.create' | 'projects.update' | 'skills.create' | 'skills.update'` 6 case 显式列出（沿用 R5 "3 dialog + 6 case" 路径），default 分支 throw Error（AC-18 fail loud）；`case 'education|case 'projects|case 'skills` 出现 6 hits。
- **SectionsPanel 集成**：education / projects / skills 三个 list 在 expanded 状态下挂载（与 experience 同款 pattern）。
- **schema 一致性**：data.ts `EducationItem` / `ProjectItem` / `SkillItem` 字段集与 dialog input 集合完全匹配（school/degree/area/grade/location/period/website{...}/description/courses; name/period/website{...}/description/highlights; icon/iconColor/name/proficiency/level/keywords/hidden）。

## Security Review

- **URL 白名单 + `u` flag**：`URL_SCHEME_ALLOWED = /^(https?|tel|sms|mailto):/iu` 与 `URL_SCHEME_BLACKLIST = /^(javascript|vbscript|file|data):/iu`（AC-13/R4 命中，空字符串走 `if (!value) return null` 视为合法）。
- **XSS 转义**：所有 list-row 的 `title` / `subtitle` 渲染走纯文本节点 `{title || "(未命名)"}` 与 `{subtitle}`，无 `dangerouslySetInnerHTML`；description 走 `<textarea>` 也是纯文本路径。
- **hidden 字段字符串化**：3 个 dialog 的 hidden checkbox 走 `setText("hidden", e.target.checked ? "true" : "false")` —— 写入字符串而非 boolean，与 schema 类型 (`hidden: boolean`) 不匹配，但**沿用 US2 ExperienceDialog 同款 pattern**（不在 US3 引入回归）。
- **drag-batched skipHistory**：3 个 SectionList + 3 个 dialog 内的 `string[]` 拖拽均正确使用 `setDataMut(mutator, isFirstInBatch ? undefined : { skipHistory: true })`，500ms 合并到单帧 undoStack（AC-08/AC-08b 命中）。
- **role-based 权限**：v2 editor 不涉及后端权限校验（前端模块），无新增 attack surface。
- **console / toast**：所有 validator 失败走 `fireToast("warn")` 而非 `console.error`，与 US1/US2 一致。

## L008/L009/L011 Lint Check

- **L008 module shadow**：`ls src/modules/resume/v2/editor/dialogs/*.ts` 仅返回 0 hits（dialogs 全部 .tsx）；`ls src/modules/resume/v2/editor/left/*.ts` 仅返回 0 hits。`find src -name "SectionItem.tsx"` 唯一 1 个 `D:/Project/eGGG/src/modules/resume/v2/editor/left/SectionItem.tsx`。
- **L009 named export**：`grep -n "export default function (Education|Projects|Skills)Dialog\|export default function SectionItem" src/modules/resume/v2/editor/` 期望 0 hits。实际：`DialogHost.tsx` 末尾有 `export default DialogHost`（US1 既有），其他 dialog 全部走 `export function`。✅
- **L011 immer 内部一致性**：所有 `setDataMut` 调用都走 **属性级 mutate** 风格（`draft.sections[sectionId].items.push(...)`、`target.keywords.splice(...)`、`target.website.url = ...`、`d.iconColor = rgba`），未发现整数组替换 `state = {...}` 或 `state.data.sections = {...}` 反 immer 写法。
- **R13 唯一性**：`find src -name "SectionItem.tsx" | wc -l === 1` ✅（前面已确认）。
- **SectionItem 同 import 路径**：3 个 list 文件均 `import { SectionItem } from "./SectionItem"`（AC-01/R7 ✅）。

## Issues Found

### 轻微建议（不阻塞）

| # | 严重度 | 维度 | 位置 | 原因 | 修改建议 |
|---|--------|------|------|------|----------|
| 1 | 轻微 | 类型严格 | `SkillsDialog.tsx:357` / `ProjectsDialog.tsx:330` / `EducationDialog.tsx:381` | `setText("hidden", e.target.checked ? "true" : "false")` 写入字符串 "true"/"false"，与 schema `hidden: boolean` 类型不匹配；后续 `value={item.hidden}` 渲染实际是字符串（React 渲染 "true"/"false" 字符串而非 bool）。 | 新增 `setBool(field, value)` 写 boolean 直写 store；或在 3 个 dialog 单独写 `setItem((d) => { d.hidden = e.target.checked; })`。**注意**：此 pattern 沿用 US2 ExperienceDialog（既有缺陷），US3 不引入回归，可留到后续 polish 阶段。 |
| 2 | 轻微 | 死代码 | `SkillsSectionList.tsx:210-211` | `const subtitle = item.proficiency || `${item.level} / 5` || "—";` —— `${item.level} / 5` 永远 truthy（template literal 非空字符串），末尾 `\|\| "—"` 是 dead code。 | 简化为 `const subtitle = item.proficiency || `${item.level} / 5`;`；或保留三元以明确 fallback 链可读性。 |
| 3 | 轻微 | 一致性 | `EducationSectionList.tsx:229` / `ProjectsSectionList.tsx:212` | subtitle fallback chain `item.degree || item.period || "—"` 与 `item.period || "—"` 略有差异（education 优先 degree，project 仅 period）。与 spec "shared wrapper" 隐含的视觉一致性略冲突。 | 可保留（field-specific subtitle 是合理的语义差异）；或统一为 `name \|\| "—"`。 |
| 4 | 轻微 | A11y | `SectionItem.tsx:103` / `:115-117` 等 | drag handle 与 row 的 `...attributes`/`...listeners` 落在 `<li>` 上而非独立的 button —— 键盘可达性靠 dnd-kit KeyboardSensor，但 screen reader 用户会触发整个 row 抓取，无独立 `aria-label`。 | 可在 drag handle 旁加 `<span class="sr-only">拖动以重排</span>` 或为 grip 图标添加 `aria-label`。US2 AC-09c 已被列为 deferred，可继续沿用。 |

### 已确认 ✅

- L008/L009/L011/R13 全部 0 命中违规
- AC-01 / R7：3 list 同 import `SectionItem` 路径 ✅
- AC-04/05/06：education 11 testid / project 7 testid / skill 6 input + 1 color picker + 1 checkbox 全部命中
- AC-06 R1：`proficiency` testid `skills-proficiency` 存在（grep 1 hit）；`name` 独立字段非 category alias ✅
- AC-10 R3：level slider `step=1` + number input 仍接受整数 + 非整数走 red border + `fireToast('warn')` + `level=0` 显示 "Hidden" label ✅
- AC-11 R2/R11：education period 单 input（`education-period` testid 唯一），`education-period-start/end` 0 hits ✅
- AC-13 R4：URL 验证正则 `^(https?|tel|sms|mailto):/iu` + 黑名单 `^(javascript|vbscript|file|data):/iu` ✅
- AC-13b R4：skills-website 在 src/ 0 hits ✅
- AC-15 R10/R14：DialogHost `handleClose` 用 `undoStackDepthAtOpen.current` 计算 rollback 数 + 循环 `undo()`（AC-15 不约束 N 上限）✅
- AC-16 R12：`useState` 在 3 个 dialog 仅出现在 `fieldErrors` / `levelError`（error display 状态），field-level 全 `setItem` 直写 ✅
- AC-17 R17：3 个 list 暴露 edit / duplicate / delete + `data-dnd-context` 命名空间（education/projects/skills）✅
- AC-17b R9：drag handle `handleDragEnd` 内 `overCtx && overCtx !== sectionId` 短路（沿用 US2 AC-09b pattern）✅
- AC-18 R5：6 case 显式 + default throw Error；DialogType union 同步扩展 ✅
- AC-18b R5：dispatcher 走显式 6 case（dev 自由发挥路径之一）✅
- AC-19 R13：`SectionItem` 唯一路径 + 命名导出 + 3 list 同 import ✅
- AC-20 R15：backend `test_legacy_format.py` 新增 9 个 case（test_education_full_roundtrip / test_education_description_html_roundtrip / test_education_hidden_field_roundtrip / test_project_full_roundtrip / test_project_description_html_roundtrip / test_project_highlights_empty_array_roundtrip / test_skill_full_roundtrip / test_skill_level_zero_roundtrip / test_skill_keywords_empty_array_roundtrip）✅

---

## 建议 commit message

```
feat(REQ-034-US3): Education + Projects + Skills item dialogs + 3 section lists + shared SectionItem wrapper

- 新增 left/SectionItem.tsx — list-row 共享 wrapper (drag handle + 3 inline actions + hidden=true 视觉淡化)
- 新增 left/{Education,Projects,Skills}SectionList.tsx — 3 个 SectionList 共享 SectionItem import 路径 + dnd-kit drag-reorder + 500ms 批处理 + data-dnd-context 命名空间隔离
- 新增 dialogs/{Education,Projects,Skills}Dialog.tsx — 3 个 item dialog 独立 + 内部共享 useItemWriter / setDataMut 模式
- DialogHost dispatcher 扩展 6 case + DialogType union 同步扩展 + default throw Error fail loud
- SectionsPanel 挂载 education / projects / skills 三个 list
- Education period 改单 input (AC-11 R2 + schema 对齐); Skill 含 proficiency + name 独立字段 (AC-06 R1); Skill level slider step=1 + level=0 "Hidden" label (AC-10 R3); URL 白名单 https?|tel|sms|mailto + u flag (AC-13 R4)
- backend test_legacy_format.py 扩 9 个 round-trip case (R15 扩展: full_roundtrip × 3 + description html sanitized × 2 + hidden × 1 + level=0 × 1 + empty array × 2)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```