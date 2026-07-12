# Tasks: 跨应用交付治理 (REQ-064)

**Input**: Spec document from `/specs/064-delivery-governance/`

**Prerequisites**: plan.md (required), spec.md (required), contracts/

**Organization**: Phases 5–10, each phase = one independent PR. Execute in order after Phase 4 acceptance.

**Format**: `[TXXX] [Phase N] [PR-0N] Description`

- Each Phase is one independent reviewable rollback-safe PR
- Dependencies: previous phase PR must be merged
- Intended paths listed per task
- Validation: required checks per PR
- Rollback: `git revert -m 1 <merge-sha>`

---

## Phase 5 — 共享规则与工具适配 (PR-05)

**Branch**: `codex/065-governance-phase5-rules`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 4 merge

**Intended paths**:
- `docs/engineering/delivery-sop.md` [NEW]
- `docs/engineering/team-onboarding.md` [NEW]
- `docs/decisions/ADR-001-multi-client-delivery-governance.md` [NEW]
- `AGENTS.md` [MODIFY]
- `CLAUDE.md` [NEW]
- `.claude/settings.json` [MODIFY if tracked]
- `.cursor/rules/agent-delivery.mdc` [NEW]
- `.gitignore` [MODIFY for runtime files]
- `docs/engineering/` (relevant existing files)

### Tasks

- [ ] T101 [Phase 5] Create `docs/engineering/delivery-sop.md` — 唯一交付 SOP，覆盖完整流程：Spec → Issue → Dispatch → 分支/worktree → Draft PR → CI → Review → Squash Merge
- [ ] T102 [Phase 5] Create `docs/engineering/team-onboarding.md` — 指导开发者在 Fresh Clone 中配置客户端并完成首个 PR
- [ ] T103 [Phase 5] Create `docs/decisions/ADR-001-multi-client-delivery-governance.md` — 记录多客户端交付治理的架构决策
- [ ] T104 [Phase 5] Simplify `AGENTS.md` — 精简为公共规则，不重复 SOP 内容；通过引用方式导入
- [ ] T105 [Phase 5] Create `CLAUDE.md` — 通过 `@AGENTS.md` / SOP 导入公共规则；仅确定性 Hook 进入 `.claude/settings.json`
- [ ] T106 [Phase 5] Create `.cursor/rules/agent-delivery.mdc` — Cursor 薄适配，不复制 SOP
- [ ] T107 [Phase 5] Audit tracked Claude runtime/local files — 识别 `.claude/settings.local.json`、`.claude/state.json`、memory 文件；备份耐久知识；取消追踪；补充 `.gitignore`
- [ ] T108 [Phase 5] Scan Git history for secrets — 使用 `git log -p` 或专用扫描工具；发现后通知 Owner 轮换（不自已轮换）
- [ ] T109 [Phase 5] Create/update `.gitignore` — 确保 Claude/Cursor runtime 文件不被跟踪

### Validation

- [ ] All SOP steps are present and internally consistent
- [ ] `git diff --check` passes
- [ ] No tracked Claude/Cursor runtime files remain in index
- [ ] Secret scan completed (even if no secrets found)
- [ ] Clients (AGENTS.md, CLAUDE.md, .cursor) reference common source, don't duplicate

### Rollback

```bash
git revert -m 1 <merge-sha>
```

Restores AGENTS.md to pre-Phase 5 state, removes new files. Must verify `.gitignore` revert doesn't re-track runtime files incorrectly.

---

## Phase 6 — Intake、Dispatch 与 Governance Gate (PR-06)

**Branch**: `codex/066-governance-phase6-intake`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 5 merge

**Intended paths**:
- `.github/ISSUE_TEMPLATE/bug.yml` [NEW]
- `.github/ISSUE_TEMPLATE/feature.yml` [NEW]
- `.github/ISSUE_TEMPLATE/agent-task.yml` [NEW]
- `.github/pull_request_template.md` [NEW]
- `.github/CODEOWNERS` [NEW]
- `.github/dispatches/` [NEW directory]
- `scripts/governance/gate.ps1` [NEW]
- `scripts/governance/dispatch.ps1` [NEW]
- `scripts/governance/tests/gate.Tests.ps1` [NEW]
- `scripts/governance/tests/dispatch.Tests.ps1` [NEW]
- `docs/decisions/ADR-002-dispatch-protocol.md` [NEW]
- `docs/decisions/ADR-003-governance-gate-design.md` [NEW]

### Tasks

- [ ] T201 [Phase 6] Create `.github/ISSUE_TEMPLATE/bug.yml` — Bug 报告 Issue Form，含 dispatch_id、base_sha、AC hash、allowed paths 字段
- [ ] T202 [Phase 6] Create `.github/ISSUE_TEMPLATE/feature.yml` — Feature 需求 Issue Form
- [ ] T203 [Phase 6] Create `.github/ISSUE_TEMPLATE/agent-task.yml` — Agent 自动化任务 Issue Form
- [ ] T204 [Phase 6] Create `.github/pull_request_template.md` — PR 模板，含 Refs #N、base/dispatch、files、checks、risks、rollback 章节
- [ ] T205 [Phase 6] Create `.github/CODEOWNERS` — 定义治理关键路径的 Review 分配
- [ ] T206 [Phase 6] Create `.github/dispatches/` — Dispatch 文件存储目录及示例文件
- [ ] T207 [Phase 6] Implement `scripts/governance/dispatch.ps1` — Dispatch 状态机（创建/验证/失效/过期）
- [ ] T208 [Phase 6] Implement `scripts/governance/gate.ps1` — PR Gate 检查（Issue/Dispatch 有效性、唯一 PR、AC hash、allowed paths、base freshness、governance version）
- [ ] T209 [Phase 6] Write `scripts/governance/tests/dispatch.Tests.ps1` — Dispatch Pester 测试
- [ ] T210 [Phase 6] Write `scripts/governance/tests/gate.Tests.ps1` — Gate Pester 测试
- [ ] T211 [Phase 6] Create `docs/decisions/ADR-002-dispatch-protocol.md` — Dispatch 协议 ADR
- [ ] T212 [Phase 6] Create `docs/decisions/ADR-003-governance-gate-design.md` — Gate 设计 ADR
- [ ] T213 [Phase 6] Create labels and Project board skeleton — 定义五态（Inbox / Needs Clarification / In Progress / In Review / Done）及必要标签

### Validation

- [ ] All three Issue Forms render correctly
- [ ] PR Template has all required sections
- [ ] CODEOWNERS covers `.github/`, `docs/engineering/`, `scripts/governance/`, `specs/`
- [ ] dispatch.ps1 dispatches correctly and detects invalid state transitions
- [ ] gate.ps1 passes positive tests (valid dispatch) and negative tests (invalid base/AC/path/gov version)
- [ ] All Pester tests pass (dispatch + gate ≥ 5 tests each)

### Rollback

```bash
git revert -m 1 <merge-sha>
```

Removes all `.github/` form/template changes, reverts CODEOWNERS, removes scripts. Dispatch files in `.github/dispatches/` will be absent (no active dispatches yet).

---

## Phase 7 — CI 分层 (PR-07)

**Branch**: `codex/067-governance-phase7-ci`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 6 merge

**Intended paths**:
- `.github/workflows/frontend.yml` [MODIFY / REVERT to healthy baseline]
- `.github/workflows/backend-lint.yml` [MODIFY / REVERT to healthy baseline]
- `.github/workflows/backend-unit.yml` [MODIFY / REVERT to healthy baseline]
- `.github/workflows/contract-integration.yml` [NEW]
- `.github/workflows/e2e.yml` [MODIFY]
- `.github/workflows/eval.yml` [NEW]
- `scripts/governance/ci-health.ps1` [NEW — CI 健康检查辅助脚本]
- `.github/workflows/ci-summary.yml` [NEW — 始终可判定的 summary check]

### Tasks

- [ ] T301 [Phase 7] Diagnose and fix frontend CI — 修复前端构建/lint 失败，建立基线（在独立 commit 中，不混入业务重构）
- [ ] T302 [Phase 7] Diagnose and fix backend-lint CI — 修复后端 lint 失败
- [ ] T303 [Phase 7] Diagnose and fix backend-unit CI — 修复后端单元测试失败
- [ ] T304 [Phase 7] Create `.github/workflows/ci-summary.yml` — 始终可判定的 summary check，聚合分层结果
- [ ] T305 [Phase 7] Create `.github/workflows/contract-integration.yml` — Contract / Integration 测试（PostgreSQL、Redis 临时启动）
- [ ] T306 [Phase 7] Harden `.github/workflows/e2e.yml` — 完整启动 PostgreSQL、Redis、FastAPI、ARQ、Vite，健康检查后运行 Chromium E2E
- [ ] T307 [Phase 7] Create `.github/workflows/eval.yml` — 确定性 PR Eval（真实模型 nightly 分离）
- [ ] T308 [Phase 7] Create `scripts/governance/ci-health.ps1` — CI 健康检查辅助脚本
- [ ] T309 [Phase 7] Verify Required Check source binding — 确保 Required Check 绑定 GitHub Actions 来源
- [ ] T310 [Phase 7] Document CI 分层手册 — 更新 `docs/engineering/` 相关文档，描述分层含义和故障排查

### Validation

- [ ] frontend CI 全绿
- [ ] backend-lint CI 全绿
- [ ] backend-unit CI 全绿
- [ ] ci-summary 始终可判定
- [ ] Contract/Integration 测试通过
- [ ] E2E Chromium 测试通过
- [ ] Eval 测试通过（确定性）
- [ ] Required Check 来源绑定已验证

### Rollback

```bash
git revert -m 1 <merge-sha>
```

Reverts all workflow changes to pre-Phase 7 state. Note: if CI was red before and fixes are reverted, CI returns to red — this is expected and not a rollback failure.

---

## Phase 8 — Cursor Automation (PR-08)

**Branch**: `codex/068-governance-phase8-automation`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 6 merge (Phase 7 recommended but not required for automation logic)

**Intended paths**:
- `.github/workflows/cursor-automation.yml` [NEW]
- `scripts/governance/cursor-handler.ps1` [NEW]
- `scripts/governance/tests/cursor-handler.Tests.ps1` [NEW]

### Tasks

- [ ] T401 [Phase 8] Create `.github/workflows/cursor-automation.yml` — 监听 Issue 评论（授权真人触发）；输入 Issue 视为不可信数据
- [ ] T402 [Phase 8] Create `scripts/governance/cursor-handler.ps1` — Cursor 自动化处理脚本：
  - 固定 Dispatch snapshot 和 allowed paths
  - 使用 App/webhook 身份（最小权限）
  - 无生产 Secret、无部署、无合并
  - 默认只开 Draft PR
  - Dispatch 幂等（同一个 Issue 不重复创建分支）
- [ ] T403 [Phase 8] Write `scripts/governance/tests/cursor-handler.Tests.ps1` — Cursor 处理器 Pester 测试
- [ ] T404 [Phase 8] Update `docs/engineering/delivery-sop.md` — 加入 Cursor 自动化相关流程
- [ ] T405 [Phase 8] Document stable → webhook 升级路径 — 准备在稳定性验证后实现 Ready-label → webhook 触发（Phase 8 不做）

### Validation

- [ ] Cursor workflow 语法通过 GitHub Actions lint
- [ ] Cursor handler 脚本 Pester 测试通过
- [ ] 输入 Issue 视为不可信数据（脚本验证所有字段）
- [ ] 无生产 Secret、无部署权限、无合并权限
- [ ] 默认打开 Draft PR，不标记 Ready

### Rollback

```bash
git revert -m 1 <merge-sha>
```

Removes cursor automation workflow and handler script. No active Cursor workflows will be running.

---

## Phase 9 — Stage-B 与故障演练 (PR-09)

**Branch**: `codex/069-governance-phase9-stageb`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 5, 6, 7, 8 all merged

**Intended paths**:
- `scripts/governance/stage-b-drills.ps1` [NEW]
- `scripts/governance/tests/stage-b-drills.Tests.ps1` [NEW]
- `docs/engineering/stage-b-drill-results.md` [NEW]
- NO changes to Ruleset — Codex applies Stage-B after acceptance

### Tasks

- [ ] T501 [Phase 9] Create `scripts/governance/stage-b-drills.ps1` — 自动化故障演练脚本，至少覆盖 11 项：
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
- [ ] T502 [Phase 9] Write `scripts/governance/tests/stage-b-drills.Tests.ps1` — 演练脚本 Pester 测试
- [ ] T503 [Phase 9] Execute and document drill results — 在 `docs/engineering/stage-b-drill-results.md` 中记录通过/失败/跳过项
- [ ] T504 [Phase 9] Prepare Stage-B Ruleset proposal — 描述需启用的严格 Required Checks、conversation resolution、stale approval protection、squash-only、merge 后删除分支；由 Codex 应用
- [ ] T505 [Phase 9] Create Ruleset drift detection script — 审计脚本比较期望状态快照与 Ruleset 实际状态，发现 drift 自动创建 Issue

### Validation

- [ ] 11 项演练全部运行（允许已知预期失败但必须记录）
- [ ] 演练结果文档完整
- [ ] Stage-B 提案具体且可执行
- [ ] Ruleset drift 检测脚本经过验证（正向/负向）

### Rollback

```bash
git revert -m 1 <merge-sha>
```

Removes drill scripts and results document. Stage-B if applied by Codex separately would need separate rollback through Ruleset UI.

---

## Phase 10 — 团队验收 (PR-10)

**Branch**: `codex/070-governance-phase10-acceptance`
**Driver**: claude-code (implementation), codex (acceptance)
**Dependencies**: Phase 5, 6, 7, 8, 9 all merged; Stage-B active

**Intended paths**:
- `docs/engineering/acceptance-checklist.md` [NEW]
- `docs/engineering/stage-b-drill-results.md` [MODIFY — final pass]
- `docs/engineering/` (related evidence files)
- `docs/evidence/064-delivery-governance/` [NEW evidence tree]

### Tasks

- [ ] T601 [Phase 10] Create `docs/engineering/acceptance-checklist.md` — 验收 checklist 覆盖 Fresh Clone、客户端加载规则、Dry-run Issue 闭环
- [ ] T602 [Phase 10] Fresh Clone 验证 — 在另一台机器或全新 clone 中拉取仓库，验证：
  - AGENTS.md / CLAUDE.md / .cursor/rules 可读
  - SOP 和 Onboarding 文档存在且可理解
  - Claude `/memory` 与 Cursor Project Rules 已加载
- [ ] T603 [Phase 10] 完成 Dry-run Issue 完整闭环 — 使用专用 Dry-run Issue 测试完整流程：
  Spec（已存在）→ Issue（创建）→ Dispatch（分配）→ Branch → Draft PR → Gate 通过 → Review（模拟）→ Squash Merge
- [ ] T604 [Phase 10] 历史 Issues 逐个验证 — 不批量关闭 Issue；对每个历史 open Issue 判断是否需要关闭并添加注释
- [ ] T605 [Phase 10] 治理 Requirement 标记 done — 只在实现、验证、设置快照和第二开发者演练证据都存在时更新 `requirements-status.md` 状态
- [ ] T606 [Phase 10] 更新 `specs/README.md` — 将 REQ-064 状态改为 `done`
- [ ] T607 [Phase 10] HTML 截图 walkthrough 最终素材 — 准备已收集的截图和步骤描述；由 Codex 做最终视觉 QA

### Validation

- [ ] Fresh Clone 验证通过
- [ ] Dry-run Issue 完整闭环完成
- [ ] 历史 Issues 逐个处理（不批量关闭）
- [ ] 治理 Requirement 状态反映真实完成情况
- [ ] 验收 checklist 所有项完成

### Rollback

```bash
git revert -m 1 <merge-sha>
```

Removes acceptance checklist and evidence files. Dry-run Issue and its merged PR remain in history.

---

## Summary View

| Phase | PR | Branch Pattern | Dependencies | Key Files | Rollback |
|---|---|---|---|---|---|
| 5 — Rules & Tools | PR-05 | `codex/065-*` | Phase 4 | SOP, ADR, AGENTS.md, CLAUDE.md, .cursor | `git revert` |
| 6 — Intake & Gate | PR-06 | `codex/066-*` | Phase 5 | Issue Forms, PR Template, CODEOWNERS, scripts | `git revert` |
| 7 — CI Layering | PR-07 | `codex/067-*` | Phase 6 | Workflows, ci-summary | `git revert` |
| 8 — Cursor Automation | PR-08 | `codex/068-*` | Phase 6 | Automation workflow, handler | `git revert` |
| 9 — Stage-B Drills | PR-09 | `codex/069-*` | 5+6+7+8 | Drill scripts, results | `git revert` |
| 10 — Acceptance | PR-10 | `codex/070-*` | 5+6+7+8+9 | Acceptance checklist, evidence | `git revert` |