# Contract: Cleanup Script CLI

**Date**: 2026-06-30 | **Spec**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md)

> Phase 1 — 数据清理脚本的 CLI 接口契约。

---

## Module

`backend.scripts.cleanup_resume_data` (entry point: `python -m app.scripts.cleanup_resume_data`)

## File Location

`backend/scripts/cleanup_resume_data.py`

## Interface

### Command Line Arguments

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--dry-run` | flag | optional | false | 仅打印将影响的行数；不实际删除 |
| `--execute` | flag | optional | false | 实际执行清理（与 `--dry-run` 互斥） |
| `--backup` | flag | optional | false | 执行前 dump 关键表到 docs/evidence/036-*/db-backup.sql |
| `--verify` | flag | optional | false | 仅查询行数；不动数据 |
| `--json` | flag | optional | false | JSON 输出模式 |
| `--output-dir` | string | optional | `docs/evidence/036-data-cleanup-<ts>` | evidence 目录 |

**互斥规则**：
- `--dry-run` 与 `--execute` 互斥（必须选其一）
- `--verify` 与 `--execute` 互斥
- `--backup` 仅在 `--execute` 时有效

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | 成功 |
| `1` | 操作失败（DB 连接 / 异常） |
| `2` | 参数错误 |
| `3` | 安全检查失败（生产环境 / 缺少必要确认） |

### Output Modes

#### Default (Human-Readable)

```
[2026-06-30 12:34:56] cleanup_resume_data starting...
[2026-06-30 12:34:56] environment detected: dev (safe to proceed)
[2026-06-30 12:34:56] mode: dry-run
[2026-06-30 12:34:56] row counts BEFORE cleanup:
  resume_branches: 12
  resumes_v2: 5
  resume_statistics_v2: 5
  resume_analysis_v2: 3
  outbox (resume-related): 28
[2026-06-30 12:34:56] dry-run: no changes made
[2026-06-30 12:34:56] would truncate 4 tables + clean outbox
[2026-06-30 12:34:56] exit code: 0
```

#### `--json`

```json
{
  "mode": "dry-run",
  "environment": "dev",
  "before": {
    "resume_branches": 12,
    "resumes_v2": 5,
    "resume_statistics_v2": 5,
    "resume_analysis_v2": 3,
    "outbox_resume": 28
  },
  "after": null,
  "backup_path": null,
  "duration_seconds": 0.3,
  "exit_code": 0
}
```

## Environment Detection

脚本 MUST 检测当前环境；仅在以下环境执行实际清理：
- `dev` / `development`
- `test` / `testing`

若环境是 `staging` / `prod` / 其他 → 退出码 3（拒绝执行）。

**检测方式**（优先级）：
1. 环境变量 `APP_ENV`
2. alembic 迁移表中的 `app.environment` GUC（per `asyncpg_set_local_caveat`）
3. DB name 前缀（如 `intercraft_dev` / `intercraft_test`）

## Safety Checks

执行 `--execute` 前 MUST 通过：

| Check | Failure Action |
|---|---|
| 环境是 dev/test | exit 3 |
| 当前进程不是 root user | exit 3（避免误删） |
| DB 连接有效 | exit 1 |
| 行数非负 | exit 1 |
| 用户已确认（`--yes` flag 或 stdin 输入 `yes`） | exit 3 |

## Side Effects

执行 `--execute` 后：

| 表 | Action | Reversibility |
|---|---|---|
| `resume_branches` | TRUNCATE RESTART IDENTITY CASCADE | ❌ 不可逆 |
| `resumes_v2` | TRUNCATE RESTART IDENTITY CASCADE | ❌ 不可逆 |
| `resume_statistics_v2` | CASCADE (跟随 resumes_v2) | ❌ 不可逆 |
| `resume_analysis_v2` | CASCADE (跟随 resumes_v2) | ❌ 不可逆 |
| `outbox` (resume-related) | DELETE | ❌ 不可逆 |

执行 `--backup` 时：

| File | Action |
|---|---|
| `<output-dir>/db-backup.sql` | CREATE — `pg_dump --data-only --table=resume_branches --table=resumes_v2 --table=resume_statistics_v2 --table=resume_analysis_v2` |

执行后无论成功/失败 MUST 写：

| File | Action |
|---|---|
| `<output-dir>/cleanup.log` | CREATE — 完整 stdout/stderr |
| `<output-dir>/summary.json` | CREATE — 行数对比 + 退出码 + 时长 |

## Test Contract

**测试文件**：`backend/tests/scripts/test_cleanup_resume_data.py`

**必测场景**：
1. `--dry-run` 模式：行数报告准确；DB 未变更
2. `--verify` 模式：仅查询；无副作用
3. `--execute` 在 dev 环境：清理成功；行数 = 0
4. `--execute` 在生产环境：exit 3；无副作用
5. `--backup` + `--execute`：backup 文件存在且非空
6. `--json` 输出：合法 JSON；字段齐全
7. 退出码覆盖：0 / 1 / 2 / 3 各场景

## Dependencies

- `sqlalchemy` 2.0
- `psycopg` 或 `asyncpg`（沿用项目）
- `pg_dump` (system CLI) — 仅 `--backup` 需要

## Notes

- 脚本 MUST NOT 自动调用 alembic（避免循环依赖）
- alembic 迁移 036 是幂等的；可单独运行；与 CLI 互补
- 脚本与迁移共享同一个 `cleanup_resume_data.py` 模块的核心函数（避免逻辑分裂）

---

## References

- 036 spec FR-009~FR-012: 数据清理
- 036 research Decision 1: alembic + CLI 双轨
- 036 data-model.md: 表结构与清理方式
- Constitution II: CLI Interface 原则