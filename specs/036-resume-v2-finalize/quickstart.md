# Quickstart: 036 Resume v2 Finalize

**Date**: 2026-06-30 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

> Phase 1 — 端到端验证运行手册。

---

## Prerequisites

- 本机 dev 环境：Windows 11 + bash + uv + npm + Node 20+
- PostgreSQL 在线 + `intercraft_dev` DB
- Redis 本地 6379 ✅
- Playwright browsers 已装（`npx playwright install chromium`）
- reactive-resume 源码：`D:\Project\reactive-resume`（仅阅读参考，不修改）

## Phase A — 数据清理 + v1 触点下线

### A.1 跑清理脚本（dry-run）

```bash
cd D:/Project/eGGG
uv run python -m app.scripts.cleanup_resume_data --dry-run --json
```

**期望输出**：
```json
{
  "mode": "dry-run",
  "before": { "resume_branches": 12, "resumes_v2": 5, ... },
  "exit_code": 0
}
```

### A.2 实查落库（per `feedback_postgres_mcp_validation`）

```sql
SELECT 
  (SELECT COUNT(*) FROM resume_branches) AS v1,
  (SELECT COUNT(*) FROM resumes_v2) AS v2,
  (SELECT COUNT(*) FROM resume_statistics_v2) AS stats,
  (SELECT COUNT(*) FROM resume_analysis_v2) AS analysis;
```

**期望**：显示清理前行数（≥ 0）

### A.3 跑清理脚本（execute + backup）

```bash
uv run python -m app.scripts.cleanup_resume_data --backup --execute --yes
```

**期望**：输出"cleanup complete; logs at docs/evidence/036-data-cleanup-<ts>/"

### A.4 验证清理结果

```sql
SELECT 
  (SELECT COUNT(*) FROM resume_branches) AS v1,
  (SELECT COUNT(*) FROM resumes_v2) AS v2,
  (SELECT COUNT(*) FROM resume_statistics_v2) AS stats,
  (SELECT COUNT(*) FROM resume_analysis_v2) AS analysis;
```

**期望**：全部 = 0

### A.5 验证 v1 触点下线

```bash
cd D:/Project/eGGG

# 侧边栏菜单检查
grep -n "v2 简历\|ResumeListV2\|ResumeV2New\|ResumeEditor" src/components/layout/Sidebar.tsx
# 期望：0 命中（除已删除文件的注释）

# 路由表检查
grep -n "ResumeListV2\|ResumeV2New\|ResumeEditor\b" src/App.tsx
# 期望：0 命中

# 删除文件
ls src/pages/ResumeListV2.tsx src/pages/ResumeV2New.tsx src/pages/ResumeEditor.tsx 2>&1
# 期望：No such file or directory

# 跨模块引用
grep -rn "/resume-v2\|/resume/v2/" src/ --include="*.tsx" --include="*.ts"
# 期望：仅重定向规则 + 测试 fixture
```

### A.6 验证后端测试

```bash
cd D:/Project/eGGG/backend
uv run pytest -q
```

**期望**：100% 通过

### A.7 验证前端 typecheck + vitest

```bash
cd D:/Project/eGGG
npm run typecheck
npm run test
```

**期望**：clean + 全绿

---

## Phase B — v2 编辑器端到端走通（人工 smoke test）

### B.1 启动 dev server

```bash
# Terminal 1: backend
cd D:/Project/eGGG/backend
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2: arq worker
cd D:/Project/eGGG/backend
uv run arq app.workers.arq.WorkerSettings

# Terminal 3: frontend
cd D:/Project/eGGG
npm run dev
```

**期望**：
- backend: http://localhost:8000/docs 可访问
- frontend: http://localhost:5173 可访问

### B.2 手动 smoke test

1. 访问 http://localhost:5173/login → 登录
2. 进入 `/dashboard` → 检查侧边栏只有 1 个"简历中心"菜单项
3. 进入 `/resume` → 检查空状态 CTA
4. 点 Topbar"+" → 检查只有"新建简历"选项
5. 选模板 → 进入编辑器 → 确认三栏布局
6. 在 Basics 填字段 → 保存 → 退出再进 → 数据持久化
7. 切换模板 → 预览实时变化
8. 点 Download PDF → 下载文件
9. 关闭页签重开 → 数据保留

---

## Phase C — Playwright 验收 + 两份清单（关键关卡）

### C.1 启用 playwright webServer

修改 `playwright.config.ts` 启用 webServer 配置（如已注释）：
```ts
webServer: [
  { command: 'cd ../backend && uv run uvicorn app.main:app --port 8000', port: 8000, reuseExistingServer: true },
  { command: 'cd ../backend && uv run arq app.workers.arq.WorkerSettings', port: 8001, reuseExistingServer: true },
  { command: 'npm run dev', port: 5173, reuseExistingServer: true },
],
```

### C.2 跑 Playwright 验收脚本

```bash
cd D:/Project/eGGG
npm run e2e -- tests/e2e/036-resume-v2-finalize.spec.ts --reporter=list
```

**期望**：
- 35 个 test() 通过
- `docs/evidence/036-playwright-<ts>/` 目录有截图 + PDF + 两份清单

### C.3 检查两份清单

```bash
ls -la "docs/evidence/036-playwright-<ts>/"
# 期望：
# - step-*.png  (≥ 10 张中段截图)
# - final-resume.pdf
# - field-comparison.md
# - incomplete-features.md
# - accepted-features.md
```

打开 `incomplete-features.md` — 若有未通过项，主 Agent 触发修复循环：
1. 看失败 selector + 截图
2. 参考 `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/` 找对应组件
3. 修改 v2 编辑器
4. 重跑 Playwright

打开 `accepted-features.md` — 验收通过的细分功能清单。

### C.4 字段对比报告

打开 `field-comparison.md` 检查：
- 姓名 / 邮箱 / 学校 / 公司 / 项目名 / 技能分类 等关键字段一致
- 与 `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md` 对比

---

## Stop Conditions

036 完成条件（全部满足）：

- [ ] Phase A 全部步骤通过
- [ ] Phase B 手动 smoke test 通过
- [ ] Phase C Playwright ≥ 80% 通过
- [ ] `incomplete-features.md` 中 P1 项 = 0（剩余 P2/P3 可接受）
- [ ] `accepted-features.md` 中所有 P1 项 ✅
- [ ] `final-resume.pdf` 与参考简历关键字段一致
- [ ] 后端 pytest 100% + 前端 typecheck clean + vitest 全绿

## Rollback Strategy

若 Phase A 误删需回滚：
1. 从 `docs/evidence/036-data-cleanup-<ts>/db-backup.sql` 恢复
2. `psql -d intercraft_dev < db-backup.sql`
3. 验证 `mcp__postgres__query` 行数恢复

若 Phase B/C 改动引入 bug：
1. `git revert <commit>` 回滚代码
2. 清理脚本与代码改动解耦；代码回滚不影响 DB 状态
3. 若需重新清空 → 跑清理脚本即可

## References

- 036 spec: [spec.md](./spec.md)
- 036 plan: [plan.md](./plan.md)
- 036 research: [research.md](./research.md)
- 036 data-model: [data-model.md](./data-model.md)
- 036 contracts: [contracts/](./contracts/)
- 参考简历: `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`
- reactive-resume 源码: `D:\Project\reactive-resume`
- Constitution: `.specify/memory/constitution.md`