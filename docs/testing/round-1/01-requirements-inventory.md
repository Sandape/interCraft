# E2E 测试需求清单（Round 1）

> 范围:`specs/019-cross-module-linking`(active feature 现状) + 关键已交付模块的回归冒烟。生成日期 2026-06-17。

## 1. 范围说明

本轮 E2E 验证以 `.specify/feature.json` 当前活跃的 `019-cross-module-linking` 为主线,覆盖其全部 5 个 User Story 与 27 个 FR;同时对已交付的核心模块做最小冒烟回归,确保新功能接入没有破坏既有契约。

### 1.1 主线:019 跨模块联动

- **数据源**:`specs/019-cross-module-linking/{spec.md, contracts/, data-model.md}`
- **DB 现状**(已 `dbq.py` 验证):
  - `jobs` 已有 5 个新列:`base_location / requirements_md / employment_type / salary_range_text / headcount`
  - `interview_sessions` 已有 `job_id` 列(可空 UUID)
  - `error_questions` 已有 `source_question_id` 列(可空 UUID,部分唯一索引)
- **实际接口实现与契约文档的偏差**:
  - `POST /error-questions/{id}/clear-source` 实现为 `POST`,**契约文档写的是 `PATCH`** — 记为 P3 文档不一致
  - `GET /error-questions` 接受 `?filter[source]=auto|manual|all`(别名 query),**契约文档写的是 `?source=...`** — 记为 P3 文档不一致
- **实现层验证**:DB 模式完整,`backend/app/modules/errors/api.py:103` 与 `backend/app/modules/jobs/api.py` 均就位

### 1.2 回归冒烟范围

为确认 019 接入没有破坏既有契约,以下已交付模块跑最小冒烟:

- Auth: register / login
- Resume: 列表 / 新建分支
- Jobs(基础): 列表 / 状态机
- Interview: 5 轮完整流(已有独立 spec)
- Error Book(基础): 列表 / 手动录入
- Topbar 工具(017): 新建简历下拉

## 2. 需求清单

### 2.1 模块:账号与会话(Auth & Sessions)

| ID | 功能点 | 优先级 | 核心逻辑 | 关联接口 | 关联表 | 高风险 |
|---|---|---|---|---|---|---|
| AUTH-01 | 邮箱密码注册 | P0 | `POST /api/v1/auth/register` 创建 user + 返回 token;前端跳 `/dashboard` | `POST /api/v1/auth/register` | `users`, `user_credentials`, `auth_sessions` | 否 |
| AUTH-02 | 邮箱密码登录 | P0 | `POST /api/v1/auth/login` 校验 + 返回 token | `POST /api/v1/auth/login` | `users` | 否 |
| AUTH-03 | 游客访问受限页 | P1 | 未登录访问 `/jobs` 重定向 `/login` | — | `auth_sessions` | 否 |
| AUTH-04 | Token 失效回退 | P1 | 401 时跳转登录页 | — | `auth_sessions` | 否 |

### 2.2 模块:求职追踪(Jobs) — 019 扩展

| ID | 功能点 | 优先级 | 核心逻辑 | 关联接口 | 关联表 | 高风险 |
|---|---|---|---|---|---|---|
| JOB-01 | 新建 Job 含 5 字段 | P0 | 创建 base_location/requirements_md/employment_type/salary_range_text/headcount;详情面板 5 字段均展示 | `POST /jobs`, `GET /jobs/{id}` | `jobs` | **是**(数据落库) |
| JOB-02 | 新建 Job 不含 5 字段(默认值) | P0 | 仅填 company/position → base_location='', employment_type='unspecified', 其余 NULL;详情面板「未填写/未指定」占位 | `POST /jobs`, `GET /jobs/{id}` | `jobs` | 是 |
| JOB-03 | Job 字段边界校验 | P0 | base_location > 50 字符 / requirements_md > 5000 / salary_range_text > 100 / headcount < 1 / employment_type 非法 → 422 | `POST /jobs` | `jobs` | 是 |
| JOB-04 | 编辑 Job 修改 5 字段 | P0 | PATCH /jobs/{id};详情面板同步更新(无需刷新) | `PATCH /jobs/{id}` | `jobs` | 是 |
| JOB-05 | Job 状态机(回归) | P0 | 014 状态机未变;applied → test → oa → hr → offer/rejected/withdrawn | `PATCH /jobs/{id}/status` | `jobs`, `status_history` | 是 |
| JOB-06 | Job 详情显示 CTA「为该岗位创建简历分支」 | P0 | 仅当 branch_id IS NULL 时显示可点;跳转 `/resume?new=true&source_job_id={jobId}` | — | `jobs` | 否 |
| JOB-07 | Job 详情显示 CTA「为该岗位开始模拟面试」 | P0 | 仅当 branch_id IS NOT NULL 时可点;branch_id NULL 时置灰 + tooltip | `POST /interview-sessions` | `jobs`, `interview_sessions` | 是 |
| JOB-08 | Job 详情显示绑定的简历分支 | P0 | branch 绑后显示分支名(可点击);未绑显示「(无)」 | — | `jobs`, `resume_branches` | 否 |

### 2.3 模块:简历中心(Resume)

| ID | 功能点 | 优先级 | 核心逻辑 | 关联接口 | 关联表 | 高风险 |
|---|---|---|---|---|---|---|
| RES-01 | Topbar「新建简历」下拉 | P0 | 含「基于岗位创建」二级入口;下拉显示当前 user 全部 job | — | `jobs` | 否 |
| RES-02 | Topbar「基于岗位创建」选 job → 跳转 | P0 | 跳 `/resume?new=true&source_job_id={jobId}`;分支编辑器预填 company/position/name | `GET /jobs/{id}` | `jobs`, `resume_branches` | 是 |
| RES-03 | 分支编辑器 `requirements_md` 折叠提示 | P1 | 当 source_job_id 的 requirements_md 长度 ≥50 → 顶部折叠卡「本岗位的招聘需求(点击展开复制)」 | `GET /jobs/{id}` | `jobs` | 否 |
| RES-04 | 保存分支后回填 jobs.branch_id | P0 | `POST /resumes/branches` → `PATCH /jobs/{jobId}` 设 branch_id;失败时 Toast 提示 | `POST /resumes/branches`, `PATCH /jobs/{id}` | `resume_branches`, `jobs`, `outbox` | **是** |
| RES-05 | 列表显示简历分支 | P1 | `/resume` 列表显示用户全部分支;带搜索 | `GET /resumes/branches` | `resume_branches` | 否 |

### 2.4 模块:模拟面试(Interviews) — 019 扩展

| ID | 功能点 | 优先级 | 核心逻辑 | 关联接口 | 关联表 | 高风险 |
|---|---|---|---|---|---|---|
| INT-01 | 从 Job 创建 interview session | P0 | `POST /interview-sessions` 同时带 job_id 与 branch_id;服务端校验同 user;200 返回 session.id | `POST /interview-sessions` | `interview_sessions` | 是 |
| INT-02 | job_id 不存在或属于其他 user | P0 | 服务端 422;前端 Toast | `POST /interview-sessions` | `interview_sessions` | 是 |
| INT-03 | job_id 与 branch_id 不匹配 | P1 | 422;前端 Toast | `POST /interview-sessions` | `interview_sessions` | 是 |
| INT-04 | InterviewLive Intake 预填 | P0 | `?job_id` 时,Intake 页 3 字段只读预填 + 1 卡片展示 requirements_md | `GET /jobs/{id}` | `jobs`, `interview_sessions` | 否 |
| INT-05 | 5 轮对话流(回归) | P0 | WS 流式;每题可提交;最终到 report 页 | `WS`, `POST /interview-sessions/{id}/answers` | `interview_questions`, `ai_messages` | 是 |
| INT-06 | score 节点自动沉淀错题(本轮用 mock) | P0 | 每次 score < 6 → `error_questions` UPSERT(由部分唯一约束保证幂等) | `POST /interview-sessions/{id}/answers` | `error_questions` | **是**(数据落库) |
| INT-07 | 同一题重答不重复创建错题 | P0 | 同 source_question_id 二次触发 → UPSERT(更新 score) | 同上 | `error_questions` | **是**(幂等) |
| INT-08 | 不带 job_id 向后兼容 | P0 | 既有 Phase 4 客户端调用不带 job_id → session.job_id = NULL,行为不变 | `POST /interview-sessions` | `interview_sessions` | 是 |

### 2.5 模块:错题本(Error Book) — 019 扩展

| ID | 功能点 | 优先级 | 核心逻辑 | 关联接口 | 关联表 | 高风险 |
|---|---|---|---|---|---|---|
| ERR-01 | 错题列表(回归) | P0 | `/error-book` 列表显示当前 user 全部错题;带筛选 | `GET /error-questions` | `error_questions` | 是 |
| ERR-02 | 列表 source 筛选 auto | P0 | `?filter[source]=auto` → 仅 source_session_id IS NOT NULL | `GET /error-questions?filter[source]=auto` | `error_questions` | 是 |
| ERR-03 | 列表 source 筛选 manual | P0 | `?filter[source]=manual` → 仅 source_session_id IS NULL | `GET /error-questions?filter[source]=manual` | `error_questions` | 是 |
| ERR-04 | 错题详情显示「来自 {company} · {position} · {时间}」 | P0 | source_session_id 非空时显示静态文案 | `GET /error-questions/{id}` | `error_questions`, `interview_sessions` | 否 |
| ERR-05 | 错题详情「移除自动来源」按钮 | P0 | 调用 `POST /error-questions/{id}/clear-source`(实现为 POST,文档写 PATCH);清空 source_session_id / source_question_id | `POST /error-questions/{id}/clear-source` | `error_questions` | **是** |
| ERR-06 | 移除自动来源后文案消失 | P0 | 「来自 XX」静态文案不再显示;默认列表仍可见(已转为手动) | 同上 | `error_questions` | 是 |
| ERR-07 | 错题详情「删除」按钮(回归 016) | P0 | 复用 016 确认弹窗;`DELETE /error-questions/{id}` 软删;列表移除 | `DELETE /error-questions/{id}` | `error_questions` | **是** |
| ERR-08 | 手动录入错题(回归 016) | P0 | `POST /error-questions` source_session_id = NULL | `POST /error-questions` | `error_questions` | 是 |

### 2.6 模块:Topbar 与导航(017/010)

| ID | 功能点 | 优先级 | 核心逻辑 | 关联接口 | 关联表 | 高风险 |
|---|---|---|---|---|---|---|
| TOP-01 | Topbar 「新建简历」下拉 | P0 | 含「空白创建」「基于岗位创建」 | — | `jobs` | 否 |
| TOP-02 | Topbar 全局搜索(011) | P1 | Topbar 搜索框;输入触发 `/search` 页或下拉 | `GET /search` | 跨表 | 否 |
| TOP-03 | Topbar 帮助 / 通知 / 用户菜单 | P1 | 帮助跳转 `/help`;通知面板 + 设置;用户菜单 | `GET /users/me` | `users` | 否 |

### 2.7 模块:个人画像(006)

| ID | 功能点 | 优先级 | 核心逻辑 | 关联接口 | 关联表 | 高风险 |
|---|---|---|---|---|---|---|
| ABL-01 | 面试结束后能力维度更新 | P1 | `interview_sessions.ended_at` 后 `ability_dimensions.updated_at` 在其之后;`GET /profile` 可见 | `GET /profile` | `ability_dimensions` | 否 |
| ABL-02 | 个人画像详情页 | P2 | `/profile/{dim}` 详情;时间衰减加权聚合 | `GET /profile/{dim}` | `ability_dimensions`, `ability_dimensions_history` | 否 |

## 3. 高风险业务节点清单

| # | 节点 | 风险类型 | 涉及接口 | 必测维度 |
|---|---|---|---|---|
| HR-01 | 创建/编辑 Job 写入 5 字段 | 数据正确性 / Pydantic 校验 | `POST /jobs`, `PATCH /jobs/{id}` | 反向(超长/非法枚举/负数 headcount)、边界(空字符) |
| HR-02 | 从 Job 创建 interview session | 数据一致性 / 权限校验 | `POST /interview-sessions` | 权限(其他 user 的 job_id)、数据匹配(job_id/branch_id) |
| HR-03 | score 节点自动沉淀错题 | 数据正确性 / 幂等性 | `POST /interview-sessions/{id}/answers` | 重复触发(同 source_question_id)、分数边界(=6 / <6) |
| HR-04 | 移除自动来源 | 状态变更 / 软删除语义 | `POST /error-questions/{id}/clear-source` | 二次调用 400、清源后列表筛选 |
| HR-05 | 错题删除(软删) | 数据一致性 | `DELETE /error-questions/{id}` | 默认列表与筛选视图都不再展示;`deleted_at` 置位 |
| HR-06 | 保存分支回填 jobs.branch_id | 跨表一致性 | `POST /resumes/branches` + `PATCH /jobs/{id}` | 失败回退(网络中断 → outbox) |
| HR-07 | Job 状态机 | 状态正确性 | `PATCH /jobs/{id}/status` | 非法跃迁 422 / 时间线记录 |
| HR-08 | 权限隔离 | 越权访问 | 上述所有写接口 | user A 用 user B 的 job_id / error_id 全部应 404 |

## 4. 关联数据库表清单(本轮覆盖)

| 表 | 用途 | 关键列 | E2E 主要断言点 |
|---|---|---|---|
| `users` | 用户主表 | `id, email, display_name` | 唯一性约束 |
| `user_credentials` | 凭证 | `user_id, password_hash` | (不直接测) |
| `auth_sessions` | 登录会话 | `user_id, token, expires_at` | (不直接测) |
| `jobs` | 岗位 | 5 新字段 + 既有 014 字段 | 5 字段落库、长度校验、状态机 |
| `resume_branches` | 简历分支 | `id, user_id, name, company, position, parent_id` | 预填后保存 |
| `interview_sessions` | 面试 | 既有 + `job_id` | `job_id` 落库、`branch_id` 校验 |
| `interview_questions` | 面试题 | `id, session_id, score, dimension, text` | 分数落库 |
| `ai_messages` | 面试对话 | `question_id, role, body` | (辅助) |
| `error_questions` | 错题 | 既有 + `source_question_id` | 自动沉淀、幂等、clear-source、soft-delete |
| `ability_dimensions` | 能力维度 | `user_id, dim, score, updated_at` | 面试后 updated_at 刷新 |
| `outbox` | 离线操作 | `payload, status` | (回归) |

## 5. 不在本轮范围(显式排除)

- 002 简历编辑器增强 / 004 Phase 5 子图 / 005 Phase 6 全局能力:`planned`,无前端实现
- 邮件解析 / Offer 谈判追踪 / 日历集成:014 标记 out-of-scope
- 后端单元 / 集成 / 契约测试(已有 `backend/tests/**`)
- 前端 vitest 单元测试(已有 `src/**/*.test.tsx`)
- 性能 / 负载 / 渗透测试
- 移动端响应式

## 6. 测试环境

- 后端:`http://127.0.0.1:8000/api/v1/`(FastAPI,已运行)
- 前端:`http://127.0.0.1:5173/`(Vite dev,已运行)
- 数据库:PostgreSQL 在线(生产 dev),`dbq.py` 可查
- Redis:本地 6379
- LLM:DeepSeek V4 Pro(配置在 `backend/.env`)
- 浏览器:Chromium Desktop(Playwright MCP 默认)
