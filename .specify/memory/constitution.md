<!--
  Sync Impact Report
  ==================
  Version change: 无 → 1.0.0 (初始版本)
  Modified principles: 无 (从模板首次落地)
  Added sections:
    - Core Principles (I–V)
    - Technology & Stack Constraints
    - Development Workflow
    - Governance
  Removed sections: 无
  Templates requiring updates:
    - .specify/templates/plan-template.md        ✅ 对齐 Constitution Check 门禁(Plan 阶段 0 与阶段 1 后双重核对)
    - .specify/templates/spec-template.md        ✅ 用户故事独立可测试与 TDD 原则保持一致
    - .specify/templates/tasks-template.md       ✅ 任务按用户故事拆分,测试任务在前(P3、T10、T11 等)
  Deferred items: 无
-->

# InterCraft Constitution

## Core Principles

### I. Library-First

InterCraft 中的每个特性 MUST 以独立的、边界清晰的库或自包含模块作为起点。
前端特性模块、后端服务、AI 编排组件均遵循此规则。每个库 MUST 满足:

- **自包含** — 声明自己的依赖;不触碰全局状态或其他库的内部实现。
- **可独立测试** — 暴露钩子或测试夹具,使其在无外部依赖的情况下运行。
- **有文档** — 库根目录的 README 描述用途、公开 API、配置与"示例命令"。
- **有目的** — 为一项明确能力而存在,不是为了组织结构而设立。

针对 AI 编排层(roadmap 中的 M14–M19),每个"agent"或"chain"都视为一个
库:它持有自己的 prompt、工具与评估夹具,并可在生产运行时之外被调用。

### II. CLI Interface

InterCraft 的每个库与服务 MUST 通过 CLI 暴露其主要功能。CLI 是调试、脚本
化与 CI 使用的统一契约。

- **文本 I/O 协议** — 参数与 stdin 作为输入,结果与结构化事件写入 stdout,
  错误与告警写入 stderr。
- **输出格式** — 默认人类可读,`--json` 模式用于机器消费;JSON 是跨进程
  的标准形式。
- **退出码** — `0` 表示成功,非零表示失败,且退出码与语义必须有文档说明。
- **本地优先** — CLI 在开发机与 CI 上无需启动完整 Web 栈即可运行,使库
  可被独立演练。

Web 前端模块不直接提供 CLI,但其核心业务逻辑(校验、reducer、AI 调用)
MUST 可被 Node/CLI 夹具调用,使同一份代码在浏览器外也可被验证。

### III. Test-First (NON-NEGOTIABLE)

InterCraft 对任何非平凡的变更都执行严格的 TDD 循环:

1. **先写测试** — 选择能覆盖该切片的最低合理层级(单元 / 契约 / 集成)。
2. **运行测试** — 确认它以正确的原因失败。
3. **显式签收** — 在翻绿之前必须经过代码评审或结对审批;跳过此步骤即为
   违反原则。
4. **写最小实现** — 仅编写让测试通过的最小代码。
5. **重构** — 保持测试为绿,改进结构。

任务只有在测试就位且为绿时才视为"完成"。UI 任务遵循同样规则:组件测试、
hook 测试或 E2E 故事先于组件存在。AI prompt 任务同理:评估样例与断言
先于最终 prompt 定稿。

### IV. Integration & Synchronization Testing

InterCraft 是多层级系统:前端、后端、同步/离线客户端与 AI 编排。单元测试
必要但不充分。下列场景 MUST 由集成或契约测试覆盖:

- **新库/服务契约** — 用契约测试固定边界两侧的 schema 与行为。
- **跨服务通信** — request/response、streaming 与 WebSocket 路径均需在
  真实或内存级适配器上端到端跑通。
- **共享 schema 与数据模型变更** — 迁移在贴近生产形态的种子数据上验证。
- **同步与离线路径** — 冲突解决、最后写入胜出 vs. 操作变换、断线重连。
  这些 MUST 在模拟网络故障的场景下测试。
- **AI 编排边界** — 输入/输出、工具调用往返、模型调用失败或返回畸形
  结果时的回退行为。

模块边界处的 mock 可接受,但集成套件 MUST 命中真实或进程内等价服务 ——
不允许"全部 mock 的快乐路径"。

### V. Observability

可调试性是生产级能力的硬性要求。InterCraft 每个组件 MUST 发出结构化
日志,相关层级 MUST 暴露指标与追踪。

- **结构化日志** — JSON 或 key=value 形式,具备稳定 schema(时间戳、
  级别、服务、request_id、可选 user_id、message、context)。开发态可渲染
  为人类可读形式。
- **请求关联** — 每个请求携带一个 ID,跨服务边界、跨日志、跨 AI 编排
  运行进行传播。
- **指标** — 至少:请求率、错误率、延迟(p50/p95/p99),以及 AI 专用指标
  (token 用量、prompt 缓存命中率、模型失败率)。
- **错误上下文** — 失败需包含足够复现的上下文;堆栈 MUST NOT 是唯一
  诊断信息。
- **CLI 即可观测** — CLI 表面同时是调试表面:从已保存的输入夹具重放
  失败场景 MUST 可行。

## Technology & Stack Constraints

InterCraft 是包含 AI 编排层的全栈系统。下列约束约束技术选型。新增层级
MUST 通过修订本节加入。

- **前端** — TypeScript(严格模式)+ React 18 + Vite + TailwindCSS;
  路由使用 `react-router-dom`。组件库与全局状态方案按特性评估,需在
  对应的 `plan.md` 中给出书面理由。
- **后端与服务** — MUST 暴露 HTTP 或 gRPC 契约,具备机器可读 schema
  (OpenAPI 或等价物)。持久层 MUST 使用项目标准 ORM 与迁移工具;不允许
  即兴 SQL。
- **AI 编排** — 基于 LangGraph(roadmap M14)。每个 agent 是一个库
  (原则 I),每个 pipeline 有 CLI(原则 II),prompt 变更随评估样例
  一起发布(原则 III)。模型调用 MUST 走集中化客户端,由其强制速率限制、
  重试与结构化日志(原则 V)。
- **同步与离线** — 客户端同步引擎(M12–M13) MUST 将网络视为不可信。
  所有写入路径 MUST 幂等且可重放。
- **安全与隐私** — 用户数据 MUST 静态与传输加密;密钥从环境变量或托管
  密钥服务读取 — 严禁入仓。会话与 RLS 层(M05)是用户范围数据的唯一
  合法通道,强制启用。

## Development Workflow

- **分支** — 特性分支遵循 `[###-feature-name]` 的 Spec Kit 命名约定;
  `master` 分支始终可发布。
- **代码评审** — 每个 PR 至少需要一次批准。评审人 MUST 校验原则 I–V
  的合规性;非平凡偏离需在 `plan.md` 的 `Complexity Tracking` 中说明。
- **质量门禁** — PR 在合并前 MUST 通过 lint、类型检查、单元测试、集成
  测试与契约测试。CI 失败即阻止合并。
- **Constitution Check** — 每个 `plan.md` 包含 Constitution Check 节,
  作为 Phase 0 研究阶段的前置门禁,并在 Phase 1 设计后复检。违规项
  MUST 列入 `Complexity Tracking` 并给出理由。
- **版本管理** — 产品遵循 Semantic Versioning;公开 API(HTTP 接口、
  库导出、CLI flag)均需版本化。破坏性变更必须在对应 release 中附带
  迁移说明。
- **文档** — 库级 README 按原则 I 强制要求。跨切面设计决策记录在
  `docs/` 中,并在相关 `plan.md` 中引用。

## Governance

本宪法优先于所有其他项目实践。出现冲突时,以宪法为准,直至其被修订。

- **修订程序** — 通过 PR 修改本文件。PR 描述 MUST 说明动机、受影响的原则
  或章节,以及对既有制品的影响。批准需项目所有者(或被授权维护者)确认。
- **版本策略** — 宪法自身遵循 Semantic Versioning。
  - **MAJOR** — 不向后兼容的治理变更,或原则的删除/重新定义。
  - **MINOR** — 新增原则或章节,或对既有指导的实质性扩展。
  - **PATCH** — 澄清、措辞优化或非语义性润色。
- **合规审查** — 每个 `plan.md` 与每个 PR MUST 与本宪法对照检查。
  评审人拒绝合并缺少 `Complexity Tracking` 解释的违规变更。
- **运行时指南** — 日常开发指南位于 `CLAUDE.md` 与 `docs/`。这些文档
  MUST NOT 与宪法相矛盾;有疑义时以宪法为准。

**Version**: 1.0.0 | **Ratified**: 2026-06-12 | **Last Amended**: 2026-06-12
