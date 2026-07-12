# AI Metering（体验点数 / 用量 / 成本账务）

REQ-061 体验点数、调用用量与真实可变成本的**账务事实源**。`ai_metering` 管理每日配置化发放（初始 2,000 点）、分桶与到期、预留/结算/释放/补偿、成本率、供应商尝试、成本调整、分摊与对账。

## 职责边界

| 归属 `ai_metering` | 不归 `ai_metering` |
|---|---|
| 点数账户、分桶、预留、追加式账本事件 | AI 任务状态机（见 `ai_runtime`） |
| 尝试用量与可变成本事实、费率版本 | 商业支付、人民币定价、充值与订单（**REQ-062**，本模块不实现） |
| 日终/发票对账、孤儿成本检测 | OTel/LangSmith 导出内容（仅为投影） |

**账本事件为追加式（append-only）事实**；不得通过 CLI 或 API 破坏性修改历史分录。余额与报表为可重建投影。

**业务日**一律按 `Asia/Shanghai` 日历日解释（如 `grant-ensure`、`ledger-check`、`reconcile-daily` 的 `--business-date`）。

## 子包（规划中）

- `points/` — 发放配置、报价、预留、结算/释放/退款/补偿语义命令
- `usage_cost/` — 尝试用量/成本记录、有效费率、FX、分摊与未知费率门禁
- `reconciliation/` — 日终与发票对账、投影重建校验、问题单生命周期

## 公开面（当前）

- `MODULE_NAME`, `VERSION` — 自 `app.modules.ai_metering` 导出
- CLI — `python -m app.modules.ai_metering.cli`（亦将挂载至根 `intercraft` Typer）

## 迁移 / 回滚 / Runbook（REQ-061）

- 账本追加式；禁止 CLI/API 改写历史分录。
- `AI_LEGACY_MONTHLY_TOKEN_WRITES_FROZEN=1`：冻结遗留月度 token 计数写入（点数账本成为权威）。
- 日终对账：`ledger-check` / `orphan-cost-list` / `reconcile-daily`（见 CLI）。
- 回滚：保留兼容字段，恢复旧读路径时不得双重扣点。

完整 ORM / API / 迁移将在后续任务（T014+）落地；当前为**空壳**，不改变既有生产行为。

## CLI 示例

```bash
# 只读检查（当前返回空桩，退出码 0）
uv run python -m app.modules.ai_metering.cli account-show USER_ID --json
uv run python -m app.modules.ai_metering.cli ledger-show USER_ID --from 2026-07-01 --to 2026-07-11 --json
uv run python -m app.modules.ai_metering.cli grant-config-list --json
uv run python -m app.modules.ai_metering.cli ledger-check --business-date 2026-07-11 --json
uv run python -m app.modules.ai_metering.cli cost-rate-list --provider openai --json
uv run python -m app.modules.ai_metering.cli orphan-cost-list --from 2026-07-01T00:00:00+08:00 --to 2026-07-11T23:59:59+08:00 --json

# 投影重建（默认 dry-run，不写入）
uv run python -m app.modules.ai_metering.cli projection-rebuild --scope USER_ID --dry-run --json

# 变更类命令（实现完成前返回 not implemented，退出码 1）
uv run python -m app.modules.ai_metering.cli grant-config-create \
    --points 2000 --effective-at 2026-07-11T00:00:00+08:00 \
    --reason "initial grant table" --idempotency-key grant-v1 --json
uv run python -m app.modules.ai_metering.cli grant-ensure USER_ID \
    --business-date 2026-07-11 --reason "daily grant" --idempotency-key ensure-1 --json
```

变更类命令必须提供 `--reason` 与 `--idempotency-key`；缺失时退出码为 `2`。

## 退出码

| 码 | 含义 |
|---:|---|
| 0 | 成功 |
| 1 | 运行失败或未实现 |
| 2 | 参数无效 |
| 3 | 策略/授权拒绝 |

## 契约

- CLI：`specs/061-ai-agent-production/contracts/cli.md`（Metering CLI）
- 数据模型与 API：同 feature 下 `data-model.md`、`contracts/ai-metering.openapi.yaml`
