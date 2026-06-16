# Quickstart: Cross-Module Linking 验证冒烟指南

**Feature**: 019-cross-module-linking | **Date**: 2026-06-17

> 本文档是 019 的端到端验证指南,从空数据库走到 5 步联动链路全部命中。**不包含**完整实现代码、模型/服务/控制器主体、迁移脚本、完整测试套件——这些在 `tasks.md` 与 IMPLEMENT 阶段。

## 0. 前置条件

- [x] Phase 1 基础设施就位(PostgreSQL / Redis / RLS / alembic)
- [x] 014 / 016 / 006 / Phase 4 既有代码已部署
- [x] `backend/.env` 配置 DeepSeek API key
- [x] 本地 Redis 6379 在跑
- [x] `dbq.py` 可用(`backend/scripts/dbq.py`)

## 1. 环境初始化

```bash
# 1.1 拉分支
git fetch origin
git checkout 019-cross-module-linking

# 1.2 安装依赖(沿用 Phase 1)
cd backend && uv sync
cd ../frontend && npm ci

# 1.3 跑迁移(3 个新 alembic)
cd backend && bash scripts/db_migrate.sh
# 期望输出:Applying 019_job_fields ... OK
#         Applying 019_interview_job_id ... OK
#         Applying 019_error_source_question_id ... OK

# 1.4 启动后端
uv run uvicorn app.main:app --reload --port 8000 &
# 启动前端
cd ../frontend && npm run dev &
```

## 2. 冒烟 1:Job 5 字段扩展(US1)

### 2.1 后端契约

```bash
# 2.1.1 创建 job 只填必填(向后兼容)
TOKEN=$(curl -X POST $BASE/auth/login -d '{"email":"user@x.com","password":"x"}' | jq -r .access_token)

curl -X POST $BASE/jobs -H "Authorization: Bearer $TOKEN" \
  -d '{"company":"字节","position":"前端"}'
# 期望:200,base_location="",employment_type="unspecified",其他 NULL

# 2.1.2 创建 job 带 5 字段
curl -X POST $BASE/jobs -H "Authorization: Bearer $TOKEN" \
  -d '{
    "company":"字节","position":"前端",
    "base_location":"北京",
    "requirements_md":"## 要求\n- 3年 React 经验\n- TypeScript",
    "employment_type":"experienced",
    "salary_range_text":"30-50K · 16薪",
    "headcount":5
  }'
# 期望:200,5 字段全部入库

# 2.1.3 校验失败
curl -X POST $BASE/jobs -d '{"company":"x","position":"y","base_location":"'$(printf 'a%.0s' {1..51})'"}'
# 期望:422
```

### 2.2 前端 UI

```bash
# 2.2.1 打开 http://localhost:5173/jobs
# 期望:看到刚创建的 job,base_location / 招聘需求 / 岗位类型 / 薪资范围 / 招聘人数 都显示

# 2.2.2 点击该 job 行,详情抽屉打开
# 期望:基本信息区显示 5 字段 + 两个 CTA「为该岗位创建简历分支」「为该岗位开始模拟面试」(后者置灰)
```

### 2.3 单测 + Playwright

```bash
# 后端
cd backend && pytest tests/unit/test_jobs_extended_fields.py -v
# 期望:5 passed

# 前端
cd frontend && npm run test -- JobsDetailPanel
# 期望:3 passed(5 字段渲染 / CTA 可见性 / 默认占位)
```

## 3. 冒烟 2:Job → Resume 双向入口(US2)

### 3.1 后端契约

```bash
# 3.1.1 创建分支
BRANCH_ID=$(curl -X POST $BASE/resumes/branches -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"字节 · 前端","company":"字节","position":"前端"}' | jq -r .branch.id)

# 3.1.2 绑定到 job
curl -X PATCH $BASE/jobs/<job_id> -H "Authorization: Bearer $TOKEN" \
  -d "{\"branch_id\":\"$BRANCH_ID\"}"
# 期望:200,jobs.branch_id 更新
```

### 3.2 前端 UI

```bash
# 3.2.1 在 Job 详情面板点「为该岗位创建简历分支」
# 期望:跳转到 /resume/<newBranchId>?source_job_id=<jobId>
#       分支编辑器中 name = "字节 · 前端"(预填),可编辑
#       requirements_md 字段显示折叠卡片"本岗位的招聘需求(点击展开复制)"

# 3.2.2 编辑分支(改名 / 加内容),点保存
# 期望:分支保存成功 + job.branch_id 自动回填
#       详情面板「绑定的简历分支」字段显示新分支名

# 3.2.3 Topbar「新建简历」下拉,选「基于岗位创建」→ 选同一 job
# 期望:行为与从 Job 详情进入完全一致(同一 URL 模板)
```

### 3.3 单测 + Playwright

```bash
# 后端
pytest tests/integration/test_019_alembic_migrations.py -v
# 期望:3 passed(迁移前后兼容)

# 前端
npm run test -- ResumeEditorSourceJob
# 期望:2 passed(预填逻辑 / 招聘需求折叠卡片)

# E2E 片段
npx playwright test tests/e2e/019-cross-module-linking.spec.ts -g "Job → Resume"
# 期望:1 passed
```

## 4. 冒烟 3:Job → Interview 入口(US3)

### 4.1 前置条件

```bash
# 沿用冒烟 2 创建的 job(已有 branch_id)
# 设置 VITE_USE_MOCK=true 让 LLM 返回预设 mock 答案
echo "VITE_USE_MOCK=true" >> frontend/.env.local
npm run dev
```

### 4.2 前端 UI

```bash
# 4.2.1 在 Job 详情面板点「为该岗位开始模拟面试」
# 期望(branch_id 已绑):CTA 可点击
# 期望(branch_id 未绑):CTA 置灰,tooltip "请先绑定简历分支"

# 4.2.2 点击 CTA → 跳转到 InterviewLive
# 期望:POST /interview-sessions { job_id, branch_id } 返回 200
#       跳转到 InterviewLive Intake 阶段

# 4.2.3 Intake 阶段表单预填
# 期望:
#   position = "前端"(预填,只读,带"(来自岗位信息)"灰色说明)
#   company = "字节"(预填,只读)
#   base_location = "北京"(预填,只读)
#   requirements_md 折叠卡片(只读)
#   用户可改写,改写后入库以用户值为准
```

### 4.3 LLM 出题验证

```bash
# 4.3.1 mock LLM 答 5 题
# 期望:question_gen 节点 prompt 包含 "## 岗位招聘需求\n3年 React 经验"
#       日志输出 "requirements_md_injected" 或 "requirements_md_truncated"

# 4.3.2 完成 5 轮后查看报告页
# 期望:report 中有 "## 该面试基于以下招聘需求(摘要)" 段
```

### 4.4 单测

```bash
# 后端
pytest tests/unit/test_error_question_auto_create.py -v
# 期望:4 passed(UPSERT 幂等 / score < 6 触发 / score >= 6 不触发 / 重评不重复)

# 前端
npm run test -- IntakeFormPrefill
# 期望:2 passed(4 字段预填 / 用户改写优先)
```

## 5. 冒烟 4:Interview → Error Book 自动沉淀(US4)

### 5.1 前置条件

```bash
# 沿用冒烟 3 创建的 session,5 轮 mock 答完
# 其中至少 1 题 mock LLM 返回 score < 6(如第 2 题 score=3.5)
```

### 5.2 数据库验证

```bash
# 5.2.1 用 dbq.py 查 error_questions
python backend/scripts/dbq.py
> SELECT id, question_text, score, source_session_id, source_question_id
> FROM error_questions
> WHERE source_session_id = '<session_id>';

# 期望:至少 1 行,source_session_id 与 source_question_id 都非 NULL
```

### 5.3 前端 UI

```bash
# 5.3.1 打开 http://localhost:5173/error-book
# 期望:列表筛选区显示三选项(全部 / 来自面试 / 手动录入),默认"全部"

# 5.3.2 选「来自面试」
# 期望:仅显示 source_session_id 非空的错题
#       含刚 mock 出来的低分题

# 5.3.3 点开该错题详情
# 期望:
#   - 静态文案"来自 字节 · 前端 · 2026-06-17 14:30"
#   - 两个按钮「移除自动来源」「删除」
#   - 「删除」按钮文案为"删除『来自 字节 · 前端 · 2026-06-17 14:30 的错题』"

# 5.3.4 点「移除自动来源」
# 期望:Toast「已移除自动来源」
#       详情面板的"来自 ..."文案消失
#       默认列表仍可见(已转为手动)

# 5.3.5 重新筛选「来自面试」
# 期望:该错题不在列表

# 5.3.6 回到详情,点「删除」
# 期望:确认弹窗(复用 016 删除弹窗,文案如上)
#       确认后错题从默认列表消失
```

### 5.4 单测

```bash
# 后端
pytest tests/unit/test_error_question_clear_source.py -v
# 期望:3 passed(清空 source / 置 NULL / 404 不存在)

# 前端
npm run test -- ErrorBookDetail
# 期望:3 passed(条件渲染 / 移除 mutation / 删除 mutation)
```

## 6. 冒烟 5:Ability Profile 链路确认(US5 / FR-021)

### 6.1 数据冒烟

```bash
# 6.1.1 沿用冒烟 3-4 完成一场面试,记录 ended_at 时间戳

# 6.1.2 等 1 分钟(ability_diagnose 异步触发)

# 6.1.3 查 ability_dimensions
python backend/scripts/dbq.py
> SELECT dimension, updated_at
> FROM ability_dimensions
> WHERE user_id = '<user_id>'
> ORDER BY updated_at DESC LIMIT 5;

# 期望:至少有 1 行的 updated_at > 6.1.1 的 ended_at
```

### 6.2 前端 UI

```bash
# 6.2.1 打开 http://localhost:5173/profile
# 期望:雷达图至少 1 个维度被更新,显示 "刚刚更新" 提示
```

## 7. 端到端 E2E

```bash
# 7.1 跑 Playwright 5 步联动
cd frontend && npx playwright test tests/e2e/019-cross-module-linking.spec.ts -v

# 期望:1 passed(完整链路无 4xx/5xx,无 console error)
```

## 8. 回归测试

```bash
# 8.1 既有 014 测试零回归
cd backend && pytest tests/ -k "jobs" -v
# 期望:所有 014 测试通过

# 8.2 既有 016 测试零回归
pytest tests/ -k "errors or error_questions" -v
# 期望:所有 016 测试通过

# 8.3 既有 Phase 4 测试零回归
pytest tests/ -k "interview or agent" -v
# 期望:所有 Phase 4 测试通过

# 8.4 既有 006 测试零回归
pytest tests/ -k "ability" -v
# 期望:所有 006 测试通过

# 8.5 前端零回归
cd ../frontend && npm run test
# 期望:全部通过

# 8.6 前端 E2E 既有测试零回归
npx playwright test tests/e2e/ --grep-invert "019-cross-module-linking"
# 期望:全部通过
```

## 9. Definition of Done

- [ ] 冒烟 1-5 全部命中
- [ ] E2E 5 步联动一次通过
- [ ] 既有 014 / 016 / 006 / Phase 4 测试零回归
- [ ] 8 个 Success Criteria(SC-001 ~ SC-008)命中
- [ ] 15 个 Edge Cases(E1 ~ E15)覆盖
- [ ] Constitution 5 原则满足
- [ ] 3 个风险(R1/R3/R8)缓解策略验证

## 10. 常见问题

**Q1: 跑迁移时 `interview_sessions.job_id` 已存在怎么办?**

```bash
# 用 dbq.py 查
python backend/scripts/dbq.py
> SELECT column_name FROM information_schema.columns
> WHERE table_name='interview_sessions' AND column_name='job_id';

# 若返回 1 行:在 plan 阶段协商重命名为 interview_job_id 或复用现有列
# 若返回 0 行:继续
```

**Q2: 错题自动沉淀没触发?**

- 检查 mock LLM 是否返回 `score < 6`
- 检查 `AUTO_ERROR_THRESHOLD` 常量值
- 检查 score 节点是否调用 `await ErrorQuestionService.maybe_create_from_question(...)`
- 查日志:应该有 `auto_error_created` 结构化日志

**Q3: requirements_md 没注入 prompt?**

- 检查 `intake` 节点是否读取 `state["job_id"]` 然后查 `jobs.requirements_md`
- 检查 `build_requirements_block` 是否被调用
- 查日志:应该有 `requirements_md_injected` 或 `requirements_md_truncated`

**Q4: Playwright 5 步联动 flaky?**

- 确认 `VITE_USE_MOCK=true` 已设置
- 确认 mock LLM 返回 5 个不同的问题(避免 Phase 4 循环卡住)
- 确认 mock LLM 至少 1 题返回 `score < 6`(触发错题沉淀)
- 增加 `await page.waitForLoadState('networkidle')` 在关键步骤后
