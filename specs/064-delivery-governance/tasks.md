# Tasks: 跨应用交付治理 (REQ-064)

**Input**: Spec document from `/specs/064-delivery-governance/`

**Prerequisites**: plan.md (required), spec.md (required), contracts/

**Organization**: Phases 5–10, each phase contains one or more ordered PR slices.
Execute in strict order: no Phase N+1 until every slice of Phase N is merged.

**Format**: `[TXXX] [Phase N] [PR-SLICE] Description`

- Each PR slice is an independent reviewable rollback-safe PR
- Dependencies: previous phase ALL slices merged; within a phase, slices merge in order
- Intended paths listed per task
- Validation: required checks per PR slice
- Rollback: `git revert -m 1 <merge-sha>`

**Final task count after all edits: 52 tasks** — all FR-001 through FR-029 and SC-001 through SC-009 have corresponding task entries and requirements-status rows.

---

## Phase 5 — 共享规则与工具适配 (3 PR slices)

**Dependencies**: Phase 4 merge (all Phase 4 PRs merged)

### Slice 5a — SOP/ADR (PR-05a)

**Branch**: `codex/064-phase5a-sop-adr`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 4 merge

**Intended paths**:
- `docs/engineering/delivery-sop.md` [NEW]
- `docs/engineering/team-onboarding.md` [NEW]
- `docs/decisions/ADR-001-multi-client-delivery-governance.md` [NEW]

#### Tasks

- [ ] T101 [Phase 5] [PR-05a] Create `docs/engineering/delivery-sop.md` — 唯一交付 SOP，覆盖完整流程：Spec → Issue → Dispatch → 分支/worktree → Draft PR → CI → Review → Squash Merge
- [ ] T102 [Phase 5] [PR-05a] Create `docs/engineering/team-onboarding.md` — 指导开发者在 Fresh Clone 中配置客户端并完成首个 PR
- [ ] T103 [Phase 5] [PR-05a] Create `docs/decisions/ADR-001-multi-client-delivery-governance.md` — 记录多客户端交付治理的架构决策

#### Validation

- [ ] All SOP steps are present and internally consistent
- [ ] `git diff --check` passes
- [ ] Onboarding references SOP, does not duplicate content

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 5b — Adapters (PR-05b)

**Branch**: `codex/064-phase5b-adapters`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 5a merge

**Intended paths**:
- `AGENTS.md` [MODIFY]
- `CLAUDE.md` [NEW]
- `.claude/settings.json` [MODIFY if tracked]
- `.cursor/rules/agent-delivery.mdc` [NEW]

#### Tasks

- [ ] T104 [Phase 5] [PR-05b] Simplify `AGENTS.md` — 精简为公共规则，不重复 SOP 内容；通过引用方式导入
- [ ] T105 [Phase 5] [PR-05b] Create `CLAUDE.md` — 通过 `@AGENTS.md` / SOP 导入公共规则；仅确定性 Hook 进入 `.claude/settings.json`
- [ ] T106 [Phase 5] [PR-05b] Create `.cursor/rules/agent-delivery.mdc` — Cursor 薄适配，不复制 SOP

#### Validation

- [ ] Clients (AGENTS.md, CLAUDE.md, .cursor) reference common source, don't duplicate
- [ ] No SOP content duplicated in adapter files
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

Restores AGENTS.md to pre-Phase 5b state, removes CLAUDE.md and .cursor/rules/agent-delivery.mdc.

---

### Slice 5c — Runtime/Dirty/Secret (PR-05c)

**Branch**: `codex/064-phase5c-runtime-reconciliation`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 5b merge

**Intended paths**:
- `.gitignore` [MODIFY for runtime files]
- `docs/engineering/` (relevant existing files — audit reports)

#### Tasks

- [ ] T107 [Phase 5] [PR-05c] Audit tracked Claude runtime/local files — 识别 `.claude/settings.local.json`、`.claude/state.json`、memory 文件；备份耐久知识；取消追踪；补充 `.gitignore`
- [ ] T108 [Phase 5] [PR-05c] Scan Git history for secrets — 使用 `git log -p` 或专用扫描工具；发现后通知 Owner 轮换（不自已轮换）
- [ ] T109 [Phase 5] [PR-05c] Create/update `.gitignore` — 确保 Claude/Cursor runtime 文件不被跟踪

#### Validation

- [ ] No tracked Claude/Cursor runtime files remain in index
- [ ] Secret scan completed (even if no secrets found)
- [ ] `.gitignore` correctly covers runtime paths
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

Must verify `.gitignore` revert doesn't re-track runtime files incorrectly.

---

## Phase 6 — Intake、Dispatch 与 Governance Gate (3 PR slices)

**Dependencies**: Phase 5 all slices merged

### Slice 6a — Intake Metadata (PR-06a)

**Branch**: `codex/064-phase6a-intake-metadata`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 5 all slices merged

**Intended paths**:
- `.github/ISSUE_TEMPLATE/bug.yml` [NEW]
- `.github/ISSUE_TEMPLATE/feature.yml` [NEW]
- `.github/ISSUE_TEMPLATE/agent-task.yml` [NEW]
- `.github/pull_request_template.md` [NEW]
- `.github/CODEOWNERS` [NEW]

#### Tasks

- [ ] T201 [Phase 6] [PR-06a] Create `.github/ISSUE_TEMPLATE/bug.yml` — Bug 报告 Issue Form，含 dispatch_id、issue_number、base_sha、AC hash、allowed paths 字段
- [ ] T202 [Phase 6] [PR-06a] Create `.github/ISSUE_TEMPLATE/feature.yml` — Feature 需求 Issue Form
- [ ] T203 [Phase 6] [PR-06a] Create `.github/ISSUE_TEMPLATE/agent-task.yml` — Agent 自动化任务 Issue Form
- [ ] T204 [Phase 6] [PR-06a] Create `.github/pull_request_template.md` — PR 模板，含 Refs #N、base/dispatch、files、checks、risks、rollback 章节
- [ ] T205 [Phase 6] [PR-06a] Create `.github/CODEOWNERS` — 定义治理关键路径的 Review 分配。NekoDreamSensei 不设为主要 Reviewer 或 blocker
- [ ] T213 [Phase 6] [PR-06a] Create labels and Project board skeleton — 定义五态（Inbox / Needs Clarification / In Progress / In Review / Done）及必要标签

#### Validation

- [ ] All three Issue Forms render correctly
- [ ] PR Template has all required sections
- [ ] CODEOWNERS covers `.github/`, `docs/engineering/`, `scripts/governance/`, `specs/`; does NOT name NekoDreamSensei as mandatory reviewer
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 6b — Dispatch State (PR-06b)

**Branch**: `codex/064-phase6b-dispatch-state`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 6a merge

**Intended paths**:
- `.github/dispatches/` [NEW directory]
- `scripts/governance/dispatch.ps1` [NEW]
- `scripts/governance/tests/dispatch.Tests.ps1` [NEW]
- `docs/decisions/ADR-002-dispatch-protocol.md` [NEW]

#### Tasks

- [ ] T206 [Phase 6] [PR-06b] Create `.github/dispatches/` — Dispatch 文件存储目录及示例文件
- [ ] T207 [Phase 6] [PR-06b] Implement `scripts/governance/dispatch.ps1` — Dispatch 状态机（创建/验证/失效/过期）；必须实现每个 Issue 最多一个活跃 dispatch（不区分 driver）；过期 dispatch 不可重新激活；签发新 dispatch 时必须重新验证 base_sha（权威远端 master）、AC hash（规范 AC 字段）、allowed paths
- [ ] T211 [Phase 6] [PR-06b] Create `docs/decisions/ADR-002-dispatch-protocol.md` — Dispatch 协议 ADR
- [ ] T209 [Phase 6] [PR-06b] Write `scripts/governance/tests/dispatch.Tests.ps1` — Dispatch Pester 测试

#### Validation

- [ ] dispatch.ps1 dispatches correctly and detects invalid state transitions
- [ ] dispatch.ps1 enforces at most one active dispatch per Issue regardless of driver
- [ ] dispatch.ps1 rejects reactivation of expired/superseded dispatches
- [ ] All Pester tests pass (≥ 5 tests)
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 6c — Gate (PR-06c)

**Branch**: `codex/064-phase6c-gate`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 6b merge

**Intended paths**:
- `scripts/governance/gate.ps1` [NEW]
- `scripts/governance/tests/gate.Tests.ps1` [NEW]
- `docs/decisions/ADR-003-governance-gate-design.md` [NEW]

#### Tasks

- [ ] T208 [Phase 6] [PR-06c] Implement `scripts/governance/gate.ps1` — PR Gate 检查（Issue/Dispatch 有效性、唯一 PR、AC hash 匹配 versioned canonical acceptance statement、allowed paths 合规、base freshness 确定性验证、governance version）；base freshness 必须验证 dispatch base_sha == 权威远端 master HEAD，且 PR HEAD 从 base_sha 派生；AC hash 必须按 Dispatch Envelope v1 规范化，不能 hash checkbox 列表或整个 Issue body
- [ ] T210 [Phase 6] [PR-06c] Write `scripts/governance/tests/gate.Tests.ps1` — Gate Pester 测试
- [ ] T212 [Phase 6] [PR-06c] Create `docs/decisions/ADR-003-governance-gate-design.md` — Gate 设计 ADR

#### Validation

- [ ] gate.ps1 passes positive tests (valid dispatch) and negative tests (invalid base/AC/path/gov version/stale SHA)
- [ ] gate.ps1 verifies base_sha equals authoritative master via `gh api` (rejects stale local ref)
- [ ] gate.ps1 hashes only canonical AC field, not entire Issue body
- [ ] All Pester tests pass (≥ 5 tests)
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

## Phase 7 — CI 分层修复 (7 PR slices)

**Dependencies**: Phase 6 all slices merged

### Slice 7a — Frontend CI Repair (PR-07a)

**Branch**: `codex/064-phase7a-frontend-ci`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 6 all slices merged

**Intended paths**:
- `.github/workflows/frontend.yml` [MODIFY / REVERT to healthy baseline]

#### Tasks

- [ ] T301 [Phase 7] [PR-07a] Diagnose and fix frontend CI — 修复前端构建/lint 失败，建立基线（在独立 commit 中，不混入业务重构）

#### Validation

- [ ] frontend CI 全绿
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 7b — Backend CI Repair (PR-07b)

**Branch**: `codex/064-phase7b-backend-ci`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 7a merge

**Intended paths**:
- `.github/workflows/backend-lint.yml` [MODIFY / REVERT to healthy baseline]
- `.github/workflows/backend-unit.yml` [MODIFY / REVERT to healthy baseline]

#### Tasks

- [ ] T302 [Phase 7] [PR-07b] Diagnose and fix backend-lint CI — 修复后端 lint 失败
- [ ] T303 [Phase 7] [PR-07b] Diagnose and fix backend-unit CI — 修复后端单元测试失败

#### Validation

- [ ] backend-lint CI 全绿
- [ ] backend-unit CI 全绿
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 7c — CI Summary Check (PR-07c)

**Branch**: `codex/064-phase7c-ci-summary`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 7b merge

**Intended paths**:
- `.github/workflows/ci-summary.yml` [NEW — 始终可判定的 summary check]

#### Tasks

- [ ] T304 [Phase 7] [PR-07c] Create `.github/workflows/ci-summary.yml` — 始终可判定的 summary check，聚合分层结果

#### Validation

- [ ] ci-summary 始终可判定（不跳过，不取消）
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 7d — Contract/Integration (PR-07d)

**Branch**: `codex/064-phase7d-contract-integration`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 7c merge

**Intended paths**:
- `.github/workflows/contract-integration.yml` [NEW]

#### Tasks

- [ ] T305 [Phase 7] [PR-07d] Create `.github/workflows/contract-integration.yml` — Contract / Integration 测试（PostgreSQL、Redis 临时启动）

#### Validation

- [ ] Contract/Integration 测试通过
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 7e — E2E (PR-07e)

**Branch**: `codex/064-phase7e-e2e`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 7d merge

**Intended paths**:
- `.github/workflows/e2e.yml` [MODIFY]

#### Tasks

- [ ] T306 [Phase 7] [PR-07e] Harden `.github/workflows/e2e.yml` — 完整启动 PostgreSQL、Redis、FastAPI、ARQ、Vite，健康检查后运行 Chromium E2E

#### Validation

- [ ] E2E Chromium 测试通过
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 7f — Eval (PR-07f)

**Branch**: `codex/064-phase7f-eval`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Slice 7e merge

**Intended paths**:
- `.github/workflows/eval.yml` [NEW]
- `scripts/governance/ci-health.ps1` [NEW — CI 健康检查辅助脚本]

#### Tasks

- [ ] T307 [Phase 7] [PR-07f] Create `.github/workflows/eval.yml` — 确定性 PR Eval（真实模型 nightly 分离）
- [ ] T308 [Phase 7] [PR-07f] Create `scripts/governance/ci-health.ps1` — CI 健康检查辅助脚本

#### Validation

- [ ] Eval 测试通过（确定性）
- [ ] ci-health.ps1 辅助脚本正确报告 CI 状态
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

### Slice 7g — Required-Check Activation (PR-07g)

**Branch**: `codex/064-phase7g-required-checks`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: ALL of 7a–7f merged AND green on master

**Intended paths**:
- `docs/engineering/` (CI 分层手册)

#### Tasks

- [ ] T309 [Phase 7] [PR-07g] Verify Required Check source binding — 确保 Required Check 绑定 GitHub Actions 来源；Workflow/SOP 变更 MUST 触发 CODEOWNERS Review
- [ ] T310 [Phase 7] [PR-07g] Document CI 分层手册 — 更新 `docs/engineering/` 相关文档，描述分层含义和故障排查

#### Validation

- [ ] Required Check 来源绑定已验证
- [ ] CI 分层手册完整
- [ ] Only activates after all 7a–7f are merged AND green on master
- [ ] `git diff --check` passes

#### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

## Phase 8 — Cursor Automation (PR-08)

**Branch**: `codex/064-phase8-cursor-automation`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 7 ALL slices merged (strict ordering: Phase 8 requires Phase 7)

**Intended paths**:
- `.github/workflows/cursor-automation.yml` [NEW]
- `scripts/governance/cursor-handler.ps1` [NEW]
- `scripts/governance/tests/cursor-handler.Tests.ps1` [NEW]

### Tasks

- [ ] T401 [Phase 8] [PR-08] Create `.github/workflows/cursor-automation.yml` — 监听 Issue 评论（授权真人触发）；输入 Issue 视为不可信数据
- [ ] T402 [Phase 8] [PR-08] Create `scripts/governance/cursor-handler.ps1` — Cursor 自动化处理脚本：
  - 固定 Dispatch snapshot 和 allowed paths
  - 使用 App/webhook 身份（最小权限）
  - 无生产 Secret、无部署、无合并
  - 默认只开 Draft PR
  - Dispatch 幂等（同一个 Issue 不重复创建分支）
- [ ] T403 [Phase 8] [PR-08] Write `scripts/governance/tests/cursor-handler.Tests.ps1` — Cursor 处理器 Pester 测试
- [ ] T404 [Phase 8] [PR-08] Update `docs/engineering/delivery-sop.md` — 加入 Cursor 自动化相关流程
- [ ] T405 [Phase 8] [PR-08] Document stable → webhook 升级路径 — 准备在稳定性验证后实现 Ready-label → webhook 触发（Phase 8 不做）

### Validation

- [ ] Cursor workflow 语法通过 GitHub Actions lint
- [ ] Cursor handler 脚本 Pester 测试通过
- [ ] 输入 Issue 视为不可信数据（脚本验证所有字段）
- [ ] 无生产 Secret、无部署权限、无合并权限
- [ ] 默认打开 Draft PR，不标记 Ready
- [ ] `git diff --check` passes

### Rollback

```bash
git revert -m 1 <merge-sha>
```

Removes cursor automation workflow and handler script.

---

## Phase 9 — Stage-B 与故障演练 (PR-09)

**Branch**: `codex/064-phase9-stageb-drills`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 5, 6, 7, 8 ALL slices merged

**Intended paths**:
- `scripts/governance/stage-b-drills.ps1` [NEW]
- `scripts/governance/tests/stage-b-drills.Tests.ps1` [NEW]
- `docs/engineering/stage-b-drill-results.md` [NEW]
- NO changes to Ruleset — Codex applies Stage-B after acceptance

### Tasks

- [ ] T501 [Phase 9] [PR-09] Create `scripts/governance/stage-b-drills.ps1` — 自动化故障演练脚本，至少覆盖 11 项：
  1. direct push 被拒绝
  2. duplicate trigger 只产生一个有效 Dispatch
  3. handoff 后旧 PR 被 Gate 阻断
  4. Issue AC 编辑导致旧 Dispatch 失败
  5. path escape 被拒绝
  6. Workflow 篡改不能伪造 Required Check
  7. Check 失败、缺失、取消均阻止合并
  8. stale branch 必须更新
  9. automation 看不到生产 Secret
  10. Ruleset drift 会创建治理 Issue
  11. Revert PR 可恢复上一状态
- [ ] T502 [Phase 9] [PR-09] Write `scripts/governance/tests/stage-b-drills.Tests.ps1` — 演练脚本 Pester 测试
- [ ] T503 [Phase 9] [PR-09] Execute and document drill results — 在 `docs/engineering/stage-b-drill-results.md` 中记录通过/失败/跳过项
- [ ] T504 [Phase 9] [PR-09] Prepare Stage-B Ruleset proposal — 描述需启用的严格 Required Checks、conversation resolution、stale approval protection、squash-only、merge 后删除分支；由 Codex 应用（此项操作风险等级 R3，需 Codex 显式批准 + 截图证据）
- [ ] T505 [Phase 9] [PR-09] Create Ruleset drift detection script — 审计脚本比较期望状态快照与 Ruleset 实际状态，发现 drift 自动创建 Issue

### Validation

- [ ] 11 项演练全部运行（允许已知预期失败但必须记录）
- [ ] 演练结果文档完整
- [ ] Stage-B 提案具体且可执行
- [ ] Ruleset drift 检测脚本经过验证（正向/负向）
- [ ] `git diff --check` passes

### Rollback

```bash
git revert -m 1 <merge-sha>
```

---

## Phase 10 — 团队验收与 Reconciliation (PR-10)

**Branch**: `codex/064-phase10-acceptance`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 5, 6, 7, 8, 9 ALL slices merged; Stage-B active

**Intended paths**:
- `docs/engineering/acceptance-checklist.md` [NEW]
- `docs/engineering/stage-b-drill-results.md` [MODIFY — final pass]
- `docs/engineering/` (related evidence files)
- `docs/evidence/064-delivery-governance/` [NEW evidence tree]
- `docs/evidence/064-delivery-governance/sop-walkthrough.html` [NEW — 自包含证据素材]

### Tasks

- [ ] T601 [Phase 10] [PR-10] Create `docs/engineering/acceptance-checklist.md` — 验收 checklist 覆盖 Fresh Clone、客户端加载规则、Dry-run Issue 闭环、dirty worktree reconciliation
- [ ] T602 [Phase 10] [PR-10] Fresh Clone 验证 — 在另一台机器或全新 clone 中拉取仓库，验证：
  - AGENTS.md / CLAUDE.md / .cursor/rules 可读
  - SOP 和 Onboarding 文档存在且可理解
  - Claude `/memory` 与 Cursor Project Rules 已加载
- [ ] T603 [Phase 10] [PR-10] 完成 Dry-run Issue 完整闭环 — 使用专用 Dry-run Issue 测试完整流程：
  Spec（已存在）→ Issue（创建）→ Dispatch（分配）→ Branch → Draft PR → Gate 通过 → Review（模拟）→ Squash Merge
- [ ] T604 [Phase 10] [PR-10] 历史 Issues 逐个验证 — 不批量关闭 Issue；对每个历史 open Issue 判断是否需要关闭并添加注释
- [ ] T605 [Phase 10] [PR-10] 治理 Requirement 标记 done — 只在实现、验证、设置快照和第二开发者演练证据都存在时更新 `requirements-status.md` 状态
- [ ] T606 [Phase 10] [PR-10] 更新 `specs/README.md` — 将 REQ-064 状态改为 `done`
- [ ] T607 [Phase 10] [PR-10] 创建 `docs/evidence/064-delivery-governance/sop-walkthrough.html` — 自包含 HTML 素材，包含：
  - 每步 SOP 截图（嵌入 base64）
  - 时间戳
  - 确切 URL 或路径
  - 操作者（actor）
  - 输入条件（inputs）
  - 门禁结果（gate result）
  - 证据引用（evidence reference）
  - 回滚命令（rollback command）
  - 隐私脱敏（无密码/token/cookie/收件箱内容）
  - 覆盖：Spec → Issue → Dispatch → clean external worktree/branch → preflight → commit → Draft PR → CI → review 或显式 Owner PR-only 绕过 → squash merge → master 验证
- [ ] T608 [Phase 10] [PR-10] Dirty worktree 所有权分类 — 对 `D:\Project\eGGG` 的全部 dirty worktree 条目逐条分类：可经 Dispatch/PR 发布的规范工作、应归档到仓库外部的文件、经批准的忽略项、保留的具名用户工作
- [ ] T609 [Phase 10] [PR-10] Dirty worktree 有界路由 — 对分类后的条目执行有界路由：规范工作经 Dispatch/PR 发布；外部文件归档到仓库外；忽略项批准并补 `.gitignore`；具名用户工作保留并记录
- [ ] T610 [Phase 10] [PR-10] Phase 10 最终证明 — 提供零未归类脏条目的证明（zero unexplained dirty entries），使用 `git status --porcelain` 验证，不使用 `git reset --hard`、`git clean -fd`、强制 stash、批量猜测或覆盖用户工作

### Validation

- [ ] Fresh Clone 验证通过
- [ ] Dry-run Issue 完整闭环完成
- [ ] 历史 Issues 逐个处理（不批量关闭）
- [ ] 治理 Requirement 状态反映真实完成情况
- [ ] `docs/evidence/064-delivery-governance/sop-walkthrough.html` 存在且完整覆盖 SOP 流程
- [ ] HTML 素材无密码/token/cookie 或收件箱内容
- [ ] `D:\Project\eGGG` dirty worktree 零未归类条目
- [ ] 验收 checklist 所有项完成
- [ ] `git diff --check` passes

### Rollback

```bash
git revert -m 1 <merge-sha>
```

Removes acceptance checklist, evidence files, and HTML walkthrough. Dry-run Issue and its merged PR remain in history.

---

## Summary View

| Phase | PR | Branch Pattern | Dependencies | Key Files | Rollback |
|---|---|---|---|---|---|
| 5a — SOP/ADR | PR-05a | `codex/064-phase5a-*` | Phase 4 | SOP, Onboarding, ADR-001 | `git revert` |
| 5b — Adapters | PR-05b | `codex/064-phase5b-*` | 5a | AGENTS.md, CLAUDE.md, .cursor | `git revert` |
| 5c — Runtime | PR-05c | `codex/064-phase5c-*` | 5b | .gitignore, audit reports | `git revert` |
| 6a — Intake Metadata | PR-06a | `codex/064-phase6a-*` | Phase 5 all | Issue Forms, PR Template, CODEOWNERS | `git revert` |
| 6b — Dispatch State | PR-06b | `codex/064-phase6b-*` | 6a | dispatch.ps1, ADR-002 | `git revert` |
| 6c — Gate | PR-06c | `codex/064-phase6c-*` | 6b | gate.ps1, ADR-003 | `git revert` |
| 7a — Frontend CI | PR-07a | `codex/064-phase7a-*` | Phase 6 all | frontend.yml | `git revert` |
| 7b — Backend CI | PR-07b | `codex/064-phase7b-*` | 7a | backend-lint.yml, backend-unit.yml | `git revert` |
| 7c — Summary Check | PR-07c | `codex/064-phase7c-*` | 7b | ci-summary.yml | `git revert` |
| 7d — Contract/Integration | PR-07d | `codex/064-phase7d-*` | 7c | contract-integration.yml | `git revert` |
| 7e — E2E | PR-07e | `codex/064-phase7e-*` | 7d | e2e.yml | `git revert` |
| 7f — Eval | PR-07f | `codex/064-phase7f-*` | 7e | eval.yml, ci-health.ps1 | `git revert` |
| 7g — Required Checks | PR-07g | `codex/064-phase7g-*` | 7a–7f all green | CI docs | `git revert` |
| 8 — Cursor Automation | PR-08 | `codex/064-phase8-*` | Phase 7 all | Automation workflow, handler | `git revert` |
| 9 — Stage-B Drills | PR-09 | `codex/064-phase9-*` | 5+6+7+8 all | Drill scripts, results | `git revert` |
| 10 — Acceptance | PR-10 | `codex/064-phase10-*` | 5+6+7+8+9 all | Checklist, evidence, HTML walkthrough | `git revert` |

## Task Count Summary

**Total tasks: 52** (Phase 5: 9, Phase 6: 13, Phase 7: 10, Phase 8: 5, Phase 9: 5, Phase 10: 10)

All 29 FR (FR-001 through FR-029) and 9 SC (SC-001 through SC-009) have corresponding task entries and requirements-status rows.
