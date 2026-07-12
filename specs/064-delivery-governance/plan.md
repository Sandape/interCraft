# Implementation Plan: 跨应用交付治理 (REQ-064)

**Branch**: `064-delivery-governance` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/064-delivery-governance/spec.md`

## Summary

将 InterCraft 从 "SpecKit 存在但变更直入 master" 迭代为标准化交付流水线。共六个实施阶段（Phase 5–10），每个阶段为独立可审查可回滚 PR，按原始十阶段顺序执行。

治理核心承诺：
- 每个变更经过 `Spec → Issue → Dispatch → 独立分支/worktree → Draft PR → CI → 真人非作者 Review → Squash Merge`
- 自动化门禁确保同一 Issue 最多一个有效 PR
- Dispatch 固定 dispatch_id、driver、base SHA、AC hash、allowed paths
- 所有治理脚本 fail-closed

## Technical Context

**Language/Version**: TypeScript (React 18), Python 3.12, YAML, Markdown, PowerShell (Windows), Bash (Linux)

**Resolved Dependencies**: 沿用仓库现有工具链 — gh CLI, git, PowerShell 5.1+, Node.js, Python 3.12

**Dependency Support**: 无新增核心依赖；使用的 CLI 工具均已存在于开发环境

**Storage**: 治理状态存储在 `.github/dispatches/`（JSON 或 YAML 文件），Gate 配置存储在 `scripts/governance/`

**Testing**: Pester（PowerShell 测试框架，已用于 preflight.Tests.ps1）；CI 检查通过 GitHub Actions

**Target Platform**: 仓库基础设施（`.github/`、`docs/engineering/`、`scripts/governance/`、客户端规则文件）

**Project Type**: 治理基础设施

**Constraints**:
- 每个 PR 单一关注点，不跨阶段合并
- 不修改产品代码、CI Workflow 语法、Ruleset、客户端配置文件、`.specify/feature.json`
- 不合并、不批准、不关闭 Issue、不修改仓库设置
- 不读取或写入生产 Secret

**Risk Classification**: **R3**（Constitution 定义外部副作用为 R2、权限/Ruleset 边界变更为 R3；特征整体涉及 Ruleset 变更和自动化写入，最高风险 R3）

**Operation Risk Matrix**:
| Operation | Risk |
|---|---|
| 治理文档和规范创建 | R0 |
| 客户端适配文件（AGENTS.md, CLAUDE.md, .cursor/rules/） | R1 |
| 自动化 Gate 和 Dispatch 脚本 | R1 |
| CI 分层修复 | R1（不影响生产数据） |
| 自动化 bot 开 PR、写入分支、合并操作 | R2（外部副作用） |
| Ruleset 突变/绕过政策变更 | R3（权限/Ruleset 边界变更） |
| 直接推送 master | forbidden |

**Execution Model**: 手工创建 PR（治理负责人）+ GitHub Actions（CI）+ GitHub App（Cursor 自动化）

**External Dependencies**: GitHub API（Issue/PR/Ruleset）、GitHub Actions（CI）、Playwright（E2E 测试，Phase 7）

**Observability & Privacy**: 治理操作记录在 PR 描述、Issue 评论和提交消息中；不涉及用户数据

**Migration & Rollout**: 每个 PR 独立可回滚；Phase 9 演练通过后启用 Stage-B；无数据库迁移

**Operational Release Unit**: `.github/`、`docs/engineering/`、`scripts/governance/`、`AGENTS.md`、`CLAUDE.md`、`.cursor/rules/`

## Constitution Check

*SCREEN before Phase 0; re-check after Phase 1 design.*

| Gate | Applicability / inherited control | Pre-screen | Post-design | Evidence link |
|---|---|---|---|---|
| Boundaries & composition roots | 治理文件和脚本不触及产品代码 | CLEAR | PASS | Task paths |
| Typed contracts & authorization | Dispatch envelope, Gate contract, Handoff invariants | CLEAR | PASS | [contracts/](./contracts/) |
| Async, transactions & process isolation | 治理变更同步提交，无需事务 | CLEAR | PASS | N/A |
| Durable dispatch & concurrency ownership | Dispatch 文件化 + concurrency key | CLEAR | PASS | dispatch-envelope contract |
| Agent safety & data lifecycle | Cursor bot 无生产 Secret，不部署不合并 | CLEAR | PASS | spec FR-021/FR-020 |
| Test-first & evaluation | Pester tests for Gate; CI checks | CLEAR | PASS | preflight.Tests.ps1 |
| Observability, release & dependency support | PR 记录 + GitHub API | CLEAR | PASS | SOP / PR Template |

## Project Structure

### Documentation (this feature)

```text
specs/064-delivery-governance/
├── plan.md                     # This file
├── spec.md
├── tasks.md                    # All phases 5-10
├── requirements-status.md
├── README.md
└── contracts/
    ├── dispatch-envelope.md
    ├── governance-state-gate.md
    └── handoff-invariants.md
```

### Governance Files (future phases, repository root)

```text
docs/engineering/
├── delivery-sop.md             # [Phase 5] 唯一交付 SOP
├── team-onboarding.md          # [Phase 5] 团队上手指南
├── multi-client-governance-plan.html  # [Existing] HTML walkthrough plan
└── governance-implementation-handoff-prompt.md  # [Existing] 治理施工交接 Prompt

docs/decisions/
├── ADR-001-multi-client-delivery-governance.md   # [Phase 5] 治理 ADR
├── ADR-002-dispatch-protocol.md                  # [Phase 6] Dispatch 协议 ADR
└── ADR-003-governance-gate-design.md             # [Phase 6] Gate 设计 ADR

AGENTS.md                      # [Phase 5] 精简公共规则
CLAUDE.md                      # [Phase 5] Claude Code 适配
.claude/settings.json          # [Phase 5] Hook 配置（经 Review）
.cursor/rules/agent-delivery.mdc  # [Phase 5] Cursor 适配

.github/
├── ISSUE_TEMPLATE/            # [Phase 6] Bug, Feature, Agent Task
├── pull_request_template.md   # [Phase 6] PR Template
├── CODEOWNERS                 # [Phase 6] 代码审查分配
└── dispatches/                # [Phase 6] Dispatch 文件存储

scripts/governance/
├── preflight.ps1              # [Phase 3 done] 预检
├── tests/
│   └── preflight.Tests.ps1    # [Phase 3 done] 预检测试
├── gate.ps1                   # [Phase 6] PR Gate
├── dispatch.ps1               # [Phase 6] Dispatch 状态机
└── tests/
    ├── preflight.Tests.ps1    # [Phase 3 done]
    ├── gate.Tests.ps1         # [Phase 6]
    └── dispatch.Tests.ps1     # [Phase 6]
```

## Deviation Register

无 APPROVED DEVIATION。所有阶段按原始十阶段顺序执行，不合并、不跳过。
