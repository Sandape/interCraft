<!--
  Sync Impact Report
  ==================
  Version change: 2.0.0 → 2.1.0
  Bump rationale: MINOR — 保留七项核心原则，新增风险/适用性语言、框架中立
  composition root、事务与并发所有权、耐久 dispatch/fencing、checkpoint 兼容、
  全存储隐私生命周期和依赖支持窗口等实质性治理要求；反方复核后进一步封闭
  effect fencing、跨版本恢复矩阵、迁移互斥与逐操作风险分级。
  Modified principles:
    - I. 明确边界与依赖方向 → 增加多入口 composition root 与框架中立上下文
    - II. 类型化、契约优先的 FastAPI → 限定 FastAPI DI 只属于 HTTP 边界
    - III. 正确的异步与资源生命周期 → 增加 AsyncSession 并发、事务、进程隔离与耐久受理
    - IV. 可持久、可恢复的 LangGraph → 增加 fencing、并发所有权与存量 checkpoint 兼容
    - V. 安全且由人掌控的 Agent 行为 → 改为风险分级确认并消除确认后的 TOCTOU
    - VI. 测试优先与评测门禁 → 增加等价前置证据与风险分级评测，移除普遍双人审批
    - VII. 可观测、可靠且可运维 → 允许服务级控制继承，避免逐能力文档占位
  Added sections:
    - Normative Language, Applicability & Risk
  Removed requirements:
    - 所有生产能力各自维护完整 SLO/runbook/灰度包；改为按 operational release unit 继承或细化。
    - 所有写入和常规成本均逐次人工确认；改为按 R0–R3 风险分级授权。
    - 所有 schema migration 必须机械可 downgrade；改为 expand/contract + 安全 backout/roll-forward。
    - 所有行为变更都保留独立 RED 制品；改为风险适配的 RED 或等价前置证据。
  Templates/artifacts requiring updates:
    - .specify/templates/plan-template.md                       ✅ updated
    - .specify/templates/spec-template.md                       ✅ updated
    - .specify/templates/tasks-template.md                      ✅ updated
    - specs/061-ai-agent-production/plan.md                     ✅ updated
    - specs/061-ai-agent-production/spec.md                     ✅ governance profile updated
    - specs/061-ai-agent-production/tasks.md                    ✅ updated
    - specs/061-ai-agent-production/data-model.md               ✅ updated (dispatch intent, lifecycle, compatibility)
    - AGENTS.md / README.md / CLAUDE.md                         ✅ reviewed; no principle sync required
    - .specify/templates/commands/*.md                          ✅ directory absent; no action
  Deferred items:
    - LangGraph 0.2.28 support status is not listed by the current vendor policy; migration must be
      tracked as a time-bounded dependency deviation before production release. REQ-061 records
      `langgraph==1.2.9` + `langgraph-checkpoint-postgres==3.1.0` as the concrete fallback target.
-->

# InterCraft Constitution

## Normative Language, Applicability & Risk

本文件中的 `MUST`、`MUST NOT`、必须、不得、只能和一律均为强制要求；`SHOULD`、
应该和推荐表示默认要求，偏离时必须在 plan 中写明理由；`MAY` 和可以表示可选项。
Rationale 与示例是非规范性说明，不能降低强制要求。

每个受治理 operation/effect MUST 单独分类；feature 在 spec 中声明最高 `risk_class`
以及逐操作风险矩阵，并与故事优先级、服务档位和事故等级分开。多个条件同时命中时，
最高等级生效，低等级描述不得覆盖高等级条件：

- **R0（低）** — 只读且不跨越新的信任边界，或无外部副作用、无持久写入的纯确定性
  计算；“确定性”本身不能降低写入风险。
- **R1（中）** — 不命中 R2/R3 的、用户预期内常规可逆写入，或在既有处理边界内、受
  预算约束的标准模型调用。
- **R2（高）** — 不命中 R3 的外部副作用、向新处理方披露敏感数据、批量修改、显著
  费用或长时自主执行。
- **R3（关键）** — 不可逆写入、权限/租户边界变化、财务结算或高影响自动决策。

控制可以从所属 service/release unit 继承；继承证据和 owner 必须明确。标记 `N/A` 时
必须写出适用性理由。安全、租户隔离、审计真实性、R3 人工授权和 stale worker
隔离不得标记 `N/A`，也不得通过 deviation 豁免。

## Core Principles

### I. 明确边界与依赖方向

系统 MUST 以领域能力划分模块，并保持单向依赖：protocol adapter 负责输入输出映射；
application service 负责用例、事务和授权编排；domain 层负责业务不变量；repository、
模型供应商、工具和队列属于可替换 adapter。LangGraph 只编排有状态、多步骤、可能
中断的工作流，不承载 HTTP 细节、数据库会话生命周期或业务事实的唯一副本。

- 模块只能通过公开的类型化接口协作，MUST NOT 导入其他模块的内部 repository、
  ORM model、graph node 或私有 prompt。
- router 和 graph node MUST 保持薄层；确定性规则必须位于可独立测试的
  domain/application 代码中，不能复制到 prompt 或路由分支。
- application/domain 代码 MUST 与 FastAPI、ARQ、CLI 和 LangGraph runner 解耦。
  HTTP、worker、CLI 和 graph runner 各自拥有 composition root 与生命周期，并通过
  共享的类型化 factory/port 构造服务和 `ExecutionContext`。
- 简单、确定、单步的逻辑 MUST 使用普通函数或 application service；只有确实需要
  状态机、分支、并行、中断或恢复时才使用 LangGraph。
- 新抽象必须解决已出现的边界、复用或替换问题；仅为组织形式而增加的层级不得进入设计。

Rationale: 框架是适配层和编排工具，不是领域模型。框架中立的核心才能让 API、
worker、CLI 和图运行共享同一业务语义而不伪造依赖注入。

### II. 类型化、契约优先的 FastAPI

所有外部和跨模块接口 MUST 先定义类型化契约，再实现行为。FastAPI 请求、响应、
错误和事件使用 Pydantic v2 模型与明确状态码；公开 HTTP 契约必须进入 OpenAPI，
并由契约测试保护。

- 输入、输出和持久化模型 MUST 按职责分离；响应必须使用显式返回类型或
  `response_model` 验证并过滤字段，严禁返回 ORM 对象或含密钥/内部字段的无约束字典。
- FastAPI dependency injection 只属于 HTTP composition root。数据库 unit of work、
  当前用户/租户、授权策略、request context 与 application service MUST 在 HTTP
  边界通过依赖链提供；非 HTTP 入口使用其自己的 composition root，不得导入 router
  dependency 作为应用接口。
- 身份认证不等于授权。每个受保护操作 MUST 在入口与资源对象范围执行授权；
  worker/tool 在产生副作用前 MUST 使用当前 `ExecutionContext` 再次校验授权和归属。
- 公开契约的破坏性变更 MUST 版本化，提供迁移说明与兼容窗口；实现不得先于契约合并。
- 错误响应 MUST 使用稳定、机器可判定的错误码，并区分校验、权限、冲突、限流、
  依赖失败与内部错误；不得泄露堆栈或供应商敏感信息。

Rationale: FastAPI 的类型、依赖注入与 OpenAPI 能统一 HTTP 运行时验证、安全过滤、
文档和测试，但不能替代其他执行入口的 composition root。

### III. 正确的异步与资源生命周期

异步代码 MUST 保持 event loop 非阻塞。可等待的网络/数据库 I/O 使用兼容的 async
调用；阻塞 I/O 与 CPU 密集工作必须显式移交线程、进程或 worker。

- 数据库连接池、HTTP/模型客户端、checkpointer、Redis 等资源 MUST 由对应入口的
  lifespan 创建并可靠关闭；不得在模块导入时连接，也不得无必要地逐请求创建昂贵客户端。
- 多个 FastAPI/ARQ worker 不共享内存。进程内锁、任务表、取消标志、cache 或 limiter
  只能优化本进程，MUST NOT 承担跨进程正确性；每进程资源预算必须汇总进容量计算。
- 一个 SQLAlchemy `AsyncSession`/unit of work MUST 只属于一个 request 或并发 task，
  不得被并行 graph node 或 coroutine 共享。事务必须短且显式；模型、搜索、工具等
  外部 I/O 必须位于活动事务、数据库连接和锁之外。
- commit 只能发布满足业务不变量的状态或事务性 intent/outbox；不得为释放连接而提交
  半成品。无法形成有效状态时必须 rollback。
- 外部调用 MUST 有超时、取消传播和有界并发。重试只适用于已分类的瞬时错误，并采用
  退避与抖动；非幂等写入或结果未知的调用不得自动重放。
- 长时 AI/Agent 请求的“已受理”只在权威数据库原子提交 task、execution 与 dispatch
  intent 后成立。Redis/ARQ enqueue 成功本身不是耐久受理证据；幂等 dispatcher 与
  reconciler 必须能够重投 stranded intent。
- 队列、并发和等待时间必须有界；过载时 MUST 执行 admission/backpressure，并优先保留
  查询、取消和恢复控制面。FastAPI `BackgroundTasks` 或进程内 fire-and-forget 不得
  充当生产级耐久任务队列。

Rationale: 正确区分并发、并行、进程、事务和耐久调度，才能避免 event loop 阻塞、
双写丢任务、共享 session 竞态与请求超时后的幽灵任务。

### IV. 可持久、可恢复的 LangGraph

生产 LangGraph MUST 使用可序列化的类型化 state、明确 reducer 和耐久 checkpointer。
每次业务执行必须拥有稳定且可追踪的 thread/execution 标识；恢复、取消、超时和重复
投递必须产生确定的状态语义。

- state 只保存编排所需数据、业务引用和版本标识；大型正文、密钥、ORM 实例、客户端
  对象与不可序列化值不得进入 checkpoint。生产 checkpointer 必须启用安全反序列化模式
  或显式类型 allowlist，禁止可执行任意对象构造的宽松反序列化。
- node MUST 返回显式 state delta，MUST NOT 依赖可变全局状态。路由条件必须可测试，
  并对未知或畸形模型输出定义安全失败路径。
- 每个 execution/thread 在同一时刻必须只有一个有效写 owner。claim/lease 必须携带
  单调 fencing token 或等价 revision CAS；每次权威数据库写入、checkpoint、outbox/
  effect-intent 状态转换和结果采纳都 MUST 在同一原子操作中校验当前 fence。stale worker
  不得提交 state、终态、账务或结果。
- 恢复可能从 node 起点重新执行。外部副作用只能通过绑定当前 fence 的耐久 effect
  intent 发出，并使用供应商幂等键、去重或显式对账。lease 校验后、调用前丢失所有权的
  worker 即使完成调用，也只能留下可对账 attempt；只有当前 fence 可以采纳结果。非幂等
  或结果可能未知的副作用 MUST 隔离到独立 node；未知结果进入“待确认/对账”，禁止盲重试。
- 需要用户输入、审批或修改时 MUST 使用锁定版本支持的可持久中断语义并以同一 thread
  恢复。R2/R3 写操作必须在副作用前中断；中断前操作必须幂等。
- checkpointer 保存 thread 内执行状态，store 保存跨 thread 长期记忆；两者都不是领域、
  审计或计费事实库。长期记忆必须有来源、租户、保留、纠错和删除策略。
- 新版本 graph 会读取存量 checkpoint。每个 release MUST 声明 live state/checkpoint、
  interrupt 和 queued job/event payload 的版本/保留矩阵；N-1 只是 rolling upgrade 的
  最低覆盖，不是长期恢复范围。矩阵内每个 live version 必须有经验证的 decoder/upcaster
  和 resume 测试。破坏性变化必须选择 drain、add-then-remove、migrate、versioned route
  或 quarantine/cancel；矩阵外执行必须产生用户和运维可见的确定结果、原因与处置证据，
  不得因无法解码而静默丢失。
- graph、prompt、model policy、tool schema、evaluator 和 payload schema 必须有不可变版本；
  每次执行记录实际版本，恢复时必须能解析或明确隔离不再支持的版本。

Rationale: checkpointer 提供恢复材料，不提供单写者、业务事实或发布兼容性。只有 fencing、
幂等副作用与存量 state 兼容同时成立，恢复才真正安全。

### V. 安全且由人掌控的 Agent 行为

模型输出、检索内容、网页文本、历史消息和 tool result 一律视为不可信数据，不能成为
越权指令。Agent 只能调用经过 allowlist、类型化 schema、最小权限和超时限制的工具；
工具执行层必须独立复验参数、授权、资源归属与业务不变量。

- 读工具与写工具 MUST 分离。R0 可直接执行并审计；R1 可使用绑定范围、预算和有效期的
  session/standing authorization；R2 必须逐执行明确确认；R3 必须逐执行确认并使用
  spec 定义的 step-up 或双人审批。自动化只能在其授权风险范围内运行。
- 确认/授权依据 MUST 绑定 actor、tenant、action、target、规范化参数摘要、tool/policy
  version、预算、expiry 与 idempotency key。任一实质字段、授权、归属或策略变化后必须
  重新授权，防止确认后的 TOCTOU。
- 工具返回必须验证 schema 和业务结果；“已提交”不得报告为“已完成”，未知结果不得
  包装为成功。每次工具写入必须关联确认 receipt 或适用的 standing-policy reference。
- 用户输入、外部内容与 prompt 的边界 MUST 明确，防止提示注入把数据提升为系统指令；
  模型不得自行扩权、改写预算、降低 risk class 或跳过确认。
- 数据执行最小化原则：只向模型和外部平台发送完成任务所需的数据。密钥禁止进入
  prompt/state/log；所有存储位置必须有数据分类与生命周期表。清单 MUST 至少覆盖且
  不限于数据库、checkpoint、跨 thread store、向量/搜索索引、dispatch/outbox、
  Redis/ARQ payload、retry/dead-letter、audit/evidence、log/trace/metric、评测集、cache、
  临时文件、派生副本、备份、导出和供应商留存。
- 生命周期表 MUST 逐 store 定义允许字段、owner、租户隔离、加密、访问、保留、删除/
  墓碑、备份清理与供应商删除。删除必须按来源/provenance 传播到队列、cache、派生索引、
  备份、导出与供应商，并留下覆盖完整性和删除/到期验证证据。不可变审计应保存去标识
  事实，并通过可撤销/可替换映射关联主体，避免“不可变”成为永久保留直接 PII 的理由。

Rationale: Agent 的文本能力不能代替授权边界。风险分级、绑定确认、最小权限和完整
数据生命周期共同限制模型错误、提示注入与工具副作用的影响半径。

### VI. 测试优先与评测门禁 (NON-NEGOTIABLE)

任何行为变更 MUST 先定义能在缺少变更时失败的 regression/invariant test 或等价前置
证据，再写最小实现并重构。任务只有在需求、实现、自动验证和可复核证据同时存在时
才能标记 `done`。

- bug 与 R2/R3 确定性行为 MUST 保留 RED/GREEN 证据（命令、预期失败原因和通过结果或
  可验证 commit 顺序）。migration、配置、生成制品和概率策略可以使用 schema diff、
  dry-run、旧版本回放或基线实验等明确的等价前置证据。
- 确定性规则使用 unit/property test；FastAPI 使用 request/response、错误、auth/RLS 与
  OpenAPI contract test；数据库、Redis、worker 和 adapter 使用 integration test；关键
  用户旅程使用 E2E test。
- LangGraph 必须覆盖 node、routing、reducer、完整 graph、checkpoint、interrupt/resume、
  duplicate delivery、lease loss/fencing、cancel/approval/late-result race 与 N-1 state 恢复。
  每个测试使用隔离 state、thread 和 checkpointer。
- mock 只允许隔离边界；合并门禁不得只验证全 mock 快乐路径。模型/工具超时、限流、
  畸形输出、部分成功、未知副作用和遥测故障必须有确定性故障注入。
- prompt、model policy、tool schema、graph 或 evaluator 变更 MUST 在版本化数据集上运行
  离线回归，并按 risk class、流量和变更幅度设置阈值、样本与 rollout。主观/R2/R3 指标
  必须人工校准，不得仅以同一个 LLM 自评作为发布证据。
- 生产 AI 能力 MUST 进行符合隐私与成本策略的在线质量监控，把代表性失败转回评测集。
  削弱 R2/R3 阈值、绕过阻断门禁或批准高风险基线退化需要双人审批；普通数据纠错按
  owner 审核即可。

Rationale: 普通测试证明软件机制，评测证明概率型行为；前置证据必须真实但不应退化为
对每种制品机械截图的流程表演。

### VII. 可观测、可靠且可运维

每个请求与后台执行 MUST 通过稳定关联标识连接 request、task、LangGraph thread、
execution、node、model/tool attempt 和业务结果。结构化日志、trace、metric 与不可变
审计事件必须各司其职，任何观测平台都不得成为业务事实源。

- service/release unit 至少提供 rate/error/duration/saturation；AI 路径还提供 token、
  成本、模型/工具延迟、重试、降级、缓存、中断、取消、恢复和质量指标。高基数 ID
  只进入 log/trace，不进入无界 metric label。
- 强制审计、任务终态和账务事实 MUST 可靠持久化且不可采样；OTel、LangSmith 或指标
  后端不可用时，业务不得伪造成功，也不得因遥测重试而重复副作用。
- 日志和 trace 默认只记录脱敏元数据、哈希和版本；原始 prompt、简历、工具参数和模型
  输出的采集必须显式授权，并遵守 Principle V 的生命周期表。
- 每个 production release MUST 指定 operational release unit。低风险 capability 可以
  明确继承 unit 的 SLI/SLO、错误预算、告警、runbook、容量和回滚；R2/R3 或具有独立
  failure mode 的 capability 必须补充自己的门禁与响应步骤。
- 无副作用证据回放与会产生新调用的重新执行必须是两个独立操作。
- 运维、迁移、回放、评测和对账能力 MUST 提供可脚本化 CLI 或等价管理接口，支持
  结构化输出、稳定退出码与审计；普通 UI/领域模块不要求机械提供 CLI。

Rationale: 可观测性用于理解系统，审计事实用于证明系统。按 release unit 组织控制既能
避免逐能力占位文档，也能让真正独立的高风险 failure mode 得到治理。

## Technology & Runtime Constraints

- **Canonical stack & support** — Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy 2
  async、Alembic、PostgreSQL、Redis/ARQ、LangGraph、OpenTelemetry；实际解析版本以
  `backend/uv.lock` 为准，并在每个 plan 中记录。生产依赖 MUST 位于供应商 ACTIVE 或
  MAINTENANCE 支持窗口；不在窗口或状态无法证实的版本必须登记有 owner、expiry、
  补偿控制和升级计划的 dependency deviation。
- **Current LangGraph deviation** — 当前解析版本 0.2.28 未出现在官方现行支持列表中，
  MUST 在任何 production release 前完成支持确认或迁移到受支持版本；迁移必须保护
  存量 checkpoint、interrupt 和 queued payload。
- **FastAPI composition** — 应用按业务模块使用 `APIRouter` 组合；HTTP 横切能力通过
  dependency/middleware/lifespan 提供。middleware 不承载领域事务，router 不直接调用
  供应商 SDK，application/domain 不导入 FastAPI。
- **Persistence & migration** — PostgreSQL 是业务、审计、任务和账务事实源；session/
  unit of work 按并发 task 定界。schema/checkpointer migration 必须由 pre-deploy/init
  job 执行，并使用数据库强制的互斥锁与 migration ledger 抵抗 scheduler retry/并发；
  MUST NOT 在每个 API/worker lifespan 运行。backfill 必须幂等、可恢复且可观测。
  expand 与 contract 必须分属不同的 rolling-compatible release；只有在证明所有旧 binary、
  checkpoint、interrupt 与 queued payload 都不再读取被移除 schema 后才可 contract。
  每阶段提供经验证的 backout 或 roll-forward；只有无损时才要求 downgrade。
- **Background execution** — PostgreSQL 中的 task + dispatch intent/outbox 是耐久受理
  事实，ARQ/Redis 是可重建传输层，LangGraph 是任务内编排层。dispatcher、worker 和
  recovery 都必须处理 at-least-once、bounded admission、lease/fencing、幂等、取消、
  对账与 dead-letter；不得把 ARQ job ID 或进程内锁当作 exactly-once 保证。
- **Provider access** — 模型、embedding、搜索和外部工具只可通过集中 adapter/client
  调用，由其统一执行超时、限流、重试分类、熔断、预算、版本、脱敏和用量记录。
- **Configuration** — 配置由类型化 settings 在启动时校验；secret 仅从环境或托管
  secret store 注入。开发便利默认值不得在 staging/production 静默启用。
- **Portability** — LangSmith 可用于调试、评测和观测，但核心执行、事实记录、故障恢复
  与质量门禁 MUST NOT 依赖单一外部 SaaS 才能成立。

## Development Workflow

1. **Specify** — 每个 spec 必须声明用户价值、适用性、最高 risk class、逐操作风险矩阵、数据/信任边界、授权
   主体、同步/后台模型、失败/取消/恢复、外部副作用、隐私生命周期、可衡量成功标准和
   明确非目标；不适用项必须给出 `N/A` 理由。
2. **Pre-research screening** — Phase 0 前逐项填写 `CLEAR`、`RESEARCH REQUIRED` 或
   `BLOCKED`。`RESEARCH REQUIRED` 允许进入 Phase 0 以消除未知；`BLOCKED` 在风险或
   权限决策解决前不得继续，不能用假 PASS 绕过。
3. **Post-design check** — Phase 1 后逐项填写 `PASS`、`N/A WITH RATIONALE`、
   `APPROVED DEVIATION` 或 `FAIL`，并链接设计/测试/运维证据。`FAIL` 不得进入实现；
   deviation 必须符合 Governance。
4. **Implement** — 按可独立验证的纵向切片执行 red-green-refactor 或等价前置证据；
   contract、migration、代码、安全、恢复、评测、遥测和文档按该切片的风险同时交付。
   最终 polish 只能做聚合验证，不能首次实现强制控制。
5. **Review** — 评审必须验证依赖方向、session/事务、进程隔离、dispatch/fencing、
   越权/注入、确认 TOCTOU、checkpoint 兼容、隐私生命周期、失败语义和证据完整性。
6. **Merge gates** — 相关 lint、strict type check、unit、contract、integration、E2E、
   migration、fault/recovery 和 eval 必须通过。只有证明与风险无关的昂贵套件可以按
   经评审 path filter 跳过，且跳过理由可审计。
7. **Release** — 使用版本化制品与风险适配灰度；扩量前验证继承或专属的 SLO、质量、
   成本、安全、容量和 rollback。schema/checkpoint/payload 变更必须通过 live-version
   矩阵、至少 N-1 rolling 恢复、数据库 migration 互斥、分离的 expand/contract 与
   backout/roll-forward 演练。

## Normative References

本宪法提炼以下官方资料的稳定语义；API 用法必须以项目解析版本对应的资料为准：

- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI Background Tasks caveat](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat)
- [FastAPI Deployment Concepts](https://fastapi.tiangolo.com/deployment/concepts/)
- [FastAPI Response Models](https://fastapi.tiangolo.com/tutorial/response-model/)
- [SQLAlchemy AsyncSession concurrency](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [ARQ 0.26.3 documentation](https://raw.githubusercontent.com/python-arq/arq/v0.26.3/docs/index.rst)
- [LangGraph 0.2.28 Persistence](https://raw.githubusercontent.com/langchain-ai/langgraph/0.2.28/docs/docs/concepts/persistence.md)
- [LangGraph current Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Backward Compatibility](https://docs.langchain.com/oss/python/langgraph/backward-compatibility)
- [LangGraph Release Policy](https://docs.langchain.com/oss/python/release-policy)
- [LangGraph Testing](https://docs.langchain.com/oss/python/langgraph/test)
- [LangGraph package releases](https://pypi.org/project/langgraph/)
- [LangGraph PostgreSQL checkpointer security and releases](https://pypi.org/project/langgraph-checkpoint-postgres/)
- [LangSmith Observability](https://docs.langchain.com/langsmith/observability)
- [LangSmith Evaluation](https://docs.langchain.com/langsmith/evaluation)

## Governance

本宪法优先于其他项目实践。冲突出现时，任何实现与文档不得选择较宽松规则；必须
修订冲突制品或按下述程序修宪。

- **Amendment** — 修订通过 PR 进行，说明动机、受影响原则、迁移影响、模板同步和
  验证证据，并由项目所有者或授权维护者批准。
- **Versioning** — 宪法遵循 Semantic Versioning：原则删除/重定义或不兼容治理变更
  升 MAJOR；新增原则、章节或实质扩展升 MINOR；不改变义务的澄清升 PATCH。
- **Deviation** — `APPROVED DEVIATION` 必须记录 control/clause、scope、risk、理由、
  被拒绝的简单方案、补偿控制、owner、approver、expiry 和 removal task。到期即 FAIL；
  dependency deviation 还必须记录供应商支持状态和迁移目标。
- **Compliance** — 每个 plan 与 PR 必须对照当前版本。安全、租户隔离、审计真实性、
  R3 授权与 stale worker 隔离不可豁免；其他强制项只能按 Deviation 有期限偏离。
- **Evidence** — requirement 只有在实现与验证证据均存在时为 `done`；仅有代码时为
  `in_progress`。评审人必须拒绝没有证据或用遥测推断业务事实的完成声明。
- **Periodic review** — 每次框架大版本升级、依赖退出支持窗口、重大事故、Agent 工具
  权限扩大或至少每季度进行一次适用性复核。
- **Runtime guidance** — 日常导航以 `AGENTS.md`、`docs/testing/README.md`、
  `docs/architecture/source-map.md` 和当前 SpecKit feature 为准；它们不得降低本宪法。

**Version**: 2.1.0 | **Ratified**: 2026-06-12 | **Last Amended**: 2026-07-11
