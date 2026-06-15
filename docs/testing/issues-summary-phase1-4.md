# InterCraft Phase 1-4 问题汇总报告

> 测试时间: 2026-06-14 | 测试范围: 12个页面 + 后端API + WebSocket

## 已修复的问题 (10项)

| # | 严重度 | 问题 | 文件 | 修复方式 |
|---|--------|------|------|----------|
| 1 | 🔴 Critical | AbilityRepository BASE路径缺少`/api/v1/` | `src/repositories/AbilityRepository.ts:38` | 添加 `/api/v1/` 前缀 |
| 2 | 🔴 Critical | ActivityRepository BASE路径缺少`/api/v1/` | `src/repositories/ActivityRepository.ts:19` | 添加 `/api/v1/` 前缀 |
| 3 | 🔴 Critical | JobRepository BASE路径缺少`/api/v1/` | `src/repositories/JobRepository.ts:29` | 添加 `/api/v1/` 前缀 |
| 4 | 🔴 Critical | TaskRepository BASE路径缺少`/api/v1/` | `src/repositories/TaskRepository.ts:16` | 添加 `/api/v1/` 前缀 |
| 5 | 🔴 Critical | Windows Psycopg ProactorEventLoop错误 | `backend/app/__init__.py` | 强制设置SelectorEventLoop |
| 6 | 🟡 Medium | Dashboard使用mock数据(6个数据源) | `src/pages/Dashboard.tsx` | 真实hooks + 空状态 |
| 7 | 🔴 Critical | LangGraph checkpointer连接localhost:5432 | `backend/app/agents/checkpointer.py:32` | 使用 get_settings().database_url |
| 8 | 🟡 Medium | Profile空数据SVG渲染错误 + NaN统计 | `src/pages/Profile.tsx` | 空数据守卫 + Number() 强制转换 |
| 9 | 🟠 Low | Lock WebSocket 403 token过期 | `src/lib/lock/LockClient.ts` | Token getter 函数代替静态字符串 |
| 10 | 🔴 Critical | DeepSeek LLM API调用全部失败 | `.env` / `llm_client.py` / `config.py` | 修复base_url + model + thinking模式 |

## 已记录未修复问题 (3项)

| # | 严重度 | 问题 | 位置 | 状态 |
|---|--------|------|------|------|
| 11 | 🟡 Medium | 面试报告未持久化到DB | `backend/app/api/v1/ws/interview.py` | 待修复 |
| 12 | 🟡 Medium | 面试Session状态未更新(completed) | WS handler绕过service层 | 与#11关联 |
| 13 | 🟡 Medium | 面试中断恢复缺少前端入口 | InterviewList无"继续"按钮 | 待实现 |

## 各页面API连接状态

```
✅ Login           → 真实API
✅ Register        → 真实API  
✅ Dashboard       → 真实API (6个数据源)
✅ ResumeList      → 真实API
✅ ResumeEditor    → 真实API
✅ Jobs            → 真实API
✅ ErrorBook       → 真实API
✅ InterviewList   → 真实API (会话列表持久化正确)
⚠️ InterviewLive   → 真实API (WebSocket流程完整, LLM fallback)
⚠️ InterviewReport → 真实API (页面正常, 报告数据未持久化)
✅ Profile         → 真实API (SVG + NaN 已修复)
✅ Settings        → 真实API
```

## 测试中发现的额外问题

### E1: 新用户Dashboard体验 ✅ 已修复
- Dashboard 已接入真实API，新用户显示全空状态/引导文案

### E2: 面试创建页面缺少简历/岗位选择
- `/interview/new` 仅有公司和职位输入
- 未关联已存在的简历分支和岗位

### E3: ResumeEditor锁机制
- 进入编辑器时锁acquire返回409 (可能被旧session持有) — 这是正确行为，已由其他用户持有
- Lock WS 403 token过期重连问题已修复，长时间编辑不会因token过期断开

### E4: 前端全局搜索
- 顶部搜索框存在但未实现功能
- 输入无反应

## 后端API完整性检查

### 全部可访问的端点 (已测试)
```
✅ GET  /healthz
✅ POST /api/v1/auth/register
✅ POST /api/v1/auth/login
✅ GET  /api/v1/users/me
✅ GET  /api/v1/resume-branches
✅ POST /api/v1/resume-branches
✅ GET  /api/v1/resume-branches/{id}
✅ GET  /api/v1/ability-dimensions         (修复后)
✅ GET  /api/v1/jobs                        (修复后)
✅ GET  /api/v1/jobs/stats                  (修复后)
✅ GET  /api/v1/error-questions
✅ GET  /api/v1/interview-sessions
✅ POST /api/v1/interview-sessions
✅ WS   /api/v1/ws/interview
```

### 未直接测试但应存在的端点
```
- PATCH /api/v1/resume-branches/{id}
- DELETE /api/v1/resume-branches/{id}
- POST /api/v1/resume-branches/{id}/versions
- POST /api/v1/resume-branches/{id}/refresh-from-parent
- POST /api/v1/locks/acquire
- DELETE /api/v1/locks/{id}
- PATCH /api/v1/users/me
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET  /api/v1/activities
- GET  /api/v1/tasks
```

---

*报告生成时间: 2026-06-14*
