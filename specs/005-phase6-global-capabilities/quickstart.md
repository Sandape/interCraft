# Quickstart: Phase 6 — 全局能力收尾

## 前置条件

- Phase 1-5 全部完成,数据库已迁移至最新版本
- PostgreSQL 15 运行中(T008b 在线 DB)
- Redis 7 运行中(本地 6379)
- 后端 `backend/.env` 配置了 `DATABASE_URL` 和 `REDIS_URL`

## 迁移

```bash
# 添加 User 字段 + 创建新表
cd backend
uv run alembic upgrade head

# 确认迁移
uv run python -c "
from app.db import engine
import sqlalchemy as sa
async def check():
    async with engine.connect() as conn:
        rows = await conn.execute(sa.text('SELECT column_name FROM information_schema.columns WHERE table_name=$$users$$'))
        print([r[0] for r in rows])
"
```

预期输出: `scheduled_purge_at`, `cancellation_deadline`, `role` 出现在列清单中。

## 验证场景

### S1: 账号注销与取消

```bash
# 1. 发起注销
curl -X POST http://localhost:8000/api/v1/account/delete \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"confirmation": true}'
# 预期: 200, status=soft_deleted

# 2. 查询注销状态
curl http://localhost:8000/api/v1/account/deletion-status \
  -H "Authorization: Bearer $TOKEN"
# 预期: 200, can_cancel=true, days_until_cancellation_deadline=7

# 3. 取消注销
curl -X POST http://localhost:8000/api/v1/account/cancel-deletion \
  -H "Authorization: Bearer $TOKEN"
# 预期: 200, status=active
```

### S2: 数据导出

```bash
# 1. 发起导出
curl -X POST http://localhost:8000/api/v1/account/export \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
# 预期: 202, task_id, status=pending

# 2. 查询进度(替换 {task_id})
export TASK_ID=$(curl -s http://localhost:8000/api/v1/account/export/{task_id}/status \
  -H "Authorization: Bearer $TOKEN" | jq -r '.task_id')
# 预期: 200, status 从 processing → completed

# 3. 下载(等待 status=completed)
curl -o export.zip http://localhost:8000/api/v1/account/export/{task_id}/download \
  -H "Authorization: Bearer $TOKEN"
# 预期: 下载 ZIP 文件,含 JSON + Markdown

# 4. 验证 ZIP 内容
unzip -l export.zip
# 预期: 包含 resumes/ interviews/ error_questions/ 等目录
```

### S3: 简历导入

```bash
# 1. Markdown 导入
curl -X POST http://localhost:8000/api/v1/resumes/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test-resume.md" \
  -F "branch_name=导入测试"
# 预期: 201, branch_id, blocks_count > 0

# 2. JSON 导入(与导出格式对称)
curl -X POST http://localhost:8000/api/v1/resumes/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@exported-resume.json"
# 预期: 201
```

### S4: 审计日志

```bash
# 1. 执行一个写操作
curl -X POST http://localhost:8000/api/v1/account/delete \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"confirmation": true}'

# 2. 查看审计日志
curl "http://localhost:8000/api/v1/audit-logs?action=soft_delete&limit=10" \
  -H "Authorization: Bearer $TOKEN"
# 预期: 200, items 包含 soft_delete 记录

# 3. 取消注销(准备后续测试)
curl -X POST http://localhost:8000/api/v1/account/cancel-deletion \
  -H "Authorization: Bearer $TOKEN"

# 4. Admin 全量查询(需要 admin token)
curl "http://localhost:8000/api/v1/admin/audit-logs?limit=5" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# 预期: 200, 可看到所有用户的操作
```

### S5: Settings tab 验证

```bash
# 1. 查看订阅状态
curl http://localhost:8000/api/v1/subscription/current \
  -H "Authorization: Bearer $TOKEN"
# 预期: plan, token 用量

# 2. 查看可用方案
curl http://localhost:8000/api/v1/subscription/plans
# 预期: 3 个方案

# 3. 配额预检
curl -X POST http://localhost:8000/api/v1/subscription/pre-check \
  -H "Authorization: Bearer $TOKEN"
# 预期: 200, can_proceed=true
```

### S6: Resources & Help

```bash
# 1. 资源列表
curl "http://localhost:8000/api/v1/resources?category=tech_prep" \
  -H "Authorization: Bearer $TOKEN"
# 预期: 200, items 包含技术准备类资源

# 2. FAQ
curl http://localhost:8000/api/v1/help/faq \
  -H "Authorization: Bearer $TOKEN"
# 预期: 200, categories 包含 account/interview/resume/subscription/technical

# 3. 搜索
curl "http://localhost:8000/api/v1/help/search?q=注销&scope=all" \
  -H "Authorization: Bearer $TOKEN"
# 预期: 200, faq 和 resources 中匹配的结果
```

### S7: ARQ Cron 任务

```bash
# 手动触发 purge_expired_accounts(测试用)
cd backend
uv run python -m app.workers.cron --task purge_expired_accounts --json
# 预期: {"processed": 0, "purged_count": 0, "errors": []}

# 手动触发 cleanup_expired_exports
uv run python -m app.workers.cron --task cleanup_expired_exports --json
# 预期: {"deleted_count": N}
```

## 前端验证

```bash
cd frontend
npm run dev
```

1. 访问 `/settings` → 依次检查 4 个 tab:
   - 设备: 显示当前设备列表
   - 订阅: 显示方案 + 用量 + 重置日期
   - 安全: 修改密码 + 注销入口
   - 导出: 发起导出按钮 + 进度
2. 访问 `/resources` → 展示分类资源列表,可点击查看详情
3. 访问 `/help` → 展示 FAQ 分类,可展开,可搜索
4. 语音模式入口: 不应出现(已注释)

## 测试

```bash
# 后端测试
cd backend
uv run pytest tests/unit/account/ -v
uv run pytest tests/unit/audit/ -v
uv run pytest tests/integration/test_m20_lifecycle.py -v
uv run pytest tests/integration/test_m21_export_import.py -v
uv run pytest tests/integration/test_m22_audit.py -v

# 前端测试
cd frontend
npx vitest run tests/unit/components/settings/ -v

# E2E
npx playwright test tests/e2e/settings-flow.spec.ts
```
