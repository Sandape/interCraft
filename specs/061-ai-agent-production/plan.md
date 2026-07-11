# Implementation Plan: 全域 AI / Agent 生产级升级

**Branch**: `master` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/061-ai-agent-production/spec.md`

## Summary

REQ-061 将模拟面试、简历派生与建议、个人画像、通用/错题教练、微信 Agent、主动研究及其他模型调用，从各自的 Demo 任务状态和直接模型调用，升级为两个相互关联但职责独立的生产级模块：

1. `ai_runtime` 作为所有 AI 能力的统一控制面与审计事实源，管理任务、执行、阶段、外部调用尝试、里程碑、状态事件、取消/恢复/重试/重跑、模型策略快照、证据回放和能力适配。
2. `ai_metering` 作为体验点数、调用用量和真实可变成本的账务事实源，管理每日 2,000 点配置化发放、分桶/到期、预留/结算/释放/补偿、成本率、供应商尝试、成本调整、分摊和对账。

采用“统一事实层 + 能力适配器 + 分能力灰度切换”，保留各能力现有领域模型作为业务详情，不把普通生产力任务或微信专用任务表直接扩成全域模型。强制审计、任务终态与点数结算在同一可靠数据库边界内持久化；派生指标、在线评测、OTel、LangSmith 和运营读模型通过持久 outbox 与 ARQ 幂等投影。OTel 继续承担 trace/log/metric，LangSmith 继续承担受隐私策略控制的 AI 调试和评测实验，但二者都不是任务或账务事实源。现有管理后台四个工作区复用信息架构并改接真实投影，新增完整任务时间线、只读证据回放及 Bad Case 影响/审核闭环。商业支付、人民币价格、充值与订单履约继续归属已拆分的 REQ-062，不在本计划实现。

## Technical Context

**Language/Version**: Python 3.11+；TypeScript 5.6；React 18.3

**Resolved Dependencies**: `backend/uv.lock` / 当前 backend venv：FastAPI 0.116.2、Pydantic 2.13.4、SQLAlchemy 2.0.50、Redis 5.3.1、ARQ 0.26.3、LangGraph 0.2.28、`langgraph-checkpoint-postgres` 1.0.9、LangSmith 0.8.15、OpenTelemetry API 1.43.0；前端以根 `package-lock.json` 为准

**Dependency Support**: FastAPI/Pydantic/SQLAlchemy 按锁文件受控；LangGraph 0.2.28 未出现在[官方现行支持表](https://docs.langchain.com/oss/python/release-policy)中，登记为有期限 dependency deviation。若供应商不能书面确认支持，生产目标固定为 PyPI 2026-07-10 发布的 `langgraph==1.2.9` 与 `langgraph-checkpoint-postgres==3.1.0`，T183 必须验证兼容后更新 lockfile

**Storage**: PostgreSQL 为任务、审计、点数和成本的权威事实源；Redis 仅承担队列、短期协调、限流和缓存；加密对象/本地证据存储仅保存按策略授权的完整内容快照和评测产物

**Testing**: pytest（unit/integration/contract/eval）、Vitest、Playwright；PostgreSQL/Redis 故障注入、账本守恒与幂等性质测试、OpenAPI/CLI/能力适配器契约测试、离线评测与灰度门禁

**Target Platform**: Linux 容器化 Web/API 与异步 worker；桌面及移动浏览器；现有微信 iLink 渠道

**Project Type**: React SPA + FastAPI Web service + ARQ workers + Typer CLI

**Performance Goals**: 任务受理与取消确认 P95 ≤ 2 秒；普通取消终态 P95 ≤ 30 秒；短对话 P95 ≤ 15 秒；面试单轮评分 P95 ≤ 20 秒；简历分析 P95 ≤ 90 秒；简历派生 P95 ≤ 3 分钟；研究报告 P95 ≤ 10 分钟；任务终态后 5 分钟内结算 ≥ 99.9%；点数事件和估算成本 5 分钟内可查 ≥ 99.9%

**Constraints**: 控制面月可用性 ≥ 99.9%；已受理任务、预留和账本事件零数据丢失；重大故障 30 分钟内恢复查询/控制；所有点数与外部调用尝试 100% 记录、不可采样；OTel/LangSmith 故障不得丢强制事实或重复业务执行；管理生产数据禁止 seed/mock/in-memory fallback；审计默认仅保留脱敏元数据；内测收入固定为 0；支付能力完全排除

**Scale/Scope**: 首个生产容量包络按 10,000 注册用户、2,000 DAU、100 个并行 AI 执行、任务受理峰值 20 次/秒、外部尝试峰值 100 次/秒、任务/事件/账本合计 1,000 万行/月规划；该包络用于索引、分区、压测和告警基线，不构成商业用户上限，超过 70% 时必须重新容量评审

**Risk Classification**: 最高 R3；任务状态、Agent 写工具、用户简历、租户隔离、点数/成本账本和模型策略均包含关键授权、隐私或不可逆事实。服务档位、故事优先级和事故 P0/P1 与该 risk class 分开管理

**Operation Risk Matrix**: R0 = owner-scoped 只读任务/点数查询与无写入纯计算；R1 = 用户预期内可撤销草稿写入及既有处理边界内的预算模型调用；R2 = 搜索/渠道/可逆 Agent 外部写入、向模型发送敏感简历内容、批处理和长时自主执行；R3 = 不可逆工具写入、跨租户/权限动作、点数结算及会改变高影响发布策略的操作。单次 operation 同时命中时取最高等级

**Execution Model**: PostgreSQL 原子提交 task/execution/reservation/event/dispatch intent；幂等 dispatcher 投递 ARQ，reconciler 重投 stranded intent；外部副作用经绑定当前 claim generation 与 authorization receipt 的 durable effect intent 发出，只有当前 fence 可采纳结果；LangGraph 只负责 execution 内编排

**AI/Agent State**: 类型化 state + PostgreSQL checkpointer；启用严格 msgpack allowlist；execution/thread/flow/payload version 均持久化；每次发布维护 live-version/retention matrix、decoder/upcaster 与逐 live version resume 证据，N-1 是 rolling 最低覆盖，矩阵外执行只能 drain/migrate/quarantine 并产生可见结果

**External Dependencies**: 模型、embedding、搜索、微信渠道和 Agent tool 全部经集中 adapter；每个 operation 定义 timeout、retry class、budget、provider idempotency 或 unknown-result reconciliation，不允许 graph node/router 直调 SDK

**Observability & Privacy**: 使用 `root_task_id → task_id → execution_id → stage_attempt_id → external_attempt_id` 关联；强制事实不可采样，OTel/LangSmith 仅为脱敏投影；逐 store/provider/derived-copy 的字段、owner、隔离、加密、访问、保留与 provenance 删除传播见 [data-model.md](./data-model.md#10-retention-and-deletion)

**Migration & Rollout**: Alembic/checkpointer setup 由 pre-deploy job 执行，并以 PostgreSQL advisory lock + migration ledger 强制互斥；backfill 幂等、可恢复。expand 与 contract 分属不同 rolling-compatible release，只有证明旧 binary/checkpoint/interrupt/queued payload 不再引用旧 schema 后才能 contract；不在 API/worker lifespan 并发 migration

**Operational Release Unit**: `ai_runtime` + `ai_metering` 共享控制面为基础 release unit；各 capability 继承基础 SLO/runbook，存在独立 R2/R3 failure mode 时增加 capability-specific gate

## Constitution Check

*SCREEN: Phase 0 前已完成；Phase 1 后已复检。仅 LangGraph 支持窗口需要有期限 deviation。*

| Gate | Applicability / inherited control | Pre-screen | Post-design | Evidence |
|---|---|---|---|---|
| Boundaries & composition roots | 全部后端入口；AI Runtime owner | CLEAR | PASS | `ai_runtime`/`ai_metering` 公开 adapter contract；API/ARQ/CLI/graph runner 分入口装配共享 `ExecutionContext` |
| Typed contracts & authorization | 全部 API/worker/tool；Auth owner | CLEAR | PASS | 三份 OpenAPI、Pydantic schema、problem details、RLS/owner 与执行时授权复验 |
| Async, transactions & process isolation | API/worker/graph；Platform owner | RESEARCH REQUIRED | PASS | session-per-task、外部 I/O 不持事务、lifespan 资源、进程内状态非事实和单实例 migration 已进入设计/任务 |
| Durable dispatch & concurrency ownership | 全部长任务；AI Runtime owner | RESEARCH REQUIRED | PASS | task+dispatch intent 同事务、幂等 dispatcher/reconciler、每次权威写/effect intent/结果采纳 fence CAS、admission/dead-letter |
| LangGraph state & compatibility | 全部 graph capability；AI Runtime owner | RESEARCH REQUIRED | PASS | 类型化 state/checkpointer、严格反序列化、live-version matrix/upcaster、逐 live version resume、drain/migrate/quarantine 门禁 |
| Agent safety & data lifecycle | 逐操作 R0–R3；Security/Data owner | CLEAR | PASS | 不可变 authorization receipt、fenced effect intent、未知结果对账、RLS、逐 store 生命周期与 provenance 删除传播 |
| Test-first & evaluation | R3；Quality owner | CLEAR | PASS | unit/property/contract/integration/E2E/fault、离线/在线 eval、校准和灰度阈值均有任务入口 |
| Observability, release & dependency support | 控制面 + capability 继承；Platform owner | RESEARCH REQUIRED | APPROVED DEVIATION | 强制事实与 OTel/LangSmith 分离，SLO/容量/回滚完整；仅 LangGraph 0.2.28 支持状态未证实 |

## Deviation Register

| Control / Clause | Scope | Risk | Supplier Support Evidence / Status | Concrete Migration Target | Why Needed | Simpler Alternative Rejected | Compensating Controls | Owner | Approver | Expiry | Removal Task |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Technology & Runtime Constraints / dependency support | REQ-061 LangGraph runtime/checkpointer | 0.2.28 未列入官方当前支持窗口，安全修复与当前文档兼容性无法证实 | 已迁移至 `langgraph==1.2.9` + `langgraph-checkpoint-postgres==3.1.0`，均在供应商 ACTIVE 窗口 | `langgraph==1.2.9` + `langgraph-checkpoint-postgres==3.1.0`，更新 `backend/uv.lock` | 现有 graph/checkpoint 依赖 0.2 API，未验证直接升级会破坏存量 state 与 interrupt | 无审查升级会把依赖风险转化为生产恢复风险 | 固定 0.2.28 与 tagged docs；禁止采用仅新版 API；严格 checkpoint allowlist；逐 live-version/N-1/故障恢复测试；生产前关闭 deviation | AI Runtime technical owner | Project owner | 2026-09-30 | T183 ✅ CLOSED |

## Project Structure

### Documentation (this feature)

```text
specs/061-ai-agent-production/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ai-runtime.openapi.yaml
│   ├── ai-metering.openapi.yaml
│   ├── ai-operations.openapi.yaml
│   ├── capability-adapter.md
│   ├── event-catalog.md
│   └── cli.md
└── tasks.md                    # 仅由后续 /speckit-tasks 创建
```

### Source Code (repository root)

```text
backend/app/
├── modules/
│   ├── ai_runtime/             # 新：全域 AI 任务、执行、事件、策略快照与证据
│   │   ├── adapters/           # 面试、简历、画像、教练、Agent、研究适配器
│   │   ├── engines/            # LangGraph、工具循环和后台流水线的统一执行接口
│   │   ├── provider_gateway/   # 每次模型/搜索/工具尝试、路由、重试、熔断
│   │   ├── recovery/           # claim 续租、可信恢复、对账、dead-letter
│   │   ├── projections/        # 管理读模型、OTel/LangSmith 持久投递与积压状态
│   │   ├── api.py
│   │   ├── cli.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── state_machine.py
│   │   └── README.md
│   ├── ai_metering/            # 新：点数、用量、成本与对账
│   │   ├── points/             # 分桶、预留、结算、补偿和余额投影
│   │   ├── usage_cost/         # 用量、成本率/汇率、分摊、冲正
│   │   ├── reconciliation/     # 日结、供应商用量/月账单、数据质量门禁
│   │   ├── api.py
│   │   ├── cli.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── README.md
│   ├── agent/                  # 复用微信 Agent 的租约、幂等、outbox 和证据范式
│   ├── interviews/
│   ├── resume_intelligence/
│   ├── resume_derive/
│   ├── badcases/
│   │   ├── impact.py           # 扩展：任务/用户/版本/点数/成本影响范围
│   │   └── ...                 # 保留 FSM/审核动作/回归候选，补齐管理契约
│   ├── agent_observability/    # 改为读取真实事实/投影，移除生产 seed/demo
│   └── telemetry_contracts/
├── agents/llm_client.py        # 集中调用入口接入 execution/attempt context，不再直接改月 token
├── eval/                       # 扩充能力覆盖、校准和灰度比较
├── observability/              # 关联 request/task/execution/attempt trace
└── workers/                    # 发放、恢复、结算、投影、评测、对账任务

backend/migrations/versions/    # 从当前单一 head 0057 顺序新增 Alembic 迁移
backend/tests/
├── unit/
├── integration/
├── contract/
└── eval/

src/
├── api/
│   ├── ai-runtime.ts
│   └── ai-metering.ts
├── types/
│   ├── ai-runtime.ts
│   └── ai-metering.ts
├── components/ai/              # 统一状态、里程碑、失败操作、点数摘要
├── pages/                      # 全局 AI 任务中心、点数明细及现有能力接入
└── admin/
    ├── pages/AIOperations.tsx  # 真实联合指标与异常下钻
    ├── pages/LogsAndTraces.tsx # 任务搜索、全流程时间线、证据回放
    ├── pages/IncidentsBadcases.tsx # Bad Case 列表、影响范围、审核闭环
    └── pages/Governance.tsx    # 访问审计、策略/成本率/override 治理

tests/e2e/                      # 用户控制面、跨页恢复、账务与运营下钻验收
```

**Structure Decision**: 沿用现有单仓库 Web 应用结构。新增两个独立后端领域模块，不建立新服务；统一事实通过服务接口和 outbox 被现有能力、运营读模型与评测消费。前端以共享 API/type/component 接入现有页面，避免各能力继续维护不同的状态与扣费语义。

## Observability and LangSmith Compatibility

| Layer | Authority and responsibility | Failure behavior |
|---|---|---|
| PostgreSQL runtime/metering facts | 任务、execution、事件、外部尝试、里程碑、点数、成本、反馈、评测和 Bad Case 的权威事实 | 强制事实不能提交时停止对应终态/结算并进入结果确认或停止受理 |
| Durable projection outbox | 每个事实到管理读模型、OTel、LangSmith 的目标、尝试、确认位置、最后错误与最后成功时间 | 幂等重试；积压可见；不得重新运行模型/工具或重复账务事件 |
| OpenTelemetry | HTTP→worker→engine→provider/tool 的 trace、结构化日志、黄金信号和告警；span 携带 task/execution/attempt 关联 | 可采样的观测出口失败不影响已持久业务事实；恢复后补投影适用记录 |
| LangSmith | 经目的地策略授权的 Prompt/输出、dataset、experiment、feedback 和调试深链 | 可选；关闭、无授权或不可用时本地评测、账务和证据回放仍工作 |
| Admin read models | 面向运营的任务时间线、Bad Case、指标、点数/成本和审计查询 | 不可用时显示新鲜度、覆盖率、最后成功与重试，不使用 seed/demo 替代 |

统一 correlation contract 使用 `root_task_id → task_id → execution_id → stage_attempt_id → external_attempt_id`，再关联 milestone、point/cost、feedback/evaluation/badcase。OTel trace/span 和 LangSmith run 只携带关联标识与允许的版本/摘要；高基数 ID 不进入无界 metric label。现有 `observability`、`agent_observability` 与 `telemetry_contracts` 不再各自产生互相竞争的终态/费用事实：前者保留 instrumentation/read-model 职责，后者保留纯契约、指标与兼容投影职责。

迁移前的 `ai_messages`、`ai_invocation_records` 和 demo observability 数据只能标记为 `legacy_partial`/unknown；不能伪造重试级记录、把 unknown 记为 0 或追溯扣点。当前会创建新 trace 的“replay”必须改名为 re-execution；新的 evidence replay 只读事件，契约直接断言 provider/tool/business-write/execution/ledger 新增量均为 0。

## Admin Inspection and Bad Case Workspace

管理后台保留既有信息架构，并约束为同一事实源上的四个视角：

| Workspace | Primary questions | Required drilldown |
|---|---|---|
| AI 运营 | 哪些能力、档位、策略、发布批次的效果/稳定性/延迟/点数/成本异常？ | 聚合异常 → 任务集合 → 单任务时间线 |
| 日志与链路 | 某次 AI 使用从受理到结果、费用发生了什么？ | task → executions → stages → all external attempts → milestones → points/costs → feedback/eval/badcase |
| 事件与差例 | 每个 Bad Case 影响谁、为什么、如何处理、是否完成回归和用户处置？ | badcase → impacts/tasks/feedback/versions → review actions → fix/eval/point handling/notification |
| 治理与审计 | 谁发布策略/成本率、查看受限内容、补偿、override 或关闭 Bad Case？ | audit event → actor/reason/scope/version/evidence |

用户可见任务 API 和管理 API 使用同一 canonical IDs/status/settlement，不允许页面自行推断。管理端契约必须包含：

- 游标分页的 AI 任务列表及 task detail；
- 可按类型分页的完整 timeline 和全部外部尝试；
- 点数/成本双向下钻、版本/反馈/评测/Incident/Bad Case 关联；
- read-only evidence replay；
- Bad Case 列表、详情、影响范围、审核动作及版本化幂等 mutation；
- 每个响应的 `fresh_at`、coverage、unknown count、source；
- capability-based RBAC，至少区分 support、AI ops、quality/badcase、cost、model policy、restricted-content privacy 和 audit export。

Bad Case 继续复用现有 `modules/badcases` FSM、review action 和 golden candidate 流程，但先收敛当前 ORM/repository/migration 漂移，再扩展 durable impact links。新增管理 facade 以加法方式提供稳定契约，旧 `/api/v1/badcases` 在兼容窗口保留；前端只迁移到一个 canonical management contract，不长期维护两套字段语义。

## Delivery Strategy

1. **事实基础与契约**：建立 runtime/metering 表、状态机、不可变事件、CLI 与契约测试；此时不改变用户行为。
2. **影子采集**：集中 LLM client 和能力适配器双写任务/调用/用量事实，旧领域状态仍对用户生效；每日比较缺失、孤儿、重复和金额差异。
3. **发布安全基础**：在任何生产切换前完成风险分级授权、隐私清理、恢复/故障注入、评测校准、SLO/runbook、容量/回滚演练，并关闭 LangGraph 支持窗口 deviation。
4. **体验点数启用**：发布 Pro“新用户体验”、每日配置化发放、余额与明细；先只展示与预留演练，再启用余额门禁。
5. **分能力切换**：按简历建议/派生、面试、教练/画像/研究、微信 Agent 的独立灰度批次，将用户状态、控制操作和里程碑结算切到统一事实源；同时验证评测、OTel/LangSmith、出口故障补投影和 capability-specific stop gate，每批具备回退到旧读路径但不回滚账本的方案。
6. **运营闭环与遗留收敛**：管理工作区改用真实读模型并接入任务、Bad Case、评测、熔断、预算和供应商对账；停止 `users.monthly_token_used` 权威写入，移除生产 seed/demo、in-memory fallback 与重复扣费逻辑。删除字段或旧接口须另走兼容性/迁移评审。

每一阶段只有在覆盖率、账本守恒、状态一致性、RLS、故障恢复和回滚演练达到 [quickstart.md](./quickstart.md) 对应门槛后才可扩量。任何账本不平衡、强制证据缺失、P0/P1 安全回归或未知成本率都会阻止继续灰度。
