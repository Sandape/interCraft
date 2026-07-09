# Research: 036 Resume v2 Finalize

**Date**: 2026-06-30 | **Plan**: [plan.md](./plan.md)

> Phase 0 — 关键决策的调研依据与备选方案对比。

---

## Decision 1: 数据清理执行机制

### Decision
**alembic 数据迁移 + Python CLI 双轨**：
- alembic 版本化（`036_cleanup_resume_data.py`）做幂等迁移
- `backend/scripts/cleanup_resume_data.py` 做人工触发 + dry-run + 行数报告

### Rationale
- alembic 提供 schema 版本控制 + 幂等回滚；与既有迁移链路一致
- CLI 脚本提供运维可观测性（人类可读日志 + JSON 输出）；与 Constitution II 对齐
- 双轨避免"忘了跑脚本"或"不知道什么脚本做了什么"的歧义

### Alternatives Considered
- **A1 (只 CLI)** — 不入 alembic；风险：跨环境不可复现
- **A2 (只 alembic)** — 无 dry-run；风险：误删不可逆
- **A3 (Truncate 在 SQL shell)** — 最低门槛；但无版本控制 + 无人审

---

## Decision 2: 路由重定向实现方式

### Decision
**React Router v6 `<Navigate to={...} replace />`**：
- `src/App.tsx` 中新增 3 条 `Route` 元素：path="/resume-v2"、path="/resume-v2/new"、path="/resume/v2/:id"
- element 是 `<Navigate to="/resume" replace />` / `<Navigate to="/resume?new=true" replace />` / `<Navigate to="/resume/${id}" replace />`

### Rationale
- 沿用 react-router-dom v6 既有模式（项目已有 Suspense + Navigate）
- `replace: true` 避免历史栈污染 + 防止 redirect loop
- 不引入新依赖

### Alternatives Considered
- **B1 (浏览器扩展)** — 不可控；e2e 看不到
- **B2 (nginx 重定向)** — 改动基础设施；本机 dev 不一定有 nginx
- **B3 (JS `window.location.replace`)** — 触发整页刷新；体验差

---

## Decision 3: Playwright 验收执行模式

### Decision
**`tests/e2e/036-resume-v2-finalize.spec.ts` 单文件 + 多 `test()`**：
- 登录后用 storageState 持久化 cookie
- 主流程 1 个 `test()`（创建 → 填字段 → 保存 → 导出 PDF）
- 细分功能 12 个 `test()`（每类功能点 1 个），每个独立可跑
- 每个 `test()` 写截图到 `evidence/036-playwright-<ts>/<feature>/step-*.png`
- 全部 `test()` 完成后写两份清单（incomplete + accepted）

### Rationale
- 多 `test()` 隔离失败 → 某个功能点失败不影响其他
- 每个 `test()` 单独有截图证据
- 两份清单作为产出可对外发布
- 沿用 032 `tests/e2e/032-v2-mvp.spec.ts` 既有范式

### Alternatives Considered
- **C1 (单 test 顺序跑)** — 一个失败整个中断；不可观测
- **C2 (用 curl + pytest)** — 用户明确要求 Playwright UI 操作
- **C3 (Cypress)** — 项目用 Playwright；不引入新栈

---

## Decision 4: v2 编辑器问题修复策略

### Decision
**主 Agent 优先参考 reactive-resume 源码**：
- v2 编辑器某 dialog 字段缺失 → `D:\Project\reactive-resume/apps/artboard/src/dialogs/resume/sections/<type>.tsx` 查参考实现
- v2 不存在的功能 → 评估是否补做（034 US5 范围之外的不补；034 US1-US4 范围之内的必补）
- 实施不可逆时 → 把问题列入 `incomplete-features.md` + 决定是否回退 spec

### Rationale
- 032/034 已大量参考 reactive-resume；新 spec 沿用
- 用户明确指示 `reactive-resume 的源码在 D:\Project\reactive-resume`
- 优先补 034 US1-US6 ship 范围；超出范围降级为 incomplete

### Alternatives Considered
- **D1 (完全重做编辑器)** — 工作量远超本 spec；放弃
- **D2 (跳过修复，列 incomplete)** — 用户预期"功能完好"；不达标

---

## Decision 5: 数据清理范围

### Decision
**清空 4 张表 + 关联 outbox；保留 schema**：
- `resume_branches` (v1) — DELETE FROM
- `resumes_v2` (v2) — DELETE FROM
- `resume_statistics_v2` — DELETE FROM
- `resume_analysis_v2` — DELETE FROM
- 关联 outbox 行 — `DELETE FROM outbox WHERE ... LEFT JOIN resumes_v2 ... IS NULL`

### Rationale
- 用户明确"全面弃用 v1 + 清空脏数据"
- 保留 schema 便于回滚 + 后续若需 v1 回退
- outbox 必须清，避免悬挂外键导致后续删除失败

### Alternatives Considered
- **E1 (DROP TABLE)** — 不可逆；超出"清理数据"语义
- **E2 (只清空 resumes_v2)** — 子表悬挂外键；风险

---

## Decision 6: 跨模块引用迁移策略

### Decision
**全仓 grep 后批量替换**：
- `grep -rn "/resume-v2\|/resume/v2/" src/` 列出全部引用点
- 逐个替换为 `/resume` 或 `/resume/:id`
- 在 `accepted-features.md` 记录每处替换前后对比

### Rationale
- 自动化发现 + 人工确认；避免漏改
- 用户明确要求"前端路由逻辑正确"

### Alternatives Considered
- **F1 (逐步替换，按使用顺序)** — 易遗漏
- **F2 (用 codemod)** — TS/JSX 混 codemod 工程量大；不值得

---

## Decision 7: Phase C 验收脚本的测试粒度

### Decision（基于用户 2026-06-30 补充）
**每个细分功能点 = 1 个 Playwright `test()`**：
- 编辑器顶部 Header / Breadcrumb / Sidebar toggle — 1 test
- 左侧 Section 列表展开/折叠 — 1 test（覆盖 13 个内置 section）
- 右侧 Settings 12 子面板展开/折叠 — 1 test（覆盖 12 个）
- Section item dialog（10 类）— 10 test（每类 1 个）
- Tiptap 富文本工具栏 — 1 test（覆盖 15+ 功能）
- dock 8 个按钮 — 8 test
- 模板 Gallery 切换 — 1 test
- 公开分享开关 — 1 test
- AI 分析按钮（如可用）— 1 test
- PDF 导出 — 1 test
- JSON 导出 — 1 test
- Undo/Redo — 1 test
- 移动端 sidebar 折叠 — 1 test
- **总计 ≥ 25 个 test()**；每个产出独立截图证据

### Rationale
- 用户明确"每个细分功能点都需要 Playwright 实测"
- 25 个 test() 粒度足够小，每个失败不影响其他
- 两份清单基于 test() PASS/FAIL 自动生成

### Alternatives Considered
- **G1 (一个大 test() 串行跑所有)** — 一个失败全断；不可观测
- **G2 (抽样测)** — 用户明确"每个细分功能点"；不达标

---

## Risk Acknowledgment

| 风险 | 缓解 |
|---|---|
| 清理脚本误删 prod 数据 | 仅 dev + dump 备份 + alembic 版本控制 |
| Playwright selector 找不到 | 参考 reactive-resume 源码补 v2 组件；列入 incomplete |
| dev server 启动顺序 | 文档化启动流程（backend → arq → frontend → Playwright） |
| e2e fixture 写死老路径 | 保留重定向兼容断言 + canonical 路径断言 |
| 编辑器某 dialog 字段缺失 | 参考 reactive-resume dialogs/resume/sections/ 修复 |
| 跨模块引用 grep 遗漏 | 双轮 grep（src/ + backend/）+ Playwright 验证 |

---

## References

- 036 spec: `specs/036-resume-v2-finalize/spec.md`
- 036 plan: `specs/036-resume-v2-finalize/plan.md`
- 参考简历: `C:\Users\30803\Desktop\简历\大模型应用开发简历v1.md`
- reactive-resume 源码: `D:\Project\reactive-resume`
- 032 v2 MVP spec: `specs/032-resume-renderer-v2/spec.md`
- 034 reactive-resume parity spec: `specs/034-v2-reactive-resume-parity/spec.md`
- Constitution: `.specify/memory/constitution.md`