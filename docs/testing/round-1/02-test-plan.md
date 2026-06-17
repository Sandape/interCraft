# E2E 测试方案(Round 1)

> 范围:`019-cross-module-linking` 完整覆盖 + 已交付模块冒烟回归。生成日期 2026-06-17。

## 1. 方案总览

| 项 | 内容 |
|---|---|
| 测试目标 | 验证 019 跨模块联动链路(Job→Resume→Interview→Error Book→Ability),并确认既有 014/016/006/Phase 4 无回归 |
| 测试方法 | Playwright E2E + 后端 HTTP 断言 + PostgreSQL 断言(经 `dbq.py`) |
| 浏览器 | Chromium Desktop(单项目) |
| 后端 | `http://127.0.0.1:8000/api/v1/`(已运行) |
| 前端 | `http://127.0.0.1:5173/`(已运行) |
| 数据库 | PostgreSQL(已就位) |
| 触发方式 | Playwright MCP(`mcp__playwright__*` 工具集) |

## 2. 规范遵循

### 2.1 元素定位

- 优先 `data-testid`(已在 UI 暴露:`job-create-base-location`, `job-detail-resume-cta`, `job-detail-interview-cta`, `intake-prefill-card`, `setup-position-input`, `setup-company-input`, `error-detail`, `topbar-new-resume-from-job` 等)
- 次选精确文本定位(`getByRole('button', { name: '添加错题' })`)
- **禁用**模糊 class / id

### 2.2 智能等待

- `await expect(locator).toBeVisible({ timeout: 10_000 })`
- `await page.waitForLoadState('networkidle')`
- `await page.waitForResponse(r => r.url().includes('/jobs'))`
- **禁用**固定 `sleep`

### 2.3 双重断言

每个写操作步骤后:

1. **UI 断言**:前端可见元素
2. **接口断言**:对应 API 响应码 / body

### 2.4 数据库断言

涉及数据变更时,使用 `dbq.py` 验证:

```bash
uv run python -m scripts.dbq sql "SELECT id, base_location, employment_type FROM jobs WHERE id = '<job_id>'"
```

包装函数:`dbAssert(sql, expectMatch)` 在脚本内通过 `Bash` 工具调用 `dbq.py`,根据返回判断。

### 2.5 用例隔离

- 每条用例 `test.describe.configure({ mode: 'serial' })` 串行执行
- 注册独立的 `e2e-019-{timestamp}@intercraft-e2e.com` 用户
- `beforeEach`:创建用户 + 注入 token 到 `sessionStorage`
- `afterEach`:调用 `DELETE` 端点或保留数据(便于事后复盘)

### 2.6 失败处理

- 自动截图 `tests/e2e/screenshots/{spec}-{test}-{step}.png`
- 失败视频 `tests/e2e/videos/{spec}-{test}.webm`
- 日志 `tests/e2e/logs/{spec}.log` 记录请求/响应/DB 断言结果

## 3. 用例设计

### 3.1 冒烟测试集(`smoke.spec.ts`,5 条)

| # | ID | 描述 | 维度 |
|---|---|---|---|
| S1 | SMOKE-01 | 注册 → 创建带 5 字段的 job → 详情面板显示 5 字段 | 正向主流程 |
| S2 | SMOKE-02 | 不带 5 字段创建 job → 默认值占位 | 边界(空值) |
| S3 | SMOKE-03 | 从 Job 详情创建简历分支 → branch_id 自动回填 | 正向主流程 + 数据一致性 |
| S4 | SMOKE-04 | 从 Job 详情开模拟面试(branch 已绑)→ interview.job_id 入库 | 正向主流程 + 数据一致性 |
| S5 | SMOKE-05 | 错题列表 source=auto 筛选 + clear-source 按钮可用 | 正向主流程 |

### 3.2 全量测试集

#### A. Job 5 字段(`full-jobs-fields.spec.ts`,8 条)

| # | ID | 描述 | 维度 |
|---|---|---|---|
| A1 | JOB-UI-01 | 5 字段 UI 渲染(详情面板) | 正向主流程 |
| A2 | JOB-UI-02 | 字段超长 → UI 阻止(maxLength) | 反向异常 |
| A3 | JOB-API-01 | 字段超长 → 422 | 反向异常 |
| A4 | JOB-API-02 | 非法枚举 employment_type → 422 | 反向异常 |
| A5 | JOB-API-03 | headcount < 1 → 422 | 反向异常 |
| A6 | JOB-API-04 | 5 字段全部边界值(50/5000/100) | 边界 |
| A7 | JOB-UI-03 | 编辑 job 改字段 → 详情面板同步更新 | 数据一致性 |
| A8 | JOB-RLS-01 | 其他 user 的 job_id → GET 404 | 权限 |

#### B. Job → Resume 联动(`full-resume-binding.spec.ts`,6 条)

| # | ID | 描述 | 维度 |
|---|---|---|---|
| B1 | RES-FLOW-01 | Job 详情 CTA → 跳转 → 编辑器预填 | 正向主流程 |
| B2 | RES-FLOW-02 | 保存分支 → jobs.branch_id 回填 | 数据一致性 |
| B3 | RES-FLOW-03 | Topbar「基于岗位创建」下拉 | 入口完整性 |
| B4 | RES-UI-01 | requirements_md 折叠卡片(≥50 字符) | UI |
| B5 | RES-API-01 | 保存分支后 PATCH 失败 → Toast 提示 | 交互异常 |
| B6 | RES-PERM-01 | 跨 user 访问 source_job_id 不影响数据 | 权限 |

#### C. Job → Interview 联动(`full-interview-job.spec.ts`,7 条)

| # | ID | 描述 | 维度 |
|---|---|---|---|
| C1 | INT-FLOW-01 | branch 已绑 → 点击 CTA → 跳 InterviewLive | 正向主流程 |
| C2 | INT-FLOW-02 | Intake 预填 position / company / base_location / requirements | UI |
| C3 | INT-API-01 | job_id 不存在 → 422 | 反向异常 |
| C4 | INT-API-02 | job_id 属于其他 user → 422 | 权限 |
| C5 | INT-API-03 | job_id 与 branch_id 不匹配 → 422 | 反向异常 |
| C6 | INT-UI-01 | branch 未绑 → CTA 置灰 + tooltip | 反向异常 |
| C7 | INT-COMPAT-01 | 不带 job_id 创建 → 向后兼容 | 兼容性 |

#### D. 错题自动沉淀 + clear-source(`full-error-source.spec.ts`,7 条)

| # | ID | 描述 | 维度 |
|---|---|---|---|
| D1 | ERR-FILTER-01 | `?filter[source]=auto` 仅返回有 source 的 | 正向 |
| D2 | ERR-FILTER-02 | `?filter[source]=manual` 仅返回无 source 的 | 正向 |
| D3 | ERR-CLEAR-01 | clear-source → source_session_id / source_question_id 置 NULL | 数据一致性 |
| D4 | ERR-CLEAR-02 | 二次 clear-source → 400 source_already_cleared | 反向异常 |
| D5 | ERR-CLEAR-03 | 清源后「来自 XX」文案消失 | UI |
| D6 | ERR-AUTO-01 | score < 6 → 自动创建 error_question(用 API 模拟) | 正向 |
| D7 | ERR-DEL-01 | DELETE 软删 → 默认列表不再显示 | 软删语义 |

#### E. 权限与跨用户隔离(`full-permissions.spec.ts`,4 条)

| # | ID | 描述 | 维度 |
|---|---|---|---|
| E1 | PERM-01 | user A 访问 user B 的 job → 404 | 权限 |
| E2 | PERM-02 | user A 创建带 user B job_id 的 session → 422 | 权限 |
| E3 | PERM-03 | user A clear user B 的 error_source → 404 | 权限 |
| E4 | PERM-04 | 游客访问 `/jobs` → 重定向 `/login` | 权限 |

#### F. 边界与异常(`full-edge.spec.ts`,5 条)

| # | ID | 描述 | 维度 |
|---|---|---|---|
| F1 | EDGE-01 | base_location 51 字符 → 422 | 边界 |
| F2 | EDGE-02 | requirements_md 5001 字符 → 422 | 边界 |
| F3 | EDGE-03 | salary_range_text 101 字符 → 422 | 边界 |
| F4 | EDGE-04 | headcount = 0 / -1 / 字符串 → 422 | 边界 |
| F5 | EDGE-05 | 同一题重答 → 不重复创建(同 source_question_id) | 幂等 |

#### G. 5 步联动冒烟(`full-cross-module-e2e.spec.ts`,1 条)

| # | ID | 描述 | 维度 |
|---|---|---|---|
| G1 | CHAIN-01 | 新建 user → 建 job(5 字段) → 创建分支 → 开面试(API) → 注入 error(API) → /error-book 看见 + clear-source | 端到端 |

**总计**:冒烟 5 条 + 全量 38 条 = 43 条用例

## 4. 用例 → 维度覆盖矩阵

| 维度 | 用例数 | 覆盖 |
|---|---|---|
| 正向主流程 | 11 | S1/S3/S4/S5/A1/A7/B1/B2/B3/C1/C2/D1/D2/D3/D5/D6/D7/G1 |
| 反向异常 | 12 | S2/A2/A3/A4/A5/C3/C5/C6/D4/F1/F2/F3/F4 |
| 边界 | 5 | A6/F1/F2/F3/F4 |
| 交互异常 | 4 | B5/C6/D2(响应)/G1 网络 |
| 权限 | 6 | A8/B6/C4/E1/E2/E3/E4 |
| 数据一致性 | 8 | S3/S4/A7/B2/C1/D3/D6/F5 |

**高风险节点覆盖**:HR-01(创建/编辑 Job)100%,HR-02(创建 session)100%,HR-03(自动沉淀)100%,HR-04(clear-source)100%,HR-05(软删)100%,HR-06(branch_id 回填)100%,HR-07(状态机)由既有 015 spec 覆盖,HR-08(权限)100%。

## 5. 脚本组织

```
tests/e2e/round-1/
├── fixtures/
│   └── auth.ts             # 注册 + 注入 token
├── helpers/
│   ├── db.ts               # 包装 dbq.py
│   └── api.ts              # HTTP helpers
├── smoke.spec.ts            # 5 条冒烟
├── full-jobs-fields.spec.ts
├── full-resume-binding.spec.ts
├── full-interview-job.spec.ts
├── full-error-source.spec.ts
├── full-permissions.spec.ts
├── full-edge.spec.ts
└── full-cross-module-e2e.spec.ts
```

## 6. 执行顺序

```
1. smoke.spec.ts          → 确认环境就绪
2. full-jobs-fields.spec.ts
3. full-resume-binding.spec.ts
4. full-interview-job.spec.ts
5. full-error-source.spec.ts
6. full-permissions.spec.ts
7. full-edge.spec.ts
8. full-cross-module-e2e.spec.ts
```

任一文件失败,记录缺陷,继续执行其余(便于全面记录)。

## 7. 报告产出

- `03-defect-report.md` — 缺陷清单
- `04-summary-report.md` — 总结报告
- `logs/execution.log` — 完整执行日志
- `screenshots/` — 关键步骤截图
- `videos/` — 失败用例录屏
