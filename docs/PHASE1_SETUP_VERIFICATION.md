# Phase 1 (Setup) — 自动化验收方案

> 用途:独立 Agent 按本方案机械执行,逐项验证 `specs/001-intercraft-product-spec/tasks.md` §"Phase 1: Setup (Shared Infrastructure)" 中 **T001–T008b** 共 9 个任务是否已正确完成。
>
> **本方案是验收脚本,不是实现指南**。Agent 不得修改任何项目文件;发现不符合时只记录并报告,不得自行修复。

---

## 0. 范围

| 项 | 说明 |
|---|---|
| 验收对象 | T001 / T002 / T003 / T004 / T005 / T006 / T007 / T008 / T008b |
| 任务来源 | `specs/001-intercraft-product-spec/tasks.md` L41–L53 |
| 不验收 | Phase 2 (Foundational) 及之后 — 那些目录/文件**应当尚未出现**(见 §3.10 反向检查) |
| 工作目录 | `D:\Project\eGGG` |
| 操作系统 | Windows 11 + Git Bash;命令使用 bash 语法,路径使用正斜杠或 Windows 反斜杠均可 |

---

## 1. 前置条件

执行前 Agent 必须确认以下工具可用。任一缺失 → 直接终止验收并报告"环境不满足"。

| 工具 | 检查命令 | 期望 |
|---|---|---|
| `git` | `git --version` | 非空,≥ 2.40 |
| `node` | `node --version` | `v20.x` 或 `v22.x` |
| `npm` | `npm --version` | `10.x` 或 `11.x` |
| `python` | `python --version` | `Python 3.12.x` |
| `uv` | `uv --version` | `0.4.x` 或更高 |
| `redis-cli` | `redis-cli -p 6379 PING` | `PONG` |
| `curl` | `curl --version` | 非空 |
| 网络可达 | `curl -sS -o /dev/null -w "%{http_code}" --max-time 5 https://pypi.org` | `200` 或 `301`/`302` |
| 在线 DB | `Test-NetConnection 81.71.152.210 -Port 5432`(PowerShell)或 `timeout 5 bash -c '</dev/tcp/81.71.152.210/5432'`(bash) | `True` / 退出码 0 |

`uv` 缺失时按 https://docs.astral.sh/uv/ 提示由用户安装后再启动,不要替用户安装。

---

## 2. 验收方法

### 2.1 流程

1. 在 `D:\Project\eGGG` 下创建 `docs/evidence/PHASE1_SETUP_<UTC时间戳>/` 目录。
2. 对每条检查运行命令,把 **stdout / stderr / exit code** 全部重定向到 `evidence/<check-id>.log`。
3. 对照 §3 表格中的"通过条件"判定 PASS / FAIL。
4. 全部完成后,在 `evidence/SCORECARD.md` 中填入 §4 评分卡。
5. 把整个 `evidence/` 目录的相对路径写回到本方案的 §7 报告区,作为 Agent 的最终输出。

### 2.2 通用规则

- **不修改项目**:Agent 不得写、删、改 `D:\Project\eGGG` 下任何文件(创建 `evidence/` 目录除外,且必须落在 `docs/evidence/` 内)。
- **不引入副作用**:`uv sync`、`npm install` 这类命令在沙箱外会产生 lock 更新 — 执行前先确认 `uv.lock` / `package-lock.json` 当前 commit hash,跑完后 `git status` 若有变化,记录为 `INFO`(不算 FAIL),但要提示用户复核。
- **不要在日志里打印敏感值**:`backend/.env` 里的 `DATABASE_URL` 包含密码,验证时只能 grep key 名称,不要 echo value。`JWT_SECRET` / `MASTER_KEY` 同理。
- **网络超时统一 30s**;超过即视 FAIL。
- **幂等性**:每条检查可重复执行,结果应一致(除 T008b 的 `alembic upgrade head` — 已在 head 时是 no-op,视为 PASS)。

### 2.3 退出约定

- 验收全程零 FAIL → Agent 最终输出 `PHASE1_SETUP_VERIFICATION: PASS`
- 任意 1 项 FAIL → Agent 最终输出 `PHASE1_SETUP_VERIFICATION: FAIL (<check-id>: <reason>)`
- 前置条件缺失 → Agent 最终输出 `PHASE1_SETUP_VERIFICATION: ABORT (<missing tool>)`

---

## 3. 检查清单

> 格式约定:
> - **Check ID**:全局唯一,`F<task-num>.<seq>`,如 `F1.3` = T001 第 3 项
> - **命令**:Agent 在 `D:\Project\eGGG` 下执行;多行用 `&&` 串联
> - **通过条件**:必须全部命中
> - **失败条件**:任一命中即 FAIL

### 3.1 T001 — 后端项目骨架

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F1.1** | `test -f backend/pyproject.toml && echo OK` | 输出 `OK` | 文件缺失 |
| **F1.2** | `grep -E '^name *=' backend/pyproject.toml` | 命中(说明有项目名) | 无 `name` 字段 |
| **F1.3** | `test -f backend/app/__init__.py && grep -E '__version__ *= *["'\'']0\.1\.0["'\'']' backend/app/__init__.py` | 退出码 0 | 缺少 `__version__ = "0.1.0"` |
| **F1.4** | `test -f backend/Dockerfile` | 退出码 0 | Dockerfile 缺失 |
| **F1.5** | `test -f backend/.dockerignore` | 退出码 0 | .dockerignore 缺失 |
| **F1.6** | `test -d backend/app && find backend/app -maxdepth 2 -type d` | 至少包含 `app/` 自身(允许 src layout 也可,但本任务写的是 `app/__init__.py`,所以 `app/` 必须存在) | 目录结构不对 |
| **F1.7** | `test -f backend/uv.lock && head -1 backend/uv.lock` | uv.lock 首行非空,version 字段为 1 | 锁文件缺失或格式异常 |

### 3.2 T002 — docker-compose 文件

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F2.1** | `test -f backend/docker-compose.yml` | 退出码 0 | 缺失 |
| **F2.2** | `grep -E '^services:' backend/docker-compose.yml` | 命中 | 顶层无 `services:` |
| **F2.3** | `grep -iE 'redis|api|worker' backend/docker-compose.yml` | 三个关键词至少出现两次(说明这些服务已声明) | 服务定义明显缺失 |
| **F2.4** | `grep -iE 'postgres:15' backend/docker-compose.yml` | 命中(允许被注释掉) | 完全找不到 postgres 痕迹 |
| **F2.5** | `test -f backend/docker-compose.test.yml` | 退出码 0 | 缺失 |
| **F2.6**(反) | `command -v docker >/dev/null 2>&1 && echo HAVE_DOCKER || echo NO_DOCKER` | 记录 `HAVE_DOCKER` 或 `NO_DOCKER`,**均不视为 FAIL**;只是说明信息(本机无 Docker 是预期状态) | — |
| **F2.7**(反) | `docker compose -f backend/docker-compose.yml config 2>&1 \| head -5` | 仅在 `F2.6=HAVE_DOCKER` 时执行;输出应无 "ERROR" | 解析失败(本机无 Docker 时跳过) |

> 注意:T002 任务规范明确"不运行 `docker compose up`",所以本验收**不**要求服务实际启动;只检查文件存在 + YAML 解析合法。

### 3.3 T003 — env 模板

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F3.1** | `test -f .env.example` | 退出码 0 | 根 `.env.example` 缺失 |
| **F3.2** | `for k in DATABASE_URL REDIS_URL JWT_SECRET MASTER_KEY BCRYPT_COST_ROUNDS CORS_ALLOWED_ORIGINS LOG_LEVEL; do grep -q "^$k=" .env.example \|\| { echo "MISSING: $k"; exit 1; }; done && echo OK` | 输出 `OK` | 缺少任一必填键 |
| **F3.3** | `grep -E '^REDIS_URL=redis://localhost:6379/0' .env.example` | 命中 | 默认值不对 |
| **F3.4** | `grep -E '^DATABASE_URL=postgresql\+asyncpg://' .env.example` | 命中(占位符也允许,关键是 schema 对) | schema 不是 asyncpg |
| **F3.5** | `head -5 .env.example` | 第一行附近有"生产前必须替换"或同义警告 | 无任何警告注释 |
| **F3.6** | `grep -E '^\.env$' .gitignore` | 命中 | `.env` 未被 ignore |
| **F3.7**(信) | `test -f backend/.env.example` | 记录是否存在;**task 规范已澄清根目录即可,backend/.env.example 不强制** | — |
| **F3.8**(信) | `test -f backend/.env` | 仅记录是否存在,不要 echo 内容 | — |

### 3.4 T004 — 前端 `package.json`

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F4.1** | `test -f package.json` | 退出码 0 | 缺失 |
| **F4.2** | `node -e "const p=require('./package.json'); const need=['test','test:ui','test:coverage','e2e','gen:api','lint','typecheck']; const miss=need.filter(k=>!(k in p.scripts)); if(miss.length){console.error('MISSING scripts:',miss);process.exit(1)} else console.log('OK')"` | 输出 `OK` | 任一 script 缺失 |
| **F4.3** | `node -e "const p=require('./package.json'); const need={deps:['zustand','@tanstack/react-query','fractional-indexing','fast-json-patch','js-sha256'], dev:['vitest','@testing-library/react','@testing-library/jest-dom','happy-dom','msw','@playwright/test','openapi-typescript']}; const missD=need.deps.filter(k=>!p.dependencies[k]); const missDV=need.dev.filter(k=>!p.devDependencies[k]); const all=[...missD.map(k=>'dep:'+k),...missDV.map(k=>'dev:'+k)]; if(all.length){console.error('MISSING:',all);process.exit(1)} else console.log('OK')"` | 输出 `OK` | 依赖缺失 |
| **F4.4** | `test -d node_modules` | 退出码 0 | 未安装(应跑过 `npm install`) |
| **F4.5** | `npx tsc --noEmit 2>&1 \| tail -5; echo "exit=$?"` | exit code = 0,输出空或仅 informational | 任何 TS 错误 |
| **F4.6** | `npm test -- --run 2>&1 \| tail -20; echo "exit=$?"` | exit code = 0;允许 0 个测试文件(Phase 1 还没写测试文件),但 vitest 自身应能起 | vitest 启动失败 |
| **F4.7** | `test -f scripts/gen-api.mjs` | 退出码 0 | gen:api 脚本文件缺失 |
| **F4.8**(信) | `test -d src/api && test -f src/api/schema.d.ts` | 记录是否存在;schema.d.ts 在 .gitignore,可能未生成,只记录 | — |

### 3.5 T005 — 后端 `pyproject.toml` 依赖

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F5.1** | `test -f backend/pyproject.toml` | 退出码 0 | 缺失 |
| **F5.2** | `grep -E '^fastapi *(=|>=)' backend/pyproject.toml` | 命中,且约束形如 `>=0.115,<0.117` | 缺失或版本范围错 |
| **F5.3** | `grep -E 'sqlalchemy\[asyncio\]' backend/pyproject.toml` | 命中 | 缺失 |
| **F5.4** | `for pkg in asyncpg alembic 'pydantic-settings' structlog 'fastapi-users\[sqlalchemy\]' 'PyJWT\[cryptography\]' cryptography bcrypt arq redis jsonpatch 'python-fractional-indexing' httpx pytest 'pytest-asyncio' ruff mypy; do grep -qiE "(^|[^a-z])${pkg//[/\\[}" backend/pyproject.toml \|\| { echo "MISSING: $pkg"; exit 1; }; done && echo OK` | 输出 `OK`(可能有 1-2 个因 grep 转义问题需要人工复审,记录到 evidence) | 关键包缺失 |
| **F5.5** | `cd backend && uv sync --frozen 2>&1 \| tail -10; echo "exit=$?"` | exit code = 0;可能输出 "Audited" / "Resolved" 字样 | 依赖解析失败 |

> 注:F5.4 的 grep 因 `[` `]` 字符在正则中是特殊字符,转义不一定完美,若个别包 grep 漏报,**人工对照 §3.5 期望清单**(`fastapi>=0.115,<0.117` / `sqlalchemy[asyncio]>=2.0.30,<2.1` / `asyncpg` / `alembic` / `pydantic-settings` / `structlog` / `fastapi-users[sqlalchemy]>=13.0,<14.0` / `PyJWT[cryptography]>=2.9,<3.0` / `cryptography` / `bcrypt` / `arq` / `redis` / `jsonpatch` / `python-fractional-indexing` / `httpx` / `pytest` / `pytest-asyncio` / `ruff` / `mypy`),缺失即 FAIL。

### 3.6 T006 — 工具链配置

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F6.1** | `test -f backend/ruff.toml` | 退出码 0 | 缺失 |
| **F6.2** | `test -f backend/.pre-commit-config.yaml` | 退出码 0 | 缺失 |
| **F6.3** | `grep -E 'ruff|mypy|tsc|vitest' backend/.pre-commit-config.yaml \| wc -l` | 输出 ≥ 4(四个 hook 全列) | hook 不全 |
| **F6.4** | `test -f tsconfig.json && node -e "const t=require('./tsconfig.json'); const c=t.compilerOptions\|\|{}; if(c.strict!==true){console.error('strict not true');process.exit(1)} console.log('OK')"` | 输出 `OK` | `strict` 不是 true |
| **F6.5** | `test -f vite.config.ts && grep -E 'test:|vitest' vite.config.ts` | 命中(vitest config block 存在) | vite.config.ts 中无 vitest 段 |
| **F6.6**(信) | `cd backend && uv run ruff check . 2>&1 \| tail -5; echo "exit=$?"` | exit code = 0;空仓库可能 "All checks passed!" | ruff 配置错 |
| **F6.7**(信) | `cd backend && uv run mypy --version 2>&1` | 输出版本号 | mypy 不可用(若 F5.5 成功,这里必然可用) |

### 3.7 T007 — 根目录文档与 .gitignore

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F7.1** | `test -f README.md` | 退出码 0 | 根 README 缺失 |
| **F7.2** | `grep -iE 'quickstart|5-minute|5 分钟' README.md` | 命中 | 没指向 quickstart |
| **F7.3** | `test -f backend/README.md` | 退出码 0 | backend README 缺失 |
| **F7.4** | `for cmd in 'uv sync' 'uv run pytest' 'uv run uvicorn' 'uv run arq'; do grep -q "$cmd" backend/README.md \|\| { echo "MISSING: $cmd"; exit 1; }; done && echo OK` | 输出 `OK` | 命令说明不全 |
| **F7.5** | `for k in 'backend/.venv' 'src/api/schema.d.ts' 'playwright-report' 'node_modules' '.env.local'; do grep -qF "$k" .gitignore \|\| echo "MISSING: $k"; done` | 全部命中(5 行,允许顺序不同) | 关键忽略项缺失 |
| **F7.6** | `test -f Makefile` | 退出码 0(本任务未强制,但 T150 之后会要求,作为信息记录) | — |

### 3.8 T008 — 启动脚本

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F8.1** | `test -f scripts/run-all-tests.sh` | 退出码 0 | 缺失 |
| **F8.2** | `for kw in pytest vitest playwright; do grep -q "$kw" scripts/run-all-tests.sh \|\| { echo "MISSING: $kw"; exit 1; }; done && echo OK` | 输出 `OK` | 三大测试入口缺一 |
| **F8.3** | `test -f scripts/dev-up.sh` | 退出码 0 | 缺失 |
| **F8.4** | `grep -E 'docker compose up' scripts/dev-up.sh` | 命中输出"未找到 docker compose up"即视为 PASS(本机无 Docker 就不该调它) | 实际命中 = FAIL(违反 task 约束) |
| **F8.5** | `for kw in 'uv sync' 'alembic' 'gen:api' 'npm run dev'; do grep -q "$kw" scripts/dev-up.sh \|\| { echo "MISSING: $kw"; exit 1; }; done && echo OK` | 输出 `OK` | 启动链不完整 |
| **F8.6** | `grep -iE 'redis.*6379|localhost:6379' scripts/dev-up.sh` | 命中 | 没有 Redis 提示横幅 |
| **F8.7** | `bash -n scripts/run-all-tests.sh && bash -n scripts/dev-up.sh && echo OK` | 输出 `OK` | 任一脚本语法错 |

### 3.9 T008b — 在线 Postgres 接入

> **本节会接触真实 DB。处理 `backend/.env` 时:用 `grep -E '^KEY=' file` 验证键存在,绝不 `cat` / `echo` value。**

| Check | 命令 | 通过条件 | 失败条件 |
|---|---|---|---|
| **F8b.1** | `test -f backend/.env` | 退出码 0 | `.env` 缺失(用户没接入) |
| **F8b.2** | `grep -qE '^DATABASE_URL=postgresql\+asyncpg://' backend/.env` | 退出码 0;**只 grep 键名前缀,不要打 value** | DATABASE_URL 缺失或 schema 错 |
| **F8b.3** | `grep -qE '^REDIS_URL=redis://' backend/.env` | 退出码 0 | REDIS_URL 缺失 |
| **F8b.4** | `grep -E '^DATABASE_URL=' backend/.env \| cut -d@ -f2` | 输出形如 `host:port/dbname`(允许密码占位) | URL 解析不出 host:port |
| **F8b.5** | `redis-cli -p 6379 PING` | 输出 `PONG` | Redis 不可达 |
| **F8b.6** | `cd backend && uv run alembic current 2>&1 \| tail -10; echo "exit=$?"` | exit code = 0;输出包含一个 revision id(形如 `0001_xxx (head)`) | 迁移未跑过 |
| **F8b.7** | `cd backend && uv run alembic upgrade head 2>&1 \| tail -5; echo "exit=$?"` | exit code = 0;输出 "Running upgrade ... -> 0001_xxx" 或 "already at head" | 迁移执行失败 |
| **F8b.8** | `cd backend && uv run python -c "import asyncio, asyncpg, os; d=os.environ['DATABASE_URL'].replace('postgresql+asyncpg','postgresql'); async def main(): c=await asyncpg.connect(d); r=await c.fetchval('SELECT 1'); await c.close(); print('SELECT 1 =', r); asyncio.run(main())" 2>&1; echo "exit=$?"` | 输出 `SELECT 1 = 1`;exit code = 0 | DB 连不上或权限错 |
| **F8b.9** | `cd backend && uv run python -c "import asyncio, asyncpg, os; d=os.environ['DATABASE_URL'].replace('postgresql+asyncpg','postgresql'); async def main(): c=await asyncpg.connect(d); rows=await c.fetch(\"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename\"); print([r['tablename'] for r in rows]); await c.close(); asyncio.run(main())" 2>&1; echo "exit=$?"` | 输出至少包含 6 张表:`auth_sessions` / `resume_blocks` / `resume_branches` / `resume_versions` / `user_credentials` / `users` | 表数 < 6 或关键表缺失 |

> 备注:F8b.6-F8b.9 在 DB 不可达时整体 FAIL;这正是 T008b 的"接入"含义,FAIL 即表示用户没接好。

### 3.10 反向检查 — Phase 2+ 不应出现

> 这些是 Phase 2 才开始写的目录/文件;**当前 boundary 应为缺失**。若已存在 → 报告 `INFO: phase 2+ files detected`,不算 FAIL,但提示用户复核(可能项目已越过 boundary)。

| Check | 命令 | 期望(PASS 状态) |
|---|---|---|
| **FN.1** | `test ! -d backend/app/core || echo "EXISTS: backend/app/core"` | `EXISTS` → INFO;不存在 → PASS |
| **FN.2** | `test ! -d backend/app/modules || echo "EXISTS: backend/app/modules"` | 同上 |
| **FN.3** | `test ! -d backend/migrations/versions || echo "EXISTS: backend/migrations/versions"` | 同上 |
| **FN.4** | `test ! -d backend/app/workers || echo "EXISTS: backend/app/workers"` | 同上 |
| **FN.5** | `find src/pages -maxdepth 1 -name "*.tsx" 2>/dev/null \| wc -l` | 记录文件数;Phase 1 时 src/pages 可能已有 Login/Register 雏形(T074/T075 属 US1,见 §3.10 注释) |

> **重要校准**:上面的反向检查是**对照 `tasks.md` §Phase 1 边界** — 即"Setup 完结时,Phase 2 的 M01/M02/M03 还没写"。但 `tasks.md` §Phase 1 把 US1(账号)的 T063-T080(前端 auth slice,含 Login/Register 页面)放在了 §"Phase 3: User Story 1" 而非 §"Phase 1: Setup"。
>
> 因此:
> - `backend/app/core/`、`backend/app/modules/`、`backend/migrations/versions/`、`backend/app/workers/` → 应**确实不存在**于 Setup boundary。
> - `src/pages/Login.tsx`、`src/pages/Register.tsx` → Setup boundary 时**也不应存在**(它们属 US1)。
> - 但如果本验收在 **Phase 1+2+3 全部完成后**才跑(项目已越过 boundary),FN.\* 全部会触发 INFO,**这是预期,不是失败**。Agent 应在评分卡"边界状态"一栏明确写出"项目已越过 Setup boundary"。

---

## 4. 评分卡

执行完成后,Agent 在 `docs/evidence/PHASE1_SETUP_<timestamp>/SCORECARD.md` 写入:

```markdown
# Phase 1 (Setup) 验收评分卡

- **执行时间(UTC)**: <ISO 8601>
- **Git HEAD**: <commit hash>
- **边界状态**: <at boundary / past boundary by N tasks>

## 总览

| 类别 | 总数 | PASS | FAIL | INFO |
|---|---|---|---|---|
| T001 后端骨架 (F1.x) | 7 | | | |
| T002 docker-compose (F2.x) | 7 | | | |
| T003 env 模板 (F3.x) | 8 | | | |
| T004 前端 package.json (F4.x) | 8 | | | |
| T005 后端 pyproject (F5.x) | 5 | | | |
| T006 工具链 (F6.x) | 7 | | | |
| T007 根目录文件 (F7.x) | 6 | | | |
| T008 启动脚本 (F8.x) | 7 | | | |
| T008b 在线 DB (F8b.x) | 9 | | | |
| 反向检查 (FN.x) | 5 | | | |
| **合计** | **69** | | | |

## 失败项明细

| Check | 期望 | 实际 | 证据文件 |
|---|---|---|---|
| | | | `evidence/Fx.x.log` |

## 结论

- `PHASE1_SETUP_VERIFICATION: PASS` (0 FAIL)
- `PHASE1_SETUP_VERIFICATION: FAIL (<n> FAIL)`
- `PHASE1_SETUP_VERIFICATION: ABORT (<reason>)`
```

---

## 5. 证据采集规范

```
docs/evidence/PHASE1_SETUP_<UTC时间戳>/
├── SCORECARD.md            # §4 评分卡
├── env-precheck.log        # §1 前置条件
├── F1.1.log ... F1.7.log   # 每条 check 一份日志
├── F2.1.log ...
├── ...
├── F8b.1.log ... F8b.9.log
├── FN.1.log ... FN.5.log
└── git-before.txt          # `git rev-parse HEAD` 起点
└── git-after.txt           # 跑完后 `git status --porcelain` (预期空)
```

每份 `.log` 内容格式:

```
$ <command>
<stdout>
<stderr>
exit_code=<N>
```

---

## 6. 失败处理协议

1. **任意 FAIL**:Agent 立即停止后续无关 check(避免级联误报),先把失败项 + 日志写入 SCORECARD,再继续可独立执行的下条 check(只为了完整证据)。
2. **不在日志里粘贴 .env value** — F8b.2/F8b.3 即使要排错也只贴 key 名。
3. **若 `uv sync` / `npm install` 改了 lock 文件**:把 `git diff <lockfile>` 摘要写入 `evidence/lockfile-changes.log`,在 SCORECARD 标 INFO,但不视为 FAIL。
4. **DB 相关 FAIL(F8b.6-F8b.9)**:Agent 不要尝试重置 DB 或重跑 migration,只记录;用户决定是否人工介入。

---

## 7. Agent 最终输出格式

```
=== PHASE1_SETUP_VERIFICATION ===
verdict: <PASS|FAIL|ABORT>
boundary_state: <at boundary | past boundary by N tasks>
total_checks: 69
passed: <n>
failed: <n>
info: <n>
failed_items: [<check-id>, ...]
evidence_dir: docs/evidence/PHASE1_SETUP_<UTC时间戳>/
scorecard: docs/evidence/PHASE1_SETUP_<UTC时间戳>/SCORECARD.md
notes: <一行简短总结,可选>
=== END ===
```

---

## 附录 A — Phase 1 任务原文速查

引自 `specs/001-intercraft-product-spec/tasks.md` L41–L53,方便 Agent 对照:

- **T001** 后端骨架:`backend/pyproject.toml` + `backend/app/__init__.py`(`__version__ = "0.1.0"`) + `backend/Dockerfile` + `backend/.dockerignore`
- **T002** docker-compose:`backend/docker-compose.yml`(postgres:15 **注释掉**,redis:7 **禁用**,api,worker) + `backend/docker-compose.test.yml` 占位;**不**跑 `docker compose up`
- **T003** env 模板:根 `.env.example` + `backend/.env.example` 含实际本地默认值;生产前必须替换 JWT_SECRET/MASTER_KEY,T008b 替换 DATABASE_URL
- **T004** 前端 devDeps + scripts:`test` / `test:ui` / `test:coverage` / `e2e` / `gen:api` / `lint` / `typecheck`
- **T005** 后端依赖(plan §Technical Context 列出的所有固定版本)
- **T006** 工具链:`backend/ruff.toml` + `backend/.pre-commit-config.yaml`(ruff + mypy + tsc + vitest) + `tsconfig.json`(`strict: true`) + `vite.config.ts`(vitest 段)
- **T007** 根文件:`README.md`(5-min 入口) + `backend/README.md`(uv sync / pytest / uvicorn / arq) + `.gitignore` 增补
- **T008** scripts:`scripts/run-all-tests.sh` + `scripts/dev-up.sh`(无 `docker compose up`)
- **T008b** 在线 PG:`backend/.env` 写 `DATABASE_URL`,alembic upgrade head 成功

## 附录 B — 不在 Phase 1 范围(防越界)

- 任何 `backend/app/modules/**` 业务代码(US1+)
- 任何 `backend/app/core/config.py` 等 M01 产物(Foundational)
- 任何 `backend/migrations/versions/*.py`(Foundational)
- 任何 `src/pages/Login.tsx` / `src/pages/Register.tsx`(US1)
- 任何 `src/repositories/AuthRepository.ts`(US1)
- 任何 `backend/tests/**` 实际测试逻辑(Foundational 起的 T009+ 才有)
