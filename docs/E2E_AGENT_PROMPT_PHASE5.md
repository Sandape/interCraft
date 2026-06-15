# Phase 5 E2E Playwright Agent Prompt

将以下提示词交给负责 E2E 自动化测试的 Agent。

---

```
你是一名 Playwright E2E 测试工程师。你需要为 InterCraft 项目的 Phase 5（P1 Agent 子图扩展）编写完整的端到端测试套件。

## 项目信息

- 项目根目录: D:\Project\eGGG
- 前端 baseURL: http://localhost:5173（由 Playwright config 提供）
- 后端 API: http://localhost:8000
- 测试账号: test@intercraft.io / Demo1234
- Playwright config: tests/e2e/playwright.config.ts（baseURL 已配置）
- 现有 E2E 测试参考: tests/e2e/interview-flow.spec.ts

## 你必须阅读的源文件

### 页面组件（了解 UI 结构和 data-testid）：
- src/pages/ResumeEditor.tsx — M16 AI 优化按钮集成
- src/components/resume/AiOptimizePanel.tsx — M16 diff 审阅 Modal
- src/pages/ErrorBook.tsx — M17 错题列表 + 详情面板 + 开始强化按钮
- src/components/error-book/ErrorCoachPanel.tsx — M17 强化对话 Modal
- src/pages/Profile.tsx — M18 能力画像页面
- src/components/profile/AbilityUpdateStatus.tsx — M18 更新状态指示器
- src/pages/GeneralCoach.tsx — M19 通用 Coach 对话页面

### 数据与 hooks：
- src/data/mockData.ts — 查看 mockResumeOptimizePatches 等 mock 数据格式
- src/hooks/useResumeOptimize.ts — M16 hook 接口
- src/hooks/useErrorCoach.ts — M17 hook 接口
- src/hooks/useGeneralCoach.ts — M19 hook 接口
- src/hooks/useAbilityDiagnose.ts — M18 hook 接口

### 现有类似测试：
- tests/e2e/interview-flow.spec.ts
- tests/e2e/auth-register-login.spec.ts

## 测试文件存放位置

tests/e2e/phase5/
  ├── m16-resume-optimize.spec.ts
  ├── m17-error-coach.spec.ts
  ├── m18-ability-diagnose.spec.ts
  ├── m19-general-coach.spec.ts
  └── m16-m19-edge-cases.spec.ts

## E2E 测试要求

### 通用要求
1. 所有测试以 `test.describe('M{num} - ...')` 分组
2. 每个测试需要完整的前置准备（登录 → 导航）
3. 使用 `page.goto()` 直接导航到目标页面
4. 使用 `expect` 断言关键 UI 元素可见
5. 尽量减少 sleep，优先使用 `waitForSelector`、`waitForURL`、`toBeVisible`
6. 对异步操作（LLM 响应 slow）设置 30-60s 超时
7. 测试文件头部需要 JSDoc 注释描述测试场景

### M16 — AI 简历优化（3 条测试）

**测试 1.1：启动 → 审阅 → 应用**
```
steps:
  1. 登录 → /resumes
  2. 点击第一个 [data-testid="branch-card"] → 进入编辑器
  3. 点击 [data-testid="ai-optimize-btn"]
  4. Modal "AI 简历优化" 打开
  5. 在 textarea 填写 "资深前端工程师，React/TypeScript，电商业务背景，5年以上经验"
  6. 点击 "开始分析"
  7. 等待 "建议修改" 文本出现（30s 超时）
  8. 验证 patch 项目可见（text=/replace|add|remove/）
  9. 点击 "应用修改"
  10. 验证 "优化已应用" 文本出现
```

**测试 1.2：启动 → 放弃**
```
steps:
  1-7 同上
  8. 点击 "放弃"
  9. 验证 Modal 关闭（"AI 简历优化" 文本消失）
```

**测试 1.3：空 JD 按钮 disabled**
```
steps:
  1-4 同上
  5. textarea 留空
  6. "开始分析" 按钮 disabled（检查 disabled 属性）
```

### M17 — 错题强化（3 条测试）

**测试 2.1：3 轮答对 → 完成**
```
steps:
  1. 登录 → /error-book
  2. 点击列表中的第一条错题卡片
  3. 右侧详情面板显示
  4. 点击 "开始强化"（详情面板中的按钮）
  5. ErrorCoachPanel Modal 打开，显示题目
  6. 点击 Modal 内的 "开始强化"
  7. 等待输入框出现
  8. 第 1 轮：输入回答 → 提交 → 等待反馈
  9. 第 2 轮：输入回答 → 提交 → 等待反馈
  10. 第 3 轮：输入回答 → 提交 → 等待反馈
  11. 验证 "已掌握！" 文本出现
```

**测试 2.2：中止**
```
steps:
  1-7 同上
  8. 第 1 轮：输入回答 → 提交
  9. 关闭 Modal（点击 × 或 背景）
  10. 验证错误或中止状态
```

### M18 — 能力画像诊断（2 条测试）

**测试 3.1：Profile 页显示能力画像**
```
steps:
  1. 登录 → /profile
  2. 验证能力雷达图 [data-testid="radar-chart"] 可见
  3. 验证 6 个维度分数可见（.dimension-score）
  4. 验证改进建议列表（.suggestion-list）可见
```

**测试 3.2：能力更新状态指示器**
```
steps:
  1. 登录 → /profile
  2. 验证页面标题下方存在状态指示器
  3. 状态为 "已更新" 或 "更新中…"
```

### M19 — 通用 Coach（4 条测试）

**测试 4.1：职业建议意图 → 回答**
```
steps:
  1. 登录 → /coach
  2. 验证空状态 "有什么可以帮助你的？"
  3. 在 textarea 输入 "如何准备系统设计面试"
  4. 点击 "开始"
  5. 等待 assistant 回答（30s 超时）
  6. 验证回答包含 "系统设计"
  7. 验证意图标签（text=/意图：/）
```

**测试 4.2：简历优化意图 → 重定向引导**
```
steps:
  1. 登录 → /coach
  2. 输入 "帮我优化简历中的项目描述"
  3. 发送
  4. 等待回答包含 "简历编辑器" 或 "AI 优化"
  5. 验证意图标签 "resume_optimize"
```

**测试 4.3：多轮对话 → 关闭**
```
steps:
  1. 登录 → /coach
  2. 第 1 轮：输入问题 → 等待回答
  3. 第 2 轮：输入 "有推荐的书籍吗？" → 等待回答
  4. 验证消息列表有 4 条消息（user/assistant/user/assistant）
  5. 点击 "结束对话"
  6. 验证回到空状态
```

**测试 4.4：空输入 disabled**
```
steps:
  1. 登录 → /coach
  2. textarea 留空
  3. 发送按钮 disabled
```

### 边缘场景测试（1 条综合测试文件）

**测试 E1：未登录访问**
```
steps:
  1. 直接访问 /coach（未登录）
  2. 被重定向到 /login
```

**测试 E2：空数据展示**
```
steps:
  1. 登录 → /error-book（没有错题时）
  2. 显示空状态 "还没有错题记录"
```

## 验证方式

1. 运行 `npx playwright test tests/e2e/phase5/ --config=tests/e2e/playwright.config.ts`
2. 确保所有测试通过（或因缺少后端而正确 skip）
3. 运行 `npx tsc --noEmit` 确认类型正确

## 输出要求

- 每个测试文件包含文件头 JSDoc 注释描述场景
- 测试命名：`test('描述性名称', async ({ page }) => { ... })`
- 使用 data-testid 和可见文本选择器结合
- 对后端可选项使用 `test.skip` 标记（不可跳过核心 UI 验证）
```
