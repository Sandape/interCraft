# Contract: Playwright Spec

**Date**: 2026-06-30 | **Spec**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md)

> Phase 1 — Playwright 验收脚本的契约与产出规范。

---

## File Location

`tests/e2e/036-resume-v2-finalize.spec.ts`

## Test Granularity

每个细分功能点 = 1 个 `test()`，总计 ≥ 25 个 `test()`：

| # | 测试 | 覆盖 |
|---|---|---|
| 1 | login + access /resume + empty state | 入口 + 空状态 CTA |
| 2 | topbar + dropdown shows single "新建简历" | Topbar 收口 |
| 3 | template gallery modal opens | Template Gallery 触发 |
| 4 | select template + create + navigate to /resume/:id | 新建流程 |
| 5 | editor header / breadcrumb / sidebar toggle | 编辑器顶部 |
| 6 | left section list 13 built-in sections | Section 列表展开/折叠 |
| 7 | right settings 12 sub-panels | Settings 面板展开/折叠 |
| 8 | experience item dialog create/edit/delete | Dialog 1/10 |
| 9 | education item dialog | Dialog 2/10 |
| 10 | projects item dialog | Dialog 3/10 |
| 11 | skills item dialog (with level) | Dialog 4/10 |
| 12 | profiles item dialog (network picker) | Dialog 5/10 |
| 13 | languages item dialog | Dialog 6/10 |
| 14 | interests item dialog | Dialog 7/10 |
| 15 | awards item dialog | Dialog 8/10 |
| 16 | certifications item dialog | Dialog 9/10 |
| 17 | references item dialog | Dialog 10/10 |
| 18 | Tiptap rich text toolbar 15+ features | 富文本 |
| 19 | dock button zoom in/out | Dock 1/8 |
| 20 | dock button center view | Dock 2/8 |
| 21 | dock button toggle page stacking | Dock 3/8 |
| 22 | dock button open AI agent | Dock 4/8 |
| 23 | dock button copy URL | Dock 5/8 |
| 24 | dock button download JSON | Dock 6/8 |
| 25 | dock button download PDF | Dock 7/8 |
| 26 | settings panel template gallery switch | 模板切换 |
| 27 | settings panel typography (body/heading) | 字体调整 |
| 28 | settings panel design (colors + level) | 设计调整 |
| 29 | settings panel page (format/margins) | 页面调整 |
| 30 | settings panel sharing + statistics | 分享 |
| 31 | undo/redo (Ctrl+Z / Ctrl+Shift+Z) | 历史栈 |
| 32 | auto-save 500ms debounce | 自动保存 |
| 33 | mobile sidebar collapse | 移动端 |
| 34 | public URL `/r/:u/:slug` access | 公开访问 |
| 35 | cross-module link interview → /resume | 跨模块引用 |

**主流程额外覆盖**（贯穿多个 test）：
- 完整填写一份简历（参照 `大模型应用开发简历v1.md`）→ 导出 PDF

## Strict UI-Only Constraint

**禁止**使用 API 注入数据。允许的操作：
- `page.click()`
- `page.fill()`
- `page.type()`
- `page.locator(...).press(...)`
- `page.locator(...).selectOption(...)`
- `page.locator(...).check() / uncheck()`
- `page.locator(...).dragTo(...)`
- `page.evaluate()` — 仅用于读取 DOM（如 `getAttribute`），不允许写 store
- `page.request.*` — **禁止**（直接命中 API）

**允许的辅助操作**：
- `page.goto()` — 导航（不是数据注入）
- `page.waitFor*()` — 等待
- `page.screenshot()` — 截图证据

## Test Setup

```typescript
import { test, expect, type Page } from '@playwright/test'
import * as fs from 'node:fs/promises'
import * as path from 'node:path'

const EVIDENCE_DIR = `docs/evidence/036-playwright-${new Date().toISOString().replace(/[:.]/g, '-')}`

test.beforeAll(async () => {
  await fs.mkdir(EVIDENCE_DIR, { recursive: true })
})

test.afterAll(async () => {
  // 写两份清单
  await generateIncompleteList(EVIDENCE_DIR)
  await generateAcceptedList(EVIDENCE_DIR)
})

// 每个 test() 内部：
test('login + access /resume + empty state', async ({ page }) => {
  // 1. 登录
  await page.goto('/login')
  await page.fill('[data-testid="email-input"]', '...')
  await page.fill('[data-testid="password-input"]', '...')
  await page.click('[data-testid="login-button"]')
  
  // 2. 访问 /resume
  await page.goto('/resume')
  await page.waitForSelector('[data-testid="empty-state-cta"]')
  
  // 3. 截图证据
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, 'step-01-empty-state.png'),
    fullPage: true,
  })
  
  // 4. 断言
  await expect(page.getByText('创建你的第一份简历')).toBeVisible()
})
```

## Evidence Output

每个 `test()` MUST 在以下路径产出证据：

```
docs/evidence/036-playwright-<ts>/
├── step-<NN>-<feature>.png          # 每个 test 1 张全屏截图
├── test-results.json                 # { test_name: { status, screenshot, duration_ms } }
├── final-resume.pdf                  # 主流程完成后导出的 PDF
├── field-comparison.md               # 与参考简历字段对比报告
├── incomplete-features.md            # 未完成功能清单
└── accepted-features.md              # 已完成验收功能清单
```

## Two Lists Specification

### `incomplete-features.md` 格式

```markdown
# 未完成功能清单

**生成时间**: <ts>
**Playwright 测试轮次**: <N>/35 通过
**总分**: <X>/35 = <Y>%

## 未通过的功能点（按优先级）

### P1 - 阻塞
| 功能 | 失败 selector | 现象 | 截图 | 修复建议 |
|---|---|---|---|---|
| Settings - Design - Colors | `data-testid="color-primary"` | 找不到 selector；编辑器无法调整主色 | `step-XX-design-colors.png` | 参考 reactive-resume `apps/artboard/src/components/sidebars/left/sections/design.tsx` 确认字段命名 |

### P2 - 非阻塞
| 功能 | 失败原因 |
|---|---|
| (空) | — |

### P3 - 已知缺口
| 功能 | 备注 |
|---|---|
| (空) | — |

## 待修复项（按模块）

### 编辑器对话框
- [ ] Experience item dialog 中 "website" 字段缺失 reference → 参考 `reactive-resume/apps/artboard/src/dialogs/resume/sections/experience.tsx`

### Settings 面板
- (无)

### 后端接口
- (无)
```

### `accepted-features.md` 格式

```markdown
# 已完成验收功能清单

**生成时间**: <ts>
**Playwright 测试轮次**: <N>/35 通过

## P1 必做（全部通过）

### 入口
- [x] **登录**：step-01-login.png — 通过
- [x] **访问 /resume**：step-02-resume-empty.png — 通过
- [x] **Topbar + 菜单单按钮**：step-03-topbar-plus.png — 通过
- [x] **侧边栏单一简历入口**：step-04-sidebar.png — 通过

### 新建流程
- [x] **Template Gallery 弹出**：step-05-template-gallery.png — 通过
- [x] **选择 Pikachu 模板创建**：step-06-created.png — 通过

### 编辑器
- [x] **Basics 表单**：step-07-basics.png — 填字段：姓名=李祖荫 / 邮箱=3080340895@qq.com / 电话=... / 学校=天津科技大学 — 通过
- [x] **Summary 富文本**：step-08-summary.png — 填 6 条亮点 — 通过
... (35 项)

## P2 应做（≥ 80% 通过）
...

## P3 可选
...

## 字段对比摘要

详见 [field-comparison.md](./field-comparison.md)

| 字段 | 参考简历 | Playwright 创建 | 一致 |
|---|---|---|---|
| 姓名 | 李祖荫 | 李祖荫 | ✅ |
| 邮箱 | 3080340895@qq.com | 3080340895@qq.com | ✅ |
| ... | ... | ... | ... |
```

## Failure Recovery

如果某个 `test()` 失败：

1. 主 Agent 检查截图 + 错误日志
2. 在 `incomplete-features.md` 追加失败项
3. **若问题在 v2 编辑器代码侧** → 主 Agent 参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 修复
4. 修复后重跑 Playwright；通过则追加到 `accepted-features.md`
5. 重复直到 ≥ 80% 通过率

## Performance Budget

- 单个 `test()` ≤ 60 秒
- 总脚本 ≤ 10 分钟
- 截图 PNG ≤ 5MB each

## References

- 036 spec FR-031~FR-035: Playwright 验收
- 036 research Decision 3: 多 test() 隔离
- 036 research Decision 7: 25+ 测试粒度（基于用户 2026-06-30 补充）
- reactive-resume 源码: `D:\Project\reactive-resume`