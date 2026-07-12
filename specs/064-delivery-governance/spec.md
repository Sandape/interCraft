# Feature Specification: 跨应用交付治理

**Feature Branch**: `[064-delivery-governance]`

**Created**: 2026-07-12

**Status**: Ready for Plan / Tasks

**Input**: Accepted governance handoff prompt (`governance-implementation-handoff-prompt.md`), Phase 1–3 completion (Ruleset, Preflight), Issue #19 dispatch acceptance criteria.

## Product Problem & Scope

InterCraft 仓库当前存在多个治理缺口：SpecKit 文档与产品代码变更之间缺乏强制门禁；多个客户端（Codex、Claude Code、Cursor、人工开发）可能同时修改同一路径；CI 持续红色且非 Required；无标准化 Issue Forms、PR Template、CODEOWNERS 或 Dispatch 协议。

本需求不解决具体产品缺陷，而是建立一套持续可行的多客户端交付治理体系：保证每次变更都经过 `Spec → Issue → Dispatch → 独立分支/worktree → Draft PR → CI → 真人非作者 Review → Squash Merge` 流程。

治理体系本身不产生直接用户价值，但消除当前开发流程中的协调开销、合并冲突和绕过风险。

### In Scope

- 共享规则文档（SOP、团队上手指南、ADR）
- 多客户端工具适配（Codex AGENTS.md 精简、Claude Code CLAUDE.md、Cursor Project Rules）
- 跟踪的 Claude runtime 文件审计与治理
- Issue Forms（Bug、Feature、Agent Task）、PR Template、CODEOWNERS、标签与 Project 五态
- Dispatch 状态机与 Handoff 协议
- PR Gate 自动检查（Issue/Dispatch 有效性、AC hash、allowed paths、base freshness、governance version）
- CI 分层修复（基础 → Contract/Integration → E2E → Eval）
- Cursor 自动化（真人评论触发 → 稳定后 Webhook）
- Stage-B 正向/负向故障演练（至少 11 项验证）
- 团队验收（Fresh Clone、客户端验证、Dry-run 闭环）
- 可追溯的 HTML 截图 walkthrough 素材

### Non-Goals

- Phase 4 Spec-only PR 不修改产品代码、CI Workflow、Ruleset 或客户端配置；这些治理制品只能在其后已列明的独立阶段/PR 中修改
- 自动化身份不部署、不审批、不合并；经用户明确授权的 Sandape Owner/Codex 验收操作不属于自动化身份权限
- 不读取、复制或配置生产 Secret / 生产数据库 / 生产 MCP
- 不修改 `.specify/feature.json`（指向 `specs/063-derive-page-fill`）
- Phase 4 本身不触及 `D:\Project\eGGG` dirty worktree；但治理体系在 Phase 10 最终验收前 MUST 完成 reconciliation，包括所有权分类和有界路由

### Governance Profile

**Highest Risk Class**: R3。Constitution 将外部副作用定义为 R2、权限/Ruleset 边界变更定义为 R3。
本需求涉及仓库自动化写入（R2）和 Ruleset 边界变更（R3），因此特征级最高风险为 R3。

| Governed operation / effect | Risk class | Actor / target / trust boundary | Required authorization and evidence |
|---|---|---|---|
| 治理体系（本需求整体特征） | R3 | Codex / 仓库治理基础设施 | Spec acceptance + Codex review + 每执行人工授权 |
| 治理文档与 SOP 创建/修改 | R1 | 治理负责人 / specs/ + docs/engineering/ | Issue dispatch + PR + 非作者审批 |
| 客户端适配文件创建/修改 | R1 | 治理负责人 / AGENTS.md, CLAUDE.md, .cursor/rules/ | Issue dispatch + PR + CODEOWNERS |
| 自动化 bot 开 PR、写入分支、合并操作 | R2 | GitHub App / 仓库 | Issue dispatch + PR Gate + 显式人工授权（每执行） |
| Issue Forms / PR Template 创建 | R1 | 治理负责人 / .github/ | Issue dispatch + PR + 非作者审批 |
| Dispatch 与 Gate 脚本创建 | R1 | 治理负责人 / scripts/governance/ | Issue dispatch + PR + test harness |
| Ruleset 突变/绕过政策变更 | R3 | Sandape Owner（可明确委托 Codex 操作）/ 仓库 Ruleset | 每执行 Owner 明确确认 + GitHub 已认证 Owner UI step-up + 修改前后截图证据；不要求 NekoDreamSensei 作为固定第二人 |
| 直接推送 master | forbidden | 任何人 / master | —（Ruleset 永久禁止，不可绕过） |

### Authorization & Approval Policy

- **默认审批要求**：每个合入 `master` 的 PR 至少需要一位非作者的真人审批。此要求适用于所有治理 PR。
- **Owner PR-only 绕过**：Sandape 仓库/产品 Owner 可亲自操作或明确委托 Codex 在紧急或低风险场景中使用 PR-only 绕过审批，但必须附带显式理由和可验证证据（截图、日志等）。直接推送绕过在任何情况下均被禁止。
- **直接推送永久禁止**：直接推送 `master` 在任何情况下均被禁止，由 Ruleset 强制实施。
- **Reviewer 设定**：NekoDreamSensei 不设为主要 Reviewer 或 blocker。如需其审查，应在 PR 中 @mention 请求，不作为 CODEOWNERS 强制要求。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 团队能理解并遵守交付流程 (Priority: P1)

作为 InterCraft 开发者（Codex、Claude Code、Cursor 或人工），我希望阅读一份 SOP 和 Onboarding 文档后能独立完成「从 Issue 到 Squash Merge」的全流程，而不需要问 Owner 每步该做什么。

**Why this priority**: 这是治理体系的基础可用性承诺。

**Independent Test**: 在 Fresh Clone 中按 SOP 完成一个 Dry-run Issue 全流程，记录每一步的输出。

**Acceptance Scenarios**:

1. **Given** 治理体系就绪，**When** 一位新开发者阅读 `docs/engineering/delivery-sop.md` 和 `docs/engineering/team-onboarding.md`，**Then** 应能理解从 Issue 创建到 PR 合并的完整步骤。
2. **Given** 开发者安装了 Claude Code 和 Cursor，**When** 按 Onboarding 配置客户端，**Then** 客户端应加载正确的规则和约束，不再建议直接推送 `master`。
3. **Given** 存在一份已验收的 Spec，**When** 开发者创建对应 Issue，**Then** Issue 内容应符合 Issue Form 模板，包含 dispatch_id、base_sha、AC hash、allowed paths。

---

### User Story 2 — 自动化确保交付门禁一致执行 (Priority: P1)

作为 Codex（验收负责人），我希望自动化 Dispatch 与 PR Gate 确保只有被授权、可验证、并且不冲突的变更能进入 `master`。

**Why this priority**: 在多客户端并行开发场景下，只有机械强制才能保证流程不被绕过。

**Independent Test**: 对 gate 脚本运行正向与负向测试用例集；验证直推被拒、重复 Dispatch 被幂等、handoff 后旧 PR 被阻断。

**Acceptance Scenarios**:

1. **Given** 治理 Gate 脚本已部署，**When** 尝试直接推送 `master`，**Then** 被 Ruleset 拒绝。
2. **Given** 一个 Issue 已有活跃 Dispatch，**When** 同一 Issue 触发新的 Dispatch，**Then** 自动化幂等处理，不产生重复分支。
3. **Given** 一个 Dispatch 已 handoff 给另一位 Driver，**When** 旧 Driver 的 PR 尝试通过 Gate，**Then** Gate 检查拒绝该 PR。
4. **Given** Issue 的 AC hash 被编辑，**When** 对应 Dispatch 的 PR 运行 Gate，**Then** 检查失败，PR 不能通过。

---

### User Story 3 — CI 提供可靠的变更质量信号 (Priority: P1)

作为 Reviewer，我希望 CI 在 PR 上提供分层质量信号：基础检查必须全绿才能请求 Review，Contract/Integration 与 E2E 覆盖关键路径。

**Why this priority**: 当前 CI 持续红色且非 Required，Reviewer 无法信任 CI 结果作为合并条件。

**Independent Test**: 对修复后的 CI 运行已知通过和已知失败的 PR，确认通过/失败状态正确反映。

**Acceptance Scenarios**:

1. **Given** CI 已修复，**When** 提交无 lint 错误的代码，**Then** frontend/backend-lint/backend-unit 均为绿色。
2. **Given** CI 已修复，**When** 提交含 lint 错误的代码，**Then** 对应 check 为红色。
3. **Given** Stage-B 启用后，**When** Required Check 为红色，**Then** 合并按钮被禁用。

---

### User Story 4 — 故障场景可演练和回滚 (Priority: P2)

作为治理负责人，我希望在 Stage-B 启用前验证治理体系的故障行为，且任何一个 PR 都可以安全回滚。

**Why this priority**: 治理本身不应成为开发瓶颈；回滚和故障演练保障了系统的健壮性。

**Independent Test**: 对 Phase 5–10 的每个 PR 执行回滚测试；执行至少 11 项故障演练场景。

**Acceptance Scenarios**:

1. **Given** 任意治理 PR 合并后出现问题，**When** 执行 `git revert`，**Then** 仓库恢复到该 PR 之前的状态，无残留变更。
2. **Given** Stage-B 演练场景全部通过，**When** 启用严格 Required Checks，**Then** 已知失败的 PR 无法合并。
3. **Given** Ruleset 被意外修改（drift），**When** 审计脚本检测到漂移，**Then** 自动创建治理 Issue。

### Edge Cases

- 客户端本地规则与远端 SOP 不一致：以 SOP 为准，审计脚本标记偏离。
- Dispatch 与 PR 的 base SHA 落后远端：Gate 要求更新后才能通过。
- Cursor 自动化在未稳定前只分诊，不直接修改代码。
- CI Workflow 修改必须触发 CODEOWNERS Review。
- 治理文档的变更路径与产品代码冲突：以 `.github/`、`docs/engineering/`、`specs/` 为治理专属路径。
- Ruleset 理论上可由 Admin 绕过：使用期望状态快照和审计脚本检测 drift，不声称绝对不可绕过。
- 网络传输失败导致远端 ref 不可靠：通过 `gh api` 验证远端 `master`，不使用 stale local ref。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 包含一份 `docs/engineering/delivery-sop.md`，覆盖从 Issue 创建到 Squash Merge 完整流程。
- **FR-002**: 系统 MUST 包含一份 `docs/engineering/team-onboarding.md`，指导开发者在 Fresh Clone 中配置客户端并完成首个 PR。
- **FR-003**: 系统 MUST 包含至少一份 ADR，记录关键架构决策，包括多客户端治理、Dispatch 协议、Gate 设计。
- **FR-004**: Codex AGENTS.md MUST 精简并只引用全局规则，不重复 SOP 内容。
- **FR-005**: Claude Code CLAUDE.md MUST 通过 `@AGENTS.md` / SOP 导入公共规则，仅含确定性 Hook 在 `.claude/settings.json` 中。
- **FR-006**: Cursor Project Rules MUST 在 `.cursor/rules/agent-delivery.mdc` 中薄适配，不复制 SOP。
- **FR-007**: 系统 MUST 审计当前 tracked Claude runtime/local 文件；备份耐久知识后取消追踪并补 `.gitignore`。
- **FR-008**: 系统 MUST 检查 Git 历史中的 Secret；发现后 MUST 轮换并通知 Owner。
- **FR-009**: 系统 MUST 提供 Issue Forms（Bug、Feature、Agent Task），包含 dispatch_id、base_sha、AC hash、allowed paths 等字段。
- **FR-010**: 系统 MUST 提供 PR Template，包含 Refs #N、base/dispatch、files、checks、risks、rollback 章节。
- **FR-011**: 系统 MUST 提供 CODEOWNERS 定义治理关键路径的 Reviewer。
- **FR-012**: 系统 MUST 提供标签（label）和五态 Project 模型（Inbox / Needs Clarification / In Progress / In Review / Done）。
- **FR-013**: Dispatch 状态机 MUST 支持 dispatch_id、driver、base SHA、Spec/Task ID、AC hash、allowed paths、governance version。
- **FR-014**: Dispatch 状态机 MUST 满足：Inbox / Needs Clarification 可无 Driver；In Progress / In Review 必须有一个当前 Dispatch；同一 Issue 最多一个活跃 Dispatch，不区分 driver。
- **FR-015**: PR Gate MUST 检查 Issue/Dispatch 有效性、唯一有效 PR、AC hash 匹配、allowed paths 合规、base freshness、evidence 存在、governance version 匹配。
- **FR-016**: 同一 Issue 的自动化 MUST 使用 concurrency/idempotency，不得将 assignee/label 当作原子锁。
- **FR-017**: GitHub 无法阻止两个本地客户端同时开始工作；Gate 承诺：同一 Issue 同时最多一个交付 PR 能通过。
- **FR-018**: CI MUST 分层：基础（frontend、backend-lint、backend-unit、summary）；Contract/Integration；E2E；Eval。
- **FR-019**: Required Check MUST 绑定 GitHub Actions 来源；Workflow/SOP 变更 MUST 触发 CODEOWNERS Review。
- **FR-020**: Cursor 自动化初期 MUST 使用授权真人的 Issue 评论触发，不得直接通过 Ready-label → webhook。
- **FR-021**: 自动化使用 App/webhook 身份和最小权限，不使用人类 PAT，不继承生产 Secrets，不部署、不审批、不合并。
- **FR-022**: Stage-B 启用前 MUST 至少验证 11 项故障场景（直推拒绝、重复 Dispatch 幂等、handoff 阻断、AC 编辑失败、path escape 拒绝、Workflow 篡改、Check 失败/缺失/取消、stale branch、Secret 隔离、Ruleset drift、revert 恢复）。
- **FR-023**: Team 验收 MUST 包含 Fresh Clone 拉取规则、客户端验证、Dry-run Issue 完整闭环。
- **FR-024**: 历史 Issues MUST 逐个验证，不批量猜测关闭原因。
- **FR-025**: 所有治理 Requirement 标记 done 前 MUST 存在实现、验证、设置快照和第二开发者演练证据。
- **FR-026**: 治理体系 MUST 在 Phase 10 前对 `D:\Project\eGGG` 的全部 dirty worktree 条目完成所有权分类，识别每条脏条目属于：可经 Dispatch/PR 发布的规范工作、应归档到仓库外部的文件、经批准的忽略项、或保留的具名用户工作。
- **FR-027**: 治理体系 MUST 在 Phase 10 提供零未归类脏条目的证明（zero unexplained dirty entries），不使用 `git reset --hard`、`git clean -fd`、强制 stash、批量猜测或覆盖用户工作。
- **FR-028**: 系统 MUST 在 `docs/evidence/064-delivery-governance/sop-walkthrough.html` 提供自包含的证据素材，包含每步 SOP 截图、时间戳、确切 URL/路径、操作者、输入条件、门禁结果、证据引用、回滚命令和隐私脱敏。覆盖 Spec → Issue → Dispatch → clean external worktree/branch → preflight → commit → Draft PR → CI → review 或显式 Owner PR-only 绕过 → squash merge → master 验证。
- **FR-029**: 所有 FR/SC MUST 在 `tasks.md` 中有对应任务条目，并在 `requirements-status.md` 中有对应状态行。

### Governed Boundaries & Failure Semantics *(mandatory)*

- **Contract**: 所有治理脚本和 Gate 必须有明确失败语义（fail-closed）；preflight.ps1 已有 13 测试用例；后续 Gate 脚本同样需要测试覆盖。
- **Authorization**: 治理 Issue 由 Codex 签发；Dispatch 只能由授权 Driver 执行；Gate 仅允许同一 Issue 一个有效 PR。
- **Execution**: 治理脚本必须验证仓库 root、branch、base SHA、dirty state、allowed paths；偏离即拒绝。
- **External Effects**: Cursor 自动化使用 bot 身份，不影响人工 PAT 或生产 Secret。
- **Data Lifecycle**: 治理 Issue 和 PR 数据随仓库生命周期管理；不需要额外的数据清理策略。
- **Compatibility**: 治理体系必须兼容现有 SpecKit 目录结构和 `.specify/feature.json` 约束。

### AI & Agent Safety Requirements *(mandatory when AI or Agent behavior is in scope)*

- **State**: Dispatch 使用文件化状态（JSON 或 YAML），存储在 `.github/dispatches/` 或等价 tracks 目录，不依赖 GitHub Issue 正文解析作为唯一真相。
- **Tools**: 治理脚本只能写 allowed paths（`specs/README.md`、`specs/064-delivery-governance/**`）；写路径在 dispatch 中固定。
- **Trust Boundary**: Issue Forms 内容视为不可信输入；Gate 脚本验证所有字段。
- **Quality**: 治理脚本必须有测试覆盖（至少正向/负向各一条）；CI 修复后基础 check 必须全绿。

### Key Entities

- **Dispatch Envelope**: dispatch_id, issue_number, driver, base_sha, spec_task_id, ac_hash, canonical_ac_text_version, allowed_paths, governance_version, created_at, state (active | superseded | expired)
- **Governance State**: 跟踪当前活跃治理 PR 的状态、当前阶段、已通过的检查、阻隔项
- **Handoff Invariant**: 记录 Dispatch 转移的条件和验证

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 治理 SOP 覆盖完整流程（Spec → Issue → Dispatch → 分支 → Draft PR → CI → Review → Squash Merge），缺少任何步骤即为不合格。
- **SC-002**: 三客户端（Codex、Claude Code、Cursor）加载正确规则后，均不推荐直接推送 `master`。
- **SC-003**: PR Gate 在正向（合法 Dispatch）和负向（直推/重复/陈旧 base/AC 不匹配/path 越权/过期 governance version）测试中均通过。
- **SC-004**: Dispatch 状态机在 Issue 内容或 Driver 变化后正确使旧 Dispatch 失效。
- **SC-005**: CI 修复后基础检查（frontend/backend-lint/backend-unit）全绿。
- **SC-006**: 11 项 Stage-B 故障演练场景均通过预期验证，无意外通过或意外失败。
- **SC-007**: Dry-run Issue 完整闭环（Spec → Issue → Dispatch → PR → Gate → Review → Merge）在 Fresh Clone 中完成。
- **SC-008**: Phase 10 完成后 `D:\Project\eGGG` 无未归类的 dirty 条目（zero unexplained dirty entries）。
- **SC-009**: `docs/evidence/064-delivery-governance/sop-walkthrough.html` 覆盖完整 SOP 流程，每步包含截图、时间戳和隐私脱敏。

## Assumptions

- Stage-A Ruleset 18825748 保持激活状态；Phase 9 演练通过后由 Codex 启用 Stage-B。
- 远端 `master` 使用 `880580a088ecf0186fddcb64c46edd48e60043d7` 作为 Phase 4 的权威基线。
- `.specify/feature.json` 保持指向 `specs/063-derive-page-fill`；本需求不修改全局 pointer。
- 本需求编号为 **REQ-064**：由 Codex 手动分析确认为下一个可用编号。全局 `.specify/feature.json` pointer 由规范前置脚本解析并保持指向 `specs/063-derive-page-fill`，不依赖 SpecKit analyze。
- 治理体系不改变产品代码的目录结构、数据库 schema 或 API contract。
- 各客户端（Codex、Claude Code、Cursor）均能读取 SOP 和规则文件；规则文件使用标准 Markdown/YAML 格式。
- CI 修复（Phase 7）在治理 PR 中独立进行，不混入业务重构。
- HTML 截图 walkthrough 是 Phase 10 的必交自包含验收制品，由 Codex 截图、保存并执行最终视觉 QA。
