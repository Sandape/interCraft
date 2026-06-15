# Phase 2 Release Notes — P1 业务实体上线

**Date**: 2026-06-13
**Status**: Complete (T001-T111)
**Baseline**: Phase 1 (P0 auth + resumes)

## 演示场景 (Demo Scenarios)

### 1. 能力画像 (US5)
1. 注册新用户 → `/profile` 自动显示 6 维度雷达图（actual=0, ideal=10）
2. 手动 PATCH 某维度 sub_scores → 刷新持久化
3. 禁用某维度 → 雷达图不再展示该维度
4. 历史图表按月份聚合展示

### 2. 错题本 (US6)
1. `/error-book` 创建错题（可选关联维度）→ 列表即时出现
2. 状态推进：fresh → practicing → mastered
3. 非法状态转换返回 409（如 fresh → mastered）
4. Reset mastered → fresh（frequency 重置为 3）
5. 列表按维度/状态/频次筛选 + 文本搜索

### 3. 求职追踪 + 任务 + 活动流 (US8)
1. `/jobs` 创建职位 → 自动创建「准备 X 公司面试」任务 + 写 activity
2. 状态推进：applied → screening → interview → offer
3. 推进到 rejected → 任务归档
4. 多次推进不创建重复任务（UNIQUE 约束）
5. 漏斗统计 `/jobs/stats` 实时更新
6. 活动流游标分页 forward-only

### 4. 设置 (US11)
1. `/settings` → 「资料」tab 读写 4 字段（display_name / title / years_of_experience / target_role）
2. Email 字段禁用（不可编辑）
3. 其他 tab（设备/订阅/安全）显示「Phase 6 上线」占位

### 5. 面试历史只读骨架 (US4 partial)
1. `GET /interview-sessions` 返回 200 + 数据
2. `POST /interview-sessions` 返回 405
3. `POST /internal/interview-sessions` 返回 501

## 与 Phase 1 差异

| 方面 | Phase 1 | Phase 2 |
|------|---------|---------|
| 数据表 | 6 张 | 13 张（+7） |
| API 端点 | 23 | 30+（+7 模块） |
| 前端页面 | 5 | 8（+ErrorBook, +Jobs, +InterviewList） |
| 后端测试 | 23 单元 | 123 passed, 22 skipped |
| 前端测试 | 4 vitest | 39 vitest |
| E2E 测试 | 2 | 10（+8 Phase 2） |
| 无后端 mock | 所有后端集成测试 | 同 Phase 1 |

## 风险回顾

- **T008b (Postgres)**: 本地测试使用在线 Postgres，22 个需要真实数据库的测试 skipped
- **RLS 隔离**: 7 张新表全部启用 RLS，跨用户访问返回 404（已验证）
- **MSW Body is unusable**: 已知 MSW 3.x 内部 stderr 警告，不影响测试结果
- **Windows asyncio**: event_loop fixture 已改为 function scope

## 验收清单 (Acceptance Checklist)

- [x] 后端 123 tests passed, 22 skipped
- [x] 前端 39 tests passed (9 test files)
- [x] TypeScript 编译零错误
- [x] Vite 生产构建成功（1708 modules）
- [x] VITE_USE_MOCK=true 回归通过
- [x] CLI 验证脚本 3/3 通过
- [x] Phase 1 功能无回归
- [x] Profile / ErrorBook / Jobs / Settings 资料 tab 在真实 API 下可用
- [x] RLS 7 表跨用户隔离验证通过
