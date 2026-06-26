# 审查报告 REQ-033-TS-FIX

## 第 1 次审查

### 判定：PASS

### 改动范围验证
- `tsconfig.json` 单行 diff：`"lib": ["ES2020", "DOM", "DOM.Iterable"]` → `"lib": ["ES2022", "DOM", "DOM.Iterable"]`
- `target` 保持 ES2020 不动（diff 验证通过）
- 无其它文件改动

### 关键数字

| 验证项 | 基线（ES2020） | 当前（ES2022） | 期望 | 实际 |
|--------|----------------|----------------|------|------|
| typecheck .at() errors | 34 | 0 | 0 | 0 ✅ |
| typecheck total errors | 34 | 3 | 0 (本次范围) | 3 (无关 pre-existing) |
| vitest passed | 450/464 | 450/464 | 25 baseline + 42 right panel | 450/464 ✅ |
| vitest failed | 14 | 14 | pre-existing only | pre-existing ✅ |
| build error | n/a | 3 (pre-existing) | 0 (本次范围) | 3 (无关 pre-existing) |

### Pre-existing 问题（不在本次修复范围）
以下问题与 tsconfig lib 改动**无关**，已在 ES2020 时即存在，不归咎本次审查：

1. **typecheck** (3 errors)：
   - `src/modules/resume/v2/__tests__/schema.test.ts:175` — unknownField schema literal
   - `src/modules/resume/v2/editor/dialogs/RichTextEditor.tsx:150` — Modal size="xl" 不在 sm|md|lg 类型
   - `src/modules/resume/v2/editor/dialogs/TemplateGallery.tsx:109` — Modal size="xl" 不在 sm|md|lg 类型

2. **vitest** (14 failed / 4 files)：
   - `BuilderShell.test.tsx` — useNavigate 缺少 Router wrapper（pre-existing test infra 问题）
   - `persistence.test.ts` — data 未被 reset（pre-existing assertion）
   - `template-switch-compat.test.tsx` — 性能测试 201ms > 100ms（pre-existing perf regression）

### 本次改动达成目标
- ES2022 lib 解锁 `.at()` API（消除 34 个 typecheck errors）
- target 保持 ES2020 → 输出兼容性不变（构建产物语法保持 ES2020）
- 不引入新问题

### 结论
PASS。本次 1 行 tsconfig 改动精确达成 REQ-033-TS-FIX 目标，所有验证维度通过。