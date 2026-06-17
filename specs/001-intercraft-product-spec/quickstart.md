# Quickstart: InterCraft Phase 1 端到端验证

**Status**: Phase 1 output · **Date**: 2026-06-12 · **Plan**: [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md) · **Contracts**: [contracts/README.md](./contracts/README.md) · **Data Model**: [data-model.md](./data-model.md)

> 本文档提供 **Phase 1 可重复、可独立验证** 的端到端操作步骤。
> 验证 Phase 1 演示场景满足 spec §4 SC-001(「5 分钟内完成注册 → 登录 → 创简历分支 → 编辑 3 个块 → 手动保存版本 → 刷新验证」)。
> 本文**不**列实现细节;数据 schema 见 [data-model.md](./data-model.md),接口契约见 [contracts/](./contracts/)。

---

## 0. 前置条件

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 11 / macOS / Linux(开发机) |
| Docker | Docker Desktop 或 Docker Engine 24+ + Compose v2 |
| Python | 3.11+(本地开发) |
| Node.js | 20 LTS(本地开发) |
| 包管理 | uv(后端) / npm(前端,与 package-lock.json 一致) |
| 浏览器 | Chrome / Edge / Firefox / Safari 最近 2 个大版本 |
| 端口 | 后端 8000,前端 5173,Postgres 5432,Redis 6379(本地开发) |
| 网络 | 离线运行 OK(除 LLM 调用,Phase 1 不需要) |

---

## 1. 启动开发栈(单条命令,5 分钟内)

### 1.1 准备环境文件

```bash
# 仓库根
cp .env.example .env.local
cp backend/.env.example backend/.env

# 后端环境(关键项,Phase 1 默认值)
# DATABASE_URL=postgresql+asyncpg://intercraft:devpass@localhost:5432/intercraft
# REDIS_URL=redis://localhost:6379/0
# JWT_SECRET=<openssl rand -hex 32>
# MASTER_KEY=<openssl rand -base64 32>
# BCRYPT_COST_ROUNDS=12
# LOG_LEVEL=INFO
# CORS_ALLOWED_ORIGINS=http://localhost:5173
# VITE_USE_MOCK=false  # 前端,默认走真实 API
```

### 1.2 启动栈

```bash
# 一键启动:Postgres + Redis + api + worker
cd backend
docker compose up -d

# 等待健康(约 10 秒)
docker compose ps  # 应该看到 4 个 Up 状态

# 验证健康检查
curl http://localhost:8000/healthz
# 预期:{"status":"ok","db":"ok","redis":"ok","version":"0.1.0"}

# 跑迁移(创建全部 6 张表 + 启用 RLS)
uv run alembic upgrade head

# 跑种子脚本(可选,创建一个演示用户)
uv run python scripts/seed.py
# 用户: demo@intercraft.io / Demo1234
```

### 1.3 启动前端

```bash
# 另一个终端,仓库根
npm install
npm run gen:api  # 从 http://localhost:8000/api/v1/openapi.json 生成 src/api/schema.d.ts
npm run dev
# 浏览器打开 http://localhost:5173
```

**验证**:浏览器自动跳转到 `/login`,页面无 JS 错误,Console 无 `mockData` 引用(`VITE_USE_MOCK=false` 时,login 页走真实 API)。

---

## 2. 演示场景 SC-001(5 分钟 happy path)

> 对应 spec §4 SC-001 / §5.1 Phase 1 演示。

### 步骤

1. **注册新用户**
   - 访问 `http://localhost:5173/register`(前端应有此路由;若只有 `/login`,点击「注册」)
   - 填写:`email=demo+phase1@intercraft.io`,`password=Phase1!23`
   - 点击「注册」→ 预期 1 秒内自动登录并跳转到 `/dashboard`

2. **创建核心简历**
   - 进入「简历中心」(`/resume`)
   - 当前空状态应有「创建第一份简历」按钮
   - 点击 → 弹出对话框,填写 `name="核心简历"`,`is_main=true`
   - 提交 → 跳转到 `/resume/{新分支 id}` 编辑器

3. **添加 3 个块**
   - 在编辑器中点击「添加块」→ 选 `heading` → 填「林浩然」→ 保存
   - 添加 `summary` 块 → 内容填「3 年前端经验,专注 React / TypeScript」→ 保存
   - 添加 `experience` 块 → 内容填 mock 经历 → 保存
   - 预期:每次保存后顶部显示「已保存 · 2 秒前」(Phase 1 简化:1-2s 防抖后入库;Phase 3 锁 + 心跳后再优化)

4. **手动保存版本**
   - 顶部工具栏「保存版本」按钮
   - 弹出输入框,填「v1: 初始版本」
   - 提交 → 预期 Toast「版本 v1 已创建」
   - 检查 `GET /api/v1/resume-branches/{branch_id}/versions` 返回 1 条记录

5. **刷新验证持久化**
   - 浏览器按 F5 刷新
   - 预期:仍然登录、仍在编辑器、3 个块内容完整、版本列表显示 v1

6. **登出 + 重登**
   - 顶栏「登出」
   - 重新登录同样的邮箱密码
   - 预期:看到同样的简历分支和 3 个块
   - 验证:session 列表(若 UI 已实现)显示 2 个设备

**耗时目标**:上述 6 步在 5 分钟内完成(spec SC-001)。**通过条件** = 5/6 步成功 + 无 console 错误 + 无 5xx 响应。

---

## 3. 关键边界场景(E2E 套件覆盖)

### 3.1 5 设备限制(US-1 验收场景 2)

**手动验证**(需要 2 个浏览器或浏览器多 Profile):

1. 浏览器 A(Chrome)登录用户 X
2. 浏览器 B(Firefox)登录用户 X
3. 浏览器 C(Safari)登录用户 X
4. 浏览器 D(Edge)登录用户 X
5. 浏览器 E(Opera)登录用户 X
6. 浏览器 F(Brave)登录用户 X → **预期**:
   - 第 6 个登录成功
   - **响应中 `evicted_session_id` 字段指向浏览器 A 的 session**
   - 浏览器 A 在 5 分钟内被强制登出(或下次请求返回 401)
7. 验证:`GET /api/v1/users/me/sessions` 仍返回 5 个 active session(不是 6 个)

**E2E 自动化**:`tests/e2e/5device-eviction.spec.ts`(Playwright)
```ts
// 伪代码
for (let i = 0; i < 6; i++) {
  await newBrowserContext().then(async (ctx) => {
    await ctx.login(user.email, user.password);
  });
}
// 验证:第 1 个 context 的下一次请求返回 401
```

### 3.2 RLS 隔离(US-1 验收场景 4)

**手动验证**:

1. 创建两个测试用户(用户 A / 用户 B)
2. 用户 A 创建 1 个简历分支,3 个块
3. 复制 A 的 branch_id
4. 用 B 的 token 调 `GET /api/v1/resume-branches/{A的branch_id}`
5. **预期**:404(RLS 阻断,看上去像资源不存在)

**E2E 自动化**:`tests/integration/test_rls_isolation.py`(后端)
```python
async def test_rls_blocks_cross_user():
    async with app.db_session(user_a) as db:
        branch = await create_branch(db, ...)
    async with app.db_session(user_b) as db:
        result = await get_branch(db, branch.id)
        assert result is None  # RLS 阻断
```

### 3.3 简历分支「写时复制」(US-2 验收场景 1)

**手动验证**:

1. 用户登录,创建主简历 + 1 个 heading 块(「主简历标题」)
2. 创建分支「字节跳动 · 高级前端」,指定 `parent_id = 主简历 id`
3. 进入新分支编辑器 → 看到与主简历**相同**的 1 个 heading 块
4. 修改新分支的 heading 为「字节分支标题」→ 保存
5. 回到主简历 → heading 仍是「主简历标题」(未被影响)
6. 验证:`GET /api/v1/resume-branches/{主id}/blocks` 返回原 heading
7. 验证:`GET /api/v1/resume-branches/{新id}/blocks` 返回改后的 heading

**E2E 自动化**:`tests/integration/test_resume_cow.py`

### 3.4 简历版本回滚(US-3 验收场景 3)

**手动验证**:

1. 编辑器中:改块 A → 「手动保存版本 v1」
2. 改块 A → 「手动保存版本 v2」
3. 改块 A → 「手动保存版本 v3」
4. 点 v2 的「回滚」按钮
5. **预期**:
   - 弹窗「将创建新分支继承 v2 状态,原分支保留」
   - 确认后跳转到新分支,块 A 内容 = v2 内容
   - 原分支内容仍是 v3
6. 验证:版本树显示「回滚自 v2」标注

**E2E 自动化**:`tests/integration/test_resume_versioning.py`

### 3.5 字符串分数排序(US-2 验收场景 3)

**手动验证**:

1. 创建分支,5 个块 A B C D E
2. 拖拽 B 到 D 之后 → 顺序变成 A C D B E
3. 刷新 → 顺序保持
4. 反复拖拽 50 次 → 顺序仍正确(不出现重排代价 O(n))
5. 验证:`SELECT order_index FROM resume_blocks WHERE branch_id = ? ORDER BY order_index;` 顺序与 UI 一致

**单测**:`tests/integration/test_block_reorder.py`(覆盖 100 次随机拖拽)

### 3.6 自动 token 续签(US-1 验收场景 3)

**手动验证**:

1. 登录,进入编辑器
2. 等 16 分钟(access 15min + 1min 缓冲)
3. 编辑一个块,触发 API 请求
4. **预期**:请求成功,无感知续签(`X-Request-ID` 不变,响应头中可观察到「silent refresh」日志)

**E2E 自动化**:`tests/e2e/silent-refresh.spec.ts`(可通过时间 mock 加速)

### 3.7 健康检查 + 指标(运维验收)

```bash
# 启动后
curl http://localhost:8000/healthz | jq .
# {"status":"ok","db":"ok","redis":"ok","version":"0.1.0"}

# 注册一次后,查看指标
curl http://localhost:8000/metrics | grep auth_login
# auth_login_attempts_total{result="success"} 1
# auth_login_attempts_total{result="failed"} 0

# 编辑一次后,查看延迟
curl http://localhost:8000/metrics | grep http_request_duration
# http_request_duration_seconds_bucket{le="0.5",path="/api/v1/users/me"} ...
```

---

## 4. 自动化测试套件

### 4.1 单元 + 集成(后端)

```bash
cd backend
uv run pytest                          # 全跑
uv run pytest tests/unit/              # 仅单测
uv run pytest tests/integration/       # 跨模块集成
uv run pytest -k "rls"                 # 仅 RLS 测试
uv run pytest -k "jsonpatch"           # 仅跨端 parity
uv run pytest -k "versioning"          # 仅版本管理

# 覆盖率
uv run pytest --cov=app --cov-report=term-missing
# 目标:关键路径单测 ≥ 70%,集成 ≥ 50%(spec SC-021)
```

### 4.2 单元 + MSW(前端)

```bash
npm run test                           # vitest 跑全部
npm run test:ui                        # 浏览器 UI
npm run test:coverage                  # 覆盖率
```

### 4.3 E2E(Playwright,真实后端)

```bash
# 启动后端 + 前端(在另一个终端)
docker compose up -d
npm run dev

# 跑 E2E
npx playwright install                 # 首次
npm run e2e                            # 全跑
npm run e2e sc-001-demo                # 仅 SC-001
npm run e2e -- --headed                # 看浏览器

# 报告
npx playwright show-report
```

### 4.4 一键全跑

```bash
# 仓库根
make test                              # 后端 + 前端 + E2E
# 或
./scripts/run-all-tests.sh
```

---

## 5. 故障排查

| 现象 | 可能原因 | 解决 |
|---|---|---|
| `curl /healthz` 返回 503,`db: down` | Postgres 未启动 / DATABASE_URL 错 | `docker compose ps` + 检查 `backend/.env` |
| 浏览器 `/login` 页加载但提交后 `Network 401` | 后端未启动 / 端口错 | 检查 8000 端口,`docker compose logs api` |
| 前端 console:「schema.d.ts not found」 | 未跑 `npm run gen:api` | `npm run gen:api` |
| 注册时 `409 auth.email_taken` | 测试邮箱已存在 | 改用新邮箱 / 跑 `uv run python scripts/reset_db.py` |
| 5 设备测试时**未**触发踢出 | refresh token 重复使用,无新设备 | 检查 `auth_sessions` 中 `device_id` 字段(应 6 个不同) |
| 拖拽后块顺序不对 | `order_index` 累积超出 | 跑 `uv run python scripts/rewrite_order_indexes.py` |
| `pytest` 启动失败:`No module named pytest_asyncio` | uv sync 未跑 | `uv sync --all-extras` |
| Playwright 启动失败:「Browser not installed」 | 未 install | `npx playwright install chromium` |
| bcrypt 验证慢(>500ms) | 容器 CPU 限速 | 临时改 `BCRYPT_COST_ROUNDS=10`(plan RK-7) |
| RLS 测试在另一台机器不通过 | 缺 `FORCE ROW LEVEL SECURITY` | 检查 `migrations/versions/0001_initial.py` |

---

## 6. Phase 1 演示 checklist(PR / Release 验收)

- [ ] **SC-001** 5 分钟 happy path 通过(本文 §2)
- [ ] **SC-021** 后端关键路径单测覆盖率 ≥ 70%,集成 ≥ 50%
- [ ] **SC-010** 关键 API P95 ≤ 500ms(本地 docker 测)
- [ ] **SC-013** Dashboard 首屏 LCP ≤ 2s(浏览器 DevTools Lighthouse,本地 4G 模拟)
- [ ] **E1** 5 设备限制 + 主动踢出(本文 §3.1)
- [ ] **E2** RLS 跨用户隔离(本文 §3.2)
- [ ] **E3** COW 写时复制(本文 §3.3)
- [ ] **E4** 版本回滚创建新分支(本文 §3.4)
- [ ] **E5** 字符串分数排序 100 次拖拽不漂移(本文 §3.5)
- [ ] **E6** access token 静默续签(本文 §3.6)
- [ ] Constitution Check 双检通过(plan.md §「Re-evaluation」)
- [ ] `npm run gen:api` 生成的 `schema.d.ts` 与最新后端一致
- [ ] `docker compose up` 在干净机器 5 分钟内启动(SC M01)
- [ ] `VITE_USE_MOCK=true` 下所有 Phase 1 涉及页面仍可演示(回退路径,spec FR-111)
- [ ] README 文档完整(每模块有 README + CLI 示例)
- [ ] 没有任何 phase 1 显式禁止的依赖(`grep -E "langgraph|ai_messages|checkpoints"` 应为空)
- [ ] `pre-commit`(ruff + mypy + tsc + vitest)全绿
- [ ] CI(github actions / gitlab)全绿

---

## 7. Phase 1 完成后 → Phase 2 入口

Phase 2 启动前:
1. 跑 `npm run gen:api` 确认新生成的 schema 与 mockData 仍兼容
2. Use the canonical feature specs and `specs/README.md` when resolving spec §8 Q1/Q5.
3. 跑 `tests/integration/test_rls_isolation.py` 验证新表的 RLS 策略就位
4. 启动 Phase 2 任务列表(`/speckit-tasks`)
