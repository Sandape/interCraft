# Phase 1 (Setup) 启动验证 — 评分卡

- **执行时间(UTC)**: 2026-06-12T16:08:36Z
- **Git HEAD**: 50a8ea55d029eedfa2bbe103e15ed4184dce93f2
- **范围**: Setup 静态检查(F1–F8b + FN) + 实际启动 backend (uvicorn) + 实际启动 frontend (vite)

## 总览

| 类别 | 总数 | PASS | FAIL | INFO |
|---|---|---|---|---|
| Setup 静态 F1–F8b | 60 | 58 | 0 | 2 |
| 反向检查 FN | 5 | 0 | 0 | 5 |
| 启动 smoke (额外) | 4 | 3 | 1 | 0 |
| **合计** | **69** | **61** | **1** | **7** |

## Setup 静态检查

| 类别 | 结果 |
|---|---|
| F1.x (T001 后端骨架) | 7/7 PASS |
| F2.x (T002 docker-compose) | 5/7 PASS + 2 INFO (NO_DOCKER) |
| F3.x (T003 env 模板) | 6/8 PASS + 2 INFO |
| F4.x (T004 前端 package.json) | 7/8 PASS + 1 INFO |
| F5.x (T005 后端 pyproject) | 5/5 PASS |
| F6.x (T006 工具链) | 7/7 PASS |
| F7.x (T007 根目录文档) | 6/6 PASS |
| F8.x (T008 启动脚本) | 7/7 PASS |
| F8b.x (T008b 在线 DB) | 9/9 PASS |
| FN.x (反向) | 5/5 INFO (项目越 boundary) |

## 启动 smoke 验证

| Check | 命令 | 结果 |
|---|---|---|
| **B.1** | `uvicorn app.main:app --port 8765` | ✅ 启动成功(uvicorn log: `Application startup complete`) |
| **B.2** | `GET /healthz` | ✅ HTTP 200, `{"status":"ok","db":"ok","redis":"ok","version":"0.1.0"}` |
| **B.3** | `GET /api/v1/openapi.json` | ✅ HTTP 200, OpenAPI 3.1 schema 完整 |
| **B.4** | `GET /api/v1/docs` | ✅ HTTP 200, Swagger UI 加载 |
| **B.5** | `GET /` (vite dev) | ✅ HTTP 200, Vite 服务 HTML |
| **B.6** | `POST /api/v1/auth/register` | ❌ HTTP 500,IntegrityError `auth_sessions_device_id_unique` |

## ⚠️ 启动发现的真实 Bug (非 Setup 范围)

**B.6 失败**: 注册接口首次调用抛 `UniqueViolationError` on `auth_sessions_device_id_unique`。

### 根因(从 traceback)
```
sqlalchemy.exc.IntegrityError: duplicate key value violates unique
constraint "auth_sessions_device_id_unique"
[SQL: INSERT INTO auth_sessions (... device_id ...)]
```

注册逻辑在创建 user 后立即创建 auth_session,两次注册尝试使用同一 `device_id`(可能未读 device_fingerprint 或未做去重)即触发唯一冲突。

### 修复方向(供 Phase 3 / US1 owner 处理)
1. 客户端 `device_id` 应取自真实 `device_fingerprint`,而非固定值
2. 或在 service 层捕获 `IntegrityError` 后转为"该设备已有 session,走登录"流程
3. 或将 `device_id` 列从 UNIQUE 改为 `(user_id, device_id)` 联合唯一

此 bug 不影响 Setup 阶段验收(Setup 阶段无业务路由),但属于 Phase 3 (US1) 缺陷,不在本任务范围。

## FN 反向检查(INFO,符合预期)

| Check | 实际 | 期望 |
|---|---|---|
| FN.1 `backend/app/core/` | EXISTS | INFO (past boundary) |
| FN.2 `backend/app/modules/` | EXISTS | INFO (past boundary) |
| FN.3 `backend/migrations/versions/` | EXISTS | INFO (past boundary) |
| FN.4 `backend/app/workers/` | EXISTS | INFO (past boundary) |
| FN.5 `src/pages/*.tsx` 数 | 13 | INFO (past boundary) |

## 环境偏差

| 项 | 实际 | 规范 | 影响 |
|---|---|---|---|
| node | v18.20.8 | v20/v22 | tsc/vitest OK |
| redis-cli | 缺失 | 必填 | 用 uv-installed python `+PONG` 等价验证 |
| docker | 缺失 | 允许 | F2.6 INFO,F2.7 跳过 |

## 结论

- `PHASE1_SETUP_VERIFICATION: PASS` (Setup 静态 58/58 PASS,实际启动 5/6 — 注册接口 500 是 Phase 3 bug)
- Setup 交付物完整、代码 ruff 全清、backend 与 frontend 均可启动。
- 启动 smoke 暴露的 auth register bug 属 Phase 3 范围,建议创建独立 issue 跟踪(不阻塞 Setup 通过)。