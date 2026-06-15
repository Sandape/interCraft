# InterCraft Phase 1-4 优化建议

> 基于Playwright E2E测试发现的可优化项

## 一、性能优化

### 1.1 LLM调用优化 (高优)
- **问题**: DeepSeek API首次响应超过4分钟(score + question_gen)
- **建议**:
  - 评分和问题生成拆分为独立调用，流式返回中间结果
  - 评分完成后立即显示(不等问题生成)
  - 考虑使用更小的模型做评分(如DeepSeek-Lite)，大模型做问题生成
  - 添加请求超时(60s)，超时后提示用户重试

### 1.2 前端加载状态优化 (中优)
- **问题**: 用户提交答案后只看到"面试官正在评估"旋转图标，无进度感
- **建议**:
  - 添加阶段指示器: "评分中..." → "生成下一题..."
  - 显示预估等待时间
  - 超过30秒显示"仍在处理中，请耐心等待"提示

## 二、用户体验优化

### 2.1 Dashboard数据接入 (高优)
- **当前**: 6个数据源使用mockData，新用户看到虚假数据
- **建议**: 按优先级逐步接入:
  1. `abilityDimensions` → `useAbilities()` + `useDimensionsMeta()` (API已就绪)
  2. `recentActivities` → `useActivities()` (API已就绪)
  3. `upcomingTasks` → `useTasks()` (API已就绪)
  4. `interviewHistory` → `useInterviewSessions()` (API已就绪)
  5. `dashboardStats` → 从上述数据派生
  6. `growthTrajectory` → `useAbilityHistory()` (API已就绪)

### 2.2 Profile空状态 (中优)
- **问题**: 新用户无能力数据时雷达图崩溃
- **建议**:
  - 空数据时显示占位引导: "完成第一场模拟面试后生成能力画像"
  - SVG组件添加空数据保护

### 2.3 面试创建流程 (中优)
- **问题**: `/interview/new` 仅提供文本输入，未关联简历/岗位
- **建议**:
  - 添加简历分支下拉选择器
  - 添加已有岗位快捷选择
  - 预填来自Dashboard的推荐

### 2.4 全局搜索 (低优)
- **问题**: 搜索框存在但未实现
- **建议**: 实现全局搜索，支持搜索简历/面试/错题

## 三、稳定性优化

### 3.1 Lock管理 (中优)
- **问题**: 多次出现lock acquire 409 + lock WS 403
- **建议**:
  - 编辑器离开时主动释放lock
  - 服务端定时清理过期lock (>30min)
  - Lock WS在token刷新后自动重连

### 3.2 Token刷新流程 (低优)
- **问题**: 旧tab/lock WS使用过期token
- **建议**: 全局事件总线监听token刷新，通知所有WS重连

### 3.3 前端WS重连 (低优)
- **当前**: 已经实现了指数退避重连(1s-16s)
- **建议**: 添加重连次数上限提示，超过上限给出手动重试按钮

## 四、代码质量优化

### 4.1 Repository BASE路径规范 (高优 ✅ 已修复)
- **问题**: 4个repo的BASE缺少 `/api/v1/` 前缀
- **建议**: 在CI中添加检查，确保所有repo的BASE都使用完整路径

### 4.2 类型安全 (低优)
- **问题**: Dashboard.tsx中多处使用 `any` 类型(mockData导入)
- **建议**: 替换为真实API后，使用生成的OpenAPI类型

## 五、测试建议

### 5.1 E2E测试覆盖
- **建议**: 基于本次测试流程创建Playwright E2E测试套件
  - `tests/e2e/auth.spec.ts` — 注册/登录/登出
  - `tests/e2e/resume.spec.ts` — 简历CRUD
  - `tests/e2e/jobs.spec.ts` — 岗位管理
  - `tests/e2e/interview.spec.ts` — 面试流程(mock LLM)
  - `tests/e2e/dashboard.spec.ts` — Dashboard数据

### 5.2 API契约测试
- **建议**: 使用后端OpenAPI schema验证前端请求
- 运行 `npm run gen:api` 后检查类型错误

## 优先级排序

| 优先级 | 项 | 预估工时 |
|--------|-----|---------|
| P0 | LLM超时重试机制 | 2h |
| P1 | Dashboard数据接入 | 4h |
| P1 | Profile空状态修复 | 1h |
| P2 | 面试创建关联简历/岗位 | 3h |
| P2 | Lock过期清理 | 2h |
| P3 | 全局搜索实现 | 4h |
| P3 | E2E测试套件 | 8h |

---

*报告生成时间: 2026-06-14*
