# AI Runtime（AI 任务控制面）

REQ-061 全域 AI 任务、执行、事件、恢复与投影的统一控制面。`ai_runtime` 是 AI 生命周期状态与审计证据的**事实源**；各业务能力（面试、简历、研究等）通过 **adapter** 接入，领域表仍由能力模块自有。

## 职责边界

| 归属 `ai_runtime` | 不归 `ai_runtime` |
|---|---|
| `AITask` / `AIExecution` / 不可变事件 / 里程碑 | 面试回合、简历段落等领域详情表 |
| 能力适配器注册与验收信封 | 能力业务逻辑与 UI |
| 恢复、死信、外部效应围栏 | 点数账务（见 `ai_metering`） |
| 投影投递状态与重试 | OTel/LangSmith **内容**（仅为投影，非事实） |

**OTel / LangSmith 是投影（projection），不是事实源。** 权威状态以 PostgreSQL 中的 runtime 表与追加事件为准；可观测性导出可滞后、可重建，不得反向驱动状态机。

## 子包（规划中）

- `adapters/` — 能力验收信封、里程碑与版本快照
- `provider_gateway/` — 模型策略、路由、熔断与外部调用围栏
- `recovery/` — 派发意图投递、claim 围栏、死信与对账
- `projections/` — 运营读模型、OTel、LangSmith 投递
- `authorization/` — 不可变授权回执与外部效应意图
- `privacy/` — 脱敏、删除编排与 provenance 策略
- `engines/` — 与框架无关的执行上下文工厂

## 公开面（当前）

- `MODULE_NAME`, `VERSION` — 自 `app.modules.ai_runtime` 导出
- HTTP 用户面：`/api/v1/ai-tasks*`（控制/恢复）
- 运营检查：`/api/v1/admin-console/ai/tasks*`（US12 搜索/详情/时间线/尝试/只读回放）
- CLI — `python -m app.modules.ai_runtime.cli`

## 投影 CLI

```bash
uv run python -m app.modules.ai_runtime.cli projection-status --destination otel --json
uv run python -m app.modules.ai_runtime.cli projection-retry --delivery-id ID --reason catchup --idempotency-key k1 --json
uv run python -m app.modules.ai_runtime.cli shadow-compare --fixture path/to/pairs.json --dry-run --json
```

投影命令**不得**调用 engines/providers/tools/metering。

## 迁移 / 回滚

- 影子捕获：`migration.py` + `shadow-compare` CLI；`legacy_partial` 幂等戳记，不伪造用量/重试/扣点。
- 遗留 `monthly_token_used` 写入：`AI_LEGACY_MONTHLY_TOKEN_WRITES_FROZEN=1` 后冻结（T169）。
- LangGraph 升级（T183）仍为发布 blocker，见 `docs/evidence/061-ai-agent-production/langgraph-support-migration.md`。

## 隐私

运营读模型默认脱敏；受限揭示需 reason + TTL，并写审计。OTel/LangSmith 仅为投影。

完整 API / 服务将在后续任务（T013+）落地；当前为**空壳**，不改变既有生产行为。

## CLI 示例

```bash
# 任务只读检查（当前返回空桩）
uv run python -m app.modules.ai_runtime.cli task-show TASK_ID --json
uv run python -m app.modules.ai_runtime.cli task-timeline TASK_ID --json

# 证据回放（只读；不得创建 provider/tool/ledger 事实）
uv run python -m app.modules.ai_runtime.cli evidence-replay TASK_ID --json

# 恢复扫描（默认 dry-run）
uv run python -m app.modules.ai_runtime.cli recover-scan --older-than 60 --dry-run --json

# 适配器与策略
uv run python -m app.modules.ai_runtime.cli adapter-list --status active --json
uv run python -m app.modules.ai_runtime.cli policy-show resume_intelligence analysis standard --json

# 投影状态（非事实）
uv run python -m app.modules.ai_runtime.cli projection-status --destination otel --json
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

- CLI：`specs/061-ai-agent-production/contracts/cli.md`（Runtime CLI）
- 数据模型与 API：同 feature 下 `data-model.md`、`contracts/`
