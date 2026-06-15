# Phase 5 E2E 测试工作流 — P1 Agent 子图扩展

> **目标版本**: 2026-06-15 | **涉及模块**: M16–M19
> **前置条件**: Phase 1-4 全部部署运行，Phase 4 M14 LangGraph 基础设施已落地
> **测试账号**: test@intercraft.io / Demo1234

---

## 目录

1. [M16 — AI 简历优化 (Resume Optimize)](#m16--ai-简历优化-resume-optimize)
2. [M17 — 错题强化 (Error Coach)](#m17--错题强化-error-coach)
3. [M18 — 能力画像自动诊断 (Ability Diagnose)](#m18--能力画像自动诊断-ability-diagnose)
4. [M19 — 通用 Coach (General Coach)](#m19--通用-coach-general-coach)
5. [边缘场景与异常测试](#边缘场景与异常测试)
6. [回归检查清单](#回归检查清单)

---

## M16 — AI 简历优化 (Resume Optimize)

### 测试数据

| 字段 | 值 |
|------|-----|
| 测试用户 | test@intercraft.io |
| 简历分支 | 取第一个可用分支（`[data-testid="branch-card"]`） |
| 目标 JD | `资深前端工程师，React/TypeScript，电商业务背景，5年以上经验` |
| 预期 patches | 3 条（replace/add/replace） |

### 工作流 1.1：启动优化 → 审阅 diff → 应用 → 验证版本

```
UI 流：
  登录 → /resumes → 点击首个分支卡片
  → 进入简历编辑器，页面 URL 为 /resumes/{branchId}/editor
  → 在分支元信息栏点击 data-testid="ai-optimize-btn"
  → Modal 打开，标题 "AI 简历优化"
  → 在 textarea 中填写目标 JD
  → 点击 "开始分析"
  → 等待分析完成（loading spinner 消失）
  → diff 面板显示 proposed_patches（"建议修改 (N 项)"）
  → 点击 "应用修改"
  → 显示成功状态 "优化已应用" + version ID

后端验证：
  GET /api/v1/agents/resume-optimize/{thread_id}/state
  → status = "completed"
  → version_id 非空

数据验证（DB）：
  SELECT * FROM resume_versions WHERE branch_id = '{branch_id}' AND author_type = 'ai' AND trigger = 'ai'
  → 至少 1 条记录

  SELECT * FROM resume_blocks WHERE branch_id = '{branch_id}' AND content LIKE '%抖音电商中后台%'
  → 找到更新后的块内容

锁验证：
  GET /api/v1/locks/status?resource_type=resume_branch&resource_id={branch_id}
  → 锁已释放（返回未锁定）
```

### 工作流 1.2：启动优化 → 放弃修改

```
UI 流：
  登录 → /resumes → 进入编辑器 → 点击 AI 优化
  → 填写 JD → 开始分析
  → 等待 diff 面板显示
  → 点击 "放弃"
  → Modal 关闭
  → 简历内容未变化

后端验证：
  GET /api/v1/agents/resume-optimize/{thread_id}/state
  → status = "completed"
  → version_id = null
```

### 工作流 1.3：锁冲突（双浏览器）

```
准备工作流（需两个浏览器上下文）：
  浏览器 A：
    登录 → 进入简历编辑器 → 点击 AI 优化 → 填写 JD → 开始分析
    → 等待 interrupt（停在 "应用/放弃" 页面，不操作）

  浏览器 B（同一用户 或 不同用户）：
    登录 → 进入同一简历编辑器
    → 点击 AI 优化 → 填写 JD → 开始分析
    → 期望：收到 423 Locked 错误
    → UI 上显示 "资源已被锁定" 提示
```

### 工作流 1.4：锁超时自动释放（不需要 UI）

```
API 直接验证：
  1. POST start → 获取 thread_id
  2. 不 confirm，等待 30 分钟 + 5s 缓冲（或手动触发巡检 CRON）
  3. 锁超时自动释放
  4. 再次对该分支 start → 应该成功（非 423）

注意：E2E 中可跳过 30 分钟等待，仅验证代码路径存在即可。
可直接调用 ARQ task：
  uv run python -m app.workers.tasks.resume_optimize_timeout
```

### 关键选择器

| 元素 | 选择器 |
|------|--------|
| AI 优化按钮 | `[data-testid="ai-optimize-btn"]` |
| Modal 标题 | `text="AI 简历优化"` |
| JD 输入框 | Modal 中第一个 `textarea` |
| 开始分析按钮 | `button:has-text("开始分析")` |
| Diff 面板 | `text="建议修改"` |
| Patch 操作标签 | `text=/replace\|add\|remove/` |
| 应用按钮 | `button:has-text("应用修改")` |
| 放弃按钮 | `button:has-text("放弃")` |
| 成功状态 | `text="优化已应用"` |
| 失败状态 | `text="放弃修改"` |
| 错误提示 | `.text-danger-500, .text-danger-400` |

---

## M17 — 错题强化 (Error Coach)

### 测试数据

| 字段 | 值 |
|------|-----|
| 测试用户 | test@intercraft.io |
| 错题 | 取 frequency > 0 的第一条错题 |
| 3 轮回答 | 每轮输入有意义的参考答案 |

### 工作流 2.1：3 轮答对 → frequency 递减

```
UI 流：
  登录 → /error-book
  → 在左侧列表中选择一条错题（frequency > 0）
  → 右侧详情面板显示错题信息
  → 点击 "开始强化" 按钮
  → ErrorCoachPanel Modal 打开，标题 "错题强化"
  → 点击 "开始强化"（Modal 内按钮）
  → 显示题目 + 输入框 + 提示等级

  第 1 轮：
  → 输入回答（提示等级 small 可见）
  → 点击 "提交" 或按 Enter
  → 看到评分反馈

  第 2 轮：
  → 输入另一段回答
  → 提交
  → 看到评分反馈 + 提示等级变为 medium

  第 3 轮：
  → 输入第三段回答
  → 提交
  → 看到 "已掌握！" 完成状态
  → 显示 "答对 3 题，本题 frequency 已递减"

  验证：
  → 关闭 Modal
  → 再次查看错题 frequency 应减 1
  → 如果原 frequency = 3，现 frequency = 2
```

### 工作流 2.2：中途中止

```
UI 流：
  登录 → /error-book
  → 选择错题 → 开始强化
  → 第 1 轮提交（未答对）
  → 点击 Modal 关闭按钮（×）或 "结束对话"
  → 确认状态 "已退出"
  → 显示 "本次答对 N 题"
```

### 工作流 2.3：错题 completion（frequency → 0 → mastered）

```
前提：选择 frequency = 1 的错题
UI 流：
  → 3 轮答对
  → frequency 变为 0
  → 页面刷新后
  → 错题状态变为 "已掌握"（StatusBadge 显示 mastered）
  → "开始强化" 按钮不再显示（frequency = 0 时隐藏）
```

### 关键选择器

| 元素 | 选择器 |
|------|--------|
| 错题列表卡片 | `.card`（列表中） |
| 详情面板 "开始强化" | `button:has-text("开始强化")` |
| ErrorCoachPanel Modal | `text="错题强化"` |
| Modal 内 "开始强化" | `button:has-text("开始强化")`（Modal 内） |
| 回答输入框 | Modal 中 `textarea` |
| 提交按钮 | `button:has-text("提交")` |
| 正确次数 | `text=/正确次数/` |
| 完成状态 | `text="已掌握！"` |
| 中止状态 | `text="已退出"` |
| StatusBadge mastered | `.status-badge-mastered` |

---

## M18 — 能力画像自动诊断 (Ability Diagnose)

### 测试数据

| 字段 | 值 |
|------|-----|
| 测试用户 | test@intercraft.io |
| 面试 session | 完成一场面试后自动触发 |
| 观察维度 | 6 维度（技术深度、系统设计、工程实践、沟通表达、算法能力、业务理解） |

### 工作流 3.1：面试 → 自动诊断 → Profile 页显示更新

```
UI 流（跨 Phase 4 + Phase 5）：
  预置条件：完成一场完整的模拟面试
  → 面试报告页面出现（/interviews/{id}/report）
  → 等待 10-30 秒（ARQ 调度窗口）

  进入 Profile：
  登录 → /profile
  → 页面标题下方显示 "能力画像更新中…" 或 "已更新"
  → 6 维度雷达图显示最新分数
  → 每个维度有改进建议列表

  验证活动流：
  → 在活动列表中看到 "能力画像已更新" 或类似记录
  → 成长轨迹曲线可用
```

### 工作流 3.2：手动触发诊断（API 验证用）

```
API：
  ARQ 手动触发：
    uv run python -m app.workers.tasks.diagnose_after_interview --user-id {user_id} --session-id {session_id}

  DB 验证：
    SELECT * FROM ability_dimensions WHERE user_id = '{user_id}'
    → actual 分数已更新

    SELECT * FROM activities WHERE user_id = '{user_id}' AND type = 'ability.suggestion'
    → 有建议记录

    SELECT * FROM ability_dimensions_history WHERE user_id = '{user_id}'
    → 有历史记录
```

### 关键选择器

| 元素 | 选择器 |
|------|--------|
| 能力更新状态 | `text=/能力画像更新中|已更新/` |
| 雷达图 | `[data-testid="radar-chart"]` |
| 维度分数 | `.dimension-score` |
| 改进建议列表 | `.suggestion-list` |
| 成长轨迹 | `[data-testid="growth-trajectory"]` |
| 活动流项目 | `text="能力画像已更新"` |

---

## M19 — 通用 Coach (General Coach)

### 测试数据

| 字段 | 值 |
|------|-----|
| 测试用户 | test@intercraft.io |
| 问题 1 | `如何准备系统设计面试` |
| 问题 2 | `帮我优化简历中的项目描述` |
| 问题 3 | `今天天气怎么样` |
| 问题 4 | `请解释 React Fiber 的工作原理` |

### 工作流 4.1：职业建议意图 → 流式回答

```
UI 流：
  登录 → /coach
  → 空状态页显示 "有什么可以帮助你的？"
  → 在 textarea 中输入 "如何准备系统设计面试"
  → 点击 "开始" 按钮 或 按 Enter
  → 等待加载状态

  → assistant 气泡出现
  → 内容包含 "系统设计" 关键词
  → 页面底部出现 "意图：career_advice" 标签
  → 可以继续输入后续问题

  验证：
  → 滚动到消息列表底部
  → 消息历史中 2 条记录（user + assistant）
  → 意图标签正确
```

### 工作流 4.2：简历优化意图 → 跳转引导

```
UI 流：
  登录 → /coach
  → 输入 "帮我优化简历中的项目描述"
  → 发送
  → assistant 回答中包含 "简历编辑器" 或 "AI 优化" 关键词
  → 意图标签 = "resume_optimize"
  → 页面显示重定向引导面板（"检测到您的问题属于「resume_optimize」范畴"）
  → redirect_to = "/resume"
```

### 工作流 4.3：闲聊意图

```
UI 流：
  登录 → /coach
  → 输入 "今天天气怎么样"
  → 发送
  → assistant 回答（不拒绝，进行一般性回应）
  → 意图标签 = "chitchat"

注意：确定性低，可只验证返回非空且不崩溃即可。
```

### 工作流 4.4：多轮对话 → 关闭

```
UI 流：
  登录 → /coach
  → 第 1 轮：输入 "如何准备系统设计面试" → 等待回答
  → 第 2 轮：输入 "有什么推荐的书吗" → 等待回答
  → 点击 "结束对话"
  → 页面回到空状态 "有什么可以帮助你的？"
  → 消息列表清空

API 验证：
  GET /api/v1/agents/general-coach/{thread_id}/state
  → session_active = false
```

### 关键选择器

| 元素 | 选择器 |
|------|--------|
| 空状态标题 | `text="有什么可以帮助你的？"` |
| 输入框 | `textarea`（coach 页面） |
| 开始/发送按钮 | `button:has-text("开始")` / `button:has-text("发送")` |
| 用户消息气泡 | `.bg-brand-500.text-white` |
| 助手消息气泡 | `.bg-surface-muted` |
| 意图标签 | `text=/意图：/` |
| 重定向面板 | `text="检测到您的问题属于"` |
| 结束对话 | `button:has-text("结束对话")` |
| 加载指示器 | `.animate-spin.text-brand-500` |
| 错误提示 | `.text-danger-500` |

---

## 边缘场景与异常测试

### E1: 网络错误处理
```
M16：
  → 分析过程中后端断开 → 显示错误提示 → 可重试

M17：
  → 提交回答时后端超时 → 可重新提交

M19：
  → WS 断开 → 消息发送失败 → 显示错误提示 → 可重试
```

### E2: 空数据
```
M16：
  → 输入空 JD → "开始分析" 按钮 disabled

M17：
  → 没有错题 → 错题本空状态 "还没有错题记录"
  → 没有 frequency > 0 的错题 → "开始强化" 按钮不显示

M18：
  → 没有面试记录 → 能力画像使用初始值
  → 诊断结果为空 → 不崩溃

M19：
  → 空输入 → 发送按钮 disabled
  → 初次打开 → 空状态页面
```

### E3: 并发与冲突
```
M16 (锁冲突)：
  → 同分支正在优化中 → 再次点击 AI 优化 → 显示 "资源已被锁定"

M19 (多会话)：
  → 先启动一个对话未关闭 → 再次开新对话 → 服务端行为（可关闭旧的或出错）
```

### E4: 超时
```
M16: 30 分钟无操作 → 锁自动释放
M17: 10 分钟无输入 → 自动结束
M19: 2 小时无活动 → session_active = false
```

---

## 回归检查清单

### M16 回归
- [ ] 点击 AI 优化 → Modal 打开
- [ ] 填写 JD → 开始分析 → loading 状态
- [ ] 分析完成 → diff 面板显示 patches
- [ ] 每项 patch 显示 op + path + value
- [ ] 点击 "应用修改" → 成功状态 + version ID
- [ ] 点击 "放弃" → Modal 关闭，内容未变
- [ ] 锁冲突时显示 423 错误
- [ ] 优化完成后锁释放
- [ ] 版本历史中出现 AI 优化记录

### M17 回归
- [ ] 选择错题 → 详情面板显示
- [ ] 点击 "开始强化" → Modal 打开
- [ ] 提交回答 → 评分反馈
- [ ] 提示等级逐步增大（small → medium → detailed）
- [ ] 3 轮答对 → "已掌握！"
- [ ] frequency 递减
- [ ] frequency → 0 时状态变为 mastered
- [ ] 中止 → "已退出" 提示
- [ ] 空回答 → 提交按钮 disabled

### M18 回归
- [ ] 面试完成 → ARQ 自动触发
- [ ] Profile 页状态指示器变化
- [ ] 6 维度分数更新
- [ ] 改进建议列表生成
- [ ] 活动流中出现记录
- [ ] 成长轨迹曲线可用

### M19 回归
- [ ] /coach 空状态页面
- [ ] 输入问题 → 流式回答
- [ ] 意图标签显示
- [ ] resume_optimize 意图 → redirect_to 面板
- [ ] 多轮对话
- [ ] 结束对话 → 清空回到空状态
- [ ] 错误处理 → 不崩溃

---

## 附录：API 验证命令

```bash
# M16: 状态查询
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/agents/resume-optimize/{thread_id}/state | jq .

# M17: 状态查询
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/agents/error-coach/{thread_id}/state | jq .

# M18: DB 手工验证
docker exec -it postgres psql -U intercraft -d intercraft -c \
  "SELECT dimension, actual, delta FROM ability_dimensions WHERE user_id='{user_id}';"
docker exec -it postgres psql -U intercraft -d intercraft -c \
  "SELECT id, type, content FROM activities WHERE user_id='{user_id}' AND type='ability.suggestion' LIMIT 5;"

# M19: 状态查询
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/agents/general-coach/{thread_id}/state | jq .
```
