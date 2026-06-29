# 审查报告 REQ-034-US2

## 第 1 次审查

## Summary

- 范围：ExperienceDialog（new）+ ExperienceSectionList（new）+ DialogHost dispatcher 扩展 + SectionsPanel 挂载 + 4 个测试文件 + backend 3 case
- 测试运行：`npx vitest run` 3 个测试文件 → **30/30 passed**
- 26 ACs 中 **24 通过**，**2 缺失实现**（AC-08b drag 批处理、AC-09c 键盘交互验证弱化）
- 4 个问题（2 严重，1 中等，1 轻微）

## Architecture Compliance

| 检查 | 结论 | 备注 |
|------|------|------|
| L008 module shadow — `dialogs.ts` / `left.ts` 存在？ | PASS | 仅 .tsx 文件，无 shadow |
| L008 consumer 走命名导入 | PASS | `DialogHost.tsx:24` 命名导入 `ExperienceDialog`；`SectionsPanel.tsx:23` 命名导入 `ExperienceSectionList` |
| L009 default export 一致性 | **FAIL** | 见 Issues #1 |
| dispatcher 扩展模式 | PASS | 复用既有 `useDialogStore` + `DialogSpec` 接口 |
| `setDataMut` immer draft 模式 | PASS | 与 US1 一致（`setDataMut((draft) => {...})`） |
| 复用 US1 `useResumeV2Store` | PASS | 走 `setDataMut` 触发 500ms debounce autosave + undoStack |
| `data-dnd-context="items"` 命名空间 | PASS | ExperienceSectionList.tsx:183 标记 |
| SectionItem 复用结构清晰 | PASS | `SortableItemRow` + `SortableRoleRow` 同款 dnd-kit 模式 |
| 错误处理（unknown type） | PASS | DialogHost.tsx:155-162 throw Error（AC-11b-revised 通过） |
| Backend round-trip test 完整 | PASS | `test_legacy_format.py` 3 case（full_roundtrip + hidden + html_roundtrip） |

## Security Review

| 检查 | 结论 | 证据 |
|------|------|------|
| `dangerouslySetInnerHTML` in row | PASS | `git grep` 0 hits；测试 AC-12b-extended 验证 `row.querySelector('b') === null` |
| `dangerouslySetInnerHTML` in dialog | PASS | `git grep` 0 hits；XSS payload 走 React text node 渲染 |
| URL 白名单 regex + `u` flag | PASS | `ExperienceDialog.tsx:64-65` `/^(javascript\|vbscript\|file\|data):/iu` + `/^(https?\|tel\|sms\|mailto):/iu` |
| 接受 IPv6 / unicode URL | PASS | test `accepts tel: / mailto: / IPv6 / unicode` 通过 |
| URL 黑名单 | PASS | `javascript: / data: / vbscript: / file:` 被拒并 fireToast('warn') |
| 输入 maxLength 防御 | PASS | TEXT_MAX=256, PERIOD_MAX=64, URL_MAX=2048, LABEL_MAX=64, DESC_MAX=4096 |
| `hidden=true` 视觉淡化 | PASS | `opacity-60 line-through` (line 279) + `data-hidden` attribute |
| 后端 HTML 描述存储 | KNOWN | `test_experience_description_html_roundtrip` 注释明确：存储端不做 sanitization，sanitization 在 PDF renderer；测试 pinned 当前行为 |
| SQL 注入 | N/A | 纯前端组件；后端走 SQLAlchemy bind |

## L008 / L009 / L011 Lint Check

| ID | 命令 | 期望 | 实际 |
|----|------|------|------|
| L008 | `ls src/modules/resume/v2/editor/dialogs/*.ts` | 0 hits | 0 hits ✅ |
| L008 | `ls src/modules/resume/v2/editor/left/*.ts` | 0 hits | 0 hits ✅ |
| L009 | `grep -n "export default function ExperienceDialog\|export default function ExperienceSectionList" src/modules/resume/v2/editor/` | 0 hits | **2 hits** ❌（见 Issues #1） |
| L011c | `grep -n "default: return null\|default: null" src/modules/resume/v2/editor/dialogs/DialogHost.tsx` | 0 hits | 0 hits ✅ |
| L011 | `grep -n "dangerouslySetInnerHTML" src/modules/resume/v2/editor/left/ExperienceSectionList.tsx` | 0 hits | 0 hits ✅ |
| AC-11b | `grep -rn "'experience\.create-item'\|'experience\.update-item'\|'experience\.add'\|'experience\.edit'\|'experience\.delete'" src/` | 0 hits | 0 hits ✅（DialogHost.tsx:36 注释中显式声明 `'experience.delete'` 不存在是合理的解释） |
| L011 (R12) | immer property-level mutate | 属性级 | 字段直写 `d.company = ...` 模式 ✅；roles 拖拽用 `arrayMove` + `d.roles = moved` ⚠️（见 Issues #3） |
| AC-14 | `useState` in ExperienceDialog | 仅 `fieldErrors` | `useState<Record<string, string>>({})` for fieldErrors + 1 行 `void useRef`（见 Issues #4） |
| AC-09b | `data-dnd-context="items"` 标记 | 存在 | ExperienceSectionList.tsx:183 ✅ |

## Issues Found

| # | 严重度 | 维度 | 位置 | 原因 | 修改建议 |
|---|--------|------|------|------|----------|
| 1 | 严重 | L009 命名导出 | `ExperienceDialog.tsx:588` + `ExperienceSectionList.tsx:332` | `export default` 冗余，违反 AC-12b 静态检查。consumer 全部走命名导入（DialogHost.tsx:24, SectionsPanel.tsx:23），与右栏 panels 改造（DesignPanel/LayoutPanel 等已统一到 `export function`）不一致 | 删除 2 行 `export default` 即可；右栏改造已示范该 pattern |
| 2 | 严重 | AC-08b 实现缺失 | `ExperienceDialog.tsx:229-239` (`reorderRoles`) + `ExperienceSectionList.tsx:155-178` (`handleDragEnd`) | drag-reorder 每次 onDragEnd 立即触发 `setDataMut` → undoStack +1 帧；spec 起草说明"AC-08b 必走 500ms 批处理"，R3 接受原因明确"连续 drag 20 帧塞满 undoStack 挤出用户编辑" | 引入 `useDebouncedCallback` / trailing 500ms 合并：保存首次 drag snapshot，500ms 内只 commit 终态 setDataMut；保持单次 undo 能恢复拖拽前顺序 |
| 3 | 中等 | immer R12 内部一致性 | `ExperienceSectionList.tsx:174-176` (`handleDragEnd`) | `arrayMove` 返回新数组，code 走 `arr.splice(0, arr.length, ...moved)` 整数组替换（不是属性级 mutate）；dnd-kit sortable context 缓存依赖 `roles` 引用一致性，整数组替换会触发不必要的 re-render。同类问题在 `ExperienceDialog.tsx:236-237` `d.roles = moved` | 改用属性级 mutate：`for (let i=0; i<moved.length; i++) arr[i] = moved[i]; arr.length = moved.length;` 或 dnd-kit 推荐的 `arr.splice(...)` 单元素 swap |
| 4 | 轻微 | 代码风格 | `ExperienceDialog.tsx:28,592` + `ExperienceSectionList.tsx:19,334` | 导入 `useRef` 但未使用，靠 `void useRef;` 抑制 lint warning（hack） | 删除 `useRef` 导入 + 删除 `void useRef;` 行；或实际启用 focus management ref |

### 额外观察（不阻塞）

- **AC-08b 测试覆盖缺失**：`ExperienceDialog.test.tsx:263-299` describe 注释 `drag-reorder (AC-08, AC-08b)` 但实际只测了 AC-08 一次性 reorder；`vi.advanceTimersByTime(500)` + 5×onDragEnd 合并断言缺失。Issue #2 修复时一并补 test
- **AC-09c 键盘测试弱化**：`ExperienceSectionList.test.tsx:243-272` 仅验证静态 `aria-roledescription="sortable"` + `role` 属性，未实际模拟 Space/Arrow 键盘事件（jsdom 限制下 dnd-kit KeyboardSensor 难以模拟，但至少应尝试 `fireEvent.keyDown(row, {key:' '})` + 验证 `data-dragging`）；建议加 `// AC-09c partial — full keyboard sim requires dnd-kit integration test`
- **`experience.create` dispatcher 行为**：DialogHost.tsx:139 对 `experience.create` 调用 `ExperienceDialog itemId=""`，立即进入 `if (!item)` 防御分支并 `setTimeout(onClose, 0)`。这是设计意图（line 131-134 注释），但用户体验上 `experience.create` 等同 dead code；当前所有 caller 走 `SectionList.handleAdd` 提前 push + 改派 `experience.update`。建议未来移除 `experience.create` case，或在 `DialogHost` 注释中明示"DEPRECATED: use experience.update after pushing empty item"
- **AC-04b toast 文案模糊**：`ExperienceDialog.tsx:397-400` toast 写"切换将隐藏现有 description 字段(已自动隐藏,后续切回可继续编辑)"，但实际不会清空 description（roles 非空时 description DOM 不渲染但 store 值保留）。测试只断言 `fireToast` 被以 `'warn'` 级别调用，描述不够 informative
- **`hidden` checkbox 走 `setText("hidden", "true"|"false")` 字符串**：ExperienceDialog.tsx:358 将 boolean 序列化为字符串再写入 schema（schema 可能是 boolean 或 string），依赖 schema 容忍；建议改用 `setItem(d => { d.hidden = e.target.checked })` 直接属性级 mutate

## 测试结果

```
Test Files  3 passed (3)
Tests       30 passed (30)
Duration    3.75s
```

测试文件：ExperienceDialog.test.tsx (12) + ExperienceSectionList.test.tsx (8) + DialogHost.test.tsx (9+1=10) + DialogHost 新增 case

## 判定：FAIL

**理由**：
- Issue #1 L009 命名导出违规是 blocker（spec 必避陷阱，ac-matrix 显式 cast 死）
- Issue #2 AC-08b 500ms drag 批处理未实现 + 测试缺失，是 26 AC 中明确 lock 的高优先级反例（R3 接受）
- Issue #3 immer 整数组替换与 R12 reviewer 把关要求相左
- Issue #4 是 code smell 但不阻塞

## 失败教训（供 main agent 写入 lessons.json）

```json
{
  "category": "review-pattern",
  "title": "命名导出 + 拖拽批处理 双漏防",
  "problem": "US2 实施在新 dialog / list 文件尾部同时加了冗余 `export default`（违反 L009 grep 静态检查），且 drag-reorder 未做 500ms undoStack 批处理（违反 AC-08b 显式约束）。两处都是 spec ac-matrix 锁定陷阱，dev 端没有强制 lint 守住",
  "fix_hint": "(1) review 阶段先跑 `git grep 'export default function' src/modules/resume/v2/editor/` 静态扫描；(2) 涉及 dnd-kit 拖拽的组件优先实现 `useDebouncedCallback` wrapper 包裹 setDataMut；(3) 右栏 panels（Design/Layout/Page/Styles/Typography）已示范 `export function` 统一 pattern，dev 端可加 eslint rule `import/no-default-export` 强制"
}
```

## 下一步

主 Agent 推 dev 修复 Issues #1 #2 #3（#4 顺手）：
1. 删除 2 处 `export default`
2. 引入 `useDebouncedCallback`（500ms trailing）包裹 `reorderRoles` / `handleDragEnd`，首次 drag 拍 snapshot，500ms 内只 commit 终态
3. 拖拽 mutate 改属性级（不用 `d.roles = moved` / `arr.splice(0, n, ...moved)`）
4. 补 AC-08b 拖拽批处理测试
5. 顺手删除 `useRef` 未使用导入

修复完成后由 reviewer 复审 AC-08b 实现 + L009 grep 干净后 PASS。

## 建议 commit message

```text
feat(034): REQ-034-US2 Experience item dialog + roles[] + section-item list + add-button

- ExperienceDialog: 9 top-level fields + roles[] add/remove/dnd-kit reorder
- ExperienceSectionList: items[] sortable + 3 inline actions (edit/duplicate/delete)
- DialogHost dispatcher 扩展: 'experience.create' | 'experience.update' + unknown type throw
- URL 白名单: https?|tel|sms|mailto + 黑名单 javascript|vbscript|file|data + u flag
- 26 ACs 全部 lock（24 实现 / 2 由 R3 R12 reviewer 把关）

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

注：本审查 FAIL，未 commit。
