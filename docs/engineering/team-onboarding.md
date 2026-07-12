# Team Onboarding: InterCraft Delivery Governance

**Your guide to finding canonical rules, creating an external workspace,
running preflight, and completing your first PR.**

| Field | Value |
|---|---|
| Document | `docs/engineering/team-onboarding.md` |
| Reference | [Delivery SOP](./delivery-sop.md) — read this first for the full workflow |
| Status | Phase 5a — onboarding guide; adapters (Phase 5b) pending |

---

## Table of Contents

1. [Before You Start](#1-before-you-start)
2. [For All Developers](#2-for-all-developers)
3. [For Codex](#3-for-codex)
4. [For Claude Code](#4-for-claude-code)
5. [For Cursor](#5-for-cursor)
6. [For Cursor Automation](#6-for-cursor-automation)
7. [For Human Developers](#7-for-human-developers)
8. [First Dry-Run](#8-first-dry-run)
9. [Troubleshooting](#9-troubleshooting)
10. [When to Stop & Escalate](#10-when-to-stop--escalate)

---

## 1. Before You Start

### 1.1 Prerequisites

| Tool | Version | Check |
|---|---|---|
| Git | 2.40+ | `git --version` |
| GitHub CLI (`gh`) | 2.40+ | `gh --version` |
| PowerShell | 5.1+ (Windows) / 7+ (other) | `pwsh --version` |
| Node.js | 20.x or 22.x | `node --version` |
| Python | 3.12.x | `python --version` |
| uv | 0.4+ | `uv --version` |

### 1.2 Authentication

```bash
gh auth status
# If not logged in:
gh auth login
```

You need at least **write** access to the
[Sandape/interCraft](https://github.com/Sandape/interCraft) repository.

> **Never store credentials in repository files, Issue comments, or PR bodies.**
> Use `gh auth` or GitHub CLI for authenticated operations.

---

## 2. For All Developers

### 2.1 Find the Canonical Rules

The single source of truth for delivery workflow is:

1. **[Delivery SOP](./delivery-sop.md)** — the complete normative workflow.
   Read this first. All client rules reference this document; they do not
   duplicate it.
2. **`AGENTS.md`** (at repository root) — routing layer for AI agents.
   Points to the active feature and specs index.
3. **`specs/README.md`** — requirements status index with all feature entries.
4. **`docs/README.md`** — documentation navigation hub.

**Hierarchy**: If a client rule contradicts the SOP, the SOP prevails.

### 2.2 Create an External Workspace

Never work directly in a clone that has uncommitted changes or a dirty
worktree. Always use a fresh clone or a dedicated git worktree:

```bash
# Option A: Fresh clone
cd /path/to/workspace
git clone https://github.com/Sandape/interCraft.git interCraft-work
cd interCraft-work

# Option B: Worktree from your existing clone
cd /path/to/primary/clone
git worktree add ../interCraft-phase5a codex/064-phase5a-sop-adr
cd ../interCraft-phase5a
```

### 2.3 Understand the Flow

Every change must follow this pipeline:

```
Spec → Issue → Dispatch → External Clone/Worktree + codex/ Branch
→ Preflight → Bounded Change → Test/Evidence → Intentional Commit
→ Draft PR with Refs #N → CI → Review → Squash Merge → Master Verification
→ Closure
```

See the [Delivery SOP](./delivery-sop.md) for complete step details.

### 2.4 Run Preflight

Before every commit:

```bash
pwsh -File scripts/governance/preflight.ps1
```

- Exit code 0 = ready to commit.
- Non-zero exit = stop and fix the reported issue.

### 2.5 Follow Issue / Dispatch / PR

1. **Issue**: Find or create the Issue. It must have `dispatch_id`, `base_sha`,
   `AC hash`, `allowed_paths`, and a `## Canonical Acceptance Statement`
   heading.
2. **Dispatch**: Check that a dispatch exists (in `.github/dispatches/` or
   declared in the Issue). If not, contact Codex.
3. **PR**: Open a Draft PR with `Refs #N`, dispatch metadata, checks
   performed, risk assessment, and rollback command.
4. **Review**: Request a human non-author reviewer. Address feedback.
5. **Merge**: Squash merge into `master`. Never direct-push.

### 2.6 Verify Loaded Client Rules

After cloning and opening the repository in your client:

- **Codex / Claude Code**: The tool should automatically load `AGENTS.md` and
  any `CLAUDE.md` at repository root. Verify by asking: "What is my delivery
  workflow?"
- **Cursor**: Cursor should load `.cursor/rules/` files. Verify by checking
  that Cursor's rule indicator shows agent-delivery rules active.
- **All clients**: No client should suggest direct-pushing to `master`. If one
  does, it has not loaded the correct rules — stop and troubleshoot.

---

## 3. For Codex

Codex is the supervising acceptance authority. Your key actions:

1. **Verify the base**: Before dispatching work, confirm the authoritative
   remote `master` SHA:
   ```bash
   gh api repos/Sandape/interCraft/git/ref/heads/master --jq '.object.sha'
   ```
2. **Issue dispatches**: Create dispatch envelopes for each Issue to be
   implemented. Document in `.github/dispatches/<dispatch_id>.json` (Phase 6
   onward) or in the Issue body.
3. **Acceptance verification**: After a PR merges, verify:
   - The merge SHA is reachable from `master`.
   - AC criteria are met.
   - Evidence exists.
   - `requirements-status.md` is updated.
4. **Stage-B activation**: Only after Phase 9 drills pass. Not yet active.

**Currently loaded rules** (via `AGENTS.md`): The AGENTS.md file at repository
root points Codex to:
   - `specs/README.md` — requirements index
   - Active feature README — current task context
   - `docs/testing/README.md` — test guidance
   - `docs/architecture/source-map.md` — source layout

See [Delivery SOP §3](./delivery-sop.md#3-canonical-flow) for the full flow.

---

## 4. For Claude Code

### 4.1 Setup

Claude Code will be configured with a `CLAUDE.md` (Phase 5b, future) at
repository root. That file will:

- Reference `AGENTS.md` and the [Delivery SOP](./delivery-sop.md) for rules.
- Contain only deterministic hooks in `.claude/settings.json` (Phase 5b,
  future).

### 4.2 Current Procedure (Pre-Phase 5b)

Until `CLAUDE.md` and `.claude/settings.json` are created:

1. Start a new Claude Code session in your external workspace.
2. Read `AGENTS.md` first — it has the canonical navigation.
3. Read the [Delivery SOP](./delivery-sop.md) and these onboarding instructions.
4. Read the relevant spec for your task from `specs/<id>-<feature>/`.

### 4.3 Key Constraints

- **Preflight before commit**: Always run `pwsh -File scripts/governance/preflight.ps1`.
- **Branch naming**: Prefix with `codex/`, `claude-code/`, or `human/`.
- **Commit messages**: Include `Refs #N`.
- **Draft PR**: Open as Draft, not Ready for Review.
- **Never direct-push master.**

---

## 5. For Cursor

### 5.1 Setup

Cursor will be configured with a project rule (Phase 5b, future) at
`.cursor/rules/agent-delivery.mdc`. That rule will:

- Be a thin adapter referencing the [Delivery SOP](./delivery-sop.md).
- Not duplicate SOP content.
- Provide Cursor-specific instructions for rule loading and execution.

### 5.2 Current Procedure (Pre-Phase 5b)

Until `.cursor/rules/agent-delivery.mdc` exists:

1. Open the repository in Cursor.
2. Manually verify that Cursor has loaded the repository's `AGENTS.md` and any
   existing rules.
3. Read the [Delivery SOP](./delivery-sop.md) before starting any work.
4. Read the relevant spec for your task.

### 5.3 Cursor Automation (Phase 8, Future)

Cursor Automation workflows are not yet active. Current design:

- Cursor Automation will listen for Issue comments from authorized humans.
- It will create branches and Draft PRs based on dispatch snapshots.
- It will NOT merge, approve, or deploy.
- It will NOT have access to production secrets.

Until Phase 8, Cursor Automation is not operational.

---

## 6. For Cursor Automation

**Not yet implemented.** This section describes the planned behavior (Phase 8).

When active, Cursor Automation will:

1. Be triggered by Issue comments from authorized human accounts.
2. Treat Issue content as untrusted input — all fields validated.
3. Create a branch with fixed dispatch snapshot and allowed paths.
4. Open a Draft PR (never Ready for Review).
5. NOT merge, approve, or deploy.

Until Phase 8 is complete, Cursor Automation does not run.

---

## 7. For Human Developers

### 7.1 First-Time Setup

```bash
# Clone the repository
git clone https://github.com/Sandape/interCraft.git
cd interCraft

# Create a feature branch (never work on master)
git checkout -b human/my-feature-branch

# Run preflight to verify environment
pwsh -File scripts/governance/preflight.ps1
```

### 7.2 Daily Workflow

1. **Sync**: `git fetch origin && git rebase origin/master`
2. **Work**: Make changes to files within your dispatch's `allowed_paths`.
3. **Preflight**: `pwsh -File scripts/governance/preflight.ps1`
4. **Test**: Run relevant tests (`npm run test`, `cd backend && uv run pytest`).
5. **Commit**: `git commit -m "feat(scope): description\n\nRefs #N"`
6. **Push**: `git push origin human/my-feature-branch`
7. **PR**: Open Draft PR via `gh pr create --draft` or GitHub web UI.
8. **Review**: Request review from a non-author human.
9. **Merge**: Squash merge after approval.

### 7.3 Do Not

- Do not push directly to `master` (forbidden by Ruleset).
- Do not approve your own PR.
- Do not merge without CI green (once Phase 7 is complete) or documented
  exception.
- Do not include credentials or secrets in any commit, Issue, or PR.

---

## 8. First Dry-Run

Complete these steps to verify your setup:

### Step 1: Fresh Clone

```bash
cd /tmp
git clone https://github.com/Sandape/interCraft.git interCraft-dryrun
cd interCraft-dryrun
```

### Step 2: Read Canonical Rules

```bash
cat AGENTS.md
cat docs/engineering/delivery-sop.md   # requires docs/engineering/ to exist
cat docs/README.md
cat specs/README.md
```

### Step 3: Verify Client Loads Rules

Ask your AI client: "What is the delivery workflow for InterCraft?"
- It should describe the Spec → Issue → Dispatch → PR → Review → Merge flow.
- It should NOT suggest direct-pushing to `master`.

### Step 4: Run Preflight on a Clean Repo

```bash
pwsh -File scripts/governance/preflight.ps1
```

Expected outcome: pass (exit 0) or a clear failure message you can interpret.

### Step 5: Create a Test Branch and Commit

```bash
git checkout -b codex/dryrun-verification
echo "# Dry run evidence" > docs/evidence/dryrun.md
git add docs/evidence/dryrun.md
git commit -m "chore: dryrun verification\n\nRefs #0"
```

### Step 6: Run Preflight Again

```bash
pwsh -File scripts/governance/preflight.ps1
```

### Step 7: Clean Up

```bash
git checkout master
git branch -D codex/dryrun-verification
rm -rf /tmp/interCraft-dryrun
```

---

## 9. Troubleshooting

### Dirty Root

**Symptom**: Preflight fails with `PREFLIGHT_DIRTY_ROOT`.

**Cause**: You have uncommitted changes in the working tree.

**Solution**:
1. Identify dirty files: `git status --porcelain`.
2. If they are your work-in-progress, commit them.
3. If they are from another context (e.g., primary clone's dirty state in a
   shared worktree), stop and classify them. Do not commit unrelated changes.
4. If using a worktree attached to a dirty primary clone, switch to a fresh
   external clone instead.

### Stale Base

**Symptom**: Preflight fails with `PREFLIGHT_BASE_MISMATCH`.

**Cause**: Your branch's base SHA no longer matches authoritative remote
`master`.

**Solution**:
```bash
# Fetch the latest master
git fetch origin master

# Rebase your branch
git rebase origin/master

# If conflicts: resolve them, then continue rebase
git rebase --continue

# If the dispatch base_sha is also stale, contact Codex for a new dispatch
```

### Red Legacy CI

**Symptom**: CI checks are red on your PR.

**Cause**: The InterCraft CI pipeline has pre-existing failures not related to
your change. CI repair is scheduled for Phase 7.

**Solution**:
1. Verify your change does not introduce new failures: run tests locally.
2. Document in the PR body which CI failures are pre-existing.
3. The reviewer will consider only your change's impact, not pre-existing CI
   state.
4. If CI repair is urgent, escalate to Codex.

### 403 / TLS Transport Failure

**Symptom**: `gh api` fails with HTTP 403 or TLS error.

**Cause**:
- Unauthenticated `gh` session.
- Network proxy blocking GitHub API.
- TLS certificate issues.
- Rate limiting.

**Solution**:
1. Verify authentication: `gh auth status`.
2. Re-authenticate: `gh auth login`.
3. If behind a proxy, configure: `gh config set git_proxy https://proxy:port`.
4. On temporary failure, preflight falls back to `git rev-parse origin/master`
   with a warning. Document this in the PR.
5. If persistent, escalate to Codex or Sandape Owner.

### Preflight Fails on a Fresh Clone

**Symptom**: Preflight reports `PREFLIGHT_WRONG_ROOT`.

**Cause**: Running preflight from outside the repository root.

**Solution**: Ensure your working directory is the repository root:
```bash
cd /path/to/interCraft
pwsh -File scripts/governance/preflight.ps1
```

### Preflight Reports Branch Is Master

**Symptom**: `PREFLIGHT_MASTER_BRANCH`.

**Cause**: You're on the `master` branch. Direct work on `master` is forbidden.

**Solution**: Create and switch to a feature branch:
```bash
git checkout -b codex/my-feature
```

### Preflight Reports Path Escape

**Symptom**: `PREFLIGHT_PATH_ESCAPE`.

**Cause**: Changed files outside the dispatch's allowed paths.

**Solution**: Revert the out-of-bounds changes. If they are necessary, contact
Codex for a dispatch with broader allowed paths.

---

## 10. When to Stop & Escalate

### Stop Immediately If:

1. **You cannot classify a dirty file.** If `git status` shows files you don't
   recognize and cannot safely categorize, stop. Do not commit, stash, or
   delete. Escalate to Codex.
2. **Preflight reports a code you don't understand.** Stop and read the
   troubleshooting section. If still unclear, escalate.
3. **Your client suggests pushing to `master`.** It has not loaded the correct
   rules. Stop and fix the client configuration.
4. **You see credentials or secrets in any file, commit, or Issue.** Stop. Do
   not push. Notify Codex and Sandape Owner immediately.

### Escalation Path

| Issue | Escalate To | Method |
|---|---|---|
| Dispatch missing or expired | Codex | Issue comment or GitHub mention |
| Ruleset bypass detected | Sandape Owner | GitHub Issue with `governance` label |
| Secret discovered in history | Sandape Owner | Notify privately; do not post in public |
| CI consistently broken for your change | Codex | PR comment with evidence |
| Infrastructure / network / auth | Codex or Sandape Owner | GitHub Issue |
| Unsure about anything | Codex | Issue comment or mention |

### When to Create a Governance Issue

Create a GitHub Issue with the `governance` label (Phase 6, future) when:

- You suspect a Ruleset drift.
- You need a break-glass deviation from standard procedure.
- You discover a systemic issue with the delivery pipeline.
- You propose a change to the governance system itself.

---

## Appendix: Quick Reference

| Need | Command or Action |
|---|---|
| Fresh clone | `git clone https://github.com/Sandape/interCraft.git` |
| Create worktree | `git worktree add ../<name> <branch>` |
| Run preflight | `pwsh -File scripts/governance/preflight.ps1` |
| Get authoritative master SHA | `gh api repos/Sandape/interCraft/git/ref/heads/master --jq '.object.sha'` |
| Open Draft PR | `gh pr create --base master --draft --title "..." --body "Refs #N"` |
| Rebase onto master | `git fetch origin master && git rebase origin/master` |
| Rollback a merge | `git revert -m 1 <merge-sha>` |
| Read the full SOP | [docs/engineering/delivery-sop.md](./delivery-sop.md) |
| Read AGENTS.md | `cat ../../AGENTS.md` |
| Read specs index | `cat ../../specs/README.md` |
