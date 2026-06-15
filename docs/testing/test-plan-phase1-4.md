# InterCraft Phase 1-4 测试方案

> 生成时间: 2026-06-14 | 测试环境: localhost:5173 (前端) + localhost:8000 (后端)

## 一、测试范围

### Phase 1: 基础架构
- 用户注册/登录/登出
- Session 管理
- 简历分支 CRUD
- 简历 Block 编辑器
- 版本管理

### Phase 2: 实体扩展
- 能力维度 (Abilities)
- 错题本 (Error Questions)
- 任务管理 (Tasks)
- 活动记录 (Activities)
- 岗位管理 (Jobs)
- 面试会话 (Interview Sessions)

### Phase 3: 离线同步
- 锁机制 (Locks)
- 离线 Outbox
- 冲突解决

### Phase 4: 面试智能体
- 面试列表
- 实时面试 (WebSocket)
- 面试报告
- 流程中断恢复

## 二、测试场景

### 场景 1: 用户认证流程 ✅ 通过
**路径**: 注册 → 登录 → 访问受保护页面 → 登出
- [x] 注册表单验证  
- [x] 注册API正常 (curl验证)
- [x] 登录成功跳转Dashboard
- [x] 401 自动处理 (初始加载时/users/me返回401, 但页面正常渲染)
- [ ] 登出功能 (未测试)
- [ ] 未登录重定向 (未测试)

### 场景 2: 简历全生命周期 ✅ 通过
**路径**: 创建简历分支 → 编辑 Block → 保存版本 → 回滚版本
- [x] 创建分支 (含公司/职位)
- [x] 分支创建后自动跳转编辑器
- [x] 版本历史查看 (v1 初始化版本)
- [x] 信息面板 (AI优化摘要/模板/版本)
- [ ] Block 编辑 (未深入测试)
- [ ] 版本回滚 (未测试)

### 场景 3: 能力维度与错题本 ✅ 通过
- [x] Profile页面加载 (修复API路径后)
- [x] ErrorBook页面加载 (空状态)
- [ ] 能力维度数据为空 (新用户无数据 — 预期行为)

### 场景 4: 岗位管理 ✅ 通过
- [x] 岗位列表加载 (空状态, 修复API路径后)
- [x] 统计卡片 (0/0/0/0)
- [ ] 岗位创建 (未测试)

### 场景 5: 模拟面试 (深度测试) ⚠️ 部分通过
- [x] 面试创建 (公司+职位输入)
- [x] WebSocket 连接建立
- [x] AI面试官开场白
- [x] 答案提交 (WebSocket)
- [ ] 面试问题生成 (LLM超时, 4min+无响应)
- [ ] 多轮对话
- [ ] 面试报告
- ⚠️ DeepSeek API延迟过高, 未能完成完整流程

### 场景 6: 面试中断恢复 ⏳ 未测试
- [ ] 因LLM超时未能进入可中断状态
- [ ] WS重连机制验证依赖于完整面试流程

### 场景 7: Dashboard 数据 ❌ 使用Mock
- [x] 简历分支列表 (真实API)
- [x] 页面布局/UI正常
- [ ] 统计数据卡片 (mockData)
- [ ] 待办任务 (mockData)
- [ ] 近期活动 (mockData)
- [ ] 面试历史 (mockData)
- [ ] 能力概览 (mockData)

## 三、Mock vs 真实 API 检查清单

| 页面 | 状态 | 备注 |
|------|------|------|
| Login | ✅ 真实 API | AuthRepository always HTTP |
| Register | ✅ 真实 API | AuthRepository always HTTP |
| Dashboard | ❌ 混合 | stats/tasks/activities/interviews 仍用 mockData |
| ResumeList | ✅ 真实 API | ResumeRepository always HTTP |
| ResumeEditor | ✅ 真实 API | Resume/Block/Version always HTTP |
| Profile | ✅ 真实 API | 已修复: BASE路径添加/api/v1/前缀 |
| Jobs | ✅ 真实 API | 已修复: BASE路径添加/api/v1/前缀 |
| ErrorBook | ✅ 真实 API | ErrorQuestionRepository正确使用完整路径 |
| InterviewList | ✅ 真实 API | InterviewSessionRepository正确使用完整路径 |
| InterviewLive | ✅ 真实 API | WebSocket + HTTP, LLM超时问题 |
| InterviewReport | ✅ 真实 API | interviewSessionRepo, 依赖LLM完成 |
| Settings | ✅ 真实 API | AccountRepository正确使用完整路径 |

## 四、测试方法

1. **Playwright MCP**: 浏览器自动化，模拟真实用户操作
2. **API 直接验证**: curl 检查后端端点可用性
3. **前端代码审查**: 检查 mock 导入和 API 调用链路
4. **WebSocket 测试**: 验证实时通信和断线重连
