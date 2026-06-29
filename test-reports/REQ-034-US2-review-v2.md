# 审查报告 REQ-034-US2

## 第 2 次审查（重审）

## Re-Review Summary

仅核验 4 个 FAIL 项的修复情况。范围不超出 `ExperienceDialog.tsx` / `ExperienceSectionList.tsx` / 2 个测试文件。
US1 已 ship 的 BasicsDialog / PictureDialog / DialogHost / SectionsPanel / PagePanel / TypographyPanel 中的 `export default` 保留不动。

## Issues Verification Table

| # | 严重度 | 描述 | 状态 | 证据 |
|---|--------|------|------|------|
| 1 | 严重 | L009 命名导出违规 | **FIXED** | `grep -n "export default function ExperienceDialog\|export default function ExperienceSectionList" src/modules/resume/v2/editor/` → 0 hits。`ExperienceDialog.tsx:157` 与 `ExperienceSectionList.tsx:95` 均为 `export function` 命名导出。dialog 文件尾部 `export { NEW_ID as NEW_EXPERIENCE_ID }`（重新导出常量，非 default export） |
| 2 | 严重 | AC-08b 500ms 拖拽批处理未实现 | **FIXED** | `ExperienceDialog.tsx:68,178-181,248-285` 引入 `DRAG_BATCH_MS=500` + `dragBatchRef` + 500ms setTimeout 重置 + 首个 drag 走默认 setDataMut（推 undo snapshot），后续 drag 走 `{ skipHistory: true }`。`ExperienceSectionList.tsx:45,110-113,182-215` 同款。`ExperienceDialog.test.tsx:300-366` 新增 test "5 rapid onDragEnd events within 500ms collapse into 1 undoStack entry (AC-08b)"，断言 `undoAfter === undoBefore + 1` + captured snapshot 为 pre-drag 顺序 + 1 次 undo 恢复原序。`ExperienceSectionList.test.tsx:280-349` 同款 list 端 test |
| 3 | 中等 | immer R12 整数组替换 | **FIXED** | `ExperienceDialog.tsx:269-270`：`const [movedItem] = target.roles.splice(oldIdx, 1); target.roles.splice(newIdx, 0, movedItem);` — 属性级 mutate，roles 引用稳定。`ExperienceSectionList.tsx:199-200`：`const [movedItem] = arr.splice(oldIdx, 1); arr.splice(newIdx, 0, movedItem);` — 同样属性级 mutate。已无 `d.roles = moved` / `arr.splice(0, n, ...moved)` 整数组替换 |
| 4 | 轻微 | useRef unused + `void useRef;` hack | **FIXED** | `useRef` 现已实际用于 `dragBatchRef` (ExperienceDialog.tsx:178, ExperienceSectionList.tsx:110)。`grep "void useRef" src/modules/resume/v2/editor/` → 0 hits。hack 已删除 |

## 重新跑测试结果

```
$ npx vitest run src/modules/resume/v2/editor/dialogs/__tests__/ExperienceDialog.test.tsx \
                 src/modules/resume/v2/editor/left/__tests__/ExperienceSectionList.test.tsx

Test Files  2 passed (2)
Tests       23 passed (23)
Duration    3.25s
```

新增测试用例（验证 AC-08b 500ms 批处理）：
- `ExperienceDialog.test.tsx:300-366` — "5 rapid onDragEnd events within 500ms collapse into 1 undoStack entry (AC-08b)" → PASS
- `ExperienceSectionList.test.tsx:280-349` — "5 rapid drag-end events within 500ms collapse into 1 undoStack entry" → PASS

子断言全部通过：
- `undoAfter === undoBefore + 1` ✅
- captured snapshot 为 pre-drag 顺序 [r1, r2, r3] / [e1, e2, e3] ✅
- 1 次 undo 后 store 恢复 pre-drag 顺序 ✅

### 判定：PASS

**理由**：
- 4 个 issues 全部 FIXED
- 23/23 测试通过（含 2 个新加 AC-08b 用例）
- L009 静态检查 0 hits
- 既有 21 个用例无回归
- US1 已 ship 文件未触碰

## 建议 commit message

```text
fix(034): REQ-034-US2 resolve review issues #1-#4

- L009: drop redundant `export default` from ExperienceDialog + ExperienceSectionList
  (use named `export function` to align with right-rail panels pattern)
- AC-08b: implement 500ms drag-reorder batch via dragBatchRef
  (first onDragEnd pushes undo snapshot, subsequent in window apply with skipHistory:true)
- R12: replace `d.roles = moved` with `arr.splice` property-level mutate
  (preserve id set + stable draft reference for dnd-kit SortableContext cache)
- useRef: actually wire dragBatchRef instead of `void useRef` lint-hack
- tests: add AC-08b batch coverage (5 rapid onDragEnd → 1 undoStack entry → 1 undo restores)

All 23 tests pass (21 prior + 2 new AC-08b cases). grep L009 clean.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

## 下一步

主 Agent 可指示 commit + 推进 REQ-034-US3。
